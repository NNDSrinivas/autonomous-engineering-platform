/**
 * Azure Cost Management Source Module
 * 
 * Collects cost data from Azure Cost Management API for deterministic analysis.
 * No AI inference - pure metrics + billing data extraction.
 */

import { 
    AzureCostConfig,
    AzureCostData, 
    AzureSubscriptionCost, 
    AzureResourceGroupCost, 
    AzureResourceCost,
    AzureServiceCost, 
    CostTrend 
} from '../types';

interface AzureUsageDetail {
    instanceName: string;
    resourceName: string;
    resourceType: string;
    resourceGroupName: string;
    cost: number;
    usageQuantity: number;
    unit: string;
    date: string;
    meterName: string;
    serviceFamily: string;
    location: string;
}

/**
 * Collects comprehensive Azure cost data for analysis
 */
export class AzureCostCollector {
    private config: AzureCostConfig;
    private consumptionClient: any; // Would be ConsumptionManagementClient from Azure SDK
    private resourceClient: any; // Would be ResourceManagementClient from Azure SDK

    constructor(config: AzureCostConfig) {
        this.config = config;
        // In real implementation: 
        // this.consumptionClient = new ConsumptionManagementClient(credentials, config.subscriptionId)
        // this.resourceClient = new ResourceManagementClient(credentials, config.subscriptionId)
        this.consumptionClient = null; // Mock for now
        this.resourceClient = null; // Mock for now
    }

    /**
     * Main entry point - collect all Azure cost data
     */
    async collectCostData(timeRange: { start: string; end: string }): Promise<AzureCostData> {
        try {
            const [totalCost, subscriptions, resourceGroups, services, trends] = await Promise.all([
                this.getTotalCost(timeRange),
                this.getSubscriptionCosts(timeRange),
                this.getResourceGroupCosts(timeRange),
                this.getServiceCosts(timeRange),
                this.getCostTrends(timeRange)
            ]);

            return {
                totalCost,
                subscriptions,
                resourceGroups,
                services,
                trends
            };
        } catch (error) {
            console.error('Azure Cost data collection failed:', error);
            const message = error instanceof Error ? error.message : String(error);
            throw new Error(`Azure cost data collection failed: ${message}`);
        }
    }

    /**
     * Get total Azure spending for the time period
     */
    private async getTotalCost(timeRange: { start: string; end: string }): Promise<number> {
        if (!this.consumptionClient) {
            return this.mockTotalCost();
        }

        try {
            const scope = `/subscriptions/${this.config.subscriptionId}`;
            const filter = `properties/usageStart ge '${timeRange.start}' and properties/usageEnd le '${timeRange.end}'`;
            
            const usageDetails = await this.consumptionClient.usageDetails.list(scope, {
                filter,
                expand: 'properties/meterDetails'
            });

            let totalCost = 0;
            for await (const usage of usageDetails) {
                totalCost += usage.cost || 0;
            }

            return totalCost;
        } catch (error) {
            console.error('Failed to get Azure total cost:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by Azure subscription
     */
    private async getSubscriptionCosts(timeRange: { start: string; end: string }): Promise<AzureSubscriptionCost[]> {
        if (!this.consumptionClient) {
            return this.mockSubscriptionCosts();
        }

        try {
            // In a real multi-subscription environment, you would iterate through all subscriptions
            // For now, we'll assume single subscription
            const scope = `/subscriptions/${this.config.subscriptionId}`;
            const filter = `properties/usageStart ge '${timeRange.start}' and properties/usageEnd le '${timeRange.end}'`;
            
            const usageDetails = await this.consumptionClient.usageDetails.list(scope, {
                filter,
                expand: 'properties/meterDetails'
            });

            let totalCost = 0;
            const resourceGroups = await this.getResourceGroupCosts(timeRange);

            for await (const usage of usageDetails) {
                totalCost += usage.cost || 0;
            }

            // Get subscription name (would come from Azure SDK)
            const subscriptionName = 'Production Subscription'; // Mock

            return [{
                subscriptionId: this.config.subscriptionId,
                subscriptionName,
                cost: totalCost,
                resourceGroups
            }];
        } catch (error) {
            console.error('Failed to get Azure subscription costs:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by Azure resource group
     */
    private async getResourceGroupCosts(timeRange: { start: string; end: string }): Promise<AzureResourceGroupCost[]> {
        if (!this.consumptionClient) {
            return this.mockResourceGroupCosts();
        }

        try {
            const scope = `/subscriptions/${this.config.subscriptionId}`;
            const filter = `properties/usageStart ge '${timeRange.start}' and properties/usageEnd le '${timeRange.end}'`;
            
            const usageDetails = await this.consumptionClient.usageDetails.list(scope, {
                filter,
                expand: 'properties/meterDetails'
            });

            const resourceGroupMap = new Map<string, { cost: number; resources: AzureResourceCost[] }>();

            for await (const usage of usageDetails) {
                const resourceGroupName = usage.resourceGroup || 'Unknown';
                const cost = usage.cost || 0;

                if (!resourceGroupMap.has(resourceGroupName)) {
                    resourceGroupMap.set(resourceGroupName, { cost: 0, resources: [] });
                }

                const group = resourceGroupMap.get(resourceGroupName)!;
                group.cost += cost;

                // Add resource details
                group.resources.push({
                    resourceName: usage.resourceName || 'Unknown',
                    resourceType: usage.resourceType || 'Unknown',
                    cost: cost,
                    usage: usage.usageQuantity || 0
                });
            }

            const resourceGroups: AzureResourceGroupCost[] = [];
            for (const [resourceGroupName, data] of resourceGroupMap) {
                resourceGroups.push({
                    resourceGroupName,
                    cost: data.cost,
                    resources: data.resources.sort((a, b) => b.cost - a.cost)
                });
            }

            return resourceGroups.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get Azure resource group costs:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by Azure service
     */
    private async getServiceCosts(timeRange: { start: string; end: string }): Promise<AzureServiceCost[]> {
        if (!this.consumptionClient) {
            return this.mockServiceCosts();
        }

        try {
            const scope = `/subscriptions/${this.config.subscriptionId}`;
            const filter = `properties/usageStart ge '${timeRange.start}' and properties/usageEnd le '${timeRange.end}'`;
            
            const usageDetails = await this.consumptionClient.usageDetails.list(scope, {
                filter,
                expand: 'properties/meterDetails'
            });

            const serviceMap = new Map<string, { cost: number; usage: number; unit: string }>();

            for await (const usage of usageDetails) {
                const serviceName = this.extractServiceName(usage.meterName, usage.serviceFamily);
                const cost = usage.cost || 0;
                const usageQuantity = usage.usageQuantity || 0;
                const unit = usage.unit || 'units';

                if (!serviceMap.has(serviceName)) {
                    serviceMap.set(serviceName, { cost: 0, usage: 0, unit });
                }

                const service = serviceMap.get(serviceName)!;
                service.cost += cost;
                service.usage += usageQuantity;
            }

            const services: AzureServiceCost[] = [];
            for (const [serviceName, data] of serviceMap) {
                services.push({
                    serviceName,
                    cost: data.cost,
                    usage: data.usage,
                    unit: data.unit
                });
            }

            return services.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get Azure service costs:', error);
            throw error;
        }
    }

    /**
     * Get cost trends over time
     */
    private async getCostTrends(timeRange: { start: string; end: string }): Promise<CostTrend[]> {
        if (!this.consumptionClient) {
            return this.mockCostTrends();
        }

        try {
            const scope = `/subscriptions/${this.config.subscriptionId}`;
            const filter = `properties/usageStart ge '${timeRange.start}' and properties/usageEnd le '${timeRange.end}'`;
            
            const usageDetails = await this.consumptionClient.usageDetails.list(scope, {
                filter,
                expand: 'properties/meterDetails'
            });

            const dailyMap = new Map<string, number>();

            for await (const usage of usageDetails) {
                const date = new Date(usage.date).toISOString().split('T')[0];
                const cost = usage.cost || 0;

                if (!dailyMap.has(date)) {
                    dailyMap.set(date, 0);
                }
                dailyMap.set(date, dailyMap.get(date)! + cost);
            }

            const trends: CostTrend[] = [];
            const sortedDates = Array.from(dailyMap.keys()).sort();
            let previousCost = 0;

            for (const date of sortedDates) {
                const cost = dailyMap.get(date)!;
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
            console.error('Failed to get Azure cost trends:', error);
            throw error;
        }
    }

    /**
     * Extract service name from meter information
     */
    private extractServiceName(meterName: string, serviceFamily: string): string {
        if (serviceFamily) {
            return serviceFamily;
        }
        
        if (meterName) {
            // Extract service from meter name patterns
            if (meterName.toLowerCase().includes('compute')) return 'Virtual Machines';
            if (meterName.toLowerCase().includes('storage')) return 'Storage';
            if (meterName.toLowerCase().includes('sql')) return 'SQL Database';
            if (meterName.toLowerCase().includes('app service')) return 'App Service';
            if (meterName.toLowerCase().includes('bandwidth')) return 'Bandwidth';
            if (meterName.toLowerCase().includes('cosmos')) return 'Cosmos DB';
        }
        
        return 'Unknown Service';
    }

    // Mock data methods for development
    private mockTotalCost(): number {
        return 15250.80;
    }

    private mockSubscriptionCosts(): AzureSubscriptionCost[] {
        return [{
            subscriptionId: this.config.subscriptionId,
            subscriptionName: 'Production Subscription',
            cost: 15250.80,
            resourceGroups: this.mockResourceGroupCosts()
        }];
    }

    private mockResourceGroupCosts(): AzureResourceGroupCost[] {
        return [
            {
                resourceGroupName: 'prod-web-rg',
                cost: 8500.25,
                resources: [
                    { resourceName: 'prod-web-vm1', resourceType: 'Microsoft.Compute/virtualMachines', cost: 2400.15, usage: 720 },
                    { resourceName: 'prod-web-vm2', resourceType: 'Microsoft.Compute/virtualMachines', cost: 2400.15, usage: 720 },
                    { resourceName: 'prod-web-lb', resourceType: 'Microsoft.Network/loadBalancers', cost: 180.50, usage: 720 },
                    { resourceName: 'prod-storage', resourceType: 'Microsoft.Storage/storageAccounts', cost: 350.80, usage: 1000 },
                    { resourceName: 'prod-sql', resourceType: 'Microsoft.Sql/servers/databases', cost: 3168.65, usage: 720 }
                ]
            },
            {
                resourceGroupName: 'analytics-rg',
                cost: 4200.30,
                resources: [
                    { resourceName: 'analytics-vm', resourceType: 'Microsoft.Compute/virtualMachines', cost: 1800.20, usage: 720 },
                    { resourceName: 'data-storage', resourceType: 'Microsoft.Storage/storageAccounts', cost: 850.40, usage: 2500 },
                    { resourceName: 'cosmos-analytics', resourceType: 'Microsoft.DocumentDB/databaseAccounts', cost: 1549.70, usage: 500 }
                ]
            },
            {
                resourceGroupName: 'dev-rg',
                cost: 1800.15,
                resources: [
                    { resourceName: 'dev-vm', resourceType: 'Microsoft.Compute/virtualMachines', cost: 960.80, usage: 720 },
                    { resourceName: 'dev-storage', resourceType: 'Microsoft.Storage/storageAccounts', cost: 120.45, usage: 200 },
                    { resourceName: 'dev-sql', resourceType: 'Microsoft.Sql/servers/databases', cost: 718.90, usage: 720 }
                ]
            },
            {
                resourceGroupName: 'monitoring-rg',
                cost: 750.10,
                resources: [
                    { resourceName: 'log-analytics', resourceType: 'Microsoft.OperationalInsights/workspaces', cost: 450.60, usage: 100 },
                    { resourceName: 'app-insights', resourceType: 'Microsoft.Insights/components', cost: 299.50, usage: 1000 }
                ]
            }
        ];
    }

    private mockServiceCosts(): AzureServiceCost[] {
        return [
            { serviceName: 'Virtual Machines', cost: 5160.15, usage: 2160, unit: 'hours' },
            { serviceName: 'SQL Database', cost: 3887.55, usage: 1440, unit: 'hours' },
            { serviceName: 'Cosmos DB', cost: 1549.70, usage: 500, unit: 'RU/s' },
            { serviceName: 'Storage', cost: 1321.65, usage: 3700, unit: 'GB' },
            { serviceName: 'App Service', cost: 850.40, usage: 720, unit: 'hours' },
            { serviceName: 'Log Analytics', cost: 450.60, usage: 100, unit: 'GB' },
            { serviceName: 'Application Insights', cost: 299.50, usage: 1000, unit: 'GB' },
            { serviceName: 'Load Balancer', cost: 180.50, usage: 720, unit: 'hours' },
            { serviceName: 'Bandwidth', cost: 125.75, usage: 500, unit: 'GB' }
        ];
    }

    private mockCostTrends(): CostTrend[] {
        const trends: CostTrend[] = [];
        let baseCost = 490;
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 30);

        for (let i = 0; i < 30; i++) {
            const date = new Date(startDate);
            date.setDate(date.getDate() + i);
            
            const variation = (Math.random() - 0.5) * 40;
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
export async function fetchAzureCostData(
    config: AzureCostConfig,
    timeRange?: { start: string; end: string }
): Promise<AzureCostData> {
    const collector = new AzureCostCollector(config);
    return collector.collectCostData(resolveTimeRange(timeRange));
}
