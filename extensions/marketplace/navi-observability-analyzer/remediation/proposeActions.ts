/**
 * Action Proposal for NAVI Observability & Metrics Analyzer
 * 
 * This module proposes specific remediation actions based on classified issues
 * with approval workflows and risk assessment.
 */

import {
    ClassifiedIssue,
    EffortLevel,
    Priority,
    RemediationProposal,
    RemediationStep,
    RemediationType,
    RiskLevel
} from '../types';

/**
 * Propose remediation actions for a classified issue
 * @param issue The classified issue requiring remediation
 * @returns Structured remediation proposal with approval workflow
 */
export async function proposeActions(issue: ClassifiedIssue): Promise<RemediationProposal | null> {
    if (!issue || issue.confidence < 0.5) {
        return null;
    }

    // Generate actions based on issue type and severity
    const actions = generateActionsForIssue(issue);
    const requiresApproval = issue.severity === 'CRITICAL' || issue.severity === 'HIGH';
    
    return {
        id: `remediation-${issue.id}`,
        title: `Remediation for ${issue.title}`,
        description: `Proposed actions to resolve ${issue.type.toLowerCase().replace('_', ' ')}`,
        type: RemediationType.MITIGATION,
        priority: mapSeverityToPriority(issue.severity),
        confidence: issue.confidence,
        effort: EffortLevel.MEDIUM,
        risk: mapSeverityToRisk(issue.severity),
        requiresApproval,
        estimatedImpact: `Resolve ${issue.title}`,
        steps: actions,
        rollbackPlan: {
            canRollback: true,
            steps: ['Revert the last deployment', 'Monitor key metrics for 15 minutes'],
            timeEstimate: '10 minutes',
            dataLoss: false
        },
        monitoring: {
            metrics: ['error_rate', 'latency_p95', 'throughput'],
            alerts: ['error_rate_spike', 'latency_regression'],
            duration: '30 minutes',
            successCriteria: ['Metrics return to baseline', 'No new errors in logs']
        }
    };
}

/**
 * Generate specific action steps for an issue
 */
function generateActionsForIssue(issue: ClassifiedIssue) {
    const baseActions: RemediationStep[] = [
        {
            order: 1,
            action: 'Investigate root cause',
            description: issue.rootCause?.hypothesis || 'Analyze suspected root cause',
            command: 'echo "Investigation step"',
            validation: 'Root cause identified',
            automatable: false
        }
    ];

    switch (issue.type) {
        case 'PERFORMANCE_DEGRADATION':
            baseActions.push({
                order: 2,
                action: 'Check resource utilization',
                description: 'Review CPU, memory, and network metrics',
                command: 'echo "Resource check"',
                validation: 'Resource bottlenecks identified',
                automatable: true
            });
            break;
            
        default:
            baseActions.push({
                order: 2,
                action: 'Apply generic remediation',
                description: 'Standard recovery procedure',
                command: 'echo "Generic remediation"',
                validation: 'Issue mitigated',
                rollbackAction: 'echo "Rollback if needed"',
                automatable: true
            });
    }

    return baseActions;
}

/**
 * Map issue severity to priority
 */
function mapSeverityToPriority(severity: string): Priority {
    switch (severity) {
        case 'CRITICAL': return Priority.P0;
        case 'HIGH': return Priority.P1;
        case 'MEDIUM': return Priority.P2;
        case 'LOW': return Priority.P3;
        default: return Priority.P2;
    }
}

/**
 * Map issue severity to risk level
 */
function mapSeverityToRisk(severity: string): RiskLevel {
    switch (severity) {
        case 'CRITICAL': return RiskLevel.HIGH;
        case 'HIGH': return RiskLevel.MEDIUM;
        case 'MEDIUM': return RiskLevel.LOW;
        case 'LOW': return RiskLevel.LOW;
        default: return RiskLevel.MEDIUM;
    }
}
