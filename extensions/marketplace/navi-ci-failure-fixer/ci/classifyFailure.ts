/**
 * Failure Classification - Deterministic classification of CI failures
 */

import { FailureAnalysis } from '../types';

/**
 * Classify failure type based on analysis (no hallucination, pattern-based only)
 */
export function classifyFailure(analysis: FailureAnalysis): string {
    // Use confidence-weighted classification
    if (analysis.confidence < 0.6) {
        return 'UNKNOWN';
    }

    // Map analysis types to standard failure classifications
    switch (analysis.errorType) {
        case 'dependency':
            return 'DEPENDENCY';

        case 'build':
            return 'BUILD';

        case 'test':
            return 'TEST';

        case 'lint':
            return 'LINT';

        case 'types':
            return 'TYPES';

        default:
            return 'UNKNOWN';
    }
}

/**
 * Get human-readable description of failure type
 */
export function getFailureDescription(failureType: string): string {
    const descriptions: Record<string, string> = {
        'DEPENDENCY': 'Missing or conflicting package dependencies',
        'BUILD': 'Code compilation or build process failure',
        'TEST': 'Unit or integration test failures',
        'LINT': 'Code style or linting rule violations',
        'TYPES': 'TypeScript type checking errors',
        'UNKNOWN': 'Unclassified error requiring manual review'
    };

    return descriptions[failureType] || descriptions.UNKNOWN;
}

/**
 * Determine if failure type is auto-fixable
 */
export function isAutoFixable(failureType: string): boolean {
    // Only these types can be safely auto-fixed with approval
    const autoFixableTypes = ['DEPENDENCY', 'LINT', 'TYPES'];
    return autoFixableTypes.includes(failureType);
}

/**
 * Get risk level for auto-fixing this failure type
 */
export function getRiskLevel(failureType: string): 'low' | 'medium' | 'high' {
    const riskLevels: Record<string, 'low' | 'medium' | 'high'> = {
        'DEPENDENCY': 'medium', // Dependencies can have breaking changes
        'BUILD': 'high',        // Build fixes can be complex
        'TEST': 'high',         // Test fixes might hide real issues  
        'LINT': 'low',          // Lint fixes are usually safe
        'TYPES': 'medium',      // Type fixes can change behavior
        'UNKNOWN': 'high'       // Unknown issues are risky
    };

    return riskLevels[failureType] || 'high';
}
