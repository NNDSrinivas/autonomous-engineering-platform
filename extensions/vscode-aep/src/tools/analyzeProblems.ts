import { ToolContext, ToolResult } from "./types";

interface RawProblem {
    file: string;
    message: string;
    severity: string;
    line: number;
    character: number;
    source: string;
}

export async function analyzeProblems(
    ctx: ToolContext
): Promise<ToolResult> {
    const problems: RawProblem[] =
        ctx.previousResult?.data?.problems ?? [];

    if (!Array.isArray(problems)) {
        return {
            success: false,
            error: "Invalid problems input for analysis"
        };
    }

    const byFile: Record<string, RawProblem[]> = {};

    for (const p of problems) {
        if (!byFile[p.file]) {
            byFile[p.file] = [];
        }
        byFile[p.file].push(p);
    }

    const summary = Object.entries(byFile).map(
        ([file, items]) => {
            const severityCount: Record<string, number> = {};

            for (const i of items) {
                severityCount[i.severity] =
                    (severityCount[i.severity] ?? 0) + 1;
            }

            return {
                file,
                total: items.length,
                severities: severityCount,
                fixable:
                    items.every(i =>
                        i.source?.toLowerCase().includes("typescript")
                    )
            };
        }
    );

    return {
        success: true,
        data: {
            totalFiles: summary.length,
            summary
        }
    };
}