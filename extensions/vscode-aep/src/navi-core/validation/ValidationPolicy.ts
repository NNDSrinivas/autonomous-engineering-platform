/**
 * Phase 3.4 - Validation Policy
 * 
 * Controls automation levels and approval requirements for different validation
 * scenarios. This gives users fine-grained control over NAVI's autonomous
 * behavior while maintaining safety.
 */

import { ValidationType } from './ValidationEngine';

export interface ValidationPolicy {
  // Auto-fixing controls
  allowAutoFix: boolean;
  allowUnapprovedFixes: boolean;
  maxRetries: number;
  maxHealingAttempts: number;
  
  // What types of issues can be auto-fixed
  allowedAutoFixTypes: ValidationType[];
  
  // Validation controls
  requiredValidations: ValidationType[];
  optionalValidations: ValidationType[];
  skipValidationsFor: ValidationType[];
  
  // Approval requirements
  requireApprovalFor: ValidationType[];
  requireApprovalThreshold: number; // Minimum confidence score to auto-fix
  
  // Time limits
  maxValidationTime: number; // ms
  maxHealingTime: number; // ms
  
  // User experience
  showDetailedOutput: boolean;
  notifyOnAutoFix: boolean;
  createUndoCheckpoints: boolean;
}

export class ValidationPolicyManager {
  /**
   * Get default policy for new users (conservative)
   */
  static getDefaultPolicy(): ValidationPolicy {
    return {
      allowAutoFix: true,
      allowUnapprovedFixes: false,
      maxRetries: 3,
      maxHealingAttempts: 2,
      
      allowedAutoFixTypes: ['syntax', 'format', 'lint'],
      
      requiredValidations: ['syntax', 'typecheck'],
      optionalValidations: ['lint', 'format'],
      skipValidationsFor: [],
      
      requireApprovalFor: ['test', 'build', 'security'],
      requireApprovalThreshold: 0.8,
      
      maxValidationTime: 30000, // 30 seconds
      maxHealingTime: 60000, // 1 minute
      
      showDetailedOutput: false,
      notifyOnAutoFix: true,
      createUndoCheckpoints: true
    };
  }
  
  /**
   * Get enterprise policy (strict controls)
   */
  static getEnterprisePolicy(): ValidationPolicy {
    return {
      allowAutoFix: true,
      allowUnapprovedFixes: false,
      maxRetries: 2,
      maxHealingAttempts: 1,
      
      allowedAutoFixTypes: ['format'], // Only formatting fixes
      
      requiredValidations: ['syntax', 'typecheck', 'lint', 'test', 'security'],
      optionalValidations: ['build'],
      skipValidationsFor: [],
      
      requireApprovalFor: ['syntax', 'typecheck', 'test', 'build', 'security'],
      requireApprovalThreshold: 0.9,
      
      maxValidationTime: 60000, // 1 minute
      maxHealingTime: 30000, // 30 seconds
      
      showDetailedOutput: true,
      notifyOnAutoFix: true,
      createUndoCheckpoints: true
    };
  }
  
  /**
   * Get development policy (permissive for fast iteration)
   */
  static getDevelopmentPolicy(): ValidationPolicy {
    return {
      allowAutoFix: true,
      allowUnapprovedFixes: true,
      maxRetries: 5,
      maxHealingAttempts: 3,
      
      allowedAutoFixTypes: ['syntax', 'typecheck', 'lint', 'format'],
      
      requiredValidations: ['syntax', 'typecheck'],
      optionalValidations: ['lint', 'format', 'test'],
      skipValidationsFor: ['security'], // Skip slow security scans in dev
      
      requireApprovalFor: [],
      requireApprovalThreshold: 0.6,
      
      maxValidationTime: 15000, // 15 seconds
      maxHealingTime: 120000, // 2 minutes
      
      showDetailedOutput: true,
      notifyOnAutoFix: false,
      createUndoCheckpoints: true
    };
  }
  
  /**
   * Get CI/CD policy (fully autonomous)
   */
  static getCIPolicy(): ValidationPolicy {
    return {
      allowAutoFix: true,
      allowUnapprovedFixes: true,
      maxRetries: 3,
      maxHealingAttempts: 2,
      
      allowedAutoFixTypes: ['syntax', 'typecheck', 'lint', 'format'],
      
      requiredValidations: ['syntax', 'typecheck', 'lint', 'test', 'build'],
      optionalValidations: ['security'],
      skipValidationsFor: [],
      
      requireApprovalFor: [],
      requireApprovalThreshold: 0.7,
      
      maxValidationTime: 120000, // 2 minutes
      maxHealingTime: 300000, // 5 minutes
      
      showDetailedOutput: true,
      notifyOnAutoFix: false,
      createUndoCheckpoints: false // CI doesn't need undo
    };
  }
  
  /**
   * Create a custom policy based on user preferences
   */
  static createCustomPolicy(overrides: Partial<ValidationPolicy>): ValidationPolicy {
    const defaultPolicy = this.getDefaultPolicy();
    return { ...defaultPolicy, ...overrides };
  }
  
  /**
   * Get policy based on context (workspace settings, user role, etc.)
   */
  static getPolicyForContext(context: {
    userRole?: 'junior' | 'senior' | 'lead';
    environment?: 'development' | 'staging' | 'production' | 'ci';
    projectType?: 'personal' | 'team' | 'enterprise';
    riskTolerance?: 'low' | 'medium' | 'high';
  }): ValidationPolicy {
    // Environment-based selection
    if (context.environment === 'ci') {
      return this.getCIPolicy();
    }
    
    if (context.environment === 'development') {
      return this.getDevelopmentPolicy();
    }
    
    // Role-based selection
    if (context.userRole === 'junior') {
      return this.createCustomPolicy({
        allowUnapprovedFixes: false,
        maxRetries: 2,
        allowedAutoFixTypes: ['format'],
        requireApprovalFor: ['syntax', 'typecheck', 'lint', 'test'],
        requireApprovalThreshold: 0.9
      });
    }
    
    if (context.userRole === 'senior' || context.userRole === 'lead') {
      return this.createCustomPolicy({
        allowUnapprovedFixes: true,
        maxRetries: 5,
        allowedAutoFixTypes: ['syntax', 'typecheck', 'lint', 'format'],
        requireApprovalFor: ['test', 'security'],
        requireApprovalThreshold: 0.7
      });
    }
    
    // Project type selection
    if (context.projectType === 'enterprise') {
      return this.getEnterprisePolicy();
    }
    
    // Risk tolerance adjustment
    const basePolicy = this.getDefaultPolicy();
    
    if (context.riskTolerance === 'low') {
      return this.createCustomPolicy({
        ...basePolicy,
        allowUnapprovedFixes: false,
        requireApprovalFor: ['syntax', 'typecheck', 'lint', 'test', 'build', 'security'],
        requireApprovalThreshold: 0.95
      });
    }
    
    if (context.riskTolerance === 'high') {
      return this.createCustomPolicy({
        ...basePolicy,
        allowUnapprovedFixes: true,
        maxRetries: 10,
        allowedAutoFixTypes: ['syntax', 'typecheck', 'lint', 'format', 'test'],
        requireApprovalFor: [],
        requireApprovalThreshold: 0.5
      });
    }
    
    return basePolicy;
  }
  
  /**
   * Validate that a policy configuration is safe and consistent
   */
  static validatePolicy(policy: ValidationPolicy): {
    valid: boolean;
    warnings: string[];
    errors: string[];
  } {
    const warnings: string[] = [];
    const errors: string[] = [];
    
    // Check required validations include basics
    if (!policy.requiredValidations.includes('syntax')) {
      warnings.push('Syntax validation should be required for code safety');
    }
    
    // Check auto-fix types are reasonable
    if (policy.allowedAutoFixTypes.includes('security') && policy.allowUnapprovedFixes) {
      errors.push('Auto-fixing security issues without approval is dangerous');
    }
    
    // Check time limits are reasonable
    if (policy.maxValidationTime < 5000) {
      warnings.push('Very short validation timeout may cause incomplete checks');
    }
    
    if (policy.maxHealingTime > 600000) { // 10 minutes
      warnings.push('Very long healing timeout may block user workflow');
    }
    
    // Check retry limits
    if (policy.maxRetries > 10) {
      warnings.push('High retry limit may cause infinite loops on persistent issues');
    }
    
    if (policy.maxRetries === 0 && policy.allowAutoFix) {
      errors.push('Auto-fix enabled but retry limit is 0');
    }
    
    // Check approval consistency
    if (policy.allowUnapprovedFixes && policy.requireApprovalFor.length > 0) {
      warnings.push('Approval requirements may be bypassed by allowUnapprovedFixes setting');
    }
    
    return {
      valid: errors.length === 0,
      warnings,
      errors
    };
  }
  
  /**
   * Get a human-readable description of a policy
   */
  static describePolicy(policy: ValidationPolicy): string {
    const parts: string[] = [];
    
    // Auto-fix status
    if (policy.allowAutoFix) {
      parts.push(`✅ Auto-fix enabled (${policy.allowedAutoFixTypes.length} types)`);
      
      if (policy.allowUnapprovedFixes) {
        parts.push('⚡ Unapproved fixes allowed');
      } else {
        parts.push('🔒 Approval required for fixes');
      }
    } else {
      parts.push('❌ Auto-fix disabled');
    }
    
    // Validation scope
    parts.push(`🔍 Required: ${policy.requiredValidations.join(', ')}`);
    
    if (policy.requireApprovalFor.length > 0) {
      parts.push(`👤 Approval needed: ${policy.requireApprovalFor.join(', ')}`);
    }
    
    // Limits
    parts.push(`🔄 Max ${policy.maxRetries} retries, ${policy.maxHealingAttempts} healing attempts`);
    
    // User experience
    if (policy.notifyOnAutoFix) {
      parts.push('🔔 Notifications enabled');
    }
    
    if (policy.createUndoCheckpoints) {
      parts.push('⏪ Undo checkpoints created');
    }
    
    return parts.join('\n');
  }
}