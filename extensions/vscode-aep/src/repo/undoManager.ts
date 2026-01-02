import * as vscode from 'vscode';

export interface UndoEntry {
  file: string;
  originalContent: string;
  timestamp: number;
  description?: string;
}

export interface UndoSnapshot {
  id: string;
  entries: UndoEntry[];
  timestamp: number;
  description: string;
}

/**
 * Manages undo history for patch applications
 * Supports both individual file undo and batch operation undo
 */
export class UndoManager {
  private snapshots: UndoSnapshot[] = [];
  private maxHistorySize = 50;
  private outputChannel = vscode.window.createOutputChannel('Navi Undo Manager');

  /**
   * Create a new undo snapshot before applying patches
   */
  async createSnapshot(description: string): Promise<string> {
    const id = `undo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const snapshot: UndoSnapshot = {
      id,
      entries: [],
      timestamp: Date.now(),
      description
    };

    this.snapshots.push(snapshot);
    
    // Cleanup old snapshots
    if (this.snapshots.length > this.maxHistorySize) {
      this.snapshots.shift();
    }

    this.outputChannel.appendLine(`📸 Created undo snapshot: ${id} - ${description}`);
    return id;
  }

  /**
   * Add a file to the current snapshot
   */
  async addFileToSnapshot(snapshotId: string, filePath: string, description?: string): Promise<boolean> {
    try {
      const snapshot = this.snapshots.find(s => s.id === snapshotId);
      if (!snapshot) {
        this.outputChannel.appendLine(`❌ Snapshot not found: ${snapshotId}`);
        return false;
      }

      // Read current file content
      let originalContent = '';
      try {
        const uri = vscode.Uri.file(filePath);
        const buffer = await vscode.workspace.fs.readFile(uri);
        originalContent = Buffer.from(buffer).toString('utf8');
      } catch (error) {
        // File doesn't exist - store empty content
        originalContent = '';
      }

      // Add entry to snapshot
      const entry: UndoEntry = {
        file: filePath,
        originalContent,
        timestamp: Date.now(),
        description
      };

      snapshot.entries.push(entry);
      this.outputChannel.appendLine(`📝 Added to snapshot ${snapshotId}: ${filePath}`);
      return true;
    } catch (error) {
      this.outputChannel.appendLine(`🚨 Error adding file to snapshot: ${error}`);
      return false;
    }
  }

  /**
   * Undo a specific snapshot
   */
  async undoSnapshot(snapshotId: string): Promise<boolean> {
    try {
      const snapshot = this.snapshots.find(s => s.id === snapshotId);
      if (!snapshot) {
        vscode.window.showErrorMessage(`Undo snapshot not found: ${snapshotId}`);
        return false;
      }

      let successCount = 0;
      const errors: string[] = [];

      // Process each file in the snapshot
      for (const entry of snapshot.entries) {
        try {
          const success = await this.restoreFile(entry);
          if (success) {
            successCount++;
          } else {
            errors.push(entry.file);
          }
        } catch (error) {
          errors.push(`${entry.file}: ${error}`);
        }
      }

      // Remove the snapshot after successful undo
      if (successCount === snapshot.entries.length) {
        this.removeSnapshot(snapshotId);
        vscode.window.showInformationMessage(
          `✅ Undid ${successCount} changes: ${snapshot.description}`
        );
        return true;
      } else {
        vscode.window.showWarningMessage(
          `⚠️ Partial undo: ${successCount}/${snapshot.entries.length} files restored. Errors: ${errors.join(', ')}`
        );
        return false;
      }
    } catch (error) {
      this.outputChannel.appendLine(`🚨 Error during undo: ${error}`);
      vscode.window.showErrorMessage(`Failed to undo: ${error}`);
      return false;
    }
  }

  /**
   * Undo the most recent snapshot
   */
  async undoLast(): Promise<boolean> {
    if (this.snapshots.length === 0) {
      vscode.window.showWarningMessage('Nothing to undo');
      return false;
    }

    const lastSnapshot = this.snapshots[this.snapshots.length - 1];
    return await this.undoSnapshot(lastSnapshot.id);
  }

  /**
   * Undo a specific file from the most recent snapshot
   */
  async undoFile(filePath: string): Promise<boolean> {
    // Find the most recent snapshot containing this file
    for (let i = this.snapshots.length - 1; i >= 0; i--) {
      const snapshot = this.snapshots[i];
      const entry = snapshot.entries.find(e => e.file === filePath);
      
      if (entry) {
        const success = await this.restoreFile(entry);
        if (success) {
          // Remove the entry from the snapshot
          snapshot.entries = snapshot.entries.filter(e => e.file !== filePath);
          
          // Remove snapshot if it's empty
          if (snapshot.entries.length === 0) {
            this.removeSnapshot(snapshot.id);
          }
          
          vscode.window.showInformationMessage(`Undid changes to ${vscode.Uri.file(filePath).fsPath}`);
          return true;
        }
        return false;
      }
    }

    vscode.window.showWarningMessage(`No undo history found for ${vscode.Uri.file(filePath).fsPath}`);
    return false;
  }

  /**
   * Restore a file from an undo entry
   */
  private async restoreFile(entry: UndoEntry): Promise<boolean> {
    try {
      const uri = vscode.Uri.file(entry.file);
      const edit = new vscode.WorkspaceEdit();

      if (entry.originalContent) {
        // Restore original content
        try {
          const document = await vscode.workspace.openTextDocument(uri);
          const fullRange = new vscode.Range(0, 0, document.lineCount, 0);
          edit.replace(uri, fullRange, entry.originalContent);
        } catch (error) {
          // File might not exist, create it
          edit.createFile(uri, { ignoreIfExists: true });
          edit.insert(uri, new vscode.Position(0, 0), entry.originalContent);
        }
      } else {
        // Original was empty/non-existent, delete the file
        edit.deleteFile(uri, { ignoreIfNotExists: true });
      }

      const success = await vscode.workspace.applyEdit(edit);
      
      if (success) {
        this.outputChannel.appendLine(`↩️ Restored: ${entry.file}`);
      } else {
        this.outputChannel.appendLine(`❌ Failed to restore: ${entry.file}`);
      }

      return success;
    } catch (error) {
      this.outputChannel.appendLine(`🚨 Error restoring file ${entry.file}: ${error}`);
      return false;
    }
  }

  /**
   * Remove a snapshot from history
   */
  private removeSnapshot(snapshotId: string): void {
    this.snapshots = this.snapshots.filter(s => s.id !== snapshotId);
    this.outputChannel.appendLine(`🗑️ Removed snapshot: ${snapshotId}`);
  }

  /**
   * Get all available undo snapshots
   */
  getUndoHistory(): UndoSnapshot[] {
    return [...this.snapshots].reverse(); // Most recent first
  }

  /**
   * Check if there are any undo operations available
   */
  hasUndo(): boolean {
    return this.snapshots.length > 0;
  }

  /**
   * Check if a specific file has undo history
   */
  hasUndoForFile(filePath: string): boolean {
    return this.snapshots.some(snapshot =>
      snapshot.entries.some(entry => entry.file === filePath)
    );
  }

  /**
   * Clear all undo history
   */
  clearHistory(): void {
    this.snapshots = [];
    this.outputChannel.appendLine('🧹 Cleared all undo history');
    vscode.window.showInformationMessage('Undo history cleared');
  }

  /**
   * Get summary of undo history
   */
  getHistorySummary(): { total: number; files: number; oldestTimestamp: number } {
    if (this.snapshots.length === 0) {
      return { total: 0, files: 0, oldestTimestamp: 0 };
    }

    const allFiles = new Set<string>();
    let oldestTimestamp = Date.now();

    for (const snapshot of this.snapshots) {
      if (snapshot.timestamp < oldestTimestamp) {
        oldestTimestamp = snapshot.timestamp;
      }
      for (const entry of snapshot.entries) {
        allFiles.add(entry.file);
      }
    }

    return {
      total: this.snapshots.length,
      files: allFiles.size,
      oldestTimestamp
    };
  }
}

export const undoManager = new UndoManager();