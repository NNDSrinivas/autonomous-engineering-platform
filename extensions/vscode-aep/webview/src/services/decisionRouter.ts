/**
 * Phase 4.2.1 - Decision Router
 * 
 * CRITICAL RULE: Planner is no longer the default path.
 * 
 * This router decides between:
 * - Agent Path (Planner) → for clear, executable tasks
 * - Conversational Path (LLM Chat) → for everything else
 * 
 * This is the single biggest architectural change from Phase 4.1.
 */

export interface DecisionResult {
    path: 'agent' | 'conversation';
    confidence: number;
    reasoning: string;
    suggestedIntent?: string;
}

export class DecisionRouter {
    /**
     * Phase 4.2.1: Route user input to appropriate path
     * 
     * Agent Path Triggers (high confidence):
     * - Clear task requests: "fix the errors", "create a component"
     * - Specific intents: "analyze problems", "refactor code"
     * - Tool-requiring actions: "run tests", "format code"
     * 
     * Conversational Path Triggers:
     * - Greetings: "hello", "hi", "hey"
     * - Questions: "what is this?", "how does this work?"
     * - Vague requests: "help me", "I need assistance"
     * - Explanations: "explain the codebase", "what can you do?"
     * - Typos and incomplete sentences
     * - Out-of-scope requests
     */
    static route(userInput: string): DecisionResult {
        const input = userInput.toLowerCase().trim();

        // Empty input → conversation
        if (!input) {
            return {
                path: 'conversation',
                confidence: 1.0,
                reasoning: 'Empty input requires clarification'
            };
        }

        // Greetings → conversation
        const greetingPatterns = [
            /^(hi|hello|hey|good morning|good afternoon|good evening)\b/,
            /^what'?s up$/,
            /^how are you/
        ];

        if (greetingPatterns.some(pattern => pattern.test(input))) {
            return {
                path: 'conversation',
                confidence: 1.0,
                reasoning: 'Greeting detected - conversational response appropriate'
            };
        }

        // Code-level explain intents → conversational response with context
        const explainPatterns = [
            /^explain\s+this\b/i,
            /explain\s+(this|the)?\s*(file|code|function|class|component|module)/i,
            /walk\s+me\s+through\s+(this|the)\s*(code|file|function|class|component)/i
        ];

        if (explainPatterns.some(pattern => pattern.test(input))) {
            return {
                path: 'conversation',
                confidence: 0.85,
                reasoning: 'Explanation request detected - conversational response appropriate'
            };
        }

        const reviewPatterns = [
            /^review\s+this\b/i,
            /review\s+(this|the)?\s*(code|changes|diff|pr|pull request)/i,
            /\bcode\s+review\b/i
        ];

        if (reviewPatterns.some(pattern => pattern.test(input))) {
            return {
                path: 'agent',
                confidence: 0.85,
                reasoning: 'Review intent detected',
                suggestedIntent: 'REVIEW_PR'
            };
        }

        // Repo/architecture questions → conversation
        const repoQuestions = [
            /analy[sz]e\s+(the\s+)?(codebase|repo|repository|project|architecture|structure)/i,
            /explain\s+(the\s+)?(architecture|codebase|repo|repository|project|structure)/i,
            /(codebase|repo|repository|project)\s+(overview|summary|structure|architecture)/i
        ];

        if (repoQuestions.some(pattern => pattern.test(input))) {
            return {
                path: 'conversation',
                confidence: 0.85,
                reasoning: 'Repo-level question - conversational response appropriate'
            };
        }

        // Questions about capabilities → conversation
        const capabilityQuestions = [
            /what can you do/,
            /what are you/,
            /who are you/,
            /how do you work/,
            /what is this/,
            /help me understand/,
            /what's this repo/,
            /what's this project/,
            /explain\s+the\s+architecture/i
        ];

        if (capabilityQuestions.some(pattern => pattern.test(input))) {
            return {
                path: 'conversation',
                confidence: 0.9,
                reasoning: 'Capability or explanation question - requires conversational response'
            };
        }

        // Vague requests → conversation (for clarification)
        const vaguePatterns = [
            /^help$/,
            /^help me$/,
            /^fix this$/,
            /^do something$/,
            /^i need help$/,
            /^can you help/,
            /^assist me/,
            /^what should i do/
        ];

        if (vaguePatterns.some(pattern => pattern.test(input))) {
            return {
                path: 'conversation',
                confidence: 0.8,
                reasoning: 'Vague request requires clarification before planning'
            };
        }

        // Clear task patterns → agent path
        const taskPatterns = [
            { pattern: /\bfix\b.*\b(errors?|warnings?|issues?|problems?|diagnostics?)\b/i, intent: 'FIX_PROBLEMS' },
            { pattern: /\bfix\b.*\bcode\b.*\b(errors?|warnings?|issues?)\b/i, intent: 'FIX_PROBLEMS' },
            { pattern: /\bfix\b.*\b(this|these)\b.*\b(errors?|warnings?|issues?|problems?)\b/i, intent: 'FIX_PROBLEMS' },
            { pattern: /\b(problems tab|problems list|diagnostics tab)\b/i, intent: 'FIX_PROBLEMS' },
            { pattern: /\b(resolve|address|repair|clean up)\b.*\b(errors?|warnings?|issues?|problems?)\b/i, intent: 'FIX_PROBLEMS' },
            { pattern: /analyze\s+(the\s+)?(problems?|errors?|issues?|diagnostics?)/i, intent: 'ANALYZE_PROBLEMS' },
            { pattern: /create\s+a?\s*(component|file|class|function)/i, intent: 'CREATE_COMPONENT' },
            { pattern: /refactor\s+(this|the|code)/i, intent: 'REFACTOR_CODE' },
            { pattern: /run\s+(tests?|test suite|unit tests|integration tests)/i, intent: 'RUN_TESTS' },
            { pattern: /execute\s+(tests?|test suite|unit tests|integration tests)/i, intent: 'RUN_TESTS' },
            { pattern: /format\s+(code|this|the)/i, intent: 'FORMAT_CODE' },
            { pattern: /optimize\s+(performance|code)/i, intent: 'OPTIMIZE_PERFORMANCE' },
            { pattern: /add\s+(logging|error handling|tests)/i, intent: 'ADD_FEATURE' }
        ];

        for (const { pattern, intent } of taskPatterns) {
            if (pattern.test(input)) {
                return {
                    path: 'agent',
                    confidence: 0.9,
                    reasoning: `Clear task detected: ${intent}`,
                    suggestedIntent: intent
                };
            }
        }

        // Code-related requests with context → agent path
        const codePatterns = [
            /add.*to.*file/,
            /update.*function/,
            /modify.*class/,
            /implement.*method/,
            /remove.*code/,
            /delete.*file/
        ];

        if (codePatterns.some(pattern => pattern.test(input))) {
            return {
                path: 'agent',
                confidence: 0.8,
                reasoning: 'Code modification request detected'
            };
        }

        const engineeringSignals = [
            /\b(errors?|warnings?|issues?|problems?|diagnostics?)\b/,
            /\btests?\b/,
            /\brefactor\b/,
            /\boptimi[sz]e\b/,
            /\breview\b/,
            /\bcode\b/,
            /\bfile\b/,
            /\bcomponent\b/,
            /\bfunction\b/,
            /\blint\b/,
            /\btypecheck\b/
        ];

        if (engineeringSignals.some(pattern => pattern.test(input))) {
            return {
                path: 'agent',
                confidence: 0.7,
                reasoning: 'Engineering task signal detected - routing to agent for planning'
            };
        }

        // If we get here, it's ambiguous → conversation (for safety)
        return {
            path: 'conversation',
            confidence: 0.6,
            reasoning: 'Ambiguous input - using conversational clarification for safety'
        };
    }

    /**
     * Phase 4.2.2+: Enhanced intent classification with fuzzy matching
     * (Not implemented in 4.2.1 - keeping it simple)
     */
    static classifyIntent(userInput: string): string | null {
        const decision = this.route(userInput);
        return decision.suggestedIntent || null;
    }
}
