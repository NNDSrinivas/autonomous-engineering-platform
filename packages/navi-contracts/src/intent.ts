/**
 * Intent classification contracts
 * Defines the standardized intent types and validation logic
 */

/**
 * Standardized intent kinds that both extension and backend must recognize
 */
export enum IntentKind {
  GENERAL_CHAT = 'GENERAL_CHAT',
  FIX_PROBLEMS = 'FIX_PROBLEMS', 
  ANALYZE_PROJECT = 'ANALYZE_PROJECT',
  DEPLOY = 'DEPLOY',
  CLARIFY = 'CLARIFY'
}

/**
 * Intent classification request
 */
export interface IntentRequest {
  message: string;
  context?: {
    activeFile?: string;
    diagnosticsCount?: number;
    hasGitChanges?: boolean;
  };
}

/**
 * Intent classification response
 */
export interface IntentResponse {
  kind: IntentKind;
  confidence: number;
  reasoning?: string;
  fallbackApplied?: boolean;
}

/**
 * Fallback handler for unknown or ambiguous intents
 */
export function getFallbackIntent(message: string): IntentResponse {
  // Simple heuristics for fallback - never let "hi" break anything
  const lowerMessage = message.toLowerCase().trim();
  
  if (lowerMessage.includes('fix') || lowerMessage.includes('error') || lowerMessage.includes('problem')) {
    return {
      kind: IntentKind.FIX_PROBLEMS,
      confidence: 0.6,
      reasoning: 'Detected problem-solving keywords in fallback analysis',
      fallbackApplied: true
    };
  }
  
  if (lowerMessage.includes('deploy') || lowerMessage.includes('build')) {
    return {
      kind: IntentKind.DEPLOY,
      confidence: 0.6,
      reasoning: 'Detected deployment keywords in fallback analysis',
      fallbackApplied: true
    };
  }
  
  if (lowerMessage.includes('analyze') || lowerMessage.includes('explain') || lowerMessage.includes('what')) {
    return {
      kind: IntentKind.ANALYZE_PROJECT,
      confidence: 0.6,
      reasoning: 'Detected analysis keywords in fallback analysis',
      fallbackApplied: true
    };
  }
  
  // Default fallback to general chat - never breaks
  return {
    kind: IntentKind.GENERAL_CHAT,
    confidence: 0.8,
    reasoning: 'Default fallback to general conversation',
    fallbackApplied: true
  };
}

/**
 * Validates that an intent kind is supported
 */
export function isValidIntentKind(kind: string): kind is IntentKind {
  return Object.values(IntentKind).includes(kind as IntentKind);
}

/**
 * Safe intent kind parser with fallback
 */
export function parseIntentKind(kind: unknown): IntentKind {
  if (typeof kind === 'string' && isValidIntentKind(kind)) {
    return kind;
  }
  return IntentKind.GENERAL_CHAT; // Safe fallback
}