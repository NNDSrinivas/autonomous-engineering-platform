import * as vscode from 'vscode';
import { ChatResponse, DeviceCodeStart, DeviceCodeToken, JiraIssue, ProposedStep } from './types';

export class AEPClient {
  private token: string | undefined;

  constructor(
    private readonly ctx: vscode.ExtensionContext,
    private readonly baseUrl: string,
    private readonly orgId: string
  ) {}

  async hydrateToken(output?: vscode.OutputChannel): Promise<void> {
    const existing = await this.ctx.secrets.get('aep.token');
    if (existing) {
      this.token = existing;
      output?.appendLine('Restored existing AEP session token.');
    }
  }

  async persistToken(token: string | undefined): Promise<void> {
    this.token = token;
    if (token) {
      await this.ctx.secrets.store('aep.token', token);
    } else {
      await this.ctx.secrets.delete('aep.token');
    }
  }

  setToken(token: string | undefined) {
    this.token = token;
  }

  hasToken(): boolean {
    return Boolean(this.token);
  }

  async clearToken(): Promise<void> {
    await this.persistToken(undefined);
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Org-Id': this.orgId
    };

    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }

    return headers;
  }

  async startDeviceCode(): Promise<DeviceCodeStart> {
    const response = await fetch(`${this.baseUrl}/oauth/device/start`, {
      method: 'POST',
      headers: this.headers()
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    return (await response.json()) as DeviceCodeStart;
  }

  async pollDeviceCode(deviceCode: string): Promise<DeviceCodeToken> {
    const response = await fetch(`${this.baseUrl}/oauth/device/poll`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ device_code: deviceCode })
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    const token = (await response.json()) as DeviceCodeToken;
    await this.persistToken(token.access_token);
    return token;
  }

  async listMyJiraIssues(): Promise<JiraIssue[]> {
    const response = await fetch(`${this.baseUrl}/api/integrations/jira/my-issues`, {
      headers: this.headers()
    });

    if (!response.ok) {
      return [];
    }

    return (await response.json()) as JiraIssue[];
  }

  async me(): Promise<{ email?: string; name?: string; sub?: string; org?: string; roles?: string[] }> {
    const response = await fetch(`${this.baseUrl}/api/me`, { headers: this.headers() });

    if (!response.ok) {
      return {};
    }

    return (await response.json()) as {
      email?: string;
      name?: string;
      sub?: string;
      org?: string;
      roles?: string[];
    };
  }

  async proposePlan(issueKey: string): Promise<ProposedStep[]> {
    const response = await fetch(`${this.baseUrl}/api/agent/propose`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ issue_key: issueKey })
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    return (await response.json()) as ProposedStep[];
  }

  async applyPatch(patch: string): Promise<{ output: string; applied: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/ai/apply-patch`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ diff: patch, dry_run: false })
    });

    const payload = (await response.json()) as any;

    if (!response.ok) {
      throw new Error(payload.detail || JSON.stringify(payload));
    }

    return payload as { output: string; applied: boolean };
  }

  async chat(message: string, type: 'question' | 'command' = 'question'): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ message, type })
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    return (await response.json()) as ChatResponse;
  }
}
