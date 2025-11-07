import * as vscode from 'vscode';
import { DeviceCodeStart, DeviceCodeToken, JiraIssue, ProposedStep } from './types';

export class AEPClient {
  private token: string | undefined;
  constructor(private ctx: vscode.ExtensionContext, private baseUrl: string, private orgId: string){}
  setToken(t: string){ this.token = t; }

  private headers(){
    const h: any = { 'Content-Type': 'application/json', 'X-Org-Id': this.orgId };
    if (this.token) h['Authorization'] = `Bearer ${this.token}`;
    return h;
  }

  async startDeviceCode(): Promise<DeviceCodeStart>{
    const r = await fetch(`${this.baseUrl}/oauth/device/start`, { method: 'POST', headers: this.headers() });
    if (!r.ok) throw new Error(await r.text());
    return await r.json() as DeviceCodeStart;
  }
  async pollDeviceCode(deviceCode: string): Promise<DeviceCodeToken>{
    const r = await fetch(`${this.baseUrl}/oauth/device/poll`, { method: 'POST', headers: this.headers(), body: JSON.stringify({ device_code: deviceCode }) });
    if (!r.ok) throw new Error(await r.text());
    const tok = await r.json() as DeviceCodeToken;
    this.setToken(tok.access_token);
    return tok;
  }

  async listMyJiraIssues(): Promise<JiraIssue[]>{
    const r = await fetch(`${this.baseUrl}/api/integrations/jira/my-issues`, { headers: this.headers() });
    if (!r.ok) return [];
    return await r.json() as JiraIssue[];
  }

  async me(): Promise<{email?:string; name?:string; sub?:string; org?:string; roles?: string[]}> {
    const r = await fetch(`${this.baseUrl}/api/me`, { headers: this.headers() });
    if (!r.ok) return {};
    return await r.json() as {email?:string; name?:string; sub?:string; org?:string; roles?: string[]};
  }

  async proposePlan(issueKey: string): Promise<ProposedStep[]>{
    const r = await fetch(`${this.baseUrl}/api/agent/propose`, { method:'POST', headers:this.headers(), body: JSON.stringify({ issue_key: issueKey }) });
    if (!r.ok) throw new Error(await r.text());
    return await r.json() as ProposedStep[];
  }

  async applyPatch(patch: string): Promise<{output:string; applied:boolean}>{
    const r = await fetch(`${this.baseUrl}/api/ai/apply-patch`, { method:'POST', headers:this.headers(), body: JSON.stringify({ diff: patch, dry_run: false }) });
    const j = await r.json() as any;
    if (!r.ok) throw new Error(j.detail || JSON.stringify(j));
    return j as {output:string; applied:boolean};
  }
}