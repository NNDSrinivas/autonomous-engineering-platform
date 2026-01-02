/**
 * Phase 3.3 - Code Generation Engine
 * 
 * This is where NAVI transforms from a reactive fixer to a proactive code generator.
 * Like Copilot/Cline, but with explicit repo understanding and structured planning.
 */

import { RepoContext } from '../context/RepoContextBuilder';
import { ChangePlan, ChangePlanBuilder, FileEdit } from './ChangePlan';
import { LLMProvider } from '../llm/LLMProvider';

export interface GenerationRequest {
  intent: string;
  context: {
    currentFile?: string;
    selectedCode?: string;
    relatedFiles?: string[];
  };
  constraints?: {
    preserveExisting?: boolean;
    followConventions?: boolean;
    minimizeChanges?: boolean;
  };
}

export interface GenerationPrompt {
  systemPrompt: string;
  userPrompt: string;
  context: string;
  examples: string;
}

export class CodeGenerationEngine {
  constructor(
    private repoContext: RepoContext,
    private llmProvider: LLMProvider
  ) {}
  
  /**
   * Generate a structured ChangePlan for the given intent
   */
  async generatePlan(request: GenerationRequest): Promise<ChangePlan> {
    console.log(`🧠 Generating code plan: ${request.intent}`);
    
    // Step 1: Build comprehensive prompt with repo context
    const prompt = await this.buildPrompt(request);
    
    // Step 2: Generate structured plan via LLM
    const rawPlanResponse = await this.llmProvider.generateText({
      prompt: `${prompt.systemPrompt}\n\n${prompt.userPrompt}`,
      temperature: 0.7,
      maxTokens: 2000
    });
    
    const rawPlan = JSON.parse(rawPlanResponse.content);
    
    // Step 3: Convert to structured ChangePlan
    const plan = this.convertToChangePlan(request.intent, rawPlan);
    
    // Step 4: Validate and refine
    const validation = ChangePlanBuilder.validate(plan);
    if (!validation.valid) {
      throw new Error(`Invalid plan generated: ${validation.errors.join(', ')}`);
    }
    
    console.log(`✅ Generated plan: ${ChangePlanBuilder.summarize(plan)}`);
    return plan;
  }
  
  /**
   * Generate code for a specific file based on context and requirements
   */
  async generateFileContent(
    filePath: string,
    requirements: string,
    existingContent?: string
  ): Promise<string> {
    const prompt = await this.buildFileGenerationPrompt(filePath, requirements, existingContent);
    
    const response = await this.llmProvider.generateText({
      prompt: `${prompt.systemPrompt}\n\n${prompt.userPrompt}`,
      temperature: 0.7,
      maxTokens: 2000
    });
    
    return this.cleanGeneratedCode(response.content);
  }
  
  /**
   * Generate precise edits for an existing file
   */
  async generateFileEdits(
    filePath: string,
    requirements: string,
    existingContent: string
  ): Promise<FileEdit[]> {
    const prompt = await this.buildEditGenerationPrompt(filePath, requirements, existingContent);
    
    const rawEditsResponse = await this.llmProvider.generateText({
      prompt: `${prompt.systemPrompt}\n\n${prompt.userPrompt}`,
      temperature: 0.7,
      maxTokens: 2000
    });
    
    const rawEdits = JSON.parse(rawEditsResponse.content);
    
    return rawEdits.edits.map((edit: any) => ({
      type: edit.type,
      startLine: edit.startLine,
      endLine: edit.endLine,
      content: edit.content,
      reasoning: edit.reasoning
    }));
  }
  
  /**
   * Build comprehensive prompt with repo context
   */
  private async buildPrompt(request: GenerationRequest): Promise<GenerationPrompt> {
    const systemPrompt = this.buildSystemPrompt();
    const contextSection = this.buildContextSection(request);
    const constraintsSection = this.buildConstraintsSection(request.constraints);
    const examplesSection = this.buildExamplesSection();
    
    const userPrompt = `
${contextSection}

TASK: ${request.intent}

${constraintsSection}

Generate a structured plan with the following format:
{
  "description": "Clear description of what will be implemented",
  "steps": [
    {
      "operation": "create|modify|delete",
      "filePath": "absolute/path/to/file",
      "content": "full file content for create operations",
      "edits": [
        {
          "type": "insert|replace|delete",
          "startLine": 10,
          "endLine": 15,
          "content": "new code content",
          "reasoning": "why this change is needed"
        }
      ],
      "reasoning": "why this step is needed"
    }
  ],
  "riskLevel": "low|medium|high",
  "expectedOutcome": "what the user will see after completion"
}
    `.trim();
    
    return {
      systemPrompt,
      userPrompt,
      context: contextSection,
      examples: examplesSection
    };
  }
  
  /**
   * Build system prompt with repo understanding
   */
  private buildSystemPrompt(): string {
    const { language, framework, conventions } = this.repoContext;
    
    return `You are NAVI, an expert ${language}${framework ? ` ${framework}` : ''} code generator.

REPOSITORY CONTEXT:
- Language: ${language}
- Framework: ${framework || 'None'}
- Naming: ${conventions.naming}
- Indentation: ${conventions.indentSize} ${conventions.indentation}
- Quotes: ${conventions.quotes}
- Semicolons: ${conventions.semicolons ? 'Required' : 'Optional'}
- Structure: ${conventions.fileStructure}
- Patterns: ${conventions.patterns.join(', ')}

GENERATION PRINCIPLES:
1. Follow existing code patterns and conventions exactly
2. Generate complete, working code - never partial implementations
3. Preserve existing architecture and design patterns
4. Use established dependency patterns from this repo
5. Generate atomic, coherent changes across multiple files
6. Never break existing functionality
7. Include proper error handling and edge cases
8. Add appropriate comments explaining complex logic

CONSTRAINTS:
- Only modify files that need changes
- Preserve existing imports and dependencies unless changing them is essential
- Follow the established file structure and naming patterns
- Generate production-ready code with proper error handling
- Ensure all generated code passes linting and type checking

Your output must be valid JSON that can be parsed programmatically.`;
  }
  
  /**
   * Build context section with current state
   */
  private buildContextSection(request: GenerationRequest): string {
    let context = `CURRENT CONTEXT:\n`;
    
    if (request.context.currentFile) {
      context += `- Current file: ${request.context.currentFile}\n`;
    }
    
    if (request.context.selectedCode) {
      context += `- Selected code:\n\`\`\`\n${request.context.selectedCode}\n\`\`\`\n`;
    }
    
    if (request.context.relatedFiles?.length) {
      context += `- Related files: ${request.context.relatedFiles.join(', ')}\n`;
    }
    
    // Add key architectural information
    context += `\nREPOSITORY STRUCTURE:\n`;
    context += `- Root: ${this.repoContext.structure.rootDir}\n`;
    if (this.repoContext.structure.srcDir) {
      context += `- Source: ${this.repoContext.structure.srcDir}\n`;
    }
    context += `- Common directories: ${this.repoContext.structure.commonDirs.join(', ')}\n`;
    
    // Add key dependencies
    if (this.repoContext.dependencies.length > 0) {
      context += `\nKEY DEPENDENCIES:\n`;
      this.repoContext.dependencies
        .filter(dep => dep.usage === 'core')
        .slice(0, 5)
        .forEach(dep => {
          context += `- ${dep.name}: ${dep.commonPatterns.join(', ')}\n`;
        });
    }
    
    return context;
  }
  
  /**
   * Build constraints section
   */
  private buildConstraintsSection(constraints?: GenerationRequest['constraints']): string {
    if (!constraints) return '';
    
    let section = `CONSTRAINTS:\n`;
    
    if (constraints.preserveExisting) {
      section += `- Preserve existing code structure and functionality\n`;
    }
    
    if (constraints.followConventions) {
      section += `- Strictly follow established coding conventions\n`;
    }
    
    if (constraints.minimizeChanges) {
      section += `- Make minimal changes necessary to achieve the goal\n`;
    }
    
    return section;
  }
  
  /**
   * Build examples section based on repo patterns
   */
  private buildExamplesSection(): string {
    const patterns = this.repoContext.conventions.patterns;
    
    if (patterns.includes('react-patterns')) {
      return `
EXAMPLE PATTERNS (React):
- Use functional components with hooks
- Extract custom hooks for reusable logic
- Use proper TypeScript interfaces for props
- Follow component composition patterns
      `.trim();
    }
    
    if (patterns.includes('service-layer')) {
      return `
EXAMPLE PATTERNS (Service Layer):
- Separate business logic into service classes
- Use dependency injection patterns
- Implement proper error handling
- Follow repository pattern for data access
      `.trim();
    }
    
    return '';
  }
  
  /**
   * Build prompt for individual file generation
   */
  private async buildFileGenerationPrompt(
    filePath: string,
    requirements: string,
    existingContent?: string
  ): Promise<GenerationPrompt> {
    const systemPrompt = this.buildSystemPrompt();
    
    const userPrompt = `
Generate complete content for file: ${filePath}

REQUIREMENTS: ${requirements}

${existingContent ? `EXISTING CONTENT:\n\`\`\`\n${existingContent}\n\`\`\`\n` : ''}

Generate the complete file content following the repository conventions.
Return only the file content, no explanations or markdown formatting.
    `.trim();
    
    return { systemPrompt, userPrompt, context: '', examples: '' };
  }
  
  /**
   * Build prompt for generating file edits
   */
  private async buildEditGenerationPrompt(
    filePath: string,
    requirements: string,
    existingContent: string
  ): Promise<GenerationPrompt> {
    const systemPrompt = this.buildSystemPrompt();
    
    const userPrompt = `
Generate precise edits for file: ${filePath}

REQUIREMENTS: ${requirements}

EXISTING CONTENT:
\`\`\`
${existingContent}
\`\`\`

Generate minimal edits to achieve the requirements. Return JSON format:
{
  "edits": [
    {
      "type": "insert|replace|delete",
      "startLine": 10,
      "endLine": 15,
      "content": "new code",
      "reasoning": "explanation"
    }
  ]
}
    `.trim();
    
    return { systemPrompt, userPrompt, context: '', examples: '' };
  }
  
  /**
   * Convert raw LLM response to structured ChangePlan
   */
  private convertToChangePlan(intent: string, rawPlan: any): ChangePlan {
    let plan = ChangePlanBuilder.create(intent);
    plan.description = rawPlan.description || plan.description;
    plan.riskLevel = rawPlan.riskLevel || 'medium';
    plan.expectedOutcome = rawPlan.expectedOutcome || '';
    
    // Convert steps
    for (const rawStep of rawPlan.steps || []) {
      switch (rawStep.operation) {
        case 'create':
          plan = ChangePlanBuilder.addFileCreation(
            plan,
            rawStep.filePath,
            rawStep.content || '',
            rawStep.reasoning || ''
          );
          break;
          
        case 'modify':
          if (rawStep.edits) {
            const edits: FileEdit[] = rawStep.edits.map((edit: any) => ({
              type: edit.type,
              startLine: edit.startLine,
              endLine: edit.endLine,
              content: edit.content,
              reasoning: edit.reasoning
            }));
            
            plan = ChangePlanBuilder.addFileModification(
              plan,
              rawStep.filePath,
              edits,
              rawStep.reasoning || ''
            );
          }
          break;
          
        case 'delete':
          plan = ChangePlanBuilder.addFileDeletion(
            plan,
            rawStep.filePath,
            rawStep.reasoning || ''
          );
          break;
      }
    }
    
    return plan;
  }
  
  /**
   * Clean up generated code (remove markdown, fix formatting)
   */
  private cleanGeneratedCode(code: string): string {
    // Remove markdown code blocks
    code = code.replace(/```[\w]*\n/g, '').replace(/```/g, '');
    
    // Remove leading/trailing whitespace
    code = code.trim();
    
    // Ensure proper line endings
    code = code.replace(/\r\n/g, '\n');
    
    return code;
  }
}