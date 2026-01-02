// extensions/vscode-aep/src/navi-core/perception/DiagnosticsPerception.ts
/**
 * Phase 1.3: Global Diagnostics Perception + Phase 2.2: Diagnostic Clustering
 * 
 * Collects ALL VS Code diagnostics across the workspace (not scoped to changed files).
 * Pure perception layer — no opinions, no fixes, no planning.
 * 
 * Phase 2.2 Addition: Clusters diagnostics by root cause to eliminate cascading error spam.
 */

import * as vscode from 'vscode';

export interface NaviDiagnostic {
    file: string;
    line: number;
    severity: 'error' | 'warning' | 'info';
    message: string;
    source?: string;
}

// Phase 2.2: Diagnostic clustering types
export type DiagnosticCategory =
    | 'syntax'
    | 'structure'
    | 'type'
    | 'lint'
    | 'unknown';

export interface DiagnosticCluster {
    fileUri: string;
    category: DiagnosticCategory;
    root: vscode.Diagnostic;
    related: vscode.Diagnostic[];
}

/**
 * Identifies mechanical syntax errors that should auto-fix without user intervention.
 * These are deterministic compiler failures, not semantic ambiguities.
 */
export function isMechanicalSyntaxError(diagnostic: vscode.Diagnostic): boolean {
    const msg = diagnostic.message.toLowerCase();

    return (
        msg.includes("has no corresponding closing tag") ||
        msg.includes("expression expected") ||
        msg.includes("identifier expected") ||
        msg.includes("'}' expected") ||
        msg.includes("')' expected") ||
        msg.includes("']' expected") ||
        msg.includes("unterminated") ||
        msg.includes("missing") ||
        msg.includes("unexpected token") ||
        // TypeScript specific error codes
        diagnostic.code === 1005 || // Expected token
        diagnostic.code === 17008   // JSX element has no corresponding closing tag
    );
}

export class DiagnosticsPerception {
    /**
     * Phase 2.2: Entry point — clusters raw VS Code diagnostics into root-cause groups
     * This eliminates cascading error spam by grouping related structural issues.
     */
    public static clusterDiagnostics(
        diagnosticsByFile: Map<vscode.Uri, vscode.Diagnostic[]>
    ): DiagnosticCluster[] {
        const clusters: DiagnosticCluster[] = [];

        for (const [uri, diagnostics] of diagnosticsByFile.entries()) {
            const sorted = [...diagnostics].sort(
                (a, b) => a.range.start.line - b.range.start.line
            );

            const consumed = new Set<vscode.Diagnostic>();

            for (const diag of sorted) {
                if (consumed.has(diag)) continue;

                const category = this.classifyDiagnostic(diag);

                // Only cluster syntax / structural errors
                if (category !== 'syntax' && category !== 'structure') {
                    clusters.push({
                        fileUri: uri.toString(),
                        category,
                        root: diag,
                        related: [],
                    });
                    consumed.add(diag);
                    continue;
                }

                const related: vscode.Diagnostic[] = [];

                for (const candidate of sorted) {
                    if (candidate === diag) continue;
                    if (consumed.has(candidate)) continue;

                    if (
                        this.isRelatedStructuralDiagnostic(
                            diag,
                            candidate,
                            category
                        )
                    ) {
                        related.push(candidate);
                        consumed.add(candidate);
                    }
                }

                consumed.add(diag);

                clusters.push({
                    fileUri: uri.toString(),
                    category,
                    root: diag,
                    related,
                });
            }
        }

        return clusters;
    }

    /**
     * Phase 2.2: Determines whether two diagnostics are manifestations of the same root cause
     */
    private static isRelatedStructuralDiagnostic(
        root: vscode.Diagnostic,
        candidate: vscode.Diagnostic,
        category: DiagnosticCategory
    ): boolean {
        // Same category only
        if (this.classifyDiagnostic(candidate) !== category) return false;

        const lineDistance = Math.abs(
            root.range.start.line - candidate.range.start.line
        );

        // Structural issues cascade nearby (within 6 lines)
        if (lineDistance > 6) return false;

        // TypeScript / JSX parser errors that commonly cascade
        const structuralCodes = new Set([
            '1003', // Identifier expected
            '1005', // ')' or '>' expected
            '1109', // Expression expected
            '17002', // JSX closing tag expected
            '17008', // JSX element has no corresponding closing tag
        ]);

        const rootCode = String(root.code ?? '');
        const candidateCode = String(candidate.code ?? '');

        return (
            structuralCodes.has(rootCode) ||
            structuralCodes.has(candidateCode)
        );
    }

    /**
     * Phase 2.2: Maps VS Code diagnostics to NAVI categories for intelligent clustering
     */
    private static classifyDiagnostic(
        diagnostic: vscode.Diagnostic
    ): DiagnosticCategory {
        const code = String(diagnostic.code ?? '');
        const message = diagnostic.message.toLowerCase();

        // TypeScript structural parser errors
        if (
            diagnostic.source === 'ts' &&
            [
                '1003', // Identifier expected
                '1005', // ')' or '>' expected
                '1109', // Expression expected
                '17002', // JSX closing tag expected
                '17008', // JSX element has no corresponding closing tag
            ].includes(code)
        ) {
            return 'structure';
        }

        // Structural issues by message content
        if (
            message.includes('expected') ||
            message.includes('closing') ||
            message.includes('unterminated') ||
            message.includes('missing')
        ) {
            return 'structure';
        }

        // Syntax errors
        if (diagnostic.severity === vscode.DiagnosticSeverity.Error) {
            return 'syntax';
        }

        // Lint warnings
        if (diagnostic.severity === vscode.DiagnosticSeverity.Warning) {
            return 'lint';
        }

        return 'unknown';
    }

    /**
     * Collect all diagnostics across the entire workspace.
     * 
     * @returns Array of normalized diagnostics with file, line, severity, and message
     */
    static collectWorkspaceDiagnostics(): NaviDiagnostic[] {
        const diagnostics = vscode.languages.getDiagnostics();
        const results: NaviDiagnostic[] = [];

        for (const [uri, diags] of diagnostics) {
            for (const diag of diags) {
                results.push({
                    file: uri.fsPath,
                    line: (diag.range?.start?.line ?? 0) + 1,
                    severity: DiagnosticsPerception.mapSeverity(diag.severity),
                    message: diag.message,
                    source: diag.source,
                });
            }
        }

        return results;
    }

    /**
     * Map VS Code DiagnosticSeverity to string representation.
     */
    private static mapSeverity(
        severity: vscode.DiagnosticSeverity | undefined
    ): 'error' | 'warning' | 'info' {
        switch (severity) {
            case vscode.DiagnosticSeverity.Error:
                return 'error';
            case vscode.DiagnosticSeverity.Warning:
                return 'warning';
            default:
                return 'info';
        }
    }
}

