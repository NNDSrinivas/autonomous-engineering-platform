/**
 * Context and workspace contracts
 * Defines the structure for workspace and execution context
 */

/**
 * Git repository information
 */
export interface GitInfo {
  branch: string;
  hasChanges: boolean;
  changedFiles?: string[];
  commitHash?: string;
  remoteUrl?: string;
}

/**
 * Diagnostic information summary
 */
export interface DiagnosticsSummary {
  errorCount: number;
  warningCount: number;
  infoCount: number;
  affectedFiles: string[];
  mostCommonIssues?: Array<{
    message: string;
    count: number;
    severity: 'error' | 'warning' | 'info';
  }>;
}

/**
 * Active file information
 */
export interface ActiveFile {
  path: string;
  relativePath: string;
  language?: string;
  size: number;
  lastModified: string;
  cursorPosition?: {
    line: number;
    column: number;
  };
  selection?: {
    start: { line: number; column: number };
    end: { line: number; column: number };
  };
}

/**
 * Workspace context information
 */
export interface WorkspaceInfo {
  rootPath: string;
  name: string;
  type?: 'git' | 'local' | 'remote';
  language?: string;
  framework?: string;
  packageManager?: 'npm' | 'yarn' | 'pnpm';
  hasTests?: boolean;
  hasCI?: boolean;
}

/**
 * Complete context pack for NAVI operations
 */
export interface ContextPack {
  // Core workspace information
  workspace: WorkspaceInfo;
  
  // Active file context (optional)
  activeFile?: ActiveFile;
  
  // Git context
  git?: GitInfo;
  
  // Diagnostics summary
  diagnostics?: DiagnosticsSummary;
  
  // User context
  user?: {
    id: string;
    preferences?: Record<string, unknown>;
  };
  
  // Session context
  session?: {
    id: string;
    startTime: string;
    messageCount: number;
  };
  
  // Timestamp
  timestamp: string;
}

/**
 * Request to gather context
 */
export interface ContextRequest {
  includeGit?: boolean;
  includeDiagnostics?: boolean;
  includeActiveFile?: boolean;
  maxDiagnostics?: number;
}

/**
 * Response containing gathered context
 */
export interface ContextResponse {
  context: ContextPack;
  success: boolean;
  warnings?: string[];
  errors?: string[];
}

/**
 * Creates a minimal context pack for fallback scenarios
 */
export function createMinimalContext(rootPath?: string): ContextPack {
  return {
    workspace: {
      rootPath: rootPath || process.cwd(),
      name: 'Unknown Workspace'
    },
    timestamp: new Date().toISOString()
  };
}

/**
 * Validates a context pack structure
 */
export function validateContextPack(context: unknown): context is ContextPack {
  if (!context || typeof context !== 'object') return false;
  
  const c = context as Partial<ContextPack>;
  return !!(
    c.workspace &&
    typeof c.workspace === 'object' &&
    c.workspace.rootPath &&
    c.workspace.name &&
    c.timestamp
  );
}

/**
 * Merges context packs, with later contexts taking precedence
 */
export function mergeContextPacks(...contexts: Partial<ContextPack>[]): ContextPack {
  const merged: Partial<ContextPack> = {};
  
  for (const context of contexts) {
    Object.assign(merged, context);
  }
  
  // Ensure required fields
  if (!merged.workspace) {
    merged.workspace = { rootPath: process.cwd(), name: 'Unknown' };
  }
  if (!merged.timestamp) {
    merged.timestamp = new Date().toISOString();
  }
  
  return merged as ContextPack;
}

/**
 * Extracts a summary string from context pack
 */
export function summarizeContext(context: ContextPack): string {
  const parts: string[] = [];
  
  parts.push(`Workspace: ${context.workspace.name}`);
  
  if (context.activeFile) {
    parts.push(`Active: ${context.activeFile.relativePath}`);
  }
  
  if (context.git) {
    parts.push(`Branch: ${context.git.branch}`);
    if (context.git.hasChanges) {
      parts.push(`(${context.git.changedFiles?.length || 0} changes)`);
    }
  }
  
  if (context.diagnostics) {
    const { errorCount, warningCount } = context.diagnostics;
    if (errorCount > 0 || warningCount > 0) {
      parts.push(`Diagnostics: ${errorCount} errors, ${warningCount} warnings`);
    }
  }
  
  return parts.join(' | ');
}