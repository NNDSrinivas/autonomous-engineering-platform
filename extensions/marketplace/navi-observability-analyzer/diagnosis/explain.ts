/**
 * Issue Explanation for NAVI Observability & Metrics Analyzer
 * 
 * This module provides detailed explanations of classified issues
 * with business context and technical insights.
 */

import { ClassifiedIssue } from '../types';

/**
 * Generate detailed explanation for a classified issue
 * @param issue The classified issue to explain
 * @returns Enhanced explanation with business context
 */
export async function explainIssue(issue: ClassifiedIssue): Promise<string> {
    const explanations = {
        [issue.type]: {
            context: `This ${issue.type.toLowerCase().replace('_', ' ')} issue affects system performance`,
            implications: `Users may experience degraded service quality`,
            urgency: `${issue.severity} severity requires ${issue.severity === 'CRITICAL' ? 'immediate' : 'timely'} attention`
        }
    };

    const explanation = explanations[issue.type] || {
        context: 'System issue detected through observability analysis',
        implications: 'Service quality may be impacted',
        urgency: 'Review recommended'
    };

    return `${explanation.context}. ${explanation.implications}. ${explanation.urgency}.`;
}