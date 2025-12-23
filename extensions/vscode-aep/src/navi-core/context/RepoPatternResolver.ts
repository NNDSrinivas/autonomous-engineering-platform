import { RepoContext } from '../fix/generative/GenerativeRepairEngine';
import { RepoPatterns } from './patterns/RepoPatternExtractor';
import type { Intent } from '../intent/IntentClassifier';

/**
 * Repository patterns resolved for specific intent context
 */
export interface ResolvedPatterns {
    language: string;
    framework?: string;
    architecture: string;
    patterns: {
        components?: string[];
        hooks?: string[];
        state?: string[];
        api?: string[];
        testing?: string[];
        styling?: string[];
    };
    conventions: {
        fileNaming: string;
        folderStructure: string;
        exportStyle: string;
        typeDefinition: string;
    };
    examples?: {
        [key: string]: string;
    };
}

/**
 * RepoPatternResolver - Maps intent to repository-specific solutions
 * 
 * This is WHY Copilot feels smart - it copies YOUR repo style
 * 
 * Mental Model:
 * ❌ Generic: "Create a React component" → Generic component
 * ✅ Repo-Aware: "Create a React component" → Component matching THIS repo's patterns
 */
export class RepoPatternResolver {

    /**
     * Resolve repository patterns for specific intent and context
     * This makes NAVI generate code that feels native to the current project
     */
    static resolve(repoContext: RepoContext, intent: Intent): ResolvedPatterns {
        const patterns = repoContext.patterns;
        if (!patterns) {
            return this.getDefaultPatterns();
        }

        return {
            language: patterns.language || 'typescript',
            framework: this.detectFramework(patterns),
            architecture: this.detectArchitecture(patterns),
            patterns: this.resolvePatternsByIntent(patterns, intent),
            conventions: this.resolveConventions(patterns),
            examples: this.generateExamples(patterns, intent)
        };
    }

    /**
     * Detect primary framework from repo patterns
     */
    private static detectFramework(patterns: RepoPatterns): string | undefined {
        if (patterns.frameworks?.includes('React')) return 'React';
        if (patterns.frameworks?.includes('Vue')) return 'Vue';
        if (patterns.frameworks?.includes('Express')) return 'Express';
        if (patterns.frameworks?.includes('FastAPI')) return 'FastAPI';
        return undefined;
    }

    /**
     * Detect architectural patterns from repo structure
     */
    private static detectArchitecture(patterns: RepoPatterns): string {
        if (patterns.frameworks?.includes('React Hooks')) return 'functional-components';
        if (patterns.language === 'typescript') return 'typed-architecture';
        if (patterns.testingPatterns?.length) return 'test-driven';
        return 'standard';
    }

    /**
     * Resolve specific patterns based on user intent
     */
    private static resolvePatternsByIntent(patterns: RepoPatterns, intent: Intent): any {
        const resolved: any = {
            components: patterns.commonImports?.filter(imp => imp.includes('component')) || [],
            hooks: patterns.commonHooks || [],
            state: this.extractStatePatterns(patterns),
            api: this.extractApiPatterns(patterns),
            testing: patterns.testingPatterns || [],
            styling: this.extractStylingPatterns(patterns)
        };

        // Customize based on intent
        switch (intent.type) {
            case 'ADD_FEATURE':
                return {
                    ...resolved,
                    focus: 'feature-implementation',
                    templates: this.getFeatureTemplates(patterns)
                };

            case 'REFACTOR':
                return {
                    ...resolved,
                    focus: 'structure-improvement',
                    antiPatterns: this.getAntiPatterns(patterns)
                };

            case 'CONVERT_PATTERN':
                return {
                    ...resolved,
                    focus: 'pattern-migration',
                    modernPatterns: this.getModernPatterns(patterns)
                };

            case 'CREATE_FILE':
                return {
                    ...resolved,
                    focus: 'file-generation',
                    scaffolds: this.getScaffoldTemplates(patterns)
                };

            default:
                return resolved;
        }
    }

    /**
     * Extract state management patterns from repo
     */
    private static extractStatePatterns(patterns: RepoPatterns): string[] {
        const statePatterns: string[] = [];

        if (patterns.commonHooks?.includes('useState')) statePatterns.push('useState');
        if (patterns.commonHooks?.includes('useReducer')) statePatterns.push('useReducer');
        if (patterns.commonHooks?.includes('useContext')) statePatterns.push('useContext');
        if (patterns.commonImports?.some(imp => imp.includes('redux'))) statePatterns.push('redux');
        if (patterns.commonImports?.some(imp => imp.includes('zustand'))) statePatterns.push('zustand');

        return statePatterns;
    }

    /**
     * Extract API patterns from repo
     */
    private static extractApiPatterns(patterns: RepoPatterns): string[] {
        const apiPatterns: string[] = [];

        if (patterns.commonHooks?.includes('useEffect')) apiPatterns.push('useEffect');
        if (patterns.commonImports?.some(imp => imp.includes('fetch'))) apiPatterns.push('fetch');
        if (patterns.commonImports?.some(imp => imp.includes('axios'))) apiPatterns.push('axios');
        if (patterns.commonImports?.some(imp => imp.includes('react-query'))) apiPatterns.push('react-query');
        if (patterns.commonImports?.some(imp => imp.includes('swr'))) apiPatterns.push('swr');

        return apiPatterns;
    }

    /**
     * Extract styling patterns from repo
     */
    private static extractStylingPatterns(patterns: RepoPatterns): string[] {
        const stylingPatterns: string[] = [];

        if (patterns.commonImports?.some(imp => imp.includes('styled'))) stylingPatterns.push('styled-components');
        if (patterns.commonImports?.some(imp => imp.includes('tailwind'))) stylingPatterns.push('tailwind');
        if (patterns.commonImports?.some(imp => imp.includes('emotion'))) stylingPatterns.push('emotion');
        if (patterns.commonImports?.some(imp => imp.includes('.css'))) stylingPatterns.push('css-modules');

        return stylingPatterns;
    }

    /**
     * Resolve naming and structural conventions
     */
    private static resolveConventions(patterns: RepoPatterns): any {
        return {
            fileNaming: patterns.fileNamingPattern || 'camelCase',
            folderStructure: patterns.folderStructure?.join('/') || 'flat',
            exportStyle: patterns.importsStyle === 'relative' ? 'named-exports' : 'default-exports',
            typeDefinition: patterns.language === 'typescript' ? 'interface-first' : 'prop-types'
        };
    }

    /**
     * Generate code examples based on repo patterns
     */
    private static generateExamples(patterns: RepoPatterns, intent: Intent): Record<string, string> {
        const examples: Record<string, string> = {};

        // React component example
        if (patterns.frameworks?.includes('React')) {
            examples.component = this.generateReactComponentExample(patterns);
        }

        // Hook example
        if (patterns.commonHooks?.length) {
            examples.hook = this.generateHookExample(patterns);
        }

        // API service example
        if (patterns.frameworks?.includes('Express') || patterns.frameworks?.includes('FastAPI')) {
            examples.service = this.generateServiceExample(patterns);
        }

        return examples;
    }

    /**
     * Generate React component example following repo patterns
     */
    private static generateReactComponentExample(patterns: RepoPatterns): string {
        const usesSemicolons = patterns.formatting?.semicolons ? ';' : '';
        const quotes = patterns.formatting?.quotes === 'single' ? "'" : '"';
        const indent = patterns.formatting?.indentation === 'spaces' ? '  ' : '\t';

        return `import React from ${quotes}react${quotes}${usesSemicolons}

export const ExampleComponent = () => {
${indent}return (
${indent}${indent}<div>
${indent}${indent}${indent}<h1>Example</h1>
${indent}${indent}</div>
${indent})${usesSemicolons}
}${usesSemicolons}`;
    }

    /**
     * Generate custom hook example
     */
    private static generateHookExample(patterns: RepoPatterns): string {
        const usesSemicolons = patterns.formatting?.semicolons ? ';' : '';
        const quotes = patterns.formatting?.quotes === 'single' ? "'" : '"';

        return `import { useState, useEffect } from ${quotes}react${quotes}${usesSemicolons}

export const useExample = () => {
  const [data, setData] = useState(null)${usesSemicolons}
  
  useEffect(() => {
    // Implementation here
  }, [])${usesSemicolons}
  
  return { data }${usesSemicolons}
}${usesSemicolons}`;
    }

    /**
     * Generate service example
     */
    private static generateServiceExample(patterns: RepoPatterns): string {
        const usesSemicolons = patterns.formatting?.semicolons ? ';' : '';

        return `export class ExampleService {
  static async getData() {
    // Implementation here
    return data${usesSemicolons}
  }
}${usesSemicolons}`;
    }

    /**
     * Get feature implementation templates
     */
    private static getFeatureTemplates(patterns: RepoPatterns): string[] {
        const templates = ['component-with-logic'];

        if (patterns.commonHooks?.length) templates.push('custom-hook');
        if (patterns.testingPatterns?.length) templates.push('with-tests');

        return templates;
    }

    /**
     * Get anti-patterns to avoid during refactoring
     */
    private static getAntiPatterns(patterns: RepoPatterns): string[] {
        const antiPatterns = ['mixed-concerns', 'deep-nesting'];

        if (patterns.language === 'typescript') antiPatterns.push('any-types');
        if (patterns.frameworks?.includes('React Hooks')) antiPatterns.push('class-components');

        return antiPatterns;
    }

    /**
     * Get modern patterns for conversion
     */
    private static getModernPatterns(patterns: RepoPatterns): string[] {
        const modernPatterns = ['functional-components'];

        if (patterns.language === 'typescript') modernPatterns.push('strict-types');
        if (patterns.commonHooks?.length) modernPatterns.push('custom-hooks');

        return modernPatterns;
    }

    /**
     * Get scaffold templates for file creation
     */
    private static getScaffoldTemplates(patterns: RepoPatterns): string[] {
        const scaffolds = ['basic-file'];

        if (patterns.frameworks?.includes('React')) scaffolds.push('react-component');
        if (patterns.testingPatterns?.length) scaffolds.push('test-file');

        return scaffolds;
    }

    /**
     * Default patterns when repo analysis is unavailable
     */
    private static getDefaultPatterns(): ResolvedPatterns {
        return {
            language: 'typescript',
            architecture: 'standard',
            patterns: {
                components: [],
                hooks: [],
                state: ['useState'],
                api: ['fetch'],
                testing: [],
                styling: []
            },
            conventions: {
                fileNaming: 'camelCase',
                folderStructure: 'flat',
                exportStyle: 'named-exports',
                typeDefinition: 'interface-first'
            }
        };
    }
}