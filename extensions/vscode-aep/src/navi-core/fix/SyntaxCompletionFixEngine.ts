import * as vscode from 'vscode';

export function isSyntaxDiagnostic(d: vscode.Diagnostic): boolean {
    const msg = d.message.toLowerCase();

    return (
        msg.includes('expected') ||
        msg.includes('unterminated') ||
        msg.includes('has no corresponding closing tag') ||
        msg.includes('identifier expected') ||
        msg.includes('expression expected') ||
        msg.includes('missing') ||
        d.code === '1005' || // TS common syntax
        d.code === '17008'   // JSX closing tag
    );
}

export interface SyntaxFixResult {
    fixedText: string;
    originalText: string;
}

export class SyntaxCompletionFixEngine {
    constructor(
        private readonly llm: {
            generateCodeFix(prompt: string): Promise<string>;
        }
    ) { }

    async generateFix(
        fileUri: vscode.Uri,
        originalText: string,
        diagnostics: vscode.Diagnostic[]
    ): Promise<SyntaxFixResult | null> {

        const syntaxDiagnostics = diagnostics.filter(isSyntaxDiagnostic);
        if (syntaxDiagnostics.length === 0) return null;

        const prompt = this.buildPrompt(
            fileUri.fsPath,
            originalText,
            syntaxDiagnostics
        );

        const fixedText = await this.llm.generateCodeFix(prompt);

        if (!fixedText || fixedText.trim() === originalText.trim()) {
            return null;
        }

        return {
            originalText,
            fixedText
        };
    }

    private buildPrompt(
        filePath: string,
        code: string,
        diagnostics: vscode.Diagnostic[]
    ): string {
        const issues = diagnostics
            .map(d => `- ${d.message} (line ${d.range.start.line + 1})`)
            .join('\n');

        return `
You are an expert TypeScript and React engineer.

The following file has syntax errors reported by the TypeScript compiler.
Your task is to FIX THE FILE so that it COMPILES.

Rules:
- Preserve existing logic and formatting
- Make the MINIMAL changes needed
- Do NOT refactor
- Do NOT add comments
- Return the FULL corrected file
- Do NOT explain anything

File path:
${filePath}

Compiler errors:
${issues}

File content:
\`\`\`
${code}
\`\`\`
`;
    }

    static buildWorkspaceEdit(
        uri: vscode.Uri,
        originalText: string,
        fixedText: string
    ): vscode.WorkspaceEdit {
        const edit = new vscode.WorkspaceEdit();

        const fullRange = new vscode.Range(
            0,
            0,
            Number.MAX_SAFE_INTEGER,
            Number.MAX_SAFE_INTEGER
        );

        edit.replace(uri, fullRange, fixedText);
        return edit;
    }

    // Temporary LLM integration point - will connect to NAVI's backend
    private async callLLM(prompt: string): Promise<string> {
        // This will be replaced with actual NAVI backend call
        // For now, return empty to prevent crashes during integration
        return '';
    }
}