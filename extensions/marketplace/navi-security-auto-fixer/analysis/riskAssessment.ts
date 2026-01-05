/**
 * Risk Assessment Engine
 * 
 * Provides comprehensive risk assessment for security findings based on
 * exploitability, impact, business criticality, and environmental factors.
 */

import { SecurityFinding, RiskAssessment, VulnerabilityType, SeverityLevel } from '../types';

/**
 * Risk scoring weights for different factors
 */
const RISK_FACTORS = {
    EXPLOITABILITY: 0.35,
    IMPACT: 0.25,
    BUSINESS_CRITICALITY: 0.2,
    EXPOSURE: 0.15,
    CONTEXT: 0.05
};

/**
 * Assess overall security risk for a collection of findings
 */
export function assessRisk(findings: SecurityFinding[]): RiskAssessment {
    if (findings.length === 0) {
        return createLowRiskAssessment();
    }

    console.log(`📊 Assessing risk for ${findings.length} security findings...`);

    // Calculate individual risk scores
    const individualRisks = findings.map(finding => calculateIndividualRisk(finding));

    // Calculate aggregate risk
    const aggregateRisk = calculateAggregateRisk(individualRisks, findings);

    // Determine business criticality
    const businessCriticality = assessBusinessCriticality(findings);

    // Determine exploitation likelihood
    const likelihood = assessExploitationLikelihood(findings);

    const riskAssessment: RiskAssessment = {
        riskScore: aggregateRisk.riskScore,
        exploitability: aggregateRisk.exploitability,
        impact: aggregateRisk.impact,
        likelihood,
        businessCriticality
    };

    console.log(`📈 Risk assessment complete: Score ${riskAssessment.riskScore.toFixed(2)}, Criticality ${riskAssessment.businessCriticality}, Likelihood ${riskAssessment.likelihood}`);

    return riskAssessment;
}

/**
 * Calculate risk for individual finding
 */
function calculateIndividualRisk(finding: SecurityFinding): {
    riskScore: number;
    exploitability: number;
    impact: number;
} {
    // Base scores from severity
    let exploitability = getSeverityExploitabilityScore(finding.severity);
    let impact = getSeverityImpactScore(finding.severity);

    // Adjust based on vulnerability type
    const typeAdjustment = getVulnerabilityTypeAdjustment(finding.type);
    exploitability *= typeAdjustment.exploitability;
    impact *= typeAdjustment.impact;

    // Adjust based on CVE presence and score
    const cveAdjustment = getCVEAdjustment(finding.cveIds);
    exploitability *= cveAdjustment.exploitability;
    impact *= cveAdjustment.impact;

    // Adjust based on context
    const contextAdjustment = getContextualAdjustment(finding);
    exploitability *= contextAdjustment.exploitability;
    impact *= contextAdjustment.impact;

    // Apply confidence factor
    const confidenceAdjustment = getConfidenceAdjustment(finding.confidence);
    exploitability *= confidenceAdjustment;
    impact *= confidenceAdjustment;

    // Calculate overall risk score
    const riskScore = (
        exploitability * RISK_FACTORS.EXPLOITABILITY +
        impact * RISK_FACTORS.IMPACT
    );

    return {
        riskScore: Math.min(1.0, riskScore),
        exploitability: Math.min(1.0, exploitability),
        impact: Math.min(1.0, impact)
    };
}

/**
 * Get base exploitability score from severity
 */
function getSeverityExploitabilityScore(severity: SeverityLevel): number {
    const scores = {
        [SeverityLevel.CRITICAL]: 0.9,
        [SeverityLevel.HIGH]: 0.7,
        [SeverityLevel.MEDIUM]: 0.5,
        [SeverityLevel.LOW]: 0.3,
        [SeverityLevel.INFO]: 0.1
    };
    return scores[severity] || 0.5;
}

/**
 * Get base impact score from severity
 */
function getSeverityImpactScore(severity: SeverityLevel): number {
    const scores = {
        [SeverityLevel.CRITICAL]: 0.95,
        [SeverityLevel.HIGH]: 0.75,
        [SeverityLevel.MEDIUM]: 0.55,
        [SeverityLevel.LOW]: 0.35,
        [SeverityLevel.INFO]: 0.15
    };
    return scores[severity] || 0.5;
}

/**
 * Get vulnerability type risk adjustments
 */
function getVulnerabilityTypeAdjustment(type: VulnerabilityType): {
    exploitability: number;
    impact: number;
} {
    const adjustments = {
        [VulnerabilityType.INJECTION]: {
            exploitability: 1.3, // Very exploitable
            impact: 1.2          // High impact
        },
        [VulnerabilityType.SECRET_EXPOSURE]: {
            exploitability: 1.1, // Directly exploitable
            impact: 1.0          // Variable impact
        },
        [VulnerabilityType.INSECURE_DESERIALIZATION]: {
            exploitability: 1.2, // Highly exploitable if accessible
            impact: 1.3          // Can lead to RCE
        },
        [VulnerabilityType.WEAK_CRYPTO]: {
            exploitability: 0.8, // Requires specific knowledge
            impact: 0.9          // Data confidentiality impact
        },
        [VulnerabilityType.CONFIGURATION]: {
            exploitability: 0.7, // Depends on configuration
            impact: 0.8          // Variable impact
        },
        [VulnerabilityType.DEPENDENCY]: {
            exploitability: 1.0, // Depends on usage
            impact: 1.0          // Depends on component
        },
        [VulnerabilityType.CODE_VULNERABILITY]: {
            exploitability: 0.9, // Varies widely
            impact: 0.9          // Varies widely
        }
    };

    return adjustments[type] || { exploitability: 1.0, impact: 1.0 };
}

/**
 * Get CVE-based risk adjustments
 */
function getCVEAdjustment(cveIds?: string[]): {
    exploitability: number;
    impact: number;
} {
    if (!cveIds || cveIds.length === 0) {
        return { exploitability: 0.9, impact: 0.9 }; // Slightly lower without CVE confirmation
    }

    // Multiple CVEs indicate more severe issues
    const cveMultiplier = Math.min(1.3, 1.0 + (cveIds.length - 1) * 0.1);

    return {
        exploitability: cveMultiplier,
        impact: cveMultiplier
    };
}

/**
 * Get contextual adjustments based on finding details
 */
function getContextualAdjustment(finding: SecurityFinding): {
    exploitability: number;
    impact: number;
} {
    let exploitabilityMultiplier = 1.0;
    let impactMultiplier = 1.0;

    const text = `${finding.title} ${finding.description}`.toLowerCase();
    const filePath = finding.filePath?.toLowerCase() || '';

    // Network accessibility increases exploitability
    if (isNetworkAccessible(text, filePath)) {
        exploitabilityMultiplier *= 1.2;
    }

    // Authentication bypass significantly increases both
    if (bypassesAuthentication(text)) {
        exploitabilityMultiplier *= 1.3;
        impactMultiplier *= 1.2;
    }

    // Remote code execution potential
    if (allowsCodeExecution(text)) {
        exploitabilityMultiplier *= 1.2;
        impactMultiplier *= 1.4;
    }

    // Data access/manipulation potential
    if (affectsDataSecurity(text)) {
        impactMultiplier *= 1.2;
    }

    // Critical component affected
    if (affectsCriticalComponent(finding.component, filePath)) {
        impactMultiplier *= 1.3;
    }

    // Production environment indicators
    if (isProductionPath(filePath)) {
        impactMultiplier *= 1.2;
    }

    return {
        exploitability: exploitabilityMultiplier,
        impact: impactMultiplier
    };
}

/**
 * Check if vulnerability is network accessible
 */
function isNetworkAccessible(text: string, filePath: string): boolean {
    const networkKeywords = [
        'http', 'web', 'api', 'server', 'network', 'remote',
        'request', 'response', 'endpoint', 'route'
    ];

    const networkPaths = ['api/', 'server/', 'web/', 'http/', 'route/'];

    return networkKeywords.some(keyword => text.includes(keyword)) ||
        networkPaths.some(path => filePath.includes(path));
}

/**
 * Check if vulnerability bypasses authentication
 */
function bypassesAuthentication(text: string): boolean {
    const authBypassKeywords = [
        'bypass', 'authentication bypass', 'auth bypass',
        'unauthorized', 'privilege escalation', 'access control'
    ];

    return authBypassKeywords.some(keyword => text.includes(keyword));
}

/**
 * Check if vulnerability allows code execution
 */
function allowsCodeExecution(text: string): boolean {
    const codeExecKeywords = [
        'code execution', 'remote code execution', 'rce',
        'command injection', 'arbitrary code', 'shell injection'
    ];

    return codeExecKeywords.some(keyword => text.includes(keyword));
}

/**
 * Check if vulnerability affects data security
 */
function affectsDataSecurity(text: string): boolean {
    const dataSecurityKeywords = [
        'data leak', 'information disclosure', 'sensitive data',
        'sql injection', 'database', 'privacy', 'confidential'
    ];

    return dataSecurityKeywords.some(keyword => text.includes(keyword));
}

/**
 * Check if vulnerability affects critical component
 */
function affectsCriticalComponent(component: string, filePath: string): boolean {
    const criticalComponents = [
        'auth', 'authentication', 'login', 'security',
        'database', 'db', 'payment', 'crypto', 'session'
    ];

    const criticalPaths = [
        'auth/', 'security/', 'payment/', 'admin/', 'api/auth'
    ];

    const compLower = component.toLowerCase();

    return criticalComponents.some(comp => compLower.includes(comp)) ||
        criticalPaths.some(path => filePath.includes(path));
}

/**
 * Check if path indicates production code
 */
function isProductionPath(filePath: string): boolean {
    const productionPaths = ['src/', 'lib/', 'app/', 'production/'];
    const nonProductionPaths = ['test/', 'spec/', 'dev/', 'example/'];

    return productionPaths.some(path => filePath.includes(path)) &&
        !nonProductionPaths.some(path => filePath.includes(path));
}

/**
 * Get confidence adjustment factor
 */
function getConfidenceAdjustment(confidence: number): number {
    // Lower confidence reduces risk scores
    return 0.5 + (confidence * 0.5);
}

/**
 * Calculate aggregate risk from individual risks
 */
function calculateAggregateRisk(
    individualRisks: ReturnType<typeof calculateIndividualRisk>[],
    findings: SecurityFinding[]
): {
    riskScore: number;
    exploitability: number;
    impact: number;
} {
    if (individualRisks.length === 0) {
        return { riskScore: 0, exploitability: 0, impact: 0 };
    }

    // Weight risks by severity
    const weightedRisks = individualRisks.map((risk, index) => {
        const severityWeight = getSeverityWeight(findings[index].severity);
        return {
            riskScore: risk.riskScore * severityWeight,
            exploitability: risk.exploitability * severityWeight,
            impact: risk.impact * severityWeight,
            weight: severityWeight
        };
    });

    const totalWeight = weightedRisks.reduce((sum, risk) => sum + risk.weight, 0);

    // Calculate weighted averages
    const riskScore = weightedRisks.reduce((sum, risk) => sum + risk.riskScore, 0) / totalWeight;
    const exploitability = weightedRisks.reduce((sum, risk) => sum + risk.exploitability, 0) / totalWeight;
    const impact = weightedRisks.reduce((sum, risk) => sum + risk.impact, 0) / totalWeight;

    // Apply systemic risk multiplier for multiple high-severity issues
    const systemicMultiplier = getSystemicRiskMultiplier(findings);

    return {
        riskScore: Math.min(1.0, riskScore * systemicMultiplier),
        exploitability: Math.min(1.0, exploitability),
        impact: Math.min(1.0, impact * systemicMultiplier)
    };
}

/**
 * Get severity weight for aggregation
 */
function getSeverityWeight(severity: SeverityLevel): number {
    const weights = {
        [SeverityLevel.CRITICAL]: 5,
        [SeverityLevel.HIGH]: 3,
        [SeverityLevel.MEDIUM]: 2,
        [SeverityLevel.LOW]: 1,
        [SeverityLevel.INFO]: 0.5
    };
    return weights[severity] || 1;
}

/**
 * Calculate systemic risk multiplier
 */
function getSystemicRiskMultiplier(findings: SecurityFinding[]): number {
    const criticalCount = findings.filter(f => f.severity === SeverityLevel.CRITICAL).length;
    const highCount = findings.filter(f => f.severity === SeverityLevel.HIGH).length;

    // Multiple critical/high issues increase systemic risk
    if (criticalCount >= 3) return 1.3;
    if (criticalCount >= 2 || (criticalCount >= 1 && highCount >= 2)) return 1.2;
    if (criticalCount >= 1 || highCount >= 3) return 1.1;

    return 1.0;
}

/**
 * Assess business criticality based on findings
 */
function assessBusinessCriticality(findings: SecurityFinding[]): RiskAssessment['businessCriticality'] {
    const criticalCount = findings.filter(f => f.severity === SeverityLevel.CRITICAL).length;
    const highCount = findings.filter(f => f.severity === SeverityLevel.HIGH).length;

    // Check for business-critical indicators
    const hasCriticalComponents = findings.some(f =>
        affectsCriticalComponent(f.component, f.filePath || '')
    );

    const hasAuthBypass = findings.some(f =>
        bypassesAuthentication(`${f.title} ${f.description}`)
    );

    const hasDataBreach = findings.some(f =>
        affectsDataSecurity(`${f.title} ${f.description}`)
    );

    if (criticalCount >= 2 || hasAuthBypass || hasDataBreach) {
        return 'CRITICAL';
    }

    if (criticalCount >= 1 || highCount >= 2 || hasCriticalComponents) {
        return 'HIGH';
    }

    if (highCount >= 1) {
        return 'MEDIUM';
    }

    return 'LOW';
}

/**
 * Assess exploitation likelihood
 */
function assessExploitationLikelihood(findings: SecurityFinding[]): RiskAssessment['likelihood'] {
    if (findings.some(f => f.severity === SeverityLevel.CRITICAL)) {
        return 'HIGH';
    }

    if (findings.some(f =>
        bypassesAuthentication(`${f.title} ${f.description}`) ||
        allowsCodeExecution(`${f.title} ${f.description}`)
    )) {
        return 'HIGH';
    }

    const avgExploitability = findings.reduce(
        (sum, f) => sum + calculateIndividualRisk(f).exploitability,
        0
    ) / findings.length;

    if (avgExploitability >= 0.8) return 'HIGH';
    if (avgExploitability >= 0.6) return 'MEDIUM';
    return 'LOW';
}

/**
 * Create low-risk assessment for clean repositories
 */
function createLowRiskAssessment(): RiskAssessment {
    return {
        riskScore: 0.1,
        exploitability: 0.1,
        impact: 0.1,
        likelihood: 'LOW',
        businessCriticality: 'LOW'
    };
}
