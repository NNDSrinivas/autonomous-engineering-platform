/**
 * NAVI CI Failure Fixer Extension - Reference Implementation
 * 
 * This extension demonstrates the complete NAVI extension architecture:
 * - Cryptographic signing & verification
 * - Permission-based runtime enforcement  
 * - Approval-gated change proposals
 * - Integration with existing NAVI intelligence
 */

import { ExtensionContext, ExtensionResult } from './types';
import { fetchLatestFailure } from './ci/fetchRuns';
import { analyzeLogs } from './ci/analyzeLogs';
import { classifyFailure } from './ci/classifyFailure';
import { proposeFix } from './fixes/index';

/**
 * Main extension entry point - called by NAVI runtime
 */
export async function onInvoke(ctx: ExtensionContext): Promise<ExtensionResult> {
    try {
        // Permission check is handled by NAVI runtime before we get here
        console.log(`[CI-Fixer] Invoked for project: ${ctx.project.name}`);

        // Step 1: Fetch latest failing CI run
        const failingRun = await fetchLatestFailure(ctx);

        if (!failingRun) {
            return {
                success: true,
                message: "✅ No failing CI runs found. All builds are passing!",
                requiresApproval: false
            };
        }

        console.log(`[CI-Fixer] Found failing run: ${failingRun.job}/${failingRun.step}`);

        // Step 2: Analyze failure logs using existing NAVI intelligence
        const analysis = await analyzeLogs(failingRun.logs);

        // Step 3: Classify failure type deterministically
        const failureType = classifyFailure(analysis);

        console.log(`[CI-Fixer] Classified as: ${failureType}`);

        // Step 4: Propose fix (no auto-apply - approval required)
        const proposal = await proposeFix(failureType, failingRun, ctx);

        if (!proposal.fixable) {
            return {
                success: false,
                message: `❌ CI failed due to ${failureType}. Unable to auto-fix - manual review recommended.`,
                details: {
                    failureType,
                    errorMessage: failingRun.error_message,
                    logSnippet: failingRun.log_snippet
                },
                requiresApproval: false
            };
        }

        // Return proposal for approval
        return {
            success: true,
            message: `🔧 CI failed due to ${failureType}. Fix proposal ready for approval.`,
            requiresApproval: true,
            proposal: {
                summary: proposal.summary,
                changes: proposal.changes,
                confidence: proposal.confidence,
                rollback: true, // Enable automatic rollback
                riskLevel: proposal.riskLevel
            },
            details: {
                failureType,
                errorMessage: failingRun.error_message,
                affectedFiles: proposal.changes.map(c => c.filePath)
            }
        };

    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`[CI-Fixer] Extension error:`, error);

        return {
            success: false,
            message: `❌ Extension execution failed: ${message}`,
            requiresApproval: false
        };
    }
}

/**
 * Extension metadata for NAVI runtime
 */
export const metadata = {
    name: "CI Failure Fixer",
    version: "1.0.0",
    permissions: ["CI_READ", "REPO_READ", "PROPOSE_CODE_CHANGES", "REQUEST_APPROVAL"],
    trustLevel: "CORE"
};
