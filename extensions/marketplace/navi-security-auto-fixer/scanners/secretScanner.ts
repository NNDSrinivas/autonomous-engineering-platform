/**
 * Secret Scanner
 * 
 * Scans source code and configuration files for exposed secrets, API keys,
 * credentials, and other sensitive information that should not be committed.
 */

import { RepositoryAPI, SecurityFinding, VulnerabilityType, SeverityLevel, FindingSource } from '../types';

/**
 * Secret detection pattern
 */
interface SecretPattern {
    /** Pattern name/type */
    name: string;

    /** Regex pattern to match secrets */
    pattern: RegExp;

    /** Severity level */
    severity: SeverityLevel;

    /** Description */
    description: string;

    /** Confidence level */
    confidence: number;

    /** Remediation advice */
    remediation: string;
}

/**
 * Known secret patterns to detect
 */
const SECRET_PATTERNS: SecretPattern[] = [
    // AWS Access Keys
    {
        name: 'AWS Access Key ID',
        pattern: /AKIA[0-9A-Z]{16}/g,
        severity: SeverityLevel.CRITICAL,
        description: 'AWS Access Key ID detected',
        confidence: 0.95,
        remediation: 'Rotate AWS credentials immediately and use IAM roles or environment variables'
    },

    // AWS Secret Access Key
    {
        name: 'AWS Secret Access Key',
        pattern: /aws(.{0,20})?['\"][0-9a-zA-Z\/+]{40}['\"]/gi,
        severity: SeverityLevel.CRITICAL,
        description: 'AWS Secret Access Key detected',
        confidence: 0.9,
        remediation: 'Rotate AWS credentials immediately and use secure credential storage'
    },

    // Google API Key
    {
        name: 'Google API Key',
        pattern: /AIza[0-9A-Za-z\\-_]{35}/g,
        severity: SeverityLevel.HIGH,
        description: 'Google API Key detected',
        confidence: 0.9,
        remediation: 'Rotate Google API key and use environment variables'
    },

    // GitHub Token
    {
        name: 'GitHub Token',
        pattern: /gh[ps]_[a-zA-Z0-9]{36}/g,
        severity: SeverityLevel.HIGH,
        description: 'GitHub Personal Access Token detected',
        confidence: 0.95,
        remediation: 'Rotate GitHub token immediately and use secure storage'
    },

    // Generic API Key patterns
    {
        name: 'API Key',
        pattern: /\bAPI_KEY\s*=\s*[a-zA-Z0-9_-]{8,}/gi,
        severity: SeverityLevel.HIGH,
        description: 'API key detected',
        confidence: 0.85,
        remediation: 'Move API keys to environment variables or a secret manager'
    },
    {
        name: 'Generic API Key',
        pattern: /(api[_-]?key|apikey|secret[_-]?key|secretkey)['"]\s*[:=]\s*['"][a-zA-Z0-9]{20,}['"]/gi,
        severity: SeverityLevel.HIGH,
        description: 'Potential API key or secret detected',
        confidence: 0.7,
        remediation: 'Move sensitive keys to environment variables or secure credential store'
    },

    // Database connection strings
    {
        name: 'Database Connection String',
        pattern: /(password|pwd)['"]\s*[:=]\s*['"][^'"]{3,}['"]|mysql:\/\/[^:]+:[^@]+@|postgresql:\/\/[^:]+:[^@]+@/gi,
        severity: SeverityLevel.HIGH,
        description: 'Database credential in connection string detected',
        confidence: 0.8,
        remediation: 'Use environment variables for database credentials'
    },

    // JWT Tokens
    {
        name: 'JWT Token',
        pattern: /eyJ[a-zA-Z0-9]{10,}\.[a-zA-Z0-9]{10,}\.[a-zA-Z0-9_-]{10,}/g,
        severity: SeverityLevel.MEDIUM,
        description: 'JSON Web Token detected',
        confidence: 0.8,
        remediation: 'Ensure JWT tokens are not hardcoded and have proper expiration'
    },

    // Private Key patterns
    {
        name: 'Private Key',
        pattern: /-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----/g,
        severity: SeverityLevel.CRITICAL,
        description: 'Private key detected',
        confidence: 0.95,
        remediation: 'Remove private key from code and use secure key management'
    },

    // Generic passwords
    {
        name: 'Hardcoded Password',
        pattern: /(password|passwd|pwd)['"]\s*[:=]\s*['"][^'"]{6,}['"]/gi,
        severity: SeverityLevel.MEDIUM,
        description: 'Potential hardcoded password detected',
        confidence: 0.6,
        remediation: 'Use environment variables or secure credential storage for passwords'
    },

    // Slack Tokens
    {
        name: 'Slack Token',
        pattern: /xox[baprs]-[0-9a-zA-Z-]+/g,
        severity: SeverityLevel.HIGH,
        description: 'Slack API token detected',
        confidence: 0.9,
        remediation: 'Rotate Slack token and use environment variables'
    },

    // Discord Tokens
    {
        name: 'Discord Token',
        pattern: /[MN][a-zA-Z\d]{23}\.[a-zA-Z\d]{6}\.[a-zA-Z\d_\-]{27}/g,
        severity: SeverityLevel.HIGH,
        description: 'Discord bot token detected',
        confidence: 0.9,
        remediation: 'Rotate Discord token immediately'
    }
];

/**
 * Files that commonly contain secrets
 */
const SECRET_PRONE_FILES = [
    '.env',
    '.env.local',
    '.env.production',
    'config.json',
    'settings.py',
    'application.properties',
    'application.yml',
    'docker-compose.yml'
];

/**
 * Scan repository for exposed secrets and credentials
 */
export async function scanSecrets(repo: RepositoryAPI): Promise<SecurityFinding[]> {
    const findings: SecurityFinding[] = [];

    try {
        // Get all files to scan
        const filesToScan = await getFilesToScan(repo);

        if (!filesToScan.length) {
            console.log('🔑 No files found for secret scanning');
            return findings;
        }

        console.log(`🔍 Secret scanning ${filesToScan.length} files...`);

        // Scan each file for secret patterns
        for (const filePath of filesToScan) {
            try {
                const content = await repo.readFile(filePath);
                const fileFindings = scanFileForSecrets(filePath, content);
                findings.push(...fileFindings);

                if (fileFindings.length > 0) {
                    console.log(`🚨 Found ${fileFindings.length} potential secrets in ${filePath}`);
                }

            } catch (error) {
                console.warn(`⚠️  Could not scan ${filePath} for secrets:`, error);
            }
        }

        console.log(`📊 Secret scan complete: ${findings.length} potential secrets found`);
        return findings;

    } catch (error) {
        console.error('❌ Secret scanning failed:', error);
        throw new Error(`Secret scanning failed: ${error}`);
    }
}

/**
 * Get list of files to scan for secrets
 */
async function getFilesToScan(repo: RepositoryAPI): Promise<string[]> {
    const filePatterns = [
        '**/*.js',
        '**/*.ts',
        '**/*.py',
        '**/*.java',
        '**/*.php',
        '**/*.rb',
        '**/*.go',
        '**/*.cs',
        '**/*.json',
        '**/*.yml',
        '**/*.yaml',
        '**/*.env*',
        '**/config.*',
        '**/settings.*'
    ];

    const allFiles: string[] = [];

    for (const pattern of filePatterns) {
        try {
            const files = await repo.listFiles(pattern);
            allFiles.push(...files);
        } catch (error) {
            console.warn(`⚠️  Could not list files with pattern ${pattern}:`, error);
        }
    }

    // Filter and prioritize files
    const filteredFiles = allFiles.filter(file => {
        const lowercasePath = file.toLowerCase();

        // Skip obviously safe files
        if (lowercasePath.includes('node_modules') ||
            lowercasePath.includes('.git/') ||
            lowercasePath.includes('build/') ||
            lowercasePath.includes('dist/') ||
            lowercasePath.includes('.min.')) {
            return false;
        }

        return true;
    });

    // Prioritize secret-prone files
    return filteredFiles.sort((a, b) => {
        const aIsProne = SECRET_PRONE_FILES.some(prone => a.includes(prone));
        const bIsProne = SECRET_PRONE_FILES.some(prone => b.includes(prone));

        if (aIsProne && !bIsProne) return -1;
        if (!aIsProne && bIsProne) return 1;
        return 0;
    });
}

/**
 * Scan individual file for secret patterns
 */
function scanFileForSecrets(filePath: string, content: string): SecurityFinding[] {
    const findings: SecurityFinding[] = [];

    for (const pattern of SECRET_PATTERNS) {
        const matches = [...content.matchAll(pattern.pattern)];

        for (const match of matches) {
            // Apply false positive filtering
            if (isLikelyFalsePositive(filePath, match[0], pattern)) {
                continue;
            }

            const lineNumber = getLineNumber(content, match.index || 0);
            const codeSnippet = getRedactedCodeSnippet(content, lineNumber);

            const finding: SecurityFinding = {
                id: `${filePath}-secret-${pattern.name}-${lineNumber}`,
                type: VulnerabilityType.SECRET_EXPOSURE,
                severity: adjustSeverityByFile(filePath, pattern.severity),
                cveIds: [], // Secret findings don't have CVEs
                component: filePath,
                filePath,
                lineNumber,
                title: `${pattern.name} exposed in ${filePath}`,
                description: `${pattern.description}. Detected value: [REDACTED]. ${pattern.remediation}`,
                evidence: [
                    {
                        type: 'CODE_PATTERN',
                        content: codeSnippet,
                        filePath,
                        lineRange: [Math.max(1, lineNumber - 1), lineNumber + 1]
                    }
                ],
                source: FindingSource.SECRET_SCANNER,
                confidence: pattern.confidence,
                detectedAt: new Date().toISOString()
            };

            findings.push(finding);
        }
    }

    return findings;
}

/**
 * Check if match is likely a false positive
 */
function isLikelyFalsePositive(filePath: string, match: string, _pattern: SecretPattern): boolean {
    const lowerPath = filePath.toLowerCase();

    // Skip test files with dummy secrets
    if (filePath.includes('test') || filePath.includes('spec')) {
        const testIndicators = ['test', 'dummy', 'fake', 'mock', 'example', 'sample'];
        if (testIndicators.some(indicator => match.toLowerCase().includes(indicator))) {
            return true;
        }
    }

    // Skip documentation files
    if (filePath.includes('README') || filePath.includes('doc') || filePath.includes('.md')) {
        return true;
    }

    // Skip comments
    if (match.trim().startsWith('//') || match.trim().startsWith('#') || match.trim().startsWith('/*')) {
        return true;
    }

    // Skip common false positive patterns
    if (SECRET_PRONE_FILES.some(prone => lowerPath.includes(prone))) {
        return false;
    }

    const falsePositivePatterns = [
        'your-api-key-here',
        'insert-key-here',
        'replace-with',
        'example.com',
        'localhost',
        '127.0.0.1'
    ];

    return falsePositivePatterns.some(fp => match.toLowerCase().includes(fp));
}

/**
 * Adjust severity based on file location
 */
function adjustSeverityByFile(filePath: string, baseSeverity: SeverityLevel): SeverityLevel {
    // More severe in configuration files
    if (SECRET_PRONE_FILES.some(prone => filePath.includes(prone))) {
        return baseSeverity;
    }

    // More severe in production paths
    if (filePath.includes('prod') || filePath.includes('production')) {
        return baseSeverity;
    }

    // Less severe in test/development files
    if (filePath.includes('test') || filePath.includes('dev') || filePath.includes('example')) {
        const severityMap: Record<SeverityLevel, SeverityLevel> = {
            [SeverityLevel.CRITICAL]: SeverityLevel.HIGH,
            [SeverityLevel.HIGH]: SeverityLevel.MEDIUM,
            [SeverityLevel.MEDIUM]: SeverityLevel.LOW,
            [SeverityLevel.LOW]: SeverityLevel.INFO,
            [SeverityLevel.INFO]: SeverityLevel.INFO
        };
        return severityMap[baseSeverity];
    }

    return baseSeverity;
}

/**
 * Get line number for character index
 */
function getLineNumber(content: string, charIndex: number): number {
    const upToIndex = content.substring(0, charIndex);
    return upToIndex.split('\n').length;
}

/**
 * Get redacted code snippet (hide actual secret values)
 */
function getRedactedCodeSnippet(content: string, lineNumber: number): string {
    const lines = content.split('\n');
    const start = Math.max(0, lineNumber - 2);
    const end = Math.min(lines.length, lineNumber + 1);

    return lines
        .slice(start, end)
        .map((line, i) => {
            const actualLineNum = start + i + 1;
            const marker = actualLineNum === lineNumber ? '> ' : '  ';

            // Redact sensitive values on the target line
            let displayLine = line;
            if (actualLineNum === lineNumber) {
                // Basic redaction - replace potential secrets with [REDACTED]
                displayLine = line.replace(/['"]\s*[:=]\s*['"][^'"]{6,}['"]/, '"[REDACTED]"');
                displayLine = displayLine.replace(/=\s*[^'"\s]{6,}/, '= [REDACTED]');
                displayLine = displayLine.replace(/[a-zA-Z0-9\/+]{20,}/, '[REDACTED]');
            }

            return `${marker}${actualLineNum}: ${displayLine}`;
        })
        .join('\n');
}
