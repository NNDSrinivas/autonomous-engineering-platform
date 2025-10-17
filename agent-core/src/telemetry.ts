export interface Telemetry {
  model: string;
  phase: string;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  timestamp: number;
}

export interface TelemetrySummary {
  total_calls: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  average_latency_ms: number;
  models_used: string[];
  phases_used: string[];
}

export const metrics: Telemetry[] = [];

export function record(telemetry: Telemetry): void {
  metrics.push({
    ...telemetry,
    timestamp: telemetry.timestamp || Date.now()
  });
}

export function summary(): TelemetrySummary {
  if (metrics.length === 0) {
    return {
      total_calls: 0,
      total_tokens: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_cost_usd: 0,
      average_latency_ms: 0,
      models_used: [],
      phases_used: []
    };
  }

  const total_calls = metrics.length;
  const total_tokens = metrics.reduce((sum, m) => sum + m.tokens, 0);
  const total_input_tokens = metrics.reduce((sum, m) => sum + m.input_tokens, 0);
  const total_output_tokens = metrics.reduce((sum, m) => sum + m.output_tokens, 0);
  const total_cost_usd = metrics.reduce((sum, m) => sum + m.cost_usd, 0);
  const total_latency = metrics.reduce((sum, m) => sum + m.latency_ms, 0);
  const average_latency_ms = total_latency / total_calls;
  
  const models_used = [...new Set(metrics.map(m => m.model))];
  const phases_used = [...new Set(metrics.map(m => m.phase))];

  return {
    total_calls,
    total_tokens,
    total_input_tokens,
    total_output_tokens,
    total_cost_usd: Math.round(total_cost_usd * 1000000) / 1000000, // Round to 6 decimal places
    average_latency_ms: Math.round(average_latency_ms * 100) / 100, // Round to 2 decimal places
    models_used,
    phases_used
  };
}

export function getMetrics(): Telemetry[] {
  return [...metrics]; // Return a copy
}

export function clearMetrics(): void {
  metrics.length = 0;
}

export function getMetricsForModel(model: string): Telemetry[] {
  return metrics.filter(m => m.model === model);
}

export function getMetricsForPhase(phase: string): Telemetry[] {
  return metrics.filter(m => m.phase === phase);
}

export function getCostBreakdown(): { [model: string]: number } {
  const breakdown: { [model: string]: number } = {};
  
  for (const metric of metrics) {
    if (!breakdown[metric.model]) {
      breakdown[metric.model] = 0;
    }
    breakdown[metric.model] += metric.cost_usd;
  }
  
  return breakdown;
}