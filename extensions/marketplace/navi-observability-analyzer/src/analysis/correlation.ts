/**
 * Correlation Engine for NAVI Observability & Metrics Analyzer
 * 
 * This module provides advanced signal correlation analysis to identify
 * relationships between metrics, logs, and traces for root cause analysis
 * and predictive insights using deterministic mathematical methods.
 */

import { 
  MetricSeries, 
  LogEntry, 
  TraceSpan, 
  ObservabilityContext, 
  CorrelationInsight,
  MetricType 
} from '../../types';

export interface CorrelationConfig {
  // Minimum correlation coefficient to consider significant
  minCorrelationStrength: number;
  
  // Time window for correlation analysis (minutes)
  analysisWindow: number;
  
  // Maximum time lag to consider for cross-correlation (minutes)
  maxTimeLag: number;
  
  // Minimum data points required for correlation
  minDataPoints: number;
  
  // Correlation types to analyze
  enabledAnalysis: {
    metricToMetric: boolean;
    metricToLog: boolean;
    metricToTrace: boolean;
    logToTrace: boolean;
    seasonalPatterns: boolean;
    cascadingFailures: boolean;
  };
}

export interface CorrelationResult {
  sourceSignal: string;
  targetSignal: string;
  correlationType: 'positive' | 'negative' | 'leading' | 'lagging';
  strength: number; // -1 to 1
  confidence: number; // 0 to 1
  timeLag: number; // minutes
  significance: 'weak' | 'moderate' | 'strong' | 'very_strong';
  description: string;
  businessContext: string;
  technicalImplication: string[];
}

export interface CascadingFailurePattern {
  id: string;
  triggerEvent: {
    type: 'metric_spike' | 'error_surge' | 'latency_increase' | 'availability_drop';
    source: string;
    timestamp: Date;
    severity: number;
  };
  propagationChain: Array<{
    service: string;
    metricName: string;
    delay: number; // minutes after trigger
    impact: 'minor' | 'moderate' | 'major' | 'critical';
  }>;
  rootCause: {
    service: string;
    component: string;
    confidence: number;
    evidence: string[];
  };
  mitigation: string[];
}

export interface SeasonalPattern {
  patternId: string;
  metricName: string;
  patternType: 'daily' | 'weekly' | 'monthly' | 'hourly';
  amplitude: number;
  baselineValue: number;
  peakTimes: string[]; // e.g., ["09:00", "13:00", "17:00"]
  confidence: number;
  businessContext: string;
  predictiveInsights: string[];
}

export interface LogMetricCorrelation {
  logPattern: string;
  metricName: string;
  correlation: {
    type: 'precedes' | 'follows' | 'concurrent';
    strength: number;
    timeDelta: number; // seconds
  };
  businessImpact: string;
  actionable: boolean;
  recommendations: string[];
}

export class CorrelationEngine {
  constructor(private config: CorrelationConfig) {}

  /**
   * Perform comprehensive correlation analysis
   */
  async analyzeCorrelations(context: ObservabilityContext): Promise<CorrelationInsight[]> {
    const insights: CorrelationInsight[] = [];

    try {
      // Metric-to-metric correlations
      if (this.config.enabledAnalysis.metricToMetric) {
        const metricCorrelations = await this.analyzeMetricCorrelations(context.metrics);
        insights.push(...metricCorrelations);
      }

      // Metric-to-log correlations
      if (this.config.enabledAnalysis.metricToLog && context.logs) {
        const logCorrelations = await this.analyzeMetricLogCorrelations(context.metrics, context.logs);
        insights.push(...logCorrelations);
      }

      // Cascading failure detection
      if (this.config.enabledAnalysis.cascadingFailures) {
        const cascadingPatterns = await this.detectCascadingFailures(context);
        insights.push(...cascadingPatterns);
      }

      // Seasonal pattern detection
      if (this.config.enabledAnalysis.seasonalPatterns) {
        const seasonalInsights = await this.detectSeasonalPatterns(context.metrics);
        insights.push(...seasonalInsights);
      }

      // Trace correlation (if traces available)
      if (this.config.enabledAnalysis.metricToTrace && context.traces) {
        const traceCorrelations = await this.analyzeTraceCorrelations(context.metrics, context.traces);
        insights.push(...traceCorrelations);
      }

    } catch (error) {
      console.error('Correlation analysis failed:', error);
    }

    return this.rankInsightsByImportance(insights);
  }

  /**
   * Analyze correlations between metrics
   */
  private async analyzeMetricCorrelations(metrics: MetricSeries[]): Promise<CorrelationInsight[]> {
    const insights: CorrelationInsight[] = [];

    for (let i = 0; i < metrics.length; i++) {
      for (let j = i + 1; j < metrics.length; j++) {
        const correlation = this.calculatePearsonCorrelation(metrics[i], metrics[j]);
        
        if (Math.abs(correlation.strength) >= this.config.minCorrelationStrength) {
          const severity = this.inferSeverity(correlation.confidence, Math.abs(correlation.strength));
          insights.push({
            id: `metric-correlation-${i}-${j}`,
            type: 'correlation',
            severity,
            title: `${metrics[i].name} ↔ ${metrics[j].name}`,
            description: correlation.description,
            confidence: correlation.confidence,
            businessImpact: this.assessBusinessImpact(correlation),
            technicalDetails: correlation.technicalImplication,
            affectedResources: [metrics[i].name, metrics[j].name],
            recommendedActions: this.recommendCorrelationActions(metrics[i], metrics[j], correlation),
            correlationResult: correlation,
            detectedAt: new Date()
          });
        }
      }
    }

    return insights;
  }

  /**
   * Calculate Pearson correlation coefficient between two metrics
   */
  private calculatePearsonCorrelation(metric1: MetricSeries, metric2: MetricSeries): CorrelationResult {
    // Align time series by timestamp
    const alignedData = this.alignTimeSeries(metric1, metric2);
    
    if (alignedData.length < this.config.minDataPoints) {
      return this.createNullCorrelation(metric1.name, metric2.name);
    }

    const values1 = alignedData.map(d => d.value1);
    const values2 = alignedData.map(d => d.value2);

    // Calculate Pearson correlation coefficient
    const mean1 = values1.reduce((a, b) => a + b, 0) / values1.length;
    const mean2 = values2.reduce((a, b) => a + b, 0) / values2.length;

    let numerator = 0;
    let sumSq1 = 0;
    let sumSq2 = 0;

    for (let i = 0; i < values1.length; i++) {
      const diff1 = values1[i] - mean1;
      const diff2 = values2[i] - mean2;
      
      numerator += diff1 * diff2;
      sumSq1 += diff1 * diff1;
      sumSq2 += diff2 * diff2;
    }

    const denominator = Math.sqrt(sumSq1 * sumSq2);
    const correlation = denominator === 0 ? 0 : numerator / denominator;

    // Determine correlation type and significance
    const correlationType = correlation > 0 ? 'positive' : 'negative';
    const strength = Math.abs(correlation);
    const significance = this.classifyCorrelationStrength(strength);
    
    // Calculate statistical confidence
    const confidence = this.calculateConfidence(correlation, alignedData.length);

    return {
      sourceSignal: metric1.name,
      targetSignal: metric2.name,
      correlationType,
      strength: correlation,
      confidence,
      timeLag: 0, // Direct correlation, no lag
      significance,
      description: this.generateCorrelationDescription(metric1, metric2, correlation),
      businessContext: this.generateBusinessContext(metric1, metric2, correlation),
      technicalImplication: this.generateTechnicalImplications(metric1, metric2, correlation)
    };
  }

  /**
   * Analyze correlations between metrics and log events
   */
  private async analyzeMetricLogCorrelations(
    metrics: MetricSeries[], 
    logs: LogEntry[]
  ): Promise<CorrelationInsight[]> {
    const insights: CorrelationInsight[] = [];

    for (const metric of metrics) {
      const logCorrelations = await this.findLogEventCorrelations(metric, logs);
      
      for (const correlation of logCorrelations) {
        if (correlation.actionable) {
          const severity = this.inferSeverity(correlation.correlation.strength, correlation.correlation.strength);
          insights.push({
            id: `log-metric-${metric.name}-${Date.now()}`,
            type: 'log_correlation',
            severity,
            title: `${correlation.logPattern} → ${metric.name}`,
            description: `Log pattern correlates with ${metric.name} changes`,
            confidence: correlation.correlation.strength,
            businessImpact: correlation.businessImpact,
            technicalDetails: correlation.recommendations,
            affectedResources: [metric.name, correlation.logPattern],
            recommendedActions: [
              ...correlation.recommendations,
              `Add alert linking "${correlation.logPattern}" events to ${metric.name} anomalies`
            ],
            logCorrelation: correlation,
            detectedAt: new Date()
          });
        }
      }
    }

    return insights;
  }

  /**
   * Find correlations between log events and metric changes
   */
  private async findLogEventCorrelations(
    metric: MetricSeries, 
    logs: LogEntry[]
  ): Promise<LogMetricCorrelation[]> {
    const correlations: LogMetricCorrelation[] = [];

    // Group logs by common patterns (error types, services, etc.)
    const logPatterns = this.extractLogPatterns(logs);

    for (const pattern of logPatterns) {
      const patternLogs = logs.filter(log => this.matchesPattern(log, pattern));
      
      if (patternLogs.length < 3) continue; // Need minimum occurrences

      const correlation = this.calculateLogMetricCorrelation(patternLogs, metric);
      
      if (correlation && correlation.correlation.strength > 0.3) {
        correlations.push(correlation);
      }
    }

    return correlations.sort((a, b) => b.correlation.strength - a.correlation.strength);
  }

  /**
   * Extract common patterns from log entries
   */
  private extractLogPatterns(logs: LogEntry[]): string[] {
    const patterns = new Set<string>();

    for (const log of logs) {
      // Extract error patterns
      if (log.level === 'ERROR' || log.level === 'FATAL') {
        const errorPattern = this.extractErrorPattern(log.message);
        if (errorPattern) patterns.add(errorPattern);
      }

      // Extract service patterns
      if (log.service) {
        patterns.add(`service:${log.service}`);
      }

      // Extract HTTP error patterns
      const httpError = log.message.match(/HTTP (\d{3})/);
      if (httpError) {
        patterns.add(`http_${httpError[1]}`);
      }
    }

    return Array.from(patterns);
  }

  /**
   * Extract error pattern from log message
   */
  private extractErrorPattern(message: string): string | null {
    // Common error patterns
    const patterns = [
      /Connection refused/i,
      /Timeout/i,
      /OutOfMemory/i,
      /Database.*error/i,
      /Authentication.*failed/i,
      /Rate limit exceeded/i,
      /Service unavailable/i
    ];

    for (const pattern of patterns) {
      if (pattern.test(message)) {
        return pattern.source.replace(/[\/\\]/g, '').toLowerCase();
      }
    }

    return null;
  }

  /**
   * Calculate correlation between log events and metric values
   */
  private calculateLogMetricCorrelation(
    patternLogs: LogEntry[], 
    metric: MetricSeries
  ): LogMetricCorrelation | null {
    const logTimestamps = patternLogs.map(log => log.timestamp);
    const metricAnomalies = this.detectMetricAnomalies(metric);

    if (metricAnomalies.length === 0) return null;

    // Find temporal correlations
    let maxCorrelation = 0;
    let bestTimeDelta = 0;
    let correlationType: 'precedes' | 'follows' | 'concurrent' = 'concurrent';

    for (const anomaly of metricAnomalies) {
      for (const logTime of logTimestamps) {
        const timeDelta = (anomaly.timestamp - logTime) / 1000; // seconds
        
        if (Math.abs(timeDelta) <= 300) { // Within 5 minutes
          const correlation = this.calculateTemporalCorrelation(timeDelta);
          
          if (correlation > maxCorrelation) {
            maxCorrelation = correlation;
            bestTimeDelta = timeDelta;
            correlationType = timeDelta < -30 ? 'precedes' : timeDelta > 30 ? 'follows' : 'concurrent';
          }
        }
      }
    }

    if (maxCorrelation < 0.3) return null;

    const pattern = patternLogs[0].service || 'unknown';
    
    return {
      logPattern: pattern,
      metricName: metric.name,
      correlation: {
        type: correlationType,
        strength: maxCorrelation,
        timeDelta: bestTimeDelta
      },
      businessImpact: this.assessLogMetricBusinessImpact(pattern, metric.name, correlationType),
      actionable: maxCorrelation > 0.5,
      recommendations: this.generateLogMetricRecommendations(pattern, metric.name, correlationType)
    };
  }

  /**
   * Detect cascading failure patterns
   */
  private async detectCascadingFailures(context: ObservabilityContext): Promise<CorrelationInsight[]> {
    const insights: CorrelationInsight[] = [];
    const patterns = this.analyzeCascadingPatterns(context.metrics);

    for (const pattern of patterns) {
      if (pattern.rootCause.confidence > 0.7) {
        const severity = this.inferCascadeSeverity(pattern);
        insights.push({
          id: `cascade-${pattern.id}`,
          type: 'cascading_failure',
          severity,
          title: `Cascading Failure: ${pattern.rootCause.service}`,
          description: `Failure in ${pattern.rootCause.service} caused downstream impacts`,
          confidence: pattern.rootCause.confidence,
          businessImpact: this.assessCascadingFailureImpact(pattern),
          technicalDetails: pattern.rootCause.evidence,
          affectedResources: this.extractCascadeResources(pattern),
          recommendedActions: pattern.mitigation.length > 0
            ? pattern.mitigation
            : ['Isolate failing service', 'Review dependency health', 'Apply circuit breakers'],
          cascadingPattern: pattern,
          detectedAt: new Date()
        });
      }
    }

    return insights;
  }

  /**
   * Analyze cascading failure patterns in metrics
   */
  private analyzeCascadingPatterns(metrics: MetricSeries[]): CascadingFailurePattern[] {
    const patterns: CascadingFailurePattern[] = [];
    
    // Find error rate spikes that could trigger cascades
    const errorMetrics = metrics.filter(m => this.getMetricType(m) === MetricType.ERROR_RATE);
    
    for (const errorMetric of errorMetrics) {
      const spikes = this.detectMetricSpikes(errorMetric);
      
      for (const spike of spikes) {
        const cascadePattern = this.traceCascadingImpact(spike, metrics);
        if (cascadePattern) {
          patterns.push(cascadePattern);
        }
      }
    }

    return patterns;
  }

  /**
   * Detect seasonal and cyclical patterns in metrics
   */
  private async detectSeasonalPatterns(metrics: MetricSeries[]): Promise<CorrelationInsight[]> {
    const insights: CorrelationInsight[] = [];

    for (const metric of metrics) {
      const patterns = this.analyzeSeasonality(metric);
      
      for (const pattern of patterns) {
        if (pattern.confidence > 0.6) {
          const severity = this.inferSeasonalSeverity(pattern);
          insights.push({
            id: `seasonal-${pattern.patternId}`,
            type: 'seasonal_pattern',
            severity,
            title: `${pattern.patternType} pattern in ${metric.name}`,
            description: `Regular ${pattern.patternType} cycle detected`,
            confidence: pattern.confidence,
            businessImpact: pattern.businessContext,
            technicalDetails: pattern.predictiveInsights,
            affectedResources: [metric.name],
            recommendedActions: [
              'Adjust capacity planning to match seasonal demand',
              ...pattern.predictiveInsights
            ],
            seasonalPattern: pattern,
            detectedAt: new Date()
          });
        }
      }
    }

    return insights;
  }

  // Helper methods (simplified implementations)
  
  private alignTimeSeries(metric1: MetricSeries, metric2: MetricSeries) {
    // Simplified alignment - in production, use interpolation
    const aligned = [];
    const tolerance = 60000; // 1 minute tolerance

    for (const point1 of metric1.dataPoints) {
      const point2 = metric2.dataPoints.find(p => 
        Math.abs(p.timestamp - point1.timestamp) <= tolerance
      );
      
      if (point2) {
        aligned.push({
          timestamp: point1.timestamp,
          value1: point1.value,
          value2: point2.value
        });
      }
    }

    return aligned;
  }

  private createNullCorrelation(name1: string, name2: string): CorrelationResult {
    return {
      sourceSignal: name1,
      targetSignal: name2,
      correlationType: 'positive',
      strength: 0,
      confidence: 0,
      timeLag: 0,
      significance: 'weak',
      description: 'Insufficient data for correlation analysis',
      businessContext: 'No correlation found',
      technicalImplication: []
    };
  }

  private classifyCorrelationStrength(strength: number): 'weak' | 'moderate' | 'strong' | 'very_strong' {
    if (strength >= 0.8) return 'very_strong';
    if (strength >= 0.6) return 'strong';
    if (strength >= 0.3) return 'moderate';
    return 'weak';
  }

  private calculateConfidence(correlation: number, dataPoints: number): number {
    // Statistical confidence based on correlation strength and sample size
    const strength = Math.abs(correlation);
    const sampleFactor = Math.min(1, dataPoints / 30);
    return Math.min(0.99, strength * sampleFactor);
  }

  private generateCorrelationDescription(
    metric1: MetricSeries, 
    metric2: MetricSeries, 
    correlation: number
  ): string {
    const direction = correlation > 0 ? 'increases' : 'decreases';
    const strength = this.classifyCorrelationStrength(Math.abs(correlation));
    
    return `${strength} ${correlation > 0 ? 'positive' : 'negative'} correlation: ` +
           `When ${metric1.name} increases, ${metric2.name} typically ${direction}`;
  }

  private generateBusinessContext(
    metric1: MetricSeries, 
    metric2: MetricSeries, 
    correlation: number
  ): string {
    // Generate business context based on metric types
    if (this.getMetricType(metric1) === MetricType.THROUGHPUT && this.getMetricType(metric2) === MetricType.RESPONSE_TIME) {
      return correlation < 0 ? 
        'Higher load leads to better resource utilization and lower latency' :
        'Higher load creates resource contention and increased latency';
    }
    
    return 'Correlation may indicate shared dependencies or causal relationship';
  }

  private generateTechnicalImplications(
    metric1: MetricSeries, 
    metric2: MetricSeries, 
    correlation: number
  ): string[] {
    const implications: string[] = [];
    
    if (Math.abs(correlation) > 0.7) {
      implications.push('Strong correlation suggests shared infrastructure or dependencies');
      implications.push('Consider monitoring both metrics together for anomaly detection');
    }
    
    if (correlation < -0.5) {
      implications.push('Negative correlation may indicate resource competition');
      implications.push('Optimization of one metric might improve the other');
    }

    return implications;
  }

  private getMetricType(metric: MetricSeries): MetricType {
    return metric.metricType ?? MetricType.BUSINESS_METRIC;
  }

  private inferSeverity(confidence: number, strength: number): 'low' | 'medium' | 'high' | 'critical' {
    const score = Math.max(confidence, strength);
    if (score >= 0.85) return 'critical';
    if (score >= 0.7) return 'high';
    if (score >= 0.5) return 'medium';
    return 'low';
  }

  private inferCascadeSeverity(pattern: CascadingFailurePattern): 'low' | 'medium' | 'high' | 'critical' {
    if (pattern.propagationChain.some(p => p.impact === 'critical')) {
      return 'critical';
    }
    if (pattern.propagationChain.some(p => p.impact === 'major')) {
      return 'high';
    }
    if (pattern.propagationChain.some(p => p.impact === 'moderate')) {
      return 'medium';
    }
    return 'low';
  }

  private inferSeasonalSeverity(pattern: SeasonalPattern): 'low' | 'medium' | 'high' | 'critical' {
    if (pattern.amplitude >= pattern.baselineValue * 0.75) {
      return 'high';
    }
    if (pattern.amplitude >= pattern.baselineValue * 0.4) {
      return 'medium';
    }
    return 'low';
  }

  private extractCascadeResources(pattern: CascadingFailurePattern): string[] {
    const resources = new Set<string>([pattern.rootCause.service]);
    for (const hop of pattern.propagationChain) {
      resources.add(hop.service);
    }
    return Array.from(resources);
  }

  private recommendCorrelationActions(
    metric1: MetricSeries,
    metric2: MetricSeries,
    correlation: CorrelationResult
  ): string[] {
    const actions = [
      `Review shared dependencies between ${metric1.name} and ${metric2.name}`,
      `Add correlated alerts for ${metric1.name} and ${metric2.name}`
    ];

    if (Math.abs(correlation.strength) > 0.7) {
      actions.push('Investigate potential causal relationship before the next release');
    }

    if (correlation.strength < 0) {
      actions.push('Check for resource contention or throttling between services');
    }

    return actions;
  }

  private detectMetricAnomalies(metric: MetricSeries) {
    // Simplified anomaly detection
    const values = metric.dataPoints.map(p => p.value);
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const stdDev = Math.sqrt(values.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / values.length);
    
    return metric.dataPoints.filter(point => 
      Math.abs(point.value - mean) > 2 * stdDev
    );
  }

  private calculateTemporalCorrelation(timeDelta: number): number {
    // Simple temporal correlation based on proximity
    return Math.max(0, 1 - Math.abs(timeDelta) / 300);
  }

  private assessBusinessImpact(correlation: CorrelationResult): string {
    if (correlation.strength > 0.8) {
      return 'High - Strong correlation indicates critical dependency';
    } else if (correlation.strength > 0.5) {
      return 'Medium - Moderate correlation suggests operational relationship';
    }
    return 'Low - Weak correlation, monitor for changes';
  }

  private assessLogMetricBusinessImpact(pattern: string, metricName: string, type: string): string {
    return `${type} relationship between ${pattern} events and ${metricName} changes`;
  }

  private generateLogMetricRecommendations(pattern: string, metricName: string, type: string): string[] {
    return [
      `Monitor ${pattern} events as early indicator for ${metricName} issues`,
      `Consider alerting on ${pattern} patterns to prevent ${metricName} degradation`
    ];
  }

  private detectMetricSpikes(metric: MetricSeries) {
    // Simplified spike detection
    return this.detectMetricAnomalies(metric);
  }

  private traceCascadingImpact(spike: any, metrics: MetricSeries[]): CascadingFailurePattern | null {
    // Simplified cascading analysis - would be more complex in production
    return null;
  }

  private assessCascadingFailureImpact(pattern: CascadingFailurePattern): string {
    return `Cascading failure from ${pattern.rootCause.service} affected ${pattern.propagationChain.length} downstream services`;
  }

  private analyzeSeasonality(metric: MetricSeries): SeasonalPattern[] {
    // Simplified seasonality detection - would use FFT or similar in production
    return [];
  }

  private analyzeTraceCorrelations(metrics: MetricSeries[], traces: TraceSpan[]): Promise<CorrelationInsight[]> {
    // Trace correlation analysis - placeholder for complex implementation
    return Promise.resolve([]);
  }

  private matchesPattern(log: LogEntry, pattern: string): boolean {
    return log.message.toLowerCase().includes(pattern.toLowerCase()) ||
           log.service === pattern ||
           log.level.toLowerCase() === pattern.toLowerCase();
  }

  private rankInsightsByImportance(insights: CorrelationInsight[]): CorrelationInsight[] {
    return insights.sort((a, b) => {
      // Prioritize by confidence and business impact
      const aScore = a.confidence * (a.businessImpact.includes('High') ? 2 : 1);
      const bScore = b.confidence * (b.businessImpact.includes('High') ? 2 : 1);
      return bScore - aScore;
    });
  }
}

// Default configuration for production correlation analysis
export const DEFAULT_CORRELATION_CONFIG: CorrelationConfig = {
  minCorrelationStrength: 0.3,
  analysisWindow: 120, // 2 hours
  maxTimeLag: 30, // 30 minutes
  minDataPoints: 10,
  enabledAnalysis: {
    metricToMetric: true,
    metricToLog: true,
    metricToTrace: false, // Disabled by default due to complexity
    logToTrace: false,
    seasonalPatterns: true,
    cascadingFailures: true
  }
};
