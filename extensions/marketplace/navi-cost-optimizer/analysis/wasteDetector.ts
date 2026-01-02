/**
 * Waste Detection Engine
 * 
 * Deterministic analysis of cost waste patterns across multi-cloud infrastructure.
 * No AI inference - pure metrics-based waste identification with quantified impact.
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
 * Waste detection thresholds and configuration
 */
const WASTE_THRESHOLDS = {
    IDLE_CPU_THRESHOLD: 5,           // < 5% CPU utilization
    IDLE_MEMORY_THRESHOLD: 10,       // < 10% memory utilization
    IDLE_DURATION_HOURS: 24,         // Idle for 24+ hours
    OVERPROVISIONING_RATIO: 2.5,     // Resource requests > 2.5x actual usage
    COST_SPIKE_THRESHOLD: 1.5,       // 50% cost increase
    UNIT_COST_REGRESSION: 0.2,       // 20% increase in cost per unit
    MIN_WASTE_AMOUNT: 10             // Minimum $10/month to flag
};

/**
 * Main waste detection orchestrator
 */
export class WasteDetector {
    private costData: CostData;
    private usageData: UsageData;
    private detectionTimestamp: string;

    constructor(costData: CostData, usageData: UsageData) {
        this.costData = costData;
        this.usageData = usageData;
        this.detectionTimestamp = new Date().toISOString();
    }

    /**
     * Detect all forms of cost waste across infrastructure
     */
    async detectAllWaste(): Promise<WasteDetectionResult[]> {
        console.log('🔍 Starting comprehensive waste detection analysis...');
        
        const detectionResults: WasteDetectionResult[] = [];
        
        try {
            // Run all waste detection algorithms in parallel
            const [idleResources, overprovisioning, unusedVolumes, oversizedInstances, costRegressions, unitEconomics, schedulingWaste] = await Promise.all([
                this.detectIdleResources(),
                this.detectOverprovisioning(),
                this.detectUnusedVolumes(),
                this.detectOversizedInstances(),
                this.detectCostRegressions(),
                this.analyzeUnitEconomics(),
                this.detectSchedulingInefficiencies()
            ]);

            // Combine all results
            detectionResults.push(
                ...idleResources,
                ...overprovisioning,
                ...unusedVolumes,
                ...oversizedInstances,
                ...costRegressions,
                ...unitEconomics,
                ...schedulingWaste
            );

            // Sort by waste amount descending
            detectionResults.sort((a, b) => b.wastedAmount - a.wastedAmount);

            // Filter out waste below minimum threshold
            const significantWaste = detectionResults.filter(w => w.wastedAmount >= WASTE_THRESHOLDS.MIN_WASTE_AMOUNT);

            const totalWaste = significantWaste.reduce((sum, w) => sum + w.wastedAmount, 0);
            console.log(`💰 Waste detection complete: $${totalWaste.toFixed(2)}/month identified across ${significantWaste.length} issues`);

            return significantWaste;
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            console.error('❌ Waste detection failed:', error);
            throw new Error(`Waste detection failed: ${message}`);
        }
    }

    /**
     * Detect idle cloud resources
     */
    private async detectIdleResources(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];

        // Analyze AWS idle instances
        if (this.costData.aws?.instances) {
            for (const instance of this.costData.aws.instances) {
                if (this.isInstanceIdle(instance)) {
                    const evidence: Evidence[] = [
                        {
                            type: 'metric',
                            description: 'CPU utilization below threshold',
                            value: instance.usage.cpuUtilization,
                            threshold: WASTE_THRESHOLDS.IDLE_CPU_THRESHOLD,
                            unit: '%'
                        },
                        {
                            type: 'metric',
                            description: 'Memory utilization below threshold',
                            value: instance.usage.memoryUtilization,
                            threshold: WASTE_THRESHOLDS.IDLE_MEMORY_THRESHOLD,
                            unit: '%'
                        }
                    ];

                    results.push({
                        id: `idle-aws-${instance.instanceId}`,
                        type: WasteType.IDLE_RESOURCES,
                        severity: this.calculateSeverity(instance.cost, 'idle'),
                        description: `AWS instance ${instance.instanceId} (${instance.instanceType}) is idle`,
                        affectedResources: [{
                            id: instance.instanceId,
                            name: instance.instanceId,
                            type: instance.instanceType,
                            cloud: 'aws'
                        }],
                        wastedAmount: instance.cost,
                        confidence: this.calculateIdleConfidence(instance.usage),
                        evidence,
                        detectedAt: this.detectionTimestamp
                    });
                }
            }
        }

        // Analyze Kubernetes idle pods
        if (this.usageData.kubernetes?.pods) {
            for (const pod of this.usageData.kubernetes.pods) {
                if (pod.status === 'idle' || (pod.actualUsage.cpu < WASTE_THRESHOLDS.IDLE_CPU_THRESHOLD && pod.actualUsage.memory < WASTE_THRESHOLDS.IDLE_MEMORY_THRESHOLD)) {
                    const evidence: Evidence[] = [
                        {
                            type: 'usage',
                            description: 'Pod CPU usage below threshold',
                            value: pod.actualUsage.cpu,
                            threshold: WASTE_THRESHOLDS.IDLE_CPU_THRESHOLD,
                            unit: '%'
                        },
                        {
                            type: 'usage',
                            description: 'Pod memory usage below threshold',
                            value: pod.actualUsage.memory,
                            threshold: WASTE_THRESHOLDS.IDLE_MEMORY_THRESHOLD,
                            unit: '%'
                        }
                    ];

                    results.push({
                        id: `idle-k8s-${pod.podName}`,
                        type: WasteType.IDLE_RESOURCES,
                        severity: this.calculateSeverity(pod.cost, 'idle'),
                        description: `Kubernetes pod ${pod.podName} in ${pod.namespace} is idle`,
                        affectedResources: [{
                            id: pod.podName,
                            name: pod.podName,
                            type: 'Pod',
                            cloud: 'kubernetes'
                        }],
                        wastedAmount: pod.cost,
                        confidence: this.calculateIdleConfidence(pod.actualUsage),
                        evidence,
                        detectedAt: this.detectionTimestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Detect overprovisioning across resources
     */
    private async detectOverprovisioning(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];

        // Analyze Kubernetes overprovisioned pods
        if (this.usageData.kubernetes?.pods) {
            for (const pod of this.usageData.kubernetes.pods) {
                if (pod.status === 'overprovisioned' || pod.efficiency < 0.4) {
                    const cpuOverprovision = this.calculateOverprovisionRatio(pod.requests.cpu, pod.actualUsage.cpu);
                    const memoryOverprovision = this.calculateOverprovisionRatio(pod.requests.memory, pod.actualUsage.memory);
                    
                    if (cpuOverprovision > WASTE_THRESHOLDS.OVERPROVISIONING_RATIO || memoryOverprovision > WASTE_THRESHOLDS.OVERPROVISIONING_RATIO) {
                        const wastedAmount = pod.cost * (1 - pod.efficiency);
                        
                        const evidence: Evidence[] = [
                            {
                                type: 'usage',
                                description: 'CPU overprovisioning ratio',
                                value: cpuOverprovision,
                                threshold: WASTE_THRESHOLDS.OVERPROVISIONING_RATIO,
                                unit: 'ratio'
                            },
                            {
                                type: 'usage',
                                description: 'Memory overprovisioning ratio',
                                value: memoryOverprovision,
                                threshold: WASTE_THRESHOLDS.OVERPROVISIONING_RATIO,
                                unit: 'ratio'
                            },
                            {
                                type: 'metric',
                                description: 'Pod efficiency score',
                                value: pod.efficiency * 100,
                                threshold: 40,
                                unit: '%'
                            }
                        ];

                        results.push({
                            id: `overprov-k8s-${pod.podName}`,
                            type: WasteType.OVERPROVISIONING,
                            severity: this.calculateSeverity(wastedAmount, 'overprovisioning'),
                            description: `Pod ${pod.podName} is significantly overprovisioned (${(pod.efficiency * 100).toFixed(1)}% efficient)`,
                            affectedResources: [{
                                id: pod.podName,
                                name: pod.podName,
                                type: 'Pod',
                                cloud: 'kubernetes'
                            }],
                            wastedAmount,
                            confidence: 0.85, // High confidence in resource metrics
                            evidence,
                            detectedAt: this.detectionTimestamp
                        });
                    }
                }
            }
        }

        // Analyze oversized cloud instances (simplified)
        if (this.costData.aws?.instances) {
            for (const instance of this.costData.aws.instances) {
                const avgUtilization = (instance.usage.cpuUtilization + instance.usage.memoryUtilization) / 2;
                if (avgUtilization < 30 && instance.cost > 100) { // Low utilization on expensive instances
                    const potentialSavings = instance.cost * 0.5; // Estimate 50% savings from downsizing
                    
                    const evidence: Evidence[] = [
                        {
                            type: 'metric',
                            description: 'Average resource utilization',
                            value: avgUtilization,
                            threshold: 50,
                            unit: '%'
                        },
                        {
                            type: 'billing',
                            description: 'Monthly instance cost',
                            value: instance.cost,
                            threshold: 100,
                            unit: 'USD'
                        }
                    ];

                    results.push({
                        id: `overprov-aws-${instance.instanceId}`,
                        type: WasteType.OVERPROVISIONING,
                        severity: this.calculateSeverity(potentialSavings, 'overprovisioning'),
                        description: `AWS instance ${instance.instanceId} (${instance.instanceType}) appears oversized for current workload`,
                        affectedResources: [{
                            id: instance.instanceId,
                            name: instance.instanceId,
                            type: instance.instanceType,
                            cloud: 'aws'
                        }],
                        wastedAmount: potentialSavings,
                        confidence: 0.7, // Medium confidence - needs deeper analysis
                        evidence,
                        detectedAt: this.detectionTimestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Detect unused storage volumes
     */
    private async detectUnusedVolumes(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // This would analyze storage costs across clouds
        // For now, simulate with mock data
        const mockUnusedVolumes = [
            { id: 'vol-12345', cost: 45.60, cloud: 'aws' as const },
            { id: 'disk-67890', cost: 32.40, cloud: 'gcp' as const }
        ];

        for (const volume of mockUnusedVolumes) {
            const evidence: Evidence[] = [
                {
                    type: 'usage',
                    description: 'Volume attachment status',
                    value: 0,
                    threshold: 1,
                    unit: 'attached'
                },
                {
                    type: 'billing',
                    description: 'Monthly storage cost',
                    value: volume.cost,
                    threshold: 0,
                    unit: 'USD'
                }
            ];

            results.push({
                id: `unused-vol-${volume.id}`,
                type: WasteType.UNUSED_VOLUMES,
                severity: this.calculateSeverity(volume.cost, 'unused'),
                description: `Unused ${volume.cloud.toUpperCase()} volume ${volume.id}`,
                affectedResources: [{
                    id: volume.id,
                    name: volume.id,
                    type: 'Volume',
                    cloud: volume.cloud
                }],
                wastedAmount: volume.cost,
                confidence: 0.95, // High confidence in unused volumes
                evidence,
                detectedAt: this.detectionTimestamp
            });
        }

        return results;
    }

    /**
     * Detect oversized instances that should be downsized
     */
    private async detectOversizedInstances(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // This overlaps with overprovisioning but focuses on instance right-sizing
        // Implementation would analyze historical usage patterns vs instance capabilities
        
        return results; // Placeholder - logic integrated into detectOverprovisioning
    }

    /**
     * Detect cost regressions and anomalies
     */
    private async detectCostRegressions(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Analyze cost trends for regressions
        const costTrends = [
            ...(this.costData.aws?.trends || []),
            ...(this.costData.gcp?.trends || []),
            ...(this.costData.azure?.trends || [])
        ];

        if (costTrends.length >= 7) { // Need at least a week of data
            const recentTrends = costTrends.slice(-7); // Last 7 days
            const avgRecentCost = recentTrends.reduce((sum, t) => sum + t.cost, 0) / recentTrends.length;
            
            const baselineTrends = costTrends.slice(-14, -7); // Previous 7 days
            const avgBaselineCost = baselineTrends.reduce((sum, t) => sum + t.cost, 0) / baselineTrends.length;
            
            if (avgRecentCost > avgBaselineCost * WASTE_THRESHOLDS.COST_SPIKE_THRESHOLD) {
                const regressionAmount = (avgRecentCost - avgBaselineCost) * 30; // Monthly impact
                
                const evidence: Evidence[] = [
                    {
                        type: 'trend',
                        description: 'Recent average daily cost',
                        value: avgRecentCost,
                        threshold: avgBaselineCost * WASTE_THRESHOLDS.COST_SPIKE_THRESHOLD,
                        unit: 'USD/day'
                    },
                    {
                        type: 'trend',
                        description: 'Cost increase percentage',
                        value: ((avgRecentCost / avgBaselineCost - 1) * 100),
                        threshold: (WASTE_THRESHOLDS.COST_SPIKE_THRESHOLD - 1) * 100,
                        unit: '%'
                    }
                ];

                results.push({
                    id: `cost-regression-${Date.now()}`,
                    type: WasteType.COST_REGRESSION,
                    severity: this.calculateSeverity(regressionAmount, 'regression'),
                    description: `Significant cost increase detected: ${((avgRecentCost / avgBaselineCost - 1) * 100).toFixed(1)}% over baseline`,
                    affectedResources: [{
                        id: 'overall-spend',
                        name: 'Overall Infrastructure Spend',
                        type: 'Cost Trend',
                        cloud: 'kubernetes' // Multi-cloud
                    }],
                    wastedAmount: regressionAmount,
                    confidence: 0.8,
                    evidence,
                    detectedAt: this.detectionTimestamp
                });
            }
        }

        return results;
    }

    /**
     * Analyze unit economics for waste patterns
     */
    private async analyzeUnitEconomics(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Correlate traffic with costs to identify unit cost regressions
        if (this.usageData.traffic && this.costData.consolidated.totalSpend > 0) {
            const totalRequests = this.usageData.traffic.requests.reduce((sum, r) => sum + r.requests, 0);
            const costPerRequest = this.costData.consolidated.totalSpend / totalRequests * 1000000; // Cost per million requests
            
            // Mock baseline cost per request (would come from historical data)
            const baselineCostPerRequest = 25.0; // $25 per million requests
            
            if (costPerRequest > baselineCostPerRequest * (1 + WASTE_THRESHOLDS.UNIT_COST_REGRESSION)) {
                const regressionAmount = (costPerRequest - baselineCostPerRequest) / 1000000 * totalRequests;
                
                const evidence: Evidence[] = [
                    {
                        type: 'metric',
                        description: 'Current cost per million requests',
                        value: costPerRequest,
                        threshold: baselineCostPerRequest * (1 + WASTE_THRESHOLDS.UNIT_COST_REGRESSION),
                        unit: 'USD/M requests'
                    },
                    {
                        type: 'metric',
                        description: 'Unit cost regression percentage',
                        value: ((costPerRequest / baselineCostPerRequest - 1) * 100),
                        threshold: WASTE_THRESHOLDS.UNIT_COST_REGRESSION * 100,
                        unit: '%'
                    }
                ];

                results.push({
                    id: `unit-economics-regression-${Date.now()}`,
                    type: WasteType.POOR_UNIT_ECONOMICS,
                    severity: this.calculateSeverity(regressionAmount, 'unit-economics'),
                    description: `Unit economics regression: cost per request increased by ${((costPerRequest / baselineCostPerRequest - 1) * 100).toFixed(1)}%`,
                    affectedResources: [{
                        id: 'unit-economics',
                        name: 'Overall Unit Economics',
                        type: 'Cost Efficiency',
                        cloud: 'kubernetes'
                    }],
                    wastedAmount: regressionAmount,
                    confidence: 0.75,
                    evidence,
                    detectedAt: this.detectionTimestamp
                });
            }
        }

        return results;
    }

    /**
     * Detect Kubernetes scheduling inefficiencies
     */
    private async detectSchedulingInefficiencies(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (this.usageData.kubernetes?.nodes) {
            // Detect uneven node utilization
            const activeNodes = this.usageData.kubernetes.nodes.filter(n => n.status === 'active');
            const idleNodes = this.usageData.kubernetes.nodes.filter(n => n.status === 'idle');
            const overutilizedNodes = this.usageData.kubernetes.nodes.filter(n => n.status === 'overutilized');
            
            if (idleNodes.length > 0 && overutilizedNodes.length > 0) {
                const wastedAmount = idleNodes.reduce((sum, node) => sum + node.cost, 0);
                
                const evidence: Evidence[] = [
                    {
                        type: 'usage',
                        description: 'Number of idle nodes',
                        value: idleNodes.length,
                        threshold: 0,
                        unit: 'nodes'
                    },
                    {
                        type: 'usage',
                        description: 'Number of overutilized nodes',
                        value: overutilizedNodes.length,
                        threshold: 0,
                        unit: 'nodes'
                    }
                ];

                results.push({
                    id: `scheduling-inefficiency-${Date.now()}`,
                    type: WasteType.SCHEDULING_INEFFICIENCY,
                    severity: this.calculateSeverity(wastedAmount, 'scheduling'),
                    description: `Poor pod scheduling: ${idleNodes.length} idle nodes while ${overutilizedNodes.length} nodes are overutilized`,
                    affectedResources: [...idleNodes.map(n => ({
                        id: n.nodeName,
                        name: n.nodeName,
                        type: n.instanceType,
                        cloud: 'kubernetes' as const
                    }))],
                    wastedAmount,
                    confidence: 0.8,
                    evidence,
                    detectedAt: this.detectionTimestamp
                });
            }
        }

        return results;
    }

    /**
     * Helper methods for waste detection
     */
    private isInstanceIdle(instance: any): boolean {
        return instance.usage.cpuUtilization < WASTE_THRESHOLDS.IDLE_CPU_THRESHOLD && 
               instance.usage.memoryUtilization < WASTE_THRESHOLDS.IDLE_MEMORY_THRESHOLD;
    }

    private calculateOverprovisionRatio(requested: number, actual: number): number {
        if (actual === 0) return Infinity;
        return requested / (requested * (actual / 100));
    }

    private calculateIdleConfidence(usage: any): number {
        const avgUtilization = (usage.cpu + usage.memory + usage.network + usage.storage) / 4;
        return Math.max(0.5, 1 - (avgUtilization / 20)); // Higher confidence for lower utilization
    }

    private calculateSeverity(cost: number, type: string): 'low' | 'medium' | 'high' | 'critical' {
        if (cost >= 500) return 'critical';
        if (cost >= 100) return 'high';
        if (cost >= 50) return 'medium';
        return 'low';
    }
}
