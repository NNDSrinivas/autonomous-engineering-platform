/**
 * Anomaly Detection Engine
 * 
 * Deterministic anomaly detection using statistical methods and thresholds.
 * No ML hallucination - pure signal-based detection for enterprise safety.
 */

import {
    MetricSeries,
    MetricDataPoint,
    Anomaly,
    AnomalyType,
    SeverityLevel,
    Evidence,
    EvidenceType
} from '../types';

/**
 * Detect anomalies in metric data
 */
export async function detectAnomalies(metrics: MetricSeries[]): Promise<Anomaly[]> {
    console.log(`🔍 Analyzing ${metrics.length} metric series for anomalies...`);
    
    const anomalies: Anomaly[] = [];
    
    for (const metric of metrics) {
        const metricAnomalies = await analyzeMetricForAnomalies(metric);
        anomalies.push(...metricAnomalies);
    }
    
    // Sort by severity and confidence
    anomalies.sort((a, b) => {
        const severityOrder = {
            [SeverityLevel.CRITICAL]: 4,
            [SeverityLevel.HIGH]: 3,
            [SeverityLevel.MEDIUM]: 2,
            [SeverityLevel.LOW]: 1,
            [SeverityLevel.INFO]: 0
        };
        
        if (severityOrder[a.severity] !== severityOrder[b.severity]) {
            return severityOrder[b.severity] - severityOrder[a.severity];
        }
        
        return b.confidence - a.confidence;
    });
    
    console.log(`🚨 Detected ${anomalies.length} anomalies`);
    return anomalies;
}

/**
 * Analyze a single metric series for anomalies
 */
async function analyzeMetricForAnomalies(metric: MetricSeries): Promise<Anomaly[]> {
    if (metric.dataPoints.length < 3) {
        return []; // Need at least 3 points for analysis
    }
    
    const anomalies: Anomaly[] = [];
    const dataPoints = metric.dataPoints.sort((a, b) => a.timestamp - b.timestamp);
    
    // Calculate baseline statistics from historical data
    const baseline = calculateBaseline(dataPoints);
    if (!baseline) {
        return [];
    }
    
    // Check for various anomaly types
    const latestPoint = dataPoints[dataPoints.length - 1];
    const latestValue = latestPoint.value;
    
    // Spike detection (sudden increase)
    const spikeAnomaly = detectSpike(metric, latestValue, baseline);
    if (spikeAnomaly) anomalies.push(spikeAnomaly);
    
    // Drop detection (sudden decrease for throughput metrics)
    const dropAnomaly = detectDrop(metric, latestValue, baseline);
    if (dropAnomaly) anomalies.push(dropAnomaly);
    
    // Threshold violations
    const thresholdAnomaly = detectThresholdViolation(metric, latestValue);
    if (thresholdAnomaly) anomalies.push(thresholdAnomaly);
    
    // Trend analysis (gradual changes)
    const trendAnomaly = detectTrend(metric, dataPoints);
    if (trendAnomaly) anomalies.push(trendAnomaly);
    
    return anomalies;
}

/**
 * Calculate baseline statistics for comparison
 */
function calculateBaseline(dataPoints: MetricDataPoint[]): any {
    if (dataPoints.length < 2) return null;
    
    // Use all but the last point as baseline (exclude current point)
    const baselinePoints = dataPoints.slice(0, -1);
    const values = baselinePoints.map(p => p.value);
    
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
    const stdDev = Math.sqrt(variance);
    
    const sorted = [...values].sort((a, b) => a - b);
    const p50 = sorted[Math.floor(sorted.length * 0.5)];
    const p95 = sorted[Math.floor(sorted.length * 0.95)];
    const p99 = sorted[Math.floor(sorted.length * 0.99)];
    
    return {
        mean,
        stdDev,
        min: Math.min(...values),
        max: Math.max(...values),
        p50,
        p95,
        p99,
        sampleSize: values.length
    };
}

/**
 * Detect spike anomalies (sudden increases)
 */
function detectSpike(metric: MetricSeries, currentValue: number, baseline: any): Anomaly | null {
    // Define spike thresholds based on metric type
    const spikeMultiplier = getSpikeThreshold(metric.name);
    const threshold = baseline.mean + (baseline.stdDev * spikeMultiplier);
    
    if (currentValue <= threshold) {
        return null;
    }
    
    const deviation = (currentValue - baseline.mean) / baseline.mean;
    const severity = calculateSpikeSeverity(deviation, metric.name);
    const confidence = Math.min(0.95, Math.max(0.6, deviation * 0.5));
    
    return {
        id: `spike_${metric.name}_${Date.now()}`,
        type: determineAnomalyType(metric.name, 'spike'),
        severity,
        metric: metric.name,
        startTime: Date.now(),
        current: currentValue,
        baseline: baseline.mean,
        deviation,
        confidence,
        description: `${metric.name} spiked to ${currentValue.toFixed(2)} (${(deviation * 100).toFixed(1)}% above baseline)`,
        evidence: [
            {
                type: EvidenceType.METRIC_SPIKE,
                content: `Current value: ${currentValue.toFixed(2)}, Baseline: ${baseline.mean.toFixed(2)} (±${baseline.stdDev.toFixed(2)})`,
                source: metric.metadata.source,
                relevance: 1.0
            }
        ]
    };
}

/**
 * Detect drop anomalies (sudden decreases in throughput)
 */
function detectDrop(metric: MetricSeries, currentValue: number, baseline: any): Anomaly | null {
    // Only check for drops in throughput/rate metrics
    if (!isThroughputMetric(metric.name)) {
        return null;
    }
    
    const dropThreshold = baseline.mean * 0.5; // 50% drop
    
    if (currentValue >= dropThreshold) {
        return null;
    }
    
    const deviation = (baseline.mean - currentValue) / baseline.mean;
    const severity = calculateDropSeverity(deviation);
    const confidence = Math.min(0.9, Math.max(0.7, deviation));
    
    return {
        id: `drop_${metric.name}_${Date.now()}`,
        type: AnomalyType.THROUGHPUT_DROP,
        severity,
        metric: metric.name,
        startTime: Date.now(),
        current: currentValue,
        baseline: baseline.mean,
        deviation,
        confidence,
        description: `${metric.name} dropped to ${currentValue.toFixed(2)} (${(deviation * 100).toFixed(1)}% below baseline)`,
        evidence: [
            {
                type: EvidenceType.METRIC_SPIKE,
                content: `Current value: ${currentValue.toFixed(2)}, Baseline: ${baseline.mean.toFixed(2)}`,
                source: metric.metadata.source,
                relevance: 1.0
            }
        ]
    };
}

/**
 * Detect threshold violations
 */
function detectThresholdViolation(metric: MetricSeries, currentValue: number): Anomaly | null {
    const thresholds = getMetricThresholds(metric.name);
    if (!thresholds) return null;
    
    let violatedThreshold: any = null;
    let severity = SeverityLevel.LOW;
    
    if (thresholds.critical && currentValue > thresholds.critical) {
        violatedThreshold = { level: 'critical', value: thresholds.critical };
        severity = SeverityLevel.CRITICAL;
    } else if (thresholds.high && currentValue > thresholds.high) {
        violatedThreshold = { level: 'high', value: thresholds.high };
        severity = SeverityLevel.HIGH;
    } else if (thresholds.medium && currentValue > thresholds.medium) {
        violatedThreshold = { level: 'medium', value: thresholds.medium };
        severity = SeverityLevel.MEDIUM;
    }
    
    if (!violatedThreshold) return null;
    
    const deviation = (currentValue - violatedThreshold.value) / violatedThreshold.value;
    
    return {
        id: `threshold_${metric.name}_${Date.now()}`,
        type: determineAnomalyType(metric.name, 'threshold'),
        severity,
        metric: metric.name,
        startTime: Date.now(),
        current: currentValue,
        baseline: violatedThreshold.value,
        deviation,
        confidence: 0.95, // High confidence for threshold violations
        description: `${metric.name} exceeded ${violatedThreshold.level} threshold (${currentValue.toFixed(2)} > ${violatedThreshold.value})`,
        evidence: [
            {
                type: EvidenceType.METRIC_SPIKE,
                content: `Threshold violation: ${currentValue.toFixed(2)} > ${violatedThreshold.value} (${violatedThreshold.level})`,
                source: metric.metadata.source,
                relevance: 1.0
            }
        ]
    };
}

/**
 * Detect trend anomalies (gradual changes)
 */
function detectTrend(metric: MetricSeries, dataPoints: MetricDataPoint[]): Anomaly | null {
    if (dataPoints.length < 5) return null; // Need more points for trend analysis
    
    // Calculate simple linear trend
    const values = dataPoints.map(p => p.value);
    const n = values.length;
    const x = Array.from({ length: n }, (_, i) => i);
    
    const sumX = x.reduce((sum, val) => sum + val, 0);
    const sumY = values.reduce((sum, val) => sum + val, 0);
    const sumXY = x.reduce((sum, val, i) => sum + val * values[i], 0);
    const sumXX = x.reduce((sum, val) => sum + val * val, 0);
    
    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    
    // Check if trend is significant
    const avgValue = sumY / n;
    const relativeSlope = Math.abs(slope) / avgValue;
    
    if (relativeSlope < 0.1) return null; // Trend not significant enough
    
    const isIncreasing = slope > 0;
    const severity = relativeSlope > 0.3 ? SeverityLevel.HIGH : 
                    relativeSlope > 0.2 ? SeverityLevel.MEDIUM : SeverityLevel.LOW;
    
    const anomalyType = isIncreasing ? 
        (isLatencyMetric(metric.name) ? AnomalyType.LATENCY_SPIKE : AnomalyType.ERROR_RATE_INCREASE) :
        AnomalyType.THROUGHPUT_DROP;
    
    return {
        id: `trend_${metric.name}_${Date.now()}`,
        type: anomalyType,
        severity,
        metric: metric.name,
        startTime: dataPoints[0].timestamp,
        endTime: dataPoints[dataPoints.length - 1].timestamp,
        current: values[values.length - 1],
        baseline: values[0],
        deviation: relativeSlope,
        confidence: Math.min(0.8, relativeSlope * 2),
        description: `${metric.name} shows ${isIncreasing ? 'increasing' : 'decreasing'} trend (${(relativeSlope * 100).toFixed(1)}% change)`,
        evidence: [
            {
                type: EvidenceType.PATTERN_MATCH,
                content: `Trend analysis: slope=${slope.toFixed(4)}, relative change=${(relativeSlope * 100).toFixed(1)}%`,
                source: metric.metadata.source,
                relevance: 0.8
            }
        ]
    };
}

/**
 * Get spike detection threshold based on metric type
 */
function getSpikeThreshold(metricName: string): number {
    const lowerName = metricName.toLowerCase();
    
    if (lowerName.includes('error') || lowerName.includes('failure')) {
        return 2; // More sensitive for error rates
    }
    if (lowerName.includes('latency') || lowerName.includes('duration')) {
        return 2; // Sensitive for latency metrics
    }
    if (lowerName.includes('cpu') || lowerName.includes('memory')) {
        return 2.5; // Less sensitive for resource utilization
    }
    
    return 3; // Default threshold
}

/**
 * Calculate severity based on spike deviation
 */
function calculateSpikeSeverity(deviation: number, metricName: string): SeverityLevel {
    if (isLatencyMetric(metricName)) {
        if (deviation > 2.0) return SeverityLevel.CRITICAL;
        if (deviation > 1.0) return SeverityLevel.HIGH;
        if (deviation > 0.5) return SeverityLevel.MEDIUM;
        return SeverityLevel.LOW;
    }
    
    if (isErrorRateMetric(metricName)) {
        if (deviation > 5.0) return SeverityLevel.CRITICAL;
        if (deviation > 2.0) return SeverityLevel.HIGH;
        if (deviation > 1.0) return SeverityLevel.MEDIUM;
        return SeverityLevel.LOW;
    }
    
    // Default severity calculation
    if (deviation > 3.0) return SeverityLevel.CRITICAL;
    if (deviation > 2.0) return SeverityLevel.HIGH;
    if (deviation > 1.0) return SeverityLevel.MEDIUM;
    return SeverityLevel.LOW;
}

/**
 * Calculate severity for drop anomalies
 */
function calculateDropSeverity(deviation: number): SeverityLevel {
    if (deviation > 0.8) return SeverityLevel.CRITICAL; // 80% drop
    if (deviation > 0.6) return SeverityLevel.HIGH;     // 60% drop
    if (deviation > 0.4) return SeverityLevel.MEDIUM;   // 40% drop
    return SeverityLevel.LOW;
}

/**
 * Determine anomaly type based on metric name and detection method
 */
function determineAnomalyType(metricName: string, detectionMethod: string): AnomalyType {
    const lowerName = metricName.toLowerCase();
    
    if (lowerName.includes('latency') || lowerName.includes('duration') || lowerName.includes('response_time')) {
        return AnomalyType.LATENCY_SPIKE;
    }
    if (lowerName.includes('error') || lowerName.includes('failure') || lowerName.includes('5xx')) {
        return AnomalyType.ERROR_RATE_INCREASE;
    }
    if (lowerName.includes('throughput') || lowerName.includes('requests') || lowerName.includes('rps')) {
        return detectionMethod === 'drop' ? AnomalyType.THROUGHPUT_DROP : AnomalyType.LATENCY_SPIKE;
    }
    if (lowerName.includes('cpu') || lowerName.includes('memory') || lowerName.includes('disk')) {
        return AnomalyType.RESOURCE_SATURATION;
    }
    if (lowerName.includes('availability') || lowerName.includes('uptime')) {
        return AnomalyType.AVAILABILITY_DEGRADATION;
    }
    
    return AnomalyType.LATENCY_SPIKE; // Default
}

/**
 * Check if metric represents latency/duration
 */
function isLatencyMetric(metricName: string): boolean {
    const lowerName = metricName.toLowerCase();
    return lowerName.includes('latency') || 
           lowerName.includes('duration') || 
           lowerName.includes('response_time') ||
           lowerName.includes('time');
}

/**
 * Check if metric represents error rate
 */
function isErrorRateMetric(metricName: string): boolean {
    const lowerName = metricName.toLowerCase();
    return lowerName.includes('error') || 
           lowerName.includes('failure') || 
           lowerName.includes('5xx') ||
           lowerName.includes('exception');
}

/**
 * Check if metric represents throughput
 */
function isThroughputMetric(metricName: string): boolean {
    const lowerName = metricName.toLowerCase();
    return lowerName.includes('throughput') || 
           lowerName.includes('requests') || 
           lowerName.includes('rps') ||
           lowerName.includes('qps') ||
           lowerName.includes('rate');
}

/**
 * Get predefined thresholds for common metrics
 */
function getMetricThresholds(metricName: string): any {
    const lowerName = metricName.toLowerCase();
    
    if (lowerName.includes('cpu') && lowerName.includes('percent')) {
        return { medium: 70, high: 85, critical: 95 };
    }
    if (lowerName.includes('memory') && lowerName.includes('percent')) {
        return { medium: 80, high: 90, critical: 95 };
    }
    if (lowerName.includes('disk') && lowerName.includes('percent')) {
        return { medium: 80, high: 90, critical: 95 };
    }
    if (lowerName.includes('error_rate') || lowerName.includes('error') && lowerName.includes('rate')) {
        return { medium: 0.01, high: 0.05, critical: 0.1 }; // 1%, 5%, 10%
    }
    if (lowerName.includes('latency') && lowerName.includes('p95')) {
        return { medium: 500, high: 1000, critical: 2000 }; // milliseconds
    }
    
    return null; // No predefined thresholds
}