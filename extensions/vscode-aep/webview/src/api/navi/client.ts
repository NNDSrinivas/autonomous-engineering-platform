// Webview NAVI API helpers (runtime-config aware).
import { fetchEventSource } from "@microsoft/fetch-event-source";

const FALLBACK_BACKEND_BASE_URL = "http://127.0.0.1:8787";

type RuntimeConfig = {
  backendBaseUrl?: string;
  authToken?: string;
  orgId?: string;
  userId?: string;
};

// Type-safe interfaces for API requests/responses
export interface WorkspaceInfo {
  rootPath: string;
  technologies: string[];
  totalFiles: number;
  gitBranch?: string;
}

export interface EditorContext {
  currentFile: string;
  language: string;
  selection?: {
    text: string;
    range: {
      start: { line: number; character: number };
      end: { line: number; character: number };
    };
  };
  surroundingCode?: {
    before: string;
    after: string;
  };
  imports?: string[];
}

export interface CodeContext {
  workspace?: WorkspaceInfo;
  editor?: EditorContext;
  additionalContext?: Record<string, unknown>;
}

export interface Diagnostic {
  message: string;
  severity: number;
  line: number;
  character: number;
  source?: string;
  code?: string | number;
}

export interface MemorySearchResult {
  id: string;
  content: string;
  similarity: number;
  metadata?: Record<string, unknown>;
  source?: string;
  timestamp?: string;
}

export interface TaskContextResponse {
  task: {
    key: string;
    summary: string;
    description?: string;
    status: string;
    assignee?: string;
  };
  relatedTasks?: Array<{
    key: string;
    summary: string;
    relation: string;
  }>;
  recentComments?: Array<{
    author: string;
    body: string;
    created: string;
  }>;
  linkedPRs?: Array<{
    number: number;
    title: string;
    url: string;
    status: string;
  }>;
  relatedMeetings?: Array<{
    id: string;
    title: string;
    date: string;
  }>;
  codeReferences?: Array<{
    filePath: string;
    lineNumber?: number;
    snippet?: string;
  }>;
}

function getRuntimeConfig(): RuntimeConfig {
  if (typeof window === "undefined") {
    return {};
  }
  const config = (window as any).__AEP_CONFIG__ || {};
  return {
    backendBaseUrl: config.backendBaseUrl,
    authToken: config.authToken,
    orgId: config.orgId,
    userId: config.userId,
  };
}

/**
 * Build headers for API requests including auth token if available
 * Exported for use in other modules that need to make authenticated requests
 */
export function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const { orgId, userId, authToken } = getRuntimeConfig();

  if (orgId) {
    headers["X-Org-Id"] = orgId;
  }
  if (userId) {
    headers["X-User-Id"] = userId;
  }
  if (authToken) {
    headers.Authorization = authToken.startsWith("Bearer ") ? authToken : `Bearer ${authToken}`;
  }
  return headers;
}

/**
 * Resolve the backend base URL.
 * Priority:
 * 1) VS Code webview runtime config
 * 2) Same-origin (local dev)
 * 3) Fallback localhost
 */
export function resolveBackendBase(): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const override = getRuntimeConfig().backendBaseUrl;

  const base = override || origin || FALLBACK_BACKEND_BASE_URL;
  const cleaned = base.replace(/\/$/, "");
  return cleaned.replace(/\/api\/navi\/chat$/i, "");
}

/**
 * Enhanced NAVI API Client for Webview
 * Provides code generation, refactoring, and autonomous coding capabilities
 */
export class NaviAPIClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || resolveBackendBase();
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        ...buildHeaders(),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API request failed: ${response.status} ${error}`);
    }

    return response.json();
  }

  // Code Generation APIs

  async generateCode(request: {
    prompt: string;
    context: CodeContext;
    language: string;
  }): Promise<{ code: string; explanation: string }> {
    return this.request('/api/code/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async explainCode(code: string): Promise<string> {
    const response = await this.request<{ explanation: string }>('/api/code/explain', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
    return response.explanation;
  }

  async refactorCode(request: {
    code: string;
    context: CodeContext;
    language: string;
  }): Promise<{ refactoredCode: string; explanation: string }> {
    return this.request('/api/code/refactor', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async generateTests(request: {
    code: string;
    language: string;
    filePath: string;
  }): Promise<{ testCode: string; framework: string }> {
    return this.request('/api/code/tests', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async fixBug(request: {
    code: string;
    diagnostics: Diagnostic[];
    context: CodeContext;
  }): Promise<{ fixedCode: string; explanation: string }> {
    return this.request('/api/code/fix', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getInlineCompletion(request: {
    prefix: string;
    suffix: string;
    language: string;
    context: CodeContext;
  }): Promise<{ completion: string; confidence: number }> {
    return this.request('/api/code/complete', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Git & PR APIs

  async createPR(request: {
    title: string;
    changes: Array<{ file: string; additions: number; deletions: number }>;
    context: CodeContext;
  }): Promise<{ url: string; number: number }> {
    return this.request('/api/git/pr', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async reviewChanges(request: {
    changes: Array<{ file: string; additions: number; deletions: number }>;
    context: CodeContext;
  }): Promise<{ comments: Array<{ file: string; line: number; message: string }>; summary: string }> {
    return this.request('/api/git/review', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Memory & Context APIs

  async searchMemory(query: string, k: number = 10): Promise<MemorySearchResult[]> {
    const response = await this.request<{ hits: MemorySearchResult[] }>('/api/search/', {
      method: 'POST',
      body: JSON.stringify({ q: query, k }),
    });
    return response.hits;
  }

  async getTaskContext(taskKey: string): Promise<TaskContextResponse> {
    return this.request<TaskContextResponse>('/api/context/pack', {
      method: 'POST',
      body: JSON.stringify({
        query: taskKey,
        task_key: taskKey,
        k: 10,
      }),
    });
  }

  // Task & Planning APIs

  async getTasks(): Promise<any[]> {
    return this.request('/api/tasks');
  }

  async createPlan(request: {
    title: string;
    task_key?: string;
    context: any;
  }): Promise<{ plan_id: string; plan: any }> {
    return this.request('/api/plan/', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async addPlanStep(
    planId: string,
    step: {
      text: string;
      kind: string;
      meta?: any;
    }
  ): Promise<void> {
    await this.request(`/api/plan/${planId}/step`, {
      method: 'POST',
      body: JSON.stringify(step),
    });
  }

  async executePlan(planId: string): Promise<void> {
    await this.request(`/api/plan/${planId}/execute`, {
      method: 'POST',
    });
  }

  // ========================================================================
  // Advanced Operations APIs (Git, Database, Debugging)
  // ========================================================================

  // Git Operations

  async gitCherryPick(request: {
    workspace_path: string;
    commit_hashes: string[];
    no_commit?: boolean;
  }, approved: boolean = false): Promise<GitOperationResult> {
    return this.request(`/api/advanced/git/cherry-pick?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async gitRebase(request: {
    workspace_path: string;
    onto: string;
    interactive?: boolean;
  }, approved: boolean = false): Promise<GitOperationResult> {
    return this.request(`/api/advanced/git/rebase?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async gitSquash(request: {
    workspace_path: string;
    num_commits: number;
    message: string;
  }, approved: boolean = false): Promise<GitOperationResult> {
    return this.request(`/api/advanced/git/squash?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async gitStash(request: {
    workspace_path: string;
    operation: 'save' | 'pop' | 'list' | 'apply' | 'drop' | 'clear';
    message?: string;
    stash_id?: string;
  }): Promise<GitOperationResult> {
    return this.request('/api/advanced/git/stash', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async gitBisect(request: {
    workspace_path: string;
    operation: 'start' | 'good' | 'bad' | 'reset' | 'skip' | 'run';
    commit?: string;
    script?: string;
  }): Promise<GitOperationResult> {
    return this.request('/api/advanced/git/bisect', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async gitReflog(request: {
    workspace_path: string;
    operation: 'show' | 'recover';
    ref?: string;
    limit?: number;
  }): Promise<GitOperationResult> {
    return this.request('/api/advanced/git/reflog', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async gitCleanupBranches(request: {
    workspace_path: string;
    dry_run?: boolean;
    include_remote?: boolean;
  }, approved: boolean = false): Promise<GitOperationResult> {
    return this.request(`/api/advanced/git/cleanup-branches?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Database Operations

  async dbSchemaDiff(request: {
    workspace_path: string;
    source: 'models' | 'database' | 'migration';
    target: 'models' | 'database' | 'migration';
  }): Promise<DatabaseOperationResult> {
    return this.request('/api/advanced/db/schema-diff', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async dbGenerateMigration(request: {
    workspace_path: string;
    message: string;
    autogenerate?: boolean;
  }, approved: boolean = false): Promise<DatabaseOperationResult> {
    return this.request(`/api/advanced/db/generate-migration?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async dbApplyMigration(request: {
    workspace_path: string;
    revision?: string;
    dry_run?: boolean;
  }, approved: boolean = false): Promise<DatabaseOperationResult> {
    return this.request(`/api/advanced/db/apply-migration?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async dbRollback(request: {
    workspace_path: string;
    steps?: number;
    revision?: string;
  }, approved: boolean = false): Promise<DatabaseOperationResult> {
    return this.request(`/api/advanced/db/rollback?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async dbMigrationHistory(workspace_path: string, verbose?: boolean): Promise<DatabaseOperationResult> {
    const params = new URLSearchParams({ workspace_path });
    if (verbose !== undefined) params.append('verbose', String(verbose));
    return this.request(`/api/advanced/db/migration-history?${params}`);
  }

  async dbSeed(request: {
    workspace_path: string;
    seed_file?: string;
    environment?: 'dev' | 'test' | 'staging';
  }, approved: boolean = false): Promise<DatabaseOperationResult> {
    return this.request(`/api/advanced/db/seed?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Debugging Operations

  async debugAnalyzeError(request: {
    error_output: string;
    workspace_path?: string;
    language?: string;
  }): Promise<DebugAnalysisResult> {
    return this.request('/api/advanced/debug/analyze-error', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async debugPerformance(request: {
    workspace_path: string;
    file_path?: string;
  }): Promise<DebugAnalysisResult> {
    return this.request('/api/advanced/debug/performance', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async debugDeadCode(workspace_path: string): Promise<DebugAnalysisResult> {
    return this.request(`/api/advanced/debug/dead-code?workspace_path=${encodeURIComponent(workspace_path)}`, {
      method: 'POST',
    });
  }

  async debugCircularDeps(workspace_path: string): Promise<DebugAnalysisResult> {
    return this.request(`/api/advanced/debug/circular-deps?workspace_path=${encodeURIComponent(workspace_path)}`, {
      method: 'POST',
    });
  }

  async debugCodeSmells(workspace_path: string): Promise<DebugAnalysisResult> {
    return this.request(`/api/advanced/debug/code-smells?workspace_path=${encodeURIComponent(workspace_path)}`, {
      method: 'POST',
    });
  }

  async debugAutoFix(request: {
    workspace_path: string;
    apply?: boolean;
  }, approved: boolean = false): Promise<DebugAnalysisResult> {
    return this.request(`/api/advanced/debug/auto-fix?approved=${approved}`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // MCP Operations

  async listMcpTools(): Promise<McpToolsResponse> {
    return this.request('/api/advanced/mcp/tools');
  }

  async listMcpServers(): Promise<McpServerListResponse> {
    return this.request('/api/advanced/mcp/servers');
  }

  async createMcpServer(payload: McpServerCreateRequest): Promise<McpServer> {
    return this.request('/api/advanced/mcp/servers', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateMcpServer(serverId: number, payload: McpServerUpdateRequest): Promise<McpServer> {
    return this.request(`/api/advanced/mcp/servers/${serverId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async deleteMcpServer(serverId: number): Promise<{ ok: boolean }> {
    return this.request(`/api/advanced/mcp/servers/${serverId}`, {
      method: 'DELETE',
    });
  }

  async testMcpServer(serverId: number): Promise<McpServerTestResponse> {
    return this.request(`/api/advanced/mcp/servers/${serverId}/test`, {
      method: 'POST',
    });
  }

  async executeMcpTool(
    tool_name: string,
    arguments_: Record<string, unknown>,
    approved: boolean = false,
    server_id?: string
  ): Promise<McpExecutionResult> {
    const serverParam = server_id ? `&server_id=${encodeURIComponent(server_id)}` : '';
    return this.request(`/api/advanced/mcp/execute?tool_name=${encodeURIComponent(tool_name)}&approved=${approved}${serverParam}`, {
      method: 'POST',
      body: JSON.stringify(arguments_),
    });
  }

  async getUsageAnalytics(days: number = 30): Promise<AnalyticsUsageResponse> {
    return this.request(`/api/analytics/usage?days=${encodeURIComponent(String(days))}`);
  }

  async getOrgAnalytics(days: number = 30): Promise<AnalyticsOrgResponse> {
    return this.request(`/api/analytics/org?days=${encodeURIComponent(String(days))}`);
  }

  async advancedHealthCheck(): Promise<AdvancedHealthResponse> {
    return this.request('/api/advanced/health');
  }

  /**
   * Stream NAVI responses with Server-Sent Events for better UX
   * Shows real-time progress updates instead of waiting for full response
   */
  async streamNaviChat(request: {
    message: string;
    workspace?: string;
    llm_provider?: string;
    onStatus?: (status: string) => void;
    onResult?: (result: any) => void;
    onError?: (error: string) => void;
    onDone?: () => void;
  }): Promise<void> {
    const url = `${this.baseUrl}/api/navi/process/stream`;

    return fetchEventSource(url, {
      method: 'POST',
      headers: {
        ...buildHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: request.message,
        workspace: request.workspace,
        llm_provider: request.llm_provider || 'openai',
      }),
      onmessage(event) {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'status':
              request.onStatus?.(data.message);
              break;
            case 'result':
              request.onResult?.(data.data);
              break;
            case 'error':
              request.onError?.(data.message);
              break;
            case 'done':
              request.onDone?.();
              break;
          }
        } catch (error) {
          console.error('[NaviClient] Failed to parse SSE message:', error);
          request.onError?.('Failed to parse server response');
        }
      },
      onerror(err) {
        console.error('[NaviClient] SSE connection error:', err);
        request.onError?.('Connection error');
        throw err; // Stop retry
      },
    });
  }
}

// ========================================================================
// Type Definitions for Advanced Operations
// ========================================================================

export interface GitOperationResult {
  success?: boolean;
  requires_approval?: boolean;
  message?: string;
  operation?: string;
  details?: Record<string, unknown>;
  output?: string;
  error?: string;
  commits?: string[];
  branches?: string[];
  stashes?: Array<{ id: string; message: string }>;
  reflog?: Array<{ ref: string; action: string; message: string }>;
}

export interface DatabaseOperationResult {
  success?: boolean;
  requires_approval?: boolean;
  message?: string;
  operation?: string;
  details?: Record<string, unknown>;
  diff?: string;
  migration_file?: string;
  migrations?: Array<{ revision: string; message: string; applied: boolean }>;
  error?: string;
}

export interface DebugAnalysisResult {
  success: boolean;
  errors?: Array<{
    language: string;
    category: string;
    error_type: string;
    message: string;
    file_path?: string;
    line?: number;
    column?: number;
    severity: string;
    suggestions: string[];
    auto_fix?: {
      type: string;
      description: string;
      changes?: Record<string, unknown>;
    };
  }>;
  issues?: Array<{
    type: string;
    severity: string;
    file?: string;
    line?: number;
    message: string;
    suggestion?: string;
  }>;
  summary?: {
    total_errors: number;
    by_category: Record<string, number>;
    by_severity: Record<string, number>;
  };
  debugging_commands?: string[];
  error?: string;
}

export interface McpToolsResponse {
  server_info: {
    name: string;
    version: string;
    protocolVersion: string;
    capabilities: Record<string, unknown>;
  };
  servers: McpServer[];
  tools: Array<{
    name: string;
    description: string;
    inputSchema: {
      type: string;
      properties: Record<string, unknown>;
      required: string[];
    };
    metadata: {
      category: string;
      requires_approval: boolean;
      server_id?: string | number;
      server_name?: string;
      source?: 'builtin' | 'external';
      transport?: string;
      scope?: 'org' | 'user' | 'builtin';
    };
  }>;
}

export interface McpServer {
  id: number | string;
  name: string;
  url: string;
  transport: string;
  auth_type: string;
  enabled: boolean;
  status: string;
  tool_count?: number | null;
  last_checked_at?: string | null;
  last_error?: string | null;
  config?: {
    auth_header_name?: string | null;
    headers?: Record<string, string>;
    username?: string | null;
  };
  source?: 'builtin' | 'external';
  scope?: 'org' | 'user' | 'builtin';
}

export interface McpServerCreateRequest {
  name: string;
  url: string;
  transport: string;
  auth_type: string;
  auth_header_name?: string | null;
  headers?: Record<string, string>;
  username?: string | null;
  token?: string | null;
  password?: string | null;
  enabled?: boolean;
}

export interface McpServerUpdateRequest {
  name?: string;
  url?: string;
  transport?: string;
  auth_type?: string;
  auth_header_name?: string | null;
  headers?: Record<string, string>;
  username?: string | null;
  token?: string | null;
  password?: string | null;
  enabled?: boolean;
  clear_secrets?: boolean;
}

export interface McpServerListResponse {
  items: McpServer[];
}

export interface McpServerTestResponse {
  ok: boolean;
  tool_count?: number;
  error?: string;
}

export interface McpExecutionResult {
  success: boolean;
  data: unknown;
  error?: string;
  metadata: {
    tool?: string;
    category?: string;
    executed_at?: string;
    requires_approval?: boolean;
    server_id?: string | number;
    server_name?: string;
    source?: 'builtin' | 'external';
    scope?: 'org' | 'user' | 'builtin';
  };
}

export interface AnalyticsRange {
  days: number;
  start: string;
  end: string;
}

export interface AnalyticsSummary {
  requests: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number | null;
  error_rate: number;
  error_count: number;
}

export interface AnalyticsModelBreakdown {
  model: string;
  requests: number;
  tokens: number;
  cost: number;
}

export interface AnalyticsDailyUsage {
  date: string | null;
  tokens: number;
  cost: number;
}

export interface AnalyticsTaskBreakdown {
  status: string;
  count: number;
}

export interface AnalyticsErrorBreakdown {
  severity: string;
  count: number;
}

export interface AnalyticsUsageResponse {
  scope: 'user';
  range: AnalyticsRange;
  summary: AnalyticsSummary;
  models: AnalyticsModelBreakdown[];
  daily: AnalyticsDailyUsage[];
  tasks: AnalyticsTaskBreakdown[];
  errors: AnalyticsErrorBreakdown[];
  note?: string;
}

export interface AnalyticsOrgResponse {
  scope: 'org';
  range: AnalyticsRange;
  summary: AnalyticsSummary;
  models: AnalyticsModelBreakdown[];
  daily: AnalyticsDailyUsage[];
  tasks: AnalyticsTaskBreakdown[];
  errors: AnalyticsErrorBreakdown[];
  top_users: Array<{ user_id: number; tokens: number; cost: number; requests: number }>;
  note?: string;
}

export interface AdvancedHealthResponse {
  status: string;
  mcp_server: {
    name: string;
    version: string;
    protocolVersion: string;
  };
  tools_count: number;
  categories: string[];
}

// Export singleton instance
export const naviClient = new NaviAPIClient();
