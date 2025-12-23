/**
 * IntentClassifier - The Brain that understands what users actually want
 * 
 * Mental Model Shift:
 * ❌ Old: Only respond to diagnostics (reactive)
 * ✅ New: Understand user intent (proactive engineering work)
 * 
 * This is what makes NAVI do "real engineering work" instead of just fixing errors
 */

export type IntentType =
    | 'FIX_ERRORS'      // Traditional diagnostic fixing
    | 'REFACTOR'        // Improve code structure/quality
    | 'ADD_FEATURE'     // Implement new functionality
    | 'PLAN_FEATURE'    // 👈 NEW - Plan feature before implementation
    | 'CONVERT_PATTERN' // Migrate between patterns (class→hooks, etc)
    | 'CREATE_FILE'     // Generate new files/components
    | 'EXPLAIN_CODE'    // Code analysis and documentation
    | 'OPTIMIZE'        // Performance improvements
    | 'TEST'            // Add/improve testing
    | 'UNKNOWN';        // Fallback for unclear intent

export interface Intent {
    type: IntentType;
    confidence: number;
    raw: string;
    details?: {
        target?: string;        // What to work on
        approach?: string;      // How to do it
        constraints?: string[]; // Limitations/requirements
    };
}

export class IntentClassifier {

    /**
     * Classify user message to understand engineering intent
     * This replaces "diagnostic-only thinking" with "intent-driven engineering"
     */
    static classify(message: string): Intent {
        const m = message.toLowerCase().trim();

        // FIX_ERRORS - Traditional diagnostic fixing
        if (this.matchesPattern(m, [
            /fix|error|broken|issue|problem|bug/,
            /not working|failing|crash/,
            /syntax error|compilation/,
            /undefined|null reference/
        ])) {
            return {
                type: 'FIX_ERRORS',
                confidence: 0.9,
                raw: message,
                details: {
                    target: this.extractTarget(message, ['file', 'function', 'component']),
                    approach: 'diagnostic-driven'
                }
            };
        }

        // REFACTOR - Code structure improvements
        if (this.matchesPattern(m, [
            /refactor|clean up|improve|optimize/,
            /restructure|reorganize|simplify/,
            /extract|split|combine|merge/,
            /rename|move|separate/
        ])) {
            return {
                type: 'REFACTOR',
                confidence: 0.85,
                raw: message,
                details: {
                    target: this.extractTarget(message, ['component', 'function', 'class', 'file']),
                    approach: 'structure-preserving'
                }
            };
        }

        // ADD_FEATURE - New functionality implementation
        if (this.matchesPattern(m, [
            /add|create|implement|build/,
            /new feature|functionality/,
            /make it|enable|support/,
            /add support for|implement/
        ])) {
            return {
                type: 'ADD_FEATURE',
                confidence: 0.8,
                raw: message,
                details: {
                    target: this.extractTarget(message, ['feature', 'component', 'function', 'API']),
                    approach: 'additive'
                }
            };
        }

        // PLAN_FEATURE - Plan feature before implementation
        if (this.matchesPattern(m, [
            /plan|design|architect|think about/,
            /how to implement|how to add|how to build/,
            /what would it take|what files|what changes/,
            /plan feature|feature plan|implementation plan/
        ])) {
            return {
                type: 'PLAN_FEATURE',
                confidence: 0.85,
                raw: message,
                details: {
                    target: this.extractTarget(message, ['feature', 'component', 'functionality']),
                    approach: 'planning-first'
                }
            };
        }

        // CONVERT_PATTERN - Pattern migration/modernization
        if (this.matchesPattern(m, [
            /convert|rewrite|migrate|modernize/,
            /change from .* to|switch to/,
            /use hooks instead|make functional/,
            /typescript|es6|async\/await/
        ])) {
            return {
                type: 'CONVERT_PATTERN',
                confidence: 0.85,
                raw: message,
                details: {
                    target: this.extractTarget(message, ['component', 'class', 'function']),
                    approach: 'pattern-migration'
                }
            };
        }

        // CREATE_FILE - Generate new files/components
        if (this.matchesPattern(m, [
            /create|generate|scaffold/,
            /new component|new service|new hook/,
            /make a|build a/,
            /add a new/
        ])) {
            return {
                type: 'CREATE_FILE',
                confidence: 0.8,
                raw: message,
                details: {
                    target: this.extractTarget(message, ['component', 'service', 'hook', 'utility']),
                    approach: 'template-based'
                }
            };
        }

        // EXPLAIN_CODE - Code analysis and documentation
        if (this.matchesPattern(m, [
            /explain|understand|what does/,
            /how does|why|document/,
            /analyze|review|comment/
        ])) {
            return {
                type: 'EXPLAIN_CODE',
                confidence: 0.7,
                raw: message,
                details: {
                    approach: 'analysis'
                }
            };
        }

        // OPTIMIZE - Performance improvements
        if (this.matchesPattern(m, [
            /optimize|performance|faster/,
            /slow|memory|efficient/,
            /cache|lazy load|bundle/
        ])) {
            return {
                type: 'OPTIMIZE',
                confidence: 0.8,
                raw: message,
                details: {
                    approach: 'performance-focused'
                }
            };
        }

        // TEST - Add/improve testing
        if (this.matchesPattern(m, [
            /test|testing|spec|unit test/,
            /coverage|mock|jest|vitest/
        ])) {
            return {
                type: 'TEST',
                confidence: 0.85,
                raw: message,
                details: {
                    approach: 'test-driven'
                }
            };
        }

        // UNKNOWN - Fallback
        return {
            type: 'UNKNOWN',
            confidence: 0.3,
            raw: message,
            details: {
                approach: 'exploratory'
            }
        };
    }

    /**
     * Check if message matches any of the given patterns
     */
    private static matchesPattern(message: string, patterns: RegExp[]): boolean {
        return patterns.some(pattern => pattern.test(message));
    }

    /**
     * Extract target entities from user message
     */
    private static extractTarget(message: string, entityTypes: string[]): string | undefined {
        for (const entityType of entityTypes) {
            const regex = new RegExp(`(this|the)\\s+${entityType}|${entityType}\\s+(\\w+)`, 'i');
            const match = message.match(regex);
            if (match) {
                return match[0];
            }
        }
        return undefined;
    }

    /**
     * Get human-readable description of intent
     */
    static describe(intent: Intent): string {
        const descriptions = {
            'FIX_ERRORS': 'Fix errors and resolve issues',
            'REFACTOR': 'Improve code structure and quality',
            'ADD_FEATURE': 'Implement new functionality',
            'PLAN_FEATURE': 'Plan feature implementation before coding',
            'CONVERT_PATTERN': 'Migrate to modern patterns',
            'CREATE_FILE': 'Generate new files and components',
            'EXPLAIN_CODE': 'Analyze and document code',
            'OPTIMIZE': 'Improve performance and efficiency',
            'TEST': 'Add or improve testing',
            'UNKNOWN': 'General code assistance'
        };

        return descriptions[intent.type] || 'Unknown intent';
    }

    /**
     * Determine if intent requires file system changes
     */
    static requiresFileChanges(intent: Intent): boolean {
        return ['FIX_ERRORS', 'REFACTOR', 'ADD_FEATURE', 'CONVERT_PATTERN', 'CREATE_FILE', 'OPTIMIZE', 'TEST'].includes(intent.type);
    }

    /**
     * Get suggested confidence threshold for auto-apply
     */
    static getAutoApplyThreshold(intent: Intent): number {
        const thresholds = {
            'FIX_ERRORS': 0.8,      // High confidence for fixes
            'REFACTOR': 0.7,        // Medium confidence for refactors
            'ADD_FEATURE': 0.6,     // Lower confidence for new features
            'PLAN_FEATURE': 0.7,    // Medium confidence for planning
            'CONVERT_PATTERN': 0.75, // High confidence for patterns
            'CREATE_FILE': 0.6,     // Lower confidence for creation
            'EXPLAIN_CODE': 0.9,    // High confidence for explanations
            'OPTIMIZE': 0.7,        // Medium confidence for optimizations
            'TEST': 0.8,           // High confidence for testing
            'UNKNOWN': 0.5         // Low confidence for unknown
        };

        return thresholds[intent.type] || 0.6;
    }
}