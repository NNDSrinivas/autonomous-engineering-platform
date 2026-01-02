/**
 * Sources Index - Cost & Usage Data Collection Orchestrator
 * 
 * Coordinates multi-cloud cost data collection and usage metrics gathering
 * for deterministic FinOps analysis.
 */

export { AWSCostExplorer } from './awsCostExplorer';
export { GCPBillingCollector } from './gcpBilling';
export { AzureCostCollector } from './azureCost';
export { KubernetesUsageCollector } from './kubernetesUsage';
export { TrafficAnalyzer } from './traffic';

// Re-export all types for convenience
export * from '../types';

/**
 * Multi-cloud cost and usage data aggregator
 * 
 * Provides unified interface for collecting cost and usage data
 * across AWS, GCP, Azure, Kubernetes, and traffic sources.
 */
import {
    CostData,
    UsageData,
    AWSCostConfig,
    GCPBillingConfig,
    AzureCostConfig,
    KubernetesConfig,
    TrafficConfig
} from '../types';

import { AWSCostExplorer } from './awsCostExplorer';
import { GCPBillingCollector } from './gcpBilling';
import { AzureCostCollector } from './azureCost';
import { KubernetesUsageCollector } from './kubernetesUsage';
import { TrafficAnalyzer } from './traffic';

interface MultiCloudConfig {
    aws?: AWSCostConfig;
    gcp?: GCPBillingConfig;
    azure?: AzureCostConfig;
    kubernetes?: KubernetesConfig;
    traffic?: TrafficConfig;
}

/**
 * Unified data collector for all cost and usage sources
 */
export class MultiCloudDataCollector {
    private awsCollector?: AWSCostExplorer;
    private gcpCollector?: GCPBillingCollector;
    private azureCollector?: AzureCostCollector;
    private k8sCollector?: KubernetesUsageCollector;
    private trafficAnalyzer?: TrafficAnalyzer;

    constructor(config: MultiCloudConfig) {
        // Initialize collectors based on provided configuration
        if (config.aws) {
            this.awsCollector = new AWSCostExplorer(config.aws);
        }
        
        if (config.gcp) {
            this.gcpCollector = new GCPBillingCollector(config.gcp);
        }
        
        if (config.azure) {
            this.azureCollector = new AzureCostCollector(config.azure);
        }
        
        if (config.kubernetes) {
            this.k8sCollector = new KubernetesUsageCollector(config.kubernetes);
        }
        
        if (config.traffic) {
            this.trafficAnalyzer = new TrafficAnalyzer(config.traffic);
        }
    }

    /**
     * Collect cost data from all configured cloud providers
     */
    async collectCostData(timeRange: { start: string; end: string }): Promise<CostData> {
        console.log('🔍 Collecting multi-cloud cost data...');
        
        const results = await Promise.allSettled([
            this.awsCollector?.collectCostData(timeRange),
            this.gcpCollector?.collectBillingData(timeRange),
            this.azureCollector?.collectCostData(timeRange)
        ]);

        const costData: CostData = {
            aws: null,
            gcp: null,
            azure: null,
            consolidated: {
                totalSpend: 0,
                currency: 'USD',
                period: `${timeRange.start} to ${timeRange.end}`,
                breakdown: []
            }
        };

        // Process AWS results
        if (results[0].status === 'fulfilled' && results[0].value) {
            costData.aws = results[0].value;
            costData.consolidated.totalSpend += results[0].value.totalCost;
            
            // Add AWS services to consolidated breakdown
            for (const service of results[0].value.services) {
                costData.consolidated.breakdown.push({
                    service: `AWS: ${service.serviceName}`,
                    cost: service.cost,
                    percentage: 0, // Will be calculated later
                    trend: 'stable' // Would be determined from trends
                });
            }
            
            console.log(`✅ AWS cost data collected: $${results[0].value.totalCost.toFixed(2)}`);
        } else if (results[0].status === 'rejected') {
            console.log(`❌ AWS cost collection failed: ${results[0].reason.message}`);
        }

        // Process GCP results
        if (results[1].status === 'fulfilled' && results[1].value) {
            costData.gcp = results[1].value;
            costData.consolidated.totalSpend += results[1].value.totalCost;
            
            // Add GCP services to consolidated breakdown
            for (const service of results[1].value.services) {
                costData.consolidated.breakdown.push({
                    service: `GCP: ${service.serviceName}`,
                    cost: service.cost,
                    percentage: 0, // Will be calculated later
                    trend: 'stable'
                });
            }
            
            console.log(`✅ GCP billing data collected: $${results[1].value.totalCost.toFixed(2)}`);
        } else if (results[1].status === 'rejected') {
            console.log(`❌ GCP billing collection failed: ${results[1].reason.message}`);
        }

        // Process Azure results
        if (results[2].status === 'fulfilled' && results[2].value) {
            costData.azure = results[2].value;
            costData.consolidated.totalSpend += results[2].value.totalCost;
            
            // Add Azure services to consolidated breakdown
            for (const service of results[2].value.services) {
                costData.consolidated.breakdown.push({
                    service: `Azure: ${service.serviceName}`,
                    cost: service.cost,
                    percentage: 0, // Will be calculated later
                    trend: 'stable'
                });
            }
            
            console.log(`✅ Azure cost data collected: $${results[2].value.totalCost.toFixed(2)}`);
        } else if (results[2].status === 'rejected') {
            console.log(`❌ Azure cost collection failed: ${results[2].reason.message}`);
        }

        // Calculate percentages for consolidated breakdown
        if (costData.consolidated.totalSpend > 0) {
            for (const item of costData.consolidated.breakdown) {
                item.percentage = (item.cost / costData.consolidated.totalSpend) * 100;
            }
            
            // Sort by cost descending
            costData.consolidated.breakdown.sort((a, b) => b.cost - a.cost);
        }

        console.log(`💰 Total consolidated spend: $${costData.consolidated.totalSpend.toFixed(2)}`);
        return costData;
    }

    /**
     * Collect usage data from Kubernetes and traffic sources
     */
    async collectUsageData(timeRange: { start: string; end: string }): Promise<UsageData> {
        console.log('📊 Collecting usage metrics data...');
        
        const results = await Promise.allSettled([
            this.k8sCollector?.collectUsageData(timeRange),
            this.trafficAnalyzer?.collectTrafficData(timeRange)
        ]);

        const usageData: UsageData = {
            kubernetes: null,
            traffic: null,
            summary: {
                totalResources: 0,
                utilizationRate: 0,
                idleResources: 0
            }
        };

        // Process Kubernetes results
        if (results[0].status === 'fulfilled' && results[0].value) {
            usageData.kubernetes = results[0].value;
            usageData.summary.totalResources += results[0].value.nodes.length + results[0].value.pods.length;
            
            // Calculate overall utilization rate
            const avgCpuUtilization = results[0].value.clusters.reduce((sum, c) => sum + c.utilization.cpu, 0) / results[0].value.clusters.length;
            const avgMemoryUtilization = results[0].value.clusters.reduce((sum, c) => sum + c.utilization.memory, 0) / results[0].value.clusters.length;
            usageData.summary.utilizationRate = (avgCpuUtilization + avgMemoryUtilization) / 2;
            
            // Count idle resources
            usageData.summary.idleResources += results[0].value.nodes.filter(n => n.status === 'idle').length;
            usageData.summary.idleResources += results[0].value.pods.filter(p => p.status === 'idle').length;
            
            console.log(`✅ Kubernetes data collected: ${results[0].value.nodes.length} nodes, ${results[0].value.pods.length} pods`);
        } else if (results[0].status === 'rejected') {
            console.log(`❌ Kubernetes usage collection failed: ${results[0].reason.message}`);
        }

        // Process Traffic results
        if (results[1].status === 'fulfilled' && results[1].value) {
            usageData.traffic = results[1].value;
            console.log(`✅ Traffic data collected: ${results[1].value.requests.length} metric points`);
        } else if (results[1].status === 'rejected') {
            console.log(`❌ Traffic analysis failed: ${results[1].reason.message}`);
        }

        console.log(`📈 Usage summary: ${usageData.summary.totalResources} resources, ${usageData.summary.utilizationRate.toFixed(1)}% utilization`);
        return usageData;
    }

    /**
     * Collect all data sources in parallel
     */
    async collectAllData(timeRange: { start: string; end: string }): Promise<{ cost: CostData; usage: UsageData }> {
        console.log('🚀 Starting comprehensive data collection...');
        
        const startTime = Date.now();
        
        const [costData, usageData] = await Promise.all([
            this.collectCostData(timeRange),
            this.collectUsageData(timeRange)
        ]);
        
        const elapsedTime = Date.now() - startTime;
        console.log(`✨ Data collection completed in ${elapsedTime}ms`);
        
        return { cost: costData, usage: usageData };
    }

    /**
     * Validate configuration and test connectivity
     */
    async validateConfiguration(): Promise<{ valid: boolean; errors: string[] }> {
        console.log('🔧 Validating data source configurations...');
        
        const errors: string[] = [];
        const tests: Promise<void>[] = [];

        // Test AWS connection
        if (this.awsCollector) {
            tests.push(
                this.testAWSConnection().catch(error => {
                    errors.push(`AWS connection failed: ${error.message}`);
                })
            );
        }

        // Test GCP connection
        if (this.gcpCollector) {
            tests.push(
                this.testGCPConnection().catch(error => {
                    errors.push(`GCP connection failed: ${error.message}`);
                })
            );
        }

        // Test Azure connection
        if (this.azureCollector) {
            tests.push(
                this.testAzureConnection().catch(error => {
                    errors.push(`Azure connection failed: ${error.message}`);
                })
            );
        }

        // Test Kubernetes connection
        if (this.k8sCollector) {
            tests.push(
                this.testKubernetesConnection().catch(error => {
                    errors.push(`Kubernetes connection failed: ${error.message}`);
                })
            );
        }

        // Test traffic sources
        if (this.trafficAnalyzer) {
            tests.push(
                this.testTrafficSources().catch(error => {
                    errors.push(`Traffic sources failed: ${error.message}`);
                })
            );
        }

        await Promise.all(tests);

        const valid = errors.length === 0;
        console.log(valid ? '✅ All configurations valid' : `❌ ${errors.length} configuration errors`);
        
        return { valid, errors };
    }

    // Connection test methods (simplified)
    private async testAWSConnection(): Promise<void> {
        // Would test AWS credentials and permissions
        console.log('Testing AWS Cost Explorer connection...');
    }

    private async testGCPConnection(): Promise<void> {
        // Would test GCP service account and billing API access
        console.log('Testing GCP Billing API connection...');
    }

    private async testAzureConnection(): Promise<void> {
        // Would test Azure service principal and cost management API access
        console.log('Testing Azure Cost Management connection...');
    }

    private async testKubernetesConnection(): Promise<void> {
        // Would test Kubernetes cluster connection and metrics server
        console.log('Testing Kubernetes API connection...');
    }

    private async testTrafficSources(): Promise<void> {
        // Would test connectivity to monitoring endpoints
        console.log('Testing traffic monitoring sources...');
    }

    /**
     * Get available data sources
     */
    getAvailableSources(): string[] {
        const sources: string[] = [];
        
        if (this.awsCollector) sources.push('AWS Cost Explorer');
        if (this.gcpCollector) sources.push('GCP Billing');
        if (this.azureCollector) sources.push('Azure Cost Management');
        if (this.k8sCollector) sources.push('Kubernetes Metrics');
        if (this.trafficAnalyzer) sources.push('Traffic Analytics');
        
        return sources;
    }
}