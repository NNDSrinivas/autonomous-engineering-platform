/**
 * LLM Provider interface for Phase 3 components
 */

export interface LLMRequest {
  prompt: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
}

export interface LLMResponse {
  content: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

export interface LLMProvider {
  generateText(request: LLMRequest): Promise<LLMResponse>;
  generateCode(request: LLMRequest): Promise<LLMResponse>;
  chat(messages: Array<{role: string; content: string}>): Promise<LLMResponse>;
}