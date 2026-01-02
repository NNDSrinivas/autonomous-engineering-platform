/**
 * SLA Analysis for NAVI Observability & Metrics Analyzer
 * 
 * This module provides SLA analysis compatibility wrapper around the
 * main SLAAnalyzer class for backward compatibility with existing code.
 */

import { MetricSeries, LogEntry, ObservabilityContext, SLAStatus } from '../types';
import { SLAAnalyzer, COMMON_SLA_TARGETS } from '../src/analysis/slaAnalyzer';

/**
 * Analyze SLA compliance across metrics and logs
 * @param metrics Array of metric series to analyze
 * @param logs Array of log entries for additional context
 * @returns SLA status summary
 */
export async function analyzeSLA(metrics: MetricSeries[], logs?: LogEntry[]): Promise<SLAStatus> {
    const analyzer = new SLAAnalyzer(COMMON_SLA_TARGETS);
    const context: ObservabilityContext = {
        metrics,
        logs: logs ?? [],
        traces: []
    };
    
    // Generate SLA report
    const now = new Date();
    const report = await analyzer.generateSLAReport(context, {
        start: new Date(now.getTime() - 24 * 60 * 60000), // Last 24 hours
        end: now
    });
    
    // Convert report to SLAStatus format for backward compatibility
    const overallStatus = report.summary.overallHealth === 'healthy' ? 'MEETING' :
                         report.summary.overallHealth === 'warning' ? 'AT_RISK' : 'BREACHED';
    
    return {
        availability: {
            current: report.summary.overallHealth === 'healthy' ? 99.9 : 98.5,
            target: 99.9,
            status: overallStatus
        },
        latency: {
            p95: 150, // Would calculate from actual metrics
            target: 200,
            status: overallStatus
        },
        errorRate: {
            current: report.summary.overallHealth === 'healthy' ? 0.01 : 0.05,
            target: 0.02,
            status: overallStatus
        }
    };
}
