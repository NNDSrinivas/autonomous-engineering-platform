/**
 * Phase 3.3 - Patch Assembler
 * 
 * Converts synthesized patches into VS Code WorkspaceEdit operations for atomic application.
 * This is the final step that bridges NAVI's structured generation with VS Code's editing API.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { Patch, AppliedEdit } from '../generation/CodeSynthesizer';

export interface AssembledEdit {
  workspaceEdit: vscode.WorkspaceEdit;
  summary: EditSummary;
  preview: string[];
}

export interface EditSummary {
  totalFiles: number;
  filesCreated: number;
  filesModified: number;
  filesDeleted: number;
  filesMoved: number;
  totalChanges: number;
  estimatedImpact: 'low' | 'medium' | 'high';
}

export class PatchAssembler {
  /**
   * Assemble patches into a VS Code WorkspaceEdit for atomic application
   */
  assemble(patches: Patch[]): AssembledEdit {
    console.log(`🔧 Assembling ${patches.length} patches into WorkspaceEdit`);
    
    const workspaceEdit = new vscode.WorkspaceEdit();
    const preview: string[] = [];
    const summary = this.calculateSummary(patches);
    
    // Process patches in dependency order (creates first, then modifies, then deletes)
    const sortedPatches = this.sortPatchesByDependency(patches);
    
    for (const patch of sortedPatches) {
      try {
        this.assemblePatch(patch, workspaceEdit, preview);
      } catch (error) {
        console.error(`Failed to assemble patch for ${patch.filePath}:`, error);
        throw new Error(`Patch assembly failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    
    console.log(`✅ Assembled ${summary.totalChanges} changes across ${summary.totalFiles} files`);
    
    return {
      workspaceEdit,
      summary,
      preview
    };
  }
  
  /**
   * Assemble a single patch into the WorkspaceEdit
   */
  private assemblePatch(
    patch: Patch,
    workspaceEdit: vscode.WorkspaceEdit,
    preview: string[]
  ): void {
    const uri = vscode.Uri.file(patch.filePath);
    
    switch (patch.operation) {
      case 'create':
        this.assembleFileCreation(patch, workspaceEdit, preview);
        break;
      
      case 'modify':
        this.assembleFileModification(patch, workspaceEdit, preview);
        break;
      
      case 'delete':
        this.assembleFileDeletion(patch, workspaceEdit, preview);
        break;
      
      case 'move':
        this.assembleFileMove(patch, workspaceEdit, preview);
        break;
      
      default:
        throw new Error(`Unknown patch operation: ${patch.operation}`);
    }
  }
  
  /**
   * Assemble file creation patch
   */
  private assembleFileCreation(
    patch: Patch,
    workspaceEdit: vscode.WorkspaceEdit,
    preview: string[]
  ): void {
    if (!patch.content) {
      throw new Error(`File creation patch missing content: ${patch.filePath}`);
    }
    
    const uri = vscode.Uri.file(patch.filePath);
    
    // Ensure directory exists
    const dir = path.dirname(patch.filePath);
    if (!fs.existsSync(dir)) {
      // VS Code will handle directory creation automatically when we create the file
    }
    
    // Create the file with content
    workspaceEdit.createFile(uri, { 
      overwrite: false, // Don't overwrite existing files
      ignoreIfExists: false // Throw error if file exists
    });
    
    // Insert the content
    const fullRange = new vscode.Range(0, 0, 0, 0);
    workspaceEdit.insert(uri, new vscode.Position(0, 0), patch.content);
    
    preview.push(`📄 Create ${patch.filePath} (${patch.content.split('\n').length} lines)`);
  }
  
  /**
   * Assemble file modification patch
   */
  private assembleFileModification(
    patch: Patch,
    workspaceEdit: vscode.WorkspaceEdit,
    preview: string[]
  ): void {
    if (!patch.edits || patch.edits.length === 0) {
      throw new Error(`File modification patch missing edits: ${patch.filePath}`);
    }
    
    const uri = vscode.Uri.file(patch.filePath);
    
    // Apply edits in reverse order (highest line number first) to maintain line numbers
    const sortedEdits = [...patch.edits].sort((a, b) => b.startLine - a.startLine);
    
    for (const edit of sortedEdits) {
      this.assembleEdit(edit, uri, workspaceEdit);
    }
    
    preview.push(`✏️ Modify ${patch.filePath} (${patch.edits.length} edits)`);
  }
  
  /**
   * Assemble file deletion patch
   */
  private assembleFileDeletion(
    patch: Patch,
    workspaceEdit: vscode.WorkspaceEdit,
    preview: string[]
  ): void {
    const uri = vscode.Uri.file(patch.filePath);
    
    workspaceEdit.deleteFile(uri, {
      recursive: false, // Only delete files, not directories
      ignoreIfNotExists: false // Throw error if file doesn't exist
    });
    
    preview.push(`🗑️ Delete ${patch.filePath}`);
  }
  
  /**
   * Assemble file move/rename patch
   */
  private assembleFileMove(
    patch: Patch,
    workspaceEdit: vscode.WorkspaceEdit,
    preview: string[]
  ): void {
    if (!patch.newPath) {
      throw new Error(`File move patch missing newPath: ${patch.filePath}`);
    }
    
    const sourceUri = vscode.Uri.file(patch.filePath);
    const targetUri = vscode.Uri.file(patch.newPath);
    
    workspaceEdit.renameFile(sourceUri, targetUri, {
      overwrite: false, // Don't overwrite existing files
      ignoreIfExists: false // Throw error if target exists
    });
    
    preview.push(`📁 Move ${patch.filePath} → ${patch.newPath}`);
  }
  
  /**
   * Assemble a single edit operation
   */
  private assembleEdit(
    edit: AppliedEdit,
    uri: vscode.Uri,
    workspaceEdit: vscode.WorkspaceEdit
  ): void {
    switch (edit.type) {
      case 'insert':
        if (!edit.content) {
          throw new Error('Insert edit missing content');
        }
        
        const insertPosition = new vscode.Position(edit.startLine, 0);
        workspaceEdit.insert(uri, insertPosition, edit.content + '\n');
        break;
      
      case 'replace':
        if (!edit.content) {
          throw new Error('Replace edit missing content');
        }
        
        const endLine = edit.endLine || edit.startLine;
        const replaceRange = new vscode.Range(
          edit.startLine,
          0,
          endLine + 1,
          0
        );
        
        workspaceEdit.replace(uri, replaceRange, edit.content + '\n');
        break;
      
      case 'delete':
        const deleteEndLine = edit.endLine || edit.startLine;
        const deleteRange = new vscode.Range(
          edit.startLine,
          0,
          deleteEndLine + 1,
          0
        );
        
        workspaceEdit.delete(uri, deleteRange);
        break;
      
      default:
        throw new Error(`Unknown edit type: ${edit.type}`);
    }
  }
  
  /**
   * Sort patches by dependency order to prevent conflicts
   */
  private sortPatchesByDependency(patches: Patch[]): Patch[] {
    // Order: creates first, then modifies, then moves, then deletes
    return patches.sort((a, b) => {
      const orderMap = { create: 1, modify: 2, move: 3, delete: 4 };
      return (orderMap as any)[a.operation] - (orderMap as any)[b.operation];
    });
  }
  
  /**
   * Calculate summary statistics for the assembled edits
   */
  private calculateSummary(patches: Patch[]): EditSummary {
    const summary: EditSummary = {
      totalFiles: 0,
      filesCreated: 0,
      filesModified: 0,
      filesDeleted: 0,
      filesMoved: 0,
      totalChanges: 0,
      estimatedImpact: 'low'
    };
    
    const uniqueFiles = new Set<string>();
    
    for (const patch of patches) {
      uniqueFiles.add(patch.filePath);
      summary.totalChanges++;
      
      switch (patch.operation) {
        case 'create':
          summary.filesCreated++;
          break;
        case 'modify':
          summary.filesModified++;
          summary.totalChanges += (patch.edits?.length || 1) - 1; // -1 because we already counted the patch
          break;
        case 'delete':
          summary.filesDeleted++;
          break;
        case 'move':
          summary.filesMoved++;
          break;
      }
    }
    
    summary.totalFiles = uniqueFiles.size;
    
    // Estimate impact based on scope
    if (summary.totalFiles > 10 || summary.filesDeleted > 0) {
      summary.estimatedImpact = 'high';
    } else if (summary.totalFiles > 3 || summary.totalChanges > 20) {
      summary.estimatedImpact = 'medium';
    } else {
      summary.estimatedImpact = 'low';
    }
    
    return summary;
  }
  
  /**
   * Validate that patches can be safely applied
   */
  validatePatches(patches: Patch[]): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    const filesToCreate = new Set<string>();
    const filesToModify = new Set<string>();
    const filesToDelete = new Set<string>();
    
    for (const patch of patches) {
      switch (patch.operation) {
        case 'create':
          if (fs.existsSync(patch.filePath)) {
            errors.push(`Cannot create existing file: ${patch.filePath}`);
          }
          if (filesToCreate.has(patch.filePath)) {
            errors.push(`Duplicate file creation: ${patch.filePath}`);
          }
          filesToCreate.add(patch.filePath);
          break;
        
        case 'modify':
          if (!fs.existsSync(patch.filePath)) {
            errors.push(`Cannot modify non-existent file: ${patch.filePath}`);
          }
          if (filesToDelete.has(patch.filePath)) {
            errors.push(`Cannot modify file marked for deletion: ${patch.filePath}`);
          }
          filesToModify.add(patch.filePath);
          break;
        
        case 'delete':
          if (!fs.existsSync(patch.filePath)) {
            errors.push(`Cannot delete non-existent file: ${patch.filePath}`);
          }
          if (filesToCreate.has(patch.filePath) || filesToModify.has(patch.filePath)) {
            errors.push(`Cannot delete file with pending changes: ${patch.filePath}`);
          }
          filesToDelete.add(patch.filePath);
          break;
        
        case 'move':
          if (!patch.newPath) {
            errors.push(`Move operation missing target path: ${patch.filePath}`);
          } else if (fs.existsSync(patch.newPath)) {
            errors.push(`Cannot move to existing file: ${patch.newPath}`);
          }
          break;
      }
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }
}