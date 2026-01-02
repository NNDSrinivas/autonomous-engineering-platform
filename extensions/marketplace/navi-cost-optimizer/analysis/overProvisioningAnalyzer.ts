/**
 * Overprovisioning Analyzer
 * 
 * Specialized analysis of resource overprovisioning with specific focus on
 * right-sizing opportunities and efficiency improvements.
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
 * Overprovisioning analysis configuration
 */
const OVERPROV_CONFIG = {
    EFFICIENCY_THRESHOLD: 0.6,         // < 60% efficiency is overprovisioned
    UTILIZATION_THRESHOLD: 40,         // < 40% utilization suggests overprovisioning
    MIN_SAVINGS_THRESHOLD: 20,         // Minimum $20/month savings to recommend
    HIGH_COST_THRESHOLD: 100,          // $100+ instances get priority analysis
    CONFIDENCE_BASELINE: 0.8,          // Base confidence for overprovisioning detection
    MIN_OBSERVATION_DAYS: 7            // Need 7 days of data for reliable analysis
};

/**
 * Right-sizing recommendations for different instance types
 */
const RIGHTSIZING_MAP: Record<string, string[]> = {
    // AWS instance families
    't3.2xlarge': ['t3.xlarge', 't3.large'],
    't3.xlarge': ['t3.large', 't3.medium'],
    't3.large': ['t3.medium', 't3.small'],
    'm5.2xlarge': ['m5.xlarge', 'm5.large'],
    'm5.xlarge': ['m5.large', 'c5.large'],
    'c5.2xlarge': ['c5.xlarge', 'c5.large'],
    'c5.xlarge': ['c5.large', 'c5.medium'],
    
    // GCP machine types
    'n1-standard-8': ['n1-standard-4', 'n1-standard-2'],
    'n1-standard-4': ['n1-standard-2', 'n1-standard-1'],
    'n1-highmem-4': ['n1-standard-4', 'n1-standard-2'],
    
    // Azure VM sizes
    'Standard_D4s_v3': ['Standard_D2s_v3', 'Standard_B2s'],
    'Standard_D2s_v3': ['Standard_B2s', 'Standard_B1s']
};

/**
 * Specialized overprovisioning analysis with right-sizing recommendations
 */
export class OverprovisioningAnalyzer {
    private costData: CostData;
    private usageData: UsageData;
    private timestamp: string;

    constructor(costData: CostData, usageData: UsageData) {
        this.costData = costData;
        this.usageData = usageData;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Analyze all overprovisioning opportunities
     */
    async analyzeOverprovisioning(): Promise<WasteDetectionResult[]> {
        console.log('🔍 Analyzing overprovisioning across infrastructure...');
        
        const results: WasteDetectionResult[] = [];
        
        try {
            const [cloudOverprov, k8sOverprov, storageOverprov] = await Promise.all([
                this.analyzeCloudInstanceOverprovisioning(),
                this.analyzeKubernetesOverprovisioning(),
                this.analyzeStorageOverprovisioning()
            ]);

            results.push(...cloudOverprov, ...k8sOverprov, ...storageOverprov);

            // Sort by potential savings
            results.sort((a, b) => b.wastedAmount - a.wastedAmount);

            // Filter by minimum savings threshold
            const significantOverprov = results.filter(r => r.wastedAmount >= OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD);

            const totalSavings = significantOverprov.reduce((sum, r) => sum + r.wastedAmount, 0);
            console.log(`📈 Overprovisioning analysis complete: $${totalSavings.toFixed(2)}/month potential savings from ${significantOverprov.length} optimizations`);

            return significantOverprov;
        } catch (error) {
            console.error('❌ Overprovisioning analysis failed:', error);
            throw error;
        }
    }

    /**
     * Analyze cloud instance overprovisioning
     */
    private async analyzeCloudInstanceOverprovisioning(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Analyze AWS instances
        if (this.costData.aws?.instances) {
            for (const instance of this.costData.aws.instances) {
                const analysis = this.analyzeInstanceUtilization(instance, 'aws');
                if (analysis.isOverprovisioned) {
                    results.push(analysis.wasteResult);
                }
            }
        }

        // Mock GCP and Azure analysis (would be similar structure)
        const mockCloudInstances = [
            {
                id: 'gcp-instance-123',
                type: 'n1-standard-4',
                cost: 145.60,
                utilization: { cpu: 25, memory: 35, network: 20, storage: 45 },
                cloud: 'gcp' as const
            },
            {
                id: 'azure-vm-456',
                type: 'Standard_D4s_v3',
                cost: 156.80,
                utilization: { cpu: 18, memory: 22, network: 15, storage: 38 },
                cloud: 'azure' as const
            }
        ];

        for (const instance of mockCloudInstances) {
            const analysis = this.analyzeInstanceUtilization(instance, instance.cloud);
            if (analysis.isOverprovisioned) {
                results.push(analysis.wasteResult);
            }
        }

        return results;
    }

    /**
     * Analyze Kubernetes overprovisioning
     */
    private async analyzeKubernetesOverprovisioning(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (!this.usageData.kubernetes?.pods) {
            return results;
        }

        // Analyze pod overprovisioning
        for (const pod of this.usageData.kubernetes.pods) {
            if (pod.efficiency < OVERPROV_CONFIG.EFFICIENCY_THRESHOLD && pod.cost >= OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD) {
                const potentialSavings = this.calculatePodRightsizingSavings(pod);
                
                if (potentialSavings >= OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD) {
                    const evidence = this.generateOverprovisioningEvidence(pod);
                    
                    results.push({
                        id: `overprov-pod-${pod.podName}`,
                        type: WasteType.OVERPROVISIONING,
                        severity: this.determineSeverity(potentialSavings),
                        description: `Pod ${pod.podName} is overprovisioned with ${(pod.efficiency * 100).toFixed(1)}% efficiency`,
                        affectedResources: [{
                            id: pod.podName,
                            name: pod.podName,
                            type: 'Pod',
                            cloud: 'kubernetes',
                            tags: { 
                                namespace: pod.namespace,
                                efficiency: (pod.efficiency * 100).toFixed(1) + '%'
                            }
                        }],
                        wastedAmount: potentialSavings,
                        confidence: this.calculateOverprovisioningConfidence(pod),
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        // Analyze namespace-level overprovisioning patterns
        const namespaceAnalysis = this.analyzeNamespaceOverprovisioning();
        results.push(...namespaceAnalysis);

        return results;
    }

    /**
     * Analyze storage overprovisioning
     */
    private async analyzeStorageOverprovisioning(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock storage analysis - would analyze actual storage utilization
        const mockStorageVolumes = [
            {
                id: 'vol-oversized-123',
                size: 500, // 500GB
                used: 85,  // 85GB used (17% utilization)
                cost: 50.00,
                type: 'gp3',
                cloud: 'aws' as const
            },
            {
                id: 'disk-big-456',
                size: 1000, // 1TB
                used: 120,  // 120GB used (12% utilization)
                cost: 120.00,
                type: 'pd-standard',
                cloud: 'gcp' as const
            }
        ];

        for (const volume of mockStorageVolumes) {
            const utilizationPct = (volume.used / volume.size) * 100;
            
            if (utilizationPct < 25 && volume.cost >= 20) { // < 25% utilization on $20+ volumes
                const rightSize = Math.ceil(volume.used * 1.5); // 50% buffer
                const potentialSavings = (volume.cost * (volume.size - rightSize)) / volume.size;
                
                if (potentialSavings >= OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD) {
                    const evidence: Evidence[] = [
                        {
                            type: 'usage',
                            description: 'Storage utilization percentage',
                            value: utilizationPct,
                            threshold: 25,
                            unit: '%'
                        },
                        {
                            type: 'billing',
                            description: 'Current monthly storage cost',
                            value: volume.cost,
                            threshold: 20,
                            unit: 'USD'
                        }
                    ];

                    results.push({
                        id: `overprov-storage-${volume.id}`,
                        type: WasteType.OVERPROVISIONING,
                        severity: this.determineSeverity(potentialSavings),
                        description: `${volume.cloud.toUpperCase()} storage volume ${volume.id} is oversized (${utilizationPct.toFixed(1)}% utilized)`,
                        affectedResources: [{
                            id: volume.id,
                            name: volume.id,
                            type: volume.type,
                            cloud: volume.cloud,
                            tags: {
                                size: `${volume.size}GB`,
                                utilization: `${utilizationPct.toFixed(1)}%`
                            }
                        }],
                        wastedAmount: potentialSavings,
                        confidence: 0.85,
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Analyze individual instance utilization for overprovisioning
     */
    private analyzeInstanceUtilization(instance: any, cloud: string): {
        isOverprovisioned: boolean;
        wasteResult: WasteDetectionResult;
    } {
        const avgUtilization = (instance.utilization?.cpu + instance.utilization?.memory) / 2 || 
                              (instance.usage?.cpuUtilization + instance.usage?.memoryUtilization) / 2;
        
        const isOverprovisioned = avgUtilization < OVERPROV_CONFIG.UTILIZATION_THRESHOLD;
        
        if (!isOverprovisioned) {
            return { isOverprovisioned: false, wasteResult: {} as WasteDetectionResult };
        }

        // Calculate potential savings from right-sizing
        const instanceType = instance.instanceType || instance.type;
        const rightsizingOptions = RIGHTSIZING_MAP[instanceType] || [];
        const estimatedSavings = rightsizingOptions.length > 0 ? instance.cost * 0.4 : instance.cost * 0.3; // 30-40% savings
        
        const evidence: Evidence[] = [
            {
                type: 'metric',
                description: 'Average resource utilization',
                value: avgUtilization,
                threshold: OVERPROV_CONFIG.UTILIZATION_THRESHOLD,
                unit: '%'
            },
            {
                type: 'billing',
                description: 'Monthly instance cost',
                value: instance.cost,
                threshold: 0,
                unit: 'USD'
            }
        ];

        const wasteResult: WasteDetectionResult = {
            id: `overprov-${cloud}-${instance.id || instance.instanceId}`,
            type: WasteType.OVERPROVISIONING,
            severity: this.determineSeverity(estimatedSavings),
            description: `${cloud.toUpperCase()} instance ${instance.id || instance.instanceId} (${instanceType}) is overprovisioned with ${avgUtilization.toFixed(1)}% average utilization`,
            affectedResources: [{
                id: instance.id || instance.instanceId,
                name: instance.id || instance.instanceId,
                type: instanceType,
                cloud: cloud as 'aws' | 'gcp' | 'azure',
                tags: {
                    currentSize: instanceType,
                    recommendedSize: rightsizingOptions[0] || 'smaller-instance',
                    utilization: `${avgUtilization.toFixed(1)}%`
                }
            }],
            wastedAmount: estimatedSavings,
            confidence: this.calculateInstanceOverprovisioningConfidence(avgUtilization, instance.cost),
            evidence,
            detectedAt: this.timestamp
        };

        return { isOverprovisioned: true, wasteResult };
    }

    /**
     * Analyze namespace-level overprovisioning patterns
     */
    private analyzeNamespaceOverprovisioning(): WasteDetectionResult[] {
        const results: WasteDetectionResult[] = [];
        
        if (!this.usageData.kubernetes?.namespaces) {
            return results;
        }

        for (const namespace of this.usageData.kubernetes.namespaces) {
            const avgUtilization = (namespace.utilization.cpu + namespace.utilization.memory) / 2;
            
            if (avgUtilization < OVERPROV_CONFIG.UTILIZATION_THRESHOLD && 
                namespace.cost >= OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD * 2) {
                
                const potentialSavings = namespace.cost * 0.3; // Estimated 30% savings from right-sizing
                
                const evidence: Evidence[] = [
                    {
                        type: 'usage',
                        description: 'Namespace average utilization',
                        value: avgUtilization,
                        threshold: OVERPROV_CONFIG.UTILIZATION_THRESHOLD,
                        unit: '%'
                    },
                    {
                        type: 'billing',
                        description: 'Namespace monthly cost',
                        value: namespace.cost,
                        threshold: OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD * 2,
                        unit: 'USD'
                    },
                    {
                        type: 'metric',
                        description: 'Number of pods in namespace',
                        value: namespace.pods,
                        threshold: 1,
                        unit: 'pods'
                    }
                ];

                results.push({
                    id: `overprov-namespace-${namespace.namespaceName}`,
                    type: WasteType.OVERPROVISIONING,
                    severity: this.determineSeverity(potentialSavings),
                    description: `Namespace ${namespace.namespaceName} shows overprovisioning pattern with ${avgUtilization.toFixed(1)}% average utilization across ${namespace.pods} pods`,
                    affectedResources: [{
                        id: namespace.namespaceName,
                        name: namespace.namespaceName,
                        type: 'Namespace',
                        cloud: 'kubernetes',
                        tags: {
                            podCount: namespace.pods.toString(),
                            utilization: `${avgUtilization.toFixed(1)}%`
                        }
                    }],
                    wastedAmount: potentialSavings,
                    confidence: 0.75, // Medium confidence for namespace-level analysis
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Calculate potential savings from pod right-sizing
     */
    private calculatePodRightsizingSavings(pod: any): number {
        // Estimate savings based on efficiency
        const wastedEfficiency = 1 - pod.efficiency;
        const potentialSavings = pod.cost * wastedEfficiency * 0.8; // 80% of wasted efficiency is recoverable
        return potentialSavings;
    }

    /**
     * Generate evidence for overprovisioning
     */
    private generateOverprovisioningEvidence(pod: any): Evidence[] {
        return [
            {
                type: 'usage',
                description: 'Pod efficiency score',
                value: pod.efficiency * 100,
                threshold: OVERPROV_CONFIG.EFFICIENCY_THRESHOLD * 100,
                unit: '%'
            },
            {
                type: 'metric',
                description: 'CPU utilization vs requests',
                value: pod.actualUsage.cpu,
                threshold: 60,
                unit: '%'
            },
            {
                type: 'metric',
                description: 'Memory utilization vs requests',
                value: pod.actualUsage.memory,
                threshold: 60,
                unit: '%'
            },
            {
                type: 'billing',
                description: 'Pod monthly cost',
                value: pod.cost,
                threshold: OVERPROV_CONFIG.MIN_SAVINGS_THRESHOLD,
                unit: 'USD'
            }
        ];
    }

    /**
     * Calculate overprovisioning confidence for pods
     */
    private calculateOverprovisioningConfidence(pod: any): number {
        // Higher confidence for lower efficiency and consistent patterns
        const efficiencyScore = 1 - pod.efficiency;
        const utilizationScore = Math.max(0, (60 - (pod.actualUsage.cpu + pod.actualUsage.memory) / 2) / 60);
        const confidenceScore = (efficiencyScore * 0.6) + (utilizationScore * 0.4);
        
        return Math.min(0.95, OVERPROV_CONFIG.CONFIDENCE_BASELINE + (confidenceScore * 0.15));
    }

    /**
     * Calculate overprovisioning confidence for instances
     */
    private calculateInstanceOverprovisioningConfidence(utilization: number, cost: number): number {
        // Higher confidence for lower utilization and higher cost instances
        const utilizationScore = Math.max(0, (60 - utilization) / 60);
        const costScore = Math.min(1, cost / 200); // Normalize cost impact
        const confidenceScore = (utilizationScore * 0.7) + (costScore * 0.3);
        
        return Math.min(0.92, OVERPROV_CONFIG.CONFIDENCE_BASELINE + (confidenceScore * 0.12));
    }

    /**
     * Determine severity based on potential savings
     */
    private determineSeverity(savings: number): 'low' | 'medium' | 'high' | 'critical' {
        if (savings >= 300) return 'critical';
        if (savings >= 150) return 'high';
        if (savings >= 75) return 'medium';
        return 'low';
    }

    /**
     * Get right-sizing recommendations for instance type
     */
    getRightsizingRecommendations(instanceType: string): {
        recommended: string[];
        estimatedSavings: string;
        confidence: string;
    } {
        const options = RIGHTSIZING_MAP[instanceType] || [];
        
        return {
            recommended: options.length > 0 ? options : ['Consider smaller instance family'],
            estimatedSavings: options.length > 0 ? '30-50%' : '20-40%',
            confidence: options.length > 0 ? 'High' : 'Medium'
        };
    }
}
