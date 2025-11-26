"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.greet = greet;
exports.fetchContextPack = fetchContextPack;
exports.proposePlan = proposePlan;
exports.proposePlanLLM = proposePlanLLM;
const env_1 = require("./env");
const router_1 = require("./router");
const telemetry_1 = require("./telemetry");
async function greet() {
    const name = process.env.USER || 'Developer';
    const hr = new Date().getHours();
    const part = hr < 12 ? 'Morning' : hr < 18 ? 'Afternoon' : 'Evening';
    let tasks = [];
    try {
        const userId = process.env.DEV_USER_ID || 'default_user';
        const r = await fetch(`${(0, env_1.coreApi)()}/api/navi/jira-tasks?user_id=${userId}&limit=5`);
        const j = await r.json();
        tasks = (j.tasks || []).slice(0, 5).map((t) => ({
            key: t.jira_key,
            title: t.title?.replace(`[Jira] ${t.jira_key}: `, '') || t.jira_key,
            status: t.status
        }));
    }
    catch { }
    return { text: `Hello ${name}, Good ${part}! You have ${tasks.length} assigned tasks. Pick one to start:`, tasks };
}
async function fetchContextPack(key) {
    try {
        const r = await fetch(`${(0, env_1.coreApi)()}/api/context/task/${encodeURIComponent(key)}`);
        return await r.json();
    }
    catch {
        return { ticket: { key }, explain: { what: "", why: "", how: [] }, sources: {} };
    }
}
async function proposePlan(pack) {
    const files = ['backend/auth/jwt.py'];
    return {
        items: [
            { id: 'p1', kind: 'edit', desc: `Implement fix for ${pack?.ticket?.key || 'ticket'} (JWT expiry)`, files },
            { id: 'p2', kind: 'test', desc: 'Run focused tests', command: 'pytest -q tests/auth/test_jwt.py' },
            { id: 'p3', kind: 'cmd', desc: 'Run full test suite', command: 'pytest -q' },
            { id: 'p4', kind: 'git', desc: 'Create branch & commit', command: 'git checkout -b feat/jwt-expiry && git add -A && git commit -m "feat: jwt expiry fix (#ticket)"' }
        ]
    };
}
async function proposePlanLLM(pack) {
    try {
        const response = await (0, router_1.generatePlan)(pack);
        // Record telemetry data
        if (response.telemetry) {
            (0, telemetry_1.record)(response.telemetry);
        }
        return response.plan;
    }
    catch (error) {
        console.error('LLM plan generation failed:', error);
        // Fallback to hardcoded plan on error
        return proposePlan(pack);
    }
}
