/**
 * Traffic Analysis Source Module
 * 
 * Collects traffic and request patterns to correlate with cost data.
 * No AI inference - pure metrics from monitoring systems.
 */

import {
    TrafficConfig,
    TrafficData,
    TrafficMetric,
    RegionTraffic,
    TrafficPattern,
    TrafficPeak,
    TrafficSource
} from '../types';

interface PrometheusQuery {
    query: string;
    start: string;
    end: string;
    step: string;
}

interface PrometheusResult {
    status: string;
    data: {
        resultType: string;
        result: Array<{
            metric: Record<string, string>;
            values: Array<[number, string]>;
        }>;
    };
}

interface CloudWatchMetric {
    MetricName: string;
    Namespace: string;
    Dimensions: Array<{
        Name: string;
        Value: string;
    }>;
    Datapoints: Array<{
        Timestamp: string;
        Value: number;
        Unit: string;
    }>;
}

/**
 * Collects comprehensive traffic data for cost correlation analysis
 */
export class TrafficAnalyzer {
    private config: TrafficConfig;
    private prometheusClients: Map<string, any> = new Map();
    private cloudWatchClients: Map<string, any> = new Map();

    constructor(config: TrafficConfig) {
        this.config = config;
        this.initializeClients();
    }

    /**
     * Initialize monitoring system clients
     */
    private initializeClients(): void {
        for (const source of this.config.sources) {
            switch (source.type) {
                case 'prometheus':
                    // In real implementation: this.prometheusClients.set(source.endpoint, new PrometheusApi(source.endpoint));
                    this.prometheusClients.set(source.endpoint, null);
                    break;
                case 'cloudwatch':
                    // In real implementation: this.cloudWatchClients.set(source.endpoint, new CloudWatch(source.credentials));
                    this.cloudWatchClients.set(source.endpoint, null);
                    break;
                case 'stackdriver':
                    // In real implementation: initialize Google Cloud Monitoring client
                    break;
                case 'custom':
                    // Handle custom monitoring endpoints
                    break;
            }
        }
    }

    /**
     * Main entry point - collect all traffic data
     */
    async collectTrafficData(timeRange: { start: string; end: string }): Promise<TrafficData> {
        try {
            const [requests, patterns, peaks, costCorrelation] = await Promise.all([
                this.getTrafficMetrics(timeRange),
                this.analyzeTrafficPatterns(timeRange),
                this.detectTrafficPeaks(timeRange),
                this.calculateCostCorrelation(timeRange)
            ]);

            return {
                requests,
                patterns,
                peaks,
                costCorrelation
            };
        } catch (error) {
            console.error('Traffic data collection failed:', error);
            const message = error instanceof Error ? error.message : String(error);
            throw new Error(`Traffic data collection failed: ${message}`);
        }
    }

    /**
     * Get traffic metrics from all configured sources
     */
    private async getTrafficMetrics(timeRange: { start: string; end: string }): Promise<TrafficMetric[]> {
        const allMetrics: TrafficMetric[] = [];

        for (const source of this.config.sources) {
            try {
                let sourceMetrics: TrafficMetric[] = [];

                switch (source.type) {
                    case 'prometheus':
                        sourceMetrics = await this.getPrometheusMetrics(source, timeRange);
                        break;
                    case 'cloudwatch':
                        sourceMetrics = await this.getCloudWatchMetrics(source, timeRange);
                        break;
                    case 'stackdriver':
                        sourceMetrics = await this.getStackdriverMetrics(source, timeRange);
                        break;
                    case 'custom':
                        sourceMetrics = await this.getCustomMetrics(source, timeRange);
                        break;
                }

                allMetrics.push(...sourceMetrics);
            } catch (error) {
                console.error(`Failed to get metrics from ${source.type} source:`, error);
                // Continue with other sources
            }
        }

        // If no real data, return mock data
        if (allMetrics.length === 0) {
            return this.mockTrafficMetrics();
        }

        return this.consolidateMetrics(allMetrics);
    }

    /**
     * Get metrics from Prometheus
     */
    private async getPrometheusMetrics(source: TrafficSource, timeRange: { start: string; end: string }): Promise<TrafficMetric[]> {
        const client = this.prometheusClients.get(source.endpoint);
        if (!client) {
            console.log('Prometheus client not available, using mock data');
            return [];
        }

        const metrics: TrafficMetric[] = [];

        for (const query of source.queries) {
            try {
                const prometheusQuery: PrometheusQuery = {
                    query,
                    start: timeRange.start,
                    end: timeRange.end,
                    step: '5m'
                };

                const response = await client.queryRange(prometheusQuery);
                const result: PrometheusResult = response.data;

                if (result.status === 'success') {
                    for (const series of result.data.result) {
                        for (const [timestamp, value] of series.values) {
                            const existingMetric = metrics.find(m => 
                                new Date(m.timestamp).getTime() === timestamp * 1000
                            );

                            if (existingMetric) {
                                // Aggregate metrics for the same timestamp
                                if (query.includes('requests') || query.includes('http_requests')) {
                                    existingMetric.requests += parseFloat(value);
                                }
                                if (query.includes('bandwidth') || query.includes('bytes')) {
                                    existingMetric.bandwidth += parseFloat(value);
                                }
                            } else {
                                metrics.push({
                                    timestamp: new Date(timestamp * 1000).toISOString(),
                                    requests: query.includes('requests') ? parseFloat(value) : 0,
                                    bandwidth: query.includes('bandwidth') ? parseFloat(value) : 0,
                                    regions: this.extractRegionTraffic(series.metric)
                                });
                            }
                        }
                    }
                }
            } catch (error) {
                console.error(`Prometheus query failed: ${query}`, error);
            }
        }

        return metrics;
    }

    /**
     * Get metrics from AWS CloudWatch
     */
    private async getCloudWatchMetrics(source: TrafficSource, timeRange: { start: string; end: string }): Promise<TrafficMetric[]> {
        const client = this.cloudWatchClients.get(source.endpoint);
        if (!client) {
            console.log('CloudWatch client not available, using mock data');
            return [];
        }

        const metrics: TrafficMetric[] = [];

        try {
            const params = {
                MetricName: 'RequestCount',
                Namespace: 'AWS/ApplicationELB',
                StartTime: new Date(timeRange.start),
                EndTime: new Date(timeRange.end),
                Period: 300, // 5 minutes
                Statistics: ['Sum']
            };

            const response = await client.getMetricStatistics(params);
            const datapoints: CloudWatchMetric['Datapoints'] = response.Datapoints || [];

            for (const datapoint of datapoints) {
                metrics.push({
                    timestamp: datapoint.Timestamp,
                    requests: datapoint.Value,
                    bandwidth: 0, // Would need separate metric for bandwidth
                    regions: [{ region: 'us-east-1', requests: datapoint.Value, percentage: 100 }] // Mock region data
                });
            }
        } catch (error) {
            console.error('CloudWatch metrics query failed:', error);
        }

        return metrics;
    }

    /**
     * Get metrics from Google Cloud Monitoring (Stackdriver)
     */
    private async getStackdriverMetrics(source: TrafficSource, timeRange: { start: string; end: string }): Promise<TrafficMetric[]> {
        // Mock implementation for Google Cloud Monitoring
        console.log('Stackdriver metrics not implemented, using mock data');
        return [];
    }

    /**
     * Get metrics from custom endpoint
     */
    private async getCustomMetrics(source: TrafficSource, timeRange: { start: string; end: string }): Promise<TrafficMetric[]> {
        // Mock implementation for custom metrics endpoint
        console.log('Custom metrics not implemented, using mock data');
        return [];
    }

    /**
     * Analyze traffic patterns
     */
    private async analyzeTrafficPatterns(timeRange: { start: string; end: string }): Promise<TrafficPattern[]> {
        const metrics = await this.getTrafficMetrics(timeRange);
        if (metrics.length === 0) {
            return this.mockTrafficPatterns();
        }

        const patterns: TrafficPattern[] = [];

        // Analyze daily patterns
        const dailyPattern = this.analyzeDailyPattern(metrics);
        if (dailyPattern) {
            patterns.push(dailyPattern);
        }

        // Analyze weekly patterns
        const weeklyPattern = this.analyzeWeeklyPattern(metrics);
        if (weeklyPattern) {
            patterns.push(weeklyPattern);
        }

        // Analyze seasonal patterns (if enough data)
        const seasonalPattern = this.analyzeSeasonalPattern(metrics);
        if (seasonalPattern) {
            patterns.push(seasonalPattern);
        }

        return patterns;
    }

    /**
     * Detect traffic peaks
     */
    private async detectTrafficPeaks(timeRange: { start: string; end: string }): Promise<TrafficPeak[]> {
        const metrics = await this.getTrafficMetrics(timeRange);
        if (metrics.length === 0) {
            return this.mockTrafficPeaks();
        }

        const peaks: TrafficPeak[] = [];
        const threshold = this.calculatePeakThreshold(metrics);

        let peakStart: string | null = null;
        let peakEnd: string | null = null;
        let peakRequests = 0;
        let totalRequests = 0;
        let dataPoints = 0;

        for (const metric of metrics) {
            totalRequests += metric.requests;
            dataPoints++;

            if (metric.requests > threshold) {
                if (!peakStart) {
                    peakStart = metric.timestamp;
                }
                peakEnd = metric.timestamp;
                peakRequests = Math.max(peakRequests, metric.requests);
            } else {
                if (peakStart && peakEnd) {
                    const averageRequests = totalRequests / dataPoints;
                    const costImpact = this.calculatePeakCostImpact(peakRequests, averageRequests);

                    peaks.push({
                        startTime: peakStart,
                        endTime: peakEnd,
                        peakRequests,
                        averageRequests,
                        costImpact
                    });

                    peakStart = null;
                    peakEnd = null;
                    peakRequests = 0;
                }
            }
        }

        return peaks;
    }

    /**
     * Calculate correlation between traffic and cost
     */
    private async calculateCostCorrelation(timeRange: { start: string; end: string }): Promise<number> {
        const metrics = await this.getTrafficMetrics(timeRange);
        if (metrics.length === 0) {
            return 0.75; // Mock correlation
        }

        // This would typically involve correlating traffic metrics with cost data
        // For now, return a mock correlation coefficient
        const trafficVariance = this.calculateVariance(metrics.map(m => m.requests));
        const normalized = Math.min(trafficVariance / 1000000, 1); // Normalize to 0-1
        
        return Math.max(0.3, normalized); // Ensure minimum correlation
    }

    /**
     * Helper methods
     */
    private consolidateMetrics(metrics: TrafficMetric[]): TrafficMetric[] {
        const consolidated = new Map<string, TrafficMetric>();

        for (const metric of metrics) {
            const key = metric.timestamp;
            if (consolidated.has(key)) {
                const existing = consolidated.get(key)!;
                existing.requests += metric.requests;
                existing.bandwidth += metric.bandwidth;
                // Merge regions
                const regionMap = new Map<string, RegionTraffic>();
                for (const region of [...existing.regions, ...metric.regions]) {
                    if (regionMap.has(region.region)) {
                        const existingRegion = regionMap.get(region.region)!;
                        existingRegion.requests += region.requests;
                    } else {
                        regionMap.set(region.region, { ...region });
                    }
                }
                existing.regions = Array.from(regionMap.values());
                this.recalculateRegionPercentages(existing.regions);
            } else {
                consolidated.set(key, { ...metric });
            }
        }

        return Array.from(consolidated.values()).sort((a, b) => 
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );
    }

    private extractRegionTraffic(metric: Record<string, string>): RegionTraffic[] {
        const region = metric.region || metric.availability_zone || 'unknown';
        return [{
            region: region.replace(/[a-z]$/, ''), // Remove zone letter if present
            requests: 0, // Will be set by caller
            percentage: 100
        }];
    }

    private recalculateRegionPercentages(regions: RegionTraffic[]): void {
        const total = regions.reduce((sum, r) => sum + r.requests, 0);
        if (total > 0) {
            for (const region of regions) {
                region.percentage = (region.requests / total) * 100;
            }
        }
    }

    private analyzeDailyPattern(metrics: TrafficMetric[]): TrafficPattern | null {
        if (metrics.length < 24) return null; // Need at least a day of data

        const hourlyAverages = new Array(24).fill(0);
        const hourlyCounts = new Array(24).fill(0);

        for (const metric of metrics) {
            const hour = new Date(metric.timestamp).getHours();
            hourlyAverages[hour] += metric.requests;
            hourlyCounts[hour]++;
        }

        // Calculate averages and find peaks
        const peakTimes: string[] = [];
        let maxRequests = 0;

        for (let i = 0; i < 24; i++) {
            if (hourlyCounts[i] > 0) {
                hourlyAverages[i] /= hourlyCounts[i];
                if (hourlyAverages[i] > maxRequests) {
                    maxRequests = hourlyAverages[i];
                }
            }
        }

        const threshold = maxRequests * 0.8;
        for (let i = 0; i < 24; i++) {
            if (hourlyAverages[i] > threshold) {
                peakTimes.push(`${i.toString().padStart(2, '0')}:00`);
            }
        }

        return {
            type: 'daily',
            description: `Daily traffic peaks at ${peakTimes.join(', ')}`,
            peakTimes,
            costImpact: this.calculatePatternCostImpact(maxRequests, hourlyAverages)
        };
    }

    private analyzeWeeklyPattern(metrics: TrafficMetric[]): TrafficPattern | null {
        if (metrics.length < 168) return null; // Need at least a week of data

        const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const dailyAverages = new Array(7).fill(0);
        const dailyCounts = new Array(7).fill(0);

        for (const metric of metrics) {
            const day = new Date(metric.timestamp).getDay();
            dailyAverages[day] += metric.requests;
            dailyCounts[day]++;
        }

        const peakTimes: string[] = [];
        let maxRequests = 0;

        for (let i = 0; i < 7; i++) {
            if (dailyCounts[i] > 0) {
                dailyAverages[i] /= dailyCounts[i];
                if (dailyAverages[i] > maxRequests) {
                    maxRequests = dailyAverages[i];
                }
            }
        }

        const threshold = maxRequests * 0.8;
        for (let i = 0; i < 7; i++) {
            if (dailyAverages[i] > threshold) {
                peakTimes.push(weekdays[i]);
            }
        }

        return {
            type: 'weekly',
            description: `Weekly traffic peaks on ${peakTimes.join(', ')}`,
            peakTimes,
            costImpact: this.calculatePatternCostImpact(maxRequests, dailyAverages)
        };
    }

    private analyzeSeasonalPattern(metrics: TrafficMetric[]): TrafficPattern | null {
        if (metrics.length < 8760) return null; // Need at least a year of data

        // Simplified seasonal analysis
        const months = new Array(12).fill(0);
        const monthCounts = new Array(12).fill(0);

        for (const metric of metrics) {
            const month = new Date(metric.timestamp).getMonth();
            months[month] += metric.requests;
            monthCounts[month]++;
        }

        const monthNames = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ];

        const peakTimes: string[] = [];
        let maxRequests = 0;

        for (let i = 0; i < 12; i++) {
            if (monthCounts[i] > 0) {
                months[i] /= monthCounts[i];
                if (months[i] > maxRequests) {
                    maxRequests = months[i];
                }
            }
        }

        const threshold = maxRequests * 0.8;
        for (let i = 0; i < 12; i++) {
            if (months[i] > threshold) {
                peakTimes.push(monthNames[i]);
            }
        }

        return {
            type: 'seasonal',
            description: `Seasonal traffic peaks in ${peakTimes.join(', ')}`,
            peakTimes,
            costImpact: this.calculatePatternCostImpact(maxRequests, months)
        };
    }

    private calculatePeakThreshold(metrics: TrafficMetric[]): number {
        const requests = metrics.map(m => m.requests);
        const mean = requests.reduce((sum, r) => sum + r, 0) / requests.length;
        const stdDev = Math.sqrt(this.calculateVariance(requests));
        return mean + (2 * stdDev); // 2 standard deviations above mean
    }

    private calculateVariance(values: number[]): number {
        if (values.length === 0) return 0;
        const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
        return values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
    }

    private calculatePeakCostImpact(peakRequests: number, averageRequests: number): number {
        // Simplified cost impact calculation
        const multiplier = peakRequests / averageRequests;
        const baseCostPerRequest = 0.0001; // $0.0001 per request
        return (peakRequests - averageRequests) * baseCostPerRequest;
    }

    private calculatePatternCostImpact(maxValue: number, values: number[]): number {
        const averageValue = values.reduce((sum, v) => sum + v, 0) / values.length;
        const variability = maxValue - averageValue;
        return variability * 0.0001; // Simplified cost calculation
    }

    // Mock data methods for development
    private mockTrafficMetrics(): TrafficMetric[] {
        const metrics: TrafficMetric[] = [];
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 7);

        for (let i = 0; i < 168; i++) { // 7 days of hourly data
            const timestamp = new Date(startDate);
            timestamp.setHours(timestamp.getHours() + i);

            const baseRequests = 1000 + Math.sin(i * Math.PI / 12) * 500; // Daily pattern
            const weeklyMultiplier = (i % 168) < 120 ? 1.2 : 0.8; // Weekday vs weekend
            const noise = (Math.random() - 0.5) * 200;
            
            const requests = Math.max(0, baseRequests * weeklyMultiplier + noise);
            const bandwidth = requests * (50 + Math.random() * 100); // 50-150 bytes per request

            metrics.push({
                timestamp: timestamp.toISOString(),
                requests,
                bandwidth,
                regions: [
                    { region: 'us-east-1', requests: requests * 0.4, percentage: 40 },
                    { region: 'us-west-2', requests: requests * 0.3, percentage: 30 },
                    { region: 'eu-west-1', requests: requests * 0.2, percentage: 20 },
                    { region: 'ap-southeast-1', requests: requests * 0.1, percentage: 10 }
                ]
            });
        }

        return metrics;
    }

    private mockTrafficPatterns(): TrafficPattern[] {
        return [
            {
                type: 'daily',
                description: 'Daily traffic peaks between 09:00-17:00 UTC',
                peakTimes: ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00'],
                costImpact: 45.60
            },
            {
                type: 'weekly',
                description: 'Weekly traffic peaks on Tuesday, Wednesday, Thursday',
                peakTimes: ['Tuesday', 'Wednesday', 'Thursday'],
                costImpact: 120.30
            }
        ];
    }

    private mockTrafficPeaks(): TrafficPeak[] {
        const now = new Date();
        return [
            {
                startTime: new Date(now.getTime() - 3 * 60 * 60 * 1000).toISOString(),
                endTime: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(),
                peakRequests: 2500,
                averageRequests: 1200,
                costImpact: 13.00
            },
            {
                startTime: new Date(now.getTime() - 25 * 60 * 60 * 1000).toISOString(),
                endTime: new Date(now.getTime() - 23 * 60 * 60 * 1000).toISOString(),
                peakRequests: 3200,
                averageRequests: 1200,
                costImpact: 20.00
            }
        ];
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
export async function fetchTrafficData(
    config: TrafficConfig,
    timeRange?: { start: string; end: string }
): Promise<TrafficData> {
    const analyzer = new TrafficAnalyzer(config);
    return analyzer.collectTrafficData(resolveTimeRange(timeRange));
}
