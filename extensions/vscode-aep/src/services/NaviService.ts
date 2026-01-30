/**
 * NAVI V2 Service
 * Handles communication with NAVI backend including approval flow
 */

import * as vscode from 'vscode';
import axios from 'axios';

export interface NaviPlan {
  planId: string;
  message: string;
  requiresApproval: boolean;
  actionsWithRisk: ActionWithRisk[];
  thinkingSteps: string[];
  filesRead: string[];
  projectType?: string;
  framework?: string;
}

export interface ActionWithRisk {
  type: 'createFile' | 'editFile' | 'runCommand';
  path?: string;
  command?: string;
  content?: string;
  risk: 'low' | 'medium' | 'high';
  warnings: string[];
  preview?: string;
}

export interface ExecutionUpdate {
  type: 'action_start' | 'action_complete' | 'plan_complete' | 'error';
  index?: number;
  action?: ActionWithRisk;
  success?: boolean;
  output?: string;
  error?: string;
  exitCode?: number;
}

export class NaviService {
  private static instance: NaviService;
  private baseUrl = 'http://localhost:8787';
  private activePlan: NaviPlan | null = null;

  private constructor() {}

  static getInstance(): NaviService {
    if (!NaviService.instance) {
      NaviService.instance = new NaviService();
    }
    return NaviService.instance;
  }

  setBaseUrl(baseUrl: string): void {
    const normalized = baseUrl.replace(/\/+$/, '');
    this.baseUrl = normalized || this.baseUrl;
  }

  /**
   * Create a plan (doesn't execute)
   */
  async createPlan(
    message: string,
    workspace: string,
    context?: any
  ): Promise<NaviPlan> {
    const response = await axios.post(`${this.baseUrl}/api/navi/v2/plan`, {
      message,
      workspace,
      llm_provider: 'anthropic',
      context,
    });

    const data: any = response.data;

    const plan: NaviPlan = {
      planId: data.plan_id,
      message: data.message,
      requiresApproval: data.requires_approval,
      actionsWithRisk: data.actions_with_risk || [],
      thinkingSteps: data.thinking_steps || [],
      filesRead: data.files_read || [],
      projectType: data.project_type,
      framework: data.framework,
    };

    this.activePlan = plan;
    return plan;
  }

  /**
   * Get plan by ID
   */
  async getPlan(planId: string): Promise<NaviPlan> {
    const response = await axios.get(`${this.baseUrl}/api/navi/v2/plan/${planId}`);
    const data: any = response.data;
    return {
      planId: data.id,
      message: data.response.message,
      requiresApproval: data.response.requires_approval,
      actionsWithRisk: data.response.actions_with_risk || [],
      thinkingSteps: data.response.thinking_steps || [],
      filesRead: data.response.files_read || [],
      projectType: data.response.project_type,
      framework: data.response.framework,
    };
  }

  /**
   * Approve and execute plan
   */
  async approvePlan(
    planId: string,
    approvedActionIndices: number[]
  ): Promise<string> {
    const response = await axios.post(
      `${this.baseUrl}/api/navi/v2/plan/${planId}/approve`,
      { approved_action_indices: approvedActionIndices }
    );

    return response.data.execution_id;
  }

  async approvePlanStream(
    planId: string,
    approvedActionIndices: number[],
    onUpdate: (update: ExecutionUpdate) => void
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/navi/v2/plan/${planId}/approve/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({ approved_action_indices: approvedActionIndices }),
      }
    );

    if (!response.ok || !response.body) {
      const text = response.body ? await response.text() : '';
      throw new Error(`Plan stream failed: ${response.status} ${text}`.trim());
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIndex: number;
      while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        if (!line.startsWith('data:')) continue;

        const payload = line.slice('data:'.length).trim();
        if (!payload) continue;

        try {
          const parsed = JSON.parse(payload);
          onUpdate(parsed);
        } catch {
          onUpdate({ type: 'error', error: payload } as ExecutionUpdate);
        }
      }
    }
  }

  /**
   * Show diff view for a file modification
   */
  async showDiff(
    action: ActionWithRisk,
    workspaceRoot: string
  ): Promise<void> {
    if (action.type !== 'editFile' || !action.path || !action.content) {
      throw new Error('Can only show diff for file edits');
    }

    const filePath = vscode.Uri.file(`${workspaceRoot}/${action.path}`);

    // Read original file content
    let originalContent = '';
    try {
      const fileContent = await vscode.workspace.fs.readFile(filePath);
      originalContent = Buffer.from(fileContent).toString('utf8');
    } catch (error) {
      // File doesn't exist yet
      originalContent = '';
    }

    // Create temp file with new content
    const tempUri = vscode.Uri.file(
      `${workspaceRoot}/${action.path}.proposed`
    );
    await vscode.workspace.fs.writeFile(
      tempUri,
      Buffer.from(action.content, 'utf8')
    );

    // Open diff view
    await vscode.commands.executeCommand(
      'vscode.diff',
      filePath,
      tempUri,
      `${action.path} (Original ↔ Proposed)`
    );
  }

  /**
   * Show diff for create file (empty vs new content)
   */
  async showCreateFileDiff(
    action: ActionWithRisk,
    workspaceRoot: string
  ): Promise<void> {
    if (action.type !== 'createFile' || !action.path || !action.content) {
      throw new Error('Invalid create file action');
    }

    // Create empty temp file for "before"
    const emptyUri = vscode.Uri.file(
      `${workspaceRoot}/${action.path}.empty`
    );
    await vscode.workspace.fs.writeFile(emptyUri, Buffer.from('', 'utf8'));

    // Create temp file with new content for "after"
    const newUri = vscode.Uri.file(
      `${workspaceRoot}/${action.path}.new`
    );
    await vscode.workspace.fs.writeFile(
      newUri,
      Buffer.from(action.content, 'utf8')
    );

    // Open diff view
    await vscode.commands.executeCommand(
      'vscode.diff',
      emptyUri,
      newUri,
      `${action.path} (New File)`
    );
  }

  /**
   * Open file in editor
   */
  async openFile(filePath: string, workspaceRoot: string): Promise<void> {
    const uri = vscode.Uri.file(`${workspaceRoot}/${filePath}`);
    await vscode.window.showTextDocument(uri);
  }

  /**
   * Execute a single action manually
   */
  async executeAction(
    action: ActionWithRisk,
    workspaceRoot: string
  ): Promise<void> {
    if (action.type === 'createFile' && action.path && action.content) {
      const uri = vscode.Uri.file(`${workspaceRoot}/${action.path}`);
      await vscode.workspace.fs.writeFile(
        uri,
        Buffer.from(action.content, 'utf8')
      );
      vscode.window.showInformationMessage(`Created ${action.path}`);
    } else if (action.type === 'editFile' && action.path && action.content) {
      const uri = vscode.Uri.file(`${workspaceRoot}/${action.path}`);
      await vscode.workspace.fs.writeFile(
        uri,
        Buffer.from(action.content, 'utf8')
      );
      vscode.window.showInformationMessage(`Modified ${action.path}`);
    } else if (action.type === 'runCommand' && action.command) {
      // Run command in terminal
      const terminal = vscode.window.createTerminal({
        name: 'NAVI Command',
        cwd: workspaceRoot,
      });
      terminal.sendText(action.command);
      terminal.show();
    }
  }

  /**
   * Clear active plan
   */
  clearActivePlan(): void {
    this.activePlan = null;
  }

  /**
   * Get active plan
   */
  getActivePlan(): NaviPlan | null {
    return this.activePlan;
  }
}
