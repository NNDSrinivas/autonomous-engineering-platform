import * as vscode from 'vscode';

/**
 * SyntaxCompletionFixer - The Copilot Brain
 * 
 * Generates concrete WorkspaceEdits for mechanical syntax errors.
 * This is AUTHORITATIVE - it doesn't suggest, it FIXES.
 */
export class SyntaxCompletionFixer {
    /**
     * Generate a concrete WorkspaceEdit for a mechanical syntax error.
     * Returns null only if the error type is not supported.
     */
    static async generateFix(
        document: vscode.TextDocument,
        diagnostic: vscode.Diagnostic
    ): Promise<vscode.WorkspaceEdit | null> {
        const text = document.getText();
        const position = diagnostic.range.start;
        const message = diagnostic.message.toLowerCase();

        console.log(`[SyntaxCompletionFixer] Generating fix for: "${diagnostic.message}"`);

        // JSX missing closing tag - most common case
        if (message.includes("has no corresponding closing tag")) {
            return this.fixMissingJsxClosingTag(document, diagnostic, text);
        }

        // Missing braces, parentheses, brackets
        if (message.includes("'}' expected")) {
            return this.insertToken(document, position, "}");
        }
        if (message.includes("')' expected")) {
            return this.insertToken(document, position, ")");
        }
        if (message.includes("']' expected")) {
            return this.insertToken(document, position, "]");
        }

        // Expression expected - often missing semicolon or closing token
        if (message.includes("expression expected")) {
            return this.fixExpressionExpected(document, position, text);
        }

        // Identifier expected - usually missing variable name or incomplete statement
        if (message.includes("identifier expected")) {
            return this.fixIdentifierExpected(document, position, text);
        }

        console.log(`[SyntaxCompletionFixer] No fix strategy for: "${diagnostic.message}"`);
        return null;
    }

    private static fixMissingJsxClosingTag(
        document: vscode.TextDocument,
        diagnostic: vscode.Diagnostic,
        text: string
    ): vscode.WorkspaceEdit {
        const edit = new vscode.WorkspaceEdit();

        // Extract tag name from error message (e.g., "JSX element 'div' has no corresponding closing tag")
        const tagMatch = diagnostic.message.match(/JSX element '([^']+)'/);
        const tagName = tagMatch ? tagMatch[1] : 'div'; // fallback to div

        // Find the best insertion point - end of line or after the element content
        const line = document.lineAt(diagnostic.range.start.line);
        const insertPosition = line.range.end;

        edit.insert(document.uri, insertPosition, `</${tagName}>`);

        console.log(`[SyntaxCompletionFixer] Inserting JSX closing tag: </${tagName}>`);
        return edit;
    }

    private static insertToken(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: string
    ): vscode.WorkspaceEdit {
        const edit = new vscode.WorkspaceEdit();
        edit.insert(document.uri, position, token);

        console.log(`[SyntaxCompletionFixer] Inserting token: "${token}"`);
        return edit;
    }

    private static fixExpressionExpected(
        document: vscode.TextDocument,
        position: vscode.Position,
        text: string
    ): vscode.WorkspaceEdit {
        const edit = new vscode.WorkspaceEdit();
        const lineText = document.lineAt(position.line).text;

        // Heuristic: if line ends with incomplete syntax, add semicolon
        if (!lineText.trim().endsWith(';') && !lineText.trim().endsWith('}')) {
            const lineEnd = document.lineAt(position.line).range.end;
            edit.insert(document.uri, lineEnd, ';');
            console.log(`[SyntaxCompletionFixer] Adding semicolon for expression expected`);
        } else {
            // Insert placeholder or most likely missing token
            edit.insert(document.uri, position, '""'); // empty string as safe default
            console.log(`[SyntaxCompletionFixer] Adding empty string for expression expected`);
        }

        return edit;
    }

    private static fixIdentifierExpected(
        document: vscode.TextDocument,
        position: vscode.Position,
        text: string
    ): vscode.WorkspaceEdit {
        const edit = new vscode.WorkspaceEdit();

        // Insert a placeholder identifier
        edit.insert(document.uri, position, 'placeholder');

        console.log(`[SyntaxCompletionFixer] Inserting placeholder identifier`);
        return edit;
    }
}