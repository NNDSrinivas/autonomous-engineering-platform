/**
 * NAVI Client for VS Code Extension
 * Provides backend communication with streaming support
 */

export interface NaviClientConfig {
    apiUrl: string;
    realtimeUrl: string;
    orgId: string;
    userId?: string;
    apiKey?: string;
}

export class NaviClient {
    private apiUrl: string;
    private realtimeUrl: string;
    private orgId: string;
    private userId: string;
    private apiKey?: string;
    private listeners: Map<string, Set<(data: any) => void>> = new Map();

    constructor(apiUrl: string, realtimeUrl: string, orgId: string, userId: string = 'dev-user') {
        this.apiUrl = apiUrl;
        this.realtimeUrl = realtimeUrl;
        this.orgId = orgId;
        this.userId = userId;
    }

    private getHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            'X-Org-Id': this.orgId,
            'X-User-Id': this.userId
        };

        if (this.apiKey) {
            headers['Authorization'] = `Bearer ${this.apiKey}`;
        }

        return headers;
    }

    async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${this.apiUrl}${endpoint}`;
        const response = await fetch(url, {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`API request failed: ${response.status} ${error}`);
        }

        return response.json() as Promise<T>;
    }

    on(event: string, callback: (data: any) => void): () => void {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event)!.add(callback);

        return () => {
            this.listeners.get(event)?.delete(callback);
        };
    }

    private emit(event: string, data: any) {
        this.listeners.get(event)?.forEach(callback => callback(data));
    }

    // API Methods

    async generateCode(request: {
        prompt: string;
        context: any;
        language: string;
    }): Promise<{ code: string; explanation: string }> {
        return this.request('/api/code/generate', {
            method: 'POST',
            body: JSON.stringify(request)
        });
    }

    async explainCode(code: string): Promise<string> {
        const response = await this.request<{ explanation: string }>('/api/code/explain', {
            method: 'POST',
            body: JSON.stringify({ code })
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
            body: JSON.stringify(request)
        });
    }

    async generateTests(request: {
        code: string;
        language: string;
        filePath: string;
    }): Promise<{ testCode: string; framework: string }> {
        return this.request('/api/code/tests', {
            method: 'POST',
            body: JSON.stringify(request)
        });
    }

    async fixBug(request: {
        code: string;
        diagnostics: any[];
        context: any;
    }): Promise<{ fixedCode: string; explanation: string }> {
        return this.request('/api/code/fix', {
            method: 'POST',
            body: JSON.stringify(request)
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
            body: JSON.stringify(request)
        });
    }

    async createPR(request: {
        title: string;
        changes: any[];
        context: any;
    }): Promise<{ url: string; number: number }> {
        return this.request('/api/git/pr', {
            method: 'POST',
            body: JSON.stringify(request)
        });
    }

    async reviewChanges(request: {
        changes: any[];
        context: any;
    }): Promise<{ comments: any[]; summary: string }> {
        return this.request('/api/git/review', {
            method: 'POST',
            body: JSON.stringify(request)
        });
    }

    async searchMemory(query: string, k: number = 10): Promise<any[]> {
        const response = await this.request<{ hits: any[] }>('/api/search/', {
            method: 'POST',
            body: JSON.stringify({ q: query, k })
        });
        return response.hits;
    }

    async getTaskContext(taskKey: string): Promise<any> {
        return this.request(`/api/context/pack`, {
            method: 'POST',
            body: JSON.stringify({
                query: taskKey,
                task_key: taskKey,
                k: 10
            })
        });
    }

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
            body: JSON.stringify(request)
        });
    }

    async addPlanStep(planId: string, step: {
        text: string;
        kind: string;
        meta?: any;
    }): Promise<void> {
        await this.request(`/api/plan/${planId}/step`, {
            method: 'POST',
            body: JSON.stringify(step)
        });
    }

    async executePlan(planId: string): Promise<void> {
        await this.request(`/api/plan/${planId}/execute`, {
            method: 'POST'
        });
    }

    dispose() {
        this.listeners.clear();
    }
}
