/**
 * GenerativeStructuralFixEngine - The core breakthrough for Copilot/Cline parity
 * 
 * This engine eliminates the alternatives UI for syntax/structural errors by:
 * 1. Taking broken files as input
 * 2. Generating complete, valid file content via LLM
 * 3. Applying one atomic patch
 * 4. No user micromanagement required
 * 
 * This is what makes NAVI feel professional instead of like a diagnostic tool.
 */

import * as vscode from 'vscode';
import { DiagnosticCluster } from '../perception/DiagnosticsPerception';

export interface StructuralFixResult {
    success: boolean;
    fixedCode?: string;
    error?: string;
}

export class GenerativeStructuralFixEngine {
    /**
     * Main entry point - generates a complete fixed version of a file
     * based on structural/syntax error clusters
     */
    static async generateFix(
        cluster: DiagnosticCluster
    ): Promise<StructuralFixResult> {
        try {
            const uri = vscode.Uri.parse(cluster.fileUri);
            const doc = await vscode.workspace.openTextDocument(uri);
            const originalCode = doc.getText();

            const prompt = this.buildPrompt(originalCode, cluster);
            const fixedCode = await this.callLLM(prompt);

            if (!fixedCode || !this.isValidCode(fixedCode, originalCode)) {
                return {
                    success: false,
                    error: 'LLM failed to generate valid code'
                };
            }

            return {
                success: true,
                fixedCode
            };

        } catch (error) {
            return {
                success: false,
                error: `Generative fix failed: ${error}`
            };
        }
    }

    /**
     * Apply the generated fix as a single atomic workspace edit
     */
    static async applyFullFilePatch(
        fileUri: string,
        newContent: string
    ): Promise<boolean> {
        try {
            const uri = vscode.Uri.parse(fileUri);
            const doc = await vscode.workspace.openTextDocument(uri);

            const fullRange = new vscode.Range(
                doc.positionAt(0),
                doc.positionAt(doc.getText().length)
            );

            const edit = new vscode.WorkspaceEdit();
            edit.replace(uri, fullRange, newContent);

            const applied = await vscode.workspace.applyEdit(edit);
            console.log(`[GenerativeStructuralFixEngine] Full file patch applied: ${applied}`);

            return applied;

        } catch (error) {
            console.error(`[GenerativeStructuralFixEngine] Failed to apply patch:`, error);
            return false;
        }
    }

    /**
     * Builds the LLM prompt for structural repair
     */
    private static buildPrompt(
        code: string,
        cluster: DiagnosticCluster
    ): string {
        const rootMessage = cluster.root.message;
        const relatedMessages = cluster.related.map(d => `- ${d.message}`).join('\n');

        return `Fix the structural/syntax errors in this code file.

Root issue: ${rootMessage}

${cluster.related.length > 0 ? `Related errors:\n${relatedMessages}\n` : ''}

Requirements:
- Fix ALL syntax and structural errors
- Ensure JSX/HTML tags are properly closed
- Balance all brackets, parentheses, and braces
- Preserve existing logic and functionality
- Maintain original formatting style
- Return the COMPLETE corrected file

---- CODE TO FIX ----
${code}
---- END CODE ----

Return only the corrected code, no explanations:`;
    }

    /**
     * Temporary LLM client - uses existing NAVI infrastructure
     * TODO: Replace with proper LLMClient when available
     */
    private static async callLLM(prompt: string): Promise<string | null> {
        try {
            // For now, we'll integrate with NAVI's existing LLM infrastructure
            // This is a placeholder that will be replaced with actual LLM calls

            // Simulate basic structural fixes for common patterns
            // In production, this would call the actual LLM service
            return this.applyBasicStructuralFixes(prompt);

        } catch (error) {
            console.error('[GenerativeStructuralFixEngine] LLM call failed:', error);
            return null;
        }
    }

    /**
     * Basic structural fix patterns (temporary until full LLM integration)
     * This handles the most common syntax issues deterministically
     */
    private static applyBasicStructuralFixes(prompt: string): string | null {
        // Extract the code section from the prompt
        const codeMatch = prompt.match(/---- CODE TO FIX ----\n([\s\S]*?)\n---- END CODE ----/);
        if (!codeMatch) return null;

        let code = codeMatch[1];

        // Common structural fixes
        // 1. Missing closing IIFE
        if (prompt.includes('})();') && !code.trim().endsWith('})();')) {
            if (code.includes('window.addEventListener') || code.includes('vscode.postMessage')) {
                code = code.trim() + '\n})();';
            }
        }

        // 2. Missing closing JSX tags
        if (prompt.includes('JSX') || prompt.includes('closing tag')) {
            // Find unclosed JSX elements and close them
            const jsxMatches = code.match(/<(\w+)[^>]*>/g);
            if (jsxMatches) {
                for (const match of jsxMatches) {
                    const tagName = match.match(/<(\w+)/)?.[1];
                    if (tagName && !code.includes(`</${tagName}>`)) {
                        const insertPos = code.lastIndexOf('</');
                        if (insertPos > -1) {
                            code = code.slice(0, insertPos) + `</${tagName}>\n` + code.slice(insertPos);
                        }
                    }
                }
            }
        }

        // 3. Missing closing braces/parentheses
        const openBraces = (code.match(/\{/g) || []).length;
        const closeBraces = (code.match(/\}/g) || []).length;
        if (openBraces > closeBraces) {
            code += '\n' + '}'.repeat(openBraces - closeBraces);
        }

        const openParens = (code.match(/\(/g) || []).length;
        const closeParens = (code.match(/\)/g) || []).length;
        if (openParens > closeParens) {
            code += ')'.repeat(openParens - closeParens);
        }

        return code;
    }

    /**
     * Validates that the generated code is reasonable
     */
    private static isValidCode(generatedCode: string, originalCode: string): boolean {
        // Basic sanity checks
        if (!generatedCode || generatedCode.trim().length === 0) {
            return false;
        }

        // Should be similar length (not drastically different)
        const lengthRatio = generatedCode.length / originalCode.length;
        if (lengthRatio < 0.5 || lengthRatio > 2.0) {
            return false;
        }

        // Should contain basic structural elements if original did
        if (originalCode.includes('function') && !generatedCode.includes('function')) {
            return false;
        }

        if (originalCode.includes('class') && !generatedCode.includes('class')) {
            return false;
        }

        // Should have balanced braces for JS/TS files
        const openBraces = (generatedCode.match(/\{/g) || []).length;
        const closeBraces = (generatedCode.match(/\}/g) || []).length;
        if (Math.abs(openBraces - closeBraces) > 1) {
            return false;
        }

        return true;
    }
}