/**
 * Unit Economics Analyzer
 * 
 * Analyzes cost efficiency at the unit level (per transaction, per user, per request)
 * to identify opportunities for improving cost-effectiveness and business metrics.
 */

import {
    WasteDetectionResult,
    WasteType,
    CostData,
    UsageData,
    Evidence
} from '../types';

/**
 * Unit economics configuration
 */
const UNIT_ECONOMICS_CONFIG = {
    MIN_EFFICIENCY_THRESHOLD: 0.7,      // < 70% cost efficiency is concerning
    COST_PER_USER_THRESHOLD: 5.0,       // > $5/user/month is expensive
    COST_PER_TRANSACTION_THRESHOLD: 0.10, // > $0.10/transaction is high
    MIN_SAMPLE_SIZE: 1000,              // Need 1000+ samples for reliable analysis
    EFFICIENCY_CONFIDENCE: 0.85,         // Base confidence for efficiency analysis
    MIN_MONTHLY_IMPACT: 50              // Minimum $50/month impact to report
};

/**
 * Unit economics analysis for cost efficiency optimization
 */
export class UnitEconomicsAnalyzer {
    private costData: CostData;
    private usageData: UsageData;
    private timestamp: string;

    constructor(costData: CostData, usageData: UsageData) {
        this.costData = costData;
        this.usageData = usageData;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Analyze unit economics across all dimensions
     */
    async analyzeUnitEconomics(): Promise<WasteDetectionResult[]> {
        console.log('📊 Analyzing unit economics and cost efficiency...');
        
        const results: WasteDetectionResult[] = [];
        
        try {
            const [costPerUser, costPerTransaction, resourceEfficiency, serviceEfficiency] = await Promise.all([
                this.analyzeCostPerUser(),
                this.analyzeCostPerTransaction(),
                this.analyzeResourceEfficiency(),
                this.analyzeServiceEfficiency()
            ]);

            results.push(...costPerUser, ...costPerTransaction, ...resourceEfficiency, ...serviceEfficiency);

            // Sort by monthly impact
            results.sort((a, b) => b.wastedAmount - a.wastedAmount);

            // Filter by minimum impact threshold
            const significantIssues = results.filter(r => r.wastedAmount >= UNIT_ECONOMICS_CONFIG.MIN_MONTHLY_IMPACT);

            const totalImpact = significantIssues.reduce((sum, r) => sum + r.wastedAmount, 0);
            console.log(`📈 Unit economics analysis complete: $${totalImpact.toFixed(2)}/month optimization potential from ${significantIssues.length} inefficiencies`);

            return significantIssues;
        } catch (error) {
            console.error('❌ Unit economics analysis failed:', error);
            throw error;
        }
    }

    /**
     * Analyze cost per user metrics
     */
    private async analyzeCostPerUser(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock user metrics - would come from actual usage data
        const userMetrics = [
            {
                service: 'User Authentication Service',
                totalCost: 450.00,
                activeUsers: 25000,
                costPerUser: 0.018,
                industry_benchmark: 0.012,
                cloud: 'aws'
            },
            {
                service: 'Data Processing Pipeline',
                totalCost: 890.50,
                activeUsers: 18500,
                costPerUser: 0.048,
                industry_benchmark: 0.025,
                cloud: 'gcp'
            },
            {
                service: 'API Gateway',
                totalCost: 235.75,
                activeUsers: 22000,
                costPerUser: 0.0107,
                industry_benchmark: 0.015,
                cloud: 'aws'
            }
        ];

        for (const metric of userMetrics) {
            if (metric.costPerUser > metric.industry_benchmark * 1.5) { // 50% above benchmark
                const excessCostPerUser = metric.costPerUser - metric.industry_benchmark;
                const monthlyWaste = excessCostPerUser * metric.activeUsers;
                
                if (monthlyWaste >= UNIT_ECONOMICS_CONFIG.MIN_MONTHLY_IMPACT) {
                    const efficiencyRatio = metric.industry_benchmark / metric.costPerUser;
                    
                    const evidence: Evidence[] = [
                        {
                            type: 'metric',
                            description: 'Cost per active user',
                            value: metric.costPerUser,
                            threshold: metric.industry_benchmark * 1.5,
                            unit: 'USD/user'
                        },
                        {
                            type: 'metric',
                            description: 'Industry benchmark cost per user',
                            value: metric.industry_benchmark,
                            threshold: 0,
                            unit: 'USD/user'
                        },
                        {
                            type: 'usage',
                            description: 'Monthly active users',
                            value: metric.activeUsers,
                            threshold: UNIT_ECONOMICS_CONFIG.MIN_SAMPLE_SIZE,
                            unit: 'users'
                        },
                        {
                            type: 'billing',
                            description: 'Total service cost',
                            value: metric.totalCost,
                            threshold: 0,
                            unit: 'USD'
                        }
                    ];

                    results.push({
                        id: `unit-cost-user-${metric.service.toLowerCase().replace(/\s+/g, '-')}`,
                        type: WasteType.POOR_UNIT_ECONOMICS,
                        severity: this.determineSeverity(monthlyWaste),
                        description: `${metric.service} has high cost per user: $${metric.costPerUser.toFixed(3)} vs industry benchmark $${metric.industry_benchmark.toFixed(3)} (${(efficiencyRatio * 100).toFixed(1)}% efficiency)`,
                        affectedResources: [{
                            id: metric.service.toLowerCase().replace(/\s+/g, '-'),
                            name: metric.service,
                            type: 'Service',
                            cloud: metric.cloud as 'aws' | 'gcp' | 'azure',
                            tags: {
                                costPerUser: `$${metric.costPerUser.toFixed(3)}`,
                                benchmark: `$${metric.industry_benchmark.toFixed(3)}`,
                                activeUsers: metric.activeUsers.toString(),
                                efficiency: `${(efficiencyRatio * 100).toFixed(1)}%`
                            }
                        }],
                        wastedAmount: monthlyWaste,
                        confidence: this.calculateUnitEconomicsConfidence(metric.activeUsers, efficiencyRatio),
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Analyze cost per transaction metrics
     */
    private async analyzeCostPerTransaction(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock transaction metrics
        const transactionMetrics = [
            {
                service: 'Payment Processing',
                totalCost: 340.25,
                monthlyTransactions: 150000,
                costPerTransaction: 0.00227,
                benchmark: 0.0015,
                cloud: 'aws'
            },
            {
                service: 'Order Management',
                totalCost: 285.50,
                monthlyTransactions: 85000,
                costPerTransaction: 0.00336,
                benchmark: 0.002,
                cloud: 'gcp'
            },
            {
                service: 'Notification Service',
                totalCost: 125.75,
                monthlyTransactions: 45000,
                costPerTransaction: 0.00279,
                benchmark: 0.001,
                cloud: 'azure'
            }
        ];

        for (const metric of transactionMetrics) {
            if (metric.costPerTransaction > metric.benchmark * 1.4) { // 40% above benchmark
                const excessCostPerTransaction = metric.costPerTransaction - metric.benchmark;
                const monthlyWaste = excessCostPerTransaction * metric.monthlyTransactions;
                
                if (monthlyWaste >= UNIT_ECONOMICS_CONFIG.MIN_MONTHLY_IMPACT) {
                    const efficiencyRatio = metric.benchmark / metric.costPerTransaction;
                    
                    const evidence: Evidence[] = [
                        {
                            type: 'metric',
                            description: 'Cost per transaction',
                            value: metric.costPerTransaction,
                            threshold: metric.benchmark * 1.4,
                            unit: 'USD/transaction'
                        },
                        {
                            type: 'metric',
                            description: 'Benchmark cost per transaction',
                            value: metric.benchmark,
                            threshold: 0,
                            unit: 'USD/transaction'
                        },
                        {
                            type: 'usage',
                            description: 'Monthly transactions',
                            value: metric.monthlyTransactions,
                            threshold: UNIT_ECONOMICS_CONFIG.MIN_SAMPLE_SIZE,
                            unit: 'transactions'
                        }
                    ];

                    results.push({
                        id: `unit-cost-txn-${metric.service.toLowerCase().replace(/\s+/g, '-')}`,
                        type: WasteType.POOR_UNIT_ECONOMICS,
                        severity: this.determineSeverity(monthlyWaste),
                        description: `${metric.service} has high cost per transaction: $${metric.costPerTransaction.toFixed(4)} vs benchmark $${metric.benchmark.toFixed(4)} (${(efficiencyRatio * 100).toFixed(1)}% efficiency)`,
                        affectedResources: [{
                            id: metric.service.toLowerCase().replace(/\s+/g, '-'),
                            name: metric.service,
                            type: 'Service',
                            cloud: metric.cloud as 'aws' | 'gcp' | 'azure',
                            tags: {
                                costPerTxn: `$${metric.costPerTransaction.toFixed(4)}`,
                                benchmark: `$${metric.benchmark.toFixed(4)}`,
                                monthlyTxns: metric.monthlyTransactions.toString(),
                                efficiency: `${(efficiencyRatio * 100).toFixed(1)}%`
                            }
                        }],
                        wastedAmount: monthlyWaste,
                        confidence: this.calculateUnitEconomicsConfidence(metric.monthlyTransactions, efficiencyRatio),
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Analyze resource efficiency patterns
     */
    private async analyzeResourceEfficiency(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Analyze Kubernetes resource efficiency
        if (this.usageData.kubernetes?.pods) {
            for (const pod of this.usageData.kubernetes.pods) {
                if (pod.efficiency < UNIT_ECONOMICS_CONFIG.MIN_EFFICIENCY_THRESHOLD && 
                    pod.cost >= UNIT_ECONOMICS_CONFIG.MIN_MONTHLY_IMPACT) {
                    
                    const wastedEfficiency = 1 - pod.efficiency;
                    const monthlyWaste = pod.cost * wastedEfficiency * 0.7; // 70% of inefficiency is recoverable
                    
                    const evidence: Evidence[] = [
                        {
                            type: 'usage',
                            description: 'Resource efficiency score',
                            value: pod.efficiency * 100,
                            threshold: UNIT_ECONOMICS_CONFIG.MIN_EFFICIENCY_THRESHOLD * 100,
                            unit: '%'
                        },
                        {
                            type: 'metric',
                            description: 'CPU efficiency',
                            value: (pod.actualUsage.cpu / pod.requests.cpu) * 100,
                            threshold: 70,
                            unit: '%'
                        },
                        {
                            type: 'metric',
                            description: 'Memory efficiency',
                            value: (pod.actualUsage.memory / pod.requests.memory) * 100,
                            threshold: 70,
                            unit: '%'
                        }
                    ];

                    results.push({
                        id: `resource-efficiency-${pod.podName}`,
                        type: WasteType.POOR_UNIT_ECONOMICS,
                        severity: this.determineSeverity(monthlyWaste),
                        description: `Pod ${pod.podName} has low resource efficiency: ${(pod.efficiency * 100).toFixed(1)}% (wasted capacity: ${(wastedEfficiency * 100).toFixed(1)}%)`,
                        affectedResources: [{
                            id: pod.podName,
                            name: pod.podName,
                            type: 'Pod',
                            cloud: 'kubernetes',
                            tags: {
                                namespace: pod.namespace,
                                efficiency: `${(pod.efficiency * 100).toFixed(1)}%`,
                                cpuEfficiency: `${((pod.actualUsage.cpu / pod.requests.cpu) * 100).toFixed(1)}%`,
                                memoryEfficiency: `${((pod.actualUsage.memory / pod.requests.memory) * 100).toFixed(1)}%`
                            }
                        }],
                        wastedAmount: monthlyWaste,
                        confidence: UNIT_ECONOMICS_CONFIG.EFFICIENCY_CONFIDENCE,
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Analyze service-level efficiency
     */
    private async analyzeServiceEfficiency(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock service efficiency analysis
        const serviceEfficiencyMetrics = [
            {
                service: 'Database Cluster',
                totalCost: 1250.00,
                capacity: 100, // 100% capacity
                utilization: 45, // 45% utilized
                efficiency: 0.45,
                cloud: 'aws'
            },
            {
                service: 'Cache Layer',
                totalCost: 380.50,
                capacity: 100,
                utilization: 28,
                efficiency: 0.28,
                cloud: 'gcp'
            },
            {
                service: 'Load Balancer',
                totalCost: 165.75,
                capacity: 100,
                utilization: 62,
                efficiency: 0.62,
                cloud: 'azure'
            }
        ];

        for (const metric of serviceEfficiencyMetrics) {
            if (metric.efficiency < UNIT_ECONOMICS_CONFIG.MIN_EFFICIENCY_THRESHOLD && 
                metric.totalCost >= UNIT_ECONOMICS_CONFIG.MIN_MONTHLY_IMPACT) {
                
                const wastedEfficiency = 1 - metric.efficiency;
                const monthlyWaste = metric.totalCost * wastedEfficiency * 0.6; // 60% recoverable
                
                const evidence: Evidence[] = [
                    {
                        type: 'usage',
                        description: 'Service utilization',
                        value: metric.utilization,
                        threshold: UNIT_ECONOMICS_CONFIG.MIN_EFFICIENCY_THRESHOLD * 100,
                        unit: '%'
                    },
                    {
                        type: 'billing',
                        description: 'Monthly service cost',
                        value: metric.totalCost,
                        threshold: UNIT_ECONOMICS_CONFIG.MIN_MONTHLY_IMPACT,
                        unit: 'USD'
                    },
                    {
                        type: 'metric',
                        description: 'Efficiency score',
                        value: metric.efficiency * 100,
                        threshold: UNIT_ECONOMICS_CONFIG.MIN_EFFICIENCY_THRESHOLD * 100,
                        unit: '%'
                    }
                ];

                results.push({
                    id: `service-efficiency-${metric.service.toLowerCase().replace(/\s+/g, '-')}`,
                    type: WasteType.POOR_UNIT_ECONOMICS,
                    severity: this.determineSeverity(monthlyWaste),
                    description: `${metric.service} shows poor efficiency: ${metric.utilization}% utilization with ${(wastedEfficiency * 100).toFixed(1)}% wasted capacity`,
                    affectedResources: [{
                        id: metric.service.toLowerCase().replace(/\s+/g, '-'),
                        name: metric.service,
                        type: 'Service',
                        cloud: metric.cloud as 'aws' | 'gcp' | 'azure',
                        tags: {
                            utilization: `${metric.utilization}%`,
                            efficiency: `${(metric.efficiency * 100).toFixed(1)}%`,
                            wastedCapacity: `${(wastedEfficiency * 100).toFixed(1)}%`
                        }
                    }],
                    wastedAmount: monthlyWaste,
                    confidence: UNIT_ECONOMICS_CONFIG.EFFICIENCY_CONFIDENCE,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Calculate confidence for unit economics analysis
     */
    private calculateUnitEconomicsConfidence(sampleSize: number, efficiencyRatio: number): number {
        // Higher confidence for larger sample sizes and clearer efficiency gaps
        const sampleScore = Math.min(1, sampleSize / 10000);
        const efficiencyScore = Math.min(1, (1 - efficiencyRatio) * 2); // Amplify efficiency gaps
        
        return Math.min(0.95, UNIT_ECONOMICS_CONFIG.EFFICIENCY_CONFIDENCE + (sampleScore * 0.05) + (efficiencyScore * 0.05));
    }

    /**
     * Determine severity based on monthly cost impact
     */
    private determineSeverity(impact: number): 'low' | 'medium' | 'high' | 'critical' {
        if (impact >= 400) return 'critical';
        if (impact >= 200) return 'high';
        if (impact >= 100) return 'medium';
        return 'low';
    }

    /**
     * Get unit economics summary
     */
    async getUnitEconomicsSummary(): Promise<{
        totalInefficiencies: number;
        totalMonthlyImpact: number;
        averageEfficiency: number;
        worstPerformers: Array<{
            name: string;
            efficiency: number;
            impact: number;
        }>;
        benchmarkComparison: {
            aboveBenchmark: number;
            belowBenchmark: number;
            onTarget: number;
        };
    }> {
        const analysis = await this.analyzeUnitEconomics();
        
        const summary = {
            totalInefficiencies: analysis.length,
            totalMonthlyImpact: analysis.reduce((sum, a) => sum + a.wastedAmount, 0),
            averageEfficiency: 0,
            worstPerformers: [] as Array<{ name: string; efficiency: number; impact: number; }>,
            benchmarkComparison: {
                aboveBenchmark: 0,
                belowBenchmark: 0,
                onTarget: 0
            }
        };

        // Extract efficiency data from analysis results
        const efficiencies = analysis
            .map(a => {
                const efficiencyTag = a.affectedResources[0]?.tags?.efficiency;
                return efficiencyTag ? parseFloat(efficiencyTag.replace('%', '')) / 100 : 0;
            })
            .filter(e => e > 0);

        summary.averageEfficiency = efficiencies.length > 0 ? 
            efficiencies.reduce((sum, e) => sum + e, 0) / efficiencies.length : 0;

        // Get worst performers
        summary.worstPerformers = analysis
            .sort((a, b) => b.wastedAmount - a.wastedAmount)
            .slice(0, 5)
            .map(a => ({
                name: a.affectedResources[0]?.name || 'Unknown',
                efficiency: efficiencies[0] || 0,
                impact: a.wastedAmount
            }));

        // Benchmark comparison (mock data)
        summary.benchmarkComparison = {
            aboveBenchmark: Math.floor(analysis.length * 0.2),
            belowBenchmark: analysis.length - Math.floor(analysis.length * 0.2),
            onTarget: 0
        };

        return summary;
    }
}
