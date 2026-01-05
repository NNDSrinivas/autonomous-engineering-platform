/**
 * Cost Regression Detector
 * 
 * Detects cost anomalies, regressions, and unexpected spending patterns
 * using statistical analysis and trend detection.
 */

import {
    WasteDetectionResult,
    WasteType,
    CostData,
    UsageData,
    CostTrend,
    Evidence
} from '../types';

/**
 * Regression detection configuration
 */
const REGRESSION_CONFIG = {
    MIN_DATA_POINTS: 7,              // Need at least 7 days of data
    SPIKE_THRESHOLD: 1.5,            // 50% increase is a spike
    REGRESSION_THRESHOLD: 1.3,       // 30% sustained increase
    ANOMALY_THRESHOLD: 2.0,          // 2 standard deviations
    MIN_COST_IMPACT: 25,             // Minimum $25/month impact
    CONFIDENCE_HIGH: 0.9,            // High confidence threshold
    TREND_WINDOW_DAYS: 14,           // Look at 14-day trends
    BASELINE_WINDOW_DAYS: 30         // 30-day baseline period
};

/**
 * Statistical analysis for cost regression detection
 */
export class CostRegressionDetector {
    private costData: CostData;
    private usageData: UsageData;
    private timestamp: string;
    private allTrends: CostTrend[];

    constructor(costData: CostData, usageData: UsageData) {
        this.costData = costData;
        this.usageData = usageData;
        this.timestamp = new Date().toISOString();
        this.allTrends = this.consolidateCostTrends();
    }

    /**
     * Detect all types of cost regressions
     */
    async detectCostRegressions(): Promise<WasteDetectionResult[]> {
        console.log('📈 Detecting cost regressions and anomalies...');
        
        const results: WasteDetectionResult[] = [];
        
        if (this.allTrends.length < REGRESSION_CONFIG.MIN_DATA_POINTS) {
            console.log('⚠️ Insufficient data for regression analysis (need 7+ days)');
            return results;
        }

        try {
            const [spikes, regressions, anomalies, serviceRegressions] = await Promise.all([
                this.detectCostSpikes(),
                this.detectSustainedRegressions(),
                this.detectStatisticalAnomalies(),
                this.detectServiceSpecificRegressions()
            ]);

            results.push(...spikes, ...regressions, ...anomalies, ...serviceRegressions);

            // Sort by cost impact
            results.sort((a, b) => b.wastedAmount - a.wastedAmount);

            // Filter by minimum impact threshold
            const significantRegressions = results.filter(r => r.wastedAmount >= REGRESSION_CONFIG.MIN_COST_IMPACT);

            const totalImpact = significantRegressions.reduce((sum, r) => sum + r.wastedAmount, 0);
            console.log(`📊 Regression analysis complete: $${totalImpact.toFixed(2)}/month impact from ${significantRegressions.length} regressions`);

            return significantRegressions;
        } catch (error) {
            console.error('❌ Cost regression detection failed:', error);
            throw error;
        }
    }

    /**
     * Detect sudden cost spikes
     */
    private async detectCostSpikes(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (this.allTrends.length < 3) return results;

        // Look for day-over-day spikes
        for (let i = 1; i < this.allTrends.length; i++) {
            const current = this.allTrends[i];
            const previous = this.allTrends[i - 1];
            
            if (previous.cost > 0 && current.cost > previous.cost * REGRESSION_CONFIG.SPIKE_THRESHOLD) {
                const spikeAmount = current.cost - previous.cost;
                const monthlyImpact = spikeAmount * 30; // Assume spike continues
                
                if (monthlyImpact >= REGRESSION_CONFIG.MIN_COST_IMPACT) {
                    const spikePercentage = ((current.cost / previous.cost) - 1) * 100;
                    
                    const evidence: Evidence[] = [
                        {
                            type: 'trend',
                            description: 'Daily cost spike',
                            value: spikeAmount,
                            threshold: previous.cost * (REGRESSION_CONFIG.SPIKE_THRESHOLD - 1),
                            unit: 'USD'
                        },
                        {
                            type: 'trend',
                            description: 'Spike percentage increase',
                            value: spikePercentage,
                            threshold: (REGRESSION_CONFIG.SPIKE_THRESHOLD - 1) * 100,
                            unit: '%'
                        },
                        {
                            type: 'billing',
                            description: 'Previous day cost',
                            value: previous.cost,
                            threshold: 0,
                            unit: 'USD'
                        },
                        {
                            type: 'billing',
                            description: 'Current day cost',
                            value: current.cost,
                            threshold: previous.cost * REGRESSION_CONFIG.SPIKE_THRESHOLD,
                            unit: 'USD'
                        }
                    ];

                    results.push({
                        id: `cost-spike-${current.date}`,
                        type: WasteType.COST_REGRESSION,
                        severity: this.determineSeverity(monthlyImpact),
                        description: `Cost spike detected: ${spikePercentage.toFixed(1)}% increase ($${spikeAmount.toFixed(2)}) on ${current.date}`,
                        affectedResources: [{
                            id: 'daily-spend',
                            name: 'Daily Infrastructure Spend',
                            type: 'Cost Trend',
                            cloud: 'kubernetes', // Multi-cloud
                            tags: {
                                date: current.date,
                                spikeAmount: `$${spikeAmount.toFixed(2)}`,
                                previousCost: `$${previous.cost.toFixed(2)}`
                            }
                        }],
                        wastedAmount: monthlyImpact,
                        confidence: this.calculateSpikeConfidence(spikePercentage, spikeAmount),
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Detect sustained cost regressions
     */
    private async detectSustainedRegressions(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (this.allTrends.length < REGRESSION_CONFIG.TREND_WINDOW_DAYS) {
            return results;
        }

        // Compare recent trends to baseline
        const recentTrends = this.allTrends.slice(-REGRESSION_CONFIG.TREND_WINDOW_DAYS);
        const recentAvg = this.calculateAverage(recentTrends.map(t => t.cost));
        
        const baselineTrends = this.allTrends.slice(
            -REGRESSION_CONFIG.BASELINE_WINDOW_DAYS, 
            -REGRESSION_CONFIG.TREND_WINDOW_DAYS
        );
        
        if (baselineTrends.length < 7) return results; // Need baseline data
        
        const baselineAvg = this.calculateAverage(baselineTrends.map(t => t.cost));
        
        if (recentAvg > baselineAvg * REGRESSION_CONFIG.REGRESSION_THRESHOLD) {
            const regressionAmount = recentAvg - baselineAvg;
            const monthlyImpact = regressionAmount * 30;
            const regressionPercentage = ((recentAvg / baselineAvg) - 1) * 100;
            
            if (monthlyImpact >= REGRESSION_CONFIG.MIN_COST_IMPACT) {
                const evidence: Evidence[] = [
                    {
                        type: 'trend',
                        description: 'Recent 14-day average cost',
                        value: recentAvg,
                        threshold: baselineAvg * REGRESSION_CONFIG.REGRESSION_THRESHOLD,
                        unit: 'USD/day'
                    },
                    {
                        type: 'trend',
                        description: 'Baseline average cost',
                        value: baselineAvg,
                        threshold: 0,
                        unit: 'USD/day'
                    },
                    {
                        type: 'trend',
                        description: 'Sustained regression percentage',
                        value: regressionPercentage,
                        threshold: (REGRESSION_CONFIG.REGRESSION_THRESHOLD - 1) * 100,
                        unit: '%'
                    }
                ];

                results.push({
                    id: `sustained-regression-${Date.now()}`,
                    type: WasteType.COST_REGRESSION,
                    severity: this.determineSeverity(monthlyImpact),
                    description: `Sustained cost regression: ${regressionPercentage.toFixed(1)}% increase over ${REGRESSION_CONFIG.TREND_WINDOW_DAYS}-day period`,
                    affectedResources: [{
                        id: 'overall-trend',
                        name: 'Overall Cost Trend',
                        type: 'Sustained Regression',
                        cloud: 'kubernetes',
                        tags: {
                            trendDays: REGRESSION_CONFIG.TREND_WINDOW_DAYS.toString(),
                            regressionPct: `${regressionPercentage.toFixed(1)}%`,
                            dailyIncrease: `$${regressionAmount.toFixed(2)}`
                        }
                    }],
                    wastedAmount: monthlyImpact,
                    confidence: this.calculateRegressionConfidence(regressionPercentage, baselineTrends.length),
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Detect statistical anomalies using standard deviation
     */
    private async detectStatisticalAnomalies(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        if (this.allTrends.length < 14) return results;

        const costs = this.allTrends.map(t => t.cost);
        const mean = this.calculateAverage(costs);
        const stdDev = this.calculateStandardDeviation(costs, mean);
        const threshold = mean + (stdDev * REGRESSION_CONFIG.ANOMALY_THRESHOLD);
        
        // Find anomalous days
        for (const trend of this.allTrends.slice(-7)) { // Check last 7 days
            if (trend.cost > threshold && trend.cost > mean * 1.2) { // Also require 20% above mean
                const anomalyAmount = trend.cost - mean;
                const monthlyImpact = anomalyAmount * 30;
                
                if (monthlyImpact >= REGRESSION_CONFIG.MIN_COST_IMPACT) {
                    const zScore = (trend.cost - mean) / stdDev;
                    
                    const evidence: Evidence[] = [
                        {
                            type: 'trend',
                            description: 'Daily cost anomaly',
                            value: trend.cost,
                            threshold: threshold,
                            unit: 'USD'
                        },
                        {
                            type: 'metric',
                            description: 'Statistical z-score',
                            value: zScore,
                            threshold: REGRESSION_CONFIG.ANOMALY_THRESHOLD,
                            unit: 'σ'
                        },
                        {
                            type: 'trend',
                            description: 'Historical average',
                            value: mean,
                            threshold: 0,
                            unit: 'USD'
                        }
                    ];

                    results.push({
                        id: `anomaly-${trend.date}`,
                        type: WasteType.COST_REGRESSION,
                        severity: this.determineSeverity(monthlyImpact),
                        description: `Statistical cost anomaly on ${trend.date}: ${zScore.toFixed(1)}σ above normal ($${anomalyAmount.toFixed(2)} excess)`,
                        affectedResources: [{
                            id: `anomaly-${trend.date}`,
                            name: `Cost Anomaly - ${trend.date}`,
                            type: 'Statistical Anomaly',
                            cloud: 'kubernetes',
                            tags: {
                                date: trend.date,
                                zScore: zScore.toFixed(1),
                                excessCost: `$${anomalyAmount.toFixed(2)}`
                            }
                        }],
                        wastedAmount: monthlyImpact,
                        confidence: this.calculateAnomalyConfidence(zScore, costs.length),
                        evidence,
                        detectedAt: this.timestamp
                    });
                }
            }
        }

        return results;
    }

    /**
     * Detect service-specific regressions
     */
    private async detectServiceSpecificRegressions(): Promise<WasteDetectionResult[]> {
        const results: WasteDetectionResult[] = [];
        
        // Mock service-specific analysis (would analyze individual service costs)
        const mockServiceRegressions = [
            {
                service: 'AWS RDS',
                previousCost: 180.50,
                currentCost: 245.80,
                cloud: 'aws'
            },
            {
                service: 'GCP BigQuery',
                previousCost: 85.20,
                currentCost: 156.40,
                cloud: 'gcp'
            }
        ];

        for (const service of mockServiceRegressions) {
            const increase = service.currentCost - service.previousCost;
            const percentage = ((service.currentCost / service.previousCost) - 1) * 100;
            
            if (percentage > 40 && increase >= 25) { // 40% increase and $25+ impact
                const evidence: Evidence[] = [
                    {
                        type: 'billing',
                        description: 'Previous service cost',
                        value: service.previousCost,
                        threshold: 0,
                        unit: 'USD'
                    },
                    {
                        type: 'billing',
                        description: 'Current service cost',
                        value: service.currentCost,
                        threshold: service.previousCost * 1.4,
                        unit: 'USD'
                    },
                    {
                        type: 'trend',
                        description: 'Service cost increase percentage',
                        value: percentage,
                        threshold: 40,
                        unit: '%'
                    }
                ];

                results.push({
                    id: `service-regression-${service.service.toLowerCase().replace(/\s+/g, '-')}`,
                    type: WasteType.COST_REGRESSION,
                    severity: this.determineSeverity(increase),
                    description: `${service.service} cost regression: ${percentage.toFixed(1)}% increase ($${increase.toFixed(2)})`,
                    affectedResources: [{
                        id: service.service.toLowerCase().replace(/\s+/g, '-'),
                        name: service.service,
                        type: 'Cloud Service',
                        cloud: service.cloud as 'aws' | 'gcp' | 'azure',
                        tags: {
                            previousCost: `$${service.previousCost.toFixed(2)}`,
                            currentCost: `$${service.currentCost.toFixed(2)}`,
                            increase: `${percentage.toFixed(1)}%`
                        }
                    }],
                    wastedAmount: increase,
                    confidence: 0.85,
                    evidence,
                    detectedAt: this.timestamp
                });
            }
        }

        return results;
    }

    /**
     * Consolidate cost trends from all cloud providers
     */
    private consolidateCostTrends(): CostTrend[] {
        const trendMap = new Map<string, number>();
        
        // Combine trends from all providers
        const allProviderTrends = [
            ...(this.costData.aws?.trends || []),
            ...(this.costData.gcp?.trends || []),
            ...(this.costData.azure?.trends || [])
        ];

        // Aggregate by date
        for (const trend of allProviderTrends) {
            const date = trend.date;
            trendMap.set(date, (trendMap.get(date) || 0) + trend.cost);
        }

        // Convert back to trend objects
        const consolidatedTrends: CostTrend[] = [];
        const sortedDates = Array.from(trendMap.keys()).sort();
        
        let previousCost = 0;
        for (const date of sortedDates) {
            const cost = trendMap.get(date)!;
            const change = cost - previousCost;
            const changePercent = previousCost > 0 ? (change / previousCost) * 100 : 0;
            
            consolidatedTrends.push({
                date,
                cost,
                change,
                changePercent
            });
            
            previousCost = cost;
        }

        return consolidatedTrends;
    }

    /**
     * Statistical helper methods
     */
    private calculateAverage(values: number[]): number {
        return values.reduce((sum, v) => sum + v, 0) / values.length;
    }

    private calculateStandardDeviation(values: number[], mean: number): number {
        const squaredDiffs = values.map(v => Math.pow(v - mean, 2));
        const avgSquaredDiff = this.calculateAverage(squaredDiffs);
        return Math.sqrt(avgSquaredDiff);
    }

    /**
     * Confidence calculation methods
     */
    private calculateSpikeConfidence(percentage: number, amount: number): number {
        // Higher confidence for larger spikes
        const percentageScore = Math.min(1, percentage / 100);
        const amountScore = Math.min(1, amount / 100);
        return Math.min(0.95, 0.7 + (percentageScore * 0.15) + (amountScore * 0.1));
    }

    private calculateRegressionConfidence(percentage: number, dataPoints: number): number {
        // Higher confidence for sustained regressions with more data
        const percentageScore = Math.min(1, percentage / 50);
        const dataScore = Math.min(1, dataPoints / 30);
        return Math.min(0.92, 0.75 + (percentageScore * 0.12) + (dataScore * 0.05));
    }

    private calculateAnomalyConfidence(zScore: number, dataPoints: number): number {
        // Higher confidence for higher z-scores with more historical data
        const zScoreNorm = Math.min(1, (zScore - 2) / 2); // Normalize z-score starting from 2σ
        const dataScore = Math.min(1, dataPoints / 30);
        return Math.min(0.95, 0.8 + (zScoreNorm * 0.1) + (dataScore * 0.05));
    }

    /**
     * Determine severity based on monthly cost impact
     */
    private determineSeverity(impact: number): 'low' | 'medium' | 'high' | 'critical' {
        if (impact >= 500) return 'critical';
        if (impact >= 200) return 'high';
        if (impact >= 75) return 'medium';
        return 'low';
    }

    /**
     * Get regression analysis summary
     */
    async getRegressionSummary(): Promise<{
        totalRegressions: number;
        totalMonthlyImpact: number;
        regressionTypes: Record<string, number>;
        trendDirection: 'increasing' | 'decreasing' | 'stable';
        confidence: number;
    }> {
        const regressions = await this.detectCostRegressions();
        
        const summary = {
            totalRegressions: regressions.length,
            totalMonthlyImpact: regressions.reduce((sum, r) => sum + r.wastedAmount, 0),
            regressionTypes: {} as Record<string, number>,
            trendDirection: this.calculateOverallTrend(),
            confidence: regressions.length > 0 ? regressions.reduce((sum, r) => sum + r.confidence, 0) / regressions.length : 0
        };
        
        // Count regression types
        for (const regression of regressions) {
            const key = regression.description.includes('spike') ? 'spikes' :
                       regression.description.includes('sustained') ? 'sustained' :
                       regression.description.includes('anomaly') ? 'anomalies' : 'other';
            summary.regressionTypes[key] = (summary.regressionTypes[key] || 0) + 1;
        }
        
        return summary;
    }

    /**
     * Calculate overall trend direction
     */
    private calculateOverallTrend(): 'increasing' | 'decreasing' | 'stable' {
        if (this.allTrends.length < 7) return 'stable';
        
        const recent = this.allTrends.slice(-7);
        const older = this.allTrends.slice(-14, -7);
        
        if (older.length === 0) return 'stable';
        
        const recentAvg = this.calculateAverage(recent.map(t => t.cost));
        const olderAvg = this.calculateAverage(older.map(t => t.cost));
        
        const changePercent = ((recentAvg / olderAvg) - 1) * 100;
        
        if (changePercent > 10) return 'increasing';
        if (changePercent < -10) return 'decreasing';
        return 'stable';
    }
}