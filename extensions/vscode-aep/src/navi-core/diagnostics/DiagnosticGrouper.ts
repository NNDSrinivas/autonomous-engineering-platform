import * as vscode from 'vscode';

/**
 * Represents a group of related diagnostics with a root cause
 */
export interface DiagnosticGroup {
    file: vscode.Uri;
    root: vscode.Diagnostic;
    related: vscode.Diagnostic[];
    severity: 'critical' | 'cascading' | 'minor';
}

/**
 * DiagnosticGrouper - Groups diagnostics by root cause to eliminate cascade fixing
 * 
 * Mental Model:
 * ❌ Old: Fix each diagnostic independently → cascade of fixes
 * ✅ New: Find root cause → fix once → all cascades resolve
 * 
 * This is what makes NAVI behave like Copilot/Cline instead of a linter
 */
export class DiagnosticGrouper {

    /**
     * Group diagnostics by root cause analysis
     * Returns groups prioritized by impact and cascading potential
     */
    static group(diagnostics: Map<string, vscode.Diagnostic[]>): DiagnosticGroup[] {
        const groups: DiagnosticGroup[] = [];

        for (const [uriString, diags] of diagnostics.entries()) {
            if (!diags.length) continue;

            const uri = vscode.Uri.parse(uriString);
            const fileGroups = this.groupDiagnosticsInFile(uri, diags);
            groups.push(...fileGroups);
        }

        // Sort by severity - critical errors first
        return groups.sort((a, b) => {
            const severityOrder = { 'critical': 0, 'cascading': 1, 'minor': 2 };
            return severityOrder[a.severity] - severityOrder[b.severity];
        });
    }

    /**
     * Group diagnostics within a single file by root cause
     */
    private static groupDiagnosticsInFile(file: vscode.Uri, diags: vscode.Diagnostic[]): DiagnosticGroup[] {
        // Sort by line number ascending - root causes are usually earlier
        const sorted = [...diags].sort(
            (a, b) => a.range.start.line - b.range.start.line
        );

        const groups: DiagnosticGroup[] = [];
        const processed = new Set<vscode.Diagnostic>();

        for (const diagnostic of sorted) {
            if (processed.has(diagnostic)) continue;

            const group = this.buildGroupFromRoot(file, diagnostic, sorted, processed);
            groups.push(group);
        }

        return groups;
    }

    /**
     * Build a diagnostic group starting from a potential root cause
     */
    private static buildGroupFromRoot(
        file: vscode.Uri,
        root: vscode.Diagnostic,
        allDiags: vscode.Diagnostic[],
        processed: Set<vscode.Diagnostic>
    ): DiagnosticGroup {

        processed.add(root);
        const related: vscode.Diagnostic[] = [];

        // Find related diagnostics that could be cascading from this root
        for (const diag of allDiags) {
            if (processed.has(diag)) continue;

            if (this.isPotentialCascade(root, diag)) {
                related.push(diag);
                processed.add(diag);
            }
        }

        return {
            file,
            root,
            related,
            severity: this.categorizeGroupSeverity(root, related)
        };
    }

    /**
     * Determine if a diagnostic is likely a cascade from the root
     */
    private static isPotentialCascade(root: vscode.Diagnostic, candidate: vscode.Diagnostic): boolean {
        const rootLine = root.range.start.line;
        const candidateLine = candidate.range.start.line;

        // Cascades typically occur after the root cause
        if (candidateLine <= rootLine) return false;

        // Check for known cascade patterns
        const rootMsg = root.message.toLowerCase();
        const candidateMsg = candidate.message.toLowerCase();

        // Syntax error cascades
        if (rootMsg.includes('unexpected') || rootMsg.includes('missing')) {
            if (candidateMsg.includes('unexpected') ||
                candidateMsg.includes('expected') ||
                candidateMsg.includes('unterminated')) {
                return true;
            }
        }

        // JSX-specific cascades
        if (rootMsg.includes('jsx') || rootMsg.includes('tag')) {
            if (candidateMsg.includes('jsx') || candidateMsg.includes('tag') || candidateMsg.includes('element')) {
                return true;
            }
        }

        // TypeScript error cascades
        if (rootMsg.includes('cannot find') || rootMsg.includes('does not exist')) {
            if (candidateMsg.includes('property') || candidateMsg.includes('type')) {
                return true;
            }
        }

        // Bracket/parentheses cascades (very common)
        if (rootMsg.includes('expected') && (rootMsg.includes('}') || rootMsg.includes(')') || rootMsg.includes(']'))) {
            if (candidateMsg.includes('expected') || candidateMsg.includes('unexpected')) {
                return true;
            }
        }

        return false;
    }

    /**
     * Categorize the severity/impact of a diagnostic group
     */
    private static categorizeGroupSeverity(root: vscode.Diagnostic, related: vscode.Diagnostic[]): 'critical' | 'cascading' | 'minor' {
        const rootMsg = root.message.toLowerCase();

        // Critical: Structural breaks that cause many cascades
        if (related.length >= 3) return 'critical';

        if (rootMsg.includes('unexpected token') ||
            rootMsg.includes('missing') ||
            rootMsg.includes('unterminated') ||
            rootMsg.includes('jsx')) {
            return 'critical';
        }

        // Cascading: Errors that cause some related issues
        if (related.length > 0) return 'cascading';

        // Minor: Isolated issues
        return 'minor';
    }

    /**
     * Get summary of diagnostic groups for logging/debugging
     */
    static summarizeGroups(groups: DiagnosticGroup[]): string {
        const summary = groups.map(group => {
            const fileName = group.file.fsPath.split('/').pop();
            return `${fileName}: ${group.severity} (root: "${group.root.message}", +${group.related.length} related)`;
        }).join('\n');

        return `Diagnostic Groups (${groups.length} total):\n${summary}`;
    }
}