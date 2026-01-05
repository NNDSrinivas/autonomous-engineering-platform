/**
 * Fix Proposals Index
 * 
 * Central orchestrator for generating security fix proposals
 */

import { SecurityFinding, RemediationProposal } from '../types';
import { generateDependencyFixes } from './dependencyFixes';
import { generateConfigFixes } from './configFixes';  
import { generateCodeFixes } from './codeFixes';

/**
 * Generate all applicable fix proposals for security findings
 */
export function proposeFixes(findings: SecurityFinding[]): RemediationProposal[] {
    console.log(`🔧 Generating fixes for ${findings.length} security findings...`);
    
    const allProposals: RemediationProposal[] = [];
    
    try {
        // Generate dependency fixes
        const dependencyProposals = generateDependencyFixes(findings);
        allProposals.push(...dependencyProposals);
        
        // Generate configuration fixes
        const configProposals = generateConfigFixes(findings);
        allProposals.push(...configProposals);
        
        // Generate code fixes
        const codeProposals = generateCodeFixes(findings);
        allProposals.push(...codeProposals);
        
        console.log(`✅ Generated ${allProposals.length} fix proposals total`);
        console.log(`   - Dependency fixes: ${dependencyProposals.length}`);
        console.log(`   - Configuration fixes: ${configProposals.length}`);
        console.log(`   - Code fixes: ${codeProposals.length}`);
        
        // Sort by confidence and risk
        return allProposals.sort((a, b) => {
            // Higher confidence first
            if (b.confidence !== a.confidence) {
                return b.confidence - a.confidence;
            }
            
            // Lower risk first
            const riskOrder = { 'LOW': 0, 'MEDIUM': 1, 'HIGH': 2 };
            return riskOrder[a.risk] - riskOrder[b.risk];
        });
        
    } catch (error) {
        console.error('❌ Error generating fix proposals:', error);
        return [];
    }
}

/**
 * Filter proposals by confidence threshold
 */
export function filterProposalsByConfidence(
    proposals: RemediationProposal[], 
    threshold: number
): RemediationProposal[] {
    return proposals.filter(proposal => proposal.confidence >= threshold);
}

/**
 * Group proposals by risk level
 */
export function groupProposalsByRisk(proposals: RemediationProposal[]): {
    LOW: RemediationProposal[];
    MEDIUM: RemediationProposal[];
    HIGH: RemediationProposal[];
} {
    return {
        LOW: proposals.filter(p => p.risk === 'LOW'),
        MEDIUM: proposals.filter(p => p.risk === 'MEDIUM'),
        HIGH: proposals.filter(p => p.risk === 'HIGH')
    };
}