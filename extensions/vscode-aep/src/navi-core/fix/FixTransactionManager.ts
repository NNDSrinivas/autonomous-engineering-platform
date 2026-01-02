// extensions/vscode-aep/src/navi-core/fix/FixTransactionManager.ts
/**
 * Phase 2.2 Step 4: Batch Fix & Undo Support
 * 
 * Provides atomic fix transactions with rollback capability.
 * Ensures NAVI fixes are either completely successful or completely reverted,
 * matching Copilot/Cline trust model.
 * 
 * Key Guarantees:
 * - All fixes apply atomically or none apply
 * - One-click undo for any NAVI fix session
 * - No partial/broken intermediate states
 * - Workspace-level trust and safety
 */

import * as vscode from 'vscode';

/**
 * Manages atomic fix transactions with full rollback capability.
 * 
 * This is the core component that makes NAVI fixes trustworthy and reversible,
 * eliminating user fear of "what if the fix breaks something?"
 */
export class FixTransactionManager {
    private static lastSnapshot: Map<string, string> | null = null;
    private static lastTransactionTimestamp: number | null = null;

    /**
     * Begins a new fix transaction by taking snapshots of all affected files.
     * This enables atomic rollback if any part of the fix fails.
     * 
     * @param uris Files that will be modified in this transaction
     */
    static async begin(uris: vscode.Uri[]): Promise<void> {
        console.log(`[FixTransactionManager] Beginning transaction for ${uris.length} files`);

        const snapshot = new Map<string, string>();

        for (const uri of uris) {
            try {
                const document = await vscode.workspace.openTextDocument(uri);
                snapshot.set(uri.toString(), document.getText());
                console.log(`[FixTransactionManager] Snapshotted ${uri.fsPath}`);
            } catch (error) {
                console.error(`[FixTransactionManager] Failed to snapshot ${uri.fsPath}: ${error}`);
                throw new Error(`Cannot begin transaction: failed to read ${uri.fsPath}`);
            }
        }

        this.lastSnapshot = snapshot;
        this.lastTransactionTimestamp = Date.now();

        console.log(`[FixTransactionManager] Transaction begun with ${snapshot.size} file snapshots`);
    }

    /**
     * Rolls back the last transaction to the pre-fix state.
     * This is the "undo" functionality that users can trust.
     */
    static async rollback(): Promise<void> {
        if (!this.lastSnapshot) {
            console.log(`[FixTransactionManager] No snapshot to rollback`);
            return;
        }

        console.log(`[FixTransactionManager] Rolling back ${this.lastSnapshot.size} files`);

        const workspaceEdit = new vscode.WorkspaceEdit();

        for (const [uriString, originalContent] of this.lastSnapshot.entries()) {
            try {
                const uri = vscode.Uri.parse(uriString);
                const document = await vscode.workspace.openTextDocument(uri);

                // Replace entire file content with snapshot
                const fullRange = new vscode.Range(
                    document.positionAt(0),
                    document.positionAt(document.getText().length)
                );

                workspaceEdit.replace(uri, fullRange, originalContent);
                console.log(`[FixTransactionManager] Queued rollback for ${uri.fsPath}`);
            } catch (error) {
                console.error(`[FixTransactionManager] Failed to prepare rollback for ${uriString}: ${error}`);
                throw new Error(`Rollback failed: cannot restore ${uriString}`);
            }
        }

        // Apply all rollbacks atomically
        const success = await vscode.workspace.applyEdit(workspaceEdit);

        if (success) {
            console.log(`[FixTransactionManager] Rollback successful`);
            this.clear();
        } else {
            console.error(`[FixTransactionManager] Rollback failed to apply workspace edit`);
            throw new Error('Rollback failed: workspace edit could not be applied');
        }
    }

    /**
     * Commits the current transaction, clearing the snapshot.
     * This indicates the fix was successful and undo is no longer needed.
     */
    static commit(): void {
        if (this.lastSnapshot) {
            console.log(`[FixTransactionManager] Committing transaction (clearing ${this.lastSnapshot.size} snapshots)`);
            this.clear();
        }
    }

    /**
     * Checks if there's an undo-able transaction available.
     * Used to determine whether to show "Undo" UI elements.
     */
    static hasUndo(): boolean {
        return this.lastSnapshot !== null;
    }

    /**
     * Gets information about the last transaction for user display.
     */
    static getUndoInfo(): { fileCount: number; timestamp: number } | null {
        if (!this.lastSnapshot || !this.lastTransactionTimestamp) {
            return null;
        }

        return {
            fileCount: this.lastSnapshot.size,
            timestamp: this.lastTransactionTimestamp
        };
    }

    /**
     * Clears the current transaction state.
     * Private helper for commit() and rollback().
     */
    private static clear(): void {
        this.lastSnapshot = null;
        this.lastTransactionTimestamp = null;
    }

    /**
     * Creates a WorkspaceEdit from multiple fix results.
     * This enables atomic application of all fixes in a batch.
     * 
     * @param fixes Array of fix results to apply
     * @returns WorkspaceEdit that can be applied atomically
     */
    static createBatchEdit(fixes: Array<{
        uri: vscode.Uri;
        newContent: string;
    }>): vscode.WorkspaceEdit {
        const workspaceEdit = new vscode.WorkspaceEdit();

        for (const fix of fixes) {
            // Replace entire file with fixed content
            const uri = fix.uri;
            workspaceEdit.createFile(uri, { ignoreIfExists: true });

            // We'll need to get the current content to create proper range
            // For now, this is a placeholder - the actual implementation
            // will need to handle this in the calling code
            workspaceEdit.replace(
                uri,
                new vscode.Range(0, 0, Number.MAX_VALUE, Number.MAX_VALUE),
                fix.newContent
            );
        }

        return workspaceEdit;
    }
}