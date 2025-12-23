/**
 * Phase 3.2 - User Consent State
 * 
 * Tracks what the user has approved, declined, or set policies for.
 * This ensures we don't ask for the same approval twice and respects user preferences.
 */

import { ActionType } from './ActionIntent';

export interface ConsentRecord {
  actionType: ActionType;
  description: string;
  timestamp: Date;
  approved: boolean;
  rememberChoice?: boolean; // User asked to remember this choice
  expiresAt?: Date; // When this consent expires
}

export interface ConsentPolicy {
  // Auto-approve these action types (user granted blanket permission)
  alwaysApprove: ActionType[];
  
  // Never approve these action types (user explicitly blocked)
  neverApprove: ActionType[];
  
  // Ask every time for these
  alwaysAsk: ActionType[];
  
  // Session-specific approvals (reset when VS Code restarts)
  sessionApprovals: ActionType[];
}

export class UserConsentState {
  private consentHistory: ConsentRecord[] = [];
  private policy: ConsentPolicy = {
    alwaysApprove: [],
    neverApprove: [],
    alwaysAsk: [],
    sessionApprovals: []
  };
  
  /**
   * Check if we already have consent for this type of action
   */
  hasExistingConsent(actionType: ActionType, description?: string): 'approved' | 'denied' | 'ask' {
    // Check permanent policy first
    if (this.policy.alwaysApprove.includes(actionType)) {
      return 'approved';
    }
    
    if (this.policy.neverApprove.includes(actionType)) {
      return 'denied';
    }
    
    if (this.policy.alwaysAsk.includes(actionType)) {
      return 'ask';
    }
    
    // Check session approvals
    if (this.policy.sessionApprovals.includes(actionType)) {
      return 'approved';
    }
    
    // Check recent consent history
    const recentConsent = this.consentHistory
      .filter(record => record.actionType === actionType)
      .filter(record => !record.expiresAt || record.expiresAt > new Date())
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())[0];
    
    if (recentConsent) {
      if (recentConsent.rememberChoice) {
        return recentConsent.approved ? 'approved' : 'denied';
      }
      
      // If it's the same description and within last 5 minutes, reuse consent
      if (description && recentConsent.description === description) {
        const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
        if (recentConsent.timestamp > fiveMinutesAgo) {
          return recentConsent.approved ? 'approved' : 'denied';
        }
      }
    }
    
    return 'ask';
  }
  
  /**
   * Record user's consent decision
   */
  recordConsent(
    actionType: ActionType,
    description: string,
    approved: boolean,
    options: {
      rememberChoice?: boolean;
      sessionOnly?: boolean;
      expirationMinutes?: number;
    } = {}
  ): void {
    const record: ConsentRecord = {
      actionType,
      description,
      timestamp: new Date(),
      approved,
      rememberChoice: options.rememberChoice
    };
    
    if (options.expirationMinutes) {
      record.expiresAt = new Date(Date.now() + options.expirationMinutes * 60 * 1000);
    }
    
    this.consentHistory.push(record);
    
    // Update policy based on user choice
    if (options.rememberChoice) {
      if (approved) {
        this.addToPolicy('alwaysApprove', actionType);
      } else {
        this.addToPolicy('neverApprove', actionType);
      }
    } else if (options.sessionOnly && approved) {
      this.addToPolicy('sessionApprovals', actionType);
    }
    
    // Keep history manageable
    this.trimHistory();
  }
  
  /**
   * Set user policy for an action type
   */
  setActionPolicy(actionType: ActionType, policy: 'always' | 'never' | 'ask' | 'session'): void {
    // Remove from all existing policies
    this.removeFromAllPolicies(actionType);
    
    // Add to appropriate policy
    switch (policy) {
      case 'always':
        this.policy.alwaysApprove.push(actionType);
        break;
      case 'never':
        this.policy.neverApprove.push(actionType);
        break;
      case 'ask':
        this.policy.alwaysAsk.push(actionType);
        break;
      case 'session':
        this.policy.sessionApprovals.push(actionType);
        break;
    }
  }
  
  /**
   * Clear session-specific approvals (called on extension restart)
   */
  clearSessionApprovals(): void {
    this.policy.sessionApprovals = [];
  }
  
  /**
   * Get current policy for debugging/UI
   */
  getPolicy(): ConsentPolicy {
    return { ...this.policy };
  }
  
  /**
   * Get recent consent history
   */
  getRecentHistory(limit: number = 10): ConsentRecord[] {
    return this.consentHistory
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      .slice(0, limit);
  }
  
  /**
   * Clear expired consent records
   */
  cleanupExpiredConsent(): void {
    const now = new Date();
    this.consentHistory = this.consentHistory.filter(
      record => !record.expiresAt || record.expiresAt > now
    );
  }
  
  /**
   * Export state for persistence
   */
  exportState(): {
    consentHistory: ConsentRecord[];
    policy: ConsentPolicy;
  } {
    return {
      consentHistory: [...this.consentHistory],
      policy: { ...this.policy }
    };
  }
  
  /**
   * Import state from persistence
   */
  importState(state: {
    consentHistory: ConsentRecord[];
    policy: ConsentPolicy;
  }): void {
    this.consentHistory = state.consentHistory.map(record => ({
      ...record,
      timestamp: new Date(record.timestamp),
      expiresAt: record.expiresAt ? new Date(record.expiresAt) : undefined
    }));
    this.policy = { ...state.policy };
    
    // Clear expired records after import
    this.cleanupExpiredConsent();
  }
  
  /**
   * Reset all consent (nuclear option)
   */
  reset(): void {
    this.consentHistory = [];
    this.policy = {
      alwaysApprove: [],
      neverApprove: [],
      alwaysAsk: [],
      sessionApprovals: []
    };
  }
  
  // Private helper methods
  
  private addToPolicy(policyType: keyof ConsentPolicy, actionType: ActionType): void {
    const array = this.policy[policyType] as ActionType[];
    if (!array.includes(actionType)) {
      array.push(actionType);
    }
  }
  
  private removeFromAllPolicies(actionType: ActionType): void {
    this.policy.alwaysApprove = this.policy.alwaysApprove.filter(t => t !== actionType);
    this.policy.neverApprove = this.policy.neverApprove.filter(t => t !== actionType);
    this.policy.alwaysAsk = this.policy.alwaysAsk.filter(t => t !== actionType);
    this.policy.sessionApprovals = this.policy.sessionApprovals.filter(t => t !== actionType);
  }
  
  private trimHistory(): void {
    // Keep last 100 records
    if (this.consentHistory.length > 100) {
      this.consentHistory = this.consentHistory
        .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        .slice(0, 100);
    }
  }
}