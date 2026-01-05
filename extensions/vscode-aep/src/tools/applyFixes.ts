import { ToolContext, ToolResult } from "./types";

interface AnalyzedFile {
    file: string;
    total: number;
    severities: Record<string, number>;
    fixable: boolean;
}

export async function applyFixes(
    ctx: ToolContext
): Promise<ToolResult> {
    const summary: AnalyzedFile[] =
        ctx.previousResult?.data?.summary ?? [];

    if (!Array.isArray(summary)) {
        return {
            success: false,
            error: "Invalid analysis input for applyFixes"
        };
    }

    const plannedFixes = summary
        .filter(f => f.fixable)
        .map(f => ({
            file: f.file,
            plannedActions: [
                "Inspect TypeScript errors",
                "Apply safe syntax corrections",
                "Re-run diagnostics"
            ]
        }));

    return {
        success: true,
        data: {
            filesAffected: plannedFixes.length,
            plannedFixes
        }
    };
}