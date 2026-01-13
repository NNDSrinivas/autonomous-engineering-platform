import * as vscode from 'vscode';
import * as path from 'path';
import fg from 'fast-glob';
import { NaviClient } from './NaviClient';

export interface FileNode {
    name: string;
    path: string;
    type: 'file' | 'directory';
    children?: FileNode[];
    language?: string;
    size?: number;
}

export interface EditorContext {
    currentFile: string;
    language: string;
    selection?: {
        text: string;
        range: {
            start: { line: number; character: number };
            end: { line: number; character: number };
        };
    };
    surroundingCode: {
        before: string;
        after: string;
    };
    imports: string[];
    dependencies: string[];
    relatedFiles: string[];
}

export interface WorkspaceContext {
    rootPath: string;
    fileTree: FileNode[];
    packageJson?: any;
    readme?: string;
    gitBranch?: string;
    technologies: string[];
    totalFiles: number;
    totalSize: number;
}

export class ContextService {
    private client: NaviClient;
    private indexCache: Map<string, any> = new Map();
    private fileWatcher?: vscode.FileSystemWatcher;
    private maxSearchFiles: number = 100; // Default limit, configurable
    private maxMatchesPerFile: number = 5; // Default limit
    private maxSearchResults: number = 20; // Default limit

    constructor(client: NaviClient, options?: {
        maxSearchFiles?: number;
        maxMatchesPerFile?: number;
        maxSearchResults?: number;
    }) {
        this.client = client;
        if (options) {
            this.maxSearchFiles = options.maxSearchFiles ?? 100;
            this.maxMatchesPerFile = options.maxMatchesPerFile ?? 5;
            this.maxSearchResults = options.maxSearchResults ?? 20;
        }
        this.setupFileWatcher();
    }

    /**
     * Index the entire workspace
     */
    async indexWorkspace(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            return;
        }

        const rootPath = workspaceFolders[0].uri.fsPath;

        try {
            // Get all files (excluding common ignore patterns)
            const files = await fg('**/*', {
                cwd: rootPath,
                ignore: [
                    '**/node_modules/**',
                    '**/dist/**',
                    '**/build/**',
                    '**/.git/**',
                    '**/out/**',
                    '**/__pycache__/**',
                    '**/*.pyc',
                    '**/venv/**',
                    '**/.venv/**'
                ],
                dot: false,
                onlyFiles: true
            });

            // Cache file list
            this.indexCache.set('files', files);

            // Detect technologies
            const technologies = await this.detectTechnologies(rootPath, files);
            this.indexCache.set('technologies', technologies);

            // Read package.json if exists
            try {
                const packagePath = path.join(rootPath, 'package.json');
                const packageContent = await vscode.workspace.fs.readFile(vscode.Uri.file(packagePath));
                const packageJson = JSON.parse(Buffer.from(packageContent).toString('utf8'));
                this.indexCache.set('packageJson', packageJson);
            } catch {
                // package.json doesn't exist or can't be read
            }

            // Read README if exists
            try {
                const readmePath = path.join(rootPath, 'README.md');
                const readmeContent = await vscode.workspace.fs.readFile(vscode.Uri.file(readmePath));
                const readme = Buffer.from(readmeContent).toString('utf8');
                this.indexCache.set('readme', readme);
            } catch {
                // README doesn't exist
            }

            console.log(`Indexed ${files.length} files with technologies: ${technologies.join(', ')}`);
        } catch (error) {
            console.error('Failed to index workspace:', error);
        }
    }

    /**
     * Get context for the current editor
     */
    async getEditorContext(editor: vscode.TextEditor): Promise<EditorContext> {
        const document = editor.document;
        const position = editor.selection.active;

        // Get selection if any
        let selection;
        if (!editor.selection.isEmpty) {
            selection = {
                text: document.getText(editor.selection),
                range: {
                    start: {
                        line: editor.selection.start.line,
                        character: editor.selection.start.character
                    },
                    end: {
                        line: editor.selection.end.line,
                        character: editor.selection.end.character
                    }
                }
            };
        }

        // Get surrounding code (5 lines before and after)
        const beforeRange = new vscode.Range(
            Math.max(0, position.line - 5),
            0,
            position.line,
            0
        );
        const afterRange = new vscode.Range(
            position.line,
            0,
            Math.min(document.lineCount - 1, position.line + 5),
            document.lineAt(Math.min(document.lineCount - 1, position.line + 5)).text.length
        );

        const surroundingCode = {
            before: document.getText(beforeRange),
            after: document.getText(afterRange)
        };

        // Extract imports
        const imports = this.extractImports(document);

        // Get dependencies from package.json
        const dependencies = this.getDependencies();

        // Find related files
        const relatedFiles = await this.findRelatedFiles(document.fileName);

        return {
            currentFile: document.fileName,
            language: document.languageId,
            selection,
            surroundingCode,
            imports,
            dependencies,
            relatedFiles
        };
    }

    /**
     * Get workspace-level context
     */
    async getWorkspaceContext(): Promise<WorkspaceContext> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            throw new Error('No workspace folder open');
        }

        const rootPath = workspaceFolders[0].uri.fsPath;
        const files = this.indexCache.get('files') || [];
        const fileTree = await this.buildFileTree(rootPath);

        // Get git branch
        let gitBranch: string | undefined;
        try {
            const git = vscode.extensions.getExtension('vscode.git')?.exports;
            if (git) {
                const repositories = git.getAPI(1).repositories;
                if (repositories.length > 0) {
                    gitBranch = repositories[0].state.HEAD?.name;
                }
            }
        } catch {
            // Git not available
        }

        // Calculate total size
        let totalSize = 0;
        for (const file of files) {
            try {
                const filePath = path.join(rootPath, file);
                const stat = await vscode.workspace.fs.stat(vscode.Uri.file(filePath));
                totalSize += stat.size;
            } catch {
                // Skip files that can't be stat'd
            }
        }

        return {
            rootPath,
            fileTree,
            packageJson: this.indexCache.get('packageJson'),
            readme: this.indexCache.get('readme'),
            gitBranch,
            technologies: this.indexCache.get('technologies') || [],
            totalFiles: files.length,
            totalSize
        };
    }

    /**
     * Search code in workspace
     */
    async searchCode(query: string): Promise<Array<{file: string; matches: Array<{line: number; text: string}>}>> {
        const results: Array<{file: string; matches: Array<{line: number; text: string}>}> = [];
        const files = this.indexCache.get('files') || [];
        const rootPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;

        if (!rootPath) {
            return results;
        }

        // Search in cached files
        for (const file of files.slice(0, this.maxSearchFiles)) {
            try {
                const filePath = path.join(rootPath, file);
                const content = await vscode.workspace.fs.readFile(vscode.Uri.file(filePath));
                const text = Buffer.from(content).toString('utf8');
                const lines = text.split('\n');

                const matches: Array<{line: number; text: string}> = [];
                lines.forEach((line, idx) => {
                    if (line.toLowerCase().includes(query.toLowerCase())) {
                        matches.push({ line: idx + 1, text: line.trim() });
                    }
                });

                if (matches.length > 0) {
                    results.push({ file, matches: matches.slice(0, this.maxMatchesPerFile) });
                }
            } catch {
                // Skip files that can't be read
            }
        }

        return results.slice(0, this.maxSearchResults);
    }

    /**
     * Get file tree structure
     */
    async getFileTree(): Promise<FileNode[]> {
        const rootPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!rootPath) {
            return [];
        }

        return this.buildFileTree(rootPath);
    }

    /**
     * Get dependencies for a file
     */
    async getDependenciesForFile(filePath: string): Promise<string[]> {
        try {
            const uri = vscode.Uri.file(filePath);
            const content = await vscode.workspace.fs.readFile(uri);
            const text = Buffer.from(content).toString('utf8');
            const document = await vscode.workspace.openTextDocument(uri);

            return this.extractImports(document);
        } catch {
            return [];
        }
    }

    /**
     * Private helper methods
     */

    private setupFileWatcher(): void {
        this.fileWatcher = vscode.workspace.createFileSystemWatcher('**/*');

        this.fileWatcher.onDidChange(() => {
            // Debounce and re-index
            this.debounceReindex();
        });

        this.fileWatcher.onDidCreate(() => {
            this.debounceReindex();
        });

        this.fileWatcher.onDidDelete(() => {
            this.debounceReindex();
        });
    }

    private debounceTimer?: NodeJS.Timeout;
    private debounceReindex(): void {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        this.debounceTimer = setTimeout(() => {
            this.indexWorkspace();
        }, 2000); // Re-index after 2 seconds of no changes
    }

    private async detectTechnologies(rootPath: string, files: string[]): Promise<string[]> {
        const technologies = new Set<string>();

        // Check for framework/tool indicators
        const indicators: Record<string, string[]> = {
            'React': ['package.json:react', 'tsconfig.json', 'jsx', 'tsx'],
            'Vue': ['package.json:vue', 'vue'],
            'Angular': ['package.json:@angular', 'angular.json'],
            'Node.js': ['package.json', 'node_modules'],
            'Python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'py'],
            'TypeScript': ['tsconfig.json', 'ts', 'tsx'],
            'JavaScript': ['js', 'jsx'],
            'Java': ['pom.xml', 'build.gradle', 'java'],
            'Go': ['go.mod', 'go'],
            'Rust': ['Cargo.toml', 'rs'],
            'Docker': ['Dockerfile', 'docker-compose.yml'],
            'Kubernetes': ['k8s/', 'deployment.yaml']
        };

        for (const [tech, patterns] of Object.entries(indicators)) {
            for (const pattern of patterns) {
                if (pattern.includes(':')) {
                    // Check package.json dependency
                    const [file, dep] = pattern.split(':');
                    if (files.includes(file)) {
                        try {
                            const packagePath = path.join(rootPath, file);
                            const content = await vscode.workspace.fs.readFile(vscode.Uri.file(packagePath));
                            const pkg = JSON.parse(Buffer.from(content).toString('utf8'));
                            if (pkg.dependencies?.[dep] || pkg.devDependencies?.[dep]) {
                                technologies.add(tech);
                            }
                        } catch {}
                    }
                } else if (files.some(f => f.includes(pattern))) {
                    technologies.add(tech);
                }
            }
        }

        return Array.from(technologies);
    }

    private async buildFileTree(rootPath: string, maxDepth: number = 3): Promise<FileNode[]> {
        const buildTree = async (dirPath: string, depth: number = 0): Promise<FileNode[]> => {
            if (depth >= maxDepth) {
                return [];
            }

            try {
                const entries = await vscode.workspace.fs.readDirectory(vscode.Uri.file(dirPath));
                const nodes: FileNode[] = [];

                for (const [name, type] of entries) {
                    // Skip common ignore patterns
                    if (name === 'node_modules' || name === '.git' || name === 'dist' || name === 'build') {
                        continue;
                    }

                    const fullPath = path.join(dirPath, name);
                    const relativePath = path.relative(rootPath, fullPath);

                    if (type === vscode.FileType.Directory) {
                        const children = await buildTree(fullPath, depth + 1);
                        nodes.push({
                            name,
                            path: relativePath,
                            type: 'directory',
                            children
                        });
                    } else {
                        const language = this.getLanguageFromFile(name);
                        nodes.push({
                            name,
                            path: relativePath,
                            type: 'file',
                            language
                        });
                    }
                }

                return nodes.sort((a, b) => {
                    if (a.type === b.type) {
                        return a.name.localeCompare(b.name);
                    }
                    return a.type === 'directory' ? -1 : 1;
                });
            } catch {
                return [];
            }
        };

        return buildTree(rootPath);
    }

    private extractImports(document: vscode.TextDocument): string[] {
        const imports: string[] = [];
        const text = document.getText();

        // JavaScript/TypeScript imports
        const jsImportRegex = /import .* from ['"](.+)['"]/g;
        let match;
        while ((match = jsImportRegex.exec(text)) !== null) {
            imports.push(match[1]);
        }

        // Python imports
        const pyImportRegex = /(?:from|import) ([\w.]+)/g;
        while ((match = pyImportRegex.exec(text)) !== null) {
            imports.push(match[1]);
        }

        return imports;
    }

    private getDependencies(): string[] {
        const packageJson = this.indexCache.get('packageJson');
        if (!packageJson) {
            return [];
        }

        const deps = [
            ...Object.keys(packageJson.dependencies || {}),
            ...Object.keys(packageJson.devDependencies || {})
        ];

        return deps;
    }

    private async findRelatedFiles(currentFile: string): Promise<string[]> {
        const related: string[] = [];
        const baseName = path.basename(currentFile, path.extname(currentFile));
        const dir = path.dirname(currentFile);
        const files = this.indexCache.get('files') || [];

        // Find test files
        for (const file of files) {
            if (file.includes(baseName) &&
                (file.includes('.test.') || file.includes('.spec.') || file.includes('__tests__'))) {
                related.push(file);
            }
        }

        // Find same name different extension
        const extensions = ['.ts', '.tsx', '.js', '.jsx', '.css', '.scss', '.test.ts', '.spec.ts'];
        for (const ext of extensions) {
            const possibleFile = path.join(dir, baseName + ext);
            if (files.includes(path.relative(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '', possibleFile))) {
                related.push(possibleFile);
            }
        }

        return related;
    }

    private getLanguageFromFile(fileName: string): string | undefined {
        const ext = path.extname(fileName).toLowerCase();
        const languageMap: Record<string, string> = {
            '.ts': 'typescript',
            '.tsx': 'typescriptreact',
            '.js': 'javascript',
            '.jsx': 'javascriptreact',
            '.py': 'python',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.css': 'css',
            '.html': 'html',
            '.json': 'json',
            '.md': 'markdown'
        };

        return languageMap[ext];
    }

    dispose(): void {
        this.fileWatcher?.dispose();
        this.indexCache.clear();
    }
}
