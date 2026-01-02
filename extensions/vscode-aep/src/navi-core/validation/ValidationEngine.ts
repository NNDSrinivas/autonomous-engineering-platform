/**
 * Phase 3.4 - Validation Engine
 * 
 * The core orchestrator that ensures NAVI behaves like a Staff Engineer who 
 * never submits broken code. This is what transforms NAVI from code generator 
 * to engineering agent - comprehensive validation with self-healing capabilities.
 */

import * as vscode from 'vscode';
import { RepoContext } from '../context/RepoContextBuilder';
import { ChangePlan } from '../generation/ChangePlan';

export interface ValidationContext {
  // Core context
  workspaceRoot: string;
  language: string;
  framework?: string;
  repoContext: RepoContext;
  
  // What was changed
  changePlan?: ChangePlan;
  modifiedFiles: string[];
  
  // Validation scope
  validationTypes: ValidationType[];
  
  // Policy controls
  allowAutoFix: boolean;
  maxRetries: number;
  skipValidation: ValidationType[];
}

export interface ValidationResult {
  passed: boolean;
  issues: ValidationIssue[];
  summary: ValidationSummary;
  executionTime: number;
  timestamp: Date;
}

export interface ValidationIssue {
  id: string;
  type: ValidationType;
  severity: 'blocking' | 'warning' | 'info';
  message: string;
  file?: string;
  line?: number;
  column?: number;
  suggestion?: string;
  fixable: boolean;
  rawOutput?: string; // Original tool output for debugging
}

export interface ValidationSummary {
  totalChecks: number;
  passed: number;
  failed: number;
  warnings: number;
  blockers: number;
  skipped: number;
}

export type ValidationType = 
  | 'syntax' 
  | 'typecheck' 
  | 'lint' 
  | 'test' 
  | 'build' 
  | 'security' 
  | 'format' 
  | 'deps';

export class ValidationEngine {
  private validators: Map<ValidationType, Validator> = new Map();
  
  constructor() {
    this.initializeValidators();
  }
  
  /**
   * Main validation orchestrator - runs all applicable validations
   */
  async validate(context: ValidationContext): Promise<ValidationResult> {
    const startTime = Date.now();
    console.log(`🧪 Starting validation for ${context.modifiedFiles.length} files`);
    
    // Get applicable validators
    const applicableValidators = this.getApplicableValidators(context);
    console.log(`📋 Running ${applicableValidators.length} validators: ${applicableValidators.map(v => v.type).join(', ')}`);
    
    const issues: ValidationIssue[] = [];
    let passed = 0;
    let failed = 0;
    let warnings = 0;
    let blockers = 0;
    let skipped = 0;
    
    // Run validations in parallel where possible
    const validationPromises = applicableValidators.map(async (validator) => {
      if (context.skipValidation.includes(validator.type)) {
        skipped++;
        return [];
      }
      
      try {
        console.log(`🔍 Running ${validator.type} validation...`);
        const validatorIssues = await validator.validate(context);
        
        if (validatorIssues.length === 0) {
          passed++;
          console.log(`✅ ${validator.type} validation passed`);
        } else {
          failed++;
          const blockingIssues = validatorIssues.filter(i => i.severity === 'blocking');
          const warningIssues = validatorIssues.filter(i => i.severity === 'warning');
          
          blockers += blockingIssues.length;
          warnings += warningIssues.length;
          
          console.log(`❌ ${validator.type} validation failed: ${blockingIssues.length} blockers, ${warningIssues.length} warnings`);
        }
        
        return validatorIssues;
      } catch (error) {
        console.error(`💥 ${validator.type} validator crashed:`, error);
        failed++;
        blockers++;
        
        return [{
          id: `${validator.type}_crash`,
          type: validator.type,
          severity: 'blocking' as const,
          message: `${validator.type} validation failed: ${error instanceof Error ? error.message : String(error)}`,
          fixable: false,
          rawOutput: error instanceof Error ? error.stack : String(error)
        }];
      }
    });
    
    // Collect all results
    const allIssues = await Promise.all(validationPromises);
    issues.push(...allIssues.flat());
    
    const executionTime = Date.now() - startTime;
    const totalPassed = issues.length === 0;
    
    const result: ValidationResult = {
      passed: totalPassed,
      issues,
      summary: {
        totalChecks: applicableValidators.length,
        passed,
        failed,
        warnings,
        blockers,
        skipped
      },
      executionTime,
      timestamp: new Date()
    };
    
    console.log(`🎯 Validation complete: ${totalPassed ? 'PASSED' : 'FAILED'} (${executionTime}ms)`);
    console.log(`📊 Summary: ${passed} passed, ${failed} failed, ${warnings} warnings, ${blockers} blockers`);
    
    return result;
  }
  
  /**
   * Get validators that apply to this context
   */
  private getApplicableValidators(context: ValidationContext): Validator[] {
    const applicable: Validator[] = [];
    
    for (const validationType of context.validationTypes) {
      const validator = this.validators.get(validationType);
      if (validator && validator.appliesTo(context)) {
        applicable.push(validator);
      }
    }
    
    return applicable;
  }
  
  /**
   * Initialize available validators
   */
  private initializeValidators(): void {
    // Syntax validation (universal)
    this.validators.set('syntax', new SyntaxValidator());
    
    // TypeScript-specific
    this.validators.set('typecheck', new TypeCheckValidator());
    
    // Code quality
    this.validators.set('lint', new LintValidator());
    this.validators.set('format', new FormatValidator());
    
    // Testing
    this.validators.set('test', new TestValidator());
    
    // Build system
    this.validators.set('build', new BuildValidator());
    
    // Security
    this.validators.set('security', new SecurityValidator());
    
    // Dependencies
    this.validators.set('deps', new DependencyValidator());
  }
  
  /**
   * Get default validation types for a language/framework
   */
  static getDefaultValidations(language: string, framework?: string): ValidationType[] {
    const defaults: ValidationType[] = ['syntax'];
    
    if (language === 'typescript' || language === 'javascript') {
      defaults.push('typecheck', 'lint', 'format');
      
      if (framework === 'react') {
        defaults.push('test');
      }
    }
    
    if (language === 'java') {
      defaults.push('build', 'test', 'lint');
    }
    
    if (language === 'python') {
      defaults.push('lint', 'format', 'test', 'security');
    }
    
    // Always include dependency validation
    defaults.push('deps');
    
    return defaults;
  }
}

/**
 * Base validator interface
 */
export abstract class Validator {
  abstract type: ValidationType;
  abstract name: string;
  abstract description: string;
  
  /**
   * Check if this validator applies to the given context
   */
  abstract appliesTo(context: ValidationContext): boolean;
  
  /**
   * Run the validation and return issues
   */
  abstract validate(context: ValidationContext): Promise<ValidationIssue[]>;
  
  /**
   * Helper to create validation issues
   */
  protected createIssue(
    type: ValidationType,
    severity: ValidationIssue['severity'],
    message: string,
    options: Partial<ValidationIssue> = {}
  ): ValidationIssue {
    return {
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type,
      severity,
      message,
      fixable: false,
      ...options
    };
  }
}

/**
 * Syntax validation (uses VS Code diagnostics)
 */
class SyntaxValidator extends Validator {
  type: ValidationType = 'syntax';
  name = 'Syntax Check';
  description = 'Validates code syntax and basic structure';
  
  appliesTo(context: ValidationContext): boolean {
    // Syntax validation applies to all languages
    return true;
  }
  
  async validate(context: ValidationContext): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];
    
    for (const filePath of context.modifiedFiles) {
      try {
        // Use VS Code's diagnostic API
        const uri = vscode.Uri.file(filePath);
        const diagnostics = vscode.languages.getDiagnostics(uri);
        
        for (const diagnostic of diagnostics) {
          // Only include syntax and compiler errors
          if (diagnostic.source === 'typescript' || diagnostic.source === 'python' || diagnostic.source === 'java') {
            const severity = diagnostic.severity === vscode.DiagnosticSeverity.Error ? 'blocking' : 'warning';
            
            issues.push(this.createIssue(
              'syntax',
              severity,
              diagnostic.message,
              {
                file: filePath,
                line: diagnostic.range.start.line + 1,
                column: diagnostic.range.start.character + 1,
                fixable: diagnostic.code !== undefined
              }
            ));
          }
        }
      } catch (error) {
        issues.push(this.createIssue(
          'syntax',
          'blocking',
          `Failed to check syntax for ${filePath}: ${error instanceof Error ? error.message : String(error)}`,
          { file: filePath }
        ));
      }
    }
    
    return issues;
  }
}

/**
 * TypeScript type checking
 */
class TypeCheckValidator extends Validator {
  type: ValidationType = 'typecheck';
  name = 'Type Check';
  description = 'TypeScript type checking and compilation';
  
  appliesTo(context: ValidationContext): boolean {
    return context.language === 'typescript' || 
           (context.language === 'javascript' && this.hasTypeScript(context));
  }
  
  private hasTypeScript(context: ValidationContext): boolean {
    // Check if tsconfig.json exists
    const fs = require('fs');
    const path = require('path');
    return fs.existsSync(path.join(context.workspaceRoot, 'tsconfig.json'));
  }
  
  async validate(context: ValidationContext): Promise<ValidationIssue[]> {
    // For now, we'll use VS Code's TypeScript diagnostics
    // In a full implementation, we'd run tsc programmatically
    return this.getTypeScriptDiagnostics(context.modifiedFiles);
  }
  
  private async getTypeScriptDiagnostics(files: string[]): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];
    
    for (const filePath of files) {
      const uri = vscode.Uri.file(filePath);
      const diagnostics = vscode.languages.getDiagnostics(uri);
      
      for (const diagnostic of diagnostics) {
        if (diagnostic.source === 'typescript') {
          const severity = diagnostic.severity === vscode.DiagnosticSeverity.Error ? 'blocking' : 'warning';
          
          issues.push(this.createIssue(
            'typecheck',
            severity,
            diagnostic.message,
            {
              file: filePath,
              line: diagnostic.range.start.line + 1,
              column: diagnostic.range.start.character + 1,
              fixable: true // TypeScript errors are often auto-fixable
            }
          ));
        }
      }
    }
    
    return issues;
  }
}

/**
 * Lint validation (ESLint, Pylint, etc.)
 */
class LintValidator extends Validator {
  type: ValidationType = 'lint';
  name = 'Lint Check';
  description = 'Code quality and style validation';
  
  appliesTo(context: ValidationContext): boolean {
    // Check for common linter config files
    const fs = require('fs');
    const path = require('path');
    const configs = ['.eslintrc.js', '.eslintrc.json', 'pyproject.toml', 'setup.cfg'];
    
    return configs.some(config => 
      fs.existsSync(path.join(context.workspaceRoot, config))
    );
  }
  
  async validate(context: ValidationContext): Promise<ValidationIssue[]> {
    // Use VS Code's linter diagnostics
    return this.getLintDiagnostics(context.modifiedFiles);
  }
  
  private async getLintDiagnostics(files: string[]): Promise<ValidationIssue[]> {
    const issues: ValidationIssue[] = [];
    
    for (const filePath of files) {
      const uri = vscode.Uri.file(filePath);
      const diagnostics = vscode.languages.getDiagnostics(uri);
      
      for (const diagnostic of diagnostics) {
        if (diagnostic.source === 'eslint' || diagnostic.source === 'pylint') {
          const severity = diagnostic.severity === vscode.DiagnosticSeverity.Error ? 'blocking' : 'warning';
          
          issues.push(this.createIssue(
            'lint',
            severity,
            diagnostic.message,
            {
              file: filePath,
              line: diagnostic.range.start.line + 1,
              column: diagnostic.range.start.character + 1,
              fixable: true // Lint issues are often auto-fixable
            }
          ));
        }
      }
    }
    
    return issues;
  }
}

// Placeholder validators for other types
class FormatValidator extends Validator {
  type: ValidationType = 'format';
  name = 'Format Check';
  description = 'Code formatting validation';
  
  appliesTo(): boolean { return false; } // Disabled for now
  async validate(): Promise<ValidationIssue[]> { return []; }
}

class TestValidator extends Validator {
  type: ValidationType = 'test';
  name = 'Test Runner';
  description = 'Unit and integration test execution';
  
  appliesTo(): boolean { return false; } // Disabled for now
  async validate(): Promise<ValidationIssue[]> { return []; }
}

class BuildValidator extends Validator {
  type: ValidationType = 'build';
  name = 'Build Check';
  description = 'Compilation and build validation';
  
  appliesTo(): boolean { return false; } // Disabled for now
  async validate(): Promise<ValidationIssue[]> { return []; }
}

class SecurityValidator extends Validator {
  type: ValidationType = 'security';
  name = 'Security Scan';
  description = 'Security vulnerability detection';
  
  appliesTo(): boolean { return false; } // Disabled for now
  async validate(): Promise<ValidationIssue[]> { return []; }
}

class DependencyValidator extends Validator {
  type: ValidationType = 'deps';
  name = 'Dependency Check';
  description = 'Package dependency validation';
  
  appliesTo(): boolean { return false; } // Disabled for now
  async validate(): Promise<ValidationIssue[]> { return []; }
}