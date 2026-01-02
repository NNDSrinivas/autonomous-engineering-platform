import * as vscode from 'vscode';
import { DiagnosticGroup } from '../diagnostics/DiagnosticGrouper';

/**
 * Repair plan for multi-file coherent fixes
 */
export interface RepairPlan {
    intent: string;
    priority: 'critical' | 'normal' | 'minor';
    files: RepairFileInfo[];
    estimatedComplexity: number;
}

export interface RepairFileInfo {
    uri: string;
    reason: string;
    diagnosticCount: number;
    severity: 'critical' | 'cascading' | 'minor';
}

/**
 * RepairPlanner - Creates coherent repair strategies for multiple files
 * 
 * Mental Model:
 * ❌ Old: Fix each diagnostic independently
 * ✅ New: Create coherent repair strategy that fixes root causes
 * 
 * This is the strategic layer that makes NAVI think like a senior engineer
 */
export class RepairPlanner {

    /**
     * Build a coherent repair plan from diagnostic groups
     */
    static build(groups: DiagnosticGroup[]): RepairPlan {
        if (groups.length === 0) {
            return this.createEmptyPlan();
        }

        const files = groups.map(group => this.createFileInfo(group));
        const priority = this.determinePriority(groups);
        const complexity = this.estimateComplexity(groups);
        const intent = this.generateRepairIntent(groups);

        return {
            intent,
            priority,
            files,
            estimatedComplexity: complexity
        };
    }

    /**
     * Create file info from diagnostic group
     */
    private static createFileInfo(group: DiagnosticGroup): RepairFileInfo {
        const fileName = group.file.fsPath.split('/').pop() || 'unknown';
        const totalDiagnostics = 1 + group.related.length;

        return {
            uri: group.file.toString(),
            reason: `${group.root.message} (${fileName})`,
            diagnosticCount: totalDiagnostics,
            severity: group.severity
        };
    }

    /**
     * Determine overall repair priority
     */
    private static determinePriority(groups: DiagnosticGroup[]): 'critical' | 'normal' | 'minor' {
        if (groups.some(g => g.severity === 'critical')) return 'critical';
        if (groups.some(g => g.severity === 'cascading')) return 'normal';
        return 'minor';
    }

    /**
     * Estimate repair complexity (1-10 scale)
     */
    private static estimateComplexity(groups: DiagnosticGroup[]): number {
        const totalDiagnostics = groups.reduce((sum, g) => sum + 1 + g.related.length, 0);
        const fileCount = groups.length;
        const criticalCount = groups.filter(g => g.severity === 'critical').length;

        // Base complexity from diagnostic count
        let complexity = Math.min(totalDiagnostics / 2, 5);

        // Add complexity for multiple files
        complexity += Math.min(fileCount - 1, 2);

        // Add complexity for critical errors
        complexity += criticalCount;

        return Math.min(Math.ceil(complexity), 10);
    }

    /**
     * Generate repair intent description for LLM
     */
    private static generateRepairIntent(groups: DiagnosticGroup[]): string {
        const criticalGroups = groups.filter(g => g.severity === 'critical');
        const cascadingGroups = groups.filter(g => g.severity === 'cascading');
        const minorGroups = groups.filter(g => g.severity === 'minor');

        let intent = `Fix structural errors in ${groups.length} file(s).

REPAIR STRATEGY:`;

        if (criticalGroups.length > 0) {
            intent += `
1. CRITICAL FIXES (${criticalGroups.length}):
${criticalGroups.map(g => `   - ${this.getFileName(g.file)}: ${g.root.message}`).join('\n')}
   → These are root causes that create cascading errors`;
        }

        if (cascadingGroups.length > 0) {
            intent += `
2. CASCADING FIXES (${cascadingGroups.length}):
${cascadingGroups.map(g => `   - ${this.getFileName(g.file)}: ${g.root.message}`).join('\n')}
   → These cause some related issues`;
        }

        if (minorGroups.length > 0) {
            intent += `
3. MINOR FIXES (${minorGroups.length}):
${minorGroups.map(g => `   - ${this.getFileName(g.file)}: ${g.root.message}`).join('\n')}
   → These are isolated issues`;
        }

        intent += `

APPROACH:
- Fix root structural problems first
- Restore correct syntax and architecture
- Do NOT fix symptoms individually
- Maintain repository conventions and patterns
- Apply coherent changes that resolve ALL related diagnostics`;

        return intent;
    }

    /**
     * Create empty plan for no diagnostics
     */
    private static createEmptyPlan(): RepairPlan {
        return {
            intent: 'No repairs needed - all files are clean',
            priority: 'minor',
            files: [],
            estimatedComplexity: 0
        };
    }

    /**
     * Get filename from URI
     */
    private static getFileName(uri: vscode.Uri): string {
        return uri.fsPath.split('/').pop() || 'unknown';
    }

    /**
     * Get summary of repair plan for logging
     */
    static summarizePlan(plan: RepairPlan): string {
        return `Repair Plan (${plan.priority} priority, complexity: ${plan.estimatedComplexity}/10):
${plan.files.length} files to repair:
${plan.files.map(f => `- ${f.uri.split('/').pop()}: ${f.reason} (${f.diagnosticCount} issues)`).join('\n')}

Intent: ${plan.intent.split('\n')[0]}`;
    }
}