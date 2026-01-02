/**
 * Phase 3.3 - Change Plan
 * 
 * CRITICAL ABSTRACTION: NAVI never generates code directly into files.
 * It generates a plan first. This prevents partial application and ensures
 * atomic, coherent changes across multiple files.
 */

import { ActionIntent } from '../safety/ActionIntent';

export interface ChangePlan {
  // High-level intent
  id: string;
  intent: string;
  description: string;
  timestamp: Date;
  
  // Structured changes
  steps: ChangeStep[];
  
  // Dependencies and order
  dependencies: string[]; // Other files that might be affected
  executionOrder: 'sequential' | 'parallel';
  
  // Risk assessment
  riskLevel: 'low' | 'medium' | 'high';
  reversible: boolean;
  
  // Validation
  expectedOutcome: string;
  testableConditions: string[];
}

export interface ChangeStep {
  id: string;
  filePath: string;
  operation: 'create' | 'modify' | 'delete' | 'move';
  description: string;
  
  // For create/modify operations
  content?: string;
  
  // For modify operations - precise edits
  edits?: FileEdit[];
  
  // For move operations
  newPath?: string;
  
  // Metadata
  reasoning: string;
  impactAssessment: string;
}

export interface FileEdit {
  type: 'insert' | 'replace' | 'delete';
  startLine: number;
  endLine?: number; // For replace/delete
  content?: string; // For insert/replace
  reasoning: string;
}

export interface ChangePlanValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

export class ChangePlanBuilder {
  /**
   * Create a new change plan from user intent
   */
  static create(intent: string): ChangePlan {
    return {
      id: this.generateId(),
      intent,
      description: `Implementing: ${intent}`,
      timestamp: new Date(),
      steps: [],
      dependencies: [],
      executionOrder: 'sequential',
      riskLevel: 'medium',
      reversible: true,
      expectedOutcome: '',
      testableConditions: []
    };
  }
  
  /**
   * Add a file creation step
   */
  static addFileCreation(
    plan: ChangePlan,
    filePath: string,
    content: string,
    reasoning: string
  ): ChangePlan {
    const step: ChangeStep = {
      id: this.generateStepId(),
      filePath,
      operation: 'create',
      description: `Create ${filePath}`,
      content,
      reasoning,
      impactAssessment: `New file will be created at ${filePath}`
    };
    
    return {
      ...plan,
      steps: [...plan.steps, step]
    };
  }
  
  /**
   * Add a file modification step with precise edits
   */
  static addFileModification(
    plan: ChangePlan,
    filePath: string,
    edits: FileEdit[],
    reasoning: string
  ): ChangePlan {
    const step: ChangeStep = {
      id: this.generateStepId(),
      filePath,
      operation: 'modify',
      description: `Modify ${filePath}`,
      edits,
      reasoning,
      impactAssessment: `${edits.length} edit(s) will be applied to ${filePath}`
    };
    
    return {
      ...plan,
      steps: [...plan.steps, step]
    };
  }
  
  /**
   * Add a file deletion step
   */
  static addFileDeletion(
    plan: ChangePlan,
    filePath: string,
    reasoning: string
  ): ChangePlan {
    const step: ChangeStep = {
      id: this.generateStepId(),
      filePath,
      operation: 'delete',
      description: `Delete ${filePath}`,
      reasoning,
      impactAssessment: `File ${filePath} will be permanently removed`
    };
    
    // Deletion is high risk and not easily reversible
    return {
      ...plan,
      steps: [...plan.steps, step],
      riskLevel: 'high',
      reversible: false
    };
  }
  
  /**
   * Convert ChangePlan to ActionIntent for safety system
   */
  static toActionIntent(plan: ChangePlan): ActionIntent {
    const filesAffected = plan.steps.map(step => step.filePath);
    const hasCreation = plan.steps.some(step => step.operation === 'create');
    const hasDeletion = plan.steps.some(step => step.operation === 'delete');
    
    let actionType: ActionIntent['type'] = 'MODIFY_FILE';
    if (hasCreation) actionType = 'CREATE_FILE';
    if (hasDeletion) actionType = 'DELETE_FILE';
    
    return {
      id: plan.id,
      type: actionType,
      description: plan.description,
      filesAffected,
      riskLevel: plan.riskLevel,
      reversible: plan.reversible,
      metadata: {
        reason: `Complex plan with ${plan.steps.length} steps`,
        dependencies: plan.dependencies,
        testingRequired: plan.testableConditions.length > 0
      }
    };
  }
  
  /**
   * Validate a change plan before execution
   */
  static validate(plan: ChangePlan): ChangePlanValidation {
    const validation: ChangePlanValidation = {
      valid: true,
      errors: [],
      warnings: [],
      suggestions: []
    };
    
    // Check for empty plan
    if (plan.steps.length === 0) {
      validation.errors.push('Change plan contains no steps');
      validation.valid = false;
    }
    
    // Check for conflicting file operations
    const filePaths = plan.steps.map(step => step.filePath);
    const duplicates = filePaths.filter((path, index) => filePaths.indexOf(path) !== index);
    
    if (duplicates.length > 0) {
      const conflictingSteps = plan.steps.filter(step => 
        duplicates.includes(step.filePath)
      );
      
      // Check if conflicts are resolvable
      const hasCreateAndModify = conflictingSteps.some(s => s.operation === 'create') &&
                                conflictingSteps.some(s => s.operation === 'modify');
      
      if (hasCreateAndModify) {
        validation.errors.push(`Cannot create and modify the same file: ${duplicates[0]}`);
        validation.valid = false;
      } else {
        validation.warnings.push(`Multiple operations on same file: ${duplicates.join(', ')}`);
      }
    }
    
    // Check file edit validity
    for (const step of plan.steps) {
      if (step.operation === 'modify' && step.edits) {
        for (const edit of step.edits) {
          if (edit.startLine < 0) {
            validation.errors.push(`Invalid start line ${edit.startLine} in ${step.filePath}`);
            validation.valid = false;
          }
          
          if (edit.endLine && edit.endLine < edit.startLine) {
            validation.errors.push(`End line before start line in ${step.filePath}`);
            validation.valid = false;
          }
        }
      }
    }
    
    // Risk assessment warnings
    if (plan.riskLevel === 'high') {
      validation.warnings.push('High-risk plan - consider breaking into smaller changes');
    }
    
    if (!plan.reversible) {
      validation.warnings.push('Plan contains irreversible operations');
    }
    
    // Suggestions
    if (plan.steps.length > 10) {
      validation.suggestions.push('Consider breaking large plan into multiple smaller plans');
    }
    
    if (plan.testableConditions.length === 0) {
      validation.suggestions.push('Add testable conditions to verify success');
    }
    
    return validation;
  }
  
  /**
   * Get a human-readable summary of the plan
   */
  static summarize(plan: ChangePlan): string {
    const stepsByType = plan.steps.reduce((acc, step) => {
      acc[step.operation] = (acc[step.operation] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    const operations = Object.entries(stepsByType)
      .map(([op, count]) => `${count} ${op}`)
      .join(', ');
    
    return `${plan.description} (${operations} across ${plan.steps.length} steps)`;
  }
  
  // Private helpers
  
  private static generateId(): string {
    return `plan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  private static generateStepId(): string {
    return `step_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}