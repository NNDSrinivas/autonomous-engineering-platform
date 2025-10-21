import { coreApi } from './env';
import type { Greeting, Plan, PlanItem, PlanWithTelemetry } from './protocol';
import { generatePlan } from './router';
import { record } from './telemetry';

export async function greet(): Promise<Greeting> {
  const name = process.env.USER || 'Developer';
  const hr = new Date().getHours();
  const part = hr < 12 ? 'Morning' : hr < 18 ? 'Afternoon' : 'Evening';
  let tasks: any[] = [];
  try {
    const r = await fetch(`${coreApi()}/api/jira/tasks`);
    const j = await r.json();
    tasks = (j.items || []).slice(0, 5).map((t: any) => ({ key: t.key, title: t.summary, status: t.status }));
  } catch {}
  return { text: `Hello ${name}, Good ${part}! You have ${tasks.length} assigned tasks. Pick one to start:`, tasks };
}

export async function fetchContextPack(key: string): Promise<any> {
  try {
    const r = await fetch(`${coreApi()}/api/context/task/${encodeURIComponent(key)}`);
    return await r.json();
  } catch {
    return { ticket: { key }, explain: { what: "", why: "", how: [] }, sources: {} };
  }
}

export async function proposePlan(pack: any): Promise<Plan> {
  const files = ['backend/auth/jwt.py'];
  return {
    items: [
      { id: 'p1', kind: 'edit', desc: `Implement fix for ${pack?.ticket?.key || 'ticket'} (JWT expiry)`, files },
      { id: 'p2', kind: 'test', desc: 'Run focused tests', command: 'pytest -q tests/auth/test_jwt.py' },
      { id: 'p3', kind: 'cmd',  desc: 'Run full test suite', command: 'pytest -q' },
      { id: 'p4', kind: 'git',  desc: 'Create branch & commit', command: 'git checkout -b feat/jwt-expiry && git add -A && git commit -m "feat: jwt expiry fix (#ticket)"' }
    ]
  };
}

export async function proposePlanLLM(pack: any): Promise<PlanWithTelemetry> {
  try {
    const response = await generatePlan(pack);
    
    // Record telemetry data
    if (response.telemetry) {
      record(response.telemetry);
    }
    
    // Return plan with telemetry
    return { 
      ...response.plan, 
      telemetry: response.telemetry 
    };
  } catch (error) {
    console.error('LLM plan generation failed:', error);
    
    // Fallback to hardcoded plan on error
    return proposePlan(pack);
  }
}