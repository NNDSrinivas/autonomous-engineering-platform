/**
 * Kubernetes Diagnostics Extension - Main Entry Point
 * 
 * NAVI extension for diagnosing Kubernetes cluster issues, explaining failures,
 * and proposing safe, approval-gated remediation steps.
 * 
 * Extension Identity: navi-k8s-diagnostics
 * Trust Level: CORE (cryptographically signed)
 * Permissions: K8S_READ, K8S_LOGS, REPO_READ, REQUEST_APPROVAL, PROPOSE_ACTIONS
 */

import {
    ExtensionContext,
    DiagnosticsResult,
    KubernetesIssue,
    IssueType,
    IssueSeverity
} from './types';

// Import inspection modules
import { getClusterInfo, checkKubectlAccess } from './k8s/clusterInfo';
import { inspectPods, inspectProblemPods } from './k8s/podInspector';
import { inspectDeployments, inspectProblemDeployments } from './k8s/deploymentInspector';
import { inspectServices, inspectProblemServices } from './k8s/serviceInspector';
import { getClusterEvents, filterCriticalEvents } from './k8s/events';
import { getPodLogs, analyzeLogPatterns } from './k8s/logs';

// Import diagnosis modules
import { classifyIssues, DiagnosticData } from './diagnosis/classifyIssue';
import { explainIssue } from './diagnosis/explain';
import { proposeRemediation } from './diagnosis/remediation';

/**
 * Main extension entry point
 * Called when NAVI detects intent: DIAGNOSE_INFRA → K8S_DIAGNOSTICS
 */
export async function onInvoke(ctx: ExtensionContext): Promise<DiagnosticsResult> {
    console.log('🔍 NAVI Kubernetes Diagnostics Extension v1.0.0 starting...');

    try {
        // Verify cluster access
        const hasAccess = await checkKubectlAccess();
        if (!hasAccess) {
            return {
                issues: [],
                clusterOverview: {
                    totalPods: 0,
                    healthyPods: 0,
                    totalDeployments: 0,
                    healthyDeployments: 0,
                    totalServices: 0
                },
                recommendations: [
                    '❌ No kubectl access detected',
                    '🔧 Verify kubectl is installed and configured',
                    '🔑 Check cluster credentials and connectivity',
                    '📋 Run: kubectl cluster-info'
                ],
                requiresApproval: false,
                summary: 'Kubernetes diagnostics failed - no cluster access',
                nextSteps: []
            };
        }

        console.log('✅ Cluster access verified - gathering diagnostic data...');

        // Gather comprehensive diagnostic data
        const diagnosticData = await gatherDiagnosticData(ctx);

        console.log(`📊 Data gathered: ${diagnosticData.pods.length} pods, ${diagnosticData.deployments.length} deployments, ${diagnosticData.services.length} services`);

        // Classify issues using deterministic analysis
        const issues = classifyIssues(ctx, diagnosticData);

        console.log(`🚨 Issues detected: ${issues.length} (${issues.filter(i => i.severity === IssueSeverity.CRITICAL).length} critical)`);

        // Generate explanations and remediation proposals
        const diagnosticsResult = await generateDiagnosticsResult(ctx, issues, diagnosticData);

        console.log(`✅ Kubernetes diagnostics complete - ${issues.length} issues analyzed`);
        return diagnosticsResult;

    } catch (error) {
        console.error('❌ Kubernetes diagnostics failed:', error);
        return {
            issues: [],
            clusterOverview: {
                totalPods: 0,
                healthyPods: 0,
                totalDeployments: 0,
                healthyDeployments: 0,
                totalServices: 0
            },
            recommendations: [
                `❌ Diagnostics failed: ${error}`,
                '🔧 Check cluster connectivity and permissions',
                '📋 Verify kubectl configuration',
                '🔍 Review extension logs for details'
            ],
            requiresApproval: false,
            summary: `Kubernetes diagnostics error: ${error}`,
            nextSteps: []
        };
    }
}

async function gatherDiagnosticData(ctx: ExtensionContext): Promise<DiagnosticData> {
    // Get cluster overview
    const clusterInfo = await getClusterInfo(ctx);
    console.log(`🏗️ Cluster: ${clusterInfo.version}, ${clusterInfo.nodeCount} nodes, ${clusterInfo.namespaces.length} namespaces`);

    // Inspect all resources in parallel for performance
    const [
        allPods,
        allDeployments,
        allServices,
        recentEvents
    ] = await Promise.all([
        inspectPods(ctx),
        inspectDeployments(ctx),
        inspectServices(ctx),
        getClusterEvents(ctx, undefined, 30) // Last 30 minutes
    ]);

    // Focus on critical events to reduce noise
    const criticalEvents = filterCriticalEvents(recentEvents);

    console.log(`📋 Events: ${recentEvents.length} total, ${criticalEvents.length} critical`);

    return {
        pods: allPods,
        deployments: allDeployments,
        services: allServices,
        events: criticalEvents,
        clusterInfo: {
            nodeCount: clusterInfo.nodeCount,
            version: clusterInfo.version,
            namespaces: clusterInfo.namespaces
        }
    };
}

async function generateDiagnosticsResult(
    ctx: ExtensionContext,
    issues: KubernetesIssue[],
    data: DiagnosticData
): Promise<DiagnosticsResult> {

    // Calculate cluster overview metrics
    const clusterOverview = {
        totalPods: data.pods.length,
        healthyPods: data.pods.filter(pod =>
            pod.status.phase === 'Running' &&
            pod.status.containerStatuses?.every(cs => cs.ready)
        ).length,
        totalDeployments: data.deployments.length,
        healthyDeployments: data.deployments.filter(dep =>
            dep.status.readyReplicas >= dep.spec.replicas
        ).length,
        totalServices: data.services.length
    };

    // Generate recommendations based on issues found
    const recommendations = generateRecommendations(issues, clusterOverview);

    // Generate remediation proposals for high-confidence issues
    const nextSteps = await Promise.all(
        issues
            .filter(issue => issue.confidence >= 0.7)
            .slice(0, 5) // Limit to top 5 issues
            .map(issue => proposeRemediation(ctx, issue))
    );

    // Determine if any actions require approval
    const requiresApproval = nextSteps.some(proposal => proposal.requiresApproval);

    // Generate summary
    const criticalCount = issues.filter(i => i.severity === IssueSeverity.CRITICAL).length;
    const highCount = issues.filter(i => i.severity === IssueSeverity.HIGH).length;

    let summary = '';
    if (criticalCount > 0) {
        summary = `🚨 ${criticalCount} critical issues detected requiring immediate attention`;
    } else if (highCount > 0) {
        summary = `⚠️ ${highCount} high-priority issues found affecting cluster health`;
    } else if (issues.length > 0) {
        summary = `ℹ️ ${issues.length} issues identified for monitoring and potential remediation`;
    } else {
        summary = '✅ No critical issues detected - cluster appears healthy';
    }

    // Add detailed explanations to issues
    const issuesWithExplanations = await Promise.all(
        issues.map(async issue => {
            const explanation = explainIssue(ctx, issue);
            return {
                ...issue,
                explanation
            };
        })
    );

    console.log(`📊 Generated ${recommendations.length} recommendations and ${nextSteps.length} remediation proposals`);

    return {
        issues: issuesWithExplanations,
        clusterOverview,
        recommendations,
        requiresApproval,
        summary,
        nextSteps
    };
}

function generateRecommendations(issues: KubernetesIssue[], overview: any): string[] {
    const recommendations = [];

    // Critical issues recommendations
    const criticalIssues = issues.filter(i => i.severity === IssueSeverity.CRITICAL);
    if (criticalIssues.length > 0) {
        recommendations.push(`🚨 Immediate action required: ${criticalIssues.length} critical issues detected`);
        recommendations.push('🔍 Focus on CrashLoopBackOff and deployment failures first');
        recommendations.push('📞 Consider escalating to on-call engineer if user-facing services affected');
    }

    // Pod health recommendations
    const healthyPodPercent = overview.totalPods > 0 ?
        Math.round((overview.healthyPods / overview.totalPods) * 100) : 100;

    if (healthyPodPercent < 80) {
        recommendations.push(`⚠️ Pod health: ${healthyPodPercent}% (${overview.healthyPods}/${overview.totalPods}) - investigate unhealthy pods`);
    } else if (healthyPodPercent < 95) {
        recommendations.push(`📊 Pod health: ${healthyPodPercent}% - monitor for declining trends`);
    }

    // Deployment health recommendations
    const healthyDeploymentPercent = overview.totalDeployments > 0 ?
        Math.round((overview.healthyDeployments / overview.totalDeployments) * 100) : 100;

    if (healthyDeploymentPercent < 90) {
        recommendations.push(`📈 Deployment health: ${healthyDeploymentPercent}% - check replica availability`);
    }

    // Issue pattern recommendations
    const crashLoops = issues.filter(i => i.type === IssueType.CRASH_LOOP);
    if (crashLoops.length >= 3) {
        recommendations.push('🔄 Multiple crash loops detected - check for system-wide issues (resource constraints, config problems)');
    }

    const imageIssues = issues.filter(i => i.type === IssueType.IMAGE_PULL_ERROR);
    if (imageIssues.length >= 2) {
        recommendations.push('🖼️ Multiple image pull errors - verify registry connectivity and credentials');
    }

    const networkIssues = issues.filter(i => i.type === IssueType.NETWORK_POLICY_BLOCK);
    if (networkIssues.length > 0) {
        recommendations.push('🌐 Network connectivity issues detected - review NetworkPolicies and DNS');
    }

    // General health recommendations
    if (issues.length === 0) {
        recommendations.push('✅ Cluster appears healthy - continue monitoring');
        recommendations.push('📊 Consider setting up proactive monitoring and alerting');
        recommendations.push('🔄 Regular health checks recommended to catch issues early');
    }

    // Always include SRE best practices
    recommendations.push('📋 Document any manual fixes in runbooks for future reference');
    recommendations.push('🔍 Review logs and metrics for additional context before taking action');

    return recommendations;
}

// Export additional utility functions for testing
export {
    gatherDiagnosticData,
    generateDiagnosticsResult,
    generateRecommendations
};