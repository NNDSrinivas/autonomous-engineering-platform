/**
 * AWS CloudWatch Data Source Integration
 * 
 * Fetches metrics from AWS CloudWatch for analysis and anomaly detection.
 */

import {
    CloudWatchConfig,
    MetricSeries,
    MetricDataPoint,
    MetricSource,
    MetricAggregation
} from '../types';

/**
 * Fetch metrics from AWS CloudWatch
 */
export async function fetchCloudWatchMetrics(config: CloudWatchConfig): Promise<MetricSeries[]> {
    console.log(`📊 Fetching metrics from CloudWatch in region ${config.region}...`);
    
    const metrics: MetricSeries[] = [];
    
    try {
        for (const metric of config.metrics) {
            const series = await fetchCloudWatchMetric(config, metric);
            if (series) {
                metrics.push(series);
            }
        }
        
        console.log(`✅ Successfully fetched ${metrics.length} metric series from CloudWatch`);
        return metrics;
        
    } catch (error) {
        console.error('❌ Failed to fetch CloudWatch metrics:', error);
        throw error;
    }
}

/**
 * Fetch a single CloudWatch metric
 */
async function fetchCloudWatchMetric(config: CloudWatchConfig, metric: any): Promise<MetricSeries | null> {
    try {
        // This is a simplified implementation
        // In production, you would use the AWS SDK to make the actual CloudWatch API calls
        console.log(`Fetching CloudWatch metric: ${metric.namespace}/${metric.metricName}`);
        
        // Mock implementation - replace with actual AWS SDK calls
        const mockDataPoints = generateMockCloudWatchData();
        
        return {
            name: `${metric.namespace}.${metric.metricName}`,
            unit: inferCloudWatchUnit(metric.metricName),
            dataPoints: mockDataPoints,
            metadata: {
                source: MetricSource.CLOUDWATCH,
                interval: '300s', // CloudWatch default is 5 minutes
                aggregation: inferCloudWatchAggregation(metric.metricName)
            }
        };
        
    } catch (error) {
        console.error(`Failed to fetch CloudWatch metric ${metric.metricName}:`, error);
        return null;
    }
}

/**
 * Generate mock CloudWatch data for demonstration
 * In production, replace with actual AWS SDK CloudWatch API calls
 */
function generateMockCloudWatchData(): MetricDataPoint[] {
    const now = Date.now();
    const dataPoints: MetricDataPoint[] = [];
    
    // Generate 15 minutes of data with 5-minute intervals (3 points)
    for (let i = 2; i >= 0; i--) {
        dataPoints.push({
            timestamp: now - (i * 5 * 60 * 1000),
            value: Math.random() * 100, // Mock value
        });
    }
    
    return dataPoints;
}

/**
 * Infer unit from CloudWatch metric name
 */
function inferCloudWatchUnit(metricName: string): string {
    const lowerName = metricName.toLowerCase();
    
    if (lowerName.includes('duration') || lowerName.includes('latency')) {
        return 'seconds';
    }
    if (lowerName.includes('bytes') || lowerName.includes('size')) {
        return 'bytes';
    }
    if (lowerName.includes('utilization') || lowerName.includes('percent')) {
        return 'percent';
    }
    if (lowerName.includes('count') || lowerName.includes('requests')) {
        return 'count';
    }
    if (lowerName.includes('rate')) {
        return 'per_second';
    }
    
    return '';
}

/**
 * Infer aggregation from CloudWatch metric name
 */
function inferCloudWatchAggregation(metricName: string): MetricAggregation {
    const lowerName = metricName.toLowerCase();
    
    if (lowerName.includes('sum') || lowerName.includes('total')) {
        return MetricAggregation.SUM;
    }
    if (lowerName.includes('max') || lowerName.includes('peak')) {
        return MetricAggregation.MAX;
    }
    if (lowerName.includes('min')) {
        return MetricAggregation.MIN;
    }
    
    return MetricAggregation.AVERAGE;
}

/**
 * Create common EC2 CloudWatch metrics
 */
export function createEC2Metrics(): any[] {
    return [
        {
            namespace: 'AWS/EC2',
            metricName: 'CPUUtilization',
            dimensions: {
                InstanceId: 'i-1234567890abcdef0'
            }
        },
        {
            namespace: 'AWS/EC2',
            metricName: 'NetworkIn',
            dimensions: {
                InstanceId: 'i-1234567890abcdef0'
            }
        },
        {
            namespace: 'AWS/EC2',
            metricName: 'NetworkOut',
            dimensions: {
                InstanceId: 'i-1234567890abcdef0'
            }
        },
        {
            namespace: 'AWS/EC2',
            metricName: 'DiskReadBytes',
            dimensions: {
                InstanceId: 'i-1234567890abcdef0'
            }
        },
        {
            namespace: 'AWS/EC2',
            metricName: 'DiskWriteBytes',
            dimensions: {
                InstanceId: 'i-1234567890abcdef0'
            }
        }
    ];
}

/**
 * Create common RDS CloudWatch metrics
 */
export function createRDSMetrics(): any[] {
    return [
        {
            namespace: 'AWS/RDS',
            metricName: 'CPUUtilization',
            dimensions: {
                DBInstanceIdentifier: 'mydb-instance'
            }
        },
        {
            namespace: 'AWS/RDS',
            metricName: 'DatabaseConnections',
            dimensions: {
                DBInstanceIdentifier: 'mydb-instance'
            }
        },
        {
            namespace: 'AWS/RDS',
            metricName: 'FreeableMemory',
            dimensions: {
                DBInstanceIdentifier: 'mydb-instance'
            }
        },
        {
            namespace: 'AWS/RDS',
            metricName: 'ReadLatency',
            dimensions: {
                DBInstanceIdentifier: 'mydb-instance'
            }
        },
        {
            namespace: 'AWS/RDS',
            metricName: 'WriteLatency',
            dimensions: {
                DBInstanceIdentifier: 'mydb-instance'
            }
        }
    ];
}

/**
 * Create common ELB CloudWatch metrics
 */
export function createELBMetrics(): any[] {
    return [
        {
            namespace: 'AWS/ELB',
            metricName: 'RequestCount',
            dimensions: {
                LoadBalancerName: 'my-load-balancer'
            }
        },
        {
            namespace: 'AWS/ELB',
            metricName: 'Latency',
            dimensions: {
                LoadBalancerName: 'my-load-balancer'
            }
        },
        {
            namespace: 'AWS/ELB',
            metricName: 'HTTPCode_Target_2XX_Count',
            dimensions: {
                LoadBalancerName: 'my-load-balancer'
            }
        },
        {
            namespace: 'AWS/ELB',
            metricName: 'HTTPCode_Target_5XX_Count',
            dimensions: {
                LoadBalancerName: 'my-load-balancer'
            }
        }
    ];
}