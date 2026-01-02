/**
 * Auto-fix service for applying AI-generated code fixes
 * Handles patch generation, preview, and application to workspace files
 */

import * as vscode from 'vscode';
import * as path from 'path';

export interface ReviewEntry {
  file: string;
  hunk: string;
  severity: 'low' | 'medium' | 'high';
  title: string;
  body: string;
  fixId: string;
}

export interface FixResult {
  success: boolean;
  message: string;
  appliedChanges?: string[];
  errors?: string[];
}

/**
 * Apply an auto-fix for a review entry
 */
export async function applyFixById(entry: ReviewEntry): Promise<FixResult> {
  const { file, hunk, fixId, title } = entry;
  
  try {
    // Show confirmation dialog
    const action = await vscode.window.showInformationMessage(
      `Apply auto-fix: "${title}"?`,
      { modal: true, detail: `This will modify ${file}` },
      'Apply Fix',
      'Show Preview',
      'Cancel'
    );

    if (action === 'Cancel' || !action) {
      return {
        success: false,
        message: 'Fix cancelled by user'
      };
    }

    if (action === 'Show Preview') {
      await showFixPreview(entry);
      return {
        success: false,
        message: 'Preview shown - fix not applied'
      };
    }

    // Apply the fix
    const result = await applyFixToFile(entry);
    
    if (result.success) {
      vscode.window.showInformationMessage(
        `✅ Auto-fix applied to ${path.basename(file)}`,
        'View Changes'
      ).then(selection => {
        if (selection === 'View Changes') {
          openFileWithFix(file);
        }
      });
    } else {
      vscode.window.showErrorMessage(`❌ Failed to apply fix: ${result.message}`);
    }

    return result;

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    vscode.window.showErrorMessage(`Failed to apply auto-fix: ${errorMessage}`);
    
    return {
      success: false,
      message: errorMessage,
      errors: [errorMessage]
    };
  }
}

/**
 * Show a preview of what the fix would do
 */
async function showFixPreview(entry: ReviewEntry): Promise<void> {
  try {
    const { file, hunk, title } = entry;
    
    // Create a temporary file to show the diff
    const originalUri = vscode.Uri.file(file);
    const previewUri = vscode.Uri.parse(`untitled:${path.basename(file)}.fix-preview`);
    
    // Show original file
    const originalDoc = await vscode.workspace.openTextDocument(originalUri);
    await vscode.window.showTextDocument(originalDoc, { viewColumn: vscode.ViewColumn.One });
    
    // Create preview content (for now, show the hunk)
    const previewContent = `
# Auto-fix Preview: ${title}

## Original Hunk:
\`\`\`diff
${hunk}
\`\`\`

## What this fix will do:
- Apply the changes shown in the diff above
- This is a placeholder for Batch 6 implementation

## File: ${file}
`.trim();

    // Show preview in second column
    const previewDoc = await vscode.workspace.openTextDocument(previewUri);
    const edit = new vscode.WorkspaceEdit();
    edit.insert(previewUri, new vscode.Position(0, 0), previewContent);
    await vscode.workspace.applyEdit(edit);
    await vscode.window.showTextDocument(previewDoc, { 
      viewColumn: vscode.ViewColumn.Two,
      preview: true
    });

  } catch (error) {
    console.error('Failed to show fix preview:', error);
    vscode.window.showErrorMessage('Failed to show fix preview');
  }
}

/**
 * Apply the fix to the actual file
 * This is a placeholder implementation for Batch 5
 */
async function applyFixToFile(entry: ReviewEntry): Promise<FixResult> {
  const { file, hunk, fixId, title } = entry;
  
  try {
    // Open the file
    const uri = vscode.Uri.file(file);
    const document = await vscode.workspace.openTextDocument(uri);
    
    // For Batch 5, we'll add a comment indicating where the fix would be applied
    // Batch 6 will implement actual patch parsing and application
    
    const edit = new vscode.WorkspaceEdit();
    const lastLine = document.lineCount - 1;
    const endOfFile = new vscode.Position(lastLine, document.lineAt(lastLine).text.length);
    
    const fixComment = `
// AUTO-FIX APPLIED: ${title}
// Fix ID: ${fixId}
// This is a placeholder - Batch 6 will implement real patch application
`;

    edit.insert(uri, endOfFile, fixComment);
    const success = await vscode.workspace.applyEdit(edit);
    
    if (success) {
      return {
        success: true,
        message: `Placeholder fix applied to ${file}`,
        appliedChanges: [`Added fix comment for: ${title}`]
      };
    } else {
      return {
        success: false,
        message: 'Failed to apply workspace edit'
      };
    }
    
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Unknown error applying fix',
      errors: [String(error)]
    };
  }
}

/**
 * Open the file and navigate to where the fix was applied
 */
async function openFileWithFix(filePath: string): Promise<void> {
  try {
    const uri = vscode.Uri.file(filePath);
    const document = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(document);
    
    // Navigate to the end of the file where we added the fix comment
    const lastLine = document.lineCount - 1;
    const position = new vscode.Position(lastLine, 0);
    editor.selection = new vscode.Selection(position, position);
    editor.revealRange(new vscode.Range(position, position));
    
  } catch (error) {
    console.error('Failed to open file with fix:', error);
  }
}

/**
 * Batch 6 placeholder: Parse a unified diff and apply patches
 */
export async function applyUnifiedDiffPatch(filePath: string, patch: string): Promise<FixResult> {
  // This will be implemented in Batch 6
  return {
    success: false,
    message: 'Unified diff parsing will be implemented in Batch 6'
  };
}

/**
 * Batch 6 placeholder: Generate a fix patch using AI
 */
export async function generateFixPatch(entry: ReviewEntry): Promise<string | null> {
  // This will be implemented in Batch 6 - AI will generate actual patches
  return null;
}

/**
 * Get fix capabilities for a file type
 */
export function getFixCapabilities(fileExtension: string): string[] {
  const capabilities: Record<string, string[]> = {
    '.ts': ['add-types', 'fix-imports', 'add-error-handling', 'optimize-performance'],
    '.tsx': ['add-types', 'fix-imports', 'add-error-handling', 'optimize-performance', 'fix-jsx'],
    '.js': ['fix-imports', 'add-error-handling', 'optimize-performance', 'modernize-syntax'],
    '.jsx': ['fix-imports', 'add-error-handling', 'optimize-performance', 'fix-jsx'],
    '.py': ['add-types', 'fix-imports', 'add-docstrings', 'fix-security'],
    '.java': ['add-annotations', 'fix-imports', 'optimize-performance'],
    '.css': ['fix-formatting', 'optimize-selectors', 'add-vendor-prefixes'],
    '.scss': ['fix-formatting', 'optimize-nesting', 'fix-variables'],
    '.json': ['fix-formatting', 'validate-schema'],
    '.md': ['fix-formatting', 'check-links', 'improve-structure']
  };
  
  return capabilities[fileExtension] || ['basic-formatting'];
}