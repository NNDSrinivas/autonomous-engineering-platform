import { coreApi } from './env';
import type { Plan, PlanItem } from './protocol';

export interface PlanResponse {
  plan: Plan;
  telemetry: {
    phase: string;
    model: string;
    tokens: number;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    latency_ms: number;
    timestamp: number;
  };
  key: string;
  timestamp: number;
  total_time_ms: number;
  cached: boolean;
}

export async function generatePlan(contextPack: any): Promise<PlanResponse> {
  const response = await fetch(`${coreApi()}/api/plan/${contextPack.ticket.key}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contextPack })
  });
  
  if (!response.ok) {
    throw new Error(`Plan generation failed: ${response.status} ${response.statusText}`);
  }
  
  return await response.json();
}

export async function getPlanMetrics(): Promise<any> {
  const response = await fetch(`${coreApi()}/api/plan/metrics`, {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get metrics: ${response.status} ${response.statusText}`);
  }
  
  return await response.json();
}

export async function clearPlanCache(): Promise<any> {
  const response = await fetch(`${coreApi()}/api/plan/clear-cache`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to clear cache: ${response.status} ${response.statusText}`);
  }
  
  return await response.json();
}