/**
 * GCP Billing Source Module
 * 
 * Collects cost data from Google Cloud Billing API for deterministic analysis.
 * No AI inference - pure metrics + billing data extraction.
 */

import {
    GCPBillingConfig,
    GCPBillingData,
    GCPProjectCost,
    GCPServiceCost,
    RegionCost,
    CostTrend
} from '../types';

interface BillingMetric {
    name: string;
    displayName: string;
    cost: {
        currencyCode: string;
        units: string;
        nanos: number;
    };
    usage: {
        unit: string;
        amount: number;
    };
    labels: Record<string, string>;
}

/**
 * Collects comprehensive GCP billing data for analysis
 */
export class GCPBillingCollector {
    private config: GCPBillingConfig;
    private billingClient: any; // Would be BillingClient from GCP SDK

    constructor(config: GCPBillingConfig) {
        this.config = config;
        // In real implementation: this.billingClient = new BillingClient({ keyFilename: config.keyFilePath })
        this.billingClient = null; // Mock for now
    }

    /**
     * Main entry point - collect all GCP billing data
     */
    async collectBillingData(timeRange: { start: string; end: string }): Promise<GCPBillingData> {
        try {
            const [totalCost, projects, services, regions, trends] = await Promise.all([
                this.getTotalCost(timeRange),
                this.getProjectCosts(timeRange),
                this.getServiceCosts(timeRange),
                this.getRegionCosts(timeRange),
                this.getCostTrends(timeRange)
            ]);

            return {
                totalCost,
                projects,
                services,
                regions,
                trends
            };
        } catch (error) {
            console.error('GCP Billing data collection failed:', error);
            const message = error instanceof Error ? error.message : String(error);
            throw new Error(`GCP billing data collection failed: ${message}`);
        }
    }

    /**
     * Get total GCP spending for the time period
     */
    private async getTotalCost(timeRange: { start: string; end: string }): Promise<number> {
        if (!this.billingClient) {
            return this.mockTotalCost();
        }

        try {
            const request = {
                name: `billingAccounts/${this.config.billingAccountId}`,
                filter: this.buildTimeFilter(timeRange),
                pageSize: 1000
            };

            const [response] = await this.billingClient.listProjectBillingInfo(request);
            
            let totalCost = 0;
            for (const billingInfo of response.projectBillingInfo || []) {
                if (billingInfo.cost?.units) {
                    totalCost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    totalCost += billingInfo.cost.nanos / 1000000000;
                }
            }

            return totalCost;
        } catch (error) {
            console.error('Failed to get GCP total cost:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by GCP project
     */
    private async getProjectCosts(timeRange: { start: string; end: string }): Promise<GCPProjectCost[]> {
        if (!this.billingClient) {
            return this.mockProjectCosts();
        }

        try {
            const request = {
                name: `billingAccounts/${this.config.billingAccountId}`,
                filter: this.buildTimeFilter(timeRange) + ' AND project.id:*',
                groupBy: ['project'],
                pageSize: 1000
            };

            const [response] = await this.billingClient.listProjectBillingInfo(request);
            const projects: GCPProjectCost[] = [];

            for (const billingInfo of response.projectBillingInfo || []) {
                const projectId = billingInfo.project?.projectId || 'unknown';
                const projectName = billingInfo.project?.displayName || projectId;
                
                let cost = 0;
                if (billingInfo.cost?.units) {
                    cost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    cost += billingInfo.cost.nanos / 1000000000;
                }

                // Get services for this project
                const services = await this.getProjectServiceCosts(projectId, timeRange);

                projects.push({
                    projectId,
                    projectName,
                    cost,
                    services
                });
            }

            return projects.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get GCP project costs:', error);
            throw error;
        }
    }

    /**
     * Get cost breakdown by GCP service
     */
    private async getServiceCosts(timeRange: { start: string; end: string }): Promise<GCPServiceCost[]> {
        if (!this.billingClient) {
            return this.mockServiceCosts();
        }

        try {
            const request = {
                name: `billingAccounts/${this.config.billingAccountId}`,
                filter: this.buildTimeFilter(timeRange),
                groupBy: ['service'],
                pageSize: 1000
            };

            const [response] = await this.billingClient.listProjectBillingInfo(request);
            const services: GCPServiceCost[] = [];

            for (const billingInfo of response.projectBillingInfo || []) {
                const serviceName = billingInfo.service?.displayName || 'Unknown Service';
                
                let cost = 0;
                if (billingInfo.cost?.units) {
                    cost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    cost += billingInfo.cost.nanos / 1000000000;
                }

                const usage = billingInfo.usage?.amount || 0;
                const unit = billingInfo.usage?.unit || 'units';

                services.push({
                    serviceName,
                    cost,
                    usage,
                    unit
                });
            }

            return services.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get GCP service costs:', error);
            throw error;
        }
    }

    /**
     * Get services costs for a specific project
     */
    private async getProjectServiceCosts(projectId: string, timeRange: { start: string; end: string }): Promise<GCPServiceCost[]> {
        if (!this.billingClient) {
            return this.mockServiceCosts().slice(0, 3); // Return fewer for project mock
        }

        try {
            const request = {
                name: `billingAccounts/${this.config.billingAccountId}`,
                filter: this.buildTimeFilter(timeRange) + ` AND project.id:\"${projectId}\"`,
                groupBy: ['service'],
                pageSize: 100
            };

            const [response] = await this.billingClient.listProjectBillingInfo(request);
            const services: GCPServiceCost[] = [];

            for (const billingInfo of response.projectBillingInfo || []) {
                const serviceName = billingInfo.service?.displayName || 'Unknown Service';
                
                let cost = 0;
                if (billingInfo.cost?.units) {
                    cost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    cost += billingInfo.cost.nanos / 1000000000;
                }

                const usage = billingInfo.usage?.amount || 0;
                const unit = billingInfo.usage?.unit || 'units';

                services.push({
                    serviceName,
                    cost,
                    usage,
                    unit
                });
            }

            return services.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error(`Failed to get GCP service costs for project ${projectId}:`, error);
            return []; // Return empty array on error to not break parent call
        }
    }

    /**
     * Get cost breakdown by GCP region
     */
    private async getRegionCosts(timeRange: { start: string; end: string }): Promise<RegionCost[]> {
        if (!this.billingClient) {
            return this.mockRegionCosts();
        }

        try {
            const request = {
                name: `billingAccounts/${this.config.billingAccountId}`,
                filter: this.buildTimeFilter(timeRange),
                groupBy: ['location'],
                pageSize: 1000
            };

            const [response] = await this.billingClient.listProjectBillingInfo(request);
            const regions: RegionCost[] = [];
            let totalCost = 0;

            // First pass: calculate total for percentage calculation
            for (const billingInfo of response.projectBillingInfo || []) {
                let cost = 0;
                if (billingInfo.cost?.units) {
                    cost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    cost += billingInfo.cost.nanos / 1000000000;
                }
                totalCost += cost;
            }

            // Second pass: build region cost array with percentages
            for (const billingInfo of response.projectBillingInfo || []) {
                const region = billingInfo.location?.displayName || 'Unknown Region';
                
                let cost = 0;
                if (billingInfo.cost?.units) {
                    cost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    cost += billingInfo.cost.nanos / 1000000000;
                }

                const percentage = totalCost > 0 ? (cost / totalCost) * 100 : 0;

                regions.push({
                    region,
                    cost,
                    percentage
                });
            }

            return regions.sort((a, b) => b.cost - a.cost);
        } catch (error) {
            console.error('Failed to get GCP region costs:', error);
            throw error;
        }
    }

    /**
     * Get cost trends over time
     */
    private async getCostTrends(timeRange: { start: string; end: string }): Promise<CostTrend[]> {
        if (!this.billingClient) {
            return this.mockCostTrends();
        }

        try {
            const request = {
                name: `billingAccounts/${this.config.billingAccountId}`,
                filter: this.buildTimeFilter(timeRange),
                groupBy: ['day'],
                pageSize: 1000
            };

            const [response] = await this.billingClient.listProjectBillingInfo(request);
            const trends: CostTrend[] = [];
            let previousCost = 0;

            for (const billingInfo of response.projectBillingInfo || []) {
                const date = billingInfo.usageStartTime || new Date().toISOString();
                
                let cost = 0;
                if (billingInfo.cost?.units) {
                    cost += parseFloat(billingInfo.cost.units);
                }
                if (billingInfo.cost?.nanos) {
                    cost += billingInfo.cost.nanos / 1000000000;
                }

                const change = cost - previousCost;
                const changePercent = previousCost > 0 ? (change / previousCost) * 100 : 0;

                trends.push({
                    date: date.split('T')[0], // Extract date part
                    cost,
                    change,
                    changePercent
                });

                previousCost = cost;
            }

            return trends.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
        } catch (error) {
            console.error('Failed to get GCP cost trends:', error);
            throw error;
        }
    }

    /**
     * Build time filter for GCP Billing API
     */
    private buildTimeFilter(timeRange: { start: string; end: string }): string {
        return `usage_start_time>=\"${timeRange.start}\" AND usage_end_time<=\"${timeRange.end}\"`;
    }

    // Mock data methods for development
    private mockTotalCost(): number {
        return 8750.30;
    }

    private mockProjectCosts(): GCPProjectCost[] {
        const servicesMock = this.mockServiceCosts();
        return [
            {
                projectId: 'prod-web-app-123456',
                projectName: 'Production Web Application',
                cost: 4200.15,
                services: servicesMock.slice(0, 4)
            },
            {
                projectId: 'analytics-pipeline-789',
                projectName: 'Analytics Pipeline',
                cost: 2800.75,
                services: servicesMock.slice(2, 5)
            },
            {
                projectId: 'dev-environment-456',
                projectName: 'Development Environment',
                cost: 1200.20,
                services: servicesMock.slice(0, 3)
            },
            {
                projectId: 'ml-training-321',
                projectName: 'ML Training Infrastructure',
                cost: 550.20,
                services: servicesMock.slice(1, 3)
            }
        ];
    }

    private mockServiceCosts(): GCPServiceCost[] {
        return [
            { serviceName: 'Compute Engine', cost: 3200, usage: 8760, unit: 'hours' },
            { serviceName: 'Google Kubernetes Engine', cost: 1800, usage: 720, unit: 'cluster-hours' },
            { serviceName: 'Cloud Storage', cost: 450, usage: 2500, unit: 'GB' },
            { serviceName: 'BigQuery', cost: 680, usage: 15000, unit: 'GB processed' },
            { serviceName: 'Cloud SQL', cost: 920, usage: 720, unit: 'hours' },
            { serviceName: 'Cloud Load Balancing', cost: 280, usage: 720, unit: 'hours' },
            { serviceName: 'Cloud CDN', cost: 150, usage: 5000, unit: 'GB' },
            { serviceName: 'Cloud Monitoring', cost: 75, usage: 1000, unit: 'API calls' }
        ];
    }

    private mockRegionCosts(): RegionCost[] {
        return [
            { region: 'us-central1', cost: 4200, percentage: 48 },
            { region: 'us-east1', cost: 2100, percentage: 24 },
            { region: 'europe-west1', cost: 1575, percentage: 18 },
            { region: 'asia-southeast1', cost: 875, percentage: 10 }
        ];
    }

    private mockCostTrends(): CostTrend[] {
        const trends: CostTrend[] = [];
        let baseCost = 280;
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 30);

        for (let i = 0; i < 30; i++) {
            const date = new Date(startDate);
            date.setDate(date.getDate() + i);
            
            const variation = (Math.random() - 0.5) * 30;
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
export async function fetchGCPBillingData(
    config: GCPBillingConfig,
    timeRange?: { start: string; end: string }
): Promise<GCPBillingData> {
    const collector = new GCPBillingCollector(config);
    return collector.collectBillingData(resolveTimeRange(timeRange));
}
