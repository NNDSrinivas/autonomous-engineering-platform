import * as vscode from "vscode";
import { ToolContext, ToolResult } from "./types";

export async function scanProblems(
    _ctx: ToolContext
): Promise<ToolResult> {
    const diagnostics = vscode.languages.getDiagnostics();

    const problems = diagnostics.flatMap(([uri, diags]) =>
        diags.map(d => ({
            file: uri.fsPath,
            message: d.message,
            severity: vscode.DiagnosticSeverity[d.severity],
            line: d.range.start.line + 1,
            character: d.range.start.character + 1,
            source: d.source ?? "unknown"
        }))
    );

    return {
        success: true,
        data: {
            count: problems.length,
            problems
        }
    };
}