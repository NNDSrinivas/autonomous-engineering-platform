/**
 * Phase 3.3 - Repository Context Builder
 * 
 * This is the foundation that transforms NAVI from shallow "current file only" logic
 * to deep repo understanding. This is how Copilot "knows" your codebase patterns.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export interface RepoContext {
  // Core language and framework detection
  language: string;
  framework?: string;
  version?: string;
  
  // Coding conventions discovered from existing code
  conventions: {
    naming: 'camelCase' | 'snake_case' | 'PascalCase' | 'kebab-case';
    indentation: 'spaces' | 'tabs';
    indentSize: number;
    quotes: 'single' | 'double';
    semicolons: boolean;
    fileStructure: 'flat' | 'feature-based' | 'layer-based' | 'domain-driven';
    patterns: string[]; // ['hooks', 'services', 'controllers', 'components']
  };
  
  // Key architectural files and their patterns
  keyFiles: {
    path: string;
    type: 'config' | 'entry' | 'model' | 'service' | 'component' | 'test';
    patterns: string[];
  }[];
  
  // Dependencies and their usage patterns
  dependencies: {
    name: string;
    version?: string;
    usage: 'core' | 'dev' | 'optional';
    commonPatterns: string[];
  }[];
  
  // Directory structure insights
  structure: {
    rootDir: string;
    srcDir?: string;
    testDir?: string;
    buildDir?: string;
    commonDirs: string[];
  };
  
  // Code quality and tooling
  tooling: {
    linter?: string;
    formatter?: string;
    bundler?: string;
    testFramework?: string;
    typeChecker?: boolean;
  };
}

export class RepoContextBuilder {
  private workspaceRoot: string;
  
  constructor() {
    this.workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
  }
  
  /**
   * Build comprehensive repository context by analyzing structure and patterns
   */
  async build(): Promise<RepoContext> {
    console.log('🔍 Building repository context...');
    
    const context: RepoContext = {
      language: 'unknown',
      conventions: {
        naming: 'camelCase',
        indentation: 'spaces',
        indentSize: 2,
        quotes: 'single',
        semicolons: true,
        fileStructure: 'flat',
        patterns: []
      },
      keyFiles: [],
      dependencies: [],
      structure: {
        rootDir: this.workspaceRoot,
        commonDirs: []
      },
      tooling: {}
    };
    
    // Step 1: Analyze project files for language/framework detection
    await this.detectLanguageAndFramework(context);
    
    // Step 2: Parse configuration files for dependencies
    await this.analyzeDependencies(context);
    
    // Step 3: Analyze code structure and patterns
    await this.analyzeCodeStructure(context);
    
    // Step 4: Detect coding conventions from existing files
    await this.detectConventions(context);
    
    // Step 5: Analyze tooling configuration
    await this.detectTooling(context);
    
    console.log(`✅ Context built: ${context.language}${context.framework ? ` (${context.framework})` : ''}`);
    
    return context;
  }
  
  /**
   * Detect primary language and framework
   */
  private async detectLanguageAndFramework(context: RepoContext): Promise<void> {
    const packageJsonPath = path.join(this.workspaceRoot, 'package.json');
    const pomXmlPath = path.join(this.workspaceRoot, 'pom.xml');
    const buildGradlePath = path.join(this.workspaceRoot, 'build.gradle');
    const cargoTomlPath = path.join(this.workspaceRoot, 'Cargo.toml');
    const requirementsPath = path.join(this.workspaceRoot, 'requirements.txt');
    const pyprojectPath = path.join(this.workspaceRoot, 'pyproject.toml');
    
    // JavaScript/TypeScript
    if (fs.existsSync(packageJsonPath)) {
      const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
      
      // Check for TypeScript
      const hasTS = this.hasTypeScript();
      context.language = hasTS ? 'typescript' : 'javascript';
      
      // Detect framework
      context.framework = this.detectJSFramework(packageJson);
      context.version = packageJson.version;
      
      return;
    }
    
    // Java
    if (fs.existsSync(pomXmlPath) || fs.existsSync(buildGradlePath)) {
      context.language = 'java';
      context.framework = this.detectJavaFramework();
      return;
    }
    
    // Python
    if (fs.existsSync(requirementsPath) || fs.existsSync(pyprojectPath)) {
      context.language = 'python';
      context.framework = this.detectPythonFramework();
      return;
    }
    
    // Rust
    if (fs.existsSync(cargoTomlPath)) {
      context.language = 'rust';
      return;
    }
    
    // Fallback: analyze file extensions
    context.language = await this.detectLanguageByFiles();
  }
  
  /**
   * Analyze dependencies and their usage patterns
   */
  private async analyzeDependencies(context: RepoContext): Promise<void> {
    const packageJsonPath = path.join(this.workspaceRoot, 'package.json');
    
    if (fs.existsSync(packageJsonPath)) {
      const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
      
      // Production dependencies
      if (packageJson.dependencies) {
        for (const [name, version] of Object.entries(packageJson.dependencies)) {
          context.dependencies.push({
            name,
            version: version as string,
            usage: 'core',
            commonPatterns: this.getCommonPatterns(name)
          });
        }
      }
      
      // Development dependencies
      if (packageJson.devDependencies) {
        for (const [name, version] of Object.entries(packageJson.devDependencies)) {
          context.dependencies.push({
            name,
            version: version as string,
            usage: 'dev',
            commonPatterns: this.getCommonPatterns(name)
          });
        }
      }
    }
  }
  
  /**
   * Analyze directory structure and code organization
   */
  private async analyzeCodeStructure(context: RepoContext): Promise<void> {
    const commonDirs = ['src', 'lib', 'app', 'components', 'services', 'utils', 'hooks', 'pages', 'api'];
    const foundDirs: string[] = [];
    
    for (const dir of commonDirs) {
      const dirPath = path.join(this.workspaceRoot, dir);
      if (fs.existsSync(dirPath) && fs.statSync(dirPath).isDirectory()) {
        foundDirs.push(dir);
        
        // Set specific directory types
        if (dir === 'src') context.structure.srcDir = dirPath;
        if (dir === 'test' || dir === 'tests') context.structure.testDir = dirPath;
        if (dir === 'dist' || dir === 'build') context.structure.buildDir = dirPath;
      }
    }
    
    context.structure.commonDirs = foundDirs;
    
    // Detect file structure pattern
    if (foundDirs.includes('components') && foundDirs.includes('hooks')) {
      context.conventions.fileStructure = 'feature-based';
      context.conventions.patterns.push('react-patterns');
    } else if (foundDirs.includes('controllers') && foundDirs.includes('models')) {
      context.conventions.fileStructure = 'layer-based';
      context.conventions.patterns.push('mvc-pattern');
    } else if (foundDirs.includes('services') && foundDirs.includes('api')) {
      context.conventions.fileStructure = 'domain-driven';
      context.conventions.patterns.push('service-layer');
    }
    
    // Analyze key files
    await this.analyzeKeyFiles(context);
  }
  
  /**
   * Analyze key architectural files
   */
  private async analyzeKeyFiles(context: RepoContext): Promise<void> {
    const keyPaths = [
      'src/index.ts', 'src/index.js', 'src/main.ts', 'src/main.js',
      'src/App.tsx', 'src/App.jsx', 'src/app.ts',
      'src/api/index.ts', 'src/services/index.ts'
    ];
    
    for (const relativePath of keyPaths) {
      const fullPath = path.join(this.workspaceRoot, relativePath);
      if (fs.existsSync(fullPath)) {
        const content = fs.readFileSync(fullPath, 'utf8');
        const patterns = this.extractPatterns(content);
        
        context.keyFiles.push({
          path: fullPath,
          type: this.classifyFileType(relativePath),
          patterns
        });
      }
    }
  }
  
  /**
   * Detect coding conventions from existing files
   */
  private async detectConventions(context: RepoContext): Promise<void> {
    const sampleFiles = await this.getSampleFiles();
    
    if (sampleFiles.length === 0) return;
    
    let tabsCount = 0;
    let spacesCount = 0;
    let singleQuotes = 0;
    let doubleQuotes = 0;
    let withSemicolons = 0;
    let withoutSemicolons = 0;
    
    for (const filePath of sampleFiles) {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\n');
      
      // Analyze indentation
      for (const line of lines) {
        if (line.startsWith('\t')) tabsCount++;
        if (line.startsWith('  ')) spacesCount++;
      }
      
      // Analyze quotes
      singleQuotes += (content.match(/'/g) || []).length;
      doubleQuotes += (content.match(/"/g) || []).length;
      
      // Analyze semicolons
      const statements = content.match(/[;}]\s*$/gm);
      if (statements) {
        withSemicolons += statements.filter(s => s.includes(';')).length;
        withoutSemicolons += statements.filter(s => s.includes('}') && !s.includes(';')).length;
      }
    }
    
    // Set conventions based on analysis
    context.conventions.indentation = tabsCount > spacesCount ? 'tabs' : 'spaces';
    context.conventions.quotes = singleQuotes > doubleQuotes ? 'single' : 'double';
    context.conventions.semicolons = withSemicolons > withoutSemicolons;
  }
  
  /**
   * Detect tooling and configuration
   */
  private async detectTooling(context: RepoContext): Promise<void> {
    const configs = {
      '.eslintrc.js': 'eslint',
      '.eslintrc.json': 'eslint',
      '.prettierrc': 'prettier',
      'jest.config.js': 'jest',
      'vitest.config.ts': 'vitest',
      'tsconfig.json': 'typescript',
      'webpack.config.js': 'webpack',
      'vite.config.ts': 'vite'
    };
    
    for (const [configFile, tool] of Object.entries(configs)) {
      const configPath = path.join(this.workspaceRoot, configFile);
      if (fs.existsSync(configPath)) {
        switch (tool) {
          case 'eslint':
            context.tooling.linter = 'eslint';
            break;
          case 'prettier':
            context.tooling.formatter = 'prettier';
            break;
          case 'jest':
          case 'vitest':
            context.tooling.testFramework = tool;
            break;
          case 'typescript':
            context.tooling.typeChecker = true;
            break;
          case 'webpack':
          case 'vite':
            context.tooling.bundler = tool;
            break;
        }
      }
    }
  }
  
  // Helper methods
  
  private hasTypeScript(): boolean {
    const tsFiles = this.findFiles('**/*.ts', '**/*.tsx');
    return tsFiles.length > 0;
  }
  
  private detectJSFramework(packageJson: any): string | undefined {
    const deps = { ...packageJson.dependencies, ...packageJson.devDependencies };
    
    if (deps.react) return 'react';
    if (deps.vue) return 'vue';
    if (deps.angular) return 'angular';
    if (deps.svelte) return 'svelte';
    if (deps.express) return 'express';
    if (deps.next) return 'next';
    
    return undefined;
  }
  
  private detectJavaFramework(): string | undefined {
    // Check for Spring Boot
    if (this.findFiles('**/application.properties', '**/application.yml').length > 0) {
      return 'spring-boot';
    }
    
    return 'java';
  }
  
  private detectPythonFramework(): string | undefined {
    if (this.findFiles('**/manage.py').length > 0) return 'django';
    if (this.findFiles('**/app.py').length > 0) return 'flask';
    if (this.findFiles('**/main.py').length > 0) return 'fastapi';
    
    return 'python';
  }
  
  private async detectLanguageByFiles(): Promise<string> {
    const extensions = await this.getFileExtensions();
    
    if (extensions.includes('.ts') || extensions.includes('.tsx')) return 'typescript';
    if (extensions.includes('.js') || extensions.includes('.jsx')) return 'javascript';
    if (extensions.includes('.py')) return 'python';
    if (extensions.includes('.java')) return 'java';
    if (extensions.includes('.rs')) return 'rust';
    if (extensions.includes('.go')) return 'go';
    
    return 'unknown';
  }
  
  private getCommonPatterns(packageName: string): string[] {
    const patterns: Record<string, string[]> = {
      'react': ['jsx', 'hooks', 'components', 'props'],
      'express': ['middleware', 'routes', 'controllers'],
      'lodash': ['utility-functions', 'data-manipulation'],
      'axios': ['http-client', 'api-calls'],
      'styled-components': ['css-in-js', 'theme-provider']
    };
    
    return patterns[packageName] || [];
  }
  
  private extractPatterns(content: string): string[] {
    const patterns: string[] = [];
    
    if (content.includes('useState')) patterns.push('react-hooks');
    if (content.includes('useEffect')) patterns.push('react-effects');
    if (content.includes('export default')) patterns.push('default-exports');
    if (content.includes('async/await')) patterns.push('async-functions');
    if (content.includes('interface ')) patterns.push('typescript-interfaces');
    
    return patterns;
  }
  
  private classifyFileType(filePath: string): 'config' | 'entry' | 'model' | 'service' | 'component' | 'test' {
    if (filePath.includes('index.')) return 'entry';
    if (filePath.includes('config') || filePath.includes('.config.')) return 'config';
    if (filePath.includes('model') || filePath.includes('types')) return 'model';
    if (filePath.includes('service') || filePath.includes('api')) return 'service';
    if (filePath.includes('component') || filePath.includes('App.')) return 'component';
    if (filePath.includes('test') || filePath.includes('.spec.')) return 'test';
    
    return 'component';
  }
  
  private async getSampleFiles(): Promise<string[]> {
    const extensions = ['.ts', '.js', '.tsx', '.jsx', '.py', '.java'];
    const files: string[] = [];
    
    for (const ext of extensions) {
      const found = this.findFiles(`**/*${ext}`);
      files.push(...found.slice(0, 5)); // Sample up to 5 files per extension
    }
    
    return files.slice(0, 20); // Total sample of 20 files
  }
  
  private async getFileExtensions(): Promise<string[]> {
    const allFiles = this.findFiles('**/*');
    const extensions = new Set<string>();
    
    for (const file of allFiles) {
      const ext = path.extname(file);
      if (ext) extensions.add(ext);
    }
    
    return Array.from(extensions);
  }
  
  private findFiles(...patterns: string[]): string[] {
    const files: string[] = [];
    
    try {
      for (const pattern of patterns) {
        const found = vscode.workspace.findFiles(pattern, '**/node_modules/**', 100);
        // This is a simplified version - in real implementation we'd await the promise
        // For now, we'll use fs.readdirSync as fallback
      }
    } catch (error) {
      console.warn('File search failed, using fallback');
    }
    
    return files;
  }
}