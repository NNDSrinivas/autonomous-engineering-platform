/**
 * SLA Analyzer for NAVI Observability & Metrics Analyzer
 * 
 * This module provides comprehensive SLA monitoring, tracking, and violation
 * detection with deterministic analysis and enterprise-grade reporting
 * capabilities for production service level management.
 */

import { MetricSeries, MetricDataPoint, ObservabilityContext, SLAAlert, MetricType } from '../../types';

export interface SLATarget {
  id: string;
  name: string;
  description: string;
  metricType: MetricType;
  metricName: string;
  threshold: number;
  operator: 'less_than' | 'greater_than' | 'equal' | 'not_equal';
  timeWindow: number; // minutes
  availability: number; // percentage (e.g., 99.9)
  businessImpact: 'low' | 'medium' | 'high' | 'critical';
  tags: string[];
}

export interface SLABudget {
  target: SLATarget;
  totalBudget: number; // total allowed error budget in minutes
  consumedBudget: number; // consumed error budget in minutes
  remainingBudget: number; // remaining error budget in minutes
  burnRate: number; // current burn rate (minutes per hour)
  estimatedDepletion: Date | null; // when budget will be exhausted
  healthStatus: 'healthy' | 'warning' | 'critical' | 'exhausted';
}

export interface SLAViolation {
  id: string;
  target: SLATarget;
  startTime: Date;
  endTime: Date | null; // null if ongoing
  duration: number; // minutes
  severity: 'minor' | 'major' | 'critical';
  impact: {
    affectedUsers: number | 'unknown';
    businessImpact: string;
    technicalDetails: string[];
  };
  budgetConsumption: number; // minutes consumed
  isOngoing: boolean;
}

export interface SLAReport {
  reportId: string;
  timeRange: {
    start: Date;
    end: Date;
  };
  targets: SLATarget[];
  budgets: SLABudget[];
  violations: SLAViolation[];
  summary: {
    totalTargets: number;
    targetsInViolation: number;
    totalBudgetConsumed: number;
    worstPerformingService: string;
    overallHealth: 'healthy' | 'warning' | 'critical';
  };
  trends: {
    budgetBurnTrend: 'improving' | 'stable' | 'degrading';
    violationFrequency: 'decreasing' | 'stable' | 'increasing';
    recommendation: string[];
  };
}

export class SLAAnalyzer {
  private activeViolations: Map<string, SLAViolation> = new Map();

  constructor(private targets: SLATarget[]) {}

  /**
   * Perform comprehensive SLA analysis across all targets
   */
  async analyzeSLA(context: ObservabilityContext): Promise<SLAAlert[]> {
    const alerts: SLAAlert[] = [];

    // Analyze each SLA target
    for (const target of this.targets) {
      try {
        const metric = context.metrics.find(m => 
          m.name === target.metricName && this.resolveMetricType(m) === target.metricType
        );

        if (!metric) {
          console.warn(`Metric not found for SLA target: ${target.name}`);
          continue;
        }

        const analysis = await this.analyzeTarget(target, metric);
        if (analysis) {
          alerts.push(analysis);
        }
      } catch (error) {
        console.error(`Failed to analyze SLA target ${target.name}:`, error);
      }
    }

    return alerts.sort((a, b) => {
      const severityOrder = { critical: 3, major: 2, minor: 1 };
      const aSeverity = severityOrder[a.violation?.severity || 'minor'];
      const bSeverity = severityOrder[b.violation?.severity || 'minor'];
      return bSeverity - aSeverity;
    });
  }

  /**
   * Generate comprehensive SLA report
   */
  async generateSLAReport(
    context: ObservabilityContext,
    timeRange: { start: Date; end: Date }
  ): Promise<SLAReport> {
    const budgets: SLABudget[] = [];
    const violations: SLAViolation[] = [];
    
    for (const target of this.targets) {
      const metric = context.metrics.find(m => 
        m.name === target.metricName && this.resolveMetricType(m) === target.metricType
      );

      if (!metric) continue;

      const budget = this.calculateSLABudget(target, metric, timeRange);
      budgets.push(budget);

      const targetViolations = this.detectViolations(target, metric, timeRange);
      violations.push(...targetViolations);
    }

    const summary = this.calculateSummary(budgets, violations);
    const trends = this.analyzeTrends(budgets, violations);

    return {
      reportId: `sla-report-${Date.now()}`,
      timeRange,
      targets: this.targets,
      budgets,
      violations,
      summary,
      trends
    };
  }

  /**
   * Analyze individual SLA target for violations
   */
  private async analyzeTarget(target: SLATarget, metric: MetricSeries): Promise<SLAAlert | null> {
    const now = new Date();
    const windowStart = new Date(now.getTime() - target.timeWindow * 60000);
    
    const windowStartMs = windowStart.getTime();
    const nowMs = now.getTime();
    const windowData = metric.dataPoints.filter(point =>
      point.timestamp >= windowStartMs && point.timestamp <= nowMs
    );

    if (windowData.length === 0) {
      return null;
    }

    // Check for current violation
    const violation = this.checkViolation(target, windowData);
    if (!violation) {
      // Clear any existing violation for this target
      this.activeViolations.delete(target.id);
      return null;
    }

    // Calculate error budget impact
    const budget = this.calculateErrorBudget(target, metric);
    const confidence = this.calculateViolationConfidence(violation.duration, target.timeWindow);
    
    return {
      id: `sla-${target.id}-${Date.now()}`,
      type: 'sla_violation',
      severity: violation.severity,
      title: `SLA violation: ${target.name}`,
      description: `${target.description} is violating SLA threshold`,
      affectedResources: [metric.name],
      detectedAt: violation.startTime,
      confidence,
      businessImpact: violation.impact.businessImpact,
      technicalDetails: violation.impact.technicalDetails,
      budget,
      violation,
      recommendedActions: this.generateSLARecommendations(target, violation, budget)
    };
  }

  /**
   * Check if metric data violates SLA target
   */
  private checkViolation(target: SLATarget, dataPoints: MetricDataPoint[]): SLAViolation | null {
    const violatingPoints = dataPoints.filter(point => {
      switch (target.operator) {
        case 'less_than':
          return point.value >= target.threshold;
        case 'greater_than':
          return point.value <= target.threshold;
        case 'equal':
          return Math.abs(point.value - target.threshold) > 0.001;
        case 'not_equal':
          return Math.abs(point.value - target.threshold) <= 0.001;
        default:
          return false;
      }
    });

    if (violatingPoints.length === 0) {
      return null;
    }

    // Calculate violation duration and severity
    const startTime = new Date(violatingPoints[0].timestamp);
    const endTime = new Date(violatingPoints[violatingPoints.length - 1].timestamp);
    const duration = (endTime.getTime() - startTime.getTime()) / 60000; // minutes

    const severity = this.calculateViolationSeverity(target, violatingPoints, duration);
    
    return {
      id: `violation-${target.id}-${startTime.getTime()}`,
      target,
      startTime,
      endTime: new Date(),
      duration,
      severity,
      impact: this.calculateImpact(target, violatingPoints, duration),
      budgetConsumption: this.calculateBudgetConsumption(target, duration),
      isOngoing: true
    };
  }

  /**
   * Calculate SLA error budget status
   */
  private calculateErrorBudget(target: SLATarget, metric: MetricSeries): SLABudget {
    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    return this.calculateSLABudget(target, metric, { start: monthStart, end: now });
  }

  private calculateSLABudget(
    target: SLATarget,
    metric: MetricSeries,
    timeRange: { start: Date; end: Date }
  ): SLABudget {
    const rangeStartMs = timeRange.start.getTime();
    const rangeEndMs = timeRange.end.getTime();
    const rangeData = metric.dataPoints.filter(point =>
      point.timestamp >= rangeStartMs && point.timestamp <= rangeEndMs
    );

    const totalMinutes = (rangeEndMs - rangeStartMs) / 60000;
    const allowedDowntimePercentage = (100 - target.availability) / 100;
    const totalBudget = totalMinutes * allowedDowntimePercentage;

    const consumedBudget = this.calculateConsumedBudget(target, rangeData);
    const remainingBudget = totalBudget - consumedBudget;

    const dayWindowStart = Math.max(rangeStartMs, rangeEndMs - 24 * 60 * 60000);
    const recentData = rangeData.filter(point => point.timestamp >= dayWindowStart);
    const recentConsumption = this.calculateConsumedBudget(target, recentData);
    const burnRate = recentConsumption;

    const estimatedDepletion = remainingBudget > 0 && burnRate > 0
      ? new Date(rangeEndMs + (remainingBudget / burnRate) * 24 * 60 * 60000)
      : null;

    const budgetUtilization = totalBudget > 0 ? consumedBudget / totalBudget : 0;
    let healthStatus: 'healthy' | 'warning' | 'critical' | 'exhausted';

    if (budgetUtilization >= 1.0) {
      healthStatus = 'exhausted';
    } else if (budgetUtilization >= 0.8) {
      healthStatus = 'critical';
    } else if (budgetUtilization >= 0.5) {
      healthStatus = 'warning';
    } else {
      healthStatus = 'healthy';
    }

    return {
      target,
      totalBudget,
      consumedBudget,
      remainingBudget,
      burnRate,
      estimatedDepletion,
      healthStatus
    };
  }

  private calculateViolationConfidence(duration: number, windowMinutes: number): number {
    if (windowMinutes <= 0) {
      return 0.7;
    }
    return Math.min(0.95, Math.max(0.5, duration / windowMinutes));
  }

  private resolveMetricType(metric: MetricSeries): MetricType {
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

  /**
   * Calculate consumed error budget from metric data
   */
  private calculateConsumedBudget(target: SLATarget, dataPoints: MetricDataPoint[]): number {
    let consumedMinutes = 0;

    for (let i = 0; i < dataPoints.length - 1; i++) {
      const current = dataPoints[i];
      const next = dataPoints[i + 1];
      
      const isViolation = this.isViolatingThreshold(target, current.value);
      if (isViolation) {
        const intervalMinutes = (next.timestamp - current.timestamp) / 60000;
        consumedMinutes += intervalMinutes;
      }
    }

    return consumedMinutes;
  }

  /**
   * Check if a value violates the SLA threshold
   */
  private isViolatingThreshold(target: SLATarget, value: number): boolean {
    switch (target.operator) {
      case 'less_than':
        return value >= target.threshold;
      case 'greater_than':
        return value <= target.threshold;
      case 'equal':
        return Math.abs(value - target.threshold) > 0.001;
      case 'not_equal':
        return Math.abs(value - target.threshold) <= 0.001;
      default:
        return false;
    }
  }

  /**
   * Calculate violation severity based on impact and duration
   */
  private calculateViolationSeverity(
    target: SLATarget, 
    violatingPoints: MetricDataPoint[], 
    duration: number
  ): 'minor' | 'major' | 'critical' {
    const businessImpactWeight = {
      low: 1,
      medium: 2,
      high: 3,
      critical: 4
    };

    const impactScore = businessImpactWeight[target.businessImpact];
    
    // Calculate deviation severity
    const maxDeviation = Math.max(...violatingPoints.map(point => {
      switch (target.operator) {
        case 'less_than':
          return Math.max(0, point.value - target.threshold) / target.threshold;
        case 'greater_than':
          return Math.max(0, target.threshold - point.value) / target.threshold;
        default:
          return 0;
      }
    }));

    // Combine duration, impact, and deviation
    if (duration > 30 || impactScore >= 4 || maxDeviation > 0.5) {
      return 'critical';
    } else if (duration > 15 || impactScore >= 3 || maxDeviation > 0.2) {
      return 'major';
    } else {
      return 'minor';
    }
  }

  /**
   * Calculate business and technical impact of violation
   */
  private calculateImpact(
    target: SLATarget, 
    violatingPoints: MetricDataPoint[], 
    duration: number
  ) {
    let affectedUsers: number | 'unknown' = 'unknown';
    let businessImpact = '';
    let technicalDetails: string[] = [];

    // Estimate affected users based on metric type and violation severity
    switch (target.metricType) {
      case MetricType.AVAILABILITY:
        const availabilityDrop = violatingPoints.reduce((sum, point) => 
          sum + Math.max(0, target.threshold - point.value), 0) / violatingPoints.length;
        affectedUsers = Math.round(availabilityDrop * 1000000); // Assume 1M total users
        businessImpact = `Service unavailable for ${duration.toFixed(1)} minutes`;
        technicalDetails = ['Service downtime', 'Health check failures', 'Load balancer issues'];
        break;

      case MetricType.RESPONSE_TIME:
        const avgLatency = violatingPoints.reduce((sum, point) => sum + point.value, 0) / violatingPoints.length;
        businessImpact = `Slow response times (${avgLatency.toFixed(0)}ms avg) for ${duration.toFixed(1)} minutes`;
        technicalDetails = ['High latency', 'Timeout risks', 'User experience degradation'];
        break;

      case MetricType.ERROR_RATE:
        const avgErrorRate = violatingPoints.reduce((sum, point) => sum + point.value, 0) / violatingPoints.length;
        businessImpact = `Elevated error rate (${(avgErrorRate * 100).toFixed(1)}%) for ${duration.toFixed(1)} minutes`;
        technicalDetails = ['Increased failures', 'Data processing issues', 'Integration failures'];
        break;

      default:
        businessImpact = `SLA violation in ${target.name} for ${duration.toFixed(1)} minutes`;
        technicalDetails = ['Service degradation', 'Performance issues'];
    }

    return {
      affectedUsers,
      businessImpact,
      technicalDetails
    };
  }

  /**
   * Calculate budget consumption for a violation
   */
  private calculateBudgetConsumption(target: SLATarget, duration: number): number {
    // For availability SLAs, full duration counts as downtime
    if (target.metricType === MetricType.AVAILABILITY) {
      return duration;
    }
    
    // For performance SLAs, apply a weighted consumption based on severity
    return duration * 0.5; // 50% weight for performance violations
  }

  /**
   * Generate SLA-specific recommendations
   */
  private generateSLARecommendations(
    target: SLATarget, 
    violation: SLAViolation, 
    budget: SLABudget
  ): string[] {
    const recommendations: string[] = [];

    // Budget-based recommendations
    if (budget.healthStatus === 'exhausted') {
      recommendations.push('ERROR BUDGET EXHAUSTED - Immediate action required');
      recommendations.push('Consider freezing non-critical deployments');
    } else if (budget.healthStatus === 'critical') {
      recommendations.push('Error budget critically low - Exercise extreme caution');
      recommendations.push('Focus on stability over new features');
    }

    // Violation-specific recommendations
    switch (target.metricType) {
      case MetricType.AVAILABILITY:
        recommendations.push('Check service health and dependencies');
        recommendations.push('Review load balancer configuration');
        recommendations.push('Verify infrastructure capacity');
        break;

      case MetricType.RESPONSE_TIME:
        recommendations.push('Analyze slow queries and database performance');
        recommendations.push('Review caching strategies and hit rates');
        recommendations.push('Check resource utilization and auto-scaling');
        break;

      case MetricType.ERROR_RATE:
        recommendations.push('Investigate error logs and exception patterns');
        recommendations.push('Review recent deployments and configuration changes');
        recommendations.push('Check third-party service dependencies');
        break;

      case MetricType.THROUGHPUT:
        recommendations.push('Analyze traffic patterns and capacity limits');
        recommendations.push('Review rate limiting and throttling policies');
        recommendations.push('Check database connection pool settings');
        break;
    }

    // Business impact recommendations
    if (target.businessImpact === 'critical') {
      recommendations.unshift('Escalate to executive leadership');
      recommendations.push('Prepare customer communications');
    }

    return recommendations;
  }

  /**
   * Detect all violations within a time range
   */
  private detectViolations(
    target: SLATarget, 
    metric: MetricSeries, 
    timeRange: { start: Date; end: Date }
  ): SLAViolation[] {
    const violations: SLAViolation[] = [];
    const rangeStartMs = timeRange.start.getTime();
    const rangeEndMs = timeRange.end.getTime();
    const relevantData = metric.dataPoints.filter(point =>
      point.timestamp >= rangeStartMs && point.timestamp <= rangeEndMs
    );

    let currentViolation: SLAViolation | null = null;

    for (const point of relevantData) {
      const isViolation = this.isViolatingThreshold(target, point.value);

      if (isViolation && !currentViolation) {
        // Start new violation
        currentViolation = {
          id: `violation-${target.id}-${point.timestamp}`,
          target,
          startTime: new Date(point.timestamp),
          endTime: null,
          duration: 0,
          severity: 'minor',
          impact: { affectedUsers: 'unknown', businessImpact: '', technicalDetails: [] },
          budgetConsumption: 0,
          isOngoing: true
        };
      } else if (!isViolation && currentViolation) {
        // End current violation
        currentViolation.endTime = new Date(point.timestamp);
        currentViolation.duration = (point.timestamp - currentViolation.startTime.getTime()) / 60000;
        currentViolation.isOngoing = false;
        currentViolation.severity = this.calculateViolationSeverity(target, [], currentViolation.duration);
        currentViolation.budgetConsumption = this.calculateBudgetConsumption(target, currentViolation.duration);
        
        violations.push(currentViolation);
        currentViolation = null;
      }
    }

    // Handle ongoing violation at end of time range
    if (currentViolation) {
      currentViolation.endTime = timeRange.end;
      currentViolation.duration = (timeRange.end.getTime() - currentViolation.startTime.getTime()) / 60000;
      currentViolation.severity = this.calculateViolationSeverity(target, [], currentViolation.duration);
      currentViolation.budgetConsumption = this.calculateBudgetConsumption(target, currentViolation.duration);
      violations.push(currentViolation);
    }

    return violations;
  }

  /**
   * Calculate summary statistics for SLA report
   */
  private calculateSummary(budgets: SLABudget[], violations: SLAViolation[]) {
    const totalTargets = budgets.length;
    const targetsInViolation = budgets.filter(b => 
      b.healthStatus === 'critical' || b.healthStatus === 'exhausted'
    ).length;
    
    const totalBudgetConsumed = budgets.reduce((sum, b) => sum + b.consumedBudget, 0);
    
    const worstBudget = budgets.length > 0
      ? budgets.reduce((worst, current) => {
          const worstUtilization = worst.totalBudget > 0 ? worst.consumedBudget / worst.totalBudget : 0;
          const currentUtilization = current.totalBudget > 0 ? current.consumedBudget / current.totalBudget : 0;
          return currentUtilization > worstUtilization ? current : worst;
        }, budgets[0])
      : undefined;
    
    const worstPerformingService = worstBudget?.target.name || 'Unknown';
    
    const overallHealth: SLAReport['summary']['overallHealth'] = targetsInViolation === 0 ? 'healthy' :
      targetsInViolation < totalTargets * 0.3 ? 'warning' : 'critical';

    return {
      totalTargets,
      targetsInViolation,
      totalBudgetConsumed,
      worstPerformingService,
      overallHealth
    };
  }

  /**
   * Analyze trends in SLA performance
   */
  private analyzeTrends(budgets: SLABudget[], violations: SLAViolation[]) {
    // Simple trend analysis - in production, this would use historical data
    const avgBurnRate = budgets.length > 0
      ? budgets.reduce((sum, b) => sum + b.burnRate, 0) / budgets.length
      : 0;
    const budgetBurnTrend: SLAReport['trends']['budgetBurnTrend'] =
      avgBurnRate > 100 ? 'degrading' : avgBurnRate > 50 ? 'stable' : 'improving';
    
    const recentViolations = violations.filter(v => 
      v.startTime > new Date(Date.now() - 7 * 24 * 60 * 60000) // Last 7 days
    );
    const violationFrequency: SLAReport['trends']['violationFrequency'] =
      recentViolations.length > 10 ? 'increasing' : 
      recentViolations.length > 3 ? 'stable' : 'decreasing';

    const recommendation: string[] = [];
    if (budgetBurnTrend === 'degrading') {
      recommendation.push('Focus on stability improvements and error budget conservation');
    }
    if (violationFrequency === 'increasing') {
      recommendation.push('Investigate root causes of increasing SLA violations');
    }
    if (budgets.some(b => b.healthStatus === 'exhausted')) {
      recommendation.push('Implement change freeze until error budgets recover');
    }

    return {
      budgetBurnTrend,
      violationFrequency,
      recommendation
    };
  }
}

// Common SLA targets for web services
export const COMMON_SLA_TARGETS: SLATarget[] = [
  {
    id: 'availability-99-9',
    name: 'Service Availability',
    description: '99.9% service availability',
    metricType: MetricType.AVAILABILITY,
    metricName: 'service_availability',
    threshold: 0.999,
    operator: 'greater_than',
    timeWindow: 5,
    availability: 99.9,
    businessImpact: 'critical',
    tags: ['availability', 'uptime']
  },
  {
    id: 'response-time-p95',
    name: 'Response Time P95',
    description: 'P95 response time under 500ms',
    metricType: MetricType.RESPONSE_TIME,
    metricName: 'http_request_duration_p95',
    threshold: 500,
    operator: 'less_than',
    timeWindow: 15,
    availability: 95.0,
    businessImpact: 'high',
    tags: ['performance', 'latency']
  },
  {
    id: 'error-rate-p99',
    name: 'Error Rate',
    description: 'Error rate below 1%',
    metricType: MetricType.ERROR_RATE,
    metricName: 'http_error_rate',
    threshold: 0.01,
    operator: 'less_than',
    timeWindow: 10,
    availability: 99.0,
    businessImpact: 'high',
    tags: ['reliability', 'errors']
  }
];
