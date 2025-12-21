// extensions/vscode-aep/src/navi-core/perception/DiagnosticsPerception.ts
/**
 * Phase 1.3: Global Diagnostics Perception
 * 
 * Collects ALL VS Code diagnostics across the workspace (not scoped to changed files).
 * Pure perception layer — no opinions, no fixes, no planning.
 */

import * as vscode from 'vscode';

export interface NaviDiagnostic {
    file: string;
    line: number;
    severity: 'error' | 'warning' | 'info';
    message: string;
    source?: string;
}

export class DiagnosticsPerception {
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
