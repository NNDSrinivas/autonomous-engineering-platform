/**
 * NAVI Observability & Metrics Analyzer - Main Orchestration
 * 
 * Production-aware extension that turns NAVI into a Staff SRE + Production Debugger.
 * 
 * Key capabilities:
 * - Analyze runtime metrics, logs, and traces
 * - Detect anomalies and performance regressions
 * - Correlate signals deterministically (no ML hallucination)
 * - Explain issues with business impact
 * - Propose safe remediation steps with approval workflows
 * 
 * This extension establishes NAVI as production-intelligent, competing with
 * dedicated observability tools like DataDog, New Relic, and Grafana.
 * 
 * @author Navra Labs
 * @version 1.0.0
 */

import {
    ExtensionContext,
    ObservabilityAnalysisResult,
    DataSourceConfig,
    MetricSeries,
    LogEntry,
    TraceSpan,
    Anomaly,
    ClassifiedIssue,
    RemediationProposal,
    AnalysisSummary,
    SystemHealth,
    SLAStatus,
    HealthStatus,
    SeverityLevel,
    RemediationType,
    Priority,
    EffortLevel,
    RiskLevel
} from './types';

// Source imports
import { fetchPrometheusMetrics } from './sources/prometheus';
import { fetchDatadogMetrics } from './sources/datadog';
import { fetchCloudWatchMetrics } from './sources/cloudwatch';
import { fetchLogs } from './sources/logs';
import { fetchTraces } from './sources/traces';

// Analysis imports
import { detectAnomalies } from './analysis/anomalyDetector';
import { detectRegressions } from './analysis/regressionDetector';
import { analyzeSLA } from './analysis/slaAnalyzer';
import { correlateSignals } from './analysis/correlation';

// Diagnosis imports
import { classifyIssue } from './diagnosis/classifyIssue';
import { explainIssue } from './diagnosis/explain';
import { calculateImpact } from './diagnosis/impact';

// Remediation imports
import { proposeActions } from './remediation/proposeActions';
import { generateMitigation } from './remediation/mitigation';

/**
 * Main entry point for the Observability & Metrics Analyzer extension
 */
export async function onInvoke(context: ExtensionContext, config: DataSourceConfig): Promise<ObservabilityAnalysisResult> {
    console.log(`🔍 Starting observability analysis for session ${context.sessionId}...`);
    
    try {
        // Step 1: Collect observability data from all configured sources
        const [metrics, logs, traces] = await Promise.all([
            collectMetrics(config),
            collectLogs(config),
            collectTraces(config)
        ]);

        console.log(`📊 Collected ${metrics.length} metric series, ${logs.length} log entries, ${traces.length} trace spans`);

        // Step 2: Detect anomalies and regressions
        console.log('🔍 Detecting anomalies and regressions...');
        const anomalies = await detectAnomalies(metrics);
        const regressions = await detectRegressions(metrics, traces);
        console.log(`🚨 Detected ${anomalies.length} anomalies, ${regressions.length} regressions`);

        // Step 3: Analyze SLA compliance
        console.log('🎯 Analyzing SLA compliance...');
        const slaStatus = await analyzeSLA(metrics, logs);
        
        // Step 4: Correlate signals across different data sources
        console.log('🔗 Correlating observability signals...');
        const correlatedData = await correlateSignals(anomalies, logs, traces);
        console.log(`🔗 Found ${correlatedData.length} correlated signal groups`);

        // Step 5: Classify and diagnose issues
        const issues: ClassifiedIssue[] = [];
        for (const data of correlatedData) {
            const issue = await classifyIssue(data);
            if (issue) {
                // Enhance with detailed explanation and impact analysis
                const explanation = await explainIssue(issue);
                const impact = await calculateImpact(issue, metrics);
                
                issues.push({
                    ...issue,
                    businessImpact: impact.business,
                    technicalDetails: {
                        ...issue.technicalDetails,
                        ...impact.technical
                    }
                });
            }
        }

        console.log(`📋 Classified ${issues.length} distinct issues`);

        // Step 6: Generate remediation proposals
        const recommendations: RemediationProposal[] = [];
        for (const issue of issues) {
            const proposal = await proposeActions(issue);
            if (proposal) {
                recommendations.push(proposal);
            }
        }

        // Step 7: Generate system health assessment
        const systemHealth = calculateSystemHealth(metrics, anomalies);

        // Step 8: Generate analysis summary
        const summary = generateAnalysisSummary(issues, systemHealth, metrics.length > 0, logs.length > 0, traces.length > 0);

        // Step 9: Determine if approval is required
        const requiresApproval = determineApprovalRequirement(issues, recommendations);

        // Step 10: Generate next actions
        const nextActions = generateNextActions(issues, recommendations);

        const result: ObservabilityAnalysisResult = {
            sessionId: context.sessionId,
            timestamp: new Date().toISOString(),
            summary,
            issues,
            recommendations,
            systemHealth,
            slaStatus,
            insights: [], // Will be populated by future versions
            requiresApproval,
            nextActions
        };

        console.log(`✅ Analysis complete. Found ${issues.length} issues with ${recommendations.length} recommendations`);
        return result;

    } catch (error) {
        console.error('❌ Observability analysis failed:', error);
        return createErrorResult(context, error);
    }
}

/**
 * Collect metrics from all configured sources
 */
async function collectMetrics(config: DataSourceConfig): Promise<MetricSeries[]> {
    const allMetrics: MetricSeries[] = [];

    try {
        if (config.prometheus) {
            const prometheusMetrics = await fetchPrometheusMetrics(config.prometheus);
            allMetrics.push(...prometheusMetrics);
        }

        if (config.datadog) {
            const datadogMetrics = await fetchDatadogMetrics(config.datadog);
            allMetrics.push(...datadogMetrics);
        }

        if (config.cloudwatch) {
            const cloudwatchMetrics = await fetchCloudWatchMetrics(config.cloudwatch);
            allMetrics.push(...cloudwatchMetrics);
        }

        console.log(`📊 Collected metrics from ${Object.keys(config).length} sources`);
        return allMetrics;

    } catch (error) {
        console.error('Failed to collect metrics:', error);
        return [];
    }
}

/**
 * Collect logs from configured sources
 */
async function collectLogs(config: DataSourceConfig): Promise<LogEntry[]> {
    if (!config.logs) {
        return [];
    }

    try {
        return await fetchLogs(config.logs);
    } catch (error) {
        console.error('Failed to collect logs:', error);
        return [];
    }
}

/**
 * Collect traces from configured sources
 */
async function collectTraces(config: DataSourceConfig): Promise<TraceSpan[]> {
    if (!config.traces) {
        return [];
    }

    try {
        return await fetchTraces(config.traces);
    } catch (error) {
        console.error('Failed to collect traces:', error);
        return [];
    }
}

/**
 * Calculate overall system health based on metrics and anomalies
 */
function calculateSystemHealth(metrics: MetricSeries[], anomalies: Anomaly[]): SystemHealth {
    // Extract key system metrics (CPU, Memory, Disk, Network)
    const cpuMetrics = metrics.filter(m => m.name.toLowerCase().includes('cpu'));
    const memoryMetrics = metrics.filter(m => m.name.toLowerCase().includes('memory'));
    const diskMetrics = metrics.filter(m => m.name.toLowerCase().includes('disk'));
    const networkMetrics = metrics.filter(m => m.name.toLowerCase().includes('network'));

    const cpu = calculateAverageUtilization(cpuMetrics);
    const memory = calculateAverageUtilization(memoryMetrics);
    const disk = calculateAverageUtilization(diskMetrics);
    const network = calculateAverageUtilization(networkMetrics);

    // Determine overall health based on critical anomalies
    const criticalAnomalies = anomalies.filter(a => a.severity === SeverityLevel.CRITICAL);
    const highAnomalies = anomalies.filter(a => a.severity === SeverityLevel.HIGH);

    let overall: HealthStatus;
    if (criticalAnomalies.length > 0) {
        overall = HealthStatus.CRITICAL;
    } else if (highAnomalies.length > 2) {
        overall = HealthStatus.DEGRADED;
    } else if (cpu > 90 || memory > 95 || disk > 95) {
        overall = HealthStatus.CRITICAL;
    } else if (cpu > 80 || memory > 85 || disk > 85) {
        overall = HealthStatus.DEGRADED;
    } else {
        overall = HealthStatus.HEALTHY;
    }

    return {
        cpu,
        memory,
        disk,
        network,
        overall
    };
}

/**
 * Calculate average utilization from metric series
 */
function calculateAverageUtilization(metrics: MetricSeries[]): number {
    if (metrics.length === 0) {
        return 0;
    }

    const allValues = metrics.flatMap(m => m.dataPoints.map(dp => dp.value));
    if (allValues.length === 0) {
        return 0;
    }

    return allValues.reduce((sum, val) => sum + val, 0) / allValues.length;
}

/**
 * Generate analysis summary
 */
function generateAnalysisSummary(
    issues: ClassifiedIssue[],
    systemHealth: SystemHealth,
    hasMetrics: boolean,
    hasLogs: boolean,
    hasTraces: boolean
): AnalysisSummary {
    const criticalIssues = issues.filter(i => i.severity === SeverityLevel.CRITICAL).length;
    const majorIssues = issues.filter(i => i.severity === SeverityLevel.HIGH).length;
    const minorIssues = issues.filter(i => i.severity === SeverityLevel.MEDIUM || i.severity === SeverityLevel.LOW).length;

    return {
        overallHealth: systemHealth.overall,
        criticalIssues,
        majorIssues,
        minorIssues,
        timeRange: 'Last 15 minutes', // Configurable
        coverage: {
            metrics: hasMetrics,
            logs: hasLogs,
            traces: hasTraces,
            alerts: false // TODO: Implement alert integration
        },
        confidence: calculateOverallConfidence(issues)
    };
}

/**
 * Calculate overall confidence based on data coverage and issue confidence
 */
function calculateOverallConfidence(issues: ClassifiedIssue[]): number {
    if (issues.length === 0) {
        return 0.8; // High confidence when no issues detected
    }

    const avgConfidence = issues.reduce((sum, issue) => sum + issue.confidence, 0) / issues.length;
    return avgConfidence;
}

/**
 * Determine if human approval is required
 */
function determineApprovalRequirement(issues: ClassifiedIssue[], recommendations: RemediationProposal[]): boolean {
    // Approval required if there are critical issues
    if (issues.some(i => i.severity === SeverityLevel.CRITICAL)) {
        return true;
    }

    // Approval required if any recommendation requires it
    if (recommendations.some(r => r.requiresApproval)) {
        return true;
    }

    // Approval required if there are high-risk recommendations
    if (recommendations.some(r => r.risk === RiskLevel.HIGH)) {
        return true;
    }

    return false;
}

/**
 * Generate prioritized next actions
 */
function generateNextActions(issues: ClassifiedIssue[], recommendations: RemediationProposal[]): string[] {
    const actions: string[] = [];

    if (issues.length === 0) {
        actions.push('✅ No critical issues detected - system appears healthy');
        actions.push('📊 Continue monitoring key performance indicators');
        return actions;
    }

    // Prioritize critical issues
    const criticalIssues = issues.filter(i => i.severity === SeverityLevel.CRITICAL);
    if (criticalIssues.length > 0) {
        actions.push(`🚨 Address ${criticalIssues.length} critical issue(s) immediately`);
        criticalIssues.slice(0, 3).forEach(issue => {
            actions.push(`  • ${issue.title}`);
        });
    }

    // Add high-priority recommendations
    const highPriorityRecs = recommendations
        .filter(r => r.priority === Priority.P0 || r.priority === Priority.P1)
        .slice(0, 3);

    if (highPriorityRecs.length > 0) {
        actions.push(`🔧 Execute high-priority remediation steps:`);
        highPriorityRecs.forEach(rec => {
            actions.push(`  • ${rec.title}`);
        });
    }

    // Add monitoring recommendations
    if (recommendations.some(r => r.type === RemediationType.INVESTIGATION)) {
        actions.push('🔍 Continue investigation based on proposed action items');
    }

    return actions;
}

/**
 * Create error result when analysis fails
 */
function createErrorResult(context: ExtensionContext, error: any): ObservabilityAnalysisResult {
    return {
        sessionId: context.sessionId,
        timestamp: new Date().toISOString(),
        summary: {
            overallHealth: HealthStatus.UNAVAILABLE,
            criticalIssues: 0,
            majorIssues: 0,
            minorIssues: 0,
            timeRange: 'N/A',
            coverage: {
                metrics: false,
                logs: false,
                traces: false,
                alerts: false
            },
            confidence: 0
        },
        issues: [],
        recommendations: [{
            id: 'error-remediation',
            title: 'Analysis Failed',
            description: `Observability analysis failed: ${error.message}`,
            type: RemediationType.INVESTIGATION,
            priority: Priority.P2,
            confidence: 1.0,
            effort: EffortLevel.LOW,
            risk: RiskLevel.LOW,
            requiresApproval: false,
            estimatedImpact: 'Enable proper observability data collection',
            steps: [
                {
                    order: 1,
                    action: 'Verify data source configurations',
                    validation: 'Ensure all endpoints are accessible',
                    automatable: false
                },
                {
                    order: 2,
                    action: 'Check network connectivity to observability systems',
                    validation: 'Connectivity test passes',
                    automatable: true
                }
            ],
            rollbackPlan: {
                canRollback: false,
                steps: [],
                timeEstimate: 'N/A',
                dataLoss: false
            },
            monitoring: {
                metrics: ['extension_health'],
                alerts: [],
                duration: '5 minutes',
                successCriteria: ['Successful data collection']
            }
        }],
        systemHealth: {
            cpu: 0,
            memory: 0,
            disk: 0,
            network: 0,
            overall: HealthStatus.UNAVAILABLE
        },
        slaStatus: {
            availability: {
                current: 0,
                target: 99.9,
                status: 'BREACHED'
            },
            latency: {
                p95: 0,
                target: 500,
                status: 'BREACHED'
            },
            errorRate: {
                current: 100,
                target: 1,
                status: 'BREACHED'
            }
        },
        insights: [],
        requiresApproval: false,
        nextActions: [
            '🔧 Fix observability data collection configuration',
            '📞 Contact SRE team for assistance',
            '📊 Verify monitoring system health'
        ]
    };
}
