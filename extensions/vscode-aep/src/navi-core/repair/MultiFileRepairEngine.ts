import * as vscode from 'vscode';
import { RepoContext } from '../fix/generative/GenerativeRepairEngine';
import { RepairPlan } from './RepairPlanner';

/**
 * Result of multi-file repair operation
 */
export interface MultiFileRepairResult {
    success: boolean;
    repairedFiles: RepairedFileInfo[];
    totalDiagnosticsFixed: number;
    error?: string;
}

export interface RepairedFileInfo {
    uri: string;
    originalContent: string;
    repairedContent: string;
    diagnosticsFixed: number;
}

/**
 * MultiFileRepairEngine - Fixes multiple files coherently in one operation
 * 
 * Mental Model:
 * ❌ Old: Fix file A → Fix file B → Fix file C (fragmented, partial states)
 * ✅ New: Analyze all files → Generate coherent multi-file fix → Apply atomically
 * 
 * This is what makes NAVI handle cascaded errors like Copilot/Cline
 */
export class MultiFileRepairEngine {

    /**
     * Repair multiple files coherently using repository-aware context
     */
    static async repair(plan: RepairPlan, repoContext: RepoContext): Promise<MultiFileRepairResult> {
        try {
            console.log(`[MultiFileRepairEngine] Starting repair for ${plan.files.length} files`);

            // Load all file contents
            const filesContent = await this.loadFileContents(plan);

            // Generate coherent multi-file repair
            const repairedFiles = await this.generateCoherentRepair(filesContent, plan, repoContext);

            if (repairedFiles.length === 0) {
                return {
                    success: false,
                    repairedFiles: [],
                    totalDiagnosticsFixed: 0,
                    error: 'No repairs could be generated'
                };
            }

            const totalDiagnosticsFixed = plan.files.reduce((sum, f) => sum + f.diagnosticCount, 0);

            return {
                success: true,
                repairedFiles,
                totalDiagnosticsFixed
            };

        } catch (error) {
            console.log(`[MultiFileRepairEngine] Repair failed: ${error}`);
            return {
                success: false,
                repairedFiles: [],
                totalDiagnosticsFixed: 0,
                error: String(error)
            };
        }
    }

    /**
     * Load contents of all files in the repair plan
     */
    private static async loadFileContents(plan: RepairPlan): Promise<Array<{ uri: string, content: string, reason: string }>> {
        const filesContent = await Promise.all(
            plan.files.map(async fileInfo => {
                try {
                    const uri = vscode.Uri.parse(fileInfo.uri);
                    const document = await vscode.workspace.openTextDocument(uri);
                    return {
                        uri: fileInfo.uri,
                        content: document.getText(),
                        reason: fileInfo.reason
                    };
                } catch (error) {
                    console.log(`[MultiFileRepairEngine] Failed to load ${fileInfo.uri}: ${error}`);
                    return null;
                }
            })
        );

        return filesContent.filter(f => f !== null) as Array<{ uri: string, content: string, reason: string }>;
    }

    /**
     * Generate coherent repairs using LLM with full context
     */
    private static async generateCoherentRepair(
        filesContent: Array<{ uri: string, content: string, reason: string }>,
        plan: RepairPlan,
        repoContext: RepoContext
    ): Promise<RepairedFileInfo[]> {

        const prompt = this.buildMultiFileRepairPrompt(filesContent, plan, repoContext);

        // Call LLM for multi-file repair
        const llmResponse = await this.callLLMForRepair(prompt);

        // Parse LLM response into repaired files
        return this.parseRepairResponse(llmResponse, filesContent);
    }

    /**
     * Build comprehensive prompt for multi-file repair
     */
    private static buildMultiFileRepairPrompt(
        filesContent: Array<{ uri: string, content: string, reason: string }>,
        plan: RepairPlan,
        repoContext: RepoContext
    ): string {
        const patterns = repoContext.patterns;

        return `You are a senior software engineer fixing structural code errors.

REPOSITORY CONTEXT:
${repoContext.summary}

CODING CONVENTIONS (CRITICAL - follow exactly):
${patterns ? `- Language: ${patterns.language}
- Semicolons: ${patterns.formatting?.semicolons ? 'REQUIRED' : 'NOT USED'}
- Quotes: ${patterns.formatting?.quotes === 'single' ? 'ALWAYS single quotes' : 'ALWAYS double quotes'}  
- Indentation: ${patterns.formatting?.indentation === 'spaces' ? `${patterns.formatting.indentSize || 2} spaces` : 'tabs'}
${patterns.frameworks?.length ? `- Frameworks: ${patterns.frameworks.join(', ')}` : ''}
${patterns.commonHooks?.length ? `- React hooks: ${patterns.commonHooks.join(', ')}` : ''}` : '- Follow TypeScript/JavaScript best practices'}

REPAIR STRATEGY:
${plan.intent}

PRIORITY: ${plan.priority} (complexity: ${plan.estimatedComplexity}/10)

FILES TO REPAIR (${filesContent.length} total):

${filesContent.map(file => {
            const fileName = file.uri.split('/').pop();
            return `=== FILE: ${fileName} ===
Reason: ${file.reason}
Content:
\`\`\`
${file.content}
\`\`\`
`;
        }).join('\n')}

INSTRUCTIONS:
1. Fix ALL structural errors in each file
2. Ensure fixes are coherent across all files  
3. Follow repository conventions exactly
4. Maintain original architecture and intent
5. Do NOT explain - return ONLY the fixed files
6. Format response as: === FIXED: filename.ext ===\\nfixed content\\n

Return all fixed files:`;
    }

    /**
     * Call LLM backend for repair generation
     */
    private static async callLLMForRepair(prompt: string): Promise<string> {
        // For now, use the same backend as GenerativeRepairEngine
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
                model: 'gpt-4o', // Use more powerful model for multi-file repairs
            }),
        });

        if (!response.ok) {
            throw new Error(`LLM request failed: ${response.status}`);
        }

        const result = await response.json() as any;
        return result.reply || result.content || '';
    }

    /**
     * Parse LLM response into structured repair results
     */
    private static parseRepairResponse(
        llmResponse: string,
        originalFiles: Array<{ uri: string, content: string, reason: string }>
    ): RepairedFileInfo[] {
        const repairedFiles: RepairedFileInfo[] = [];

        // Parse response format: === FIXED: filename.ext ===\ncontent
        const filePattern = /=== FIXED: (.+?) ===\n([\s\S]*?)(?=\n=== FIXED:|$)/g;
        let match;

        while ((match = filePattern.exec(llmResponse)) !== null) {
            const filename = match[1].trim();
            const repairedContent = match[2].trim();

            // Find original file by filename
            const originalFile = originalFiles.find(f =>
                f.uri.endsWith(filename) || f.uri.includes(filename)
            );

            if (originalFile) {
                repairedFiles.push({
                    uri: originalFile.uri,
                    originalContent: originalFile.content,
                    repairedContent: repairedContent,
                    diagnosticsFixed: 1 // Will be updated based on actual diagnostics cleared
                });
            }
        }

        // If parsing failed, try fallback parsing
        if (repairedFiles.length === 0 && originalFiles.length === 1) {
            // Single file repair - use entire response as fixed content
            const cleaned = llmResponse.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, '');
            repairedFiles.push({
                uri: originalFiles[0].uri,
                originalContent: originalFiles[0].content,
                repairedContent: cleaned,
                diagnosticsFixed: 1
            });
        }

        return repairedFiles;
    }

    /**
     * Apply atomic WorkspaceEdit for all repairs
     */
    static async applyRepairs(repairs: RepairedFileInfo[]): Promise<boolean> {
        if (repairs.length === 0) return false;

        console.log(`[MultiFileRepairEngine] Applying atomic repairs to ${repairs.length} files`);

        // Build single atomic WorkspaceEdit
        const workspaceEdit = new vscode.WorkspaceEdit();

        for (const repair of repairs) {
            const uri = vscode.Uri.parse(repair.uri);

            try {
                const document = await vscode.workspace.openTextDocument(uri);

                // Replace entire file content
                const fullRange = new vscode.Range(
                    document.positionAt(0),
                    document.positionAt(document.getText().length)
                );

                workspaceEdit.replace(uri, fullRange, repair.repairedContent);

            } catch (error) {
                console.log(`[MultiFileRepairEngine] Failed to prepare edit for ${repair.uri}: ${error}`);
                return false;
            }
        }

        // Apply all changes atomically
        const success = await vscode.workspace.applyEdit(workspaceEdit);

        if (success) {
            console.log(`[MultiFileRepairEngine] Successfully applied atomic repairs`);

            // Save all modified files
            for (const repair of repairs) {
                try {
                    const uri = vscode.Uri.parse(repair.uri);
                    const document = await vscode.workspace.openTextDocument(uri);
                    await document.save();
                } catch (error) {
                    console.log(`[MultiFileRepairEngine] Failed to save ${repair.uri}: ${error}`);
                }
            }
        }

        return success;
    }
}