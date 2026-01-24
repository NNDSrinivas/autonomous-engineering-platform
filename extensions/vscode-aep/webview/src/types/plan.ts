/**
 * Phase 4.1.2a - Planning Engine UI Types
 * 
 * Types for rendering structured plans in the UI instead of raw LLM text.
 */

// Intent Classification - Phase 4.1.2 Step 1
export enum IntentKind {
  REPO_INSPECTION = "repo_inspection",
  PLAN_TASK = "plan_task",
  CODE_ASSIST = "code_assist",
  FIX_DEBUG = "fix_debug",
  GENERAL_QUESTION = "general_question",
}

export interface PlanStep {
  id: string;
  title: string;
  rationale?: string;
  requires_approval?: boolean;
  tool?: string;
  input?: any;
  verify?: string[];
  status?: 'pending' | 'active' | 'completed' | 'failed' | 'skipped';
}

export interface Plan {
  id: string;
  goal: string;
  intent_kind?: string;
  steps: PlanStep[];
  requires_approval: boolean;
  confidence: number;
  reasoning: string;
  task_id?: string; // Top-level task ID for execution tracking
  diagnostics?: {
    total_count?: number;
    error_count?: number;
    warning_count?: number;
    fixable_count?: number;
    affected_files?: string[];
  };
  execution?: {
    task_id?: string;
    status?: string;
  };
}

export interface PlanResult {
  success: boolean;
  plan: Plan | null;
  reasoning: string;
  session_id: string | null;
  error: string | null;
}

export interface PlanRequest {
  intent: any; // NaviIntent from the classification
  intentKind: IntentKind; // Phase 4.1.2 - Required for planner
  context?: any;
  session_id?: string | null;
}
