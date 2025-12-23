// extensions/vscode-aep/src/navi-core/fix/FixConfidencePolicy.ts
/**
 * Phase 2.2 Step 3: Confidence & Auto-Apply Policy
 * 
 * Determines when NAVI should auto-apply fixes immediately vs when it must ask the user.
 * This enables Copilot/Cline-level UX: instant fixes for obvious issues, approval for complex changes.
 * 
 * Key Goals:
 * - No repetitive approval clicks for syntax errors
 * - No "approve → nothing happens" confusion
 * - Conservative on behavior-changing fixes
 */

import { DiagnosticCluster } from '../perception/DiagnosticsPerception';
import * as vscode from 'vscode';

export type FixDecision =
    | 'auto-apply'      // Apply immediately without user intervention
    | 'ask-user'        // Request user approval with diff preview
    | 'preview-only';   // Show diff but don't offer to apply

export interface FixPolicyContext {
    cluster: DiagnosticCluster;
    totalAffectedFiles: number;
    changeSize: 'small' | 'medium' | 'large';
    hasExports?: boolean;
    hasAPI?: boolean;
}

/**
 * Central policy engine for fix confidence and auto-application decisions.
 * 
 * This is the core component that makes NAVI feel as fast and effortless as
 * Copilot/Cline by eliminating unnecessary approval prompts.
 */
export class FixConfidencePolicy {

    /**
     * Primary decision function: determines how a fix should be handled.
     * 
     * @param context Fix context including cluster and scope information
     * @returns Decision on whether to auto-apply, ask user, or preview only
     */
    static decide(context: FixPolicyContext): FixDecision {
        const { cluster, totalAffectedFiles, changeSize } = context;

        // 🔴 RULE 1: Multi-file changes always require approval
        if (totalAffectedFiles > 1) {
            return 'ask-user';
        }

        // 🔴 RULE 2: Large changes always require approval
        if (changeSize === 'large') {
            return 'ask-user';
        }

        // 🔴 RULE 3: Files with exports/APIs require approval  
        if (context.hasExports || context.hasAPI) {
            return 'ask-user';
        }

        // 🟢 RULE 4: Structural & syntax errors → AUTO-APPLY
        // These are deterministic compiler failures, not semantic ambiguities
        if (cluster.category === 'syntax' || cluster.category === 'structure') {
            return 'auto-apply';
        }

        // 🟠 RULE 5: Lint/style issues → AUTO-APPLY (if small)
        if (cluster.category === 'lint') {
            return changeSize === 'small' ? 'auto-apply' : 'ask-user';
        }

        // 🔵 RULE 6: Type issues → ASK (could be complex)
        if (cluster.category === 'type') {
            return 'ask-user';
        }

        // 🔵 RULE 7: Unknown issues → ASK (conservative default)
        return 'ask-user';
    }

    /**
     * Determines the size/scope of a potential change based on diagnostic cluster.
     * Used to assess risk level for auto-apply decisions.
     */
    static assessChangeSize(cluster: DiagnosticCluster): 'small' | 'medium' | 'large' {
        const totalDiagnostics = 1 + cluster.related.length;

        // More diagnostics typically means more complex changes needed
        if (totalDiagnostics >= 10) {
            return 'large';
        } else if (totalDiagnostics >= 4) {
            return 'medium';
        } else {
            return 'small';
        }
    }

    /**
     * Checks if a file contains exports or API-like structures that make
     * changes more risky (could affect other files).
     */
    static async hasExportsOrAPI(uri: vscode.Uri): Promise<boolean> {
        try {
            const document = await vscode.workspace.openTextDocument(uri);
            const text = document.getText();

            // Quick heuristic check for exports/APIs
            return (
                text.includes('export ') ||
                text.includes('module.exports') ||
                text.includes('exports.') ||
                text.includes('public ') ||
                text.includes('interface ') ||
                text.includes('class ') && text.includes('export')
            );
        } catch {
            return false; // Conservative: assume no exports if can't read
        }
    }

    /**
     * Builds complete policy context for a diagnostic cluster.
     * This gathers all information needed to make an informed auto-apply decision.
     */
    static async buildContext(
        cluster: DiagnosticCluster,
        additionalFiles?: string[]
    ): Promise<FixPolicyContext> {
        const uri = vscode.Uri.parse(cluster.fileUri);
        const totalAffectedFiles = 1 + (additionalFiles?.length || 0);
        const changeSize = this.assessChangeSize(cluster);
        const hasExports = await this.hasExportsOrAPI(uri);

        return {
            cluster,
            totalAffectedFiles,
            changeSize,
            hasExports,
            hasAPI: hasExports // For now, treat exports as API indicator
        };
    }

    /**
     * Quick confidence check for the most common case: single syntax error.
     * Used for fast-path decisions without full context building.
     */
    static isObviousSyntaxFix(cluster: DiagnosticCluster): boolean {
        return (
            (cluster.category === 'syntax' || cluster.category === 'structure') &&
            cluster.related.length <= 2 // Not too many related errors
        );
    }

    /**
     * Gets human-readable explanation for a fix decision.
     * Useful for logging and user feedback.
     */
    static explainDecision(decision: FixDecision, context: FixPolicyContext): string {
        switch (decision) {
            case 'auto-apply':
                return `Auto-applying ${context.cluster.category} fix (${context.changeSize} change, single file)`;

            case 'ask-user':
                if (context.totalAffectedFiles > 1) {
                    return `Requesting approval (affects ${context.totalAffectedFiles} files)`;
                } else if (context.changeSize === 'large') {
                    return `Requesting approval (large change with ${1 + context.cluster.related.length} issues)`;
                } else if (context.hasExports) {
                    return `Requesting approval (file contains exports/API)`;
                } else {
                    return `Requesting approval (${context.cluster.category} fix requires review)`;
                }

            case 'preview-only':
                return `Showing preview only (${context.cluster.category} fix)`;

            default:
                return 'Unknown decision';
        }
    }
}