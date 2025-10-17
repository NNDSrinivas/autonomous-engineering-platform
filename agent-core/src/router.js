"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.generatePlan = generatePlan;
exports.getPlanMetrics = getPlanMetrics;
exports.clearPlanCache = clearPlanCache;
const env_1 = require("./env");
async function generatePlan(contextPack) {
    const response = await fetch(`${(0, env_1.coreApi)()}/api/plan/${contextPack.ticket.key}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contextPack })
    });
    if (!response.ok) {
        throw new Error(`Plan generation failed: ${response.status} ${response.statusText}`);
    }
    return await response.json();
}
async function getPlanMetrics() {
    const response = await fetch(`${(0, env_1.coreApi)()}/api/plan/metrics`, {
        method: "GET",
        headers: { "Content-Type": "application/json" }
    });
    if (!response.ok) {
        throw new Error(`Failed to get metrics: ${response.status} ${response.statusText}`);
    }
    return await response.json();
}
async function clearPlanCache() {
    const response = await fetch(`${(0, env_1.coreApi)()}/api/plan/clear-cache`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    });
    if (!response.ok) {
        throw new Error(`Failed to clear cache: ${response.status} ${response.statusText}`);
    }
    return await response.json();
}
