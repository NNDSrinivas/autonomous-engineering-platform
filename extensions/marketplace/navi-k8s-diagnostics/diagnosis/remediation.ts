/**
 * Kubernetes Remediation Proposal Module
 * 
 * Generates safe, approval-gated remediation proposals for Kubernetes issues.
 * ALL destructive operations require approval. Read-only investigations are auto-approved.
 */

import {
    KubernetesIssue,
    RemediationProposal,
    RemediationAction,
    IssueType,
    ExtensionContext
} from '../types';

export function proposeRemediation(ctx: ExtensionContext, issue: KubernetesIssue): RemediationProposal {
    switch (issue.type) {
        case IssueType.CRASH_LOOP:
            return proposeCrashLoopRemediation(issue);
        case IssueType.DEPLOYMENT_DOWN:
            return proposeDeploymentDownRemediation(issue);
        case IssueType.SERVICE_UNREACHABLE:
            return proposeServiceUnreachableRemediation(issue);
        case IssueType.RESOURCE_EXHAUSTION:
            return proposeResourceExhaustionRemediation(issue);
        case IssueType.IMAGE_PULL_ERROR:
            return proposeImagePullErrorRemediation(issue);
        case IssueType.NETWORK_POLICY_BLOCK:
            return proposeNetworkPolicyBlockRemediation(issue);
        case IssueType.CONFIG_ERROR:
            return proposeConfigErrorRemediation(issue);
        case IssueType.RBAC_DENIAL:
            return proposeRBACDenialRemediation(issue);
        default:
            return proposeGenericRemediation(issue);
    }
}

function proposeCrashLoopRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const podName = issue.resource.name;
    const namespace = issue.resource.namespace;

    // Investigation actions (no approval required)
    actions.push({
        type: 'INVESTIGATE',
        description: `Check container logs for crash details`,
        command: `kubectl logs ${podName} -n ${namespace} --previous --tail=100`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Describe pod to see events and configuration`,
        command: `kubectl describe pod ${podName} -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check pod resource usage and limits`,
        command: `kubectl top pod ${podName} -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    // Remediation actions (require approval)
    if (issue.confidence > 0.8) {
        actions.push({
            type: 'DELETE',
            description: `Delete stuck pod to trigger fresh restart`,
            command: `kubectl delete pod ${podName} -n ${namespace}`,
            resource: issue.resource,
            safe: false,
            reversible: true // Deployment will recreate
        });
    }

    return {
        requiresApproval: true,
        actions,
        confidence: issue.confidence,
        estimatedDowntime: "2-5 minutes (pod recreation time)",
        rollbackInstructions: [
            "Deployment will automatically recreate deleted pods",
            "If issue persists, rollback deployment to previous version:",
            `kubectl rollout undo deployment <deployment-name> -n ${namespace}`
        ],
        approvalReason: `Crash loop detected with ${Math.round(issue.confidence * 100)}% confidence. ` +
            "Pod restart recommended to clear stuck state, but may not fix underlying issue."
    };
}

function proposeDeploymentDownRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const deploymentName = issue.resource.name;
    const namespace = issue.resource.namespace;

    // Investigation first
    actions.push({
        type: 'INVESTIGATE',
        description: `Check deployment status and events`,
        command: `kubectl describe deployment ${deploymentName} -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check pods created by this deployment`,
        command: `kubectl get pods -n ${namespace} -l app=${deploymentName} -o wide`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check deployment rollout status`,
        command: `kubectl rollout status deployment/${deploymentName} -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    // Remediation actions
    actions.push({
        type: 'RESTART',
        description: `Restart deployment to retry pod creation`,
        command: `kubectl rollout restart deployment/${deploymentName} -n ${namespace}`,
        resource: issue.resource,
        safe: false,
        reversible: true
    });

    // Only suggest scaling if confidence is high and we suspect resource constraints
    if (issue.symptoms.some(s => s.includes('resource') || s.includes('capacity'))) {
        actions.push({
            type: 'SCALE',
            description: `Temporarily scale down to reduce resource pressure`,
            command: `kubectl scale deployment/${deploymentName} --replicas=1 -n ${namespace}`,
            resource: issue.resource,
            safe: false,
            reversible: true
        });
    }

    return {
        requiresApproval: true,
        actions,
        confidence: issue.confidence,
        estimatedDowntime: "3-10 minutes (deployment restart time)",
        rollbackInstructions: [
            `Check previous replica count: kubectl get deployment ${deploymentName} -n ${namespace}`,
            `Restore previous scale: kubectl scale deployment/${deploymentName} --replicas=<previous-count> -n ${namespace}`,
            `Rollback if needed: kubectl rollout undo deployment/${deploymentName} -n ${namespace}`
        ],
        approvalReason: `Deployment ${deploymentName} has insufficient replicas. ` +
            "Restart may resolve temporary issues but requires approval for service disruption."
    };
}

function proposeServiceUnreachableRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const serviceName = issue.resource.name;
    const namespace = issue.resource.namespace;

    // Investigation actions
    actions.push({
        type: 'INVESTIGATE',
        description: `Check service endpoints and backing pods`,
        command: `kubectl get endpoints ${serviceName} -n ${namespace} -o yaml`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Verify service configuration`,
        command: `kubectl describe service ${serviceName} -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check pods matching service selector`,
        command: `kubectl get pods -n ${namespace} --show-labels | grep <service-selector>`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    // For LoadBalancer services, check cloud provider status
    if (issue.symptoms.some(s => s.includes('LoadBalancer'))) {
        actions.push({
            type: 'INVESTIGATE',
            description: `Check LoadBalancer provisioning status`,
            command: `kubectl get service ${serviceName} -n ${namespace} -o yaml`,
            resource: issue.resource,
            safe: true,
            reversible: true
        });

        // Only suggest recreation for stuck LoadBalancers with high confidence
        if (issue.confidence > 0.8) {
            actions.push({
                type: 'DELETE',
                description: `Recreate LoadBalancer service (DESTRUCTIVE - will change external IP)`,
                command: `kubectl delete service ${serviceName} -n ${namespace}`,
                resource: issue.resource,
                safe: false,
                reversible: false // External IP will change
            });
        }
    }

    return {
        requiresApproval: issue.symptoms.some(s => s.includes('LoadBalancer')), // Only if potentially destructive
        actions,
        confidence: issue.confidence,
        estimatedDowntime: issue.symptoms.some(s => s.includes('LoadBalancer')) ?
            "5-15 minutes (LoadBalancer provisioning)" : "1-2 minutes",
        rollbackInstructions: [
            "Service configuration can be restored from git/backup",
            "LoadBalancer external IP will change if service is recreated",
            "Update DNS records if external IP changes"
        ],
        approvalReason: issue.symptoms.some(s => s.includes('LoadBalancer')) ?
            "LoadBalancer service recreation will change external IP address" :
            "Service investigation only - no destructive actions"
    };
}

function proposeResourceExhaustionRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const podName = issue.resource.name;
    const namespace = issue.resource.namespace;

    // Investigation actions
    actions.push({
        type: 'INVESTIGATE',
        description: `Check current resource usage`,
        command: `kubectl top pod ${podName} -n ${namespace} --containers`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check resource limits and requests`,
        command: `kubectl describe pod ${podName} -n ${namespace} | grep -A 10 "Limits\\|Requests"`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check node resource availability`,
        command: `kubectl describe node $(kubectl get pod ${podName} -n ${namespace} -o jsonpath='{.spec.nodeName}')`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    // Immediate remediation - restart pod to clear memory leaks
    actions.push({
        type: 'DELETE',
        description: `Restart pod to clear potential memory leaks (temporary fix)`,
        command: `kubectl delete pod ${podName} -n ${namespace}`,
        resource: issue.resource,
        safe: false,
        reversible: true
    });

    return {
        requiresApproval: true,
        actions,
        confidence: issue.confidence,
        estimatedDowntime: "2-5 minutes (pod restart)",
        rollbackInstructions: [
            "Pod will be automatically recreated by deployment",
            "Resource limits can be adjusted in deployment spec if needed",
            "Monitor resource usage after restart to confirm fix"
        ],
        approvalReason: "Resource exhaustion detected. Pod restart may provide temporary relief but " +
            "underlying resource limits or application issues need investigation."
    };
}

function proposeImagePullErrorRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const namespace = issue.resource.namespace;

    // Investigation actions
    actions.push({
        type: 'INVESTIGATE',
        description: `Check image pull secrets configuration`,
        command: `kubectl get secrets -n ${namespace} -o yaml | grep -A 5 "kubernetes.io/dockerconfigjson"`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Verify image exists in registry`,
        command: `kubectl describe pod <pod-name> -n ${namespace} | grep "Failed to pull image"`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check deployment image configuration`,
        command: `kubectl get deployment -n ${namespace} -o jsonpath='{.spec.template.spec.containers[*].image}'`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    return {
        requiresApproval: false, // Only investigation
        actions,
        confidence: issue.confidence,
        estimatedDowntime: "Investigation only - no service impact",
        rollbackInstructions: [
            "No changes made - investigation only",
            "If image/tag needs correction, update deployment spec",
            "If credentials needed, create/update image pull secrets"
        ],
        approvalReason: "Image pull investigation only - no modifications to cluster resources"
    };
}

function proposeNetworkPolicyBlockRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];

    // Investigation actions
    actions.push({
        type: 'INVESTIGATE',
        description: `List all network policies in cluster`,
        command: `kubectl get networkpolicies --all-namespaces -o wide`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Test pod-to-pod connectivity`,
        command: `kubectl run netshoot --image=nicolaka/netshoot -it --rm -- /bin/bash`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check DNS resolution`,
        command: `kubectl run dnsutils --image=tutum/dnsutils -it --rm -- nslookup kubernetes.default`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    return {
        requiresApproval: false, // Investigation only
        actions,
        confidence: issue.confidence * 0.7, // Network issues are complex
        estimatedDowntime: "Investigation only - no service impact",
        rollbackInstructions: [
            "Investigation only - no changes made",
            "Network policy changes require careful planning",
            "Consult security team before modifying network policies"
        ],
        approvalReason: "Network connectivity investigation - complex troubleshooting required"
    };
}

function proposeConfigErrorRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const podName = issue.resource.name;
    const namespace = issue.resource.namespace;

    // Investigation actions
    actions.push({
        type: 'INVESTIGATE',
        description: `Check pod configuration details`,
        command: `kubectl describe pod ${podName} -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Verify ConfigMaps and Secrets exist`,
        command: `kubectl get configmaps,secrets -n ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `Check deployment YAML for syntax errors`,
        command: `kubectl get deployment -n ${namespace} -o yaml | kubectl apply --dry-run=client -f -`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    return {
        requiresApproval: false,
        actions,
        confidence: issue.confidence,
        estimatedDowntime: "Investigation only",
        rollbackInstructions: [
            "Configuration investigation only",
            "Fix configuration issues in deployment spec",
            "Re-apply corrected manifests"
        ],
        approvalReason: "Configuration validation - no cluster modifications"
    };
}

function proposeRBACDenialRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];
    const namespace = issue.resource.namespace;

    // Investigation actions
    actions.push({
        type: 'INVESTIGATE',
        description: `Check ServiceAccount permissions`,
        command: `kubectl auth can-i --list --as=system:serviceaccount:${namespace}:default`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    actions.push({
        type: 'INVESTIGATE',
        description: `List RoleBindings and ClusterRoleBindings`,
        command: `kubectl get rolebindings,clusterrolebindings -A | grep ${namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    return {
        requiresApproval: false,
        actions,
        confidence: issue.confidence,
        estimatedDowntime: "Investigation only",
        rollbackInstructions: [
            "RBAC investigation only - no permissions modified",
            "Consult security team before granting additional permissions",
            "Follow principle of least privilege"
        ],
        approvalReason: "RBAC analysis - security review required for permission changes"
    };
}

function proposeGenericRemediation(issue: KubernetesIssue): RemediationProposal {
    const actions: RemediationAction[] = [];

    actions.push({
        type: 'INVESTIGATE',
        description: `Investigate ${issue.resource.kind} ${issue.resource.name}`,
        command: `kubectl describe ${issue.resource.kind.toLowerCase()} ${issue.resource.name} -n ${issue.resource.namespace}`,
        resource: issue.resource,
        safe: true,
        reversible: true
    });

    return {
        requiresApproval: false,
        actions,
        confidence: issue.confidence * 0.5, // Low confidence for generic issues
        estimatedDowntime: "Investigation only",
        rollbackInstructions: [
            "Manual investigation required",
            "No automated remediation available for this issue type"
        ],
        approvalReason: "Generic issue requiring manual analysis"
    };
}