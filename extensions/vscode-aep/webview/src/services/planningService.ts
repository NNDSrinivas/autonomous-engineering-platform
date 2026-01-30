/**
 * Phase 4.1.2a - Planning Service
 * 
 * Service to generate structured plans from classified intents.
 * Replaces generic LLM responses with intelligent, actionable plans.
 */

import type { PlanRequest, PlanResult, Plan } from '../types/plan';
import { IntentKind } from '../types/plan';
import { resolveBackendBase, buildHeaders } from '../api/navi/client';

export class PlanningService {
  private static instance: PlanningService;
  
  public static getInstance(): PlanningService {
    if (!PlanningService.instance) {
      PlanningService.instance = new PlanningService();
    }
    return PlanningService.instance;
  }

  /**
   * Generate a structured plan from a classified intent.
   * This is the core of Phase 4.1.2 - transforming intents into actionable plans.
   */
  async generatePlan(request: PlanRequest): Promise<PlanResult> {
    try {
      console.log('[PlanningService] Generating plan for intentKind:', request.intentKind);
      
      // Map IntentKind to backend format
      const backendIntent = this.mapIntentKindToBackend(request.intentKind, request.intent);
      
      const response = await fetch(`${resolveBackendBase()}/api/agent/plan`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          intent: backendIntent,
          context: request.context,
          session_id: request.session_id
        }),
      });

      if (!response.ok) {
        throw new Error(`Plan generation failed: ${response.status}`);
      }

      const data = await response.json();
      console.log('[PlanningService] Plan generated:', data.plan?.title);

      return {
        success: data.success,
        plan: data.plan,
        reasoning: data.reasoning,
        session_id: data.session_id,
        error: data.error
      };

    } catch (error) {
      console.error('[PlanningService] Plan generation failed:', error);
      
      // Return error result
      return {
        success: false,
        plan: null,
        reasoning: 'Plan generation failed',
        session_id: request.session_id || null,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  /**
   * Map IntentKind to backend NaviIntent format
   */
  private mapIntentKindToBackend(intentKind: IntentKind, originalIntent: any): any {
    // Map our IntentKind enum to backend's expected intent format
    const kindMapping = {
      [IntentKind.REPO_INSPECTION]: 'inspect_repo',
      [IntentKind.PLAN_TASK]: 'implement_feature', 
      [IntentKind.CODE_ASSIST]: 'explain_code',
      [IntentKind.FIX_DEBUG]: 'fix_bug',
      [IntentKind.GENERAL_QUESTION]: 'greet'
    };

    return {
      family: originalIntent?.family || 'engineering',
      kind: kindMapping[intentKind] || 'greet',
      priority: originalIntent?.priority || 'normal',
      requires_approval: originalIntent?.requires_approval || false,
      target: originalIntent?.target || null,
      parameters: originalIntent?.parameters || {},
      confidence: originalIntent?.confidence || 0.8,
      raw_text: originalIntent?.raw_text || 'User request'
    };
  }
}

export const planningService = PlanningService.getInstance();
