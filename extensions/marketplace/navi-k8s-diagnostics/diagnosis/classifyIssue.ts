/**
 * Kubernetes Issue Classification Module
 * 
 * Classifies Kubernetes issues based on observable symptoms from pods, deployments,
 * services, events, and logs. Provides deterministic issue identification.
 */

import {
    KubernetesIssue,
    IssueType,
    IssueSeverity,
    Pod,
    Deployment,
    Service,
    Event,
    ExtensionContext
} from '../types';

export interface DiagnosticData {
    pods: Pod[];
    deployments: Deployment[];
    services: Service[];
    events: Event[];
    clusterInfo?: {
        nodeCount: number;
        version: string;
        namespaces: string[];
    };
}

export function classifyIssues(ctx: ExtensionContext, data: DiagnosticData): KubernetesIssue[] {
    const issues: KubernetesIssue[] = [];

    // Analyze pods for issues
    for (const pod of data.pods) {
        const podIssues = analyzePodIssues(pod, data.events);
        issues.push(...podIssues);
    }

    // Analyze deployments for issues
    for (const deployment of data.deployments) {
        const deploymentIssues = analyzeDeploymentIssues(deployment, data.pods, data.events);
        issues.push(...deploymentIssues);
    }

    // Analyze services for issues
    for (const service of data.services) {
        const serviceIssues = analyzeServiceIssues(service, data.pods);
        issues.push(...serviceIssues);
    }

    // Analyze cluster-wide patterns
    const clusterIssues = analyzeClusterPatterns(data);
    issues.push(...clusterIssues);

    // Sort by severity and confidence
    return issues.sort((a, b) => {
        const severityOrder = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
        const severityDiff = severityOrder[b.severity] - severityOrder[a.severity];
        if (severityDiff !== 0) return severityDiff;
        return b.confidence - a.confidence;
    });
}

function analyzePodIssues(pod: Pod, events: Event[]): KubernetesIssue[] {
    const issues: KubernetesIssue[] = [];
    const podEvents = events.filter(e =>
        e.involvedObject.kind === 'Pod' && e.involvedObject.name === pod.metadata.name
    );

    // CrashLoopBackOff detection
    if (pod.status.containerStatuses) {
        for (const container of pod.status.containerStatuses) {
            if (container.state.waiting?.reason === 'CrashLoopBackOff') {
                issues.push({
                    type: IssueType.CRASH_LOOP,
                    severity: IssueSeverity.CRITICAL,
                    resource: {
                        kind: 'Pod',
                        name: pod.metadata.name,
                        namespace: pod.metadata.namespace
                    },
                    description: `Container ${container.name} is in CrashLoopBackOff`,
                    symptoms: [
                        `Pod phase: ${pod.status.phase}`,
                        `Container restart count: ${container.restartCount}`,
                        `Container state: ${container.state.waiting?.reason}`,
                        `Container ready: ${container.ready}`
                    ],
                    affectedPods: [pod],
                    relatedEvents: podEvents,
                    confidence: 0.95
                });
            }

            // Image pull errors
            if (container.state.waiting?.reason === 'ImagePullBackOff' ||
                container.state.waiting?.reason === 'ErrImagePull') {
                issues.push({
                    type: IssueType.IMAGE_PULL_ERROR,
                    severity: IssueSeverity.HIGH,
                    resource: {
                        kind: 'Pod',
                        name: pod.metadata.name,
                        namespace: pod.metadata.namespace
                    },
                    description: `Cannot pull image for container ${container.name}`,
                    symptoms: [
                        `Container state: ${container.state.waiting?.reason}`,
                        `Wait message: ${container.state.waiting?.message}`,
                        `Restart count: ${container.restartCount}`
                    ],
                    affectedPods: [pod],
                    relatedEvents: podEvents.filter(e => e.reason.includes('Pull')),
                    confidence: 0.90
                });
            }

            // Configuration errors
            if (container.state.waiting?.reason === 'CreateContainerConfigError') {
                issues.push({
                    type: IssueType.CONFIG_ERROR,
                    severity: IssueSeverity.HIGH,
                    resource: {
                        kind: 'Pod',
                        name: pod.metadata.name,
                        namespace: pod.metadata.namespace
                    },
                    description: `Configuration error for container ${container.name}`,
                    symptoms: [
                        `Container state: ${container.state.waiting?.reason}`,
                        `Configuration message: ${container.state.waiting?.message}`
                    ],
                    affectedPods: [pod],
                    relatedEvents: podEvents,
                    confidence: 0.85
                });
            }
        }
    }

    // Resource exhaustion detection
    const oomEvents = podEvents.filter(e =>
        e.reason === 'OOMKilled' || e.message.includes('out of memory')
    );

    if (oomEvents.length > 0) {
        issues.push({
            type: IssueType.RESOURCE_EXHAUSTION,
            severity: IssueSeverity.HIGH,
            resource: {
                kind: 'Pod',
                name: pod.metadata.name,
                namespace: pod.metadata.namespace
            },
            description: `Pod ${pod.metadata.name} is experiencing memory exhaustion`,
            symptoms: [
                `OOM events: ${oomEvents.length}`,
                `Pod phase: ${pod.status.phase}`,
                `Memory limits: ${JSON.stringify(pod.spec.containers.map(c => c.resources?.limits?.memory))}`
            ],
            affectedPods: [pod],
            relatedEvents: oomEvents,
            confidence: 0.90
        });
    }

    // RBAC/Permission issues
    const rbacEvents = podEvents.filter(e =>
        e.reason.includes('Forbid') || e.message.includes('forbidden') ||
        e.message.includes('unauthorized') || e.message.includes('RBAC')
    );

    if (rbacEvents.length > 0) {
        issues.push({
            type: IssueType.RBAC_DENIAL,
            severity: IssueSeverity.MEDIUM,
            resource: {
                kind: 'Pod',
                name: pod.metadata.name,
                namespace: pod.metadata.namespace
            },
            description: `Pod ${pod.metadata.name} has RBAC/permission issues`,
            symptoms: [
                `RBAC events: ${rbacEvents.length}`,
                `Events: ${rbacEvents.map(e => e.message).join('; ')}`
            ],
            affectedPods: [pod],
            relatedEvents: rbacEvents,
            confidence: 0.80
        });
    }

    return issues;
}

function analyzeDeploymentIssues(
    deployment: Deployment,
    pods: Pod[],
    events: Event[]
): KubernetesIssue[] {
    const issues: KubernetesIssue[] = [];
    const deploymentEvents = events.filter(e =>
        e.involvedObject.kind === 'Deployment' && e.involvedObject.name === deployment.metadata.name
    );

    const deploymentPods = pods.filter(pod =>
        pod.metadata.namespace === deployment.metadata.namespace &&
        matchesSelector(pod.metadata.labels, deployment.spec.selector.matchLabels)
    );

    // Deployment completely down
    if (deployment.status.availableReplicas === 0 && deployment.spec.replicas > 0) {
        issues.push({
            type: IssueType.DEPLOYMENT_DOWN,
            severity: IssueSeverity.CRITICAL,
            resource: {
                kind: 'Deployment',
                name: deployment.metadata.name,
                namespace: deployment.metadata.namespace
            },
            description: `Deployment ${deployment.metadata.name} has no available replicas`,
            symptoms: [
                `Target replicas: ${deployment.spec.replicas}`,
                `Available replicas: ${deployment.status.availableReplicas}`,
                `Ready replicas: ${deployment.status.readyReplicas}`,
                `Total pods: ${deploymentPods.length}`
            ],
            affectedPods: deploymentPods,
            affectedDeployments: [deployment],
            relatedEvents: deploymentEvents,
            confidence: 0.95
        });
    }

    // Partial deployment failure
    else if (deployment.status.readyReplicas < deployment.spec.replicas * 0.5) {
        const missingReplicas = deployment.spec.replicas - deployment.status.readyReplicas;

        issues.push({
            type: IssueType.DEPLOYMENT_DOWN,
            severity: IssueSeverity.HIGH,
            resource: {
                kind: 'Deployment',
                name: deployment.metadata.name,
                namespace: deployment.metadata.namespace
            },
            description: `Deployment ${deployment.metadata.name} is severely degraded`,
            symptoms: [
                `Target replicas: ${deployment.spec.replicas}`,
                `Ready replicas: ${deployment.status.readyReplicas}`,
                `Missing replicas: ${missingReplicas}`,
                `Availability: ${Math.round((deployment.status.readyReplicas / deployment.spec.replicas) * 100)}%`
            ],
            affectedPods: deploymentPods,
            affectedDeployments: [deployment],
            relatedEvents: deploymentEvents,
            confidence: 0.90
        });
    }

    return issues;
}

function analyzeServiceIssues(service: Service, pods: Pod[]): KubernetesIssue[] {
    const issues: KubernetesIssue[] = [];

    // LoadBalancer without external IP
    if (service.spec.type === 'LoadBalancer') {
        const hasExternalAccess = service.status?.loadBalancer?.ingress?.some(
            ingress => ingress.ip || ingress.hostname
        );

        if (!hasExternalAccess) {
            issues.push({
                type: IssueType.SERVICE_UNREACHABLE,
                severity: IssueSeverity.HIGH,
                resource: {
                    kind: 'Service',
                    name: service.metadata.name,
                    namespace: service.metadata.namespace
                },
                description: `LoadBalancer service ${service.metadata.name} has no external IP`,
                symptoms: [
                    `Service type: ${service.spec.type}`,
                    `LoadBalancer status: ${JSON.stringify(service.status?.loadBalancer)}`,
                    `Ports: ${service.spec.ports.map(p => `${p.port}:${p.targetPort}`).join(', ')}`
                ],
                affectedServices: [service],
                relatedEvents: [],
                confidence: 0.85
            });
        }
    }

    // Service with no backing pods
    if (service.spec.selector && Object.keys(service.spec.selector).length > 0) {
        const backingPods = pods.filter(pod =>
            pod.metadata.namespace === service.metadata.namespace &&
            matchesSelector(pod.metadata.labels, service.spec.selector)
        );

        const readyPods = backingPods.filter(pod =>
            pod.status.phase === 'Running' &&
            pod.status.containerStatuses?.every(cs => cs.ready)
        );

        if (readyPods.length === 0) {
            issues.push({
                type: IssueType.SERVICE_UNREACHABLE,
                severity: backingPods.length === 0 ? IssueSeverity.CRITICAL : IssueSeverity.HIGH,
                resource: {
                    kind: 'Service',
                    name: service.metadata.name,
                    namespace: service.metadata.namespace
                },
                description: `Service ${service.metadata.name} has no ready backing pods`,
                symptoms: [
                    `Selector: ${JSON.stringify(service.spec.selector)}`,
                    `Total matching pods: ${backingPods.length}`,
                    `Ready pods: ${readyPods.length}`,
                    `Service ports: ${service.spec.ports.length}`
                ],
                affectedServices: [service],
                affectedPods: backingPods,
                relatedEvents: [],
                confidence: 0.90
            });
        }
    }

    return issues;
}

function analyzeClusterPatterns(data: DiagnosticData): KubernetesIssue[] {
    const issues: KubernetesIssue[] = [];

    // High frequency crash loops across multiple pods
    const crashLoopPods = data.pods.filter(pod =>
        pod.status.containerStatuses?.some(cs => cs.state.waiting?.reason === 'CrashLoopBackOff')
    );

    if (crashLoopPods.length >= 3) {
        issues.push({
            type: IssueType.CRASH_LOOP,
            severity: IssueSeverity.CRITICAL,
            resource: {
                kind: 'Cluster',
                name: 'multiple-pods',
                namespace: 'cluster-wide'
            },
            description: `Cluster-wide crash loop affecting ${crashLoopPods.length} pods`,
            symptoms: [
                `Affected pods: ${crashLoopPods.length}`,
                `Namespaces: ${[...new Set(crashLoopPods.map(p => p.metadata.namespace))].join(', ')}`,
                `Pattern suggests system-wide issue`
            ],
            affectedPods: crashLoopPods,
            relatedEvents: data.events.filter(e => e.reason === 'BackOff'),
            confidence: 0.80
        });
    }

    // Network policy blocks (inferred from connection patterns)
    const networkEvents = data.events.filter(e =>
        e.message.includes('network') || e.message.includes('connection refused') ||
        e.message.includes('timeout')
    );

    if (networkEvents.length >= 5) {
        const affectedNamespaces = [...new Set(networkEvents.map(e => e.metadata.namespace))];

        issues.push({
            type: IssueType.NETWORK_POLICY_BLOCK,
            severity: IssueSeverity.MEDIUM,
            resource: {
                kind: 'Cluster',
                name: 'network-connectivity',
                namespace: 'cluster-wide'
            },
            description: `Potential network connectivity issues affecting ${affectedNamespaces.length} namespaces`,
            symptoms: [
                `Network-related events: ${networkEvents.length}`,
                `Affected namespaces: ${affectedNamespaces.join(', ')}`,
                `Common patterns: connection refused, timeouts`
            ],
            relatedEvents: networkEvents,
            confidence: 0.70
        });
    }

    return issues;
}

function matchesSelector(labels: Record<string, string>, selector: Record<string, string>): boolean {
    for (const [key, value] of Object.entries(selector)) {
        if (labels[key] !== value) {
            return false;
        }
    }
    return true;
}