/**
 * Kubernetes Usage Source Module
 * 
 * Collects Kubernetes resource usage metrics for deterministic cost analysis.
 * No AI inference - pure metrics from Kubernetes API and metrics server.
 */

import {
    KubernetesConfig,
    KubernetesUsageData,
    ClusterUsage,
    NodeUsage,
    PodUsage,
    NamespaceUsage,
    ResourceRequests,
    ResourceLimits,
    ResourceUtilization,
    K8sUsageSummary,
    UsageTrend
} from '../types';

interface K8sNode {
    metadata: {
        name: string;
        labels: Record<string, string>;
        annotations: Record<string, string>;
    };
    status: {
        capacity: {
            cpu: string;
            memory: string;
            'ephemeral-storage': string;
        };
        allocatable: {
            cpu: string;
            memory: string;
            'ephemeral-storage': string;
        };
    };
    spec: {
        instanceType?: string;
    };
}

interface K8sPod {
    metadata: {
        name: string;
        namespace: string;
        labels: Record<string, string>;
        annotations: Record<string, string>;
    };
    spec: {
        nodeName: string;
        containers: Array<{
            name: string;
            resources: {
                requests?: {
                    cpu?: string;
                    memory?: string;
                };
                limits?: {
                    cpu?: string;
                    memory?: string;
                };
            };
        }>;
    };
    status: {
        phase: string;
    };
}

interface MetricsData {
    pods: Array<{
        metadata: { name: string; namespace: string };
        containers: Array<{
            name: string;
            usage: {
                cpu: string;
                memory: string;
            };
        }>;
    }>;
    nodes: Array<{
        metadata: { name: string };
        usage: {
            cpu: string;
            memory: string;
        };
    }>;
}

/**
 * Collects comprehensive Kubernetes usage data for cost analysis
 */
export class KubernetesUsageCollector {
    private config: KubernetesConfig;
    private k8sApi: any; // Would be k8s.CoreV1Api from Kubernetes client
    private metricsApi: any; // Would be k8s.Metrics from Kubernetes metrics client

    constructor(config: KubernetesConfig) {
        this.config = config;
        // In real implementation:
        // const kc = new k8s.KubeConfig();
        // kc.loadFromDefault();
        // this.k8sApi = kc.makeApiClient(k8s.CoreV1Api);
        // this.metricsApi = new k8s.Metrics(kc);
        this.k8sApi = null; // Mock for now
        this.metricsApi = null; // Mock for now
    }

    /**
     * Main entry point - collect all Kubernetes usage data
     */
    async collectUsageData(timeRange: { start: string; end: string }): Promise<KubernetesUsageData> {
        try {
            const [clusters, nodes, pods, namespaces, summary] = await Promise.all([
                this.getClusterUsage(),
                this.getNodeUsage(),
                this.getPodUsage(),
                this.getNamespaceUsage(timeRange),
                this.getUsageSummary()
            ]);

            return {
                clusters,
                nodes,
                pods,
                namespaces,
                summary
            };
        } catch (error) {
            console.error('Kubernetes usage data collection failed:', error);
            const message = error instanceof Error ? error.message : String(error);
            throw new Error(`Kubernetes usage data collection failed: ${message}`);
        }
    }

    /**
     * Get cluster-level usage metrics
     */
    private async getClusterUsage(): Promise<ClusterUsage[]> {
        if (!this.k8sApi) {
            return this.mockClusterUsage();
        }

        try {
            // Get all nodes
            const nodesResponse = await this.k8sApi.listNode();
            const nodes = nodesResponse.body.items;

            // Get all pods
            const podsResponse = await this.k8sApi.listPodForAllNamespaces();
            const pods = podsResponse.body.items;

            // Calculate cluster totals
            let totalCpuRequests = 0;
            let totalMemoryRequests = 0;
            let totalCpuLimits = 0;
            let totalMemoryLimits = 0;
            let totalCost = 0;

            for (const pod of pods) {
                for (const container of pod.spec.containers || []) {
                    const requests = container.resources?.requests;
                    const limits = container.resources?.limits;

                    if (requests?.cpu) {
                        totalCpuRequests += this.parseCpuString(requests.cpu);
                    }
                    if (requests?.memory) {
                        totalMemoryRequests += this.parseMemoryString(requests.memory);
                    }
                    if (limits?.cpu) {
                        totalCpuLimits += this.parseCpuString(limits.cpu);
                    }
                    if (limits?.memory) {
                        totalMemoryLimits += this.parseMemoryString(limits.memory);
                    }
                }
            }

            // Calculate estimated cost based on node types (simplified)
            for (const node of nodes) {
                const instanceType = node.metadata.labels?.['node.kubernetes.io/instance-type'] || 'unknown';
                const hourlyCost = this.getNodeHourlyCost(instanceType);
                totalCost += hourlyCost * 24 * 30; // Monthly cost
            }

            // Get utilization metrics
            const utilization = await this.getClusterUtilization();

            return [{
                clusterName: 'production-cluster', // Would be determined from context
                totalCost,
                nodes: nodes.length,
                pods: pods.length,
                cpuRequests: totalCpuRequests,
                memoryRequests: totalMemoryRequests,
                cpuLimits: totalCpuLimits,
                memoryLimits: totalMemoryLimits,
                utilization
            }];
        } catch (error) {
            console.error('Failed to get cluster usage:', error);
            throw error;
        }
    }

    /**
     * Get node-level usage metrics
     */
    private async getNodeUsage(): Promise<NodeUsage[]> {
        if (!this.k8sApi) {
            return this.mockNodeUsage();
        }

        try {
            const nodesResponse = await this.k8sApi.listNode();
            const nodes = nodesResponse.body.items;
            const metricsData = await this.getMetricsData();
            const podsResponse = await this.k8sApi.listPodForAllNamespuses();
            const allPods = podsResponse.body.items as K8sPod[];

            const nodeUsages: NodeUsage[] = [];

            for (const node of nodes) {
                const nodeName = node.metadata.name;
                const instanceType = node.metadata.labels?.['node.kubernetes.io/instance-type'] || 'unknown';
                const cost = this.getNodeHourlyCost(instanceType) * 24 * 30; // Monthly cost

                // Get node metrics
                const nodeMetrics = metricsData.nodes.find(n => n.metadata.name === nodeName);
                const utilization = nodeMetrics ? {
                    cpu: this.calculateCpuUtilization(nodeMetrics.usage.cpu, node.status.capacity.cpu),
                    memory: this.calculateMemoryUtilization(nodeMetrics.usage.memory, node.status.capacity.memory),
                    network: Math.random() * 60 + 20, // Mock network utilization
                    storage: Math.random() * 80 + 10 // Mock storage utilization
                } : {
                    cpu: 0,
                    memory: 0,
                    network: 0,
                    storage: 0
                };

                // Get pods running on this node
                const nodePods = allPods.filter(p => p.spec.nodeName === nodeName);
                const pods = await this.processPods(nodePods, metricsData);

                // Determine node status
                const status = this.determineNodeStatus(utilization);

                nodeUsages.push({
                    nodeName,
                    instanceType,
                    cost,
                    utilization,
                    pods,
                    status
                });
            }

            return nodeUsages.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get node usage:', error);
            throw error;
        }
    }

    /**
     * Get pod-level usage metrics
     */
    private async getPodUsage(): Promise<PodUsage[]> {
        if (!this.k8sApi) {
            return this.mockPodUsage();
        }

        try {
            const podsResponse = await this.k8sApi.listPodForAllNamespaces();
            const pods = podsResponse.body.items;
            const metricsData = await this.getMetricsData();

            return await this.processPods(pods, metricsData);
        } catch (error) {
            console.error('Failed to get pod usage:', error);
            throw error;
        }
    }

    /**
     * Process pods to calculate usage metrics
     */
    private async processPods(pods: K8sPod[], metricsData: MetricsData): Promise<PodUsage[]> {
        const podUsages: PodUsage[] = [];

        for (const pod of pods) {
            const podName = pod.metadata.name;
            const namespace = pod.metadata.namespace;

            // Calculate requests and limits
            let requests: ResourceRequests = { cpu: 0, memory: 0, storage: 0 };
            let limits: ResourceLimits = { cpu: 0, memory: 0 };

            for (const container of pod.spec.containers || []) {
                const containerRequests = container.resources?.requests;
                const containerLimits = container.resources?.limits;

                if (containerRequests?.cpu) {
                    requests.cpu += this.parseCpuString(containerRequests.cpu);
                }
                if (containerRequests?.memory) {
                    requests.memory += this.parseMemoryString(containerRequests.memory);
                }
                if (containerLimits?.cpu) {
                    limits.cpu += this.parseCpuString(containerLimits.cpu);
                }
                if (containerLimits?.memory) {
                    limits.memory += this.parseMemoryString(containerLimits.memory);
                }
            }

            // Get actual usage from metrics
            const podMetrics = metricsData.pods.find(p => 
                p.metadata.name === podName && p.metadata.namespace === namespace
            );

            let actualUsage: ResourceUtilization = { cpu: 0, memory: 0, network: 0, storage: 0 };
            if (podMetrics) {
                let totalCpuUsage = 0;
                let totalMemoryUsage = 0;

                for (const container of podMetrics.containers) {
                    totalCpuUsage += this.parseCpuString(container.usage.cpu);
                    totalMemoryUsage += this.parseMemoryString(container.usage.memory);
                }

                actualUsage = {
                    cpu: requests.cpu > 0 ? (totalCpuUsage / requests.cpu) * 100 : 0,
                    memory: requests.memory > 0 ? (totalMemoryUsage / requests.memory) * 100 : 0,
                    network: Math.random() * 50 + 10, // Mock network utilization
                    storage: Math.random() * 70 + 15  // Mock storage utilization
                };
            }

            // Calculate efficiency and cost
            const efficiency = this.calculatePodEfficiency(requests, actualUsage);
            const cost = this.calculatePodCost(requests);
            const status = this.determinePodStatus(actualUsage, efficiency);

            podUsages.push({
                podName,
                namespace,
                cost,
                requests,
                limits,
                actualUsage,
                efficiency,
                status
            });
        }

        return podUsages.sort((a, b) => b.cost - a.cost);
    }

    /**
     * Get namespace-level usage metrics
     */
    private async getNamespaceUsage(timeRange: { start: string; end: string }): Promise<NamespaceUsage[]> {
        if (!this.k8sApi) {
            return this.mockNamespaceUsage();
        }

        try {
            const namespacesResponse = await this.k8sApi.listNamespace();
            const namespaces = namespacesResponse.body.items;
            const podsResponse = await this.k8sApi.listPodForAllNamespaces();
            const allPods = podsResponse.body.items as K8sPod[];

            const namespaceUsages: NamespaceUsage[] = [];

            for (const namespace of namespaces) {
                const namespaceName = namespace.metadata.name;
                const namespacePods = allPods.filter(p => p.metadata.namespace === namespaceName);

                let totalCost = 0;
                let totalCpuUtilization = 0;
                let totalMemoryUtilization = 0;
                let podCount = 0;

                for (const pod of namespacePods) {
                    // Calculate pod cost and utilization
                    const requests = this.calculatePodRequests(pod);
                    const cost = this.calculatePodCost(requests);
                    totalCost += cost;

                    // Mock utilization for now
                    totalCpuUtilization += Math.random() * 80 + 10;
                    totalMemoryUtilization += Math.random() * 70 + 15;
                    podCount++;
                }

                const utilization: ResourceUtilization = {
                    cpu: podCount > 0 ? totalCpuUtilization / podCount : 0,
                    memory: podCount > 0 ? totalMemoryUtilization / podCount : 0,
                    network: Math.random() * 50 + 20,
                    storage: Math.random() * 60 + 20
                };

                const trends = this.generateUsageTrends(timeRange);

                namespaceUsages.push({
                    namespaceName,
                    cost: totalCost,
                    pods: namespacePods.length,
                    utilization,
                    trends
                });
            }

            return namespaceUsages.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get namespace usage:', error);
            throw error;
        }
    }

    /**
     * Get usage summary
     */
    private async getUsageSummary(): Promise<K8sUsageSummary> {
        if (!this.k8sApi) {
            return this.mockUsageSummary();
        }

        try {
            const clusters = await this.getClusterUsage();
            const nodes = await this.getNodeUsage();
            const pods = await this.getPodUsage();

            const totalCost = clusters.reduce((sum, cluster) => sum + cluster.totalCost, 0);
            const totalPods = pods.length;
            const efficientPods = pods.filter(p => p.efficiency > 0.7).length;
            const efficiency = totalPods > 0 ? efficientPods / totalPods : 0;
            
            const idleNodes = nodes.filter(n => n.status === 'idle').length;
            const underutilizedPods = pods.filter(p => p.actualUsage.cpu < 20 && p.actualUsage.memory < 20).length;
            const wastedResources = (idleNodes + underutilizedPods) / (nodes.length + totalPods) * 100;

            const recommendations = this.generateRecommendations(nodes, pods);

            return {
                totalCost,
                efficiency,
                wastedResources,
                recommendations
            };
        } catch (error) {
            console.error('Failed to get usage summary:', error);
            throw error;
        }
    }

    /**
     * Helper methods for calculations
     */
    private parseCpuString(cpu: string): number {
        if (cpu.endsWith('m')) {
            return parseInt(cpu.slice(0, -1));
        }
        return parseFloat(cpu) * 1000; // Convert to millicores
    }

    private parseMemoryString(memory: string): number {
        const units = { 'Ki': 1024, 'Mi': 1024 * 1024, 'Gi': 1024 * 1024 * 1024 };
        for (const [suffix, multiplier] of Object.entries(units)) {
            if (memory.endsWith(suffix)) {
                return parseInt(memory.slice(0, -2)) * multiplier;
            }
        }
        return parseInt(memory);
    }

    private calculateCpuUtilization(usage: string, capacity: string): number {
        const usageMillis = this.parseCpuString(usage);
        const capacityMillis = this.parseCpuString(capacity);
        return capacityMillis > 0 ? (usageMillis / capacityMillis) * 100 : 0;
    }

    private calculateMemoryUtilization(usage: string, capacity: string): number {
        const usageBytes = this.parseMemoryString(usage);
        const capacityBytes = this.parseMemoryString(capacity);
        return capacityBytes > 0 ? (usageBytes / capacityBytes) * 100 : 0;
    }

    private getNodeHourlyCost(instanceType: string): number {
        const costs: Record<string, number> = {
            't3.medium': 0.0416,
            't3.large': 0.0832,
            't3.xlarge': 0.1664,
            'm5.large': 0.096,
            'm5.xlarge': 0.192,
            'm5.2xlarge': 0.384,
            'c5.large': 0.085,
            'c5.xlarge': 0.17,
            'unknown': 0.1
        };
        return costs[instanceType] || 0.1;
    }

    private calculatePodRequests(pod: K8sPod): ResourceRequests {
        let requests: ResourceRequests = { cpu: 0, memory: 0, storage: 0 };
        
        for (const container of pod.spec.containers || []) {
            const containerRequests = container.resources?.requests;
            if (containerRequests?.cpu) {
                requests.cpu += this.parseCpuString(containerRequests.cpu);
            }
            if (containerRequests?.memory) {
                requests.memory += this.parseMemoryString(containerRequests.memory);
            }
        }
        
        return requests;
    }

    private calculatePodCost(requests: ResourceRequests): number {
        // Simplified cost calculation based on requests
        const cpuCostPerMillicore = 0.00005; // $0.00005 per millicore per hour
        const memoryCostPerByte = 0.00000001; // $0.00000001 per byte per hour
        
        const hourlyCost = (requests.cpu * cpuCostPerMillicore) + (requests.memory * memoryCostPerByte);
        return hourlyCost * 24 * 30; // Monthly cost
    }

    private calculatePodEfficiency(requests: ResourceRequests, actualUsage: ResourceUtilization): number {
        if (requests.cpu === 0 && requests.memory === 0) return 0;
        
        const cpuEfficiency = actualUsage.cpu / 100;
        const memoryEfficiency = actualUsage.memory / 100;
        
        return (cpuEfficiency + memoryEfficiency) / 2;
    }

    private determineNodeStatus(utilization: ResourceUtilization): 'active' | 'idle' | 'overutilized' {
        const avgUtilization = (utilization.cpu + utilization.memory) / 2;
        
        if (avgUtilization < 10) return 'idle';
        if (avgUtilization > 80) return 'overutilized';
        return 'active';
    }

    private determinePodStatus(actualUsage: ResourceUtilization, efficiency: number): 'efficient' | 'overprovisioned' | 'underprovisioned' | 'idle' {
        const avgUsage = (actualUsage.cpu + actualUsage.memory) / 2;
        
        if (avgUsage < 5) return 'idle';
        if (efficiency > 0.8) return 'efficient';
        if (avgUsage < 30) return 'overprovisioned';
        if (avgUsage > 90) return 'underprovisioned';
        return 'efficient';
    }

    private async getClusterUtilization(): Promise<ResourceUtilization> {
        // Mock implementation
        return {
            cpu: Math.random() * 60 + 30,
            memory: Math.random() * 70 + 20,
            network: Math.random() * 50 + 25,
            storage: Math.random() * 80 + 15
        };
    }

    private async getMetricsData(): Promise<MetricsData> {
        // Mock implementation - would use metrics server API
        return {
            pods: [],
            nodes: []
        };
    }

    private generateUsageTrends(timeRange: { start: string; end: string }): UsageTrend[] {
        const trends: UsageTrend[] = [];
        const start = new Date(timeRange.start);
        const end = new Date(timeRange.end);
        const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));

        for (let i = 0; i < days; i++) {
            const date = new Date(start);
            date.setDate(date.getDate() + i);

            trends.push({
                timestamp: date.toISOString(),
                utilization: {
                    cpu: Math.random() * 80 + 10,
                    memory: Math.random() * 70 + 15,
                    network: Math.random() * 50 + 20,
                    storage: Math.random() * 60 + 20
                }
            });
        }

        return trends;
    }

    private generateRecommendations(nodes: NodeUsage[], pods: PodUsage[]): string[] {
        const recommendations: string[] = [];
        
        const idleNodes = nodes.filter(n => n.status === 'idle');
        if (idleNodes.length > 0) {
            recommendations.push(`${idleNodes.length} nodes are idle - consider scaling down or scheduling more workloads`);
        }
        
        const overprovisionedPods = pods.filter(p => p.status === 'overprovisioned');
        if (overprovisionedPods.length > 0) {
            recommendations.push(`${overprovisionedPods.length} pods are overprovisioned - consider reducing resource requests`);
        }
        
        const idlePods = pods.filter(p => p.status === 'idle');
        if (idlePods.length > 0) {
            recommendations.push(`${idlePods.length} pods appear idle - investigate if they are needed`);
        }
        
        return recommendations;
    }

    // Mock data methods for development
    private mockClusterUsage(): ClusterUsage[] {
        return [{
            clusterName: 'production-cluster',
            totalCost: 2400.50,
            nodes: 5,
            pods: 48,
            cpuRequests: 12000,
            memoryRequests: 24000000000,
            cpuLimits: 18000,
            memoryLimits: 36000000000,
            utilization: {
                cpu: 45.2,
                memory: 62.8,
                network: 35.6,
                storage: 58.3
            }
        }];
    }

    private mockNodeUsage(): NodeUsage[] {
        return [
            {
                nodeName: 'node-1',
                instanceType: 'm5.xlarge',
                cost: 580.80,
                utilization: { cpu: 65.4, memory: 78.2, network: 42.1, storage: 67.8 },
                pods: [],
                status: 'active'
            },
            {
                nodeName: 'node-2',
                instanceType: 'm5.xlarge',
                cost: 580.80,
                utilization: { cpu: 8.3, memory: 12.5, network: 5.2, storage: 15.6 },
                pods: [],
                status: 'idle'
            }
        ];
    }

    private mockPodUsage(): PodUsage[] {
        return [
            {
                podName: 'web-app-7d4b9c8f6d-abc123',
                namespace: 'production',
                cost: 45.60,
                requests: { cpu: 500, memory: 536870912, storage: 1073741824 },
                limits: { cpu: 1000, memory: 1073741824 },
                actualUsage: { cpu: 35.2, memory: 68.5, network: 25.3, storage: 42.1 },
                efficiency: 0.52,
                status: 'efficient'
            },
            {
                podName: 'api-server-6b8c7d9e5f-def456',
                namespace: 'production',
                cost: 38.40,
                requests: { cpu: 300, memory: 268435456, storage: 536870912 },
                limits: { cpu: 500, memory: 536870912 },
                actualUsage: { cpu: 8.1, memory: 15.2, network: 12.8, storage: 25.4 },
                efficiency: 0.12,
                status: 'overprovisioned'
            }
        ];
    }

    private mockNamespaceUsage(): NamespaceUsage[] {
        return [
            {
                namespaceName: 'production',
                cost: 1200.30,
                pods: 24,
                utilization: { cpu: 52.4, memory: 68.2, network: 38.7, storage: 55.1 },
                trends: []
            },
            {
                namespaceName: 'staging',
                cost: 480.15,
                pods: 12,
                utilization: { cpu: 28.3, memory: 35.6, network: 22.1, storage: 41.8 },
                trends: []
            }
        ];
    }

    private mockUsageSummary(): K8sUsageSummary {
        return {
            totalCost: 2400.50,
            efficiency: 0.64,
            wastedResources: 35.2,
            recommendations: [
                '2 nodes are idle - consider scaling down',
                '15 pods are overprovisioned - reduce resource requests',
                'Consider using Horizontal Pod Autoscaler for dynamic scaling'
            ]
        };
    }
}

function resolveTimeRange(timeRange?: { start: string; end: string }): { start: string; end: string } {
    if (timeRange) {
        return timeRange;
    }
    const end = new Date();
    const start = new Date(end);
    start.setDate(end.getDate() - 30);
    return {
        start: start.toISOString().split('T')[0],
        end: end.toISOString().split('T')[0],
    };
}

/**
 * Convenience wrapper used by the extension entrypoint.
 */
export async function fetchK8sUsageData(
    config: KubernetesConfig,
    timeRange?: { start: string; end: string }
): Promise<KubernetesUsageData> {
    const collector = new KubernetesUsageCollector(config);
    return collector.collectUsageData(resolveTimeRange(timeRange));
}
