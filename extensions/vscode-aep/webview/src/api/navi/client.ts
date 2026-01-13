// Webview NAVI API helpers (runtime-config aware).

const FALLBACK_BACKEND_BASE_URL = "http://127.0.0.1:8787";

type RuntimeConfig = {
  backendBaseUrl?: string;
};

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
    context: any;
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
    context: any;
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
    diagnostics: any[];
    context: any;
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
    context: any;
  }): Promise<{ completion: string; confidence: number }> {
    return this.request('/api/code/complete', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Git & PR APIs

  async createPR(request: {
    title: string;
    changes: any[];
    context: any;
  }): Promise<{ url: string; number: number }> {
    return this.request('/api/git/pr', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async reviewChanges(request: {
    changes: any[];
    context: any;
  }): Promise<{ comments: any[]; summary: string }> {
    return this.request('/api/git/review', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Memory & Context APIs

  async searchMemory(query: string, k: number = 10): Promise<any[]> {
    const response = await this.request<{ hits: any[] }>('/api/search/', {
      method: 'POST',
      body: JSON.stringify({ q: query, k }),
    });
    return response.hits;
  }

  async getTaskContext(taskKey: string): Promise<any> {
    return this.request('/api/context/pack', {
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
