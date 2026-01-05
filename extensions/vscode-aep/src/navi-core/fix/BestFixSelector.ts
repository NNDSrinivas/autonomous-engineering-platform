/**
 * BestFixSelector - Automatically picks the single best fix from multiple proposals
 * 
 * This is a critical component that transforms NAVI from showing alternatives
 * to behaving like Copilot/Cline - one best fix, applied immediately.
 * 
 * Selection Logic:
 * 1. Highest confidence first (high > medium > low)
 * 2. Prefer concrete fixes (have replacementText)
 * 3. Fallback to first viable option
 */

import { FixProposal } from '../planning/FixProposalEngine';

export class BestFixSelector {
    /**
     * Select the single best fix from multiple proposals
     * Returns null if no viable fixes exist
     */
    static select(proposals: FixProposal[]): FixProposal | null {
        if (!proposals || proposals.length === 0) {
            return null;
        }

        // Single proposal - return it
        if (proposals.length === 1) {
            return proposals[0];
        }

        console.log(`[BestFixSelector] Choosing best from ${proposals.length} proposals`);

        // Sort by confidence score (highest first)
        const sorted = [...proposals].sort((a, b) => {
            const getConfidenceScore = (confidence: string): number => {
                if (confidence === 'high') return 3;
                if (confidence === 'medium') return 2;
                if (confidence === 'low') return 1;
                return 0;
            };

            const scoreA = getConfidenceScore(a.confidence);
            const scoreB = getConfidenceScore(b.confidence);

            if (scoreA !== scoreB) {
                return scoreB - scoreA; // Higher confidence first
            }

            // Same confidence - prefer concrete fixes
            const aHasReplacement = Boolean(a.replacementText);
            const bHasReplacement = Boolean(b.replacementText);

            if (aHasReplacement && !bHasReplacement) return -1;
            if (!aHasReplacement && bHasReplacement) return 1;

            return 0; // Equal priority
        });

        // Find the best concrete fix
        const concrete = sorted.find(proposal =>
            proposal.replacementText &&
            proposal.replacementText.trim().length > 0
        );

        if (concrete) {
            console.log(`[BestFixSelector] Selected concrete fix: ${concrete.suggestedChange} (confidence: ${concrete.confidence})`);
            return concrete;
        }

        // No concrete fixes - return highest confidence proposal
        // (GenerativeRepairEngine will handle it in Step 2)
        const best = sorted[0];
        console.log(`[BestFixSelector] Selected generative fix: ${best.suggestedChange} (confidence: ${best.confidence})`);
        return best;
    }

    /**
     * Debug info about selection decision
     */
    static explainSelection(proposals: FixProposal[]): string {
        if (!proposals || proposals.length === 0) {
            return "No proposals to select from";
        }

        if (proposals.length === 1) {
            return `Single proposal: ${proposals[0].suggestedChange}`;
        }

        const selected = this.select(proposals);
        const concrete = proposals.filter(p => p.replacementText && p.replacementText.trim());

        return [
            `Total proposals: ${proposals.length}`,
            `Concrete fixes: ${concrete.length}`,
            `Selected: ${selected?.suggestedChange || 'none'}`,
            `Reason: ${selected?.replacementText ? 'concrete fix available' : 'will use generative repair'}`
        ].join(', ');
    }
}