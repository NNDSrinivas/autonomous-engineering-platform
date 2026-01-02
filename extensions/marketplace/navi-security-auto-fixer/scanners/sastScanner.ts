/**
 * Static Application Security Testing (SAST) Scanner
 * 
 * Performs static code analysis to detect security vulnerabilities in source code.
 * Focuses on common vulnerability patterns like injection, weak crypto, etc.
 */

import { RepositoryAPI, SecurityFinding, VulnerabilityType, SeverityLevel, FindingSource } from '../types';

/**
 * Security vulnerability patterns to detect in code
 */
interface VulnerabilityPattern {
    /** Regex pattern to match */
    pattern: RegExp;

    /** Type of vulnerability */
    type: VulnerabilityType;

    /** Severity level */
    severity: SeverityLevel;

    /** Human-readable description */
    description: string;

    /** File extensions to scan */
    fileExtensions: string[];

    /** Confidence level (0.0 - 1.0) */
    confidence: number;

    /** Remediation advice */
    remediation: string;
}

/**
 * Known vulnerability patterns across different languages
 */
const VULNERABILITY_PATTERNS: VulnerabilityPattern[] = [
    // SQL Injection patterns
    {
        pattern: /(db\.query|query|execute)\([^)]*\+\s*(req|request)\.(params|body|query)[^)]+\)|query\s*=.*\+.*(req|request)\.|query.*%.*(req|request)\.|execute\(.*%.*\)|cursor\.execute\([^)]*%[^)]*\)/gi,
        type: VulnerabilityType.INJECTION,
        severity: SeverityLevel.HIGH,
        description: 'SQL Injection vulnerability',
        fileExtensions: ['.py', '.js', '.ts', '.java', '.php'],
        confidence: 0.85,
        remediation: 'Use parameterized queries or prepared statements'
    },

    // Command Injection
    {
        pattern: /os\.system\(.*input|subprocess\.call\(.*input|exec\(.*input|eval\(.*input/gi,
        type: VulnerabilityType.INJECTION,
        severity: SeverityLevel.CRITICAL,
        description: 'Command injection vulnerability',
        fileExtensions: ['.py', '.js', '.ts'],
        confidence: 0.85,
        remediation: 'Sanitize user input and use safe alternatives'
    },

    // XSS vulnerabilities
    {
        pattern: /innerHTML\s*=.*request\.|document\.write\(.*request\.|\.html\(.*request\./gi,
        type: VulnerabilityType.INJECTION,
        severity: SeverityLevel.HIGH,
        description: 'Cross-site scripting (XSS) vulnerability',
        fileExtensions: ['.js', '.ts', '.html'],
        confidence: 0.75,
        remediation: 'Escape user input and use safe DOM manipulation methods'
    },

    // Weak cryptography
    {
        pattern: /hashlib\.md5\(|hashlib\.sha1\(|crypto\.createHash\(['"]md5['"]|crypto\.createHash\(['"]sha1['"]/gi,
        type: VulnerabilityType.WEAK_CRYPTO,
        severity: SeverityLevel.MEDIUM,
        description: 'Weak Cryptographic Hash',
        fileExtensions: ['.py', '.js', '.ts'],
        confidence: 0.9,
        remediation: 'Use SHA-256 or stronger hash functions'
    },

    // Insecure random number generation
    {
        pattern: /Math\.random\(\)|random\.random\(\)/gi,
        type: VulnerabilityType.WEAK_CRYPTO,
        severity: SeverityLevel.MEDIUM,
        description: 'Use of cryptographically weak random number generator',
        fileExtensions: ['.js', '.ts', '.py'],
        confidence: 0.7,
        remediation: 'Use cryptographically secure random number generators'
    },

    // Insecure deserialization
    {
        pattern: /pickle\.loads\(|pickle\.load\(|yaml\.load\([^,]*\)|JSON\.parse\(.*request\./gi,
        type: VulnerabilityType.INSECURE_DESERIALIZATION,
        severity: SeverityLevel.HIGH,
        description: 'Potentially unsafe deserialization',
        fileExtensions: ['.py', '.js', '.ts'],
        confidence: 0.8,
        remediation: 'Validate input and use safe deserialization methods'
    },

    // Hardcoded secrets/credentials
    {
        pattern: /(password|secret|key|token)\s*=\s*['"][^'"]{8,}['"]/gi,
        type: VulnerabilityType.SECRET_EXPOSURE,
        severity: SeverityLevel.HIGH,
        description: 'Potential hardcoded credential',
        fileExtensions: ['.py', '.js', '.ts', '.java', '.php', '.rb'],
        confidence: 0.6,
        remediation: 'Use environment variables or secure credential stores'
    },

    // HTTP security headers missing (in configuration)
    {
        pattern: /app\.use\(.*helmet.*\)|response\.headers\['X-Frame-Options'\]|response\.headers\['X-Content-Type-Options'\]/gi,
        type: VulnerabilityType.CONFIGURATION,
        severity: SeverityLevel.LOW,
        description: 'Missing security headers configuration',
        fileExtensions: ['.js', '.ts'],
        confidence: 0.5,
        remediation: 'Add security headers like X-Frame-Options, X-Content-Type-Options'
    }
];

/**
 * Perform static application security testing on repository
 */
export async function scanWithSAST(repo: RepositoryAPI): Promise<SecurityFinding[]> {
    const findings: SecurityFinding[] = [];

    try {
        // Get list of source code files
        const sourceFiles = await getSourceFiles(repo);

        if (!sourceFiles.length) {
            console.log('🔍 No source files found for SAST scanning');
            return findings;
        }

        console.log(`🔍 SAST scanning ${sourceFiles.length} source files...`);

        // Scan each file for vulnerability patterns
        for (const filePath of sourceFiles) {
            try {
                const content = await repo.readFile(filePath);
                const fileFindings = scanFileContent(filePath, content);
                findings.push(...fileFindings);

                if (fileFindings.length > 0) {
                    console.log(`⚠️  Found ${fileFindings.length} potential vulnerabilities in ${filePath}`);
                }

            } catch (error) {
                console.warn(`⚠️  Could not scan ${filePath}:`, error);
            }
        }

        console.log(`📊 SAST scan complete: ${findings.length} potential vulnerabilities found`);
        return findings;

    } catch (error) {
        console.error('❌ SAST scanning failed:', error);
        throw new Error(`SAST scanning failed: ${error}`);
    }
}

/**
 * Get list of source code files to scan
 */
async function getSourceFiles(repo: RepositoryAPI): Promise<string[]> {
    const filePatterns = [
        '**/*.js',
        '**/*.ts',
        '**/*.py',
        '**/*.java',
        '**/*.php',
        '**/*.rb',
        '**/*.go',
        '**/*.cs'
    ];

    const allFiles: string[] = [];

    for (const pattern of filePatterns) {
        try {
            const files = await repo.listFiles(pattern);
            allFiles.push(...files);
        } catch (error) {
            // Pattern might not be supported, continue with others
            console.warn(`⚠️  Could not list files with pattern ${pattern}:`, error);
        }
    }

    // Filter out test files, node_modules, etc.
    return allFiles.filter(file => {
        const lowercasePath = file.toLowerCase();
        return !lowercasePath.includes('node_modules') &&
            !lowercasePath.includes('test') &&
            !lowercasePath.includes('spec') &&
            !lowercasePath.includes('.min.') &&
            !lowercasePath.includes('vendor/') &&
            !lowercasePath.includes('build/') &&
            !lowercasePath.includes('dist/');
    });
}

/**
 * Scan individual file content for vulnerabilities
 */
function scanFileContent(filePath: string, content: string): SecurityFinding[] {
    const findings: SecurityFinding[] = [];
    const fileExtension = getFileExtension(filePath);

    // Check each vulnerability pattern
    for (const pattern of VULNERABILITY_PATTERNS) {
        if (!pattern.fileExtensions.includes(fileExtension)) {
            continue; // Skip patterns not applicable to this file type
        }

        const matches = [...content.matchAll(pattern.pattern)];

        for (const match of matches) {
            const lineNumber = getLineNumber(content, match.index || 0);
            const codeSnippet = getCodeSnippet(content, lineNumber);

            const finding: SecurityFinding = {
                id: `${filePath}-${pattern.type}-${lineNumber}`,
                type: pattern.type,
                severity: pattern.severity,
                cveIds: [], // SAST findings don't have CVEs
                component: filePath,
                filePath,
                lineNumber,
                title: `${pattern.description} in ${filePath}`,
                description: `${pattern.description}. ${pattern.remediation}`,
                evidence: [
                    {
                        type: 'CODE_PATTERN',
                        content: codeSnippet,
                        filePath,
                        lineRange: [Math.max(1, lineNumber - 2), lineNumber + 2]
                    }
                ],
                source: FindingSource.SAST_SCANNER,
                confidence: pattern.confidence,
                detectedAt: new Date().toISOString()
            };

            findings.push(finding);
        }
    }

    return findings;
}

/**
 * Get file extension from path
 */
function getFileExtension(filePath: string): string {
    const lastDot = filePath.lastIndexOf('.');
    return lastDot >= 0 ? filePath.substring(lastDot) : '';
}

/**
 * Get line number for character index in content
 */
function getLineNumber(content: string, charIndex: number): number {
    const upToIndex = content.substring(0, charIndex);
    return upToIndex.split('\n').length;
}

/**
 * Get code snippet around specified line
 */
function getCodeSnippet(content: string, lineNumber: number): string {
    const lines = content.split('\n');
    const start = Math.max(0, lineNumber - 3);
    const end = Math.min(lines.length, lineNumber + 2);

    return lines
        .slice(start, end)
        .map((line, i) => {
            const actualLineNum = start + i + 1;
            const marker = actualLineNum === lineNumber ? '> ' : '  ';
            return `${marker}${actualLineNum}: ${line}`;
        })
        .join('\n');
}

/**
 * Check if pattern is a likely false positive
 * (Removed unused function to fix compilation)
 */

/**
 * Get severity adjustment based on file location and context
 * (Removed unused function to fix compilation)
 */
