import { toolRegistry } from "./registry";
import { ToolContext, ToolResult } from "./types";

export async function executeTool(
    toolName: string,
    ctx: ToolContext
): Promise<ToolResult> {
    const tool = toolRegistry[toolName];

    if (!tool) {
        return {
            success: false,
            error: `Unknown tool: ${toolName}`
        };
    }

    return tool(ctx);
}