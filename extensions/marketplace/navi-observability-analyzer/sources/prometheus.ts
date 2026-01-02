/**
 * Prometheus Data Source Integration
 * 
 * Fetches metrics from Prometheus for analysis and anomaly detection.
 * Supports both basic authentication and token-based authentication.
 */

import {
    PrometheusConfig,
    MetricSeries,
    MetricDataPoint,
    MetricSource,
    MetricAggregation
} from '../types';

/**
 * Fetch metrics from Prometheus
 */
export async function fetchPrometheusMetrics(config: PrometheusConfig): Promise<MetricSeries[]> {
    console.log(`📊 Fetching metrics from Prometheus: ${config.endpoint}`);
    
    const metrics: MetricSeries[] = [];
    
    try {
        for (const query of config.queries) {
            const series = await executePrometheusQuery(config, query);
            if (series) {
                metrics.push(series);
            }
        }
        
        console.log(`✅ Successfully fetched ${metrics.length} metric series from Prometheus`);
        return metrics;
        
    } catch (error) {
        console.error('❌ Failed to fetch Prometheus metrics:', error);
        throw error;
    }
}

/**
 * Execute a single Prometheus query
 */
async function executePrometheusQuery(config: PrometheusConfig, query: any): Promise<MetricSeries | null> {
    const now = Date.now();
    const startTime = now - (15 * 60 * 1000); // Last 15 minutes
    
    const params = new URLSearchParams({
        query: query.query,
        start: Math.floor(startTime / 1000).toString(),
        end: Math.floor(now / 1000).toString(),
        step: query.interval || '30s'
    });
    
    const url = `${config.endpoint}/api/v1/query_range?${params}`;
    
    try {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json'
        };
        
        // Add authentication if configured
        if (config.basicAuth) {
            const auth = Buffer.from(`${config.basicAuth.username}:${config.basicAuth.password}`).toString('base64');
            headers['Authorization'] = `Basic ${auth}`;
        }
        
        const response = await fetch(url, { headers });
        
        if (!response.ok) {
            throw new Error(`Prometheus query failed: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json() as any;
        
        if (data.status !== 'success') {
            throw new Error(`Prometheus query error: ${data.error}`);
        }
        
        return parsePrometheusResponse(query.name, data.data);
        
    } catch (error) {
        console.error(`Failed to execute Prometheus query "${query.name}":`, error);
        return null;
    }
}

/**
 * Parse Prometheus API response into MetricSeries
 */
function parsePrometheusResponse(name: string, data: any): MetricSeries | null {
    if (!data.result || data.result.length === 0) {
        console.warn(`No data returned for Prometheus query: ${name}`);
        return null;
    }
    
    // Take the first result series (could be enhanced to handle multiple series)
    const result = data.result[0];
    const values = result.values || [];
    
    const dataPoints: MetricDataPoint[] = values.map(([timestamp, value]: [number, string]) => ({
        timestamp: timestamp * 1000, // Convert to milliseconds
        value: parseFloat(value),
        labels: result.metric
    }));
    
    if (dataPoints.length === 0) {
        return null;
    }
    
    // Determine unit from metric name (basic heuristics)
    let unit = '';
    if (name.includes('_seconds') || name.includes('_duration')) {
        unit = 'seconds';
    } else if (name.includes('_bytes')) {
        unit = 'bytes';
    } else if (name.includes('_rate') || name.includes('_per_second')) {
        unit = 'per_second';
    } else if (name.includes('_percent') || name.includes('_ratio')) {
        unit = 'percent';
    }
    
    return {
        name,
        unit,
        dataPoints,
        metadata: {
            source: MetricSource.PROMETHEUS,
            interval: '30s', // Default interval
            aggregation: inferAggregation(name)
        }
    };
}

/**
 * Infer aggregation method from metric name
 */
function inferAggregation(name: string): MetricAggregation {
    if (name.includes('_sum') || name.includes('_total')) {
        return MetricAggregation.SUM;
    }
    if (name.includes('_max') || name.includes('_maximum')) {
        return MetricAggregation.MAX;
    }
    if (name.includes('_min') || name.includes('_minimum')) {
        return MetricAggregation.MIN;
    }
    if (name.includes('_p95') || name.includes('_95th')) {
        return MetricAggregation.P95;
    }
    if (name.includes('_p99') || name.includes('_99th')) {
        return MetricAggregation.P99;
    }
    if (name.includes('_p50') || name.includes('_median')) {
        return MetricAggregation.P50;
    }
    
    // Default to average for most metrics
    return MetricAggregation.AVERAGE;
}

/**
 * Create common Prometheus queries for web services
 */
export function createCommonWebServiceQueries(): any[] {
    return [
        {
            name: 'http_request_duration_p95',
            query: 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))',
            interval: '30s',
            labels: ['service']
        },
        {
            name: 'http_request_rate',
            query: 'sum(rate(http_requests_total[5m])) by (service)',
            interval: '30s',
            labels: ['service']
        },
        {
            name: 'http_error_rate',
            query: 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service)',
            interval: '30s',
            labels: ['service']
        },
        {
            name: 'cpu_usage_percent',
            query: '100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            interval: '30s'
        },
        {
            name: 'memory_usage_percent',
            query: '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
            interval: '30s'
        },
        {
            name: 'disk_usage_percent',
            query: '(1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100',
            interval: '30s'
        }
    ];
}

/**
 * Create Kubernetes-specific Prometheus queries
 */
export function createKubernetesQueries(): any[] {
    return [
        {
            name: 'pod_cpu_usage',
            query: 'sum(rate(container_cpu_usage_seconds_total{container!="POD"}[5m])) by (pod, namespace)',
            interval: '30s',
            labels: ['pod', 'namespace']
        },
        {
            name: 'pod_memory_usage',
            query: 'sum(container_memory_working_set_bytes{container!="POD"}) by (pod, namespace)',
            interval: '30s',
            labels: ['pod', 'namespace']
        },
        {
            name: 'pod_restart_count',
            query: 'increase(kube_pod_container_status_restarts_total[1h])',
            interval: '1m',
            labels: ['pod', 'namespace']
        }
    ];
}