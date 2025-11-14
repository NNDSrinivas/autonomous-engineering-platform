import * as vscode from 'vscode';

export class Api {
    private getBaseUrl(): string {
        const cfg = vscode.workspace.getConfiguration('aep');
        return cfg.get<string>('api.baseUrl') || 'https://api.navralabs.com';
    }

    async chat(prompt: string, model: string, token: string): Promise<{ text: string } | null> {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                },
                body: JSON.stringify({
                    prompt,
                    model,
                    stream: false,
                    max_tokens: 4000,
                    temperature: 0.7
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API ${response.status}: ${errorText}`);
            }

            const data = await response.json() as any;
            return { text: data.response || data.text || data.content || 'No response from API' };
        } catch (error: any) {
            console.error('AEP API Error:', error);
            throw new Error(`API call failed: ${error?.message || String(error)}`);
        }
    }

    async getModels(token: string): Promise<string[]> {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/models`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                }
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API ${response.status}: ${errorText}`);
            }

            const data = await response.json() as any;
            return data.models || data.available_models || [];
        } catch (error: any) {
            console.error('AEP Models API Error:', error);
            // Fallback to configured models
            const cfg = vscode.workspace.getConfiguration('aep');
            return cfg.get<string[]>('model.allowed') || ['gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet'];
        }
    }

    async validateConnection(token: string): Promise<boolean> {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/health`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                }
            });

            return response.ok;
        } catch (error) {
            console.error('AEP Connection validation failed:', error);
            return false;
        }
    }

    // Method for testing if API is reachable without auth
    async ping(): Promise<boolean> {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/ping`, {
                method: 'GET',
                headers: {
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                }
            });

            return response.ok;
        } catch (error) {
            console.error('AEP Ping failed:', error);
            return false;
        }
    }
}