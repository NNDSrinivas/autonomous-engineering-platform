import * as vscode from 'vscode';
import { ChatResponse, DeviceCodeStart, DeviceCodeToken, JiraIssue, ProposedStep } from './types';

const TOKEN_SECRET = 'aep.token';

export class AEPClient {
  private token: string | undefined;

  constructor(
    private readonly ctx: vscode.ExtensionContext,
    private readonly baseUrl: string,
    private readonly orgId: string
  ) {}

  async hydrateToken(output?: vscode.OutputChannel): Promise<void> {
    const existing = await this.ctx.secrets.get(TOKEN_SECRET);
    if (!existing) {
      return;
    }

    const sanitized = this.sanitizeToken(existing);
    if (!sanitized) {
      await this.ctx.secrets.delete(TOKEN_SECRET);
      output?.appendLine('Removed invalid AEP session token from secret storage.');
      return;
    }

    this.token = sanitized;
    output?.appendLine('Restored existing AEP session token.');
  }

  async persistToken(token: string | undefined): Promise<void> {
    const sanitized = this.sanitizeToken(token);
    this.token = sanitized;
    if (sanitized) {
      await this.ctx.secrets.store(TOKEN_SECRET, sanitized);
    } else {
      await this.ctx.secrets.delete(TOKEN_SECRET);
    }
  }

  private sanitizeToken(token: string | undefined): string | undefined {
    if (typeof token !== 'string') {
      return undefined;
    }

    const trimmed = token.trim();
    if (trimmed.length === 0 || trimmed === 'undefined') {
      return undefined;
    }

    return trimmed;
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
    if (!token.access_token) {
      throw new Error('Device authorization succeeded but did not return an access token.');
    }

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
