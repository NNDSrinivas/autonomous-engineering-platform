/**
 * Prompt templates for various NAVI operations
 * Extracted to separate file for maintainability and easier testing of different prompting strategies
 */

/**
 * Repository analysis prompt template
 * Used when analyzing repository architecture and structure
 *
 * @param contextMessage - The workspace context (files, structure, technologies)
 * @param originalMessage - The user's original question/request
 * @returns Formatted prompt string
 */
export function buildRepoAnalysisPrompt(contextMessage: string, originalMessage: string): string {
  return `${contextMessage}

${originalMessage}

Please analyze the repository architecture and structure based on the attached files. Provide TWO sections:

**Section 1: Non-Technical Overview (for business stakeholders)**
- What is this project? What problem does it solve?
- Who would use this and why?
- What are the main features or capabilities?
- Explain in simple terms that anyone can understand

**Section 2: Technical Analysis (for developers)**
1. What this project does and its purpose
2. The overall architecture and how components interact
3. Key technologies and frameworks used
4. Main entry points and how the application flows
5. Any important patterns or design decisions you can identify

Provide a comprehensive overview that goes beyond just listing files. Make it accessible for both technical and non-technical readers.`;
}

/**
 * Additional prompt templates can be added here as needed
 * Examples:
 * - Code generation prompts
 * - Bug fix prompts
 * - Refactoring prompts
 * - Test generation prompts
 */
