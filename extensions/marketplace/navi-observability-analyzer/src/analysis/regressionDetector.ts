/**
 * Regression Detector for NAVI Observability & Metrics Analyzer
 * 
 * This module provides deterministic regression detection using statistical
 * methods and domain-specific knowledge to identify performance degradations
 * and failures in production systems without ML hallucinations.
 */

import { MetricSeries, ObservabilityContext, RegressionAlert, MetricType } from '../../types';

export interface RegressionDetectionConfig {
  // Time window for regression comparison (in minutes)
  comparisonWindow: number;
  
  // Minimum data points required for analysis
  minDataPoints: number;
  
  // Regression thresholds by metric type
  thresholds: {
    [MetricType.RESPONSE_TIME]: {
      percentileIncrease: number;  // e.g., 50% increase in p95
      meanIncrease: number;        // e.g., 30% increase in mean
    };
    [MetricType.THROUGHPUT]: {
      percentileDecrease: number;  // e.g., 30% decrease in p95
      meanDecrease: number;        // e.g., 20% decrease in mean
    };
    [MetricType.ERROR_RATE]: {
      absoluteIncrease: number;    // e.g., 5% absolute increase
      relativeIncrease: number;    // e.g., 200% relative increase
    };
    [MetricType.AVAILABILITY]: {
      absoluteDecrease: number;    // e.g., 2% absolute decrease
    };
    [MetricType.RESOURCE_UTILIZATION]: {
      absoluteIncrease: number;    // e.g., 20% absolute increase
    };
    [MetricType.BUSINESS_METRIC]: {
      percentileDecrease: number;  // e.g., 15% decrease in conversions
      trendReversal: boolean;      // Detect positive->negative trends
    };
  };
  
  // Minimum duration for regression to be considered significant
  minRegressionDuration: number; // minutes
}

export interface TimeWindowStats {
  mean: number;
  median: number;
  p95: number;
  p99: number;
  stdDev: number;
  count: number;
  timeRange: {
    start: Date;
    end: Date;
  };
}

export interface RegressionEvidence {
  metricName: string;
  metricType: MetricType;
  currentStats: TimeWindowStats;
  baselineStats: TimeWindowStats;
  regressionType: 'performance' | 'reliability' | 'business';
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
  detectedAt: Date;
  description: string;
  impactAssessment: {
    userImpact: 'none' | 'minimal' | 'moderate' | 'significant' | 'severe';
    businessImpact: 'none' | 'low' | 'medium' | 'high' | 'critical';
    technicalImpact: string[];
  };
}

export class RegressionDetector {
  constructor(private config: RegressionDetectionConfig) {}

  /**
   * Detect regressions across all metrics in the observability context
   */
  async detectRegressions(context: ObservabilityContext): Promise<RegressionAlert[]> {
    const regressions: RegressionAlert[] = [];

    for (const metric of context.metrics) {
      try {
        const regression = await this.analyzeMetricRegression(metric);
        if (regression) {
          regressions.push(regression);
        }
      } catch (error) {
        console.warn(`Failed to analyze regression for ${metric.name}:`, error);
      }
    }

    // Sort by severity and confidence
    return regressions.sort((a, b) => {
      const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
      const aSeverity = severityOrder[a.evidence.severity];
      const bSeverity = severityOrder[b.evidence.severity];
      
      if (aSeverity !== bSeverity) {
        return bSeverity - aSeverity; // Higher severity first
      }
      
      return b.evidence.confidence - a.evidence.confidence; // Higher confidence first
    });
  }

  /**
   * Analyze a single metric for regression patterns
   */
  private async analyzeMetricRegression(metric: MetricSeries): Promise<RegressionAlert | null> {
    if (metric.dataPoints.length < this.config.minDataPoints) {
      return null;
    }

    const metricType = this.resolveMetricType(metric);
    if (!metricType) {
      return null;
    }

    // Get current and baseline time windows
    const now = new Date();
    const currentWindow = this.getTimeWindow(
      metric, 
      new Date(now.getTime() - this.config.comparisonWindow * 60000), 
      now
    );
    
    const baselineWindow = this.getTimeWindow(
      metric,
      new Date(now.getTime() - (this.config.comparisonWindow * 2) * 60000),
      new Date(now.getTime() - this.config.comparisonWindow * 60000)
    );

    if (!currentWindow || !baselineWindow) {
      return null;
    }

    // Calculate stats for both windows
    const currentStats = this.calculateStats(currentWindow, metric);
    const baselineStats = this.calculateStats(baselineWindow, metric);

    // Detect regression based on metric type
    const evidence = this.detectRegressionByType(
      metricType,
      currentStats,
      baselineStats,
      metric.name
    );

    if (!evidence) {
      return null;
    }

    const affectedResource = metric.source ?? metric.metadata.source;

    return {
      id: `regression-${metric.name}-${Date.now()}`,
      type: 'regression',
      severity: evidence.severity,
      title: `Regression detected in ${metric.name}`,
      description: evidence.description,
      affectedResources: [String(affectedResource)],
      detectedAt: evidence.detectedAt,
      confidence: evidence.confidence,
      businessImpact: evidence.impactAssessment.businessImpact,
      technicalDetails: evidence.impactAssessment.technicalImpact,
      evidence,
      recommendedActions: this.generateRecommendedActions(evidence)
    };
  }

  /**
   * Detect regression patterns based on metric type
   */
  private detectRegressionByType(
    metricType: MetricType,
    current: TimeWindowStats,
    baseline: TimeWindowStats,
    metricName: string
  ): RegressionEvidence | null {
    let regressionDetected = false;
    let regressionType: 'performance' | 'reliability' | 'business' = 'performance';
    let severity: 'low' | 'medium' | 'high' | 'critical' = 'low';
    let confidence = 0;
    let description = '';
    let userImpact: 'none' | 'minimal' | 'moderate' | 'significant' | 'severe' = 'none';
    let businessImpact: 'none' | 'low' | 'medium' | 'high' | 'critical' = 'none';
    let technicalImpact: string[] = [];

    switch (metricType) {
      case MetricType.RESPONSE_TIME:
        const responseThreshold = this.config.thresholds[MetricType.RESPONSE_TIME];
        const p95Increase = (current.p95 - baseline.p95) / baseline.p95;
        const meanIncrease = (current.mean - baseline.mean) / baseline.mean;
        
        if (p95Increase > responseThreshold.percentileIncrease || meanIncrease > responseThreshold.meanIncrease) {
          regressionDetected = true;
          regressionType = 'performance';
          
          if (p95Increase > 1.0 || meanIncrease > 0.8) {
            severity = 'critical';
            userImpact = 'severe';
            businessImpact = 'critical';
          } else if (p95Increase > 0.7 || meanIncrease > 0.5) {
            severity = 'high';
            userImpact = 'significant';
            businessImpact = 'high';
          } else {
            severity = 'medium';
            userImpact = 'moderate';
            businessImpact = 'medium';
          }
          
          confidence = Math.min(0.95, Math.max(p95Increase, meanIncrease) * 1.2);
          description = `Response time regression: P95 increased by ${(p95Increase * 100).toFixed(1)}%, mean increased by ${(meanIncrease * 100).toFixed(1)}%`;
          technicalImpact = ['Increased latency', 'Potential timeout issues', 'Resource contention'];
        }
        break;

      case MetricType.THROUGHPUT:
        const throughputThreshold = this.config.thresholds[MetricType.THROUGHPUT];
        const p95Decrease = (baseline.p95 - current.p95) / baseline.p95;
        const meanDecrease = (baseline.mean - current.mean) / baseline.mean;
        
        if (p95Decrease > throughputThreshold.percentileDecrease || meanDecrease > throughputThreshold.meanDecrease) {
          regressionDetected = true;
          regressionType = 'performance';
          
          if (p95Decrease > 0.5 || meanDecrease > 0.4) {
            severity = 'critical';
            userImpact = 'severe';
            businessImpact = 'critical';
          } else if (p95Decrease > 0.3 || meanDecrease > 0.25) {
            severity = 'high';
            userImpact = 'significant';
            businessImpact = 'high';
          } else {
            severity = 'medium';
            userImpact = 'moderate';
            businessImpact = 'medium';
          }
          
          confidence = Math.min(0.95, Math.max(p95Decrease, meanDecrease) * 1.3);
          description = `Throughput regression: P95 decreased by ${(p95Decrease * 100).toFixed(1)}%, mean decreased by ${(meanDecrease * 100).toFixed(1)}%`;
          technicalImpact = ['Reduced capacity', 'Potential bottlenecks', 'Service degradation'];
        }
        break;

      case MetricType.ERROR_RATE:
        const errorThreshold = this.config.thresholds[MetricType.ERROR_RATE];
        const absoluteIncrease = current.mean - baseline.mean;
        const relativeIncrease = baseline.mean > 0 ? absoluteIncrease / baseline.mean : 0;
        
        if (absoluteIncrease > errorThreshold.absoluteIncrease || relativeIncrease > errorThreshold.relativeIncrease) {
          regressionDetected = true;
          regressionType = 'reliability';
          
          if (absoluteIncrease > 0.1 || relativeIncrease > 5.0) {
            severity = 'critical';
            userImpact = 'severe';
            businessImpact = 'critical';
          } else if (absoluteIncrease > 0.05 || relativeIncrease > 2.0) {
            severity = 'high';
            userImpact = 'significant';
            businessImpact = 'high';
          } else {
            severity = 'medium';
            userImpact = 'moderate';
            businessImpact = 'medium';
          }
          
          confidence = Math.min(0.98, Math.max(absoluteIncrease * 10, relativeIncrease * 0.2));
          description = `Error rate regression: Increased by ${(absoluteIncrease * 100).toFixed(2)}% absolute (${(relativeIncrease * 100).toFixed(1)}% relative)`;
          technicalImpact = ['Increased failures', 'Service instability', 'Data integrity concerns'];
        }
        break;

      case MetricType.AVAILABILITY:
        const availabilityThreshold = this.config.thresholds[MetricType.AVAILABILITY];
        const availabilityDecrease = baseline.mean - current.mean;
        
        if (availabilityDecrease > availabilityThreshold.absoluteDecrease) {
          regressionDetected = true;
          regressionType = 'reliability';
          
          if (availabilityDecrease > 0.05) {
            severity = 'critical';
            userImpact = 'severe';
            businessImpact = 'critical';
          } else if (availabilityDecrease > 0.02) {
            severity = 'high';
            userImpact = 'significant';
            businessImpact = 'high';
          } else {
            severity = 'medium';
            userImpact = 'moderate';
            businessImpact = 'medium';
          }
          
          confidence = Math.min(0.99, availabilityDecrease * 25);
          description = `Availability regression: Decreased by ${(availabilityDecrease * 100).toFixed(2)}%`;
          technicalImpact = ['Service downtime', 'Reduced reliability', 'SLA violations'];
        }
        break;

      case MetricType.BUSINESS_METRIC:
        const businessThreshold = this.config.thresholds[MetricType.BUSINESS_METRIC];
        const businessDecrease = (baseline.mean - current.mean) / baseline.mean;
        
        if (businessDecrease > businessThreshold.percentileDecrease) {
          regressionDetected = true;
          regressionType = 'business';
          
          if (businessDecrease > 0.3) {
            severity = 'critical';
            userImpact = 'significant';
            businessImpact = 'critical';
          } else if (businessDecrease > 0.2) {
            severity = 'high';
            userImpact = 'moderate';
            businessImpact = 'high';
          } else {
            severity = 'medium';
            userImpact = 'minimal';
            businessImpact = 'medium';
          }
          
          confidence = Math.min(0.92, businessDecrease * 2.5);
          description = `Business metric regression: ${metricName} decreased by ${(businessDecrease * 100).toFixed(1)}%`;
          technicalImpact = ['Revenue impact', 'User engagement drop', 'Conversion reduction'];
        }
        break;
    }

    if (!regressionDetected) {
      return null;
    }

    return {
      metricName,
      metricType,
      currentStats: current,
      baselineStats: baseline,
      regressionType,
      severity,
      confidence,
      detectedAt: new Date(),
      description,
      impactAssessment: {
        userImpact,
        businessImpact,
        technicalImpact
      }
    };
  }

  /**
   * Extract data points within a time window
   */
  private getTimeWindow(metric: MetricSeries, start: Date, end: Date): number[] | null {
    const startMs = start.getTime();
    const endMs = end.getTime();
    const windowPoints = metric.dataPoints.filter(point => 
      point.timestamp >= startMs && point.timestamp <= endMs
    );

    if (windowPoints.length < 2) {
      return null;
    }

    return windowPoints.map(point => point.value);
  }

  /**
   * Calculate statistical metrics for a time window
   */
  private calculateStats(values: number[], metric: MetricSeries): TimeWindowStats {
    const sortedValues = [...values].sort((a, b) => a - b);
    const count = values.length;
    const sum = values.reduce((a, b) => a + b, 0);
    const mean = sum / count;
    
    // Calculate percentiles
    const p95Index = Math.ceil(count * 0.95) - 1;
    const p99Index = Math.ceil(count * 0.99) - 1;
    const medianIndex = Math.ceil(count * 0.5) - 1;
    
    const p95 = sortedValues[Math.min(p95Index, count - 1)];
    const p99 = sortedValues[Math.min(p99Index, count - 1)];
    const median = sortedValues[medianIndex];
    
    // Calculate standard deviation
    const variance = values.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / count;
    const stdDev = Math.sqrt(variance);

    return {
      mean,
      median,
      p95,
      p99,
      stdDev,
      count,
      timeRange: {
        start: new Date(Math.min(...metric.dataPoints.map(p => p.timestamp))),
        end: new Date(Math.max(...metric.dataPoints.map(p => p.timestamp)))
      }
    };
  }

  /**
   * Generate recommended actions based on regression evidence
   */
  private generateRecommendedActions(evidence: RegressionEvidence): string[] {
    const actions: string[] = [];

    switch (evidence.regressionType) {
      case 'performance':
        actions.push('Review recent deployments and configuration changes');
        actions.push('Check resource utilization and scaling policies');
        actions.push('Analyze database query performance and connection pools');
        actions.push('Review application profiling data');
        
        if (evidence.severity === 'critical') {
          actions.unshift('Consider immediate rollback of recent changes');
          actions.push('Escalate to on-call engineering team');
        }
        break;

      case 'reliability':
        actions.push('Investigate error logs and exception patterns');
        actions.push('Check health check endpoints and dependencies');
        actions.push('Review circuit breaker and retry configurations');
        actions.push('Validate data integrity and consistency');
        
        if (evidence.severity === 'critical') {
          actions.unshift('Activate incident response procedure');
          actions.push('Consider traffic routing to healthy instances');
        }
        break;

      case 'business':
        actions.push('Coordinate with product and business teams');
        actions.push('Review A/B test configurations and feature flags');
        actions.push('Check payment processing and third-party integrations');
        actions.push('Analyze user journey and conversion funnels');
        
        if (evidence.severity === 'critical') {
          actions.unshift('Alert business stakeholders immediately');
          actions.push('Consider reverting business logic changes');
        }
        break;
    }

    return actions;
  }

  private resolveMetricType(metric: MetricSeries): MetricType | null {
    if (metric.metricType) {
      return metric.metricType;
    }

    const name = metric.name.toLowerCase();

    if (name.includes('latency') || name.includes('response') || name.includes('duration')) {
      return MetricType.RESPONSE_TIME;
    }
    if (name.includes('throughput') || name.includes('rps') || name.includes('requests')) {
      return MetricType.THROUGHPUT;
    }
    if (name.includes('error') || name.includes('5xx') || name.includes('failure')) {
      return MetricType.ERROR_RATE;
    }
    if (name.includes('availability') || name.includes('uptime')) {
      return MetricType.AVAILABILITY;
    }
    if (name.includes('cpu') || name.includes('memory') || name.includes('disk') || name.includes('utilization')) {
      return MetricType.RESOURCE_UTILIZATION;
    }

    return MetricType.BUSINESS_METRIC;
  }
}

// Default configuration for production environments
export const DEFAULT_REGRESSION_CONFIG: RegressionDetectionConfig = {
  comparisonWindow: 60, // 1 hour
  minDataPoints: 10,
  minRegressionDuration: 5,
  thresholds: {
    [MetricType.RESPONSE_TIME]: {
      percentileIncrease: 0.5,  // 50% increase in P95
      meanIncrease: 0.3         // 30% increase in mean
    },
    [MetricType.THROUGHPUT]: {
      percentileDecrease: 0.3,  // 30% decrease in P95
      meanDecrease: 0.2         // 20% decrease in mean
    },
    [MetricType.ERROR_RATE]: {
      absoluteIncrease: 0.02,   // 2% absolute increase
      relativeIncrease: 2.0     // 200% relative increase
    },
    [MetricType.AVAILABILITY]: {
      absoluteDecrease: 0.01    // 1% absolute decrease
    },
    [MetricType.RESOURCE_UTILIZATION]: {
      absoluteIncrease: 0.15    // 15% absolute increase
    },
    [MetricType.BUSINESS_METRIC]: {
      percentileDecrease: 0.1,  // 10% decrease
      trendReversal: true
    }
  }
};
