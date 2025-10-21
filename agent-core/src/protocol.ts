export type TaskLite = { key: string; title: string; status?: string };
export type Greeting = { text: string; tasks: TaskLite[] };
export type PlanItemKind = 'edit' | 'test' | 'cmd' | 'git' | 'pr';
export type PlanItem = { id: string; kind: PlanItemKind; desc: string; files?: string[]; command?: string; patch?: string };
export type Plan = { items: PlanItem[] };

// Telemetry data for LLM operations
export type LLMTelemetry = {
  phase: string;
  model: string;
  tokens: number;
  cost_usd: number;
  latency_ms: number;
  timestamp: number;
};

// Plan with optional telemetry for LLM-generated plans
export type PlanWithTelemetry = Plan & { telemetry?: LLMTelemetry };

export type RpcReq =
  | { id: string; method: 'session.open'; params: { name?: string } }
  | { id: string; method: 'ticket.select'; params: { key: string } }
  | { id: string; method: 'plan.propose'; params: { key: string } }
  | { id: string; method: 'plan.runStep'; params: { step: PlanItem } }
  | { id: string; method: 'tools.readFile'; params: { path: string } };

export type RpcRes =
  | { id: string; ok: true; result: any }
  | { id: string; ok: false; error: string };