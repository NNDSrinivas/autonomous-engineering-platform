/**
 * Phase 3.3 - Code Synthesizer
 * 
 * This is the ONLY place where raw LLM output is allowed.
 * It acts as a controlled boundary that converts ChangePlans to executable patches
 * without direct LLM → file writes. This prevents hallucinations and partial applications.
 */

import { ChangePlan, ChangeStep, FileEdit } from './ChangePlan';
import * as fs from 'fs';

export interface Patch {
  filePath: string;
  operation: 'create' | 'modify' | 'delete' | 'move';
  content?: string;
  edits?: AppliedEdit[];
  newPath?: string;
  originalContent?: string; // For rollback
}

export interface AppliedEdit {
  type: 'insert' | 'replace' | 'delete';
  startLine: number;
  endLine?: number;
  content?: string;
  originalContent?: string; // What was there before
}

export class CodeSynthesizer {
  /**
   * Convert a ChangePlan into executable patches
   * This is the controlled LLM boundary - no direct file system access
   */
  synthesize(plan: ChangePlan): Patch[] {
    console.log(`🔧 Synthesizing patches for: ${plan.description}`);
    
    const patches: Patch[] = [];
    
    for (const step of plan.steps) {
      try {
        const patch = this.synthesizeStep(step);
        if (patch) {
          patches.push(patch);
        }
      } catch (error) {
        console.error(`Failed to synthesize step ${step.id}:`, error);
        throw new Error(`Synthesis failed for ${step.filePath}: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    
    console.log(`✅ Synthesized ${patches.length} patches`);
    return patches;
  }
  
  /**
   * Synthesize a single change step into a patch
   */
  private synthesizeStep(step: ChangeStep): Patch | null {
    switch (step.operation) {
      case 'create':
        return this.synthesizeFileCreation(step);
      
      case 'modify':
        return this.synthesizeFileModification(step);
      
      case 'delete':
        return this.synthesizeFileDeletion(step);
      
      case 'move':
        return this.synthesizeFileMove(step);
      
      default:
        console.warn(`Unknown operation: ${step.operation}`);
        return null;
    }
  }
  
  /**
   * Create a file creation patch
   */
  private synthesizeFileCreation(step: ChangeStep): Patch {
    if (!step.content) {
      throw new Error(`File creation step missing content: ${step.filePath}`);
    }
    
    // Validate that file doesn't already exist
    if (fs.existsSync(step.filePath)) {
      throw new Error(`Cannot create file that already exists: ${step.filePath}`);
    }
    
    return {
      filePath: step.filePath,
      operation: 'create',
      content: step.content,
      originalContent: undefined // File didn't exist
    };
  }
  
  /**
   * Create a file modification patch with applied edits
   */
  private synthesizeFileModification(step: ChangeStep): Patch {
    if (!step.edits || step.edits.length === 0) {
      throw new Error(`File modification step missing edits: ${step.filePath}`);
    }
    
    // Read current file content
    if (!fs.existsSync(step.filePath)) {
      throw new Error(`Cannot modify non-existent file: ${step.filePath}`);
    }
    
    const originalContent = fs.readFileSync(step.filePath, 'utf8');
    const lines = originalContent.split('\n');
    
    // Convert FileEdits to AppliedEdits with validation
    const appliedEdits: AppliedEdit[] = [];
    
    for (const edit of step.edits) {
      const appliedEdit = this.validateAndPrepareEdit(edit, lines);
      appliedEdits.push(appliedEdit);
    }
    
    // Sort edits by line number (descending) to apply safely
    appliedEdits.sort((a, b) => b.startLine - a.startLine);
    
    return {
      filePath: step.filePath,
      operation: 'modify',
      edits: appliedEdits,
      originalContent
    };
  }
  
  /**
   * Create a file deletion patch
   */
  private synthesizeFileDeletion(step: ChangeStep): Patch {
    if (!fs.existsSync(step.filePath)) {
      throw new Error(`Cannot delete non-existent file: ${step.filePath}`);
    }
    
    // Read content for potential rollback
    const originalContent = fs.readFileSync(step.filePath, 'utf8');
    
    return {
      filePath: step.filePath,
      operation: 'delete',
      originalContent
    };
  }
  
  /**
   * Create a file move/rename patch
   */
  private synthesizeFileMove(step: ChangeStep): Patch {
    if (!step.newPath) {
      throw new Error(`File move step missing newPath: ${step.filePath}`);
    }
    
    if (!fs.existsSync(step.filePath)) {
      throw new Error(`Cannot move non-existent file: ${step.filePath}`);
    }
    
    if (fs.existsSync(step.newPath)) {
      throw new Error(`Cannot move to existing file: ${step.newPath}`);
    }
    
    const originalContent = fs.readFileSync(step.filePath, 'utf8');
    
    return {
      filePath: step.filePath,
      operation: 'move',
      newPath: step.newPath,
      originalContent
    };
  }
  
  /**
   * Validate and prepare a file edit
   */
  private validateAndPrepareEdit(edit: FileEdit, lines: string[]): AppliedEdit {
    // Validate line numbers
    if (edit.startLine < 0 || edit.startLine >= lines.length) {
      throw new Error(`Invalid start line ${edit.startLine} (file has ${lines.length} lines)`);
    }
    
    if (edit.endLine && (edit.endLine < edit.startLine || edit.endLine >= lines.length)) {
      throw new Error(`Invalid end line ${edit.endLine}`);
    }
    
    // Capture original content for rollback
    let originalContent: string;
    
    if (edit.type === 'insert') {
      originalContent = ''; // Nothing was there before
    } else if (edit.type === 'replace') {
      const endLine = edit.endLine || edit.startLine;
      originalContent = lines.slice(edit.startLine, endLine + 1).join('\n');
    } else if (edit.type === 'delete') {
      const endLine = edit.endLine || edit.startLine;
      originalContent = lines.slice(edit.startLine, endLine + 1).join('\n');
    } else {
      throw new Error(`Unknown edit type: ${edit.type}`);
    }
    
    return {
      type: edit.type,
      startLine: edit.startLine,
      endLine: edit.endLine,
      content: edit.content,
      originalContent
    };
  }
  
  /**
   * Preview what the synthesized patches will do (for approval UI)
   */
  previewPatches(patches: Patch[]): string[] {
    return patches.map(patch => this.describePatch(patch));
  }
  
  /**
   * Get a human-readable description of what a patch does
   */
  private describePatch(patch: Patch): string {
    switch (patch.operation) {
      case 'create':
        const createLines = patch.content?.split('\n').length || 0;
        return `📄 Create ${patch.filePath} (${createLines} lines)`;
      
      case 'modify':
        const editCount = patch.edits?.length || 0;
        return `✏️ Modify ${patch.filePath} (${editCount} edits)`;
      
      case 'delete':
        return `🗑️ Delete ${patch.filePath}`;
      
      case 'move':
        return `📁 Move ${patch.filePath} → ${patch.newPath}`;
      
      default:
        return `❓ Unknown operation on ${patch.filePath}`;
    }
  }
  
  /**
   * Calculate the total impact of patches (for risk assessment)
   */
  calculateImpact(patches: Patch[]): {
    filesCreated: number;
    filesModified: number;
    filesDeleted: number;
    filesMoved: number;
    totalEdits: number;
    linesAdded: number;
    linesRemoved: number;
  } {
    const impact = {
      filesCreated: 0,
      filesModified: 0,
      filesDeleted: 0,
      filesMoved: 0,
      totalEdits: 0,
      linesAdded: 0,
      linesRemoved: 0
    };
    
    for (const patch of patches) {
      switch (patch.operation) {
        case 'create':
          impact.filesCreated++;
          impact.linesAdded += patch.content?.split('\n').length || 0;
          break;
        
        case 'modify':
          impact.filesModified++;
          impact.totalEdits += patch.edits?.length || 0;
          
          // Calculate line changes for modifications
          if (patch.edits) {
            for (const edit of patch.edits) {
              if (edit.type === 'insert' && edit.content) {
                impact.linesAdded += edit.content.split('\n').length;
              } else if (edit.type === 'delete' && edit.originalContent) {
                impact.linesRemoved += edit.originalContent.split('\n').length;
              } else if (edit.type === 'replace') {
                if (edit.content) {
                  impact.linesAdded += edit.content.split('\n').length;
                }
                if (edit.originalContent) {
                  impact.linesRemoved += edit.originalContent.split('\n').length;
                }
              }
            }
          }
          break;
        
        case 'delete':
          impact.filesDeleted++;
          impact.linesRemoved += patch.originalContent?.split('\n').length || 0;
          break;
        
        case 'move':
          impact.filesMoved++;
          break;
      }
    }
    
    return impact;
  }
}