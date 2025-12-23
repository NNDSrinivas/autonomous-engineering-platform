import { Intent, IntentType } from './IntentClassifier';
import { ResolvedPatterns } from '../context/RepoPatternResolver';

/**
 * Structured plan for intent execution
 */
export interface IntentPlan {
    description: string;
    priority: 'high' | 'medium' | 'low';
    rules: string[];
    constraints: string[];
    approach: string;
    expectedFiles: number;
    riskLevel: 'low' | 'medium' | 'high';
}

/**
 * IntentPlanBuilder - Creates structured plans for different types of engineering work
 * 
 * Mental Model:
 * ❌ Old: Apply random fixes based on diagnostics
 * ✅ New: Create strategic plans with rules and constraints for engineering work
 * 
 * This is the strategic layer that makes NAVI think like a senior engineer
 */
export class IntentPlanBuilder {

    /**
     * Build structured execution plan for user intent
     */
    static build(intent: Intent, resolvedPatterns?: ResolvedPatterns): IntentPlan {
        const basePlan = this.getBasePlanForIntent(intent.type);
        const customizedPlan = this.customizeForContext(basePlan, intent, resolvedPatterns);

        return {
            ...customizedPlan,
            description: this.generateDescription(intent, resolvedPatterns),
            priority: this.determinePriority(intent),
            riskLevel: this.assessRisk(intent, customizedPlan)
        };
    }

    /**
     * Get base plan template for intent type
     */
    private static getBasePlanForIntent(intentType: IntentType): Partial<IntentPlan> {
        switch (intentType) {
            case 'FIX_ERRORS':
                return {
                    rules: [
                        'Fix all syntax and compilation errors',
                        'Preserve existing functionality',
                        'Maintain code structure and style',
                        'Apply minimal necessary changes'
                    ],
                    constraints: [
                        'Do not refactor unless required for fix',
                        'Keep changes atomic and focused',
                        'Preserve existing APIs'
                    ],
                    approach: 'diagnostic-driven',
                    expectedFiles: 1,
                    riskLevel: 'low'
                };

            case 'REFACTOR':
                return {
                    rules: [
                        'Preserve all existing functionality',
                        'Improve code readability and maintainability',
                        'Follow repository conventions exactly',
                        'Extract reusable patterns where appropriate',
                        'Eliminate code duplication'
                    ],
                    constraints: [
                        'Do not change public APIs',
                        'Do not alter business logic behavior',
                        'Keep existing test coverage',
                        'Maintain performance characteristics'
                    ],
                    approach: 'structure-preserving',
                    expectedFiles: 1,
                    riskLevel: 'medium'
                };

            case 'ADD_FEATURE':
                return {
                    rules: [
                        'Follow existing architectural patterns',
                        'Reuse existing components and utilities',
                        'Add comprehensive error handling',
                        'Include appropriate type definitions',
                        'Maintain consistency with codebase style'
                    ],
                    constraints: [
                        'Do not break existing functionality',
                        'Use established patterns and conventions',
                        'Minimize dependencies',
                        'Follow security best practices'
                    ],
                    approach: 'additive-development',
                    expectedFiles: 2,
                    riskLevel: 'medium'
                };

            case 'CONVERT_PATTERN':
                return {
                    rules: [
                        'Migrate to modern patterns systematically',
                        'Preserve all existing functionality',
                        'Update related code consistently',
                        'Follow new pattern conventions completely',
                        'Remove deprecated pattern usage'
                    ],
                    constraints: [
                        'Do not change external APIs',
                        'Maintain backward compatibility where possible',
                        'Update all related files atomically',
                        'Keep test coverage intact'
                    ],
                    approach: 'pattern-migration',
                    expectedFiles: 3,
                    riskLevel: 'high'
                };

            case 'CREATE_FILE':
                return {
                    rules: [
                        'Follow repository file naming conventions',
                        'Use established architectural patterns',
                        'Include proper type definitions',
                        'Add comprehensive documentation',
                        'Follow coding standards exactly'
                    ],
                    constraints: [
                        'Place files in appropriate directories',
                        'Use existing import patterns',
                        'Follow established export conventions',
                        'Include error boundaries where needed'
                    ],
                    approach: 'template-based-generation',
                    expectedFiles: 1,
                    riskLevel: 'low'
                };

            case 'OPTIMIZE':
                return {
                    rules: [
                        'Preserve all existing functionality',
                        'Measure performance impact',
                        'Use established optimization patterns',
                        'Maintain code readability',
                        'Document performance improvements'
                    ],
                    constraints: [
                        'Do not change public interfaces',
                        'Avoid premature optimization',
                        'Keep optimization scope focused',
                        'Maintain test coverage'
                    ],
                    approach: 'performance-focused',
                    expectedFiles: 1,
                    riskLevel: 'medium'
                };

            case 'TEST':
                return {
                    rules: [
                        'Cover all critical functionality paths',
                        'Follow existing test patterns',
                        'Include edge cases and error scenarios',
                        'Use appropriate testing utilities',
                        'Maintain test isolation'
                    ],
                    constraints: [
                        'Do not modify production code unnecessarily',
                        'Follow established test conventions',
                        'Keep tests maintainable and readable',
                        'Use existing mocking patterns'
                    ],
                    approach: 'test-driven',
                    expectedFiles: 1,
                    riskLevel: 'low'
                };

            case 'EXPLAIN_CODE':
                return {
                    rules: [
                        'Provide accurate technical analysis',
                        'Explain architectural decisions',
                        'Identify potential improvements',
                        'Document complex logic clearly'
                    ],
                    constraints: [
                        'Do not modify existing code',
                        'Focus on understanding over criticism',
                        'Provide actionable insights'
                    ],
                    approach: 'analytical',
                    expectedFiles: 0,
                    riskLevel: 'low'
                };

            default:
                return {
                    rules: ['Follow repository conventions', 'Maintain code quality'],
                    constraints: ['Minimize changes', 'Preserve functionality'],
                    approach: 'conservative',
                    expectedFiles: 1,
                    riskLevel: 'medium'
                };
        }
    }

    /**
     * Customize plan based on repository context
     */
    private static customizeForContext(
        basePlan: Partial<IntentPlan>,
        intent: Intent,
        patterns?: ResolvedPatterns
    ): IntentPlan {
        const plan = { ...basePlan } as IntentPlan;

        if (patterns) {
            // Add framework-specific rules
            if (patterns.framework === 'React') {
                plan.rules.push('Use functional components and hooks');
                plan.rules.push('Follow React best practices');
                if (patterns.patterns.hooks?.length) {
                    plan.rules.push(`Reuse existing hooks: ${patterns.patterns.hooks.join(', ')}`);
                }
            }

            // Add TypeScript-specific rules
            if (patterns.language === 'typescript') {
                plan.rules.push('Provide complete type definitions');
                plan.rules.push('Use strict TypeScript settings');
                plan.constraints.push('Avoid any types');
            }

            // Add testing constraints
            if (patterns.patterns.testing?.length) {
                plan.rules.push('Include appropriate tests');
                plan.constraints.push('Maintain test coverage standards');
            }

            // Adjust approach based on architecture
            if (patterns.architecture === 'functional-components') {
                plan.approach = `${plan.approach}-functional`;
            }
        }

        // Add intent-specific customizations
        if (intent.details?.target) {
            plan.rules.unshift(`Focus on target: ${intent.details.target}`);
        }

        if (intent.details?.constraints) {
            plan.constraints.push(...intent.details.constraints);
        }

        return plan;
    }

    /**
     * Generate human-readable plan description
     */
    private static generateDescription(intent: Intent, patterns?: ResolvedPatterns): string {
        const target = intent.details?.target || 'code';
        const framework = patterns?.framework || 'the current';
        const language = patterns?.language || 'JavaScript';

        switch (intent.type) {
            case 'FIX_ERRORS':
                return `Fix all errors in ${target} while preserving functionality and following ${framework} patterns`;

            case 'REFACTOR':
                return `Refactor ${target} to improve structure and maintainability using ${language} best practices`;

            case 'ADD_FEATURE':
                return `Add new functionality to ${target} following established ${framework} patterns and conventions`;

            case 'CONVERT_PATTERN':
                return `Convert ${target} to modern patterns while maintaining compatibility and ${framework} standards`;

            case 'CREATE_FILE':
                return `Create new ${target} following repository conventions and ${language} best practices`;

            case 'OPTIMIZE':
                return `Optimize ${target} for better performance while preserving functionality`;

            case 'TEST':
                return `Add comprehensive tests for ${target} following existing test patterns`;

            case 'EXPLAIN_CODE':
                return `Analyze and explain ${target} architecture and implementation details`;

            default:
                return `Improve ${target} following repository best practices`;
        }
    }

    /**
     * Determine execution priority based on intent
     */
    private static determinePriority(intent: Intent): 'high' | 'medium' | 'low' {
        if (intent.confidence >= 0.8) {
            switch (intent.type) {
                case 'FIX_ERRORS':
                    return 'high';
                case 'ADD_FEATURE':
                case 'CONVERT_PATTERN':
                    return 'medium';
                default:
                    return 'low';
            }
        }

        return intent.confidence >= 0.6 ? 'medium' : 'low';
    }

    /**
     * Assess risk level of plan execution
     */
    private static assessRisk(intent: Intent, plan: IntentPlan): 'low' | 'medium' | 'high' {
        let riskScore = 0;

        // Base risk by intent type
        const riskByType = {
            'FIX_ERRORS': 1,
            'EXPLAIN_CODE': 0,
            'CREATE_FILE': 1,
            'TEST': 1,
            'REFACTOR': 2,
            'ADD_FEATURE': 2,
            'PLAN_FEATURE': 1,      // Planning is low risk
            'OPTIMIZE': 2,
            'CONVERT_PATTERN': 3,
            'UNKNOWN': 2
        };

        riskScore += riskByType[intent.type] || 2;

        // Increase risk based on expected files
        riskScore += Math.min(plan.expectedFiles - 1, 2);

        // Decrease risk for high confidence
        if (intent.confidence >= 0.8) riskScore -= 1;

        // Convert to risk level
        if (riskScore <= 1) return 'low';
        if (riskScore <= 3) return 'medium';
        return 'high';
    }

    /**
     * Get execution summary for logging/display
     */
    static summarize(plan: IntentPlan, intent: Intent): string {
        return `Plan: ${plan.description}
Priority: ${plan.priority} (${intent.confidence.toFixed(2)} confidence)
Risk: ${plan.riskLevel}
Expected files: ${plan.expectedFiles}
Approach: ${plan.approach}
Key rules: ${plan.rules.slice(0, 3).join(', ')}`;
    }
}