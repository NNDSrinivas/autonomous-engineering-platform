/**
 * Phase 3.2 - Approval Engine
 * 
 * The core decision engine that determines whether an action requires user approval.
 * This is called BEFORE any executor runs - nothing bypasses this gate.
 */

import { ActionIntent, ActionType, BatchActionIntent } from './ActionIntent';
import { SafetyPolicy } from './SafetyPolicy';

export interface ApprovalDecision {
  requiresApproval: boolean;
  reason: string;
  riskFactors: string[];
  autoApprovalBlocked?: string; // Why auto-approval was blocked
}

export class ApprovalEngine {
  constructor(private policy: SafetyPolicy) {}
  
  /**
   * Core decision function - determines if an action needs user approval
   */
  requiresApproval(intent: ActionIntent): ApprovalDecision {
    const riskFactors: string[] = [];
    let requiresApproval = false;
    let reason = '';
    let autoApprovalBlocked: string | undefined;
    
    // Check risk level against auto-approval policy
    let autoApproveForRisk: boolean = false;
    if (intent.riskLevel === 'low') {
      autoApproveForRisk = this.policy.autoApprove.lowRisk;
    } else if (intent.riskLevel === 'medium') {
      autoApproveForRisk = this.policy.autoApprove.mediumRisk;
    } else if (intent.riskLevel === 'high') {
      autoApproveForRisk = this.policy.autoApprove.highRisk;
    }
    
    if (intent.riskLevel === 'high') {
      requiresApproval = true;
      reason = 'High-risk action requires manual approval';
      riskFactors.push(`High risk: ${intent.description}`);
    } else if (intent.riskLevel === 'medium' && !autoApproveForRisk) {
      requiresApproval = true;
      reason = 'Medium-risk action requires approval per policy';
      autoApprovalBlocked = 'Auto-approval disabled for medium risk actions';
      riskFactors.push(`Medium risk: affects ${intent.filesAffected.length} files`);
    } else if (intent.riskLevel === 'low' && !autoApproveForRisk) {
      requiresApproval = true;
      reason = 'Low-risk action requires approval per policy';
      autoApprovalBlocked = 'Auto-approval disabled for low risk actions';
    }
    
    // Check if action type requires confirmation
    if (this.policy.requireConfirmationFor.includes(intent.type)) {
      requiresApproval = true;
      if (!reason) {
        reason = `Action type '${intent.type}' requires confirmation`;
      }
      riskFactors.push(`Explicit confirmation required for ${intent.type}`);
    }
    
    // Check destructive actions
    if (this.isDestructiveAction(intent.type) && !this.policy.allowDestructiveActions) {
      requiresApproval = true;
      reason = 'Destructive action blocked by policy';
      riskFactors.push('Destructive action not allowed');
    }
    
    // Check file impact
    if (intent.filesAffected.length > 5) {
      requiresApproval = true;
      riskFactors.push(`Affects many files (${intent.filesAffected.length})`);
      if (!reason) {
        reason = 'Action affects multiple files';
      }
    }
    
    // Check for non-reversible actions
    if (!intent.reversible) {
      requiresApproval = true;
      riskFactors.push('Action is not reversible');
      if (!reason) {
        reason = 'Non-reversible action requires approval';
      }
    }
    
    return {
      requiresApproval,
      reason: reason || 'Action approved automatically',
      riskFactors,
      autoApprovalBlocked
    };
  }
  
  /**
   * Evaluate batch actions
   */
  requiresBatchApproval(batchIntent: BatchActionIntent): ApprovalDecision {
    if (!this.policy.allowBatchActions) {
      return {
        requiresApproval: true,
        reason: 'Batch actions not allowed by policy',
        riskFactors: ['Batch operations disabled']
      };
    }
    
    if (batchIntent.actions.length > this.policy.maxBatchSize) {
      return {
        requiresApproval: true,
        reason: `Batch size (${batchIntent.actions.length}) exceeds limit (${this.policy.maxBatchSize})`,
        riskFactors: ['Batch size too large']
      };
    }
    
    // Check each individual action
    const highRiskActions = batchIntent.actions.filter(action => 
      this.requiresApproval(action).requiresApproval
    );
    
    if (highRiskActions.length > 0) {
      return {
        requiresApproval: true,
        reason: `Batch contains ${highRiskActions.length} actions requiring approval`,
        riskFactors: [`${highRiskActions.length} high-risk actions in batch`]
      };
    }
    
    return {
      requiresApproval: false,
      reason: 'Batch approved automatically',
      riskFactors: []
    };
  }
  
  /**
   * Check if an action type is considered destructive
   */
  private isDestructiveAction(type: ActionType): boolean {
    return ['DELETE_FILE', 'RUN_COMMAND'].includes(type);
  }
  
  /**
   * Get human-readable explanation for why approval is needed
   */
  getApprovalExplanation(intent: ActionIntent): string {
    const decision = this.requiresApproval(intent);
    
    if (!decision.requiresApproval) {
      return 'This action can be performed automatically.';
    }
    
    let explanation = `Approval required: ${decision.reason}\n\n`;
    
    if (decision.riskFactors.length > 0) {
      explanation += 'Risk factors:\n';
      decision.riskFactors.forEach(factor => {
        explanation += `• ${factor}\n`;
      });
    }
    
    if (decision.autoApprovalBlocked) {
      explanation += `\nAuto-approval blocked: ${decision.autoApprovalBlocked}`;
    }
    
    return explanation.trim();
  }
  
  /**
   * Update policy (for runtime configuration changes)
   */
  updatePolicy(newPolicy: SafetyPolicy): void {
    this.policy = newPolicy;
  }
}