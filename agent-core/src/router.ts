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
  // Validate inputs
  if (
    !contextPack ||
    !contextPack.ticket ||
    typeof contextPack.ticket.key !== "string" ||
    contextPack.ticket.key.trim().length === 0
  ) {
    throw new Error("Invalid contextPack: missing or empty ticket.key");
  }

  // Extract and validate ticket key before API call
  const ticketKey = contextPack.ticket.key;
  if (!ticketKey) {
    throw new Error("Ticket key is required for plan generation");
  }

  const response = await fetch(`${coreApi()}/api/plan/${ticketKey}`, {
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