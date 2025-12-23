/**
 * Phase 3.2 - Safety Policy Engine
 * 
 * Defines the rules and policies that govern what NAVI is allowed to do.
 * This is configurable per user/organization for enterprise safety.
 */

import { ActionType } from './ActionIntent';

export interface SafetyPolicy {
  autoApprove: {
    lowRisk: boolean;
    mediumRisk: boolean;
    highRisk: boolean;
  };
  requireConfirmationFor: ActionType[];
  allowBatchActions: boolean;
  maxBatchSize: number;
  allowDestructiveActions: boolean;
  requireBackupBefore: ActionType[];
  timeoutSeconds: number;
}

/**
 * Default safety policy - Conservative by design
 * Similar to Copilot/Cline but more explicit and auditable
 */
export const DefaultSafetyPolicy: SafetyPolicy = {
  autoApprove: {
    lowRisk: false,    // Never auto-approve - always ask user
    mediumRisk: false, // Never auto-approve - always ask user  
    highRisk: false    // Never auto-approve - always ask user
  },
  requireConfirmationFor: [
    'MODIFY_FILE',
    'DELETE_FILE', 
    'RUN_COMMAND',
    'COMMIT',
    'OPEN_PR'
  ],
  allowBatchActions: true,
  maxBatchSize: 10,
  allowDestructiveActions: false, // DELETE_FILE, etc.
  requireBackupBefore: [
    'MODIFY_FILE',
    'DELETE_FILE'
  ],
  timeoutSeconds: 300 // 5 minutes to approve
};

/**
 * Enterprise safety policy - More restrictive
 */
export const EnterpriseSafetyPolicy: SafetyPolicy = {
  autoApprove: {
    lowRisk: false,
    mediumRisk: false,
    highRisk: false
  },
  requireConfirmationFor: [
    'CREATE_FILE',
    'MODIFY_FILE',
    'DELETE_FILE',
    'RUN_COMMAND',
    'CREATE_BRANCH',
    'COMMIT',
    'OPEN_PR'
  ],
  allowBatchActions: false, // One action at a time
  maxBatchSize: 1,
  allowDestructiveActions: false,
  requireBackupBefore: [
    'CREATE_FILE',
    'MODIFY_FILE',
    'DELETE_FILE'
  ],
  timeoutSeconds: 600 // 10 minutes to approve
};

/**
 * Development safety policy - More permissive for rapid iteration
 */
export const DevelopmentSafetyPolicy: SafetyPolicy = {
  autoApprove: {
    lowRisk: true,     // Auto-approve low-risk actions
    mediumRisk: false, // Still ask for medium risk
    highRisk: false    // Never auto-approve high risk
  },
  requireConfirmationFor: [
    'DELETE_FILE',
    'RUN_COMMAND',
    'COMMIT',
    'OPEN_PR'
  ],
  allowBatchActions: true,
  maxBatchSize: 20,
  allowDestructiveActions: true,
  requireBackupBefore: [
    'MODIFY_FILE',
    'DELETE_FILE'
  ],
  timeoutSeconds: 120 // 2 minutes to approve
};

/**
 * Safety policy factory
 */
export class SafetyPolicyFactory {
  static createPolicy(mode: 'default' | 'enterprise' | 'development'): SafetyPolicy {
    switch (mode) {
      case 'enterprise':
        return EnterpriseSafetyPolicy;
      case 'development':
        return DevelopmentSafetyPolicy;
      default:
        return DefaultSafetyPolicy;
    }
  }
  
  static validatePolicy(policy: SafetyPolicy): boolean {
    // Validate policy constraints
    if (policy.maxBatchSize < 1) return false;
    if (policy.timeoutSeconds < 10) return false;
    
    // If destructive actions are not allowed, they should require confirmation
    if (!policy.allowDestructiveActions) {
      const destructiveActions: ActionType[] = ['DELETE_FILE', 'RUN_COMMAND'];
      for (const action of destructiveActions) {
        if (!policy.requireConfirmationFor.includes(action)) {
          return false;
        }
      }
    }
    
    return true;
  }
}