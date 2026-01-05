/**
 * Plan and task execution contracts
 * Defines the structure for planned actions and execution steps
 */

/**
 * A planned step in task execution
 */
export interface PlanStep {
  id: string;
  title: string;
  description: string;
  tool?: string;
  inputs?: Record<string, unknown>;
  successCriteria?: string[];
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  result?: unknown;
  error?: string;
}

/**
 * A complete execution plan
 */
export interface Plan {
  id: string;
  goal: string;
  rationale: string;
  steps: PlanStep[];
  estimatedDuration?: number;
  prerequisites?: string[];
  risks?: string[];
  createdAt: string;
  updatedAt?: string;
  status: 'draft' | 'approved' | 'executing' | 'completed' | 'failed' | 'cancelled';
}

/**
 * Request to create a plan
 */
export interface CreatePlanRequest {
  goal: string;
  context?: {
    intentKind: string;
    userMessage: string;
    workspace?: {
      rootPath: string;
      activeFile?: string;
    };
    diagnostics?: {
      errorCount: number;
      warningCount: number;
      files: string[];
    };
  };
}

/**
 * Response containing a generated plan
 */
export interface CreatePlanResponse {
  plan: Plan;
  confidence: number;
  reasoning?: string;
}

/**
 * Plan execution status update
 */
export interface PlanStatusUpdate {
  planId: string;
  stepId?: string;
  status: 'running' | 'completed' | 'failed' | 'skipped';
  result?: unknown;
  error?: string;
  progress?: {
    completedSteps: number;
    totalSteps: number;
    currentStep?: string;
  };
}

/**
 * Creates a minimal valid plan for fallback scenarios
 */
export function createFallbackPlan(goal: string, reasoning = 'Fallback plan created'): Plan {
  return {
    id: `fallback-${Date.now()}`,
    goal,
    rationale: reasoning,
    steps: [
      {
        id: 'fallback-step-1',
        title: 'Acknowledge Request',
        description: `I understand you want to: ${goal}. Let me help with that.`,
        successCriteria: ['User request acknowledged']
      }
    ],
    createdAt: new Date().toISOString(),
    status: 'draft'
  };
}

/**
 * Validates a plan structure
 */
export function validatePlan(plan: unknown): plan is Plan {
  if (!plan || typeof plan !== 'object') return false;
  
  const p = plan as Partial<Plan>;
  return !!(
    p.id &&
    p.goal &&
    p.rationale &&
    Array.isArray(p.steps) &&
    p.createdAt &&
    p.status
  );
}

/**
 * Safe plan parser with validation
 */
export function parsePlan(data: unknown): Plan | null {
  if (validatePlan(data)) {
    return data;
  }
  return null;
}