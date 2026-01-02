/**
 * CI Security Reader
 * 
 * Reads and parses security scan results from CI/CD pipelines.
 * Integrates with popular security tools and CI systems.
 */

import { CISecurityAPI, SecurityFinding, VulnerabilityType, FindingSource, CISecurityReport } from '../types';

/**
 * Supported CI security tools and their report formats
 */
const SECURITY_TOOLS = {
    GITHUB_SECURITY: 'github-security',
    SNYK: 'snyk',
    SONARQUBE: 'sonarqube',
    BANDIT: 'bandit',
    ESLINT_SECURITY: 'eslint-security',
    SEMGREP: 'semgrep',
    CODEQL: 'codeql'
};

/**
 * Read security findings from CI/CD security reports
 */
export async function readCISecurity(ciAPI: CISecurityAPI): Promise<SecurityFinding[]> {
    const findings: SecurityFinding[] = [];

    try {
        console.log('🏗️  Reading CI/CD security reports...');

        // Get security reports from CI system
        const reports = await ciAPI.getSecurityReports();

        if (!reports.length) {
            console.log('📋 No CI security reports found');
            return findings;
        }

        console.log(`📊 Processing ${reports.length} CI security reports...`);

        // Process each security report
        for (const report of reports) {
            try {
                const reportFindings = parseSecurityReport(report);
                findings.push(...reportFindings);

                console.log(`✅ Processed ${report.source}: ${reportFindings.length} findings`);

            } catch (error) {
                console.warn(`⚠️  Failed to process report from ${report.source}:`, error);
            }
        }

        console.log(`📈 CI security integration complete: ${findings.length} findings from CI reports`);
        return findings;

    } catch (error) {
        console.error('❌ CI security reading failed:', error);
        throw new Error(`CI security reading failed: ${error}`);
    }
}

// Backwards-compatible alias for older call sites
export const readCISecurityReports = readCISecurity;

/**
 * Parse individual security report based on tool format
 */
function parseSecurityReport(report: CISecurityReport): SecurityFinding[] {
    const toolType = identifySecurityTool(report.source);

    switch (toolType) {
        case SECURITY_TOOLS.GITHUB_SECURITY:
            return parseGitHubSecurityReport(report);
        case SECURITY_TOOLS.SNYK:
            return parseSnykReport(report);
        case SECURITY_TOOLS.SONARQUBE:
            return parseSonarQubeReport(report);
        case SECURITY_TOOLS.BANDIT:
            return parseBanditReport(report);
        case SECURITY_TOOLS.SEMGREP:
            return parseSemgrepReport(report);
        case SECURITY_TOOLS.CODEQL:
            return parseCodeQLReport(report);
        default:
            return parseGenericReport(report);
    }
}

/**
 * Identify security tool type from report source
 */
function identifySecurityTool(source: string): string {
    const sourceLower = source.toLowerCase();

    if (sourceLower.includes('github') || sourceLower.includes('dependabot')) {
        return SECURITY_TOOLS.GITHUB_SECURITY;
    }
    if (sourceLower.includes('snyk')) {
        return SECURITY_TOOLS.SNYK;
    }
    if (sourceLower.includes('sonar')) {
        return SECURITY_TOOLS.SONARQUBE;
    }
    if (sourceLower.includes('bandit')) {
        return SECURITY_TOOLS.BANDIT;
    }
    if (sourceLower.includes('semgrep')) {
        return SECURITY_TOOLS.SEMGREP;
    }
    if (sourceLower.includes('codeql')) {
        return SECURITY_TOOLS.CODEQL;
    }

    return 'generic';
}

/**
 * Parse GitHub Security/Dependabot report
 */
function parseGitHubSecurityReport(report: CISecurityReport): SecurityFinding[] {
    // GitHub reports typically include dependency vulnerabilities
    return report.findings.map(finding => ({
        ...finding,
        id: `github-${finding.id}`,
        source: FindingSource.CI_SECURITY,
        detectedAt: report.timestamp
    }));
}

/**
 * Parse Snyk vulnerability report
 */
function parseSnykReport(report: CISecurityReport): SecurityFinding[] {
    return report.findings.map(finding => {
        // Snyk provides excellent vulnerability data
        return {
            ...finding,
            id: `snyk-${finding.id}`,
            source: FindingSource.CI_SECURITY,
            confidence: 0.9, // Snyk has high accuracy
            detectedAt: report.timestamp
        };
    });
}

/**
 * Parse SonarQube security report  
 */
function parseSonarQubeReport(report: CISecurityReport): SecurityFinding[] {
    return report.findings.map(finding => {
        // SonarQube focuses on code quality and security hotspots
        let mappedType = VulnerabilityType.CODE_VULNERABILITY;

        if (finding.title?.includes('SQL')) {
            mappedType = VulnerabilityType.INJECTION;
        } else if (finding.title?.includes('crypto') || finding.title?.includes('hash')) {
            mappedType = VulnerabilityType.WEAK_CRYPTO;
        } else if (finding.title?.includes('secret') || finding.title?.includes('credential')) {
            mappedType = VulnerabilityType.SECRET_EXPOSURE;
        }

        return {
            ...finding,
            type: mappedType,
            id: `sonar-${finding.id}`,
            source: FindingSource.CI_SECURITY,
            confidence: 0.8, // SonarQube has good accuracy but some false positives
            detectedAt: report.timestamp
        };
    });
}

/**
 * Parse Bandit (Python security) report
 */
function parseBanditReport(report: CISecurityReport): SecurityFinding[] {
    return report.findings.map(finding => {
        // Bandit specializes in Python security issues
        let mappedType = VulnerabilityType.CODE_VULNERABILITY;

        if (finding.description?.includes('injection')) {
            mappedType = VulnerabilityType.INJECTION;
        } else if (finding.description?.includes('deserialization')) {
            mappedType = VulnerabilityType.INSECURE_DESERIALIZATION;
        } else if (finding.description?.includes('hash') || finding.description?.includes('crypto')) {
            mappedType = VulnerabilityType.WEAK_CRYPTO;
        }

        return {
            ...finding,
            type: mappedType,
            id: `bandit-${finding.id}`,
            source: FindingSource.CI_SECURITY,
            confidence: 0.85, // Bandit is quite accurate for Python
            detectedAt: report.timestamp
        };
    });
}

/**
 * Parse Semgrep security report
 */
function parseSemgrepReport(report: CISecurityReport): SecurityFinding[] {
    return report.findings.map(finding => {
        // Semgrep uses rule-based detection with high precision
        return {
            ...finding,
            id: `semgrep-${finding.id}`,
            source: FindingSource.CI_SECURITY,
            confidence: 0.9, // Semgrep rules are typically high quality
            detectedAt: report.timestamp
        };
    });
}

/**
 * Parse CodeQL security report
 */
function parseCodeQLReport(report: CISecurityReport): SecurityFinding[] {
    return report.findings.map(finding => {
        // CodeQL provides high-quality semantic analysis
        return {
            ...finding,
            id: `codeql-${finding.id}`,
            source: FindingSource.CI_SECURITY,
            confidence: 0.95, // CodeQL has very high accuracy
            detectedAt: report.timestamp
        };
    });
}

/**
 * Parse generic/unknown security report format
 */
function parseGenericReport(report: CISecurityReport): SecurityFinding[] {
    return report.findings.map(finding => ({
        ...finding,
        id: `ci-${finding.source}-${finding.id}`,
        source: FindingSource.CI_SECURITY,
        confidence: Math.max(0.5, finding.confidence || 0.7), // Conservative confidence
        detectedAt: report.timestamp
    }));
}

/**
 * Normalize severity from CI tool format to our standard
 * (Removed unused function to fix compilation)
 */

/**
 * Extract CVE IDs from CI report descriptions
 * (Function removed to fix compilation - available in future versions)
 */

/**
 * Enhance finding with CI context information
 * (Functions removed to fix compilation - available in future versions)
 */
