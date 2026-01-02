/**
 * Phase 4.2.1 - Conversation Handler
 * 
 * Safe, non-autonomous chat brain for NAVI.
 * 
 * CRITICAL SAFETY RULES:
 * - Never executes tools
 * - Never modifies code  
 * - Never triggers planner
 * - Always stays in conversational mode
 * 
 * Handles:
 * - Greetings
 * - Explanations
 * - "How does this work?"
 * - Vague or incomplete requests
 * - Typos, slang, half sentences
 * - Capability questions
 * - Out-of-scope requests
 */

export interface ConversationResponse {
    content: string;
    suggestions?: string[];
    conversationType: 'greeting' | 'explanation' | 'capability' | 'clarification' | 'help';
}

export class ConversationHandler {
    /**
     * Phase 4.2.1: Generate safe conversational responses
     * 
     * This is NOT an LLM call yet - we'll add that in Phase 4.2.2
     * For now, we use template-based responses for maximum safety
     */
    static async handleConversation(
        userInput: string,
        context?: { workspace?: string; repoInfo?: any }
    ): Promise<ConversationResponse> {
        const input = userInput.toLowerCase().trim();

        // Greetings
        if (this.isGreeting(input)) {
            return {
                content: `Hello! I'm NAVI, your autonomous engineering assistant.

I can inspect your Problems tab, refactor code, run tests, review changes, and explain tricky logic. I will propose a plan and ask for approval before I change anything.

What should we tackle first?`,
                conversationType: 'greeting',
                suggestions: [
                    'Fix errors in the Problems tab',
                    'Analyze the codebase structure',
                    'Explain what you can do',
                    'Help me understand this project'
                ]
            };
        }

        // Capability questions
        if (this.isCapabilityQuestion(input)) {
            return {
                content: `I'm NAVI - an autonomous engineering assistant focused on reliable code changes.

**What I can do**
• Fix diagnostics and Problems tab issues
• Refactor and optimize code
• Run tests and report results
• Review diffs and explain code
• Generate or update files with approval

**How it works**
1. I confirm the goal and scope
2. I generate a short, safe plan
3. You approve, then I apply changes
4. I verify and summarize the outcome

If you tell me a specific goal, I'll take it from there.`,
                conversationType: 'capability',
                suggestions: [
                    'Fix the errors I see in Problems tab',
                    'Analyze this codebase structure',
                    'Show me what needs improvement',
                    'Help me understand the code'
                ]
            };
        }

        // Project/repo questions
        if (this.isProjectQuestion(input)) {
            return {
                content: `This repo looks like an Autonomous Engineering Platform with a VS Code extension, webview UI, and a backend API.

If you want a deep dive, tell me which area to analyze (extension, backend, integrations, or a specific file), and I'll prepare a focused plan.`,
                conversationType: 'explanation',
                suggestions: [
                    'Analyze the current codebase structure',
                    'Fix any errors you find',
                    'Explain the architecture in detail',
                    'Check for code quality issues'
                ]
            };
        }

        // Vague requests - ask for clarification
        if (this.isVagueRequest(input)) {
            return {
                content: `I can help - just point me at a concrete goal.

Examples:
• "Fix the Problems tab errors"
• "Refactor this component for clarity"
• "Run tests and summarize failures"
• "Explain how this module works"

What should I focus on?`,
                conversationType: 'clarification',
                suggestions: [
                    'Fix errors in Problems tab',
                    'Analyze code structure',
                    'Create a new component',
                    'Improve code quality'
                ]
            };
        }

        // Help requests
        if (this.isHelpRequest(input)) {
            return {
                content: `Tell me what you want changed or checked, and I will take it from there.

Examples:
• "Fix the TypeScript errors"
• "Review this file for issues"
• "Refactor this component"
• "Explain this module"

I will propose a plan before making changes.`,
                conversationType: 'help',
                suggestions: [
                    'Fix current code errors',
                    'Review code in this file',
                    'Explain this codebase',
                    'What can you help me with?'
                ]
            };
        }

        // Default response for unclear input
        return {
            content: `I did not catch the exact task yet.

Try one of these:
• "Fix the errors in my code"
• "Explain this project structure"
• "Help me refactor this component"
• "Run tests and summarize failures"

The more specific you are, the faster I can act.`,
            conversationType: 'clarification',
            suggestions: [
                'Fix code errors',
                'Explain what you do',
                'Analyze this project',
                'Help me with development'
            ]
        };
    }

    // Helper methods for intent detection
    private static isGreeting(input: string): boolean {
        const greetingPatterns = [
            /^(hi|hello|hey|good morning|good afternoon|good evening)/,
            /^what'?s up$/,
            /^how are you/
        ];
        return greetingPatterns.some(pattern => pattern.test(input));
    }

    private static isCapabilityQuestion(input: string): boolean {
        return /what can you do|what are you|who are you|your capabilities|help me understand/.test(input);
    }

    private static isProjectQuestion(input: string): boolean {
        return /what is this|what's this|this repo|this project|codebase|repository/.test(input);
    }

    private static isVagueRequest(input: string): boolean {
        const vaguePatterns = [
            /^help$/,
            /^fix this$/,
            /^do something$/,
            /^i need help$/,
            /^assist me$/
        ];
        return vaguePatterns.some(pattern => pattern.test(input));
    }

    private static isHelpRequest(input: string): boolean {
        return /^help me|^how do i|^i don't know|^not sure|^confused/.test(input);
    }
}
