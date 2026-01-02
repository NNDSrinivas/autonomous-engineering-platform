/**
 * Signal Correlation for NAVI Observability & Metrics Analyzer
 * 
 * This module provides correlation analysis compatibility wrapper around the
 * main CorrelationEngine class for backward compatibility with existing code.
 */

import {
    Anomaly,
    AnomalyType,
    LogEntry,
    MetricAggregation,
    MetricSeries,
    MetricSource,
    MetricType,
    ObservabilityContext,
    TraceSpan
} from '../types';
import { CorrelationEngine, DEFAULT_CORRELATION_CONFIG } from '../src/analysis/correlation';

/**
 * Correlate signals across anomalies, logs, and traces
 * @param anomalies Array of detected anomalies
 * @param logs Array of log entries
 * @param traces Array of trace spans
 * @returns Array of correlated data groups
 */
export async function correlateSignals(
    anomalies: Anomaly[], 
    logs: LogEntry[], 
    traces: TraceSpan[]
): Promise<any[]> {
    const engine = new CorrelationEngine(DEFAULT_CORRELATION_CONFIG);
    
    // Convert anomalies to metrics for correlation analysis
    const metrics: MetricSeries[] = anomalies.map(anomaly => ({
        name: anomaly.metric || anomaly.id || 'unknown_metric',
        unit: 'unknown',
        dataPoints: [{
            timestamp: anomaly.startTime,
            value: anomaly.current,
            labels: {}
        }],
        metadata: {
            source: MetricSource.CUSTOM,
            interval: 'event',
            aggregation: MetricAggregation.AVERAGE
        },
        metricType: mapAnomalyMetricType(anomaly.type),
        source: MetricSource.CUSTOM
    }));
    
    const context: ObservabilityContext = {
        metrics,
        logs,
        traces
    };
    
    const insights = await engine.analyzeCorrelations(context);
    
    // Return correlation insights as correlated data groups
    return insights.map(insight => ({
        id: insight.id,
        type: insight.type,
        signals: [insight.title],
        confidence: insight.confidence,
        description: insight.description,
        businessImpact: insight.businessImpact,
        technicalDetails: insight.technicalDetails,
        correlationData: insight.correlationResult || insight.logCorrelation || insight.cascadingPattern || insight.seasonalPattern
    }));
}

function mapAnomalyMetricType(type: AnomalyType): MetricType {
    switch (type) {
        case AnomalyType.LATENCY_SPIKE:
            return MetricType.RESPONSE_TIME;
        case AnomalyType.ERROR_RATE_INCREASE:
            return MetricType.ERROR_RATE;
        case AnomalyType.THROUGHPUT_DROP:
            return MetricType.THROUGHPUT;
        case AnomalyType.RESOURCE_SATURATION:
            return MetricType.RESOURCE_UTILIZATION;
        case AnomalyType.AVAILABILITY_DEGRADATION:
        case AnomalyType.SLA_BREACH:
            return MetricType.AVAILABILITY;
        default:
            return MetricType.BUSINESS_METRIC;
    }
}
