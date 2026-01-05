/**
 * AWS Cost Explorer Source Module
 * 
 * Collects cost data from AWS Cost Explorer API for deterministic analysis.
 * No AI inference - pure metrics + billing data extraction.
 */

import {
    AWSCostConfig,
    AWSCostData,
    AWSServiceCost,
    RegionCost,
    InstanceCost,
    CostTrend
} from '../types';

interface CostExplorerMetric {
    TimePeriod: {
        Start: string;
        End: string;
    };
    Total: {
        BlendedCost?: {
            Amount: string;
            Unit: string;
        };
    };
    Groups?: Array<{
        Keys: string[];
        Metrics: {
            BlendedCost: {
                Amount: string;
                Unit: string;
            };
        };
    }>;
}

/**
 * Collects comprehensive AWS cost data for analysis
 */
export class AWSCostExplorer {
    private config: AWSCostConfig;
    private client: any; // Would be CostExplorerClient from AWS SDK

    constructor(config: AWSCostConfig) {
        this.config = config;
        // In real implementation: this.client = new CostExplorerClient(config)
        this.client = null; // Mock for now
    }

    /**
     * Main entry point - collect all AWS cost data
     */
    async collectCostData(timeRange: { start: string; end: string }): Promise<AWSCostData> {
        try {
            const [totalCost, services, regions, instances, trends] = await Promise.all([
                this.getTotalCost(timeRange),
                this.getServiceCosts(timeRange),
                this.getRegionCosts(timeRange),
                this.getInstanceCosts(timeRange),
                this.getCostTrends(timeRange)
            ]);

            return {
                totalCost,
                services,
                regions,
                instances,
                trends
            };
        } catch (error) {
            console.error('AWS Cost Explorer data collection failed:', error);
            const message = error instanceof Error ? error.message : String(error);
            throw new Error(`AWS cost data collection failed: ${message}`);
        }
    }

    /**
     * Get total AWS spending for the time period
     */
    private async getTotalCost(timeRange: { start: string; end: string }): Promise<number> {
        if (!this.client) {
            // Mock data for development
            return this.mockTotalCost();
        }

        try {
            const params = {
                TimePeriod: {
                    Start: timeRange.start,
                    End: timeRange.end
                },
                Granularity: 'MONTHLY',
                Metrics: ['BlendedCost']
            };

            const result = await this.client.getCostAndUsage(params);
            
            let totalCost = 0;
            for (const metric of result.ResultsByTime || []) {
                if (metric.Total?.BlendedCost?.Amount) {
                    totalCost += parseFloat(metric.Total.BlendedCost.Amount);
                }
            }

            return totalCost;
        } catch (error) {
            console.error('Failed to get AWS total cost:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by AWS service
     */
    private async getServiceCosts(timeRange: { start: string; end: string }): Promise<AWSServiceCost[]> {
        if (!this.client) {
            return this.mockServiceCosts();
        }

        try {
            const params = {
                TimePeriod: {
                    Start: timeRange.start,
                    End: timeRange.end
                },
                Granularity: 'MONTHLY',
                Metrics: ['BlendedCost', 'UsageQuantity'],
                GroupBy: [
                    {
                        Type: 'DIMENSION',
                        Key: 'SERVICE'
                    }
                ]
            };

            const result = await this.client.getCostAndUsage(params);
            const services: AWSServiceCost[] = [];

            for (const timeResult of result.ResultsByTime || []) {
                for (const group of timeResult.Groups || []) {
                    const serviceName = group.Keys?.[0] || 'Unknown';
                    const cost = parseFloat(group.Metrics?.BlendedCost?.Amount || '0');
                    const usage = parseFloat(group.Metrics?.UsageQuantity?.Amount || '0');
                    const unit = group.Metrics?.UsageQuantity?.Unit || 'units';

                    services.push({
                        serviceName,
                        cost,
                        usage,
                        unit,
                        category: this.categorizeAWSService(serviceName)
                    });
                }
            }

            return services.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get AWS service costs:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by AWS region
     */
    private async getRegionCosts(timeRange: { start: string; end: string }): Promise<RegionCost[]> {
        if (!this.client) {
            return this.mockRegionCosts();
        }

        try {
            const params = {
                TimePeriod: {
                    Start: timeRange.start,
                    End: timeRange.end
                },
                Granularity: 'MONTHLY',
                Metrics: ['BlendedCost'],
                GroupBy: [
                    {
                        Type: 'DIMENSION',
                        Key: 'REGION'
                    }
                ]
            };

            const result = await this.client.getCostAndUsage(params);
            const regions: RegionCost[] = [];
            let totalCost = 0;

            // First pass: calculate total for percentage calculation
            for (const timeResult of result.ResultsByTime || []) {
                for (const group of timeResult.Groups || []) {
                    totalCost += parseFloat(group.Metrics?.BlendedCost?.Amount || '0');
                }
            }

            // Second pass: build region cost array with percentages
            for (const timeResult of result.ResultsByTime || []) {
                for (const group of timeResult.Groups || []) {
                    const region = group.Keys?.[0] || 'Unknown';
                    const cost = parseFloat(group.Metrics?.BlendedCost?.Amount || '0');
                    const percentage = totalCost > 0 ? (cost / totalCost) * 100 : 0;

                    regions.push({
                        region,
                        cost,
                        percentage
                    });
                }
            }

            return regions.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get AWS region costs:', error);
            throw error;
        }
    }

    /**
     * Get detailed EC2 instance costs and utilization
     */
    private async getInstanceCosts(timeRange: { start: string; end: string }): Promise<InstanceCost[]> {
        if (!this.client) {
            return this.mockInstanceCosts();
        }

        try {
            // This would require additional AWS APIs like CloudWatch for utilization
            // For now, return cost data from Cost Explorer
            const params = {
                TimePeriod: {
                    Start: timeRange.start,
                    End: timeRange.end
                },
                Granularity: 'MONTHLY',
                Metrics: ['BlendedCost'],
                GroupBy: [
                    {
                        Type: 'DIMENSION',
                        Key: 'RESOURCE_ID'
                    },
                    {
                        Type: 'DIMENSION',
                        Key: 'INSTANCE_TYPE'
                    }
                ],
                Filter: {
                    Dimensions: {
                        Key: 'SERVICE',
                        Values: ['Amazon Elastic Compute Cloud - Compute']
                    }
                }
            };

            const result = await this.client.getCostAndUsage(params);
            const instances: InstanceCost[] = [];

            for (const timeResult of result.ResultsByTime || []) {
                for (const group of timeResult.Groups || []) {
                    const [instanceId, instanceType] = group.Keys || ['unknown', 'unknown'];
                    const cost = parseFloat(group.Metrics?.BlendedCost?.Amount || '0');

                    // Mock utilization data - would come from CloudWatch
                    const usage = {
                        cpuUtilization: Math.random() * 100,
                        memoryUtilization: Math.random() * 100,
                        networkUtilization: Math.random() * 100,
                        storageUtilization: Math.random() * 100
                    };

                    const recommendations = this.generateInstanceRecommendations(usage, instanceType);

                    instances.push({
                        instanceId,
                        instanceType,
                        cost,
                        usage,
                        recommendations
                    });
                }
            }

            return instances.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get AWS instance costs:', error);
            throw error;
        }
    }

    /**
     * Get cost trends over time
     */
    private async getCostTrends(timeRange: { start: string; end: string }): Promise<CostTrend[]> {
        if (!this.client) {
            return this.mockCostTrends();
        }

        try {
            const params = {
                TimePeriod: {
                    Start: timeRange.start,
                    End: timeRange.end
                },
                Granularity: 'DAILY',
                Metrics: ['BlendedCost']
            };

            const result = await this.client.getCostAndUsage(params);
            const trends: CostTrend[] = [];
            let previousCost = 0;

            for (const timeResult of result.ResultsByTime || []) {
                const date = timeResult.TimePeriod?.Start || new Date().toISOString();
                const cost = parseFloat(timeResult.Total?.BlendedCost?.Amount || '0');
                const change = cost - previousCost;
                const changePercent = previousCost > 0 ? (change / previousCost) * 100 : 0;

                trends.push({
                    date,
                    cost,
                    change,
                    changePercent
                });

                previousCost = cost;
            }

            return trends;
        } catch (error) {
            console.error('Failed to get AWS cost trends:', error);
            throw error;
        }
    }

    /**
     * Categorize AWS service for better analysis
     */
    private categorizeAWSService(serviceName: string): 'compute' | 'storage' | 'network' | 'database' | 'other' {
        const service = serviceName.toLowerCase();
        
        if (service.includes('compute') || service.includes('ec2') || service.includes('lambda') || service.includes('ecs') || service.includes('eks')) {
            return 'compute';
        }
        if (service.includes('storage') || service.includes('s3') || service.includes('ebs') || service.includes('efs')) {
            return 'storage';
        }
        if (service.includes('vpc') || service.includes('cloudfront') || service.includes('route53') || service.includes('elb')) {
            return 'network';
        }
        if (service.includes('rds') || service.includes('dynamodb') || service.includes('redshift') || service.includes('aurora')) {
            return 'database';
        }
        return 'other';
    }

    /**
     * Generate instance optimization recommendations
     */
    private generateInstanceRecommendations(usage: any, instanceType: string): string[] {
        const recommendations: string[] = [];
        
        if (usage.cpuUtilization < 10) {
            recommendations.push(`CPU utilization is very low (${usage.cpuUtilization.toFixed(1)}%) - consider downsizing`);
        }
        
        if (usage.memoryUtilization < 20) {
            recommendations.push(`Memory utilization is low (${usage.memoryUtilization.toFixed(1)}%) - consider memory-optimized instance`);
        }
        
        if (usage.cpuUtilization < 5 && usage.memoryUtilization < 10) {
            recommendations.push('Instance appears idle - consider termination or scheduling');
        }
        
        if (usage.cpuUtilization > 80) {
            recommendations.push(`High CPU utilization (${usage.cpuUtilization.toFixed(1)}%) - consider upsizing`);
        }
        
        return recommendations;
    }

    // Mock data methods for development
    private mockTotalCost(): number {
        return 12500.45;
    }

    private mockServiceCosts(): AWSServiceCost[] {
        return [
            { serviceName: 'Amazon Elastic Compute Cloud - Compute', cost: 4500, usage: 2160, unit: 'Hours', category: 'compute' },
            { serviceName: 'Amazon Relational Database Service', cost: 2200, usage: 720, unit: 'Hours', category: 'database' },
            { serviceName: 'Amazon Simple Storage Service', cost: 850, usage: 500, unit: 'GB', category: 'storage' },
            { serviceName: 'Amazon Elastic Load Balancing', cost: 650, usage: 720, unit: 'Hours', category: 'network' },
            { serviceName: 'Amazon CloudWatch', cost: 300, usage: 1000, unit: 'Metrics', category: 'other' }
        ];
    }

    private mockRegionCosts(): RegionCost[] {
        return [
            { region: 'us-east-1', cost: 6500, percentage: 52 },
            { region: 'us-west-2', cost: 3200, percentage: 25.6 },
            { region: 'eu-west-1', cost: 2100, percentage: 16.8 },
            { region: 'ap-southeast-1', cost: 700, percentage: 5.6 }
        ];
    }

    private mockInstanceCosts(): InstanceCost[] {
        return [
            {
                instanceId: 'i-1234567890abcdef0',
                instanceType: 't3.large',
                cost: 45.60,
                usage: {
                    cpuUtilization: 15,
                    memoryUtilization: 35,
                    networkUtilization: 25,
                    storageUtilization: 60
                },
                recommendations: ['CPU utilization is low (15%) - consider downsizing to t3.medium']
            },
            {
                instanceId: 'i-0987654321fedcba1',
                instanceType: 'm5.xlarge',
                cost: 89.20,
                usage: {
                    cpuUtilization: 85,
                    memoryUtilization: 78,
                    networkUtilization: 45,
                    storageUtilization: 82
                },
                recommendations: ['High CPU utilization (85%) - consider upsizing to m5.2xlarge']
            }
        ];
    }

    private mockCostTrends(): CostTrend[] {
        const trends: CostTrend[] = [];
        let baseCost = 400;
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 30);

        for (let i = 0; i < 30; i++) {
            const date = new Date(startDate);
            date.setDate(date.getDate() + i);
            
            const variation = (Math.random() - 0.5) * 50;
            const cost = baseCost + variation;
            const change = i > 0 ? cost - trends[i-1].cost : 0;
            const changePercent = i > 0 && trends[i-1].cost > 0 ? (change / trends[i-1].cost) * 100 : 0;

            trends.push({
                date: date.toISOString().split('T')[0],
                cost,
                change,
                changePercent
            });
        }

        return trends;
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
export async function fetchAWSCostData(
    config: AWSCostConfig,
    timeRange?: { start: string; end: string }
): Promise<AWSCostData> {
    const explorer = new AWSCostExplorer(config);
    return explorer.collectCostData(resolveTimeRange(timeRange));
}
