/**
 * Impact Assessment for NAVI Observability & Metrics Analyzer
 * 
 * This module calculates business and technical impact of classified issues
 * using metrics context and domain knowledge.
 */

import { ClassifiedIssue, MetricSeries } from '../types';

export interface ImpactAssessment {
    business: string;
    technical: {
        affectedComponents: string[];
        estimatedDowntime: string;
        dataLoss: boolean;
        recoveryTime: string;
    };
}

/**
 * Calculate comprehensive impact assessment for an issue
 * @param issue The classified issue
 * @param metrics Context metrics for impact calculation
 * @returns Business and technical impact assessment
 */
export async function calculateImpact(
    issue: ClassifiedIssue, 
    metrics: MetricSeries[]
): Promise<ImpactAssessment> {
    
    // Assess business impact based on severity and affected services
    let businessImpact = 'Low impact';
    
    switch (issue.severity) {
        case 'CRITICAL':
            businessImpact = 'High business impact - service disruption likely affecting revenue and user satisfaction';
            break;
        case 'HIGH':
            businessImpact = 'Medium business impact - degraded user experience and potential revenue loss';
            break;
        case 'MEDIUM':
            businessImpact = 'Moderate business impact - some users may experience issues';
            break;
        case 'LOW':
            businessImpact = 'Low business impact - minimal user-facing effects';
            break;
    }

    // Assess technical impact
    const affectedComponents = issue.affectedServices || ['unknown'];
    const estimatedDowntime = issue.severity === 'CRITICAL' ? '15-30 minutes' : 
                             issue.severity === 'HIGH' ? '5-15 minutes' : 'Minimal';
    
    return {
        business: businessImpact,
        technical: {
            affectedComponents,
            estimatedDowntime,
            dataLoss: issue.severity === 'CRITICAL',
            recoveryTime: issue.severity === 'CRITICAL' ? '1-2 hours' : '15-30 minutes'
        }
    };
}