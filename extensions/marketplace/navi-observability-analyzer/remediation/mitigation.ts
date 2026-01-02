/**
 * Mitigation Generation for NAVI Observability & Metrics Analyzer
 * 
 * This module generates immediate mitigation steps for critical issues
 * before full remediation can be applied.
 */

import { ClassifiedIssue } from '../types';

export interface MitigationPlan {
    id: string;
    immediate: string[];
    monitoring: string[];
    escalation: string[];
    rollback: string[];
}

/**
 * Generate immediate mitigation plan for critical issues
 * @param issue The classified issue requiring immediate mitigation
 * @returns Structured mitigation plan with immediate and monitoring steps
 */
export async function generateMitigation(issue: ClassifiedIssue): Promise<MitigationPlan> {
    const immediate: string[] = [];
    const monitoring: string[] = [];
    const escalation: string[] = [];
    const rollback: string[] = [];

    // Always include basic monitoring
    monitoring.push('Monitor key metrics every 2 minutes');
    monitoring.push('Check error logs for new issues');
    
    // Issue-specific mitigations
    switch (issue.type) {
        case 'PERFORMANCE_DEGRADATION':
            immediate.push('Scale up resources if auto-scaling available');
            immediate.push('Check and restart unhealthy instances');
            monitoring.push('Monitor response times and throughput');
            escalation.push('Contact on-call engineer if metrics don\'t improve in 10 minutes');
            rollback.push('Revert to previous deployment if available');
            break;
            
        case 'SERVICE_OUTAGE':
            immediate.push('Activate failover if configured');
            immediate.push('Route traffic to healthy instances');
            escalation.push('Immediately page on-call team');
            rollback.push('Switch back to primary service when healthy');
            break;
            
        default:
            immediate.push('Gather additional diagnostic information');
            escalation.push('Notify relevant team based on severity');
            rollback.push('Revert recent changes if correlation found');
    }

    // Critical issues get additional escalation
    if (issue.severity === 'CRITICAL') {
        escalation.unshift('Notify incident commander immediately');
        escalation.push('Prepare customer communication');
    }

    return {
        id: `mitigation-${issue.id}`,
        immediate,
        monitoring,
        escalation,
        rollback
    };
}