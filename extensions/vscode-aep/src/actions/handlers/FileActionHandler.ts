/**
 * File Action Handler
 * Handles actions that involve file operations (create, edit, delete)
 * Shows diff view with green additions and red deletions before applying
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as Diff from 'diff';
import { BaseActionHandler, ActionContext, ActionResult, DiffStats } from '../ActionRegistry';

export class FileActionHandler extends BaseActionHandler {
    constructor() {
        super('file-operations', 100); // High priority
    }

    canHandle(action: any): boolean {
        // Handle explicit file action types, or actions with filePath/path and content/operation
        const filePath = action.filePath || action.path;
        const canHandle = !!(
            action.type === 'editFile' ||
            action.type === 'createFile' ||
            action.type === 'deleteFile' ||
            action.type === 'delete' ||
            (filePath && (action.content !== undefined || action.operation))
        );
        console.log(`[FileActionHandler] canHandle check - type: ${action.type}, filePath: ${filePath}, hasContent: ${action.content !== undefined}, result: ${canHandle}`);
        return canHandle;
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        const filePath = action.filePath || action.path;
        const content = action.content;
        const operation =
            action.operation ||
            (action.type === 'deleteFile' || action.type === 'delete'
                ? 'delete'
                : content !== undefined
                    ? 'write'
                    : 'read');

        if (!filePath) {
            throw new Error('No file path provided for file operation');
        }

        console.log(`[FileActionHandler] Executing file operation: ${operation} on ${filePath}`);

        try {
            switch (operation) {
                case 'create':
                case 'write':
                    const writeResult = await this.createOrUpdateFile(filePath, content, context);
                    return {
                        success: true,
                        message: `File ${operation === 'create' ? 'created' : 'written'}: ${filePath}`,
                        diffStats: writeResult.diffStats,
                        data: {
                            diffUnified: writeResult.diffUnified,
                            originalContent: writeResult.originalContent,
                            wasCreated: writeResult.wasCreated,
                        }
                    };

                case 'modify':
                case 'edit':
                    const editResult = await this.editFile(filePath, content, action, context);
                    return {
                        success: true,
                        message: `File modified: ${filePath}`,
                        diffStats: editResult.diffStats,
                        data: {
                            diffUnified: editResult.diffUnified,
                            originalContent: editResult.originalContent,
                        }
                    };

                case 'delete':
                    const deleteResult = await this.deleteFile(filePath, context);
                    return {
                        success: true,
                        message: `File deleted: ${filePath}`,
                        diffStats: deleteResult.diffStats,
                        data: {
                            diffUnified: deleteResult.diffUnified,
                            originalContent: deleteResult.originalContent,
                            wasDeleted: true,
                        }
                    };

                default:
                    // Default to edit/modify if we have content
                    if (content !== undefined) {
                        const defaultEditResult = await this.editFile(filePath, content, action, context);
                        return {
                            success: true,
                            message: `File updated: ${filePath}`,
                            diffStats: defaultEditResult.diffStats,
                            data: {
                                diffUnified: defaultEditResult.diffUnified,
                                originalContent: defaultEditResult.originalContent,
                            }
                        };
                    }
                    throw new Error(`Unknown file operation: ${operation}`);
            }
        } catch (error: any) {
            console.error(`[FileActionHandler] File operation failed:`, error);
            return {
                success: false,
                error: error,
                message: `File operation failed: ${error.message}`
            };
        }
    }

    private async createOrUpdateFile(
        filePath: string,
        content: string,
        context: ActionContext
    ): Promise<{ diffStats: DiffStats; diffUnified: string; originalContent: string; wasCreated: boolean }> {
        const absolutePath = this.resolveFilePath(filePath, context.workspaceRoot);
        const uri = vscode.Uri.file(absolutePath);
        const nextContent = content ?? "";
        let originalContent = "";
        let wasCreated = false;

        try {
            const existingDoc = await vscode.workspace.openTextDocument(uri);
            originalContent = existingDoc.getText();
        } catch {
            originalContent = "";
            wasCreated = true; // File didn't exist before
        }

        const diffStats = this.calculateDiffStats(originalContent, nextContent);
        const diffUnified = this.createUnifiedDiff(filePath, originalContent, nextContent);

        // Ensure directory exists
        const dir = path.dirname(absolutePath);
        await vscode.workspace.fs.createDirectory(vscode.Uri.file(dir));

        // Write file
        const encoder = new TextEncoder();
        await vscode.workspace.fs.writeFile(uri, encoder.encode(nextContent));

        // Open file in editor
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc);

        return { diffStats, diffUnified, originalContent, wasCreated };
    }

    private async editFile(
        filePath: string,
        content: string,
        action: any,
        context: ActionContext
    ): Promise<{ diffStats: DiffStats; diffUnified: string; originalContent?: string }> {
        const absolutePath = this.resolveFilePath(filePath, context.workspaceRoot);
        const uri = vscode.Uri.file(absolutePath);

        console.log(`[FileActionHandler] editFile called - path: ${absolutePath}, content length: ${content?.length || 0}`);

        // Check if file exists
        try {
            await vscode.workspace.fs.stat(uri);
        } catch {
            throw new Error(`File not found: ${filePath}`);
        }

        // If content is empty or undefined, don't write
        if (!content) {
            console.error('[FileActionHandler] No content provided for edit!');
            throw new Error('No content provided for file edit');
        }

        // Open the document first (this ensures we're working with VS Code's buffer)
        const doc = await vscode.workspace.openTextDocument(uri);
        const originalContent = doc.getText();

        console.log(`[FileActionHandler] Original content length: ${originalContent.length}, new content length: ${content.length}`);

        // Calculate diff statistics
        const diffStats = this.calculateDiffStats(originalContent, content);
        const diffUnified = this.createUnifiedDiff(filePath, originalContent, content);
        console.log(`[FileActionHandler] Diff stats - additions: ${diffStats.additions}, deletions: ${diffStats.deletions}, changes: ${diffStats.changes}`);

        // Auto-apply the edit (approved via NAVI approval panel)
        const edit = new vscode.WorkspaceEdit();
        const fullRange = new vscode.Range(
            doc.positionAt(0),
            doc.positionAt(originalContent.length)
        );
        edit.replace(uri, fullRange, content);

        const success = await vscode.workspace.applyEdit(edit);
        if (!success) {
            throw new Error('Failed to apply edit to file');
        }

        console.log(`[FileActionHandler] Edit applied successfully`);

        // Save the document to persist changes to disk
        await doc.save();
        console.log(`[FileActionHandler] File saved successfully`);

        // Show the updated document
        await vscode.window.showTextDocument(doc);

        // Show success notification with diff stats
        vscode.window.setStatusBarMessage(`✅ Applied: +${diffStats.additions} -${diffStats.deletions} lines`, 5000);

        // Return original content for potential undo
        return { diffStats, diffUnified, originalContent };
    }

    private createUnifiedDiff(filePath: string, original: string, updated: string): string {
        return Diff.createTwoFilesPatch(
            filePath,
            filePath,
            original,
            updated,
            '',
            ''
        );
    }

    /**
     * Calculate diff statistics between original and new content
     */
    private calculateDiffStats(original: string, modified: string): DiffStats {
        const changes = Diff.diffLines(original, modified);

        let additions = 0;
        let deletions = 0;
        let changeCount = 0;

        for (const change of changes) {
            if (change.added) {
                additions += change.count || 0;
                changeCount++;
            } else if (change.removed) {
                deletions += change.count || 0;
                changeCount++;
            }
        }

        return {
            additions,
            deletions,
            changes: changeCount
        };
    }

    private async deleteFile(
        filePath: string,
        context: ActionContext
    ): Promise<{ diffStats: DiffStats; diffUnified: string; originalContent: string }> {
        const absolutePath = this.resolveFilePath(filePath, context.workspaceRoot);
        const uri = vscode.Uri.file(absolutePath);

        // Capture original content for undo + diff stats
        let originalContent = '';
        try {
            const doc = await vscode.workspace.openTextDocument(uri);
            originalContent = doc.getText();
        } catch {
            throw new Error(`File not found: ${filePath}`);
        }

        const diffStats = this.calculateDiffStats(originalContent, '');
        const diffUnified = this.createUnifiedDiff(filePath, originalContent, '');

        // Only prompt if not already approved via chat
        if (!context.approvedViaChat) {
            const confirm = await vscode.window.showWarningMessage(
                `Delete file: ${filePath}?`,
                { modal: true },
                'Delete'
            );
            if (confirm !== 'Delete') {
                throw new Error('File deletion cancelled by user');
            }
        }

        await vscode.workspace.fs.delete(uri);
        return { diffStats, diffUnified, originalContent };
    }

    private resolveFilePath(filePath: string, workspaceRoot?: string): string {
        if (path.isAbsolute(filePath)) {
            return filePath;
        }

        const workspace = workspaceRoot || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspace) {
            throw new Error('No workspace folder found');
        }

        return path.join(workspace, filePath);
    }
}
