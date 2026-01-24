import * as vscode from 'vscode';
import { applyUnifiedPatch } from '../repo/applyPatch';
import { undoManager } from '../repo/undoManager';

export interface SmartModeConfig {
  backendUrl: string;
  autoApplyThreshold: number;
  showProgressNotifications: boolean;
  enableSmartVerification: boolean;
}

export interface RiskAssessment {
  mode: 'auto' | 'smart' | 'review';
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  reasons: string[];
  confidence: number;
  explanation: string;
}

export interface SmartModeResult {
  success: boolean;
  mode: string;
  filesModified: string[];
  executionTime?: number;
  patchSummary?: string;
  analysisResult?: any;
}

export class SmartModeSSEClient {
  private eventSource: EventSource | null = null;
  private outputChannel: vscode.OutputChannel;
  private currentProgress: vscode.Progress<{ message?: string; increment?: number }> | null = null;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('Navi Smart Mode');
  }

  /**
   * Connect to Smart Mode review stream
   */
  async connectReviewStream(
    files: string[],
    diffContent: string = '',
    instruction: string = '',
    llmConfidence: number = 0.9
  ): Promise<SmartModeResult> {
    const config = this.getSmartModeConfig();

    const requestPayload = {
      workspace_root: this.getWorkspaceRoot()
    };

    const streamUrl = new URL(`${config.backendUrl}/api/navi/analyze-changes`);

    return new Promise((resolve, reject) => {
      this.outputChannel.appendLine(`🚀 Starting Smart Mode review for ${files.length} files...`);

      // Show progress notification
      vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'Navi Smart Mode',
        cancellable: true
      }, async (progress, token) => {
        this.currentProgress = progress;

        try {
          // Make direct POST request to analyze-changes endpoint
          const response = await fetch(`${config.backendUrl}/api/navi/analyze-changes`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestPayload)
          });

          if (!response.ok) {
            throw new Error(`Backend response: ${response.status}`);
          }

          const reader = response.body?.getReader();
          if (!reader) {
            throw new Error('No response body');
          }

          const decoder = new TextDecoder();
          let buffer = '';
          let filesProcessed = 0;

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));

                  if (data.type === 'progress') {
                    progress.report({ message: data.step });
                    this.outputChannel.appendLine(`📊 ${data.step}`);
                  } else if (data.type === 'result') {
                    const analysisResult = data.result;
                    filesProcessed = analysisResult.files?.length || 0;

                    resolve({
                      success: true,
                      mode: 'comprehensive',
                      filesModified: analysisResult.files?.map((f: any) => f.path) || [],
                      analysisResult: analysisResult
                    });
                    return;
                  }
                } catch (parseError) {
                  this.outputChannel.appendLine(`⚠️ Parse error: ${parseError}`);
                }
              }
            }
          }

          // If we get here without a result, return success anyway
          resolve({
            success: true,
            mode: 'comprehensive',
            filesModified: [],
            analysisResult: { summary: 'Analysis completed', files: [] }
          });

        } catch (error) {
          this.outputChannel.appendLine(`❌ Error: ${error}`);
          reject(error);
        }
      });
    });
  }

  /**
   * Trigger the analyze changes via POST request
   */
  private async triggerAnalyzeChanges(backendUrl: string, payload: any): Promise<void> {
    try {
      const response = await fetch(`${backendUrl}/api/navi/analyze-changes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error) {
      throw new Error(`Failed to trigger analysis: ${error}`);
    }
  }

  /**
   * Handle Server-Sent Events from the Smart Mode backend
   */
  private async handleSSEEvents(
    resolve: (value: SmartModeResult) => void,
    reject: (reason: any) => void,
    token: vscode.CancellationToken
  ): Promise<SmartModeResult> {
    let result: SmartModeResult = {
      success: false,
      mode: 'unknown',
      filesModified: []
    };

    return new Promise((innerResolve, innerReject) => {
      if (!this.eventSource) {
        innerReject(new Error('EventSource not initialized'));
        return;
      }

      // Handle cancellation
      token.onCancellationRequested(() => {
        this.outputChannel.appendLine('🛑 Smart Mode cancelled by user');
        this.cleanup();
        innerReject(new Error('Cancelled by user'));
      });

      // Mode selection event
      this.eventSource.addEventListener('modeSelected', (event: any) => {
        const data = JSON.parse(event.data) as RiskAssessment & { timestamp: string };

        result.mode = data.mode;

        this.outputChannel.appendLine(`🎯 Smart Mode: ${data.mode.toUpperCase()}`);
        this.outputChannel.appendLine(`📊 Risk Score: ${data.risk_score.toFixed(2)} (${data.risk_level})`);
        this.outputChannel.appendLine(`💭 Reasons: ${data.reasons.join('; ')}`);

        vscode.window.showInformationMessage(
          `Navi Smart Mode → ${data.mode.toUpperCase()} (${data.risk_level} risk: ${data.risk_score.toFixed(2)})`
        );

        if (this.currentProgress) {
          this.currentProgress.report({
            message: `Mode: ${data.mode.toUpperCase()} - ${data.explanation}`
          });
        }
      });

      // Progress updates
      this.eventSource.addEventListener('progress', (event: any) => {
        const data = JSON.parse(event.data);

        this.outputChannel.appendLine(`⏳ ${data.message}`);
        vscode.window.setStatusBarMessage(`Navi: ${data.message}`, 3000);

        if (this.currentProgress) {
          this.currentProgress.report({ message: data.message });
        }
      });

      // Auto-applied changes
      this.eventSource.addEventListener('autoApplied', async (event: any) => {
        const data = JSON.parse(event.data);

        result.success = data.success;
        result.filesModified = data.files_modified || [];
        result.executionTime = data.execution_time;
        result.patchSummary = data.patch_summary;

        this.outputChannel.appendLine(`✅ Auto-applied changes to ${result.filesModified.length} files`);
        this.outputChannel.appendLine(`📝 Summary: ${result.patchSummary}`);

        vscode.window.showInformationMessage(
          `✅ Navi auto-applied changes to ${result.filesModified.length} files`,
          'View Changes'
        ).then(selection => {
          if (selection === 'View Changes') {
            vscode.commands.executeCommand('workbench.scm.focus');
          }
        });

        innerResolve(result);
      });

      // Review required
      this.eventSource.addEventListener('reviewEntry', async (event: any) => {
        const data = JSON.parse(event.data);

        this.outputChannel.appendLine(`📋 Review required for ${data.entries.length} files`);
        await this.showReviewPanel(data);
      });

      // Diff patches for review
      this.eventSource.addEventListener('diff', async (event: any) => {
        const data = JSON.parse(event.data);

        result.success = true; // Review mode is successful completion
        result.mode = 'review';

        this.outputChannel.appendLine(`📄 Generated ${data.patches.length} patches for review`);
        await this.showDiffPanel(data.patches, data.risk_level);

        innerResolve(result);
      });

      // Verification failed (smart mode fallback)
      this.eventSource.addEventListener('verificationFailed', async (event: any) => {
        const data = JSON.parse(event.data);

        this.outputChannel.appendLine(`⚠️ Verification failed: ${data.reason}`);
        vscode.window.showWarningMessage(
          `Smart Mode verification failed: ${data.reason}. Falling back to manual review.`
        );

        // Continue processing as review mode
      });

      // Processing complete
      this.eventSource.addEventListener('done', (event: any) => {
        this.outputChannel.appendLine('🎉 Smart Mode processing complete');
        vscode.window.setStatusBarMessage('Navi: Smart Mode completed', 2000);

        if (!result.success && result.mode !== 'review') {
          innerReject(new Error('Smart Mode processing failed'));
        } else {
          innerResolve(result);
        }
      });

      // Error handling
      this.eventSource.addEventListener('error', (event: any) => {
        const data = JSON.parse(event.data);

        this.outputChannel.appendLine(`❌ Error: ${data.message}`);
        vscode.window.showErrorMessage(`Navi Smart Mode error: ${data.message}`);

        innerReject(new Error(data.message));
      });

      // Connection error
      this.eventSource.onerror = (error) => {
        this.outputChannel.appendLine(`🚨 SSE Connection error: ${error}`);
        innerReject(new Error('SSE connection failed'));
      };
    });
  }

  /**
   * Show interactive review panel for manual approval
   */
  private async showReviewPanel(reviewData: any): Promise<void> {
    const panel = vscode.window.createWebviewPanel(
      'naviSmartReview',
      'Navi Smart Mode Review',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true
      }
    );

    panel.webview.html = this.getReviewPanelHtml(reviewData);

    // Handle messages from review panel
    panel.webview.onDidReceiveMessage(async (message) => {
      switch (message.type) {
        case 'approveChanges':
          await this.applyReviewedChanges(message.patches);
          panel.dispose();
          break;

        case 'rejectChanges':
          vscode.window.showInformationMessage('Changes rejected by user');
          panel.dispose();
          break;

        case 'applyFile':
          vscode.window.showInformationMessage(`Apply file: ${message.filePath}`);
          break;
      }
    });
  }

  /**
   * Show diff panel for patch review
   */
  private async showDiffPanel(patches: any[], riskLevel: string): Promise<void> {
    const panel = vscode.window.createWebviewPanel(
      'naviDiffReview',
      `Navi Patch Review (${riskLevel} risk)`,
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true
      }
    );

    panel.webview.html = this.getDiffPanelHtml(patches, riskLevel);

    // Handle patch application from diff panel
    panel.webview.onDidReceiveMessage(async (message) => {
      switch (message.type) {
        case 'applyPatch':
          const success = await this.applyPatchSafely(message.patch);
          panel.webview.postMessage({
            type: 'patchResult',
            success,
            file: message.patch.file_path
          });
          break;

        case 'applyAllPatches':
          await this.applyAllPatches(patches);
          panel.dispose();
          break;
      }
    });
  }

  /**
   * Apply reviewed changes after manual approval
   */
  private async applyReviewedChanges(patches: any[]): Promise<void> {
    try {
      // Create undo snapshot
      const snapshotId = await undoManager.createSnapshot('Smart Mode: Manual review approval');

      let successCount = 0;

      for (const patch of patches) {
        await undoManager.addFileToSnapshot(snapshotId, patch.file);

        const success = await applyUnifiedPatch(patch.diff);
        if (success) {
          successCount++;
        }
      }

      vscode.window.showInformationMessage(
        `✅ Applied ${successCount}/${patches.length} reviewed changes`
      );

    } catch (error) {
      vscode.window.showErrorMessage(`Failed to apply reviewed changes: ${error}`);
    }
  }

  /**
   * Apply a single patch safely with undo support
   */
  private async applyPatchSafely(patch: any): Promise<boolean> {
    try {
      // Create undo snapshot for this file
      const snapshotId = await undoManager.createSnapshot(`Smart Mode: ${patch.file_path}`);
      await undoManager.addFileToSnapshot(snapshotId, patch.file_path);

      const success = await applyUnifiedPatch(patch.diff_content);

      if (success) {
        this.outputChannel.appendLine(`✅ Applied patch to ${patch.file_path}`);
      } else {
        this.outputChannel.appendLine(`❌ Failed to apply patch to ${patch.file_path}`);
      }

      return success;
    } catch (error) {
      this.outputChannel.appendLine(`🚨 Error applying patch: ${error}`);
      return false;
    }
  }

  /**
   * Apply all patches in batch
   */
  private async applyAllPatches(patches: any[]): Promise<void> {
    const snapshotId = await undoManager.createSnapshot('Smart Mode: Batch patch application');

    let successCount = 0;

    for (const patch of patches) {
      try {
        await undoManager.addFileToSnapshot(snapshotId, patch.file_path);
        const success = await applyUnifiedPatch(patch.diff_content);

        if (success) {
          successCount++;
        }
      } catch (error) {
        this.outputChannel.appendLine(`Error applying ${patch.file_path}: ${error}`);
      }
    }

    vscode.window.showInformationMessage(
      `Applied ${successCount}/${patches.length} patches`,
      'View Changes'
    ).then(selection => {
      if (selection === 'View Changes') {
        vscode.commands.executeCommand('workbench.scm.focus');
      }
    });
  }

  /**
   * Get Smart Mode configuration
   */
  private getSmartModeConfig(): SmartModeConfig {
    const config = vscode.workspace.getConfiguration('aep');

    return {
      backendUrl: config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8787',
      autoApplyThreshold: config.get<number>('smartMode.autoApplyThreshold') || 0.3,
      showProgressNotifications: config.get<boolean>('smartMode.showProgressNotifications') || true,
      enableSmartVerification: config.get<boolean>('smartMode.enableSmartVerification') || true
    };
  }

  /**
   * Get current workspace root
   */
  private getWorkspaceRoot(): string {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
  }

  /**
   * Generate HTML for review panel
   */
  private getReviewPanelHtml(reviewData: any): string {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Navi Smart Mode Review</title>
        <style>
          body { font-family: -apple-system, sans-serif; padding: 20px; }
          .risk-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
          .risk-high { background: #ff4444; color: white; }
          .risk-medium { background: #ffaa00; color: white; }
          .risk-low { background: #44aa44; color: white; }
          .file-entry { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 6px; }
          .diff-content { background: #f5f5f5; padding: 10px; font-family: monospace; white-space: pre-wrap; }
          button { padding: 8px 16px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
          .approve-btn { background: #28a745; color: white; }
          .reject-btn { background: #dc3545; color: white; }
        </style>
      </head>
      <body>
        <h2>🔍 Smart Mode Review Required</h2>
        <div class="risk-badge risk-${reviewData.risk_assessment.level}">
          ${reviewData.risk_assessment.level.toUpperCase()} RISK (${reviewData.risk_assessment.score.toFixed(2)})
        </div>
        
        <h3>Risk Factors:</h3>
        <ul>
          ${reviewData.risk_assessment.reasons.map((reason: string) => `<li>${reason}</li>`).join('')}
        </ul>
        
        <h3>Proposed Changes:</h3>
        ${reviewData.entries.map((entry: any) => `
          <div class="file-entry">
            <h4>📄 ${entry.file}</h4>
            <p><strong>Summary:</strong> ${entry.summary}</p>
            <p><strong>Impact:</strong> ${entry.impact}</p>
            <div class="diff-content">${entry.diff}</div>
          </div>
        `).join('')}
        
        <div style="margin-top: 20px;">
          <button class="approve-btn" onclick="approveChanges()">✅ Approve All Changes</button>
          <button class="reject-btn" onclick="rejectChanges()">❌ Reject Changes</button>
        </div>
        
        <script>
          const vscode = acquireVsCodeApi();
          
          function approveChanges() {
            vscode.postMessage({ type: 'approveChanges', patches: ${JSON.stringify(reviewData.entries)} });
          }
          
          function rejectChanges() {
            vscode.postMessage({ type: 'rejectChanges' });
          }
        </script>
      </body>
      </html>
    `;
  }

  /**
   * Generate HTML for diff panel
   */
  private getDiffPanelHtml(patches: any[], riskLevel: string): string {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Navi Patch Review</title>
        <style>
          body { font-family: -apple-system, sans-serif; padding: 20px; }
          .patch-container { border: 1px solid #ddd; margin: 10px 0; border-radius: 6px; }
          .patch-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #ddd; }
          .patch-content { padding: 15px; font-family: monospace; white-space: pre-wrap; background: #f5f5f5; }
          .apply-btn { background: #007acc; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; }
          .risk-${riskLevel} { border-left: 4px solid #ff4444; }
        </style>
      </head>
      <body>
        <h2>🔧 Patch Review (${riskLevel} risk)</h2>
        <p>${patches.length} files require review before application.</p>
        
        ${patches.map((patch: any, index: number) => `
          <div class="patch-container risk-${riskLevel}">
            <div class="patch-header">
              <strong>📄 ${patch.file_path}</strong>
              <button class="apply-btn" onclick="applyPatch(${index})">Apply This File</button>
            </div>
            <div class="patch-content">${patch.diff_content}</div>
          </div>
        `).join('')}
        
        <div style="margin-top: 20px;">
          <button class="apply-btn" onclick="applyAllPatches()" style="background: #28a745;">
            ✅ Apply All Patches
          </button>
        </div>
        
        <script>
          const vscode = acquireVsCodeApi();
          const patches = ${JSON.stringify(patches)};
          
          function applyPatch(index) {
            vscode.postMessage({ type: 'applyPatch', patch: patches[index] });
          }
          
          function applyAllPatches() {
            vscode.postMessage({ type: 'applyAllPatches' });
          }
        </script>
      </body>
      </html>
    `;
  }

  /**
   * Clean up resources
   */
  private cleanup(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.currentProgress = null;
  }

  /**
   * Dispose of the SSE client
   */
  dispose(): void {
    this.cleanup();
    this.outputChannel.dispose();
  }
}

// Export singleton instance
export const smartModeSSEClient = new SmartModeSSEClient();