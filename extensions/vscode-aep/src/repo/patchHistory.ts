// extensions/vscode-aep/src/repo/patchHistory.ts
/**
 * Patch History & Rollback System
 * 
 * Enterprise-grade versioning and audit capabilities:
 * - Track all Navi patch applications
 * - Enable rollback to previous states
 * - Maintain audit logs for compliance
 * - Support diff comparison between versions
 * 
 * Part of Batch 7 — Advanced Intelligence Layer
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

interface PatchHistoryEntry {
  id: string;
  timestamp: number;
  patch: string;
  files: string[];
  description: string;
  fixId?: string;
  success: boolean;
  rollbackAvailable: boolean;
  metadata: {
    confidence?: number;
    riskLevel?: string;
    changeStats?: {
      additions: number;
      deletions: number;
      filesModified: number;
    };
  };
}

interface FileSnapshot {
  filePath: string;
  content: string;
  timestamp: number;
  patchId: string;
}

export class PatchHistoryManager {
  private history: PatchHistoryEntry[] = [];
  private snapshots: Map<string, FileSnapshot[]> = new Map();
  private maxHistorySize = 100;
  private storageUri: vscode.Uri;

  constructor(private context: vscode.ExtensionContext) {
    // Initialize storage location
    this.storageUri = vscode.Uri.joinPath(context.globalStorageUri, 'navi-patch-history');
    this.ensureStorageExists();
    this.loadHistory();
    
    // Register commands
    this.registerCommands();
  }

  /**
   * Record a new patch application
   */
  public async recordPatch(
    patch: string,
    files: string[],
    description: string,
    fixId?: string,
    metadata?: any
  ): Promise<string> {
    const patchId = this.generatePatchId();
    
    // Create snapshots of files before patch application
    await this.createFileSnapshots(files, patchId);
    
    const entry: PatchHistoryEntry = {
      id: patchId,
      timestamp: Date.now(),
      patch,
      files,
      description,
      fixId,
      success: true, // Assume success for now, update if needed
      rollbackAvailable: true,
      metadata: {
        confidence: metadata?.confidence,
        riskLevel: metadata?.riskLevel,
        changeStats: {
          additions: this.countPatchLines(patch, '+'),
          deletions: this.countPatchLines(patch, '-'),
          filesModified: files.length
        }
      }
    };

    this.history.unshift(entry);
    
    // Maintain history size limit
    if (this.history.length > this.maxHistorySize) {
      const removed = this.history.splice(this.maxHistorySize);
      // Clean up old snapshots
      removed.forEach(entry => this.cleanupSnapshots(entry.id));
    }

    await this.saveHistory();
    return patchId;
  }

  /**
   * Rollback a specific patch
   */
  public async rollbackPatch(patchId: string): Promise<boolean> {
    const entry = this.history.find(h => h.id === patchId);
    if (!entry) {
      vscode.window.showErrorMessage(`❌ Patch ${patchId} not found in history`);
      return false;
    }

    if (!entry.rollbackAvailable) {
      vscode.window.showErrorMessage(`❌ Rollback not available for patch ${patchId}`);
      return false;
    }

    try {
      // Confirm rollback with user
      const response = await vscode.window.showWarningMessage(
        `⚠️ Rollback patch "${entry.description}"?\n\nThis will restore ${entry.files.length} file(s) to their previous state.`,
        { modal: true },
        'Rollback',
        'Cancel'
      );

      if (response !== 'Rollback') {
        return false;
      }

      // Show progress
      const success = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Rolling back patch...',
          cancellable: false
        },
        async (progress) => {
          let filesRestored = 0;
          
          for (const filePath of entry.files) {
            progress.report({
              message: `Restoring ${path.basename(filePath)}...`,
              increment: (filesRestored / entry.files.length) * 100
            });

            const restored = await this.restoreFileSnapshot(filePath, patchId);
            if (restored) {
              filesRestored++;
            }
          }

          return filesRestored === entry.files.length;
        }
      );

      if (success) {
        // Record rollback in history
        await this.recordPatch(
          '', // No patch content for rollback
          entry.files,
          `Rollback: ${entry.description}`,
          undefined,
          { rollback: true, originalPatchId: patchId }
        );

        vscode.window.showInformationMessage(`✅ Successfully rolled back patch: ${entry.description}`);
        return true;
      } else {
        vscode.window.showErrorMessage(`❌ Failed to rollback patch: ${entry.description}`);
        return false;
      }

    } catch (error) {
      vscode.window.showErrorMessage(`❌ Rollback failed: ${error}`);
      return false;
    }
  }

  /**
   * Get patch history for display
   */
  public getHistory(): PatchHistoryEntry[] {
    return [...this.history];
  }

  /**
   * Show patch history in a quick pick
   */
  public async showHistoryQuickPick(): Promise<void> {
    if (this.history.length === 0) {
      vscode.window.showInformationMessage('📝 No patch history available');
      return;
    }

    const items = this.history.map(entry => ({
      label: `$(${entry.success ? 'check' : 'x'}) ${entry.description}`,
      description: `${entry.files.length} file(s) • ${new Date(entry.timestamp).toLocaleString()}`,
      detail: `Confidence: ${entry.metadata.confidence ? Math.round(entry.metadata.confidence * 100) + '%' : 'N/A'} • Risk: ${entry.metadata.riskLevel || 'Unknown'}`,
      entry
    }));

    const selected = await vscode.window.showQuickPick(items, {
      placeHolder: 'Select a patch to view details or rollback',
      matchOnDescription: true,
      matchOnDetail: true
    });

    if (selected) {
      await this.showPatchDetails(selected.entry);
    }
  }

  /**
   * Show detailed patch information with rollback option
   */
  private async showPatchDetails(entry: PatchHistoryEntry): Promise<void> {
    const actions: string[] = [];
    
    if (entry.rollbackAvailable) {
      actions.push('🔄 Rollback');
    }
    actions.push('📄 View Patch', '📊 View Changes', '❌ Cancel');

    const action = await vscode.window.showInformationMessage(
      `Patch Details: ${entry.description}`,
      ...actions
    );

    switch (action) {
      case '🔄 Rollback':
        await this.rollbackPatch(entry.id);
        break;
      case '📄 View Patch':
        await this.showPatchContent(entry);
        break;
      case '📊 View Changes':
        await this.showChangeStatistics(entry);
        break;
    }
  }

  /**
   * Create file snapshots before patch application
   */
  private async createFileSnapshots(files: string[], patchId: string): Promise<void> {
    for (const filePath of files) {
      try {
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
        const snapshot: FileSnapshot = {
          filePath,
          content: document.getText(),
          timestamp: Date.now(),
          patchId
        };

        let fileSnapshots = this.snapshots.get(filePath) || [];
        fileSnapshots.unshift(snapshot);
        
        // Keep last 10 snapshots per file
        if (fileSnapshots.length > 10) {
          fileSnapshots = fileSnapshots.slice(0, 10);
        }
        
        this.snapshots.set(filePath, fileSnapshots);
        
        // Save snapshot to disk
        await this.saveSnapshot(snapshot);
        
      } catch (error) {
        console.warn(`Failed to create snapshot for ${filePath}:`, error);
      }
    }
  }

  /**
   * Restore file from snapshot
   */
  private async restoreFileSnapshot(filePath: string, patchId: string): Promise<boolean> {
    const fileSnapshots = this.snapshots.get(filePath);
    if (!fileSnapshots) return false;

    const snapshot = fileSnapshots.find(s => s.patchId === patchId);
    if (!snapshot) return false;

    try {
      const uri = vscode.Uri.file(filePath);
      const edit = new vscode.WorkspaceEdit();
      
      // Replace entire file content
      const document = await vscode.workspace.openTextDocument(uri);
      const fullRange = new vscode.Range(
        document.positionAt(0),
        document.positionAt(document.getText().length)
      );
      
      edit.replace(uri, fullRange, snapshot.content);
      
      const success = await vscode.workspace.applyEdit(edit);
      if (success) {
        await document.save();
      }
      
      return success;
    } catch (error) {
      console.error(`Failed to restore snapshot for ${filePath}:`, error);
      return false;
    }
  }

  /**
   * Generate unique patch ID
   */
  private generatePatchId(): string {
    return `patch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Count lines in patch by type
   */
  private countPatchLines(patch: string, prefix: string): number {
    return patch.split('\n').filter(line => line.startsWith(prefix)).length;
  }

  /**
   * Show patch content in editor
   */
  private async showPatchContent(entry: PatchHistoryEntry): Promise<void> {
    const document = await vscode.workspace.openTextDocument({
      content: entry.patch,
      language: 'diff'
    });
    
    await vscode.window.showTextDocument(document, {
      viewColumn: vscode.ViewColumn.Beside,
      preview: true
    });
  }

  /**
   * Show change statistics
   */
  private async showChangeStatistics(entry: PatchHistoryEntry): Promise<void> {
    const stats = entry.metadata.changeStats;
    if (!stats) return;

    const message = `
📊 Change Statistics

Files Modified: ${stats.filesModified}
Lines Added: ${stats.additions}
Lines Removed: ${stats.deletions}
Net Change: ${stats.additions - stats.deletions}

Confidence: ${entry.metadata.confidence ? Math.round(entry.metadata.confidence * 100) + '%' : 'N/A'}
Risk Level: ${entry.metadata.riskLevel || 'Unknown'}

Applied: ${new Date(entry.timestamp).toLocaleString()}
    `.trim();

    vscode.window.showInformationMessage(message);
  }

  /**
   * Storage management
   */
  private async ensureStorageExists(): Promise<void> {
    try {
      await vscode.workspace.fs.createDirectory(this.storageUri);
    } catch (error) {
      // Directory might already exist
    }
  }

  private async saveHistory(): Promise<void> {
    try {
      const historyUri = vscode.Uri.joinPath(this.storageUri, 'history.json');
      const content = Buffer.from(JSON.stringify(this.history, null, 2), 'utf8');
      await vscode.workspace.fs.writeFile(historyUri, content);
    } catch (error) {
      console.error('Failed to save patch history:', error);
    }
  }

  private async loadHistory(): Promise<void> {
    try {
      const historyUri = vscode.Uri.joinPath(this.storageUri, 'history.json');
      const content = await vscode.workspace.fs.readFile(historyUri);
      this.history = JSON.parse(content.toString());
    } catch (error) {
      // File might not exist yet
      this.history = [];
    }
  }

  private async saveSnapshot(snapshot: FileSnapshot): Promise<void> {
    try {
      const fileName = `${snapshot.patchId}_${path.basename(snapshot.filePath)}.snapshot`;
      const snapshotUri = vscode.Uri.joinPath(this.storageUri, 'snapshots', fileName);
      
      // Ensure snapshots directory exists
      await vscode.workspace.fs.createDirectory(vscode.Uri.joinPath(this.storageUri, 'snapshots'));
      
      const content = Buffer.from(JSON.stringify(snapshot, null, 2), 'utf8');
      await vscode.workspace.fs.writeFile(snapshotUri, content);
    } catch (error) {
      console.error('Failed to save snapshot:', error);
    }
  }

  private cleanupSnapshots(patchId: string): void {
    // Remove snapshots for the given patch ID
    this.snapshots.forEach((snapshots, filePath) => {
      const filtered = snapshots.filter(s => s.patchId !== patchId);
      if (filtered.length !== snapshots.length) {
        this.snapshots.set(filePath, filtered);
      }
    });
  }

  /**
   * Register VS Code commands
   */
  private registerCommands(): void {
    this.context.subscriptions.push(
      vscode.commands.registerCommand('aep.showPatchHistory', () => {
        this.showHistoryQuickPick();
      }),

      vscode.commands.registerCommand('aep.rollbackLastPatch', () => {
        if (this.history.length > 0) {
          this.rollbackPatch(this.history[0].id);
        } else {
          vscode.window.showInformationMessage('📝 No patches to rollback');
        }
      })
    );
  }
}