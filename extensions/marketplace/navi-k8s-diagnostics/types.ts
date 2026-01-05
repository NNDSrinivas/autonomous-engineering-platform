/**
 * Kubernetes Diagnostics Extension - Types and Interfaces
 * 
 * Defines types for Kubernetes resource inspection, issue classification,
 * and remediation proposals with NAVI extension context integration.
 */

export interface ExtensionContext {
    /** Kubernetes API interface */
    k8s: KubernetesAPI;

    /** Extension configuration */
    config: ExtensionConfig;

    /** Approval workflow interface */
    approval: ApprovalAPI;

    /** NAVI workspace interface */
    workspace: WorkspaceAPI;
}

export interface KubernetesAPI {
    /** List pods in namespace or all namespaces */
    listPods(namespace?: string): Promise<Pod[]>;

    /** List deployments in namespace or all namespaces */
    listDeployments(namespace?: string): Promise<Deployment[]>;

    /** List services in namespace or all namespaces */
    listServices(namespace?: string): Promise<Service[]>;

    /** Get events for resource or namespace */
    getEvents(namespace?: string, resourceName?: string): Promise<Event[]>;

    /** Get logs for pod */
    getLogs(podName: string, namespace: string, options?: LogOptions): Promise<string>;

    /** Get cluster info */
    getClusterInfo(): Promise<ClusterInfo>;
}

export interface Pod {
    metadata: {
        name: string;
        namespace: string;
        labels: Record<string, string>;
        annotations: Record<string, string>;
        creationTimestamp: string;
    };
    spec: {
        containers: Container[];
        restartPolicy: string;
        nodeName?: string;
    };
    status: {
        phase: 'Pending' | 'Running' | 'Succeeded' | 'Failed' | 'Unknown';
        conditions: Condition[];
        containerStatuses?: ContainerStatus[];
        podIP?: string;
    };
}

export interface Deployment {
    metadata: {
        name: string;
        namespace: string;
        labels: Record<string, string>;
    };
    spec: {
        replicas: number;
        selector: {
            matchLabels: Record<string, string>;
        };
    };
    status: {
        availableReplicas: number;
        readyReplicas: number;
        replicas: number;
        conditions: Condition[];
    };
}

export interface Service {
    metadata: {
        name: string;
        namespace: string;
    };
    spec: {
        type: 'ClusterIP' | 'NodePort' | 'LoadBalancer' | 'ExternalName';
        ports: ServicePort[];
        selector: Record<string, string>;
    };
    status?: {
        loadBalancer?: {
            ingress?: Array<{ ip?: string; hostname?: string }>;
        };
    };
}

export interface Container {
    name: string;
    image: string;
    resources?: {
        requests?: Record<string, string>;
        limits?: Record<string, string>;
    };
    env?: Array<{ name: string; value?: string; valueFrom?: any }>;
}

export interface ContainerStatus {
    name: string;
    ready: boolean;
    restartCount: number;
    state: {
        waiting?: { reason: string; message?: string };
        running?: { startedAt: string };
        terminated?: { exitCode: number; reason: string; message?: string };
    };
}

export interface Condition {
    type: string;
    status: 'True' | 'False' | 'Unknown';
    reason?: string;
    message?: string;
    lastTransitionTime: string;
}

export interface Event {
    metadata: {
        name: string;
        namespace: string;
    };
    involvedObject: {
        kind: string;
        name: string;
        namespace: string;
    };
    reason: string;
    message: string;
    type: 'Normal' | 'Warning';
    firstTimestamp: string;
    lastTimestamp: string;
    count: number;
}

export interface ServicePort {
    name?: string;
    port: number;
    targetPort: number | string;
    protocol: 'TCP' | 'UDP';
}

export interface LogOptions {
    tailLines?: number;
    sinceTime?: string;
    container?: string;
}

export interface ClusterInfo {
    version: string;
    nodeCount: number;
    namespaces: string[];
}

export interface ExtensionConfig {
    /** Maximum log lines to retrieve */
    maxLogLines: number;

    /** Confidence threshold for auto-remediation */
    autoRemedationThreshold: number;

    /** Namespaces to monitor */
    watchNamespaces: string[];
}

export interface ApprovalAPI {
    /** Request approval for proposed actions */
    requestApproval(proposal: RemediationProposal): Promise<ApprovalResult>;
}

export interface WorkspaceAPI {
    /** Read repository files */
    readFile(path: string): Promise<string>;

    /** Get workspace root */
    getRoot(): Promise<string>;
}

export interface ApprovalResult {
    approved: boolean;
    reason?: string;
    rollbackToken?: string;
}

// Issue Classification Types

export enum IssueType {
    CRASH_LOOP = 'CRASH_LOOP',
    DEPLOYMENT_DOWN = 'DEPLOYMENT_DOWN',
    SERVICE_UNREACHABLE = 'SERVICE_UNREACHABLE',
    RESOURCE_EXHAUSTION = 'RESOURCE_EXHAUSTION',
    RESOURCE_QUOTA_EXCEEDED = 'RESOURCE_QUOTA_EXCEEDED',
    IMAGE_PULL_ERROR = 'IMAGE_PULL_ERROR',
    NETWORK_POLICY_BLOCK = 'NETWORK_POLICY_BLOCK',
    CONFIG_ERROR = 'CONFIG_ERROR',
    NODE_NOT_READY = 'NODE_NOT_READY',
    RBAC_DENIAL = 'RBAC_DENIAL',
    NO_ISSUES = 'NO_ISSUES'
}

export enum IssueSeverity {
    CRITICAL = 'CRITICAL',
    HIGH = 'HIGH',
    MEDIUM = 'MEDIUM',
    LOW = 'LOW'
}

export interface KubernetesIssue {
    type: IssueType;
    severity: IssueSeverity;
    resource: {
        kind: string;
        name: string;
        namespace: string;
    };
    description: string;
    symptoms: string[];
    affectedPods?: Pod[];
    affectedDeployments?: Deployment[];
    affectedServices?: Service[];
    relatedEvents: Event[];
    confidence: number;
}

export interface IssueExplanation {
    summary: string;
    details: string[];
    rootCause: string;
    impact: string;
    sreContext: string;
}

export interface RemediationProposal {
    requiresApproval: boolean;
    actions: RemediationAction[];
    confidence: number;
    estimatedDowntime: string;
    rollbackInstructions: string[];
    approvalReason?: string;
}

export interface RemediationAction {
    type: 'INVESTIGATE' | 'RESTART' | 'SCALE' | 'UPDATE_CONFIG' | 'DELETE' | 'APPLY_MANIFEST';
    description: string;
    command?: string;
    resource?: {
        kind: string;
        name: string;
        namespace: string;
    };
    safe: boolean;
    reversible: boolean;
}

export interface DiagnosticsResult {
    issues: KubernetesIssue[];
    clusterOverview: {
        totalPods: number;
        healthyPods: number;
        totalDeployments: number;
        healthyDeployments: number;
        totalServices: number;
    };
    recommendations: string[];
    requiresApproval: boolean;
    summary: string;
    nextSteps: RemediationProposal[];
}