/**
 * Severity Classification
 * 
 * Deterministic severity classification system that adjusts finding severity 
 * based on context, exploitability, and business impact.
 */

import { SecurityFinding, SeverityLevel, VulnerabilityType } from '../types';

/**
 * Severity scoring weights
 */
const SEVERITY_WEIGHTS = {
    BASE_SEVERITY: 0.4,
    EXPLOITABILITY: 0.25,
    IMPACT: 0.2,
    CONFIDENCE: 0.1,
    CONTEXT: 0.05
};

const CVE_SEVERITY_OVERRIDES: Record<string, SeverityLevel> = {
    'CVE-2022-24999': SeverityLevel.HIGH,
    'CVE-2019-10744': SeverityLevel.HIGH,
    'CVE-2020-8203': SeverityLevel.HIGH
};

/**
 * Classify and potentially adjust finding severity based on comprehensive analysis
 */
export function classifySeverity(finding: SecurityFinding): SeverityLevel {
    // Start with base severity
    let severityScore = getSeverityScore(finding.severity);

    // Apply exploitability modifier
    const exploitabilityModifier = getExploitabilityModifier(finding);
    severityScore += exploitabilityModifier * SEVERITY_WEIGHTS.EXPLOITABILITY;

    // Apply impact modifier
    const impactModifier = getImpactModifier(finding);
    severityScore += impactModifier * SEVERITY_WEIGHTS.IMPACT;

    // Apply confidence modifier
    const confidenceModifier = getConfidenceModifier(finding);
    severityScore += confidenceModifier * SEVERITY_WEIGHTS.CONFIDENCE;

    // Apply context modifier
    const contextModifier = getContextModifier(finding);
    severityScore += contextModifier * SEVERITY_WEIGHTS.CONTEXT;

    // Convert score back to severity level
    let adjustedSeverity = scoreToSeverity(severityScore);

    const overrideSeverity = getCVEOverrideSeverity(finding.cveIds);
    if (overrideSeverity) {
        adjustedSeverity = maxSeverity(adjustedSeverity, overrideSeverity);
    }

    // Log adjustment if severity changed significantly
    if (adjustedSeverity !== finding.severity) {
        console.log(`📊 Severity adjusted for ${finding.id}: ${finding.severity} → ${adjustedSeverity}`);
    }

    return adjustedSeverity;
}

/**
 * Convert severity level to numeric score (0-4)
 */
function getSeverityScore(severity: SeverityLevel): number {
    const scores = {
        [SeverityLevel.INFO]: 0,
        [SeverityLevel.LOW]: 1,
        [SeverityLevel.MEDIUM]: 2,
        [SeverityLevel.HIGH]: 3,
        [SeverityLevel.CRITICAL]: 4
    };
    return scores[severity] || 2;
}

/**
 * Convert numeric score back to severity level
 */
function scoreToSeverity(score: number): SeverityLevel {
    if (score >= 3.5) return SeverityLevel.CRITICAL;
    if (score >= 2.5) return SeverityLevel.HIGH;
    if (score >= 1.5) return SeverityLevel.MEDIUM;
    if (score >= 0.5) return SeverityLevel.LOW;
    return SeverityLevel.INFO;
}

function getCVEOverrideSeverity(cveIds?: string[]): SeverityLevel | null {
    if (!cveIds || cveIds.length === 0) {
        return null;
    }

    let override: SeverityLevel | null = null;
    for (const cve of cveIds) {
        const mapped = CVE_SEVERITY_OVERRIDES[cve];
        if (mapped) {
            override = override ? maxSeverity(override, mapped) : mapped;
        }
    }

    return override;
}

function maxSeverity(a: SeverityLevel, b: SeverityLevel): SeverityLevel {
    return getSeverityScore(a) >= getSeverityScore(b) ? a : b;
}

/**
 * Get exploitability modifier based on vulnerability type and characteristics
 */
function getExploitabilityModifier(finding: SecurityFinding): number {
    let modifier = 0;

    // Vulnerability type impact on exploitability
    const typeModifiers = {
        [VulnerabilityType.INJECTION]: 1.5,              // Very exploitable
        [VulnerabilityType.SECRET_EXPOSURE]: 1.0,        // Directly exploitable
        [VulnerabilityType.INSECURE_DESERIALIZATION]: 1.2, // Highly exploitable
        [VulnerabilityType.WEAK_CRYPTO]: 0.5,            // Less directly exploitable
        [VulnerabilityType.CONFIGURATION]: 0.7,           // Context dependent
        [VulnerabilityType.DEPENDENCY]: 0.8,              // Depends on usage
        [VulnerabilityType.CODE_VULNERABILITY]: 0.9       // Varies widely
    };

    modifier += typeModifiers[finding.type] || 0.5;

    // CVE presence increases exploitability confidence
    if (finding.cveIds && finding.cveIds.length > 0) {
        modifier += 0.3;

        // Multiple CVEs indicate more severe/exploitable issues
        if (finding.cveIds.length > 1) {
            modifier += 0.2;
        }
    }

    // Public exploits available (inferred from description keywords)
    if (hasPublicExploit(finding)) {
        modifier += 0.5;
    }

    // Remote exploitation possible
    if (isRemotelyExploitable(finding)) {
        modifier += 0.4;
    }

    // Authentication bypass potential
    if (bypassesAuthentication(finding)) {
        modifier += 0.3;
    }

    return Math.min(2.0, modifier); // Cap at +2.0
}

/**
 * Get business impact modifier
 */
function getImpactModifier(finding: SecurityFinding): number {
    let modifier = 0;

    // File location impact
    const locationModifier = getLocationImpactModifier(finding.filePath);
    modifier += locationModifier;

    // Component criticality
    const componentModifier = getComponentImpactModifier(finding.component);
    modifier += componentModifier;

    // Data confidentiality impact
    if (affectsDataConfidentiality(finding)) {
        modifier += 0.4;
    }

    // System integrity impact
    if (affectsSystemIntegrity(finding)) {
        modifier += 0.3;
    }

    // Service availability impact
    if (affectsAvailability(finding)) {
        modifier += 0.3;
    }

    return Math.min(1.5, modifier); // Cap at +1.5
}

/**
 * Get location-based impact modifier
 */
function getLocationImpactModifier(filePath?: string): number {
    if (!filePath) return 0;

    const path = filePath.toLowerCase();

    // Production code paths
    if (path.includes('src/') || path.includes('lib/') || path.includes('app/')) {
        return 0.3;
    }

    // Authentication/authorization modules
    if (path.includes('auth') || path.includes('login') || path.includes('security')) {
        return 0.5;
    }

    // API endpoints
    if (path.includes('api/') || path.includes('endpoint') || path.includes('route')) {
        return 0.4;
    }

    // Database access layers
    if (path.includes('db/') || path.includes('database') || path.includes('model')) {
        return 0.4;
    }

    // Configuration files
    if (path.includes('config') || path.includes('settings') || path.includes('.env')) {
        return 0.3;
    }

    // Test files (lower impact)
    if (path.includes('test') || path.includes('spec')) {
        return -0.2;
    }

    return 0;
}

/**
 * Get component-based impact modifier
 */
function getComponentImpactModifier(component: string): number {
    const comp = component.toLowerCase();

    // High-impact components
    const highImpactComponents = [
        'express', 'fastify', 'koa',           // Web frameworks
        'passport', 'jsonwebtoken', 'bcrypt',  // Auth libraries
        'sequelize', 'mongoose', 'typeorm',    // Database ORMs
        'redis', 'mongodb', 'postgresql',      // Databases
        'aws-sdk', 'azure-sdk', 'google-cloud' // Cloud SDKs
    ];

    if (highImpactComponents.some(hic => comp.includes(hic))) {
        return 0.3;
    }

    // Crypto libraries
    if (comp.includes('crypto') || comp.includes('ssl') || comp.includes('tls')) {
        return 0.4;
    }

    return 0;
}

/**
 * Get confidence-based modifier
 */
function getConfidenceModifier(finding: SecurityFinding): number {
    // Lower confidence reduces effective severity
    return (finding.confidence - 0.7) * 0.5;
}

/**
 * Get context-based modifier
 */
function getContextModifier(finding: SecurityFinding): number {
    let modifier = 0;

    // Direct user input involved
    if (involvesUserInput(finding)) {
        modifier += 0.2;
    }

    // Network accessible
    if (isNetworkAccessible(finding)) {
        modifier += 0.2;
    }

    // Affects multiple files/components
    if (hasWideImpact(finding)) {
        modifier += 0.1;
    }

    return modifier;
}

/**
 * Check if vulnerability has known public exploits
 */
function hasPublicExploit(finding: SecurityFinding): boolean {
    const description = finding.description.toLowerCase();
    const keywords = ['exploit', 'poc', 'proof of concept', 'metasploit', 'nuclei'];
    return keywords.some(keyword => description.includes(keyword));
}

/**
 * Check if vulnerability is remotely exploitable
 */
function isRemotelyExploitable(finding: SecurityFinding): boolean {
    const description = finding.description.toLowerCase();
    const title = finding.title.toLowerCase();

    const remoteKeywords = [
        'remote', 'network', 'http', 'web', 'api',
        'server', 'request', 'response', 'endpoint'
    ];

    return remoteKeywords.some(keyword =>
        description.includes(keyword) || title.includes(keyword)
    );
}

/**
 * Check if vulnerability bypasses authentication
 */
function bypassesAuthentication(finding: SecurityFinding): boolean {
    const text = `${finding.title} ${finding.description}`.toLowerCase();
    const keywords = [
        'bypass', 'authentication bypass', 'auth bypass',
        'unauthorized', 'privilege escalation', 'access control'
    ];
    return keywords.some(keyword => text.includes(keyword));
}

/**
 * Check if vulnerability affects data confidentiality
 */
function affectsDataConfidentiality(finding: SecurityFinding): boolean {
    const text = `${finding.title} ${finding.description}`.toLowerCase();
    const keywords = [
        'data leak', 'information disclosure', 'sensitive data',
        'confidential', 'privacy', 'personal information', 'pii'
    ];
    return keywords.some(keyword => text.includes(keyword));
}

/**
 * Check if vulnerability affects system integrity
 */
function affectsSystemIntegrity(finding: SecurityFinding): boolean {
    return finding.type === VulnerabilityType.INJECTION ||
        finding.type === VulnerabilityType.INSECURE_DESERIALIZATION ||
        finding.description.toLowerCase().includes('code execution') ||
        finding.description.toLowerCase().includes('file write') ||
        finding.description.toLowerCase().includes('command injection');
}

/**
 * Check if vulnerability affects service availability
 */
function affectsAvailability(finding: SecurityFinding): boolean {
    const text = `${finding.title} ${finding.description}`.toLowerCase();
    const keywords = [
        'denial of service', 'dos', 'crash', 'hang',
        'resource exhaustion', 'memory leak', 'infinite loop'
    ];
    return keywords.some(keyword => text.includes(keyword));
}

/**
 * Check if finding involves user input
 */
function involvesUserInput(finding: SecurityFinding): boolean {
    const text = `${finding.title} ${finding.description}`.toLowerCase();
    const keywords = [
        'user input', 'request', 'parameter', 'form',
        'query', 'post data', 'cookie', 'header'
    ];
    return keywords.some(keyword => text.includes(keyword));
}

/**
 * Check if vulnerability is network accessible
 */
function isNetworkAccessible(finding: SecurityFinding): boolean {
    const filePath = finding.filePath?.toLowerCase() || '';
    const text = `${finding.title} ${finding.description}`.toLowerCase();

    return filePath.includes('api') ||
        filePath.includes('server') ||
        filePath.includes('route') ||
        text.includes('http') ||
        text.includes('web') ||
        text.includes('network');
}

/**
 * Check if finding has wide impact across multiple components
 */
function hasWideImpact(finding: SecurityFinding): boolean {
    // Check if finding affects common utilities or core libraries
    const component = finding.component.toLowerCase();
    const coreComponents = [
        'util', 'common', 'shared', 'core', 'base',
        'framework', 'library', 'dependency'
    ];
    return coreComponents.some(core => component.includes(core));
}

/**
 * Get severity classification statistics
 */
export function getSeverityStats(findings: SecurityFinding[]): {
    original: Record<string, number>;
    classified: Record<string, number>;
    adjustments: {
        upgraded: number;
        downgraded: number;
        unchanged: number;
    };
} {
    const original: Record<string, number> = {};
    const classified: Record<string, number> = {};
    let upgraded = 0, downgraded = 0, unchanged = 0;

    for (const finding of findings) {
        const originalSeverity = finding.severity;
        const classifiedSeverity = classifySeverity(finding);

        original[originalSeverity] = (original[originalSeverity] || 0) + 1;
        classified[classifiedSeverity] = (classified[classifiedSeverity] || 0) + 1;

        const originalScore = getSeverityScore(originalSeverity);
        const classifiedScore = getSeverityScore(classifiedSeverity);

        if (classifiedScore > originalScore) {
            upgraded++;
        } else if (classifiedScore < originalScore) {
            downgraded++;
        } else {
            unchanged++;
        }
    }

    return {
        original,
        classified,
        adjustments: { upgraded, downgraded, unchanged }
    };
}
