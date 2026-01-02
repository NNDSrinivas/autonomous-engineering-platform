/**
 * TypeScript Definitions for NAVI Cost & Usage Optimization Extension
 * 
 * Comprehensive type definitions for FinOps-aware engineering intelligence
 * covering multi-cloud cost analysis, waste detection, and optimization proposals.
 */

// Core Request/Response Types
export interface CostAnalysisRequest {
    sessionId?: string;
    config: {
        aws?: AWSCostConfig;
        gcp?: GCPBillingConfig;
        azure?: AzureCostConfig;
        kubernetes?: KubernetesConfig;
        traffic?: TrafficConfig;
    };
    timeRange?: {
        start: string;
        end: string;
    };
    analysisTypes?: AnalysisType[];
}

export interface CostAnalysisResult {
    sessionId: string;
    timestamp: string;
    summary: AnalysisSummary;
    issues: CostIssue[];
    proposals: OptimizationProposal[];
    savingsEstimates?: SavingsEstimate[];
    message?: string;
    error?: string;
    requiresApproval: boolean;
    nextActions: string[];
}

export interface AnalysisSummary {
    totalWasteDetected: number;
    potentialSavings: number;
    optimizationOpportunities: number;
    confidence: number;
}

// Cost Data Types
export interface CostData {
    aws: AWSCostData | null;
    gcp: GCPBillingData | null;
    azure: AzureCostData | null;
    consolidated: ConsolidatedCostData;
}

export interface ConsolidatedCostData {
    totalSpend: number;
    currency: string;
    period: string;
    breakdown: CostBreakdown[];
}

export interface CostBreakdown {
    service: string;
    cost: number;
    percentage: number;
    trend: 'increasing' | 'decreasing' | 'stable';
}

export interface AWSCostData {
    totalCost: number;
    services: AWSServiceCost[];
    regions: RegionCost[];
    instances: InstanceCost[];
    trends: CostTrend[];
}

export interface AWSServiceCost {
    serviceName: string;
    cost: number;
    usage: number;
    unit: string;
    category: 'compute' | 'storage' | 'network' | 'database' | 'other';
}

export interface GCPBillingData {
    totalCost: number;
    projects: GCPProjectCost[];
    services: GCPServiceCost[];
    regions: RegionCost[];
    trends: CostTrend[];
}

export interface GCPProjectCost {
    projectId: string;
    projectName: string;
    cost: number;
    services: GCPServiceCost[];
}

export interface GCPServiceCost {
    serviceName: string;
    cost: number;
    usage: number;
    unit: string;
}

export interface AzureCostData {
    totalCost: number;
    subscriptions: AzureSubscriptionCost[];
    resourceGroups: AzureResourceGroupCost[];
    services: AzureServiceCost[];
    trends: CostTrend[];
}

export interface AzureSubscriptionCost {
    subscriptionId: string;
    subscriptionName: string;
    cost: number;
    resourceGroups: AzureResourceGroupCost[];
}

export interface AzureResourceGroupCost {
    resourceGroupName: string;
    cost: number;
    resources: AzureResourceCost[];
}

export interface AzureResourceCost {
    resourceName: string;
    resourceType: string;
    cost: number;
    usage: number;
}

export interface AzureServiceCost {
    serviceName: string;
    cost: number;
    usage: number;
    unit: string;
}

export interface RegionCost {
    region: string;
    cost: number;
    percentage: number;
}

export interface InstanceCost {
    instanceId: string;
    instanceType: string;
    cost: number;
    usage: InstanceUsage;
    recommendations: string[];
}

export interface InstanceUsage {
    cpuUtilization: number;
    memoryUtilization: number;
    networkUtilization: number;
    storageUtilization: number;
}

export interface CostTrend {
    date: string;
    cost: number;
    change: number;
    changePercent: number;
}

// Usage Data Types
export interface UsageData {
    kubernetes: KubernetesUsageData | null;
    traffic: TrafficData | null;
    summary: UsageSummary;
}

export interface UsageSummary {
    totalResources: number;
    utilizationRate: number;
    idleResources: number;
}

export interface KubernetesUsageData {
    clusters: ClusterUsage[];
    nodes: NodeUsage[];
    pods: PodUsage[];
    namespaces: NamespaceUsage[];
    summary: K8sUsageSummary;
}

export interface ClusterUsage {
    clusterName: string;
    totalCost: number;
    nodes: number;
    pods: number;
    cpuRequests: number;
    memoryRequests: number;
    cpuLimits: number;
    memoryLimits: number;
    utilization: ResourceUtilization;
}

export interface NodeUsage {
    nodeName: string;
    instanceType: string;
    cost: number;
    utilization: ResourceUtilization;
    pods: PodUsage[];
    status: 'active' | 'idle' | 'overutilized';
}

export interface PodUsage {
    podName: string;
    namespace: string;
    cost: number;
    requests: ResourceRequests;
    limits: ResourceLimits;
    actualUsage: ResourceUtilization;
    efficiency: number; // 0-1 scale
    status: 'efficient' | 'overprovisioned' | 'underprovisioned' | 'idle';
}

export interface NamespaceUsage {
    namespaceName: string;
    cost: number;
    pods: number;
    utilization: ResourceUtilization;
    trends: UsageTrend[];
}

export interface ResourceRequests {
    cpu: number; // millicores
    memory: number; // bytes
    storage: number; // bytes
}

export interface ResourceLimits {
    cpu: number; // millicores
    memory: number; // bytes
}

export interface ResourceUtilization {
    cpu: number; // percentage 0-100
    memory: number; // percentage 0-100
    network: number; // percentage 0-100
    storage: number; // percentage 0-100
}

export interface K8sUsageSummary {
    totalCost: number;
    efficiency: number;
    wastedResources: number;
    recommendations: string[];
}

export interface UsageTrend {
    timestamp: string;
    utilization: ResourceUtilization;
}

export interface TrafficData {
    requests: TrafficMetric[];
    patterns: TrafficPattern[];
    peaks: TrafficPeak[];
    costCorrelation: number; // 0-1 correlation with cost
}

export interface TrafficMetric {
    timestamp: string;
    requests: number;
    bandwidth: number;
    regions: RegionTraffic[];
}

export interface RegionTraffic {
    region: string;
    requests: number;
    percentage: number;
}

export interface TrafficPattern {
    type: 'daily' | 'weekly' | 'seasonal';
    description: string;
    peakTimes: string[];
    costImpact: number;
}

export interface TrafficPeak {
    startTime: string;
    endTime: string;
    peakRequests: number;
    averageRequests: number;
    costImpact: number;
}

// Waste Detection Types
export interface WasteDetectionResult {
    id: string;
    type: WasteType;
    severity: 'low' | 'medium' | 'high' | 'critical';
    description: string;
    affectedResources: ResourceReference[];
    wastedAmount: number; // monthly waste in dollars
    confidence: number; // 0-1
    evidence: Evidence[];
    detectedAt: string;
}

export enum WasteType {
    IDLE_RESOURCES = 'IDLE_RESOURCES',
    OVERPROVISIONING = 'OVERPROVISIONING',
    UNUSED_VOLUMES = 'UNUSED_VOLUMES',
    OVERSIZED_INSTANCES = 'OVERSIZED_INSTANCES',
    COST_REGRESSION = 'COST_REGRESSION',
    POOR_UNIT_ECONOMICS = 'UNIT_ECONOMICS',
    SCHEDULING_INEFFICIENCY = 'SCHEDULING_INEFFICIENCY'
}

export interface ResourceReference {
    id: string;
    name: string;
    type: string;
    cloud: 'aws' | 'gcp' | 'azure' | 'kubernetes';
    region?: string;
    tags?: Record<string, string>;
}

export interface Evidence {
    type: 'metric' | 'billing' | 'usage' | 'trend';
    description: string;
    value: number;
    threshold: number;
    unit: string;
}

// Issue Classification Types
export interface CostIssue {
    id: string;
    type: IssueType;
    severity: IssueSeverity;
    title: string;
    description: string;
    explanation: string;
    businessImpact: BusinessImpact;
    technicalDetails: TechnicalDetails;
    affectedResources: ResourceReference[];
    estimatedSavings: number;
    confidence: number;
    priority: IssuePriority;
    detectedAt: string;
}

export enum IssueType {
    IDLE_RESOURCES = 'IDLE_RESOURCES',
    OVERPROVISIONING = 'OVERPROVISIONING',
    COST_REGRESSION = 'COST_REGRESSION',
    INEFFICIENT_SCALING = 'INEFFICIENT_SCALING',
    UNUSED_SERVICES = 'UNUSED_SERVICES',
    POOR_RESOURCE_ALLOCATION = 'POOR_RESOURCE_ALLOCATION'
}

export enum IssueSeverity {
    LOW = 'LOW',
    MEDIUM = 'MEDIUM',
    HIGH = 'HIGH',
    CRITICAL = 'CRITICAL'
}

export enum IssuePriority {
    P0 = 'P0', // Critical - immediate attention
    P1 = 'P1', // High - within 24 hours
    P2 = 'P2', // Medium - within week
    P3 = 'P3'  // Low - when convenient
}

export interface BusinessImpactDetails {
    monthlyWaste: number;
    annualImpact: number;
    percentageOfBudget: number;
    affectedServices: string[];
    userImpact: 'none' | 'low' | 'medium' | 'high';
    revenueImpact: 'none' | 'low' | 'medium' | 'high';
}

export type BusinessImpact = BusinessImpactDetails | 'low' | 'medium' | 'high' | 'critical';

export type RemediationComplexity = 'simple' | 'medium' | 'complex';

export interface TechnicalDetails {
    rootCause: string;
    symptoms: string[];
    metrics: TechnicalMetric[];
    recommendations: string[];
}

export interface TechnicalMetric {
    name: string;
    value: number;
    unit: string;
    threshold: number;
    status: 'normal' | 'warning' | 'critical';
}

// Optimization Proposal Types
export interface OptimizationProposal {
    id: string;
    issueId: string;
    title: string;
    description: string;
    type: OptimizationType;
    priority: IssuePriority;
    confidence: number;
    estimatedSavings: number;
    implementationEffort: ImplementationEffort;
    riskLevel: RiskLevel;
    requiresApproval: boolean;
    actions: OptimizationAction[];
    safeActions: SafeActionPlan;
    timeline: Timeline;
    rollbackPlan?: string;
}

export enum OptimizationType {
    RIGHTSIZING = 'RIGHTSIZING',
    AUTOSCALING = 'AUTOSCALING',
    SCHEDULING = 'SCHEDULING',
    RESERVED_INSTANCES = 'RESERVED_INSTANCES',
    SPOT_INSTANCES = 'SPOT_INSTANCES',
    STORAGE_OPTIMIZATION = 'STORAGE_OPTIMIZATION',
    NETWORK_OPTIMIZATION = 'NETWORK_OPTIMIZATION',
    SERVICE_CONSOLIDATION = 'SERVICE_CONSOLIDATION',
    INVESTIGATION = 'INVESTIGATION'
}

export enum ImplementationEffort {
    LOW = 'LOW',     // < 1 hour
    MEDIUM = 'MEDIUM', // 1-8 hours  
    HIGH = 'HIGH'      // > 8 hours
}

export enum RiskLevel {
    LOW = 'LOW',       // No service impact
    MEDIUM = 'MEDIUM', // Potential brief impact
    HIGH = 'HIGH'      // Potential service disruption
}

export interface OptimizationAction {
    order: number;
    action: string;
    description: string;
    command?: string;
    expectedResult: string;
    validation: string;
    rollbackCommand?: string;
    automatable: boolean;
}

export interface SafeActionPlan {
    immediate: string[];        // Safe actions that can be done immediately
    validation: string[];       // Steps to validate the optimization
    rollbackPlan: string;      // How to undo the optimization
    monitoring: string[];       // What to monitor after implementation
}

export interface Timeline {
    estimatedDuration: string;
    phases: TimelinePhase[];
    milestones: string[];
}

export interface TimelinePhase {
    phase: string;
    duration: string;
    description: string;
    dependencies: string[];
}

// Savings Estimation Types
export interface SavingsEstimate {
    issueId: string;
    wasteType: WasteType;
    baseWasteAmount: number;
    monthlyAmount: number;
    annualAmount: number;
    currency: string;
    confidence: number;
    breakdown: SavingsBreakdown[];
    immediateSavings: ImmediateSavings;
    recurringSavings: RecurringSavings;
    confidenceInterval: SavingsConfidenceInterval;
    realizationTimeline: SavingsRealizationTimeline;
    implementationCost: ImplementationCost;
    netSavings: number;
    roi: SavingsROI;
    riskAdjustment: RiskAdjustment;
    businessCase: BusinessCase;
    assumptions: string[];
    risks: string[];
    monitoring: MonitoringPlan;
    estimatedAt: string;
}

export interface SavingsBreakdown {
    category: string;
    amount: number;
    percentage: number;
    description: string;
}

export interface ImmediateSavings {
    amount: number;
    confidence: number;
    description: string;
}

export interface RecurringSavings {
    optimistic: number;
    realistic: number;
    conservative: number;
    confidence: number;
}

export interface SavingsConfidenceInterval {
    confidence: number;
    lowerBound: number;
    upperBound: number;
    methodology: string;
}

export interface SavingsRealizationTimeline {
    fullRealization: number;
    milestones: SavingsMilestone[];
}

export interface SavingsMilestone {
    day: number;
    percentage: number;
    description: string;
}

export interface ImplementationCost {
    engineering: number;
    testing: number;
    coordination: number;
    contingency: number;
    total: number;
}

export interface SavingsROI {
    monthsToPayback: number;
    annualROI: number;
    threeYearNPV: number;
    riskAdjustedROI: number;
}

export interface RiskAdjustment {
    factor: number;
    reasoning: string;
    mitigationStrategies: string[];
}

export interface BusinessCase {
    executiveSummary: string;
    financialSummary: string;
    strategicValue: string;
    recommendedAction: string;
}

export interface MonitoringPlan {
    keyMetrics: string[];
    checkpoints: Array<{ day: number; focus: string }>;
    successCriteria: string[];
    rollbackTriggers: string[];
}

// Configuration Types
export interface AWSCostConfig {
    region: string;
    accessKeyId: string;
    secretAccessKey: string;
    accountId?: string;
    costBudgets?: string[];
}

export interface GCPBillingConfig {
    projectId: string;
    keyFilePath: string;
    billingAccountId: string;
}

export interface AzureCostConfig {
    subscriptionId: string;
    clientId: string;
    clientSecret: string;
    tenantId: string;
}

export interface KubernetesConfig {
    kubeconfig?: string;
    context?: string;
    namespaces?: string[];
    metricsServer?: string;
}

export interface TrafficConfig {
    sources: TrafficSource[];
    timeRange: string;
}

export interface TrafficSource {
    type: 'prometheus' | 'cloudwatch' | 'stackdriver' | 'custom';
    endpoint: string;
    credentials?: Record<string, string>;
    queries: string[];
}

// Analysis Types
export enum AnalysisType {
    WASTE_DETECTION = 'WASTE_DETECTION',
    IDLE_RESOURCES = 'IDLE_RESOURCES',
    OVERPROVISIONING = 'OVERPROVISIONING',
    COST_REGRESSION = 'COST_REGRESSION',
    UNIT_ECONOMICS = 'UNIT_ECONOMICS',
    TRAFFIC_CORRELATION = 'TRAFFIC_CORRELATION'
}

// Approval and Security Types
export interface ApprovalRequirement {
    required: boolean;
    approvers: string[];
    reason: string;
    estimatedImpact: string;
    rollbackPlan: string;
}

export interface AuditLog {
    timestamp: string;
    action: string;
    user: string;
    resource: string;
    details: Record<string, any>;
    result: 'success' | 'failure' | 'pending';
}
// Extended Types for Analysis Engines
export interface IssueClassification {
    type: IssueType;
    severity: IssueSeverity;
    priority: IssuePriority;
    confidence: number;
    reasoning: string;
    businessImpact: BusinessImpact;
    technicalDetails: TechnicalDetails;
    nextSteps: string[];
    issueId: string;
    wasteType: WasteType;
    category: string;
    remediationComplexity: RemediationComplexity;
    urgency: 'low' | 'medium' | 'high' | 'critical';
    riskLevel: 'low' | 'medium' | 'high';
    affectedSystems: string[];
    estimatedEffort: number;
    approvalRequired: boolean;
    businessJustification: string;
    typicalCauses: string[];
    recommendedActions: string[];
    classifiedAt: string;
}

export interface CostExplanation {
    issue: CostIssue;
    rootCause: RootCauseAnalysis;
    businessContext: BusinessContext;
    technicalAnalysis: TechnicalAnalysis;
    recommendations: DetailedRecommendation[];
    relatedIssues?: string[]; // IDs of related issues
}

export interface RootCauseAnalysis {
    primaryCause: string;
    contributingFactors: string[];
    evidence: Evidence[];
    confidence: number;
    timeline: CauseTimeline[];
}

export interface BusinessContext {
    impactDescription: string;
    stakeholders: string[];
    budgetImpact: number;
    urgency: 'immediate' | 'high' | 'medium' | 'low';
    businessRisk: string;
}

export interface TechnicalAnalysis {
    affectedSystems: string[];
    performanceImpact: string;
    scalabilityImpact: string;
    securityImplications?: string;
    complexityLevel: 'low' | 'medium' | 'high';
}

export interface DetailedRecommendation {
    action: string;
    description: string;
    benefits: string[];
    risks: string[];
    effort: ImplementationEffort;
    timeline: string;
    prerequisites: string[];
    successMetrics: string[];
}

export interface CauseTimeline {
    timestamp: string;
    event: string;
    impact: string;
}

export interface CostOptimizationReport {
    reportId: string;
    generatedAt: string;
    summary: OptimizationSummary;
    detailedFindings: DetailedFinding[];
    executiveSummary: ExecutiveSummary;
    recommendations: PrioritizedRecommendation[];
    implementationPlan: ImplementationPlan;
    riskAssessment: RiskAssessment;
    nextSteps: string[];
}

export interface OptimizationSummary {
    totalPotentialSavings: number;
    monthlyWasteDetected: number;
    numberOfIssues: number;
    highPriorityIssues: number;
    averageConfidence: number;
    topWasteCategories: WasteType[];
    costTrend: 'improving' | 'stable' | 'worsening';
}

export interface DetailedFinding {
    category: string;
    issues: CostIssue[];
    totalImpact: number;
    recommendations: number;
    quickWins: string[];
    longTermOpportunities: string[];
}

export interface ExecutiveSummary {
    keyFindings: string[];
    businessImpact: string;
    recommendedActions: string[];
    expectedOutcome: string;
    investmentRequired: string;
    paybackPeriod: string;
}

export interface PrioritizedRecommendation {
    rank: number;
    recommendation: DetailedRecommendation;
    expectedSavings: number;
    implementationComplexity: 'simple' | 'moderate' | 'complex';
    dependsOn: string[];
}

export interface ImplementationPlan {
    phases: ImplementationPhase[];
    totalDuration: string;
    resourceRequirements: string[];
    milestones: PlanMilestone[];
    contingencies: string[];
}

export interface ImplementationPhase {
    phaseNumber: number;
    name: string;
    description: string;
    duration: string;
    recommendations: string[];
    deliverables: string[];
    successCriteria: string[];
}

export interface PlanMilestone {
    name: string;
    targetDate: string;
    description: string;
    dependencies: string[];
}

export interface RiskAssessment {
    overallRisk: RiskLevel;
    riskFactors: RiskFactor[];
    mitigationStrategies: string[];
    contingencyPlans: string[];
}

export interface RiskFactor {
    factor: string;
    impact: 'low' | 'medium' | 'high';
    probability: 'low' | 'medium' | 'high';
    mitigation: string;
}

// Remediation Types for approval-gated optimizations
export interface RemediationProposal {
    id: string;
    issueId: string;
    title: string;
    description: string;
    type: OptimizationType;
    priority: IssuePriority;
    actions: RemediationAction[];
    estimatedSavings: number;
    riskLevel: RiskLevel;
    requiresApproval: boolean;
    approvalWorkflow?: ApprovalWorkflow;
    safetyChecks: SafetyCheck[];
    rollbackPlan: RollbackPlan;
    timeline: Timeline;
}

export interface RemediationAction {
    id: string;
    type: RemediationActionType;
    description: string;
    command?: string;
    parameters?: Record<string, any>;
    validation: ValidationStep[];
    rollbackCommand?: string;
    automatable: boolean;
    requiresApproval: boolean;
    estimatedDuration: string;
    successCriteria: string[];
}

export enum RemediationActionType {
    INVESTIGATE = 'INVESTIGATE',
    RIGHTSIZE = 'RIGHTSIZE',
    SCALE_DOWN = 'SCALE_DOWN',
    TERMINATE = 'TERMINATE',
    MIGRATE = 'MIGRATE',
    OPTIMIZE = 'OPTIMIZE',
    SCHEDULE = 'SCHEDULE',
    CONFIGURE = 'CONFIGURE'
}

export interface ApprovalWorkflow {
    required: boolean;
    approvers: Approver[];
    escalationPath: string[];
    timeoutHours: number;
    autoApproveConditions?: AutoApprovalCondition[];
}

export interface Approver {
    role: string;
    email: string;
    level: 'primary' | 'secondary' | 'escalation';
}

export interface AutoApprovalCondition {
    condition: string;
    threshold: number;
    description: string;
}

export interface SafetyCheck {
    name: string;
    description: string;
    check: string;
    expectedResult: any;
    mandatory: boolean;
    rollbackTrigger: boolean;
}

export interface RollbackPlan {
    description: string;
    steps: RollbackStep[];
    timeLimit: string;
    triggerConditions: string[];
    emergencyContacts: string[];
}

export interface RollbackStep {
    order: number;
    description: string;
    command: string;
    validation: string;
    timeoutMinutes: number;
}

export interface ValidationStep {
    name: string;
    description: string;
    command?: string;
    expectedResult: any;
    timeoutMinutes: number;
    mandatory: boolean;
}

// Enhanced Analysis Result Types
export interface EnhancedSavingsEstimate extends SavingsEstimate {
    methodology: EstimationMethodology;
    historicalData: HistoricalDataPoint[];
    scenarios: SavingsScenario[];
    sensitivityAnalysis: SensitivityFactor[];
}

export interface EstimationMethodology {
    approach: 'historical' | 'predictive' | 'hybrid';
    dataPoints: number;
    timeRange: string;
    confidenceInterval: number;
    assumptions: DetailedAssumption[];
}

export interface DetailedAssumption {
    assumption: string;
    impact: 'low' | 'medium' | 'high';
    confidence: number;
    validation: string;
}

export interface HistoricalDataPoint {
    date: string;
    actualCost: number;
    optimizedCost: number;
    savings: number;
    context: string;
}

export interface SavingsScenario {
    name: string;
    description: string;
    probability: number;
    monthlyAmount: number;
    annualAmount: number;
    conditions: string[];
}

export interface SensitivityFactor {
    factor: string;
    impact: number; // percentage change in savings
    description: string;
}
