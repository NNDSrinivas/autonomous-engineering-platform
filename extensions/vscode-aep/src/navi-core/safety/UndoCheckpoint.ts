/**
 * Phase 3.2 - Undo Checkpoint System
 * 
 * Creates restoration points before executing actions, enabling rollback.
 * Critical for maintaining user trust - every action must be undoable.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { ActionIntent } from './ActionIntent';

export interface Checkpoint {
  id: string;
  timestamp: Date;
  description: string;
  actionIntent: ActionIntent;
  
  // File states before the action
  fileSnapshots: Map<string, string | null>; // null = file didn't exist
  
  // Directory states (for created/deleted directories)
  directorySnapshots: Map<string, boolean>; // true = existed, false = didn't exist
  
  // Git state (if in git repo)
  gitState?: {
    branch: string;
    commitHash: string;
    workingTreeClean: boolean;
  };
  
  // Metadata for restoration
  workspaceState: {
    activeDocument?: string;
    visibleEditors: string[];
  };
}

export class UndoCheckpoint {
  private checkpoints: Map<string, Checkpoint> = new Map();
  private maxCheckpoints = 20; // Keep last 20 checkpoints
  
  /**
   * Create a checkpoint before executing an action
   */
  async createCheckpoint(intent: ActionIntent): Promise<string> {
    const checkpointId = this.generateId();
    const timestamp = new Date();
    
    try {
      // Capture current file states
      const fileSnapshots = new Map<string, string | null>();
      for (const filePath of intent.filesAffected) {
        try {
          if (fs.existsSync(filePath)) {
            const content = fs.readFileSync(filePath, 'utf8');
            fileSnapshots.set(filePath, content);
          } else {
            fileSnapshots.set(filePath, null);
          }
        } catch (error) {
          console.warn(`Failed to snapshot file ${filePath}:`, error);
          fileSnapshots.set(filePath, null);
        }
      }
      
      // Capture directory states (for file creation/deletion)
      const directorySnapshots = new Map<string, boolean>();
      const directories = new Set<string>();
      
      // Get all parent directories of affected files
      intent.filesAffected.forEach(filePath => {
        let dir = path.dirname(filePath);
        while (dir !== path.dirname(dir)) { // Until we reach root
          directories.add(dir);
          dir = path.dirname(dir);
        }
      });
      
      directories.forEach(dir => {
        directorySnapshots.set(dir, fs.existsSync(dir));
      });
      
      // Capture workspace state
      const workspaceState = {
        activeDocument: vscode.window.activeTextEditor?.document.uri.fsPath,
        visibleEditors: vscode.window.visibleTextEditors.map(editor => 
          editor.document.uri.fsPath
        )
      };
      
      // Capture git state if available
      const gitState = await this.captureGitState();
      
      const checkpoint: Checkpoint = {
        id: checkpointId,
        timestamp,
        description: `Before ${intent.type}: ${intent.description}`,
        actionIntent: intent,
        fileSnapshots,
        directorySnapshots,
        gitState,
        workspaceState
      };
      
      this.checkpoints.set(checkpointId, checkpoint);
      
      // Cleanup old checkpoints
      this.cleanupOldCheckpoints();
      
      console.log(`Created checkpoint ${checkpointId} for action: ${intent.description}`);
      return checkpointId;
      
    } catch (error) {
      console.error('Failed to create checkpoint:', error);
      throw new Error(`Checkpoint creation failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  
  /**
   * Restore from a checkpoint (undo the action)
   */
  async restoreCheckpoint(checkpointId: string): Promise<boolean> {
    const checkpoint = this.checkpoints.get(checkpointId);
    if (!checkpoint) {
      throw new Error(`Checkpoint ${checkpointId} not found`);
    }
    
    try {
      console.log(`Restoring checkpoint ${checkpointId}: ${checkpoint.description}`);
      
      // Close any editors that might interfere with file operations
      await vscode.commands.executeCommand('workbench.action.closeAllEditors');
      
      // Restore files
      for (const [filePath, originalContent] of checkpoint.fileSnapshots) {
        if (originalContent === null) {
          // File didn't exist originally, so delete it if it exists now
          if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
            console.log(`Deleted file: ${filePath}`);
          }
        } else {
          // File existed, restore its content
          const dir = path.dirname(filePath);
          if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
          }
          fs.writeFileSync(filePath, originalContent, 'utf8');
          console.log(`Restored file: ${filePath}`);
        }
      }
      
      // Restore directories (delete ones that didn't exist)
      for (const [dirPath, existed] of checkpoint.directorySnapshots) {
        if (!existed && fs.existsSync(dirPath)) {
          // Directory didn't exist originally but exists now - check if it's empty
          try {
            const entries = fs.readdirSync(dirPath);
            if (entries.length === 0) {
              fs.rmdirSync(dirPath);
              console.log(`Removed empty directory: ${dirPath}`);
            }
          } catch (error) {
            console.warn(`Could not remove directory ${dirPath}:`, error);
          }
        }
      }
      
      // Restore workspace state
      if (checkpoint.workspaceState.activeDocument) {
        try {
          const doc = await vscode.workspace.openTextDocument(
            checkpoint.workspaceState.activeDocument
          );
          await vscode.window.showTextDocument(doc);
        } catch (error) {
          console.warn('Could not restore active document:', error);
        }
      }
      
      // Show success message
      vscode.window.showInformationMessage(
        `✅ Undid: ${checkpoint.actionIntent.description}`,
        { modal: false }
      );
      
      return true;
      
    } catch (error) {
      console.error('Failed to restore checkpoint:', error);
      vscode.window.showErrorMessage(
        `❌ Failed to undo: ${error instanceof Error ? error.message : String(error)}`
      );
      return false;
    }
  }
  
  /**
   * Get list of available checkpoints
   */
  getCheckpoints(): Checkpoint[] {
    return Array.from(this.checkpoints.values())
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  }
  
  /**
   * Get specific checkpoint
   */
  getCheckpoint(id: string): Checkpoint | undefined {
    return this.checkpoints.get(id);
  }
  
  /**
   * Remove a checkpoint (after successful verification or user request)
   */
  removeCheckpoint(id: string): boolean {
    return this.checkpoints.delete(id);
  }
  
  /**
   * Clear all checkpoints (nuclear option)
   */
  clearAll(): void {
    this.checkpoints.clear();
  }
  
  /**
   * Get checkpoint summary for UI
   */
  getCheckpointSummary(id: string): string | undefined {
    const checkpoint = this.checkpoints.get(id);
    if (!checkpoint) {
      return undefined;
    }
    
    const fileCount = checkpoint.fileSnapshots.size;
    const timeAgo = this.formatTimeAgo(checkpoint.timestamp);
    
    return `${checkpoint.actionIntent.type} (${fileCount} files affected, ${timeAgo})`;
  }
  
  // Private helper methods
  
  private generateId(): string {
    return `checkpoint_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  private async captureGitState(): Promise<Checkpoint['gitState'] | undefined> {
    try {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return undefined;
      }
      
      // Check if this is a git repository
      const gitDir = path.join(workspaceFolder.uri.fsPath, '.git');
      if (!fs.existsSync(gitDir)) {
        return undefined;
      }
      
      // For now, we'll skip git integration to avoid complexity
      // In a full implementation, we'd use git commands to capture state
      return undefined;
      
    } catch (error) {
      console.warn('Failed to capture git state:', error);
      return undefined;
    }
  }
  
  private cleanupOldCheckpoints(): void {
    if (this.checkpoints.size <= this.maxCheckpoints) {
      return;
    }
    
    // Sort by timestamp and keep only the most recent
    const sorted = Array.from(this.checkpoints.entries())
      .sort(([, a], [, b]) => b.timestamp.getTime() - a.timestamp.getTime());
    
    // Remove oldest checkpoints
    for (let i = this.maxCheckpoints; i < sorted.length; i++) {
      this.checkpoints.delete(sorted[i][0]);
    }
  }
  
  private formatTimeAgo(timestamp: Date): string {
    const now = new Date();
    const diffMs = now.getTime() - timestamp.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    
    if (diffMinutes < 1) {
      return 'just now';
    } else if (diffMinutes === 1) {
      return '1 minute ago';
    } else if (diffMinutes < 60) {
      return `${diffMinutes} minutes ago`;
    } else {
      const diffHours = Math.floor(diffMinutes / 60);
      return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
    }
  }
}