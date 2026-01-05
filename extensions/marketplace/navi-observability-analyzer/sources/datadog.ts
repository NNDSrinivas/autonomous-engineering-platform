/**
 * DataDog Data Source Integration
 * 
 * Fetches metrics from DataDog API for analysis and anomaly detection.
 */

import {
    DatadogConfig,
    MetricSeries,
    MetricDataPoint,
    MetricSource,
    MetricAggregation
} from '../types';

/**
 * Fetch metrics from DataDog
 */
export async function fetchDatadogMetrics(config: DatadogConfig): Promise<MetricSeries[]> {
    console.log(`📊 Fetching metrics from DataDog...`);
    
    const metrics: MetricSeries[] = [];
    
    try {
        for (const query of config.queries) {
            const series = await executeDatadogQuery(config, query);
            if (series) {
                metrics.push(series);
            }
        }
        
        console.log(`✅ Successfully fetched ${metrics.length} metric series from DataDog`);
        return metrics;
        
    } catch (error) {
        console.error('❌ Failed to fetch DataDog metrics:', error);
        throw error;
    }
}

/**
 * Execute a single DataDog query
 */
async function executeDatadogQuery(config: DatadogConfig, query: any): Promise<MetricSeries | null> {
    const now = Math.floor(Date.now() / 1000);
    const from = now - (15 * 60); // Last 15 minutes
    
    const params = new URLSearchParams({
        from: from.toString(),
        to: now.toString(),
        query: formatDatadogQuery(query)
    });
    
    const url = `https://api.datadoghq.com/api/v1/query?${params}`;
    
    try {
        const headers = {
            'DD-API-KEY': config.apiKey,
            'DD-APPLICATION-KEY': config.appKey,
            'Content-Type': 'application/json'
        };
        
        const response = await fetch(url, { headers });
        
        if (!response.ok) {
            throw new Error(`DataDog query failed: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json() as any;
        
        if (data.error) {
            throw new Error(`DataDog query error: ${data.error}`);
        }
        
        return parseDatadogResponse(query, data);
        
    } catch (error) {
        console.error(`Failed to execute DataDog query "${query.metric}":`, error);
        return null;
    }
}

/**
 * Format DataDog query with aggregation and tags
 */
function formatDatadogQuery(query: any): string {
    let formattedQuery = `${query.aggregation}:${query.metric}`;
    
    if (query.tags && query.tags.length > 0) {
        formattedQuery += `{${query.tags.join(',')}}`;
    }
    
    return formattedQuery;
}

/**
 * Parse DataDog API response into MetricSeries
 */
function parseDatadogResponse(query: any, data: any): MetricSeries | null {
    if (!data.series || data.series.length === 0) {
        console.warn(`No data returned for DataDog query: ${query.metric}`);
        return null;
    }
    
    // Take the first series (could be enhanced to handle multiple series)
    const series = data.series[0];
    const pointlist = series.pointlist || [];
    
    const dataPoints: MetricDataPoint[] = pointlist.map(([timestamp, value]: [number, number]) => ({
        timestamp: timestamp * 1000, // Convert to milliseconds
        value,
        labels: series.scope ? { scope: series.scope } : undefined
    }));
    
    if (dataPoints.length === 0) {
        return null;
    }
    
    return {
        name: query.metric,
        unit: inferUnit(query.metric),
        dataPoints,
        metadata: {
            source: MetricSource.DATADOG,
            interval: series.interval || '60s',
            aggregation: mapDatadogAggregation(query.aggregation)
        }
    };
}

/**
 * Infer unit from DataDog metric name
 */
function inferUnit(metricName: string): string {
    if (metricName.includes('.duration') || metricName.includes('.latency') || metricName.includes('.time')) {
        return 'seconds';
    }
    if (metricName.includes('.bytes') || metricName.includes('.size')) {
        return 'bytes';
    }
    if (metricName.includes('.rate') || metricName.includes('.per_second')) {
        return 'per_second';
    }
    if (metricName.includes('.percent') || metricName.includes('.ratio')) {
        return 'percent';
    }
    if (metricName.includes('.count')) {
        return 'count';
    }
    
    return '';
}

/**
 * Map DataDog aggregation to our enum
 */
function mapDatadogAggregation(aggregation: string): MetricAggregation {
    switch (aggregation.toLowerCase()) {
        case 'avg':
            return MetricAggregation.AVERAGE;
        case 'sum':
            return MetricAggregation.SUM;
        case 'max':
            return MetricAggregation.MAX;
        case 'min':
            return MetricAggregation.MIN;
        default:
            return MetricAggregation.AVERAGE;
    }
}

/**
 * Create common DataDog queries for web applications
 */
export function createCommonDatadogQueries(): any[] {
    return [
        {
            metric: 'nginx.net.request_per_s',
            aggregation: 'avg',
            tags: ['service:web']
        },
        {
            metric: 'apache.performance.busy_workers',
            aggregation: 'avg',
            tags: []
        },
        {
            metric: 'system.cpu.user',
            aggregation: 'avg',
            tags: ['host:web-server']
        },
        {
            metric: 'system.mem.pct_usable',
            aggregation: 'avg',
            tags: ['host:web-server']
        },
        {
            metric: 'system.disk.used',
            aggregation: 'avg',
            tags: ['host:web-server']
        },
        {
            metric: 'mysql.performance.queries',
            aggregation: 'avg',
            tags: ['service:database']
        },
        {
            metric: 'redis.net.commands',
            aggregation: 'sum',
            tags: ['service:cache']
        }
    ];
}

/**
 * Create application performance monitoring (APM) queries
 */
export function createAPMQueries(): any[] {
    return [
        {
            metric: 'trace.web.request',
            aggregation: 'avg',
            tags: ['service:api']
        },
        {
            metric: 'trace.web.request.duration',
            aggregation: 'avg',
            tags: ['service:api']
        },
        {
            metric: 'trace.web.request.errors',
            aggregation: 'sum',
            tags: ['service:api']
        }
    ];
}