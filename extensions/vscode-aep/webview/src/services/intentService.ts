/**
 * NAVI Intent Service
 * 
 * Phase 4.1.1: Intent Classification Layer
 * 
 * Handles intent classification by communicating with the backend agent system.
 * Provides the critical bridge between frontend messages and backend intelligence.
 */

import type {
  NaviIntent,
  IntentClassificationRequest,
  IntentClassificationResponse,
  AgentResponse
} from '../types/intent';
import { IntentFamily, IntentKind } from '../types/intent';
import { IntentKind as PlannerIntentKind } from '../types/plan';
import { resolveBackendBase, buildHeaders } from '../api/navi/client';

export class IntentService {
  private static instance: IntentService;

  public static getInstance(): IntentService {
    if (!IntentService.instance) {
      IntentService.instance = new IntentService();
    }
    return IntentService.instance;
  }

  /**
   * Phase 4.1.2 Step 2 - Generate Plan from Intent
   * 
   * Calls backend /api/navi/plan to create structured plan
   */
  async generatePlan(intent: NaviIntent, sessionId?: string): Promise<any> {
    try {
      const response = await fetch(`${resolveBackendBase()}/api/navi/plan`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          intent,
          session_id: sessionId || null
        })
      });

      if (!response.ok) {
        throw new Error(`Plan generation failed: ${response.status}`);
      }

      const planResult = await response.json();
      console.log('[IntentService] Plan generated:', planResult);
      return planResult;

    } catch (error) {
      console.error('[IntentService] Plan generation failed:', error);
      throw error;
    }
  }

  /**
   * Phase 4.1.2 Step 3/4 - Execute Next Tool or Process Tool Result
   * 
   * The core Tool → Verify loop endpoint
   */
  async executeNext(sessionId: string, toolResult?: any): Promise<any> {
    try {
      const response = await fetch(`${resolveBackendBase()}/api/navi/next`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          tool_result: toolResult || null
        })
      });

      if (!response.ok) {
        throw new Error(`Next execution failed: ${response.status}`);
      }

      const nextResult = await response.json();
      console.log('[IntentService] Next step:', nextResult);
      return nextResult;

    } catch (error) {
      console.error('[IntentService] Next execution failed:', error);
      throw error;
    }
  }

  /**
   * Phase 4.1.2 Step 1 - Intent Classification for Planning Engine
   * 
   * Maps user messages to specific IntentKind for structured planning.
   * This is the missing piece that enables the planner to work.
   */
  classifyIntentKind(message: string): PlannerIntentKind {
    const text = message.toLowerCase().trim();

    console.log('[IntentService] Classifying intent kind for:', text);

    // Phase 4.1.2: Enhanced classification for problems tab workflow
    if (text.includes('problems tab') || text.includes('fix errors') ||
      text.includes('diagnostics') || text.includes('fix problems')) {
      return PlannerIntentKind.FIX_DEBUG; // Maps to backend FIX_DIAGNOSTICS
    }

    // Rule-based classification (will be enhanced with LLM later)
    if (text.includes('repo') || text.includes('repository') || text.includes('workspace') || text.includes('project')) {
      return PlannerIntentKind.REPO_INSPECTION;
    }

    if (text.includes('plan') || text.includes('task') || text.includes('implement') || text.includes('create') || text.includes('build')) {
      return PlannerIntentKind.PLAN_TASK;
    }

    if (text.includes('fix') || text.includes('debug') || text.includes('error') || text.includes('bug') || text.includes('broken')) {
      return PlannerIntentKind.FIX_DEBUG;
    }

    if (text.includes('explain') || text.includes('help') || text.includes('assist') || text.includes('code') || text.includes('review')) {
      return PlannerIntentKind.CODE_ASSIST;
    }

    // Default fallback
    return PlannerIntentKind.GENERAL_QUESTION;
  }

  /**
   * Phase 4.1.1: Classify user message intent
   * 
   * This is the core function that determines what the user wants NAVI to do.
   * Uses the production backend intent classifier for accurate categorization.
   */
  async classifyMessage(request: IntentClassificationRequest): Promise<IntentClassificationResponse> {
    try {
      console.log('[IntentService] Classifying message:', request.message);

      const response = await fetch(`${resolveBackendBase()}/api/agent/classify`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          message: request.message,
          metadata: request.context?.metadata || {},
          repo: request.context?.workspaceRoot || null,
          source: 'chat'
        }),
      });

      if (!response.ok) {
        throw new Error(`Intent classification failed: ${response.status}`);
      }

      const data = await response.json();

      // Transform backend response to our frontend types
      const intent: NaviIntent = {
        id: data.intent.id,
        family: data.intent.family,
        kind: data.intent.kind,
        source: data.intent.source,
        priority: data.intent.priority,
        confidence: data.intent.confidence,
        provider: data.intent.provider,
        raw_text: data.intent.raw_text,
        requires_approval: data.intent.requires_approval,
        target: data.intent.target,
        parameters: data.intent.parameters || {},
        time: data.intent.time,
        model_used: data.intent.model_used,
        provider_used: data.intent.provider_used
      };

      console.log('[IntentService] Intent classified:', intent);

      return {
        intent,
        proposal: data.proposal, // Will be populated by planner later
        error: undefined
      };

    } catch (error) {
      console.error('[IntentService] Classification failed:', error);

      // Fallback to basic heuristic classification
      const fallbackIntent = this.fallbackClassification(request.message);

      return {
        intent: fallbackIntent,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }





  /**
   * Fallback classification when backend is unavailable
   * 
   * Uses simple heuristics to provide basic intent detection
   */
  private fallbackClassification(message: string): NaviIntent {
    const text = message.toLowerCase().trim();

    // Phase 4.1.2: Enhanced classification for first real workflow
    let kind = IntentKind.UNKNOWN;
    let family = IntentFamily.ENGINEERING;

    // Phase 4.1.2: Problems tab / diagnostics → FIX_DIAGNOSTICS
    if (text.includes('problems tab') || text.includes('fix errors') ||
      text.includes('diagnostics') || text.includes('fix problems')) {
      kind = IntentKind.FIX_DIAGNOSTICS;
    } else if (text.includes('explain') || text.includes('what does') || text.includes('how does')) {
      kind = IntentKind.EXPLAIN_CODE;
    } else if (text.includes('fix') || text.includes('debug') || text.includes('error')) {
      kind = IntentKind.FIX_BUG;
    } else if (text.includes('implement') || text.includes('create') || text.includes('add')) {
      kind = IntentKind.IMPLEMENT_FEATURE;
    } else if (text.includes('search') || text.includes('find')) {
      kind = IntentKind.SEARCH_CODE;
    } else if (text.includes('test') || text.includes('run tests')) {
      kind = IntentKind.RUN_TESTS;
    } else if (text.includes('hi') || text.includes('hello') || text.includes('hey')) {
      kind = IntentKind.GREET;
    }

    return {
      family,
      kind,
      source: 'chat' as any,
      priority: 'normal' as any,
      confidence: 0.5, // Lower confidence for fallback
      provider: 'generic' as any,
      raw_text: message,
      requires_approval: true,
      parameters: {}
    };
  }


}

export const intentService = IntentService.getInstance();
