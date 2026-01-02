/**
 * Fix Proposal System - Generates approval-gated change proposals
 */

import { CIFailure, ExtensionContext, FixProposal } from '../types';
import { isAutoFixable, getRiskLevel } from '../ci/classifyFailure';
import { dependencyFix } from './dependencyFix';
import { testFix } from './testFix';
import { lintFix } from './lintFix';
import { typesFix } from './typesFix';

/**
 * Main fix proposal entry point
 */
export async function proposeFix(
    failureType: string,
    failure: CIFailure,
    ctx: ExtensionContext
): Promise<FixProposal> {

    console.log(`[CI-Fixer] Proposing fix for ${failureType}`);

    // Check if this failure type is auto-fixable
    if (!isAutoFixable(failureType)) {
        return {
            fixable: false,
            summary: `${failureType} failures require manual review`,
            changes: [],
            confidence: 0,
            riskLevel: getRiskLevel(failureType)
        };
    }

    // Route to appropriate fix handler
    try {
        switch (failureType) {
            case 'DEPENDENCY':
                return await dependencyFix(failure, ctx);

            case 'LINT':
                return await lintFix(failure, ctx);

            case 'TYPES':
                return await typesFix(failure, ctx);

            case 'TEST':
                return await testFix(failure, ctx);

            default:
                return createUnknownFix(failureType, failure);
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`[CI-Fixer] Error generating fix for ${failureType}:`, error);

        return {
            fixable: false,
            summary: `Failed to generate fix proposal: ${message}`,
            changes: [],
            confidence: 0,
            riskLevel: 'high'
        };
    }
}

/**
 * Create a non-fixable proposal for unknown failure types
 */
function createUnknownFix(failureType: string, failure: CIFailure): FixProposal {
    return {
        fixable: false,
        summary: `${failureType} failure cannot be automatically fixed`,
        changes: [],
        confidence: 0,
        riskLevel: 'high'
    };
}
