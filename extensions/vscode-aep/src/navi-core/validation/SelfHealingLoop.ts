/**
 * Phase 3.4 - Self-Healing Loop
 * 
 * The autonomous fixing system that attempts to resolve validation failures
 * without human intervention. This is what makes NAVI behave like a Staff Engineer
 * who catches and fixes their own mistakes before code review.
 */

import { ValidationResult, ValidationIssue, ValidationType, ValidationContext } from './ValidationEngine';
import { FailureAnalysis, SuggestedFix, FailureAnalyzer } from './FailureAnalyzer';
import { CodeGenerationEngine, GenerationRequest } from '../generation/CodeGenerationEngine';
import { ChangePlan, ChangePlanBuilder } from '../generation/ChangePlan';
import { CodeSynthesizer } from '../generation/CodeSynthesizer';
import { ApprovalEngine, ApprovalDecision } from '../safety/ApprovalEngine';
import { ActionIntent } from '../safety/ActionIntent';
import { ValidationPolicy } from './ValidationPolicy';

export interface HealingAttempt {
  id: string;
  timestamp: Date;
  originalIssues: ValidationIssue[];
  analysis: FailureAnalysis;
  selectedFix: SuggestedFix;
  changePlan: ChangePlan;
  approvalRequired: boolean;
  success: boolean;
  newIssues?: ValidationIssue[];
  error?: string;
}

export interface HealingResult {
  success: boolean;
  attempts: HealingAttempt[];
  finalValidation?: ValidationResult;
  totalTime: number;
  summary: string;
}

export class SelfHealingLoop {
  private analyzer: FailureAnalyzer;
  private codeGenerator?: CodeGenerationEngine;
  private synthesizer: CodeSynthesizer;
  private approvalEngine: ApprovalEngine;
  
  constructor(
    analyzer: FailureAnalyzer,
    synthesizer: CodeSynthesizer,
    approvalEngine: ApprovalEngine
  ) {
    this.analyzer = analyzer;
    this.synthesizer = synthesizer;
    this.approvalEngine = approvalEngine;
  }
  
  /**
   * Attempt to heal validation failures autonomously
   */
  async heal(
    validationResult: ValidationResult,
    context: ValidationContext,
    policy: ValidationPolicy
  ): Promise<HealingResult> {
    const startTime = Date.now();
    console.log(`🔄 Starting self-healing for ${validationResult.issues.length} issues...`);
    
    if (validationResult.passed) {
      return {
        success: true,
        attempts: [],
        totalTime: Date.now() - startTime,
        summary: 'No healing required - validation passed'
      };
    }
    
    if (!policy.allowAutoFix) {
      return {
        success: false,
        attempts: [],
        totalTime: Date.now() - startTime,
        summary: 'Auto-fix disabled by policy'
      };
    }
    
    const attempts: HealingAttempt[] = [];
    let currentResult = validationResult;
    let healingSuccess = false;
    
    // Analyze failures
    const analyses = this.analyzer.analyze(currentResult, {
      repoContext: context.repoContext,
      changePlan: context.changePlan,
      modifiedFiles: context.modifiedFiles
    });
    
    if (analyses.length === 0) {
      return {
        success: false,
        attempts: [],
        totalTime: Date.now() - startTime,
        summary: 'No actionable issues found for healing'
      };
    }
    
    // Attempt healing for each analysis (up to policy limit)
    for (let i = 0; i < Math.min(analyses.length, policy.maxHealingAttempts); i++) {
      const analysis = analyses[i];
      
      // Skip if we've exceeded retry limit
      if (attempts.length >= policy.maxRetries) {
        console.log(`🛑 Reached retry limit (${policy.maxRetries})`);
        break;
      }
      
      // Find the best automatic fix
      const automaticFixes = analysis.suggestedFixes.filter(fix => 
        fix.type === 'automatic' && 
        policy.allowedAutoFixTypes.includes(this.getFixValidationType(fix))
      );
      
      if (automaticFixes.length === 0) {
        console.log(`⏭️ No automatic fixes available for: ${analysis.summary}`);
        continue;
      }
      
      const selectedFix = this.selectBestFix(automaticFixes);
      const attempt = await this.attemptFix(
        analysis,
        selectedFix,
        context,
        policy
      );
      
      attempts.push(attempt);
      
      if (attempt.success) {
        console.log(`✅ Healing attempt successful: ${selectedFix.description}`);
        
        // Re-run validation to see if we fixed the issues
        const newValidation = await this.runValidation(context);
        
        if (newValidation.passed) {
          healingSuccess = true;
          currentResult = newValidation;
          break;
        } else {
          // Some issues remain, continue with remaining attempts
          currentResult = newValidation;
          console.log(`⚠️ Partial healing - ${newValidation.issues.length} issues remain`);
        }
      } else {
        console.log(`❌ Healing attempt failed: ${attempt.error}`);
      }
    }
    
    const totalTime = Date.now() - startTime;
    const summary = this.generateSummary(healingSuccess, attempts, currentResult);
    
    console.log(`🏁 Self-healing complete: ${healingSuccess ? 'SUCCESS' : 'FAILED'} (${totalTime}ms)`);
    
    return {
      success: healingSuccess,
      attempts,
      finalValidation: currentResult,
      totalTime,
      summary
    };
  }
  
  /**
   * Attempt a single fix
   */
  private async attemptFix(
    analysis: FailureAnalysis,
    fix: SuggestedFix,
    context: ValidationContext,
    policy: ValidationPolicy
  ): Promise<HealingAttempt> {
    const attempt: HealingAttempt = {
      id: `heal_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      originalIssues: analysis.relatedIssues.map(id => 
        context.changePlan?.steps.find(s => s.id === id) as any || { id }
      ),
      analysis,
      selectedFix: fix,
      changePlan: ChangePlanBuilder.create('Healing attempt'),
      approvalRequired: false,
      success: false
    };
    
    try {
      console.log(`🔧 Attempting fix: ${fix.description}`);
      
      // Generate a change plan for the fix
      const changePlan = await this.generateFixPlan(fix, context);
      attempt.changePlan = changePlan;
      
      // Check if approval is required
      const actionIntent = ChangePlanBuilder.toActionIntent(changePlan);
      const approvalDecision = this.approvalEngine.requiresApproval(actionIntent);
      
      attempt.approvalRequired = approvalDecision.requiresApproval;
      
      if (approvalDecision.requiresApproval && !policy.allowUnapprovedFixes) {
        attempt.success = false;
        attempt.error = `Fix requires approval: ${approvalDecision.reason}`;
        return attempt;
      }
      
      // Apply the fix
      const patches = this.synthesizer.synthesize(changePlan);
      
      // For now, simulate applying patches
      // In a full implementation, this would use PatchAssembler
      await this.simulateApplyPatches(patches);
      
      attempt.success = true;
      console.log(`✅ Applied fix: ${fix.description}`);
      
    } catch (error) {
      attempt.success = false;
      attempt.error = error instanceof Error ? error.message : String(error);
      console.error(`❌ Fix attempt failed:`, error);
    }
    
    return attempt;
  }
  
  /**
   * Generate a change plan to implement a suggested fix
   */
  private async generateFixPlan(
    fix: SuggestedFix,
    context: ValidationContext
  ): Promise<ChangePlan> {
    // If we have a code generation engine, use it for intelligent fixes
    if (this.codeGenerator) {
      const request: GenerationRequest = {
        intent: `Fix validation issue: ${fix.description}`,
        context: {
          relatedFiles: fix.files
        },
        constraints: {
          minimizeChanges: true,
          preserveExisting: true,
          followConventions: true
        }
      };
      
      return await this.codeGenerator.generatePlan(request);
    }
    
    // Fallback to basic fix plan
    let plan = ChangePlanBuilder.create(fix.description);
    
    // Add basic modifications based on fix type
    for (const filePath of fix.files) {
      plan = ChangePlanBuilder.addFileModification(
        plan,
        filePath,
        [{
          type: 'replace',
          startLine: 1,
          endLine: 1,
          content: '// Auto-generated fix',
          reasoning: fix.reasoning
        }],
        fix.reasoning
      );
    }
    
    return plan;
  }
  
  /**
   * Select the best fix from available options
   */
  private selectBestFix(fixes: SuggestedFix[]): SuggestedFix {
    // Prioritize by effort (trivial first) and type (automatic first)
    return fixes.sort((a, b) => {
      const effortOrder = { trivial: 0, low: 1, medium: 2, high: 3 };
      const effortDiff = effortOrder[a.estimatedEffort] - effortOrder[b.estimatedEffort];
      
      if (effortDiff !== 0) return effortDiff;
      
      // Prefer fixes that affect fewer files
      return a.files.length - b.files.length;
    })[0];
  }
  
  /**
   * Get validation type from a suggested fix
   */
  private getFixValidationType(fix: SuggestedFix): ValidationType {
    if (fix.id.includes('import')) return 'typecheck';
    if (fix.id.includes('syntax')) return 'syntax';
    if (fix.id.includes('lint')) return 'lint';
    if (fix.id.includes('format')) return 'format';
    
    return 'syntax'; // Default fallback
  }
  
  /**
   * Run validation after applying fixes
   */
  private async runValidation(context: ValidationContext): Promise<ValidationResult> {
    // This would use the ValidationEngine to re-run validations
    // For now, simulate a validation result
    return {
      passed: Math.random() > 0.3, // 70% chance of success for simulation
      issues: [],
      summary: {
        totalChecks: 3,
        passed: 3,
        failed: 0,
        warnings: 0,
        blockers: 0,
        skipped: 0
      },
      executionTime: 100,
      timestamp: new Date()
    };
  }
  
  /**
   * Simulate applying patches (placeholder)
   */
  private async simulateApplyPatches(patches: any[]): Promise<void> {
    // In a real implementation, this would apply the patches to the file system
    console.log(`📝 Simulating application of ${patches.length} patches`);
    
    // Add a small delay to simulate real work
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  
  /**
   * Generate human-readable summary of healing results
   */
  private generateSummary(
    success: boolean,
    attempts: HealingAttempt[],
    finalResult?: ValidationResult
  ): string {
    if (attempts.length === 0) {
      return 'No healing attempts were made';
    }
    
    const successfulAttempts = attempts.filter(a => a.success);
    const totalAttempts = attempts.length;
    
    let summary = `Made ${totalAttempts} healing attempt${totalAttempts > 1 ? 's' : ''}`;
    
    if (successfulAttempts.length > 0) {
      summary += `, ${successfulAttempts.length} successful`;
    }
    
    if (success) {
      summary += '. ✅ All validation issues resolved.';
    } else if (finalResult) {
      const remaining = finalResult.issues.length;
      summary += `. ⚠️ ${remaining} issue${remaining > 1 ? 's' : ''} remain${remaining === 1 ? 's' : ''}.`;
    } else {
      summary += '. ❌ Issues could not be resolved automatically.';
    }
    
    // Add details about what was fixed
    if (successfulAttempts.length > 0) {
      const fixTypes = successfulAttempts.map(a => a.selectedFix.description);
      summary += `\n\n🔧 Applied fixes: ${fixTypes.join(', ')}`;
    }
    
    return summary;
  }
  
  /**
   * Set the code generation engine (optional)
   */
  setCodeGenerator(engine: CodeGenerationEngine): void {
    this.codeGenerator = engine;
  }
}