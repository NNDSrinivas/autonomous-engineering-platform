import * as vscode from 'vscode';
import { Intent } from '../intent/IntentClassifier';
import { IntentPlan } from '../intent/IntentPlanBuilder';
import { ResolvedPatterns } from '../context/RepoPatternResolver';

/**
 * Result of generative code operation
 */
export interface GenerativeCodeResult {
    success: boolean;
    files: GeneratedFileInfo[];
    summary: string;
    error?: string;
}

export interface GeneratedFileInfo {
    uri: string;
    content: string;
    operation: 'create' | 'modify' | 'delete';
    explanation: string;
}

/**
 * GenerativeCodeEngine - The Copilot Core for all engineering work
 * 
 * Mental Model:
 * ❌ Old: Separate engines for fixes, refactors, features
 * ✅ New: Unified engine that handles ALL engineering work with context
 * 
 * This is the same class that powers:
 * - Error fixes
 * - Refactoring
 * - Feature additions  
 * - Pattern conversions
 * - File creation
 * - Code optimization
 */
export class GenerativeCodeEngine {

    /**
     * Generate code for any engineering intent - the unified Copilot-like brain
     */
    static async generate(input: {
        intent: Intent;
        plan: IntentPlan;
        resolvedPatterns: ResolvedPatterns;
        files: Array<{ uri: string; content: string; }>;
        context?: string;
    }): Promise<GenerativeCodeResult> {

        try {
            console.log(`[GenerativeCodeEngine] Generating code for ${input.intent.type} intent`);

            const prompt = this.buildUnifiedPrompt(input);
            const llmResponse = await this.callLLM(prompt, input.intent);
            const parsedResult = this.parseResponse(llmResponse, input);

            return {
                success: true,
                files: parsedResult.files,
                summary: parsedResult.summary
            };

        } catch (error) {
            console.log(`[GenerativeCodeEngine] Generation failed: ${error}`);
            return {
                success: false,
                files: [],
                summary: 'Code generation failed',
                error: String(error)
            };
        }
    }

    /**
     * Build unified prompt for all types of engineering work
     * This is the prompt engineering that makes NAVI smart
     */
    private static buildUnifiedPrompt(input: {
        intent: Intent;
        plan: IntentPlan;
        resolvedPatterns: ResolvedPatterns;
        files: Array<{ uri: string; content: string; }>;
        context?: string;
    }): string {

        return `You are a senior software engineer working in a ${input.resolvedPatterns.language} repository.

REPOSITORY CONTEXT:
Framework: ${input.resolvedPatterns.framework || 'None'}
Architecture: ${input.resolvedPatterns.architecture}
Language: ${input.resolvedPatterns.language}

CODING CONVENTIONS (CRITICAL - follow exactly):
- File naming: ${input.resolvedPatterns.conventions.fileNaming}
- Folder structure: ${input.resolvedPatterns.conventions.folderStructure}
- Export style: ${input.resolvedPatterns.conventions.exportStyle}
- Type definitions: ${input.resolvedPatterns.conventions.typeDefinition}

REPOSITORY PATTERNS:
${this.formatPatterns(input.resolvedPatterns.patterns)}

${input.resolvedPatterns.examples ? `CODE EXAMPLES FROM THIS REPO:
${Object.entries(input.resolvedPatterns.examples).map(([key, example]) => `${key}:\n${example}`).join('\n\n')}` : ''}

USER INTENT: ${input.intent.type}
"${input.intent.raw}"

EXECUTION PLAN:
${input.plan.description}

RULES (follow ALL of these):
${input.plan.rules.map(rule => `- ${rule}`).join('\n')}

CONSTRAINTS (never violate these):
${input.plan.constraints.map(constraint => `- ${constraint}`).join('\n')}

APPROACH: ${input.plan.approach}
RISK LEVEL: ${input.plan.riskLevel}
EXPECTED FILES: ${input.plan.expectedFiles}

${input.context ? `ADDITIONAL CONTEXT:\n${input.context}\n` : ''}

CURRENT FILES:
${input.files.map(file => {
            const fileName = file.uri.split('/').pop() || 'unknown';
            return `=== FILE: ${fileName} ===\nPath: ${file.uri}\n\`\`\`\n${file.content}\n\`\`\``;
        }).join('\n\n')}

INSTRUCTIONS:
1. Understand the user intent: "${input.intent.raw}"
2. Follow the execution plan exactly
3. Apply repository patterns and conventions
4. Generate complete, working code
5. Format response as: === OPERATION: filename.ext ===\\noperation_type\\ncontent\\nexplanation

IMPORTANT:
- Return ONLY the code files that need changes
- Use repository conventions exactly (quotes, semicolons, indentation)
- Follow established patterns from the examples
- Maintain architectural consistency
- NO explanations outside the required format

Generate the files:`;
    }

    /**
     * Format patterns for prompt
     */
    private static formatPatterns(patterns: any): string {
        return Object.entries(patterns).map(([key, values]) => {
            if (Array.isArray(values) && values.length > 0) {
                return `- ${key}: ${values.join(', ')}`;
            }
            return '';
        }).filter(Boolean).join('\n');
    }

    /**
     * Call LLM with appropriate model selection based on intent
     */
    private static async callLLM(prompt: string, intent: Intent): Promise<string> {
        // Choose model based on intent complexity
        const model = this.selectModel(intent);

        const response = await fetch('http://127.0.0.1:8787/api/navi/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Org-Id': 'default',
            },
            body: JSON.stringify({
                message: prompt,
                attachments: [],
                workspace_root: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '',
                model,
            }),
        });

        if (!response.ok) {
            throw new Error(`LLM request failed: ${response.status}`);
        }

        const result = await response.json() as any;
        return result.reply || result.content || '';
    }

    /**
     * Select appropriate model based on intent complexity
     */
    private static selectModel(intent: Intent): string {
        switch (intent.type) {
            case 'FIX_ERRORS':
                return 'gpt-4o-mini'; // Fast model for fixes

            case 'CONVERT_PATTERN':
            case 'ADD_FEATURE':
                return 'gpt-4o'; // Powerful model for complex work

            case 'REFACTOR':
            case 'CREATE_FILE':
                return 'gpt-4o-mini'; // Balanced model

            default:
                return 'gpt-4o-mini';
        }
    }

    /**
     * Parse LLM response into structured result
     */
    private static parseResponse(llmResponse: string, input: any): { files: GeneratedFileInfo[], summary: string } {
        const files: GeneratedFileInfo[] = [];

        // Parse format: === OPERATION: filename.ext ===\noperation_type\ncontent\nexplanation
        const filePattern = /=== OPERATION: (.+?) ===\n(create|modify|delete)\n([\s\S]*?)(?=\n=== OPERATION:|$)/g;
        let match;
        let fileCount = 0;

        while ((match = filePattern.exec(llmResponse)) !== null && fileCount < 10) {
            const filename = match[1].trim();
            const operation = match[2] as 'create' | 'modify' | 'delete';
            const contentAndExplanation = match[3].trim();

            // Split content and explanation
            const parts = contentAndExplanation.split('\n---EXPLANATION---\n');
            const content = parts[0].trim();
            const explanation = parts[1] || `${operation === 'create' ? 'Created' : operation === 'modify' ? 'Modified' : 'Deleted'} ${filename}`;

            // Resolve full URI
            const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
            const fullUri = filename.startsWith('/') ? filename : `${workspaceRoot}/${filename}`;

            files.push({
                uri: fullUri,
                content: content.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, ''),
                operation,
                explanation
            });

            fileCount++;
        }

        // Fallback parsing for single file responses
        if (files.length === 0 && input.files.length === 1) {
            const cleaned = llmResponse.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, '');
            files.push({
                uri: input.files[0].uri,
                content: cleaned,
                operation: 'modify',
                explanation: `Applied ${input.intent.type.toLowerCase()} to file`
            });
        }

        const summary = this.generateSummary(input.intent, files);
        return { files, summary };
    }

    /**
     * Generate human-readable summary of changes
     */
    private static generateSummary(intent: Intent, files: GeneratedFileInfo[]): string {
        const operations = files.reduce((acc, file) => {
            acc[file.operation] = (acc[file.operation] || 0) + 1;
            return acc;
        }, {} as Record<string, number>);

        const parts = [];
        if (operations.create) parts.push(`created ${operations.create} file(s)`);
        if (operations.modify) parts.push(`modified ${operations.modify} file(s)`);
        if (operations.delete) parts.push(`deleted ${operations.delete} file(s)`);

        const operationSummary = parts.join(', ');
        const intentDescription = intent.type.toLowerCase().replace('_', ' ');

        return `Completed ${intentDescription}: ${operationSummary}`;
    }

    /**
     * Apply generated files to workspace
     */
    static async applyToWorkspace(result: GenerativeCodeResult): Promise<boolean> {
        if (!result.success || result.files.length === 0) {
            return false;
        }

        console.log(`[GenerativeCodeEngine] Applying ${result.files.length} file changes to workspace`);

        const workspaceEdit = new vscode.WorkspaceEdit();

        for (const file of result.files) {
            const uri = vscode.Uri.file(file.uri);

            switch (file.operation) {
                case 'create':
                    workspaceEdit.createFile(uri, { ignoreIfExists: true });
                    workspaceEdit.insert(uri, new vscode.Position(0, 0), file.content);
                    break;

                case 'modify':
                    try {
                        const document = await vscode.workspace.openTextDocument(uri);
                        const fullRange = new vscode.Range(
                            document.positionAt(0),
                            document.positionAt(document.getText().length)
                        );
                        workspaceEdit.replace(uri, fullRange, file.content);
                    } catch (error) {
                        // File might not exist, create it
                        workspaceEdit.createFile(uri, { ignoreIfExists: true });
                        workspaceEdit.insert(uri, new vscode.Position(0, 0), file.content);
                    }
                    break;

                case 'delete':
                    workspaceEdit.deleteFile(uri, { ignoreIfNotExists: true });
                    break;
            }
        }

        const success = await vscode.workspace.applyEdit(workspaceEdit);

        if (success) {
            // Save all modified files
            for (const file of result.files) {
                if (file.operation !== 'delete') {
                    try {
                        const uri = vscode.Uri.file(file.uri);
                        const document = await vscode.workspace.openTextDocument(uri);
                        await document.save();
                    } catch (error) {
                        console.log(`[GenerativeCodeEngine] Failed to save ${file.uri}: ${error}`);
                    }
                }
            }
        }

        return success;
    }
}