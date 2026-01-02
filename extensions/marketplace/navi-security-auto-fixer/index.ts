/**
 * NAVI Security Vulnerability Auto-Fixer Extension
 * 
 * Production-grade enterprise security automation that detects real vulnerabilities,
 * correlates findings across multiple sources, and proposes safe minimal fixes.
 * 
 * This extension demonstrates NAVI's superiority over Copilot/Cline in:
 * - Enterprise trust and security
 * - Real-world usefulness 
 * - Production-ready automation
 * 
 * @author Navra Labs
 * @version 1.0.0
 */

import {
    ExtensionContext,
    SecurityAnalysisResult,
    SecurityFinding,
    RemediationProposal,
    SeverityLevel,
    RiskAssessment,
    SecurityConfig
} from './types';

// Core scanner imports
import { scanDependencies } from './scanners/dependencyScanner';
import { scanWithSAST } from './scanners/sastScanner';
import { scanSecrets } from './scanners/secretScanner';
import { readCISecurity } from './scanners/ciSecurityReader';

// Analysis engine imports
import { normalizeFindings } from './analysis/normalizeFindings';
import { classifySeverity } from './analysis/classifySeverity';
import { deduplicateFindings } from './analysis/dedupe';
import { assessRisk } from './analysis/riskAssessment';

// Fix generation imports
import { proposeFixes } from './fixes';

/**
 * Main extension entry point - invoked when user requests security analysis
 */
export async function onInvoke(context: ExtensionContext): Promise<SecurityAnalysisResult> {
    console.log('🔐 NAVI Security Auto-Fixer v1.0.0 starting...');

    try {
        // Step 1: Verify permissions and access
        await verifyAccess(context);
        console.log('✅ Security permissions verified');

        // Step 2: Gather security findings from all sources
        console.log('🔍 Gathering security findings from multiple sources...');
        const rawFindings = await gatherSecurityFindings(context);

        if (rawFindings.length === 0) {
            return createHealthyResult();
        }

        // Step 3: Normalize and deduplicate findings
        console.log(`📊 Processing ${rawFindings.length} raw findings...`);
        const normalizedFindings = normalizeFindings(rawFindings);
        const deduplicatedFindings = deduplicateFindings(normalizedFindings);

        // Step 4: Classify and filter by severity
        const classifiedFindings = deduplicatedFindings
            .map(finding => ({ ...finding, severity: classifySeverity(finding) }))
            .filter(finding => shouldIncludeFinding(finding, context.config));

        console.log(`⚠️  Found ${classifiedFindings.length} actionable security vulnerabilities`);

        // Step 5: Assess overall risk
        const riskAssessment = assessRisk(classifiedFindings);

        // Step 6: Generate fix proposals for critical/high severity issues
        const criticalFindings = classifiedFindings.filter(f =>
            f.severity === SeverityLevel.CRITICAL || f.severity === SeverityLevel.HIGH
        );

        const proposals = criticalFindings.length > 0
            ? proposeFixes(criticalFindings)
            : [];

        // Step 7: Generate analysis result
        const result = await generateAnalysisResult(
            classifiedFindings,
            proposals,
            riskAssessment,
            context
        );

        console.log(`🎯 Analysis complete: ${result.summary.criticalCount} critical, ${result.summary.highCount} high severity issues`);

        if (result.requiresApproval) {
            console.log('⚠️  Remediation proposals require approval due to risk level');
        }

        return result;

    } catch (error) {
        console.error('❌ Security analysis failed:', error);
        return createErrorResult(error);
    }
}

/**
 * Verify extension has required permissions and access
 */
async function verifyAccess(context: ExtensionContext): Promise<void> {
    // Verify repo access
    try {
        await context.repo.getMetadata();
    } catch (error) {
        throw new Error('Cannot access repository - check REPO_READ permission');
    }

    // Verify CI access if enabled
    if (context.config.enableSAST) {
        try {
            await context.ci.getLatestBuild();
        } catch (error) {
            console.warn('⚠️  CI access unavailable - skipping CI security reports');
        }
    }
}

/**
 * Gather security findings from all available sources
 */
async function gatherSecurityFindings(context: ExtensionContext): Promise<SecurityFinding[]> {
    const allFindings: SecurityFinding[] = [];

    // Dependency vulnerability scanning
    if (context.config.scanDependencies) {
        try {
            console.log('📦 Scanning dependencies for vulnerabilities...');
            const depFindings = await scanDependencies(context.repo);
            allFindings.push(...depFindings);
            console.log(`Found ${depFindings.length} dependency vulnerabilities`);
        } catch (error) {
            console.warn('⚠️  Dependency scanning failed:', error);
        }
    }

    // Static Application Security Testing (SAST)
    if (context.config.enableSAST) {
        try {
            console.log('🔍 Running static security analysis...');
            const sastFindings = await scanWithSAST(context.repo);
            allFindings.push(...sastFindings);
            console.log(`Found ${sastFindings.length} code vulnerabilities`);
        } catch (error) {
            console.warn('⚠️  SAST scanning failed:', error);
        }
    }

    // Secret scanning
    if (context.config.scanSecrets) {
        try {
            console.log('🔑 Scanning for exposed secrets...');
            const secretFindings = await scanSecrets(context.repo);
            allFindings.push(...secretFindings);
            console.log(`Found ${secretFindings.length} potential secret exposures`);
        } catch (error) {
            console.warn('⚠️  Secret scanning failed:', error);
        }
    }

    // CI/CD security reports
    try {
        console.log('🏗️  Reading CI/CD security reports...');
        const ciFindings = await readCISecurity(context.ci);
        allFindings.push(...ciFindings);
        console.log(`Found ${ciFindings.length} CI security findings`);
    } catch (error) {
        console.warn('⚠️  CI security reading failed:', error);
    }

    return allFindings;
}

/**
 * Determine if finding should be included based on configuration
 */
function shouldIncludeFinding(finding: SecurityFinding, config: SecurityConfig): boolean {
    // Filter by severity threshold
    const severityOrder = [
        SeverityLevel.INFO,
        SeverityLevel.LOW,
        SeverityLevel.MEDIUM,
        SeverityLevel.HIGH,
        SeverityLevel.CRITICAL
    ];

    const findingIndex = severityOrder.indexOf(finding.severity);
    const thresholdIndex = severityOrder.indexOf(config.autoFixThreshold);

    return findingIndex >= thresholdIndex && finding.confidence >= config.confidenceThreshold;
}

/**
 * Generate comprehensive analysis result
 */
async function generateAnalysisResult(
    findings: SecurityFinding[],
    proposals: RemediationProposal[],
    riskAssessment: RiskAssessment,
    _context: ExtensionContext
): Promise<SecurityAnalysisResult> {
    // Generate summary statistics
    const summary = {
        totalFindings: findings.length,
        criticalCount: findings.filter(f => f.severity === SeverityLevel.CRITICAL).length,
        highCount: findings.filter(f => f.severity === SeverityLevel.HIGH).length,
        mediumCount: findings.filter(f => f.severity === SeverityLevel.MEDIUM).length,
        lowCount: findings.filter(f => f.severity === SeverityLevel.LOW).length
    };

    // Determine if approval is required
    const requiresApproval = proposals.some(p => p.risk === 'HIGH') ||
        summary.criticalCount > 0 ||
        riskAssessment.riskScore > 0.7;

    // Generate recommendations
    const recommendations = generateRecommendations(findings, summary, riskAssessment);

    return {
        findings,
        summary,
        proposals,
        riskAssessment,
        requiresApproval,
        recommendations,
        metadata: {
            analysisTime: new Date().toISOString(),
            extensionVersion: '1.0.0',
            confidence: calculateOverallConfidence(findings)
        }
    };
}

/**
 * Generate human-readable recommendations based on findings
 */
function generateRecommendations(
    findings: SecurityFinding[],
    summary: any,
    riskAssessment: RiskAssessment
): string[] {
    const recommendations: string[] = [];

    if (summary.totalFindings === 0) {
        recommendations.push('✅ No critical security vulnerabilities detected');
        recommendations.push('🔍 Continue regular security monitoring');
        return recommendations;
    }

    // Critical severity recommendations
    if (summary.criticalCount > 0) {
        recommendations.push(`🚨 CRITICAL: ${summary.criticalCount} critical vulnerabilities require immediate attention`);
        recommendations.push('⏰ Recommend fixing critical issues within 24 hours');

        if (riskAssessment.businessCriticality === 'CRITICAL') {
            recommendations.push('🔥 Business-critical systems affected - consider emergency response');
        }
    }

    // High severity recommendations  
    if (summary.highCount > 0) {
        recommendations.push(`⚠️  HIGH: ${summary.highCount} high-severity vulnerabilities should be addressed within 7 days`);
    }

    // Dependency-specific recommendations
    const depFindings = findings.filter(f => f.type === 'DEPENDENCY');
    if (depFindings.length > 0) {
        recommendations.push(`📦 ${depFindings.length} vulnerable dependencies detected - prioritize updates`);
    }

    // Secret exposure recommendations
    const secretFindings = findings.filter(f => f.type === 'SECRET_EXPOSURE');
    if (secretFindings.length > 0) {
        recommendations.push(`🔑 ${secretFindings.length} potential secrets exposed - rotate credentials immediately`);
    }

    // Risk-based recommendations
    if (riskAssessment.riskScore > 0.8) {
        recommendations.push('🎯 High-risk repository - enable additional security monitoring');
        recommendations.push('🔐 Consider implementing additional access controls');
    }

    return recommendations;
}

/**
 * Calculate overall confidence across all findings
 */
function calculateOverallConfidence(findings: SecurityFinding[]): number {
    if (findings.length === 0) return 1.0;

    const totalConfidence = findings.reduce((sum, f) => sum + f.confidence, 0);
    return totalConfidence / findings.length;
}

/**
 * Create result for healthy repositories with no vulnerabilities
 */
function createHealthyResult(): SecurityAnalysisResult {
    return {
        findings: [],
        summary: {
            totalFindings: 0,
            criticalCount: 0,
            highCount: 0,
            mediumCount: 0,
            lowCount: 0
        },
        proposals: [],
        riskAssessment: {
            riskScore: 0.1,
            exploitability: 0.1,
            impact: 0.1,
            likelihood: 'LOW',
            businessCriticality: 'LOW'
        },
        requiresApproval: false,
        recommendations: [
            '✅ No critical security vulnerabilities detected',
            '🔍 Repository appears secure - continue regular monitoring',
            '📋 Consider implementing automated security scanning in CI/CD'
        ],
        metadata: {
            analysisTime: new Date().toISOString(),
            extensionVersion: '1.0.0',
            confidence: 1.0
        }
    };
}

/**
 * Create error result when analysis fails
 */
function createErrorResult(_error: any): SecurityAnalysisResult {
    return {
        findings: [],
        summary: {
            totalFindings: 0,
            criticalCount: 0,
            highCount: 0,
            mediumCount: 0,
            lowCount: 0
        },
        proposals: [],
        riskAssessment: {
            riskScore: 0.5,
            exploitability: 0.5,
            impact: 0.5,
            likelihood: 'MEDIUM',
            businessCriticality: 'MEDIUM'
        },
        requiresApproval: false,
        recommendations: [
            '❌ Security analysis failed',
            '🔧 Check extension permissions and repository access',
            '📋 Review CI/CD integration configuration',
            '🔍 Consult extension logs for details'
        ],
        metadata: {
            analysisTime: new Date().toISOString(),
            extensionVersion: '1.0.0',
            confidence: 0.0
        }
    };
}