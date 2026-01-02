/**
 * Regression Detection for NAVI Observability & Metrics Analyzer
 * 
 * This module provides regression detection compatibility wrapper around the
 * main RegressionDetector class for backward compatibility with existing code.
 */

import { MetricSeries, ObservabilityContext, TraceSpan } from '../types';
import { RegressionDetector, DEFAULT_REGRESSION_CONFIG } from '../src/analysis/regressionDetector';

/**
 * Detect performance regressions in metrics and traces
 * @param metrics Array of metric series to analyze
 * @param traces Array of trace spans for additional context
 * @returns Array of detected regression alerts
 */
export async function detectRegressions(metrics: MetricSeries[], traces?: TraceSpan[]): Promise<any[]> {
    const detector = new RegressionDetector(DEFAULT_REGRESSION_CONFIG);
    const context: ObservabilityContext = {
        metrics,
        logs: [],
        traces: traces ?? []
    };
    
    const alerts = await detector.detectRegressions(context);
    
    // Return the raw alerts for now - the caller will handle proper formatting
    return alerts;
}
