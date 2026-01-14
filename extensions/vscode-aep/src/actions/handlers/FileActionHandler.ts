/**
 * File Action Handler
 * Handles actions that involve file operations (create, edit, delete)
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { BaseActionHandler, ActionContext, ActionResult } from '../ActionRegistry';

export class FileActionHandler extends BaseActionHandler {
    constructor() {
        super('file-operations', 100); // High priority
    }

    canHandle(action: any): boolean {
        // Can handle if action has filePath and either content or operation
        return !!(
            action.filePath &&
            (action.content !== undefined || action.operation)
        );
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        const filePath = action.filePath;
        const content = action.content;
        const operation = action.operation || (content !== undefined ? 'write' : 'read');

        try {
            switch (operation) {
                case 'create':
                case 'write':
                    await this.createOrUpdateFile(filePath, content, context);
                    return {
                        success: true,
                        message: `File ${operation}d: ${filePath}`
                    };

                case 'edit':
                    await this.editFile(filePath, content, action, context);
                    return {
                        success: true,
                        message: `File edited: ${filePath}`
                    };

                case 'delete':
                    await this.deleteFile(filePath, context);
                    return {
                        success: true,
                        message: `File deleted: ${filePath}`
                    };

                default:
                    throw new Error(`Unknown file operation: ${operation}`);
            }
        } catch (error: any) {
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
    ): Promise<void> {
        const absolutePath = this.resolveFilePath(filePath, context.workspaceRoot);
        const uri = vscode.Uri.file(absolutePath);

        // Ensure directory exists
        const dir = path.dirname(absolutePath);
        await vscode.workspace.fs.createDirectory(vscode.Uri.file(dir));

        // Write file
        const encoder = new TextEncoder();
        await vscode.workspace.fs.writeFile(uri, encoder.encode(content));

        // Open file in editor
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc);
    }

    private async editFile(
        filePath: string,
        content: string,
        action: any,
        context: ActionContext
    ): Promise<void> {
        const absolutePath = this.resolveFilePath(filePath, context.workspaceRoot);
        const uri = vscode.Uri.file(absolutePath);

        // Check if file exists
        try {
            await vscode.workspace.fs.stat(uri);
        } catch {
            throw new Error(`File not found: ${filePath}`);
        }

        // If diff is provided, could show diff view
        // For now, just replace content
        const encoder = new TextEncoder();
        await vscode.workspace.fs.writeFile(uri, encoder.encode(content));

        // Open file
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc);
    }

    private async deleteFile(filePath: string, context: ActionContext): Promise<void> {
        const absolutePath = this.resolveFilePath(filePath, context.workspaceRoot);
        const uri = vscode.Uri.file(absolutePath);

        // Confirm deletion
        const confirm = await vscode.window.showWarningMessage(
            `Delete file: ${filePath}?`,
            { modal: true },
            'Delete'
        );

        if (confirm === 'Delete') {
            await vscode.workspace.fs.delete(uri);
        } else {
            throw new Error('File deletion cancelled by user');
        }
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
