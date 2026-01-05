/**
 * Kubernetes Issue Explanation Module
 * 
 * Generates human-readable explanations for Kubernetes issues in both
 * user-friendly and SRE technical language. Provides context and root cause analysis.
 */

import { 
    KubernetesIssue, 
    IssueExplanation, 
    IssueType,
    ExtensionContext 
} from '../types';

export function explainIssue(ctx: ExtensionContext, issue: KubernetesIssue): IssueExplanation {
    switch (issue.type) {
        case IssueType.CRASH_LOOP:
            return explainCrashLoop(issue);
        case IssueType.DEPLOYMENT_DOWN:
            return explainDeploymentDown(issue);
        case IssueType.SERVICE_UNREACHABLE:
            return explainServiceUnreachable(issue);
        case IssueType.RESOURCE_EXHAUSTION:
            return explainResourceExhaustion(issue);
        case IssueType.IMAGE_PULL_ERROR:
            return explainImagePullError(issue);
        case IssueType.NETWORK_POLICY_BLOCK:
            return explainNetworkPolicyBlock(issue);
        case IssueType.CONFIG_ERROR:
            return explainConfigError(issue);
        case IssueType.RBAC_DENIAL:
            return explainRBACDenial(issue);
        default:
            return explainGenericIssue(issue);
    }
}

function explainCrashLoop(issue: KubernetesIssue): IssueExplanation {
    const podName = issue.resource.name;
    const namespace = issue.resource.namespace;
    
    return {
        summary: `Pods are stuck in CrashLoopBackOff in ${namespace}`,
        details: [
            "**What's happening:** Your application containers are repeatedly crashing and restarting.",
            "**User Impact:** Application is unavailable - users cannot access the service.",
            "**Timeline:** Kubernetes waits increasingly longer between restart attempts (exponential backoff).",
            "**Typical Duration:** Without intervention, this can continue indefinitely."
        ],
        rootCause: "The most common causes are:\n" +
                   "• Application startup failure (missing environment variables, configuration errors)\n" +
                   "• Resource constraints (insufficient memory/CPU)\n" +
                   "• Dependency failures (database unreachable, external services down)\n" +
                   "• Code bugs causing immediate crashes on startup",
        impact: `**Business Impact:** ${issue.severity}\n` +
                `• Service downtime affecting ${issue.affectedPods?.length || 1} instances\n` +
                `• Users experiencing 503/504 errors\n` +
                `• Potential data loss if crashes occur during processing`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Pod: ${podName} in namespace ${namespace}\n` +
                   `• Pattern: CrashLoopBackOff indicates systematic failure, not transient issue\n` +
                   `• Investigation priority: Check logs → environment → dependencies → code\n` +
                   `• Monitoring: Set up alerts for restart count > 5 to catch early\n` +
                   `• Runbook: This is a common incident pattern, document troubleshooting steps`
    };
}

function explainDeploymentDown(issue: KubernetesIssue): IssueExplanation {
    const deploymentName = issue.resource.name;
    const namespace = issue.resource.namespace;
    
    return {
        summary: `Deployment ${deploymentName} has insufficient healthy replicas`,
        details: [
            "**What's happening:** Your deployment doesn't have enough running pods to handle traffic.",
            "**User Impact:** Reduced capacity or complete service unavailability.",
            "**Load Impact:** Remaining pods (if any) are handling higher than expected load.",
            "**Auto-scaling:** If HPA is configured, it may try to scale up but failing pods prevent progress."
        ],
        rootCause: "Deployment replica shortage typically indicates:\n" +
                   "• Pod startup failures (see individual pod status)\n" +
                   "• Resource constraints (cluster capacity, resource quotas)\n" +
                   "• Node issues (nodes down, cordoned, or insufficient resources)\n" +
                   "• Image pull failures preventing new pods from starting\n" +
                   "• Failed rollout due to configuration changes",
        impact: `**Business Impact:** ${issue.severity}\n` +
                `• Service degraded or down\n` +
                `• Reduced resilience - no failover capacity\n` +
                `• Potential cascade failures if remaining pods are overloaded`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Deployment: ${deploymentName} in ${namespace}\n` +
                   `• Check: kubectl get pods -n ${namespace} -l <deployment-selector>\n` +
                   `• Investigate: Pod events, node capacity, resource quotas\n` +
                   `• Immediate: Consider manual scaling if underlying issue is resource limits\n` +
                   `• Long-term: Review resource requests/limits and cluster capacity planning`
    };
}

function explainServiceUnreachable(issue: KubernetesIssue): IssueExplanation {
    const serviceName = issue.resource.name;
    const namespace = issue.resource.namespace;
    
    return {
        summary: `Service ${serviceName} cannot route traffic to healthy backends`,
        details: [
            "**What's happening:** The service exists but has no healthy pods to forward requests to.",
            "**User Impact:** API calls return connection errors, timeouts, or 503 Service Unavailable.",
            "**Load Balancer:** External load balancers show this service as unhealthy.",
            "**DNS:** Service DNS resolution works, but connections fail."
        ],
        rootCause: "Service unreachability usually means:\n" +
                   "• No pods match the service selector (label mismatch)\n" +
                   "• All matching pods are unhealthy or not ready\n" +
                   "• Service ports don't match container ports\n" +
                   "• LoadBalancer provisioning failed (cloud provider issues)\n" +
                   "• Network policies blocking traffic flow",
        impact: `**Business Impact:** ${issue.severity}\n` +
                `• API endpoints returning errors\n` +
                `• External integrations failing\n` +
                `• User-facing features broken`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Service: ${serviceName} in ${namespace}\n` +
                   `• Debug: kubectl get endpoints ${serviceName} -n ${namespace}\n` +
                   `• Check: Service selector vs pod labels\n" +
                   `• Verify: Port mappings and readiness probes\n" +
                   `• LoadBalancer: Check cloud provider console for provisioning status`
    };
}

function explainResourceExhaustion(issue: KubernetesIssue): IssueExplanation {
    return {
        summary: `Resource exhaustion detected - pods running out of memory or CPU`,
        details: [
            "**What's happening:** Your application is consuming more resources than allocated.",
            "**Memory:** OOMKilled events indicate memory limit exceeded - pod gets terminated.",
            "**CPU:** CPU throttling degrades performance before limits are enforced.",
            "**Pattern:** Resource exhaustion often correlates with traffic spikes or memory leaks."
        ],
        rootCause: "Resource exhaustion causes:\n" +
                   "• Memory leaks in application code\n" +
                   "• Insufficient resource limits/requests configured\n" +
                   "• Traffic spikes exceeding expected load\n" +
                   "• Large dataset processing without streaming\n" +
                   "• Inefficient algorithms or database queries",
        impact: `**Business Impact:** ${issue.severity}\n" +
                `• Intermittent application crashes\n" +
                `• Performance degradation during high load\n" +
                `• Unreliable user experience`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Resource: ${issue.resource.name} in ${issue.resource.namespace}\n" +
                   `• Monitor: Set up resource utilization alerts\n" +
                   `• Immediate: Increase resource limits if cluster has capacity\n" +
                   `• Investigate: Memory/CPU usage patterns over time\n" +
                   `• Long-term: Application performance profiling and optimization`
    };
}

function explainImagePullError(issue: KubernetesIssue): IssueExplanation {
    return {
        summary: `Cannot pull container image - pods stuck at ImagePullBackOff`,
        details: [
            "**What's happening:** Kubernetes cannot download the container image from the registry.",
            "**Pod Status:** Pods remain in Pending state, never reach Running.",
            "**Retry Logic:** Kubernetes retries with exponential backoff but won't give up.",
            "**Deployment:** New rollouts are blocked until image pull succeeds."
        ],
        rootCause: "Image pull failures typically indicate:\n" +
                   "• Image doesn't exist or was deleted from registry\n" +
                   "• Incorrect image tag or repository name\n" +
                   "• Missing or expired registry credentials\n" +
                   "• Private registry authentication issues\n" +
                   "• Network connectivity to image registry\n" +
                   "• Registry rate limiting or service issues",
        impact: `**Business Impact:** ${issue.severity}\n" +
                `• New deployments fail completely\n" +
                `• Cannot scale up to handle increased load\n" +
                `• Rollbacks may also fail if previous images unavailable`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Resource: ${issue.resource.name} in ${issue.resource.namespace}\n" +
                   `• Debug: kubectl describe pod <pod-name> -n ${issue.resource.namespace}\n" +
                   `• Verify: Image exists in registry and credentials are valid\n" +
                   `• Check: ImagePullSecrets configuration\n" +
                   `• Test: Manual docker pull from cluster nodes`
    };
}

function explainNetworkPolicyBlock(issue: KubernetesIssue): IssueExplanation {
    return {
        summary: `Network connectivity issues detected across multiple services`,
        details: [
            "**What's happening:** Pods cannot communicate with each other or external services.",
            "**Symptoms:** Connection timeouts, 'connection refused' errors in logs.",
            "**Scope:** Multiple pods/services affected suggests policy-level blocking.",
            "**Intermittent:** May work from some pods but not others."
        ],
        rootCause: "Network connectivity problems usually stem from:\n" +
                   "• NetworkPolicies blocking required traffic flows\n" +
                   "• Service mesh configuration issues\n" +
                   "• DNS resolution problems\n" +
                   "• Cluster networking (CNI) issues\n" +
                   "• Firewall rules blocking pod-to-pod communication\n" +
                   "• External service dependencies down",
        impact: `**Business Impact:** ${issue.severity}\n" +
                `• Microservices cannot communicate\n" +
                `• External API integrations failing\n" +
                `• Database connections timing out`,
        sreContext: "**SRE Perspective:**\n" +
                   "• Cluster-wide networking issue detected\n" +
                   "• Debug: kubectl get networkpolicies --all-namespaces\n" +
                   "• Test: Pod-to-pod connectivity with netshoot\n" +
                   "• Verify: DNS resolution and service discovery\n" +
                   "• Check: CNI plugin logs and cluster networking health"
    };
}

function explainConfigError(issue: KubernetesIssue): IssueExplanation {
    return {
        summary: `Configuration error preventing pod startup`,
        details: [
            "**What's happening:** Pod configuration is invalid and containers cannot be created.",
            "**Common Issues:** Missing ConfigMaps, invalid environment variables, malformed secrets.",
            "**Immediate:** Pods fail to start, no container process runs.",
            "**Validation:** Kubernetes validates config at creation time, but runtime dependencies may fail."
        ],
        rootCause: "Configuration errors typically involve:\n" +
                   "• Missing ConfigMap or Secret references\n" +
                   "• Invalid environment variable syntax\n" +
                   "• Incorrect volume mount paths\n" +
                   "• Security context conflicts\n" +
                   "• Resource constraint syntax errors",
        impact: `**Business Impact:** ${issue.severity}\n" +
                `• Application cannot start\n" +
                `• Deployment rollouts fail\n" +
                `• Service completely unavailable`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Resource: ${issue.resource.name} in ${issue.resource.namespace}\n" +
                   `• Debug: kubectl describe pod <pod> for detailed error messages\n" +
                   `• Verify: All referenced ConfigMaps and Secrets exist\n" +
                   `• Check: YAML syntax and Kubernetes resource validation\n" +
                   `• Fix: Correct configuration and re-apply manifests`
    };
}

function explainRBACDenial(issue: KubernetesIssue): IssueExplanation {
    return {
        summary: `RBAC permissions preventing required operations`,
        details: [
            "**What's happening:** Pods or controllers lack permissions for required Kubernetes API operations.",
            "**Symptoms:** 'Forbidden' errors in logs, controllers unable to manage resources.",
            "**Security:** RBAC is working as designed, but legitimate operations are blocked.",
            "**Scope:** May affect specific namespaces or cluster-wide operations."
        ],
        rootCause: "RBAC permission denials indicate:\n" +
                   "• Missing or incomplete Role/ClusterRole definitions\n" +
                   "• ServiceAccount not bound to required roles\n" +
                   "• Incorrect namespace-level permissions\n" +
                   "• Overly restrictive security policies\n" +
                   "• Application trying to access forbidden resources",
        impact: `**Business Impact:** ${issue.severity}\n" +
                `• Controllers unable to manage workloads\n" +
                `• Applications cannot access required APIs\n" +
                `• Automated operations failing`,
        sreContext: "**SRE Perspective:**\n" +
                   `• Resource: ${issue.resource.name} in ${issue.resource.namespace}\n" +
                   `• Debug: kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<namespace>:<sa>\n" +
                   `• Check: RoleBinding and ClusterRoleBinding configurations\n" +
                   `• Verify: ServiceAccount assignments in pod specs\n" +
                   `• Security: Follow principle of least privilege when adding permissions`
    };
}

function explainGenericIssue(issue: KubernetesIssue): IssueExplanation {
    return {
        summary: `Kubernetes issue detected: ${issue.description}`,
        details: [
            "**What's happening:** A Kubernetes resource is not functioning as expected.",
            `**Resource:** ${issue.resource.kind} ${issue.resource.name} in ${issue.resource.namespace}`,
            `**Severity:** ${issue.severity} issue requiring attention.`,
            "**Investigation:** Manual troubleshooting required to determine root cause."
        ],
        rootCause: `Issue type ${issue.type} detected with symptoms:\n` +
                   issue.symptoms.map(s => `• ${s}`).join('\n'),
        impact: `**Business Impact:** ${issue.severity}\n" +
                `• Resource health compromised\n" +
                `• May affect dependent services`,
        sreContext: `**SRE Perspective:**\n" +
                   `• Resource: ${issue.resource.kind}/${issue.resource.name} in ${issue.resource.namespace}\n" +
                   `• Confidence: ${Math.round(issue.confidence * 100)}%\n" +
                   `• Related events: ${issue.relatedEvents.length}\n" +
                   `• Manual investigation required for detailed diagnosis`
    };
}