export interface ToolContext {
    workspaceRoot: string;
    previousResult?: any;
}

export interface ToolResult {
    success: boolean;
    data?: any;
    error?: string;
}

export type ToolHandler = (ctx: ToolContext) => Promise<ToolResult>;