/**
 * Idle Resource Detector
 * 
 * Specialized detector for identifying completely idle resources across
 * multi-cloud infrastructure with high confidence scoring.
 */

import {
    WasteDetectionResult,
    WasteType,
    CostData,
    UsageData,
    ResourceReference,
    Evidence
} from '../types';

/**
 * Idle detection configuration
 */
const IDLE_CONFIG = {
    CPU_THRESHOLD: 2,              // < 2% CPU utilization
    MEMORY_THRESHOLD: 5,           // < 5% memory utilization
    NETWORK_THRESHOLD: 1,          // < 1% network utilization
    MIN_OBSERVATION_HOURS: 48,     // Minimum 48 hours of data
    CONFIDENCE_BASELINE: 0.9,      // Base confidence for idle detection
    MIN_COST_THRESHOLD: 5          // Minimum $5/month to flag
};

/**
 * Specialized idle resource detection with high precision
 */
export class IdleResourceDetector {
    private costData: CostData;
    private usageData: UsageData;
    private timestamp: string;

    constructor(costData: CostData, usageData: UsageData) {
        this.costData = costData;
        this.usageData = usageData;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Detect all idle resources across infrastructure
     */
    async detectIdleResources(): Promise<WasteDetectionResult[]> {
        console.log('🔍 Running specialized idle resource detection...');
        
        const results: WasteDetectionResult[] = [];
        
        try {
            // Detect idle resources across all platforms
            const [awsIdle, gcpIdle, azureIdle, k8sIdle] = await Promise.all([
                this.detectAWSIdleResources(),
                this.detectGCPIdleResources(),
                this.detectAzureIdleResources(),
                this.detectKubernetesIdleResources()
            ]);

            results.push(...awsIdle, ...gcpIdle, ...azureIdle, ...k8sIdle);

            // Filter by cost threshold and confidence
            const significantIdle = results.filter(r => 
                r.wastedAmount >= IDLE_CONFIG.MIN_COST_THRESHOLD && 
                r.confidence >= 0.8
            );

            const totalWaste = significantIdle.reduce((sum, r) => sum + r.wastedAmount, 0);
            console.log(`💤 Idle resource detection complete: $${totalWaste.toFixed(2)}/month in ${significantIdle.length} idle resources`);

            return significantIdle;
        } catch (error) {
            console.error('❌ Idle resource detection failed:', error);
            throw error;
        }
    }

    /**
     * Detect AWS idle resources
     */
    private async detectAWSIdleResources(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (!this.costData.aws?.instances) {
            return results;
        }

        for (const instance of this.costData.aws.instances) {
            const idleScore = this.calculateIdleScore({
                cpu: instance.usage.cpuUtilization,
                memory: instance.usage.memoryUtilization,
                network: instance.usage.networkUtilization,
                storage: instance.usage.storageUtilization
            });

            if (idleScore.isIdle) {
                const evidence = this.generateIdleEvidence('AWS EC2', instance.usage);
                
                results.push({
                    id: `idle-aws-${instance.instanceId}`,
                    type: WasteType.IDLE_RESOURCES,
                    severity: this.determineSeverity(instance.cost),
                    description: `AWS EC2 instance ${instance.instanceId} (${instance.instanceType}) is idle with ${idleScore.confidence.toFixed(1)}% confidence`,
                    affectedResources: [{
                        id: instance.instanceId,
                        name: instance.instanceId,
                        type: instance.instanceType,
                        cloud: 'aws',
                        tags: { instanceType: instance.instanceType }
                    }],
                    wastedAmount: instance.cost,
                    confidence: idleScore.confidence,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Detect GCP idle resources
     */
    private async detectGCPIdleResources(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock GCP compute instance analysis
        // In real implementation, would analyze GCP Compute Engine instances
        const mockGCPInstances = [
            {
                instanceId: 'instance-12345',
                instanceType: 'n1-standard-2',
                cost: 85.40,
                usage: { cpu: 1.2, memory: 3.8, network: 0.5, storage: 12.0 }
            }
        ];

        for (const instance of mockGCPInstances) {
            const idleScore = this.calculateIdleScore(instance.usage);
            
            if (idleScore.isIdle) {
                const evidence = this.generateIdleEvidence('GCP Compute Engine', instance.usage);
                
                results.push({
                    id: `idle-gcp-${instance.instanceId}`,
                    type: WasteType.IDLE_RESOURCES,
                    severity: this.determineSeverity(instance.cost),
                    description: `GCP Compute Engine instance ${instance.instanceId} is idle`,
                    affectedResources: [{
                        id: instance.instanceId,
                        name: instance.instanceId,
                        type: instance.instanceType,
                        cloud: 'gcp'
                    }],
                    wastedAmount: instance.cost,
                    confidence: idleScore.confidence,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Detect Azure idle resources
     */
    private async detectAzureIdleResources(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock Azure VM analysis
        // In real implementation, would analyze Azure Virtual Machines
        const mockAzureVMs = [
            {
                vmId: 'vm-idle-example',
                vmSize: 'Standard_D2s_v3',
                cost: 92.16,
                usage: { cpu: 0.8, memory: 2.1, network: 0.2, storage: 8.5 }
            }
        ];

        for (const vm of mockAzureVMs) {
            const idleScore = this.calculateIdleScore(vm.usage);
            
            if (idleScore.isIdle) {
                const evidence = this.generateIdleEvidence('Azure VM', vm.usage);
                
                results.push({
                    id: `idle-azure-${vm.vmId}`,
                    type: WasteType.IDLE_RESOURCES,
                    severity: this.determineSeverity(vm.cost),
                    description: `Azure VM ${vm.vmId} (${vm.vmSize}) is idle`,
                    affectedResources: [{
                        id: vm.vmId,
                        name: vm.vmId,
                        type: vm.vmSize,
                        cloud: 'azure'
                    }],
                    wastedAmount: vm.cost,
                    confidence: idleScore.confidence,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Detect Kubernetes idle resources
     */
    private async detectKubernetesIdleResources(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (!this.usageData.kubernetes) {
            return results;
        }

        // Check idle pods
        for (const pod of this.usageData.kubernetes.pods) {
            const idleScore = this.calculateIdleScore({
                cpu: pod.actualUsage.cpu,
                memory: pod.actualUsage.memory,
                network: pod.actualUsage.network,
                storage: pod.actualUsage.storage
            });

            if (idleScore.isIdle && pod.cost >= IDLE_CONFIG.MIN_COST_THRESHOLD) {
                const evidence = this.generateIdleEvidence('Kubernetes Pod', {
                    cpu: pod.actualUsage.cpu,
                    memory: pod.actualUsage.memory,
                    network: pod.actualUsage.network,
                    storage: pod.actualUsage.storage
                });

                results.push({
                    id: `idle-k8s-${pod.podName}`,
                    type: WasteType.IDLE_RESOURCES,
                    severity: this.determineSeverity(pod.cost),
                    description: `Kubernetes pod ${pod.podName} in namespace ${pod.namespace} is idle`,
                    affectedResources: [{
                        id: pod.podName,
                        name: pod.podName,
                        type: 'Pod',
                        cloud: 'kubernetes',
                        tags: { namespace: pod.namespace }
                    }],
                    wastedAmount: pod.cost,
                    confidence: idleScore.confidence,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        // Check idle nodes
        for (const node of this.usageData.kubernetes.nodes) {
            if (node.status === 'idle' && node.cost >= IDLE_CONFIG.MIN_COST_THRESHOLD) {
                const idleScore = this.calculateIdleScore({
                    cpu: node.utilization.cpu,
                    memory: node.utilization.memory,
                    network: node.utilization.network,
                    storage: node.utilization.storage
                });

                const evidence = this.generateIdleEvidence('Kubernetes Node', {
                    cpu: node.utilization.cpu,
                    memory: node.utilization.memory,
                    network: node.utilization.network,
                    storage: node.utilization.storage
                });

                results.push({
                    id: `idle-k8s-node-${node.nodeName}`,
                    type: WasteType.IDLE_RESOURCES,
                    severity: this.determineSeverity(node.cost),
                    description: `Kubernetes node ${node.nodeName} (${node.instanceType}) is idle`,
                    affectedResources: [{
                        id: node.nodeName,
                        name: node.nodeName,
                        type: node.instanceType,
                        cloud: 'kubernetes'
                    }],
                    wastedAmount: node.cost,
                    confidence: idleScore.confidence,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Calculate comprehensive idle score
     */
    private calculateIdleScore(usage: { cpu: number; memory: number; network: number; storage: number }): {
        isIdle: boolean;
        confidence: number;
        score: number;
    } {
        // Calculate individual thresholds
        const cpuIdle = usage.cpu < IDLE_CONFIG.CPU_THRESHOLD;
        const memoryIdle = usage.memory < IDLE_CONFIG.MEMORY_THRESHOLD;
        const networkIdle = usage.network < IDLE_CONFIG.NETWORK_THRESHOLD;
        
        // Resource must be idle on both CPU and memory
        const isIdle = cpuIdle && memoryIdle;
        
        if (!isIdle) {
            return { isIdle: false, confidence: 0, score: 0 };
        }

        // Calculate confidence based on how far below thresholds
        const cpuDistance = Math.max(0, IDLE_CONFIG.CPU_THRESHOLD - usage.cpu) / IDLE_CONFIG.CPU_THRESHOLD;
        const memoryDistance = Math.max(0, IDLE_CONFIG.MEMORY_THRESHOLD - usage.memory) / IDLE_CONFIG.MEMORY_THRESHOLD;
        const networkDistance = Math.max(0, IDLE_CONFIG.NETWORK_THRESHOLD - usage.network) / IDLE_CONFIG.NETWORK_THRESHOLD;
        
        // Weight CPU and memory higher than network
        const score = (cpuDistance * 0.4 + memoryDistance * 0.4 + networkDistance * 0.2);
        const confidence = Math.min(0.99, IDLE_CONFIG.CONFIDENCE_BASELINE + (score * 0.1));
        
        return { isIdle, confidence, score };
    }

    /**
     * Generate evidence for idle resources
     */
    private generateIdleEvidence(resourceType: string, usage: any): Evidence[] {
        return [
            {
                type: 'metric',
                description: `${resourceType} CPU utilization`,
                value: usage.cpu,
                threshold: IDLE_CONFIG.CPU_THRESHOLD,
                unit: '%'
            },
            {
                type: 'metric',
                description: `${resourceType} memory utilization`,
                value: usage.memory,
                threshold: IDLE_CONFIG.MEMORY_THRESHOLD,
                unit: '%'
            },
            {
                type: 'metric',
                description: `${resourceType} network utilization`,
                value: usage.network,
                threshold: IDLE_CONFIG.NETWORK_THRESHOLD,
                unit: '%'
            }
        ];
    }

    /**
     * Determine severity based on cost impact
     */
    private determineSeverity(cost: number): 'low' | 'medium' | 'high' | 'critical' {
        if (cost >= 200) return 'critical';
        if (cost >= 100) return 'high';
        if (cost >= 25) return 'medium';
        return 'low';
    }

    /**
     * Get summary of idle resources by type
     */
    async getIdleSummary(): Promise<{
        totalWaste: number;
        resourceCount: number;
        byCloud: Record<string, { count: number; waste: number }>;
        byType: Record<string, { count: number; waste: number }>;
    }> {
        const idleResources = await this.detectIdleResources();
        
        const summary = {
            totalWaste: idleResources.reduce((sum, r) => sum + r.wastedAmount, 0),
            resourceCount: idleResources.length,
            byCloud: {} as Record<string, { count: number; waste: number }>,
            byType: {} as Record<string, { count: number; waste: number }>
        };
        
        for (const resource of idleResources) {
            for (const affectedResource of resource.affectedResources) {
                // By cloud
                if (!summary.byCloud[affectedResource.cloud]) {
                    summary.byCloud[affectedResource.cloud] = { count: 0, waste: 0 };
                }
                summary.byCloud[affectedResource.cloud].count++;
                summary.byCloud[affectedResource.cloud].waste += resource.wastedAmount;
                
                // By type
                if (!summary.byType[affectedResource.type]) {
                    summary.byType[affectedResource.type] = { count: 0, waste: 0 };
                }
                summary.byType[affectedResource.type].count++;
                summary.byType[affectedResource.type].waste += resource.wastedAmount;
            }
        }
        
        return summary;
    }
}