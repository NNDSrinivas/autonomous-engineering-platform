// Webview NAVI API helpers (runtime-config aware).

const FALLBACK_BACKEND_BASE_URL = "http://127.0.0.1:8787";

type RuntimeConfig = {
  backendBaseUrl?: string;
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
  };
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
        'Content-Type': 'application/json',
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
}

// Export singleton instance
export const naviClient = new NaviAPIClient();
