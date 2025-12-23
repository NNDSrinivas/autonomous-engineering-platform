/**
 * Phase 3.2 - Action Intent Model
 * 
 * Every action NAVI wants to take must be expressed as an ActionIntent.
 * This is what gets submitted to the approval system before execution.
 */

export type ActionType =
  | 'CREATE_FILE'
  | 'MODIFY_FILE'
  | 'DELETE_FILE'
  | 'RUN_COMMAND'
  | 'CREATE_BRANCH'
  | 'COMMIT'
  | 'OPEN_PR';

export interface ActionIntent {
  id: string;
  type: ActionType;
  description: string;
  filesAffected: string[];
  riskLevel: 'low' | 'medium' | 'high';
  reversible: boolean;
  metadata?: {
    reason?: string;
    estimatedImpact?: string;
    dependencies?: string[];
    testingRequired?: boolean;
  };
}

export interface BatchActionIntent {
  id: string;
  description: string;
  actions: ActionIntent[];
  overallRiskLevel: 'low' | 'medium' | 'high';
}

/**
 * Helper function to determine risk level based on action characteristics
 */
export function calculateRiskLevel(
  type: ActionType,
  filesAffected: string[],
  characteristics: {
    isTestFile?: boolean;
    isConfigFile?: boolean;
    isProductionCode?: boolean;
    affectsMultipleModules?: boolean;
  }
): 'low' | 'medium' | 'high' {
  // High risk conditions
  if (type === 'DELETE_FILE') return 'high';
  if (type === 'RUN_COMMAND') return 'high';
  if (characteristics.isConfigFile) return 'high';
  if (filesAffected.length > 10) return 'high';
  if (characteristics.affectsMultipleModules) return 'high';
  
  // Medium risk conditions
  if (type === 'MODIFY_FILE' && characteristics.isProductionCode) return 'medium';
  if (filesAffected.length > 3) return 'medium';
  
  // Low risk conditions
  if (characteristics.isTestFile) return 'low';
  if (type === 'CREATE_FILE' && filesAffected.length === 1) return 'low';
  
  // Default to medium for safety
  return 'medium';
}

/**
 * Generate a unique intent ID
 */
export function generateIntentId(): string {
  return `intent_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}