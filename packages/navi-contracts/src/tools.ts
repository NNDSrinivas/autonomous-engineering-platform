/**
 * Tool execution contracts
 * Defines the interface for tool calls and results
 */

/**
 * Available tool types
 */
export enum ToolType {
  GET_DIAGNOSTICS = 'getDiagnostics',
  READ_FILE = 'readFile', 
  APPLY_EDITS = 'applyEdits',
  RUN_COMMAND = 'runCommand'
}

/**
 * Base tool call interface
 */
export interface ToolCall {
  id: string;
  tool: ToolType;
  inputs: Record<string, unknown>;
  timestamp: string;
}

/**
 * Base tool result interface
 */
export interface ToolResult {
  id: string;
  success: boolean;
  result?: unknown;
  error?: string;
  duration?: number;
  timestamp: string;
}

/**
 * Get diagnostics tool contracts
 */
export interface GetDiagnosticsCall extends ToolCall {
  tool: ToolType.GET_DIAGNOSTICS;
  inputs: {
    includeWarnings?: boolean;
    filePattern?: string;
  };
}

export interface GetDiagnosticsResult extends ToolResult {
  result?: {
    errors: Array<{
      file: string;
      line: number;
      column: number;
      message: string;
      severity: 'error' | 'warning' | 'info';
      code?: string;
    }>;
    summary: {
      errorCount: number;
      warningCount: number;
      fileCount: number;
    };
  };
}

/**
 * Read file tool contracts
 */
export interface ReadFileCall extends ToolCall {
  tool: ToolType.READ_FILE;
  inputs: {
    filePath: string;
    startLine?: number;
    endLine?: number;
    encoding?: string;
  };
}

export interface ReadFileResult extends ToolResult {
  result?: {
    content: string;
    lineCount: number;
    size: number;
    lastModified: string;
  };
}

/**
 * Apply edits tool contracts
 */
export interface ApplyEditsCall extends ToolCall {
  tool: ToolType.APPLY_EDITS;
  inputs: {
    filePath: string;
    edits: Array<{
      startLine: number;
      endLine: number;
      newText: string;
    }>;
    validateSyntax?: boolean;
  };
}

export interface ApplyEditsResult extends ToolResult {
  result?: {
    appliedEdits: number;
    newContent?: string;
    syntaxValid?: boolean;
    backupPath?: string;
  };
}

/**
 * Run command tool contracts (gated)
 */
export interface RunCommandCall extends ToolCall {
  tool: ToolType.RUN_COMMAND;
  inputs: {
    command: string;
    args?: string[];
    cwd?: string;
    timeout?: number;
    requiresApproval: boolean;
  };
}

export interface RunCommandResult extends ToolResult {
  result?: {
    exitCode: number;
    stdout: string;
    stderr: string;
    duration: number;
  };
}

/**
 * Union type for all tool calls
 */
export type AnyToolCall = GetDiagnosticsCall | ReadFileCall | ApplyEditsCall | RunCommandCall;

/**
 * Union type for all tool results
 */
export type AnyToolResult = GetDiagnosticsResult | ReadFileResult | ApplyEditsResult | RunCommandResult;

/**
 * Tool execution request
 */
export interface ToolExecutionRequest {
  calls: AnyToolCall[];
  context?: {
    planId?: string;
    stepId?: string;
    userId?: string;
  };
}

/**
 * Tool execution response
 */
export interface ToolExecutionResponse {
  results: AnyToolResult[];
  success: boolean;
  errors?: string[];
}

/**
 * Validates a tool call structure
 */
export function validateToolCall(call: unknown): call is AnyToolCall {
  if (!call || typeof call !== 'object') return false;
  
  const c = call as Partial<ToolCall>;
  return !!(
    c.id &&
    c.tool &&
    Object.values(ToolType).includes(c.tool as ToolType) &&
    c.inputs &&
    typeof c.inputs === 'object' &&
    c.timestamp
  );
}

/**
 * Creates a safe tool execution context
 */
export function createToolContext(planId?: string, stepId?: string): object {
  return {
    planId: planId || 'unknown',
    stepId: stepId || 'unknown', 
    timestamp: new Date().toISOString(),
    safety: {
      requiresApproval: true,
      timeoutMs: 30000
    }
  };
}