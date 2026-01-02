/**
 * Repo Actions - Trigger autonomous refactoring with live SSE streaming
 * 
 * Coordinates between VS Code extension, backend SSE endpoint, and webview
 * to provide real-time refactor progress and diff streaming.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { SSEClient } from '../sse/sseClient';
import { applyUnifiedPatch } from './applyPatch';
import { undoManager } from './undoManager';

export interface RefactorRequest {
  instruction: string;
  project_root: string;
  target_files?: string[];
  language?: string;
  dry_run?: boolean;
  options?: Record<string, any>;
}

export interface RefactorProgress {
  stage: 'planning' | 'transforming' | 'generating' | 'applying' | 'complete';
  progress: number;
  message: string;
  details?: Record<string, any>;
}

export class RefactorManager {
  private sseClient: SSEClient;
  private webviewPanel?: vscode.WebviewPanel;
  private currentRefactor?: {
    id: string;
    request: RefactorRequest;
    startTime: number;
  };

  constructor() {
    this.sseClient = new SSEClient({
      maxRetries: 3,
      retryDelay: 2000,
      heartbeatInterval: 30000,
      timeout: 300000 // 5 minutes for long refactors
    });

    this.setupSSEEventHandlers();
  }

  /**
   * Start autonomous refactor with live streaming
   */
  async startRefactor(
    instruction: string, 
    webviewPanel: vscode.WebviewPanel,
    options: Partial<RefactorRequest> = {}
  ): Promise<void> {
    try {
      this.webviewPanel = webviewPanel;
      
      // Get workspace root
      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspaceRoot) {
        throw new Error('No workspace folder found');
      }

      // Get backend URL from configuration
      const config = vscode.workspace.getConfiguration('aep');
      const backendUrl = config.get<string>('navi.backendUrl');
      if (!backendUrl) {
        throw new Error('Backend URL not configured');
      }

      // Prepare refactor request
      const request: RefactorRequest = {
        instruction,
        project_root: workspaceRoot,
        target_files: options.target_files,
        language: options.language || 'auto',
        dry_run: options.dry_run || false,
        options: options.options || {}
      };

      // Generate unique refactor ID
      const refactorId = `refactor_${Date.now()}`;
      this.currentRefactor = {
        id: refactorId,
        request,
        startTime: Date.now()
      };

      // Show initial progress
      vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'Navi Refactor',
        cancellable: true
      }, async (progress, token) => {
        progress.report({ message: 'Starting autonomous refactor...' });

        // Start SSE streaming
        const streamUrl = `${backendUrl.replace('/api/navi/chat', '')}/api/refactor/stream`;
        
        await this.sseClient.start(streamUrl, (type, data) => {
          this.handleSSEEvent(type, data, progress);
        });

        // Send POST request to trigger refactor
        const response = await fetch(streamUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(request)
        });

        if (!response.ok) {
          throw new Error(`Refactor failed: ${response.statusText}`);
        }

        // Handle cancellation
        token.onCancellationRequested(() => {
          this.cancelRefactor();
        });

        // Keep progress open until refactor completes
        return new Promise<void>((resolve, reject) => {
          this.sseClient.start(streamUrl, (type, data) => {
            if (type === 'done') {
              resolve();
            } else if (type === 'error') {
              reject(new Error(data.message || 'Refactor failed'));
            }
          });
        });
      });

    } catch (error) {
      console.error('[RefactorManager] Error starting refactor:', error);
      vscode.window.showErrorMessage(`Refactor failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      
      // Send error to webview
      this.postToWebview({
        type: 'refactorError',
        data: {
          error: error instanceof Error ? error.message : 'Unknown error',
          refactorId: this.currentRefactor?.id
        }
      });
    }
  }

  /**
   * Cancel current refactor
   */
  cancelRefactor(): void {
    if (this.currentRefactor) {
      console.log(`[RefactorManager] Cancelling refactor: ${this.currentRefactor.id}`);
      
      this.sseClient.stop();
      
      this.postToWebview({
        type: 'refactorCancelled',
        data: {
          refactorId: this.currentRefactor.id,
          reason: 'User cancelled'
        }
      });

      this.currentRefactor = undefined;
    }
  }

  /**
   * Setup SSE event handlers for all refactor events
   */
  private setupSSEEventHandlers(): void {
    // Live progress updates
    this.sseClient.start = async (url: string, onEvent: (type: string, data: any) => void) => {
      return new Promise((resolve, reject) => {
        // This method will be overridden when we actually start streaming
        onEvent('connected', { url });
        resolve();
      });
    };
  }

  /**
   * Handle individual SSE events and route to webview
   */
  private handleSSEEvent(
    type: string, 
    data: any, 
    progress?: vscode.Progress<{ message?: string; increment?: number }>
  ): void {
    console.log(`[RefactorManager] SSE Event: ${type}`, data);

    // Update VS Code progress notification
    if (progress) {
      switch (type) {
        case 'liveProgress':
          progress.report({ 
            message: data.message,
            increment: data.progress ? (data.progress * 100) : undefined
          });
          break;
        
        case 'refactorPlan':
          progress.report({ message: `📋 Plan created: ${data.estimated_changes} changes` });
          break;
          
        case 'fileStart':
          progress.report({ message: `🔧 Processing ${data.file}...` });
          break;
          
        case 'diffChunk':
          progress.report({ message: `📊 Generated diff for ${data.file}` });
          break;
          
        case 'patchBundle':
          progress.report({ message: `📦 Patch ready: ${data.files?.length || 0} files` });
          break;
          
        case 'done':
          progress.report({ message: '✅ Refactor completed!' });
          break;
          
        case 'error':
          progress.report({ message: `❌ Error: ${data.message}` });
          break;
      }
    }

    // Forward all events to webview
    this.postToWebview({
      type: `sse_${type}`,
      data: {
        ...data,
        refactorId: this.currentRefactor?.id,
        timestamp: new Date().toISOString()
      }
    });

    // Handle completion
    if (type === 'done') {
      this.handleRefactorComplete(data);
    } else if (type === 'error') {
      this.handleRefactorError(data);
    }
  }

  /**
   * Handle refactor completion
   */
  private handleRefactorComplete(data: any): void {
    if (!this.currentRefactor) return;

    const executionTime = Date.now() - this.currentRefactor.startTime;
    
    vscode.window.showInformationMessage(
      `🎉 Refactor completed in ${Math.round(executionTime / 1000)}s`,
      'View Changes',
      'Apply Patches'
    ).then(selection => {
      if (selection === 'View Changes') {
        vscode.commands.executeCommand('aep.showDiffs');
      } else if (selection === 'Apply Patches') {
        vscode.commands.executeCommand('aep.applyPatches');
      }
    });

    this.currentRefactor = undefined;
  }

  /**
   * Handle refactor error
   */
  private handleRefactorError(data: any): void {
    if (!this.currentRefactor) return;

    console.error('[RefactorManager] Refactor error:', data);
    
    vscode.window.showErrorMessage(
      `Refactor failed: ${data.message || 'Unknown error'}`,
      'Retry',
      'View Logs'
    ).then(selection => {
      if (selection === 'Retry' && this.currentRefactor) {
        this.startRefactor(
          this.currentRefactor.request.instruction,
          this.webviewPanel!,
          this.currentRefactor.request
        );
      } else if (selection === 'View Logs') {
        vscode.commands.executeCommand('aep.showLogs');
      }
    });

    this.currentRefactor = undefined;
  }

  /**
   * Send message to webview panel
   */
  private postToWebview(message: any): void {
    if (this.webviewPanel) {
      this.webviewPanel.webview.postMessage(message);
    }
  }

  /**
   * Get current refactor status
   */
  getCurrentRefactor() {
    return this.currentRefactor;
  }

  /**
   * Cleanup resources
   */
  dispose(): void {
    this.sseClient.stop();
    this.currentRefactor = undefined;
  }
}

// Global refactor manager instance
let globalRefactorManager: RefactorManager | null = null;

export function getRefactorManager(): RefactorManager {
  if (!globalRefactorManager) {
    globalRefactorManager = new RefactorManager();
  }
  return globalRefactorManager;
}

/**
 * Quick action to start refactor from command palette
 */
export async function runQuickRefactor(): Promise<void> {
  const instruction = await vscode.window.showInputBox({
    prompt: 'Enter refactor instruction',
    placeHolder: 'e.g., "Extract the auth logic into a separate service"',
    validateInput: (value) => {
      return value.trim().length < 10 ? 'Instruction should be more descriptive' : null;
    }
  });

  if (instruction) {
    // Get or create webview panel
    const panel = vscode.window.createWebviewPanel(
      'naviRefactor',
      'Navi Refactor',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        localResourceRoots: []
      }
    );

    const refactorManager = getRefactorManager();
    await refactorManager.startRefactor(instruction, panel);
  }
}

/**
 * Refactor selected files
 */
export async function refactorSelectedFiles(files: vscode.Uri[]): Promise<void> {
  const instruction = await vscode.window.showInputBox({
    prompt: 'What would you like to refactor in the selected files?',
      placeHolder: 'e.g., "Rename all instances of User to Customer"'
  });

  if (instruction) {
    const panel = vscode.window.createWebviewPanel(
      'naviRefactor',
      'Navi Refactor - Selected Files',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        localResourceRoots: []
      }
    );

    const refactorManager = getRefactorManager();
    await refactorManager.startRefactor(instruction, panel, {
      target_files: files.map(f => f.fsPath)
    });
  }
}

/**
 * Apply patch bundle from webview
 */
export async function applyPatchFromWebview(patchBundle: any): Promise<boolean> {
  try {
    // Create undo snapshot before applying patches
    const snapshotId = await undoManager.createSnapshot(
      `Patch application: ${patchBundle.description || 'Autonomous refactor'}`
    );

    let successCount = 0;
    const errors: string[] = [];

    // Process each file in the patch bundle
    for (const patchFile of patchBundle.files) {
      try {
        // Add file to undo snapshot
        await undoManager.addFileToSnapshot(snapshotId, patchFile.path);

        // Apply the patch
        let success = false;
        if (patchFile.modified) {
          // Apply full file content replacement
          success = await applyFileContent(patchFile.path, patchFile.modified);
        } else if (patchFile.diff) {
          // Apply unified diff patch
          success = await applyUnifiedPatch(patchFile.diff);
        }

        if (success) {
          successCount++;
        } else {
          errors.push(patchFile.path);
        }
      } catch (error) {
        console.error(`Error applying patch to ${patchFile.path}:`, error);
        errors.push(`${patchFile.path}: ${error}`);
      }
    }

    // Show results
    if (errors.length === 0) {
      vscode.window.showInformationMessage(
        `✅ Applied patches to ${successCount} files`,
        'View Changes'
      ).then(selection => {
        if (selection === 'View Changes') {
          vscode.commands.executeCommand('workbench.scm.focus');
        }
      });
      return true;
    } else {
      vscode.window.showWarningMessage(
        `⚠️ Applied ${successCount}/${patchBundle.files.length} patches. Errors: ${errors.slice(0, 3).join(', ')}${errors.length > 3 ? '...' : ''}`,
        'View Errors', 'Undo Changes'
      ).then(selection => {
        if (selection === 'Undo Changes') {
          undoManager.undoSnapshot(snapshotId);
        } else if (selection === 'View Errors') {
          vscode.window.showErrorMessage(`Patch errors:\n${errors.join('\n')}`);
        }
      });
      return false;
    }
  } catch (error) {
    console.error('Error applying patch bundle:', error);
    vscode.window.showErrorMessage(`Failed to apply patches: ${error}`);
    return false;
  }
}

/**
 * Apply file content replacement
 */
export async function applyFileContent(filePath: string, newContent: string): Promise<boolean> {
  try {
    const uri = vscode.Uri.file(filePath);
    const edit = new vscode.WorkspaceEdit();

    // Check if file exists
    try {
      const document = await vscode.workspace.openTextDocument(uri);
      // Replace entire file content
      const fullRange = new vscode.Range(0, 0, document.lineCount, 0);
      edit.replace(uri, fullRange, newContent);
    } catch (error) {
      // File doesn't exist, create it
      edit.createFile(uri, { ignoreIfExists: true });
      edit.insert(uri, new vscode.Position(0, 0), newContent);
    }

    const success = await vscode.workspace.applyEdit(edit);
    
    if (success) {
      // Open the file to show changes
      const document = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(document, { preview: false });
    }

    return success;
  } catch (error) {
    console.error(`Error applying file content to ${filePath}:`, error);
    return false;
  }
}

/**
 * Apply patch to a single file from webview
 */
export async function applyFilePatch(filePath: string, patchContent: string): Promise<boolean> {
  try {
    // Create undo snapshot for this file
    const snapshotId = await undoManager.createSnapshot(`File patch: ${path.basename(filePath)}`);
    await undoManager.addFileToSnapshot(snapshotId, filePath);

    // Apply the patch
    const success = await applyUnifiedPatch(patchContent);
    
    if (success) {
      vscode.window.showInformationMessage(
        `✅ Applied patch to ${path.basename(filePath)}`,
        'View File'
      ).then(selection => {
        if (selection === 'View File') {
          vscode.workspace.openTextDocument(filePath).then(doc => {
            vscode.window.showTextDocument(doc);
          });
        }
      });
    } else {
      vscode.window.showErrorMessage(
        `Failed to apply patch to ${path.basename(filePath)}`,
        'Undo'
      ).then(selection => {
        if (selection === 'Undo') {
          undoManager.undoSnapshot(snapshotId);
        }
      });
    }

    return success;
  } catch (error) {
    console.error(`Error applying file patch to ${filePath}:`, error);
    vscode.window.showErrorMessage(`Failed to apply patch: ${error}`);
    return false;
  }
}

/**
 * Undo last patch operation
 */
export async function undoLastPatch(): Promise<boolean> {
  try {
    if (!undoManager.hasUndo()) {
      vscode.window.showWarningMessage('Nothing to undo');
      return false;
    }

    const success = await undoManager.undoLast();
    
    if (success) {
      vscode.window.showInformationMessage('✅ Undid last patch operation');
    }
    
    return success;
  } catch (error) {
    console.error('Error undoing last patch:', error);
    vscode.window.showErrorMessage(`Failed to undo: ${error}`);
    return false;
  }
}

/**
 * Undo patch for a specific file
 */
export async function undoFilePatch(filePath: string): Promise<boolean> {
  try {
    const success = await undoManager.undoFile(filePath);
    
    if (!success && !undoManager.hasUndoForFile(filePath)) {
      vscode.window.showWarningMessage(`No undo history for ${path.basename(filePath)}`);
    }
    
    return success;
  } catch (error) {
    console.error(`Error undoing file patch for ${filePath}:`, error);
    vscode.window.showErrorMessage(`Failed to undo changes: ${error}`);
    return false;
  }
}

/**
 * Show undo history picker
 */
export async function showUndoHistory(): Promise<void> {
  const history = undoManager.getUndoHistory();
  
  if (history.length === 0) {
    vscode.window.showInformationMessage('No undo history available');
    return;
  }

  const items = history.map(snapshot => ({
    label: snapshot.description,
    description: `${snapshot.entries.length} files`,
    detail: new Date(snapshot.timestamp).toLocaleString(),
    snapshot
  }));

  const selected = await vscode.window.showQuickPick(items, {
    placeHolder: 'Select operation to undo',
    matchOnDescription: true,
    matchOnDetail: true
  });

  if (selected) {
    await undoManager.undoSnapshot(selected.snapshot.id);
  }
}