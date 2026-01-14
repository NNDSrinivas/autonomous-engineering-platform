/**
 * Navigation Action Handler
 * Handles actions that involve navigation (open files, folders, URLs)
 */

import * as vscode from 'vscode';
import { BaseActionHandler, ActionContext, ActionResult } from '../ActionRegistry';

export class NavigationActionHandler extends BaseActionHandler {
    constructor() {
        super('navigation', 80);
    }

    canHandle(action: any): boolean {
        // Can handle if action has navigation-related fields
        return !!(
            action.url ||
            action.uri ||
            action.path ||
            action.folder ||
            action.type === 'navigate' ||
            action.type === 'open'
        );
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        try {
            // Handle URL opening
            if (action.url) {
                await this.openUrl(action.url);
                return {
                    success: true,
                    message: `Opened URL: ${action.url}`
                };
            }

            // Handle folder opening
            if (action.folder || (action.uri && action.type === 'folder')) {
                await this.openFolder(action.folder || action.uri, action);
                return {
                    success: true,
                    message: `Opened folder: ${action.folder || action.uri}`
                };
            }

            // Handle file opening
            if (action.path || action.uri) {
                await this.openFile(action.path || action.uri, action);
                return {
                    success: true,
                    message: `Opened file: ${action.path || action.uri}`
                };
            }

            return {
                success: false,
                message: 'No valid navigation target found in action'
            };
        } catch (error: any) {
            return {
                success: false,
                error: error,
                message: `Navigation failed: ${error.message}`
            };
        }
    }

    private async openUrl(url: string): Promise<void> {
        const uri = vscode.Uri.parse(url);
        await vscode.env.openExternal(uri);
    }

    private async openFolder(folderPath: string, action: any): Promise<void> {
        const uri = vscode.Uri.file(folderPath);
        const newWindow = action.newWindow !== false; // Default to new window

        await vscode.commands.executeCommand('vscode.openFolder', uri, newWindow);
    }

    private async openFile(filePath: string, action: any): Promise<void> {
        const uri = vscode.Uri.file(filePath);
        const doc = await vscode.workspace.openTextDocument(uri);

        const options: vscode.TextDocumentShowOptions = {};

        // If line/column specified, go to that location
        if (action.line !== undefined) {
            const line = Math.max(0, action.line - 1); // Convert to 0-based
            const column = action.column !== undefined ? Math.max(0, action.column - 1) : 0;

            options.selection = new vscode.Range(
                new vscode.Position(line, column),
                new vscode.Position(line, column)
            );
        }

        await vscode.window.showTextDocument(doc, options);
    }
}
