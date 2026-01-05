import * as vscode from "vscode";
import { ToolContext, ToolResult } from "./types";

export async function verifyProblems(
    _ctx: ToolContext
): Promise<ToolResult> {
    const diagnostics = vscode.languages.getDiagnostics();

    const problemCount = diagnostics.reduce(
        (sum, [, diags]) => sum + diags.length,
        0
    );

    return {
        success: true,
        data: {
            remainingProblems: problemCount,
            status: problemCount === 0 ? "PASS" : "FAIL"
        }
    };
}