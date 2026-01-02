/**
 * NAVI Observability & Metrics Analyzer - Type Definitions
 * 
 * Production-ready observability extension that analyzes runtime metrics,
 * logs, and traces to detect anomalies and propose safe remediation.
 * 
 * This extension positions NAVI as a Staff SRE + Production Debugger,
 * competing with dedicated observability tools like DataDog, New Relic.
 */

// Extension Context
export interface ExtensionContext {
    workspaceRoot: string;
    userId: string;
    sessionId: string;
    timestamp: string;
    permissions: string[];
}

export interface ObservabilityContext {
    metrics: MetricSeries[];
    logs: LogEntry[];
    traces: TraceSpan[];
    alerts?: ObservabilityAlert[];
    timeRange?: { start: Date; end: Date };
}

// Metric Data Types
export interface MetricDataPoint {
    timestamp: number;
    value: number;
    labels?: Record<string, string>;
}

export interface MetricSeries {
    name: string;
    unit: string;
    dataPoints: MetricDataPoint[];
    metadata: {
        source: MetricSource;
        interval: string;
        aggregation: MetricAggregation;
    };
    metricType?: MetricType;
    source?: MetricSource;
}

export enum MetricSource {
    PROMETHEUS = 'PROMETHEUS',
    DATADOG = 'DATADOG',
    CLOUDWATCH = 'CLOUDWATCH',
    GRAFANA = 'GRAFANA',
    NEW_RELIC = 'NEW_RELIC',
    CUSTOM = 'CUSTOM'
}

export enum MetricAggregation {
    AVERAGE = 'AVERAGE',
    SUM = 'SUM',
    MAX = 'MAX',
    MIN = 'MIN',
    P50 = 'P50',
    P95 = 'P95',
    P99 = 'P99'
}

export enum MetricType {
    RESPONSE_TIME = 'RESPONSE_TIME',
    THROUGHPUT = 'THROUGHPUT', 
    ERROR_RATE = 'ERROR_RATE',
    AVAILABILITY = 'AVAILABILITY',
    RESOURCE_UTILIZATION = 'RESOURCE_UTILIZATION',
    BUSINESS_METRIC = 'BUSINESS_METRIC'
}

// Log Data Types
export interface LogEntry {
    timestamp: number;
    level: LogLevel;
    message: string;
    service: string;
    source: string;
    labels?: Record<string, string>;
    structured?: Record<string, any>;
}

export enum LogLevel {
    DEBUG = 'DEBUG',
    INFO = 'INFO',
    WARN = 'WARN',
    ERROR = 'ERROR',
    FATAL = 'FATAL'
}

// Trace Data Types
export interface TraceSpan {
    traceId: string;
    spanId: string;
    operationName: string;
    startTime: number;
    duration: number;
    tags: Record<string, string>;
    status: SpanStatus;
    parentSpanId?: string;
}

export enum SpanStatus {
    OK = 'OK',
    ERROR = 'ERROR',
    TIMEOUT = 'TIMEOUT'
}

// Anomaly Detection
export interface Anomaly {
    id: string;
    type: AnomalyType;
    severity: SeverityLevel;
    metric: string;
    startTime: number;
    endTime?: number;
    current: number;
    baseline: number;
    deviation: number;
    confidence: number;
    description: string;
    evidence: Evidence[];
}

export enum AnomalyType {
    LATENCY_SPIKE = 'LATENCY_SPIKE',
    ERROR_RATE_INCREASE = 'ERROR_RATE_INCREASE',
    THROUGHPUT_DROP = 'THROUGHPUT_DROP',
    RESOURCE_SATURATION = 'RESOURCE_SATURATION',
    AVAILABILITY_DEGRADATION = 'AVAILABILITY_DEGRADATION',
    SLA_BREACH = 'SLA_BREACH'
}

export enum SeverityLevel {
    CRITICAL = 'CRITICAL',
    HIGH = 'HIGH',
    MEDIUM = 'MEDIUM',
    LOW = 'LOW',
    INFO = 'INFO'
}

export interface Evidence {
    type: EvidenceType;
    content: string;
    timestamp?: number;
    source: string;
    relevance: number;
}

export enum EvidenceType {
    METRIC_SPIKE = 'METRIC_SPIKE',
    LOG_ERROR = 'LOG_ERROR',
    TRACE_ANOMALY = 'TRACE_ANOMALY',
    CORRELATION = 'CORRELATION',
    PATTERN_MATCH = 'PATTERN_MATCH'
}

// Issue Classification
export interface ClassifiedIssue {
    id: string;
    type: IssueType;
    title: string;
    severity: SeverityLevel;
    confidence: number;
    affectedServices: string[];
    startTime: number;
    endTime?: number;
    rootCause?: RootCause;
    businessImpact: BusinessImpact;
    technicalDetails: TechnicalDetails;
    correlatedSignals: CorrelatedSignal[];
}

export enum IssueType {
    PERFORMANCE_DEGRADATION = 'PERFORMANCE_DEGRADATION',
    SERVICE_OUTAGE = 'SERVICE_OUTAGE',
    LATENCY_REGRESSION = 'LATENCY_REGRESSION',
    ERROR_RATE_SPIKE = 'ERROR_RATE_SPIKE',
    THROUGHPUT_DEGRADATION = 'THROUGHPUT_DEGRADATION',
    RESOURCE_EXHAUSTION = 'RESOURCE_EXHAUSTION',
    DEPENDENCY_FAILURE = 'DEPENDENCY_FAILURE',
    DEPLOYMENT_REGRESSION = 'DEPLOYMENT_REGRESSION',
    CONFIGURATION_ERROR = 'CONFIGURATION_ERROR'
}

export interface RootCause {
    hypothesis: string;
    confidence: number;
    evidence: Evidence[];
    timeToDetection: number;
}

export interface BusinessImpactDetails {
    userExperience: string;
    revenue?: string;
    slaStatus: string;
    customersFacing: boolean;
}

export type BusinessImpact = BusinessImpactDetails | string;

export interface TechnicalDetails {
    affectedComponents: string[];
    errorPatterns: string[];
    performanceMetrics: Record<string, number>;
    systemHealth: SystemHealth;
}

export interface SystemHealth {
    cpu: number;
    memory: number;
    disk: number;
    network: number;
    overall: HealthStatus;
}

export enum HealthStatus {
    HEALTHY = 'HEALTHY',
    DEGRADED = 'DEGRADED',
    CRITICAL = 'CRITICAL',
    UNAVAILABLE = 'UNAVAILABLE'
}

export interface CorrelatedSignal {
    source: string;
    type: 'metric' | 'log' | 'trace';
    correlation: number;
    timeOffset: number;
    description: string;
}

// Remediation Proposals
export interface RemediationProposal {
    id: string;
    title: string;
    description: string;
    type: RemediationType;
    priority: Priority;
    confidence: number;
    effort: EffortLevel;
    risk: RiskLevel;
    requiresApproval: boolean;
    estimatedImpact: string;
    steps: RemediationStep[];
    rollbackPlan: RollbackPlan;
    monitoring: MonitoringPlan;
}

export enum RemediationType {
    INVESTIGATION = 'INVESTIGATION',
    CONFIGURATION_CHANGE = 'CONFIGURATION_CHANGE',
    SCALING_ADJUSTMENT = 'SCALING_ADJUSTMENT',
    SERVICE_RESTART = 'SERVICE_RESTART',
    ROLLBACK = 'ROLLBACK',
    MITIGATION = 'MITIGATION'
}

export enum Priority {
    P0 = 'P0', // Critical production outage
    P1 = 'P1', // Major degradation
    P2 = 'P2', // Minor issues
    P3 = 'P3', // Optimization opportunities
    P4 = 'P4'  // Nice to have
}

export enum EffortLevel {
    LOW = 'LOW',       // < 30 minutes
    MEDIUM = 'MEDIUM', // 30 minutes - 2 hours
    HIGH = 'HIGH'      // > 2 hours
}

export enum RiskLevel {
    LOW = 'LOW',       // Safe, minimal impact
    MEDIUM = 'MEDIUM', // Some risk, testing recommended
    HIGH = 'HIGH'      // High risk, requires approval
}

export interface RemediationStep {
    order: number;
    action: string;
    command?: string;
    description?: string;
    validation: string;
    rollbackAction?: string;
    automatable: boolean;
}

export interface RollbackPlan {
    canRollback: boolean;
    steps: string[];
    timeEstimate: string;
    dataLoss: boolean;
}

export interface MonitoringPlan {
    metrics: string[];
    alerts: string[];
    duration: string;
    successCriteria: string[];
}

// Analysis Results
export interface ObservabilityAnalysisResult {
    sessionId: string;
    timestamp: string;
    summary: AnalysisSummary;
    issues: ClassifiedIssue[];
    recommendations: RemediationProposal[];
    systemHealth: SystemHealth;
    slaStatus: SLAStatus;
    insights: Insight[];
    requiresApproval: boolean;
    nextActions: string[];
}

export interface AnalysisSummary {
    overallHealth: HealthStatus;
    criticalIssues: number;
    majorIssues: number;
    minorIssues: number;
    timeRange: string;
    coverage: Coverage;
    confidence: number;
}

export interface Coverage {
    metrics: boolean;
    logs: boolean;
    traces: boolean;
    alerts: boolean;
}

export interface SLAStatus {
    availability: {
        current: number;
        target: number;
        status: 'MEETING' | 'AT_RISK' | 'BREACHED';
    };
    latency: {
        p95: number;
        target: number;
        status: 'MEETING' | 'AT_RISK' | 'BREACHED';
    };
    errorRate: {
        current: number;
        target: number;
        status: 'MEETING' | 'AT_RISK' | 'BREACHED';
    };
}

export interface Insight {
    type: InsightType;
    title: string;
    description: string;
    impact: string;
    actionable: boolean;
    priority: Priority;
}

export enum InsightType {
    PERFORMANCE_OPTIMIZATION = 'PERFORMANCE_OPTIMIZATION',
    COST_REDUCTION = 'COST_REDUCTION',
    RELIABILITY_IMPROVEMENT = 'RELIABILITY_IMPROVEMENT',
    CAPACITY_PLANNING = 'CAPACITY_PLANNING',
    SECURITY_CONCERN = 'SECURITY_CONCERN'
}

// Data Source Configurations
export interface DataSourceConfig {
    prometheus?: PrometheusConfig;
    datadog?: DatadogConfig;
    cloudwatch?: CloudWatchConfig;
    logs?: LogsConfig;
    traces?: TracesConfig;
}

export interface PrometheusConfig {
    endpoint: string;
    queries: PrometheusQuery[];
    basicAuth?: {
        username: string;
        password: string;
    };
}

export interface PrometheusQuery {
    name: string;
    query: string;
    interval: string;
    labels?: string[];
}

export interface DatadogConfig {
    apiKey: string;
    appKey: string;
    queries: DatadogQuery[];
}

export interface DatadogQuery {
    metric: string;
    aggregation: string;
    tags?: string[];
}

export interface CloudWatchConfig {
    region: string;
    accessKeyId: string;
    secretAccessKey: string;
    metrics: CloudWatchMetric[];
}

export interface CloudWatchMetric {
    namespace: string;
    metricName: string;
    dimensions: Record<string, string>;
}

export interface LogsConfig {
    sources: LogSource[];
}

export interface LogSource {
    name: string;
    type: 'file' | 'elasticsearch' | 'splunk' | 'cloudwatch-logs';
    config: Record<string, any>;
}

export interface TracesConfig {
    jaeger?: JaegerConfig;
    zipkin?: ZipkinConfig;
}

export interface JaegerConfig {
    endpoint: string;
    service: string;
}

export interface ZipkinConfig {
    endpoint: string;
    service: string;
}

// Base alert interface for observability events
export interface ObservabilityAlert {
    id: string;
    type: string;
    severity: 'low' | 'medium' | 'high' | 'critical' | 'minor' | 'major';
    title: string;
    description: string;
    affectedResources: string[];
    detectedAt: Date;
    confidence: number;
    businessImpact: string;
    technicalDetails: string[];
    recommendedActions: string[];
}

// Additional alert types for specific analysis results
export interface AnomalyAlert extends ObservabilityAlert {
  type: 'anomaly';
  anomaly: Anomaly;
}

export interface RegressionAlert extends ObservabilityAlert {
  type: 'regression';
  evidence: {
    metricName: string;
    metricType: MetricType;
    currentStats: {
      mean: number;
      median: number;
      p95: number;
      p99: number;
      stdDev: number;
      count: number;
      timeRange: { start: Date; end: Date; };
    };
    baselineStats: {
      mean: number;
      median: number;
      p95: number;
      p99: number;
      stdDev: number;
      count: number;
      timeRange: { start: Date; end: Date; };
    };
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
  };
}

export interface SLAAlert extends ObservabilityAlert {
  type: 'sla_violation';
  budget: {
    target: {
      id: string;
      name: string;
      description: string;
      metricType: MetricType;
      metricName: string;
      threshold: number;
      operator: 'less_than' | 'greater_than' | 'equal' | 'not_equal';
      timeWindow: number;
      availability: number;
      businessImpact: 'low' | 'medium' | 'high' | 'critical';
      tags: string[];
    };
    totalBudget: number;
    consumedBudget: number;
    remainingBudget: number;
    burnRate: number;
    estimatedDepletion: Date | null;
    healthStatus: 'healthy' | 'warning' | 'critical' | 'exhausted';
  };
  violation: {
    id: string;
    startTime: Date;
    endTime: Date | null;
    duration: number;
    severity: 'minor' | 'major' | 'critical';
    impact: {
      affectedUsers: number | 'unknown';
      businessImpact: string;
      technicalDetails: string[];
    };
    budgetConsumption: number;
    isOngoing: boolean;
  };
}

export interface CorrelationInsight extends ObservabilityAlert {
  type: 'correlation' | 'log_correlation' | 'cascading_failure' | 'seasonal_pattern';
  correlationResult?: {
    sourceSignal: string;
    targetSignal: string;
    correlationType: 'positive' | 'negative' | 'leading' | 'lagging';
    strength: number;
    confidence: number;
    timeLag: number;
    significance: 'weak' | 'moderate' | 'strong' | 'very_strong';
    description: string;
    businessContext: string;
    technicalImplication: string[];
  };
  logCorrelation?: {
    logPattern: string;
    metricName: string;
    correlation: {
      type: 'precedes' | 'follows' | 'concurrent';
      strength: number;
      timeDelta: number;
    };
    businessImpact: string;
    actionable: boolean;
    recommendations: string[];
  };
  cascadingPattern?: {
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
      delay: number;
      impact: 'minor' | 'moderate' | 'major' | 'critical';
    }>;
    rootCause: {
      service: string;
      component: string;
      confidence: number;
      evidence: string[];
    };
    mitigation: string[];
  };
  seasonalPattern?: {
    patternId: string;
    metricName: string;
    patternType: 'daily' | 'weekly' | 'monthly' | 'hourly';
    amplitude: number;
    baselineValue: number;
    peakTimes: string[];
    confidence: number;
    businessContext: string;
    predictiveInsights: string[];
  };
}
