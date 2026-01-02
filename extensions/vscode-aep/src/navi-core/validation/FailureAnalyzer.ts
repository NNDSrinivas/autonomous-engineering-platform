/**
 * Phase 3.4 - Failure Analyzer
 * 
 * This provides human-level reasoning about why validations failed.
 * This is what makes NAVI superior to Copilot - it explains WHY something
 * broke and suggests intelligent fixes, not just raw error messages.
 */

import { ValidationResult, ValidationIssue, ValidationType } from './ValidationEngine';
import { RepoContext } from '../context/RepoContextBuilder';
import { ChangePlan } from '../generation/ChangePlan';

export interface FailureAnalysis {
  summary: string;
  rootCause: string;
  impact: 'blocking' | 'degraded' | 'minor';
  suggestedFixes: SuggestedFix[];
  relatedIssues: string[]; // IDs of related validation issues
  confidence: number; // 0-1, how confident we are in the analysis
}

export interface SuggestedFix {
  id: string;
  description: string;
  type: 'automatic' | 'guided' | 'manual';
  estimatedEffort: 'trivial' | 'low' | 'medium' | 'high';
  files: string[];
  reasoning: string;
}

export class FailureAnalyzer {
  private patterns: Map<ValidationType, FailurePattern[]> = new Map();
  
  constructor() {
    this.initializePatterns();
  }
  
  /**
   * Analyze validation failures and provide human-readable explanations
   */
  analyze(
    result: ValidationResult,
    context: {
      repoContext: RepoContext;
      changePlan?: ChangePlan;
      modifiedFiles: string[];
    }
  ): FailureAnalysis[] {
    console.log(`🔍 Analyzing ${result.issues.length} validation issues...`);
    
    if (result.passed) {
      return [];
    }
    
    // Group related issues
    const issueGroups = this.groupRelatedIssues(result.issues);
    const analyses: FailureAnalysis[] = [];
    
    for (const group of issueGroups) {
      const analysis = this.analyzeIssueGroup(group, context);
      if (analysis) {
        analyses.push(analysis);
      }
    }
    
    console.log(`🎯 Generated ${analyses.length} failure analyses`);
    return analyses;
  }
  
  /**
   * Generate a human-readable summary for the UI
   */
  generateSummary(
    result: ValidationResult, 
    analyses: FailureAnalysis[]
  ): string {
    if (result.passed) {
      return `✅ All validations passed (${result.summary.totalChecks} checks completed in ${result.executionTime}ms)`;
    }
    
    const { blockers, warnings } = result.summary;
    let summary = `❌ Validation failed: ${blockers} blocking issues`;
    
    if (warnings > 0) {
      summary += `, ${warnings} warnings`;
    }
    
    if (analyses.length > 0) {
      const primaryAnalysis = analyses[0];
      summary += `\n\n🎯 Primary issue: ${primaryAnalysis.summary}`;
      
      if (primaryAnalysis.suggestedFixes.length > 0) {
        const autoFixes = primaryAnalysis.suggestedFixes.filter(f => f.type === 'automatic');
        if (autoFixes.length > 0) {
          summary += `\n💡 ${autoFixes.length} automatic fix${autoFixes.length > 1 ? 'es' : ''} available`;
        }
      }
    }
    
    return summary;
  }
  
  /**
   * Group related issues together for better analysis
   */
  private groupRelatedIssues(issues: ValidationIssue[]): ValidationIssue[][] {
    const groups: ValidationIssue[][] = [];
    const processed = new Set<string>();
    
    for (const issue of issues) {
      if (processed.has(issue.id)) continue;
      
      const relatedGroup = [issue];
      processed.add(issue.id);
      
      // Find related issues (same file, similar error types, etc.)
      for (const otherIssue of issues) {
        if (processed.has(otherIssue.id)) continue;
        
        if (this.areIssuesRelated(issue, otherIssue)) {
          relatedGroup.push(otherIssue);
          processed.add(otherIssue.id);
        }
      }
      
      groups.push(relatedGroup);
    }
    
    // Sort groups by severity (blocking issues first)
    return groups.sort((a, b) => {
      const aBlockers = a.filter(i => i.severity === 'blocking').length;
      const bBlockers = b.filter(i => i.severity === 'blocking').length;
      return bBlockers - aBlockers;
    });
  }
  
  /**
   * Analyze a group of related issues
   */
  private analyzeIssueGroup(
    issues: ValidationIssue[],
    context: {
      repoContext: RepoContext;
      changePlan?: ChangePlan;
      modifiedFiles: string[];
    }
  ): FailureAnalysis | null {
    if (issues.length === 0) return null;
    
    const primaryIssue = issues[0];
    const patterns = this.patterns.get(primaryIssue.type) || [];
    
    // Try to match against known patterns
    for (const pattern of patterns) {
      const match = pattern.matches(issues, context);
      if (match.confidence > 0.5) {
        return {
          summary: match.explanation,
          rootCause: match.rootCause,
          impact: this.calculateImpact(issues),
          suggestedFixes: match.suggestedFixes,
          relatedIssues: issues.map(i => i.id),
          confidence: match.confidence
        };
      }
    }
    
    // Fallback to generic analysis
    return this.generateGenericAnalysis(issues, context);
  }
  
  /**
   * Generate a generic analysis when no specific pattern matches
   */
  private generateGenericAnalysis(
    issues: ValidationIssue[],
    context: {
      repoContext: RepoContext;
      changePlan?: ChangePlan;
      modifiedFiles: string[];
    }
  ): FailureAnalysis {
    const primaryIssue = issues[0];
    const affectedFiles = new Set(issues.map(i => i.file).filter(Boolean));
    
    let summary: string;
    let rootCause: string;
    
    if (issues.length === 1) {
      summary = `${primaryIssue.type} error: ${primaryIssue.message}`;
      rootCause = `Code change introduced a ${primaryIssue.type} issue`;
    } else {
      summary = `Multiple ${primaryIssue.type} errors in ${affectedFiles.size} file(s)`;
      rootCause = `Code changes introduced ${issues.length} ${primaryIssue.type} issues`;
    }
    
    const suggestedFixes: SuggestedFix[] = [];
    
    // Generic fix suggestions based on issue type
    if (primaryIssue.fixable) {
      suggestedFixes.push({
        id: `fix_${primaryIssue.type}_auto`,
        description: `Auto-fix ${primaryIssue.type} issues`,
        type: 'automatic',
        estimatedEffort: 'trivial',
        files: Array.from(affectedFiles) as string[],
        reasoning: `These ${primaryIssue.type} issues can be automatically resolved`
      });
    } else {
      suggestedFixes.push({
        id: `fix_${primaryIssue.type}_manual`,
        description: `Manually resolve ${primaryIssue.type} issues`,
        type: 'manual',
        estimatedEffort: 'medium',
        files: Array.from(affectedFiles) as string[],
        reasoning: `These issues require manual review and fixing`
      });
    }
    
    return {
      summary,
      rootCause,
      impact: this.calculateImpact(issues),
      suggestedFixes,
      relatedIssues: issues.map(i => i.id),
      confidence: 0.7 // Generic analysis has moderate confidence
    };
  }
  
  /**
   * Check if two issues are related
   */
  private areIssuesRelated(issue1: ValidationIssue, issue2: ValidationIssue): boolean {
    // Same file
    if (issue1.file && issue2.file && issue1.file === issue2.file) {
      return true;
    }
    
    // Same validation type
    if (issue1.type === issue2.type) {
      return true;
    }
    
    // Similar error messages (simple heuristic)
    if (issue1.message && issue2.message) {
      const words1 = new Set(issue1.message.toLowerCase().split(/\s+/));
      const words2 = new Set(issue2.message.toLowerCase().split(/\s+/));
      const intersection = new Set([...words1].filter(x => words2.has(x)));
      const union = new Set([...words1, ...words2]);
      
      const similarity = intersection.size / union.size;
      return similarity > 0.3;
    }
    
    return false;
  }
  
  /**
   * Calculate the overall impact of a group of issues
   */
  private calculateImpact(issues: ValidationIssue[]): 'blocking' | 'degraded' | 'minor' {
    const hasBlocking = issues.some(i => i.severity === 'blocking');
    const warningCount = issues.filter(i => i.severity === 'warning').length;
    
    if (hasBlocking) {
      return 'blocking';
    } else if (warningCount > 3) {
      return 'degraded';
    } else {
      return 'minor';
    }
  }
  
  /**
   * Initialize failure patterns for different validation types
   */
  private initializePatterns(): void {
    // TypeScript patterns
    this.patterns.set('typecheck', [
      new MissingImportPattern(),
      new TypeMismatchPattern(),
      new UndefinedVariablePattern(),
      new PropertyAccessPattern()
    ]);
    
    // Syntax patterns
    this.patterns.set('syntax', [
      new MissingBracePattern(),
      new UnterminatedStringPattern(),
      new InvalidCharacterPattern()
    ]);
    
    // Lint patterns
    this.patterns.set('lint', [
      new UnusedVariablePattern(),
      new IndentationPattern(),
      new ConsoleLogPattern()
    ]);
  }
}

/**
 * Base class for failure patterns
 */
abstract class FailurePattern {
  abstract name: string;
  abstract description: string;
  
  abstract matches(
    issues: ValidationIssue[], 
    context: any
  ): {
    confidence: number;
    explanation: string;
    rootCause: string;
    suggestedFixes: SuggestedFix[];
  };
}

/**
 * Pattern for missing import errors
 */
class MissingImportPattern extends FailurePattern {
  name = 'Missing Import';
  description = 'Detects when code references undefined imports';
  
  matches(issues: ValidationIssue[]): any {
    const importIssues = issues.filter(issue => 
      issue.message.includes('Cannot find name') ||
      issue.message.includes('is not defined') ||
      issue.message.includes('Cannot resolve module')
    );
    
    if (importIssues.length === 0) {
      return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
    }
    
    const missingNames = importIssues.map(issue => {
      const match = issue.message.match(/Cannot find name '([^']+)'/);
      return match ? match[1] : 'unknown';
    });
    
    return {
      confidence: 0.9,
      explanation: `Missing import${missingNames.length > 1 ? 's' : ''} for: ${missingNames.join(', ')}`,
      rootCause: 'Code references variables/functions that are not imported or defined',
      suggestedFixes: [{
        id: 'add_missing_imports',
        description: 'Add missing import statements',
        type: 'automatic' as const,
        estimatedEffort: 'trivial' as const,
        files: [...new Set(importIssues.map(i => i.file!).filter(Boolean))],
        reasoning: 'TypeScript can auto-suggest the correct import statements'
      }]
    };
  }
}

/**
 * Pattern for type mismatch errors
 */
class TypeMismatchPattern extends FailurePattern {
  name = 'Type Mismatch';
  description = 'Detects type compatibility issues';
  
  matches(issues: ValidationIssue[]): any {
    const typeIssues = issues.filter(issue => 
      issue.message.includes('Type ') && 
      issue.message.includes('is not assignable to type')
    );
    
    if (typeIssues.length === 0) {
      return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
    }
    
    return {
      confidence: 0.8,
      explanation: `Type compatibility issues in ${typeIssues.length} location${typeIssues.length > 1 ? 's' : ''}`,
      rootCause: 'Code change introduced type mismatches between expected and actual types',
      suggestedFixes: [{
        id: 'fix_type_mismatches',
        description: 'Fix type compatibility issues',
        type: 'guided' as const,
        estimatedEffort: 'low' as const,
        files: [...new Set(typeIssues.map(i => i.file!).filter(Boolean))],
        reasoning: 'Type issues often require understanding the intended data flow'
      }]
    };
  }
}

// Placeholder patterns for other common issues
class UndefinedVariablePattern extends FailurePattern {
  name = 'Undefined Variable';
  description = 'Variables used before declaration';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class PropertyAccessPattern extends FailurePattern {
  name = 'Property Access';
  description = 'Invalid property access on objects';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class MissingBracePattern extends FailurePattern {
  name = 'Missing Brace';
  description = 'Unclosed braces, brackets, or parentheses';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class UnterminatedStringPattern extends FailurePattern {
  name = 'Unterminated String';
  description = 'String literals missing closing quotes';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class InvalidCharacterPattern extends FailurePattern {
  name = 'Invalid Character';
  description = 'Invalid or unexpected characters in code';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class UnusedVariablePattern extends FailurePattern {
  name = 'Unused Variable';
  description = 'Variables declared but never used';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class IndentationPattern extends FailurePattern {
  name = 'Indentation';
  description = 'Inconsistent code indentation';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}

class ConsoleLogPattern extends FailurePattern {
  name = 'Console Log';
  description = 'Console.log statements in production code';
  
  matches(): any {
    return { confidence: 0, explanation: '', rootCause: '', suggestedFixes: [] };
  }
}