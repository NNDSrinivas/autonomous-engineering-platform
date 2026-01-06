export type ToolCall = {
  id: string;
  name: string;
  inputs: Record<string, unknown>;
};

export type ToolResult = {
  id: string;
  name: string;
  ok: boolean;
  output?: unknown;
  error?: string;
};