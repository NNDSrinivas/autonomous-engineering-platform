import * as vscode from 'vscode';
import { RepoPatterns } from '../../context/patterns/RepoPatternExtractor';

/**
 * GenerativeRepairEngine - The core engine for Copilot-level auto-coding
 * 
 * Mental Model:
 * ❌ Old: Diagnostic → Proposal → Alternative → Patch
 * ✅ New: Broken Code → Reconstruct Intent → Generate Correct Code → Replace Region
 * 
 * Responsibilities:
 * - Works per file (not per diagnostic)
 * - Repairs entire broken regions holistically
 * - Produces one atomic patch
 * - Uses repo context + file context
 * - Zero user interaction required
 */
export class GenerativeRepairEngine {
    /**
     * Determines if this engine can handle the given diagnostics
     * We handle any error-level diagnostics that indicate broken code
     */
    static canHandle(diagnostics: vscode.Diagnostic[]): boolean {
        return diagnostics.some(d =>
            d.severity === vscode.DiagnosticSeverity.Error
        );
    }

    /**
     * Repair an entire file holistically - the core Copilot-like operation
     */
    static async repairFile(params: {
        uri: vscode.Uri;
        text: string;
        diagnostics: vscode.Diagnostic[];
        languageId: string;
        repoContext?: RepoContext;
    }): Promise<GenerativeRepairResult> {
        const { uri, text, diagnostics, languageId, repoContext } = params;

        const prompt = this.buildPrompt({
            filePath: uri.fsPath,
            languageId,
            fileText: text,
            diagnostics,
            repoContext
        });

        const fixedText = await this.callLLM({
            purpose: 'code-repair',
            temperature: 0, // Deterministic for code repair
            system: `You are a senior software engineer with expert knowledge in ${languageId}.

TASK: Fix the broken code file completely.

REQUIREMENTS:
- Return ONLY the fully corrected code
- Preserve original formatting style and architecture  
- Fix ALL syntax errors and compilation issues
- Maintain code intent and functionality
- Follow project conventions and patterns
- NO explanations, NO markdown, NO comments about changes

OUTPUT: The complete corrected file contents only.`,
            user: prompt
        });

        return {
            range: new vscode.Range(
                new vscode.Position(0, 0),
                new vscode.Position(Number.MAX_SAFE_INTEGER, 0)
            ),
            newText: this.normalizeFileContent(fixedText)
        };
    }

    /**
     * Build the LLM prompt for generative repair with repo-aware context
     */
    private static buildPrompt(params: {
        filePath: string;
        languageId: string;
        fileText: string;
        diagnostics: vscode.Diagnostic[];
        repoContext?: RepoContext;
    }): string {
        const { filePath, languageId, fileText, diagnostics, repoContext } = params;
        const patterns = repoContext?.patterns;

        let repoConventions = '';
        if (patterns) {
            repoConventions = `
Repository coding conventions (CRITICAL - follow these exactly):
- Language: ${patterns.language}
- Semicolons: ${patterns.formatting?.semicolons ? 'REQUIRED at end of statements' : 'NOT USED - omit semicolons'}
- Quotes: ${patterns.formatting?.quotes === 'single' ? 'ALWAYS use single quotes' : 'ALWAYS use double quotes'}
- Indentation: ${patterns.formatting?.indentation === 'spaces' ? `${patterns.formatting.indentSize || 2} spaces` : 'tabs'}
${patterns.frameworks && patterns.frameworks.length > 0 ? `- Frameworks in use: ${patterns.frameworks.join(', ')}` : ''}
${patterns.commonHooks && patterns.commonHooks.length > 0 ? `- Common React hooks: ${patterns.commonHooks.join(', ')}` : ''}
${patterns.commonImports && patterns.commonImports.length > 0 ? `- Common imports: ${patterns.commonImports.slice(0, 5).join(', ')}` : ''}

`;
        }

        return `File path: ${filePath}
Language: ${languageId}

${repoConventions}${repoContext ? `Repository context:
${repoContext.summary}

` : ''}Current errors in this file:
${diagnostics.map(d => `- Line ${d.range.start.line + 1}: ${d.message}`).join('\n')}

INSTRUCTIONS:
1. Fix ALL errors completely
2. Preserve original architecture and intent
3. Match repository conventions EXACTLY (semicolons, quotes, indentation)
4. Do not introduce new abstractions or refactor unless required to fix errors
5. Maintain existing patterns and coding style
6. Return ONLY the complete corrected file

The following ${languageId} file is BROKEN and needs complete repair:

\`\`\`${languageId}
${fileText}
\`\`\`

Fixed file:`;
    }    /**
     * Call LLM backend for code generation
     */
    private static async callLLM(params: {
        purpose: string;
        temperature: number;
        system: string;
        user: string;
    }): Promise<string> {
        // TODO: Integrate with NAVI backend LLM endpoint
        // For now, return a placeholder that would come from the LLM
        const response = await fetch('http://127.0.0.1:8000/api/navi/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Org-Id': 'default',
            },
            body: JSON.stringify({
                message: `${params.system}\n\n${params.user}`,
                attachments: [],
                workspace_root: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '',
                model: 'gpt-4o-mini', // Fast model for repairs
            }),
        });

        if (!response.ok) {
            throw new Error(`LLM request failed: ${response.status}`);
        }

        const result = await response.json() as any;
        return result.reply || result.content || '';
    }

    /**
     * Normalize file content for consistent application
     */
    private static normalizeFileContent(content: string): string {
        // Remove markdown code blocks if LLM wrapped the response
        let normalized = content.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, '');

        // Ensure consistent line ending
        normalized = normalized.replace(/\r\n/g, '\n');

        // Ensure file ends with single newline
        return normalized.trimEnd() + '\n';
    }
}

/**
 * Result from generative repair operation
 */
export interface GenerativeRepairResult {
    range: vscode.Range;
    newText: string;
}

/**
 * Repository context for informed repairs
 */
export interface RepoContext {
    summary: string;
    patterns?: RepoPatterns;
}