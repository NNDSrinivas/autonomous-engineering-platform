import * as vscode from 'vscode';
import * as path from 'path';

/**
 * Repository coding patterns and conventions
 * This is what makes NAVI contextually smart - understanding how THIS repo writes code
 */
export interface RepoPatterns {
    language: string;

    // Style conventions
    formatting?: {
        semicolons: boolean;
        quotes: 'single' | 'double';
        indentation: 'spaces' | 'tabs';
        indentSize?: number;
    };

    // Import patterns
    importsStyle?: 'relative' | 'absolute' | 'mixed';
    commonImports?: string[];

    // React patterns (if applicable)
    reactStyle?: 'function' | 'arrow' | 'class';
    commonHooks?: string[];
    stateManagement?: string[];

    // Architecture patterns
    fileNamingPattern?: 'camelCase' | 'kebab-case' | 'PascalCase';
    folderStructure?: string[];

    // Framework/library usage
    frameworks?: string[];
    testingPatterns?: string[];
}

/**
 * RepoPatternExtractor - Learns the "coding DNA" of the repository
 * 
 * This is what makes NAVI fix code "the way this repo would have written it"
 * instead of just applying generic fixes.
 */
export class RepoPatternExtractor {

    /**
     * Extract coding patterns from the current workspace
     * Analyzes up to 50 files to learn conventions quickly
     */
    static async extract(workspaceUri?: vscode.Uri): Promise<RepoPatterns> {
        const baseUri = workspaceUri || vscode.workspace.workspaceFolders?.[0]?.uri;
        if (!baseUri) {
            return this.getDefaultPatterns();
        }

        try {
            // Find relevant code files (excluding node_modules, build dirs)
            const files = await vscode.workspace.findFiles(
                new vscode.RelativePattern(baseUri, '**/*.{ts,tsx,js,jsx,py,java,go,rs}'),
                new vscode.RelativePattern(baseUri, '{node_modules,build,dist,out,target,__pycache__}/**'),
                50 // Limit for performance
            );

            if (files.length === 0) {
                return this.getDefaultPatterns();
            }

            return await this.analyzeFiles(files);

        } catch (error) {
            console.log(`[RepoPatternExtractor] Error extracting patterns: ${error}`);
            return this.getDefaultPatterns();
        }
    }

    /**
     * Analyze a collection of files to extract patterns
     */
    private static async analyzeFiles(files: vscode.Uri[]): Promise<RepoPatterns> {
        const patterns: RepoPatterns = {
            language: 'typescript',
            formatting: { semicolons: true, quotes: 'single', indentation: 'spaces', indentSize: 2 },
            commonImports: [],
            frameworks: [],
            commonHooks: []
        };

        let semicolonCount = 0;
        let noSemicolonCount = 0;
        let singleQuoteCount = 0;
        let doubleQuoteCount = 0;
        let spacesCount = 0;
        let tabsCount = 0;

        const importPatterns = new Set<string>();
        const hookPatterns = new Set<string>();
        const frameworkPatterns = new Set<string>();

        for (const file of files.slice(0, 20)) { // Analyze first 20 files for speed
            try {
                const document = await vscode.workspace.openTextDocument(file);
                const text = document.getText();
                const lines = text.split('\n');

                // Detect primary language
                const ext = path.extname(file.fsPath).toLowerCase();
                if (ext === '.ts' || ext === '.tsx') {
                    patterns.language = 'typescript';
                } else if (ext === '.js' || ext === '.jsx') {
                    patterns.language = 'javascript';
                } else if (ext === '.py') {
                    patterns.language = 'python';
                }

                // Analyze formatting patterns
                this.analyzeSemicolons(text, ref => {
                    semicolonCount += ref.withSemicolon;
                    noSemicolonCount += ref.withoutSemicolon;
                });

                this.analyzeQuotes(text, ref => {
                    singleQuoteCount += ref.single;
                    doubleQuoteCount += ref.double;
                });

                this.analyzeIndentation(lines, ref => {
                    spacesCount += ref.spaces;
                    tabsCount += ref.tabs;
                });

                // Analyze import patterns
                this.analyzeImports(text, imports => {
                    imports.forEach(imp => importPatterns.add(imp));
                });

                // Analyze React patterns (if applicable)
                if (ext === '.tsx' || ext === '.jsx') {
                    this.analyzeReactPatterns(text, hooks => {
                        hooks.forEach(hook => hookPatterns.add(hook));
                    });
                }

                // Detect frameworks
                this.analyzeFrameworks(text, frameworks => {
                    frameworks.forEach(fw => frameworkPatterns.add(fw));
                });

            } catch (error) {
                console.log(`[RepoPatternExtractor] Error analyzing file ${file.fsPath}: ${error}`);
                continue;
            }
        }

        // Determine patterns based on analysis
        patterns.formatting = {
            semicolons: semicolonCount >= noSemicolonCount,
            quotes: singleQuoteCount >= doubleQuoteCount ? 'single' : 'double',
            indentation: spacesCount >= tabsCount ? 'spaces' : 'tabs',
            indentSize: 2 // Default, could be analyzed further
        };

        patterns.commonImports = Array.from(importPatterns).slice(0, 10);
        patterns.commonHooks = Array.from(hookPatterns).slice(0, 10);
        patterns.frameworks = Array.from(frameworkPatterns).slice(0, 5);

        return patterns;
    }

    /**
     * Analyze semicolon usage patterns
     */
    private static analyzeSemicolons(text: string, callback: (ref: { withSemicolon: number, withoutSemicolon: number }) => void): void {
        const lines = text.split('\n');
        let withSemicolon = 0;
        let withoutSemicolon = 0;

        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed && !trimmed.startsWith('//') && !trimmed.startsWith('/*')) {
                if (trimmed.endsWith(';')) {
                    withSemicolon++;
                } else if (trimmed.match(/^(const|let|var|return|throw|break|continue)/)) {
                    withoutSemicolon++;
                }
            }
        }

        callback({ withSemicolon, withoutSemicolon });
    }

    /**
     * Analyze quote usage patterns
     */
    private static analyzeQuotes(text: string, callback: (ref: { single: number, double: number }) => void): void {
        const singleQuotes = (text.match(/'/g) || []).length;
        const doubleQuotes = (text.match(/"/g) || []).length;
        callback({ single: singleQuotes, double: doubleQuotes });
    }

    /**
     * Analyze indentation patterns
     */
    private static analyzeIndentation(lines: string[], callback: (ref: { spaces: number, tabs: number }) => void): void {
        let spaces = 0;
        let tabs = 0;

        for (const line of lines) {
            if (line.startsWith('  ')) spaces++;
            if (line.startsWith('\t')) tabs++;
        }

        callback({ spaces, tabs });
    }

    /**
     * Analyze import patterns
     */
    private static analyzeImports(text: string, callback: (imports: string[]) => void): void {
        const imports: string[] = [];
        const importRegex = /import\s+.*?\s+from\s+['"]([^'"]+)['"]/g;
        let match;

        while ((match = importRegex.exec(text)) !== null) {
            imports.push(match[1]);
        }

        callback(imports);
    }

    /**
     * Analyze React patterns and hooks
     */
    private static analyzeReactPatterns(text: string, callback: (hooks: string[]) => void): void {
        const hooks: string[] = [];
        const hookRegex = /use[A-Z][a-zA-Z]*/g;
        let match;

        while ((match = hookRegex.exec(text)) !== null) {
            hooks.push(match[0]);
        }

        callback(hooks);
    }

    /**
     * Analyze framework usage
     */
    private static analyzeFrameworks(text: string, callback: (frameworks: string[]) => void): void {
        const frameworks: string[] = [];

        if (text.includes('React.') || text.includes('from \'react\'')) frameworks.push('React');
        if (text.includes('Vue.') || text.includes('from \'vue\'')) frameworks.push('Vue');
        if (text.includes('useState') || text.includes('useEffect')) frameworks.push('React Hooks');
        if (text.includes('express') || text.includes('app.get')) frameworks.push('Express');
        if (text.includes('FastAPI') || text.includes('@app.')) frameworks.push('FastAPI');

        callback(frameworks);
    }

    /**
     * Default patterns when extraction fails
     */
    private static getDefaultPatterns(): RepoPatterns {
        return {
            language: 'typescript',
            formatting: {
                semicolons: true,
                quotes: 'single',
                indentation: 'spaces',
                indentSize: 2
            },
            commonImports: [],
            frameworks: [],
            commonHooks: []
        };
    }
}