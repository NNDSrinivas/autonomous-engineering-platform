"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.metrics = void 0;
exports.record = record;
exports.summary = summary;
exports.getMetrics = getMetrics;
exports.clearMetrics = clearMetrics;
exports.getMetricsForModel = getMetricsForModel;
exports.getMetricsForPhase = getMetricsForPhase;
exports.getCostBreakdown = getCostBreakdown;
exports.metrics = [];
function record(telemetry) {
    exports.metrics.push({
        ...telemetry,
        timestamp: telemetry.timestamp || Date.now()
    });
}
function summary() {
    if (exports.metrics.length === 0) {
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
    const total_calls = exports.metrics.length;
    const total_tokens = exports.metrics.reduce((sum, m) => sum + m.tokens, 0);
    const total_input_tokens = exports.metrics.reduce((sum, m) => sum + m.input_tokens, 0);
    const total_output_tokens = exports.metrics.reduce((sum, m) => sum + m.output_tokens, 0);
    const total_cost_usd = exports.metrics.reduce((sum, m) => sum + m.cost_usd, 0);
    const total_latency = exports.metrics.reduce((sum, m) => sum + m.latency_ms, 0);
    const average_latency_ms = total_latency / total_calls;
    const models_used = [...new Set(exports.metrics.map(m => m.model))];
    const phases_used = [...new Set(exports.metrics.map(m => m.phase))];
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
function getMetrics() {
    return [...exports.metrics]; // Return a copy
}
function clearMetrics() {
    exports.metrics.length = 0;
}
function getMetricsForModel(model) {
    return exports.metrics.filter(m => m.model === model);
}
function getMetricsForPhase(phase) {
    return exports.metrics.filter(m => m.phase === phase);
}
function getCostBreakdown() {
    const breakdown = {};
    for (const metric of exports.metrics) {
        if (!breakdown[metric.model]) {
            breakdown[metric.model] = 0;
        }
        breakdown[metric.model] += metric.cost_usd;
    }
    return breakdown;
}
