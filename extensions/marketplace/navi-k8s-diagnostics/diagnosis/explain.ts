/**
 * Issue Explanation Module
 * 
 * Provides human-readable and SRE-focused explanations for classified Kubernetes issues.
 * Dual-level explanations help both technical teams and stakeholders understand the impact.
 */

import { ExtensionContext, KubernetesIssue, IssueType, IssueSeverity } from '../types';

export interface IssueExplanation {
    humanExplanation: string;    // Non-technical explanation for stakeholders
    sreExplanation: string;      // Technical explanation for SRE teams
    impact: string;              // Business and technical impact
    urgency: string;             // Priority and timeline
    nextSteps: string[];         // Actionable steps
    rootCause: string;           // Common causes and investigation areas
    sreContext: string;          // Technical context and debugging info
}

/**
 * Generate human-readable explanation for a classified Kubernetes issue
 */
export function explainIssue(ctx: ExtensionContext, issue: KubernetesIssue): IssueExplanation {
    console.log('🔍 Generating explanation for issue:', issue.type);

    switch (issue.type) {
        case IssueType.CRASH_LOOP:
            return explainCrashLoop(issue);

        case IssueType.DEPLOYMENT_DOWN:
            return explainDeploymentDown(issue);

        case IssueType.IMAGE_PULL_ERROR:
            return explainImagePullError(issue);

        case IssueType.SERVICE_UNREACHABLE:
            return explainServiceUnreachable(issue);

        case IssueType.RESOURCE_QUOTA_EXCEEDED:
            return explainResourceQuotaExceeded(issue);

        case IssueType.CONFIG_ERROR:
            return explainConfigError(issue);

        case IssueType.NETWORK_POLICY_BLOCK:
            return explainNetworkPolicyBlock(issue);

        case IssueType.NODE_NOT_READY:
            return explainNodeNotReady(issue);

        default:
            return explainGenericIssue(issue);
    }
}

function explainCrashLoop(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Your application container keeps crashing and restarting repeatedly. " +
            "This is like a car that won't start properly - every time it tries to run, something goes wrong and it shuts down, " +
            "then the system automatically tries to start it again.",

        sreExplanation: "CrashLoopBackOff indicates the container is failing to start or stay running consistently. " +
            "Kubernetes is backing off restart attempts with exponential delay to prevent resource exhaustion.",

        impact: "**Business Impact:** Critical\n" +
            "• Service is unavailable to users\n" +
            "• Complete loss of functionality for this component\n" +
            "• May affect dependent services and workflows",

        urgency: "Immediate - Service disruption in progress",

        nextSteps: [
            "Check application logs immediately for error messages",
            "Verify resource limits (CPU/memory) are adequate",
            "Review recent code or configuration changes",
            "Check health check endpoints and startup probes",
            "Validate environment variables and secrets"
        ],

        rootCause: "Most commonly caused by:\n" +
            "• Application errors or exceptions during startup\n" +
            "• Insufficient memory or CPU resources\n" +
            "• Missing or incorrect environment variables\n" +
            "• Failed health check or readiness probes\n" +
            "• Corrupted application configuration",

        sreContext: "**SRE Perspective:**\n" +
            "• Check: kubectl logs <pod-name> --previous for crash details\n" +
            "• Monitor: CPU/memory usage patterns before crashes\n" +
            "• Verify: Resource requests/limits vs actual usage\n" +
            "• Debug: Application startup sequence and dependencies"
    };
}

function explainDeploymentDown(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Your deployment isn't running any healthy instances of your application. " +
            "This means users cannot access your service at all - it's like having a restaurant with no open tables.",

        sreExplanation: "Deployment has zero ready replicas, indicating systematic failure to create or maintain healthy pods. " +
            "This could be due to resource constraints, configuration issues, or infrastructure problems.",

        impact: "**Business Impact:** Critical\n" +
            "• Complete service outage\n" +
            "• All user traffic failing\n" +
            "• Potential data loss if stateful\n" +
            "• SLA violations likely",

        urgency: "Immediate - Complete service outage",

        nextSteps: [
            "Check deployment status and replica count",
            "Examine pod events for creation failures",
            "Verify cluster has adequate resources",
            "Review recent deployment changes",
            "Check for node scheduling issues"
        ],

        rootCause: "Deployment failures typically caused by:\n" +
            "• Resource exhaustion (CPU, memory, storage)\n" +
            "• Image pull failures or registry issues\n" +
            "• Node affinity or scheduling constraints\n" +
            "• Persistent volume mounting problems\n" +
            "• Invalid deployment configuration",

        sreContext: "**SRE Perspective:**\n" +
            "• Emergency: Scale down if partial service possible\n" +
            "• Investigate: kubectl describe deployment <name>\n" +
            "• Check: kubectl get events --sort-by=.metadata.creationTimestamp\n" +
            "• Consider: Rollback to previous working version"
    };
}

function explainImagePullError(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Kubernetes cannot download your application's container image. " +
            "This is like trying to install an app but the download keeps failing - without the image, " +
            "your application cannot start.",

        sreExplanation: "ImagePullBackOff indicates the kubelet cannot pull the specified container image from the registry. " +
            "This could be due to authentication, network connectivity, or image availability issues.",

        impact: "**Business Impact:** High\n" +
            "• New deployments fail completely\n" +
            "• Cannot scale up to handle increased load\n" +
            "• Rollouts and updates blocked",

        urgency: "High - Blocks deployments and scaling",

        nextSteps: [
            "Verify image name and tag exist in registry",
            "Check ImagePullSecrets configuration",
            "Test registry connectivity from cluster",
            "Validate registry authentication credentials",
            "Review network policies affecting registry access"
        ],

        rootCause: "Image pull failures commonly caused by:\n" +
            "• Incorrect image name or tag\n" +
            "• Missing or expired registry credentials\n" +
            "• Network connectivity issues to registry\n" +
            "• ImagePullSecrets not properly configured\n" +
            "• Registry authentication or authorization problems",

        sreContext: "**SRE Perspective:**\n" +
            "• Debug: kubectl describe pod <pod-name> for exact error\n" +
            "• Verify: Image exists in registry and credentials are valid\n" +
            "• Check: ImagePullSecrets configuration\n" +
            "• Test: docker pull from cluster nodes if possible"
    };
}

function explainServiceUnreachable(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Other applications or users cannot connect to your service. " +
            "This is like having a phone number that goes nowhere - the service exists but traffic can't reach it.",

        sreExplanation: "Service networking failure preventing traffic from reaching healthy pods. " +
            "Could indicate selector mismatches, port configuration issues, or network policy blocks.",

        impact: "**Business Impact:** High\n" +
            "• API calls and service requests failing\n" +
            "• Microservices cannot communicate\n" +
            "• External API integrations failing\n" +
            "• Database connections timing out",

        urgency: "High - Service connectivity lost",

        nextSteps: [
            "Verify service selector matches pod labels",
            "Check port configurations and mappings",
            "Test service connectivity from within cluster",
            "Review NetworkPolicy configurations",
            "Validate LoadBalancer or Ingress setup"
        ],

        rootCause: "Service unreachability typically caused by:\n" +
            "• Service selector doesn't match pod labels\n" +
            "• Port mismatches between service and pods\n" +
            "• NetworkPolicy blocking traffic\n" +
            "• LoadBalancer provisioning failures\n" +
            "• Ingress configuration issues",

        sreContext: "**SRE Perspective:**\n" +
            "• Test: kubectl exec -it <pod> -- wget <service-name>:<port>\n" +
            "• Verify: Service endpoints with kubectl get endpoints\n" +
            "• Check: NetworkPolicy rules and ingress configuration\n" +
            "• Debug: Service discovery and DNS resolution"
    };
}

function explainResourceQuotaExceeded(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Your application is trying to use more resources than allowed. " +
            "This is like trying to park more cars than fit in a parking lot - there simply isn't enough space allocated.",

        sreExplanation: "Resource quota or limit range preventing pod scheduling or causing resource throttling. " +
            "The cluster or namespace has insufficient resources to meet the application's requirements.",

        impact: "**Business Impact:** Medium to High\n" +
            "• Performance degradation during peak load\n" +
            "• Cannot scale to handle traffic spikes\n" +
            "• Intermittent application crashes\n" +
            "• Unreliable user experience",

        urgency: "Medium - Performance and scaling impacted",

        nextSteps: [
            "Review current resource usage vs limits",
            "Check namespace resource quotas",
            "Monitor CPU and memory utilization patterns",
            "Consider increasing resource limits if justified",
            "Optimize application resource efficiency"
        ],

        rootCause: "Resource constraints typically caused by:\n" +
            "• Namespace ResourceQuota limits exceeded\n" +
            "• Pod resource requests too high for available capacity\n" +
            "• Memory or CPU intensive workloads\n" +
            "• Inadequate cluster capacity planning\n" +
            "• Resource leaks in application code",

        sreContext: "**SRE Perspective:**\n" +
            "• Monitor: Set up resource utilization alerts\n" +
            "• Immediate: Increase resource limits if cluster has capacity\n" +
            "• Investigate: Memory/CPU usage patterns over time\n" +
            "• Long-term: Application performance profiling and optimization"
    };
}

function explainConfigError(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Your application cannot start because of configuration problems. " +
            "This is like trying to start a car with the wrong key - the configuration doesn't match what's expected.",

        sreExplanation: "Configuration-related failure preventing pod startup or proper operation. " +
            "Could involve ConfigMaps, Secrets, environment variables, or YAML syntax issues.",

        impact: "**Business Impact:** High\n" +
            "• Application cannot start\n" +
            "• Deployment rollouts fail\n" +
            "• Configuration changes break existing functionality",

        urgency: "High - Application startup blocked",

        nextSteps: [
            "Validate YAML syntax and Kubernetes resource definitions",
            "Check ConfigMap and Secret references",
            "Verify environment variable configurations",
            "Review recent configuration changes",
            "Test configuration in development environment"
        ],

        rootCause: "Configuration errors commonly caused by:\n" +
            "• Invalid YAML syntax or structure\n" +
            "• Missing or incorrectly named ConfigMaps/Secrets\n" +
            "• Environment variable typos or missing values\n" +
            "• Resource reference errors\n" +
            "• Kubernetes API version compatibility issues",

        sreContext: "**SRE Perspective:**\n" +
            "• Debug: kubectl describe pod <pod> for detailed error messages\n" +
            "• Verify: All referenced ConfigMaps and Secrets exist\n" +
            "• Check: YAML syntax and Kubernetes resource validation\n" +
            "• Fix: Correct configuration and re-apply manifests"
    };
}

function explainNetworkPolicyBlock(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "Network security rules are preventing your application from communicating properly. " +
            "This is like having a firewall that's blocking legitimate traffic - the security is working, but too restrictively.",

        sreExplanation: "NetworkPolicy rules are blocking required network traffic between pods or to external services. " +
            "While this maintains security, it's preventing legitimate application communication.",

        impact: "**Business Impact:** Medium to High\n" +
            "• Inter-service communication failures\n" +
            "• Database connectivity issues\n" +
            "• API integration problems\n" +
            "• Microservices architecture disruption",

        urgency: "Medium - Communication pathways blocked",

        nextSteps: [
            "Review NetworkPolicy rules affecting the application",
            "Test network connectivity between services",
            "Validate DNS resolution within the cluster",
            "Check service mesh or ingress configurations",
            "Review firewall rules and security groups"
        ],

        rootCause: "Network connectivity issues typically caused by:\n" +
            "• Overly restrictive NetworkPolicy rules\n" +
            "• Service mesh configuration problems\n" +
            "• DNS resolution failures\n" +
            "• Firewall or security group misconfigurations\n" +
            "• Ingress controller routing issues",

        sreContext: "**SRE Perspective:**\n" +
            "• Debug: Network connectivity testing between affected pods\n" +
            "• Review: NetworkPolicy ingress/egress rules\n" +
            "• Check: Service discovery and DNS resolution\n" +
            "• Test: Direct pod-to-pod communication bypassing services"
    };
}

function explainNodeNotReady(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "One or more cluster nodes are having problems and can't run applications properly. " +
            "This is like having a server that's partially broken - it might still be running but can't handle work reliably.",

        sreExplanation: "Node in NotReady state cannot schedule new pods or may be experiencing kubelet issues. " +
            "This indicates infrastructure-level problems requiring immediate attention.",

        impact: "**Business Impact:** High\n" +
            "• Reduced cluster capacity\n" +
            "• Potential pod evictions\n" +
            "• Cannot schedule new workloads\n" +
            "• Risk of service degradation",

        urgency: "High - Infrastructure stability compromised",

        nextSteps: [
            "Check node status and recent events",
            "Investigate kubelet and container runtime health",
            "Review node resource utilization",
            "Check for disk space or memory issues",
            "Validate network connectivity to the node"
        ],

        rootCause: "Node issues commonly caused by:\n" +
            "• Kubelet service failures or crashes\n" +
            "• Container runtime (Docker/containerd) issues\n" +
            "• Network connectivity problems\n" +
            "• Disk space exhaustion\n" +
            "• Hardware or virtual machine problems",

        sreContext: "**SRE Perspective:**\n" +
            "• Emergency: Consider cordoning node to prevent new schedules\n" +
            "• Investigate: Node logs and system health\n" +
            "• Check: Kubelet status and container runtime health\n" +
            "• Monitor: Resource usage and hardware status"
    };
}

function explainGenericIssue(issue: KubernetesIssue): IssueExplanation {
    return {
        humanExplanation: "A Kubernetes resource is experiencing issues and needs attention. " +
            "This could affect the availability or performance of your application.",

        sreExplanation: "Issue type " + issue.type + " detected requiring investigation.",

        impact: "**Business Impact:** Varies by resource\n" +
            "• Resource health compromised\n" +
            "• May affect dependent services",

        urgency: "Review based on severity - Monitor and investigate",

        nextSteps: [
            "Review resource status and recent changes",
            "Check logs and events for additional context",
            "Investigate related resources and dependencies",
            "Follow standard troubleshooting procedures"
        ],

        rootCause: "Generic issue requiring detailed investigation:\n" +
            "• Check resource specifications and status\n" +
            "• Review recent configuration changes\n" +
            "• Analyze system logs and metrics\n" +
            "• Consider environmental factors",

        sreContext: "**SRE Perspective:**\n" +
            "• Manual investigation required for detailed diagnosis\n" +
            "• Gather logs, metrics, and recent change history\n" +
            "• Apply standard troubleshooting methodology"
    };
}