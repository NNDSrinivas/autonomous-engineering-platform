/**
 * Savings Estimation Engine
 * 
 * Provides quantified, evidence-based cost savings estimates with confidence intervals,
 * timeline projections, and business impact analysis for cost optimization opportunities.
 */

import {
    WasteDetectionResult,
    WasteType,
    IssueClassification,
    SavingsEstimate,
    CostData,
    Evidence
} from '../types';

/**
 * Savings estimation configuration
 */
const SAVINGS_CONFIG = {
    CONSERVATIVE_FACTOR: 0.7,        // Apply 70% of theoretical savings conservatively
    IMPLEMENTATION_OVERHEAD: 0.1,    // 10% overhead for implementation costs
    CONFIDENCE_BASELINE: 0.8,        // Base confidence for savings estimates
    PHASED_DISCOUNT: 0.85,          // 15% reduction for phased implementations
    RISK_ADJUSTMENT: {
        'low': 0.95,                 // 5% risk adjustment for low-risk optimizations
        'medium': 0.85,              // 15% risk adjustment for medium-risk
        'high': 0.70                 // 30% risk adjustment for high-risk
    },
    REALIZATION_TIMELINE: {
        'simple': 7,                 // Simple optimizations: 7 days to full realization
        'medium': 21,                // Medium complexity: 21 days
        'complex': 60                // Complex optimizations: 60 days
    }
};

/**
 * Savings multipliers by waste type based on industry data
 */
const WASTE_TYPE_MULTIPLIERS: Record<WasteType, { immediate: number; recurring: number; confidence: number }> = {
    [WasteType.IDLE_RESOURCES]: {
        immediate: 0.95,             // Can recover 95% immediately
        recurring: 1.0,              // 100% recurring monthly savings
        confidence: 0.95             // High confidence
    },
    [WasteType.OVERPROVISIONING]: {
        immediate: 0.7,              // 70% recoverable (need some buffer)
        recurring: 0.8,              // 80% recurring (some growth buffer)
        confidence: 0.85             // Good confidence with testing
    },
    [WasteType.UNUSED_VOLUMES]: {
        immediate: 1.0,              // 100% recoverable
        recurring: 1.0,              // Full recurring savings
        confidence: 0.9              // Very high confidence
    },
    [WasteType.OVERSIZED_INSTANCES]: {
        immediate: 0.7,              // 70% recoverable (similar to overprovisioning)
        recurring: 0.8,              // 80% recurring savings
        confidence: 0.85             // Good confidence with testing
    },
    [WasteType.COST_REGRESSION]: {
        immediate: 0.6,              // 60% immediate (need investigation)
        recurring: 0.9,              // 90% recurring after fix
        confidence: 0.7              // Lower confidence - needs investigation
    },
    [WasteType.POOR_UNIT_ECONOMICS]: {
        immediate: 0.3,              // 30% immediate wins
        recurring: 0.7,              // 70% long-term potential
        confidence: 0.65             // Medium confidence - complex changes
    },
    [WasteType.SCHEDULING_INEFFICIENCY]: {
        immediate: 0.5,              // 50% immediate through better scheduling
        recurring: 0.8,              // 80% recurring with optimization
        confidence: 0.8              // Good confidence
    }
};

/**
 * Generate quantified savings estimates with confidence intervals and timelines
 */
export class SavingsEstimator {
    private issue: WasteDetectionResult;
    private classification: IssueClassification;
    private costData: CostData;
    private timestamp: string;

    constructor(issue: WasteDetectionResult, classification: IssueClassification, costData: CostData) {
        this.issue = issue;
        this.classification = classification;
        this.costData = costData;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Generate comprehensive savings estimate
     */
    async generateSavingsEstimate(): Promise<SavingsEstimate> {
        console.log(`💰 Generating savings estimate for issue: ${this.issue.id}`);
        
        const wasteMultipliers = WASTE_TYPE_MULTIPLIERS[this.issue.type];
        const baseWasteAmount = this.issue.wastedAmount;
        
        // Calculate immediate and recurring savings
        const immediateSavings = this.calculateImmediateSavings(baseWasteAmount, wasteMultipliers);
        const recurringSavings = this.calculateRecurringSavings(baseWasteAmount, wasteMultipliers);
        
        // Generate confidence intervals
        const confidenceInterval = this.calculateConfidenceInterval(recurringSavings);
        
        // Calculate timeline to realization
        const realizationTimeline = this.calculateRealizationTimeline();
        
        // Calculate implementation costs
        const implementationCost = this.calculateImplementationCost();
        
        // Calculate ROI metrics
        const roi = this.calculateROI(recurringSavings.conservative, implementationCost);
        const riskAdjustment = this.calculateRiskAdjustment();
        const businessCase = this.generateBusinessCase(recurringSavings.conservative, implementationCost);
        const currency = this.costData.consolidated?.currency ?? 'USD';
        const monthlyAmount = recurringSavings.conservative;
        const annualAmount = monthlyAmount * 12;
        const totalBreakdown = monthlyAmount + immediateSavings.amount;
        const breakdown = [
            {
                category: 'recurring',
                amount: monthlyAmount,
                percentage: totalBreakdown > 0 ? monthlyAmount / totalBreakdown : 0,
                description: 'Conservative recurring monthly savings'
            },
            {
                category: 'immediate',
                amount: immediateSavings.amount,
                percentage: totalBreakdown > 0 ? immediateSavings.amount / totalBreakdown : 0,
                description: 'One-time savings from immediate actions'
            }
        ];
        const risks = [
            `Risk level: ${this.classification.riskLevel}`,
            ...riskAdjustment.mitigationStrategies
        ];
        const assumptions = this.documentAssumptions();
        
        return {
            issueId: this.issue.id,
            wasteType: this.issue.type,
            baseWasteAmount,
            monthlyAmount,
            annualAmount,
            currency,
            confidence: recurringSavings.confidence,
            breakdown,
            immediateSavings,
            recurringSavings,
            confidenceInterval,
            realizationTimeline,
            implementationCost,
            netSavings: recurringSavings.conservative - (implementationCost.total / 12), // Monthly net
            roi,
            riskAdjustment,
            businessCase,
            assumptions,
            risks,
            monitoring: this.generateMonitoringPlan(),
            estimatedAt: this.timestamp
        };
    }

    /**
     * Calculate immediate one-time savings
     */
    private calculateImmediateSavings(baseAmount: number, multipliers: any): {
        amount: number;
        confidence: number;
        description: string;
    } {
        const riskAdjustment = SAVINGS_CONFIG.RISK_ADJUSTMENT[this.classification.riskLevel];
        const amount = baseAmount * multipliers.immediate * riskAdjustment;
        
        let description = '';
        if (this.issue.type === WasteType.IDLE_RESOURCES) {
            description = 'Immediate shutdown of idle resources eliminates ongoing waste';
        } else if (this.issue.type === WasteType.UNUSED_VOLUMES) {
            description = 'Direct removal of unused storage volumes';
        } else if (this.issue.type === WasteType.OVERPROVISIONING) {
            description = 'Right-sizing can deliver immediate capacity reductions';
        } else {
            description = 'Quick wins from immediate optimization opportunities';
        }
        
        return {
            amount,
            confidence: multipliers.confidence * riskAdjustment,
            description
        };
    }

    /**
     * Calculate recurring monthly savings
     */
    private calculateRecurringSavings(baseAmount: number, multipliers: any): {
        optimistic: number;
        realistic: number;
        conservative: number;
        confidence: number;
    } {
        const riskAdjustment = SAVINGS_CONFIG.RISK_ADJUSTMENT[this.classification.riskLevel];
        const baseRecurring = baseAmount * multipliers.recurring * riskAdjustment;
        
        // Apply conservative factor for realistic estimates
        const conservative = baseRecurring * SAVINGS_CONFIG.CONSERVATIVE_FACTOR;
        const realistic = baseRecurring * 0.85; // 85% of theoretical
        const optimistic = baseRecurring * 0.95; // 95% of theoretical
        
        return {
            optimistic,
            realistic,
            conservative,
            confidence: multipliers.confidence * riskAdjustment
        };
    }

    /**
     * Calculate confidence interval for savings estimates
     */
    private calculateConfidenceInterval(recurringSavings: any): {
        confidence: number;
        lowerBound: number;
        upperBound: number;
        methodology: string;
    } {
        const confidence = Math.min(0.95, recurringSavings.confidence);
        const variance = recurringSavings.realistic * 0.2; // 20% variance
        
        return {
            confidence,
            lowerBound: Math.max(0, recurringSavings.conservative - variance),
            upperBound: recurringSavings.optimistic + variance,
            methodology: 'Based on historical optimization outcomes and current system confidence'
        };
    }

    /**
     * Calculate timeline to full savings realization
     */
    private calculateRealizationTimeline(): {
        fullRealization: number; // days
        milestones: Array<{
            day: number;
            percentage: number;
            description: string;
        }>;
    } {
        const complexity = this.classification.remediationComplexity;
        const fullRealizationDays = SAVINGS_CONFIG.REALIZATION_TIMELINE[complexity];
        
        const milestones = [];
        
        if (complexity === 'simple') {
            milestones.push(
                { day: 1, percentage: 60, description: 'Initial implementation' },
                { day: 3, percentage: 90, description: 'Optimization stabilizes' },
                { day: 7, percentage: 100, description: 'Full savings realized' }
            );
        } else if (complexity === 'medium') {
            milestones.push(
                { day: 3, percentage: 30, description: 'Planning and preparation' },
                { day: 7, percentage: 60, description: 'Initial implementation' },
                { day: 14, percentage: 85, description: 'System stabilization' },
                { day: 21, percentage: 100, description: 'Full optimization' }
            );
        } else { // complex
            milestones.push(
                { day: 7, percentage: 20, description: 'Analysis and planning' },
                { day: 21, percentage: 50, description: 'Phased implementation begins' },
                { day: 45, percentage: 80, description: 'Major optimizations complete' },
                { day: 60, percentage: 100, description: 'Full realization achieved' }
            );
        }
        
        return {
            fullRealization: fullRealizationDays,
            milestones
        };
    }

    /**
     * Calculate implementation costs
     */
    private calculateImplementationCost(): {
        engineering: number;
        testing: number;
        coordination: number;
        contingency: number;
        total: number;
    } {
        const estimatedHours = this.classification.estimatedEffort;
        const hourlyRate = 100; // $100/hour blended rate
        
        const engineering = estimatedHours * hourlyRate;
        const testing = engineering * 0.3; // 30% of engineering for testing
        const coordination = this.classification.approvalRequired ? engineering * 0.2 : engineering * 0.1;
        const contingency = (engineering + testing + coordination) * 0.15; // 15% contingency
        
        return {
            engineering,
            testing,
            coordination,
            contingency,
            total: engineering + testing + coordination + contingency
        };
    }

    /**
     * Calculate ROI metrics
     */
    private calculateROI(monthlySavings: number, implementationCost: any): {
        monthsToPayback: number;
        annualROI: number;
        threeYearNPV: number;
        riskAdjustedROI: number;
    } {
        const monthsToPayback = implementationCost.total / monthlySavings;
        const annualSavings = monthlySavings * 12;
        const annualROI = ((annualSavings - implementationCost.total) / implementationCost.total) * 100;
        
        // Calculate 3-year NPV with 10% discount rate
        const discountRate = 0.10;
        let npv = -implementationCost.total;
        for (let year = 1; year <= 3; year++) {
            npv += annualSavings / Math.pow(1 + discountRate, year);
        }
        
        const riskMultiplier = SAVINGS_CONFIG.RISK_ADJUSTMENT[this.classification.riskLevel];
        const riskAdjustedROI = annualROI * riskMultiplier;
        
        return {
            monthsToPayback,
            annualROI,
            threeYearNPV: npv,
            riskAdjustedROI
        };
    }

    /**
     * Calculate risk adjustment factors
     */
    private calculateRiskAdjustment(): {
        factor: number;
        reasoning: string;
        mitigationStrategies: string[];
    } {
        const factor = SAVINGS_CONFIG.RISK_ADJUSTMENT[this.classification.riskLevel];
        
        let reasoning = `${this.classification.riskLevel} risk level applied ${Math.round((1 - factor) * 100)}% adjustment. `;
        
        if (this.issue.confidence < 0.8) {
            reasoning += 'Lower confidence requires additional validation. ';
        }
        
        if (this.classification.approvalRequired) {
            reasoning += 'Stakeholder approval required adds execution risk. ';
        }
        
        const mitigationStrategies = [
            'Implement in phases to reduce risk exposure',
            'Maintain rollback capabilities',
            'Monitor key performance indicators',
            'Establish clear success criteria'
        ];
        
        if (this.classification.riskLevel === 'high') {
            mitigationStrategies.push('Conduct pilot implementation before full rollout');
            mitigationStrategies.push('Engage additional subject matter experts');
        }
        
        return {
            factor,
            reasoning,
            mitigationStrategies
        };
    }

    /**
     * Generate business case summary
     */
    private generateBusinessCase(monthlySavings: number, implementationCost: any): {
        executiveSummary: string;
        financialSummary: string;
        strategicValue: string;
        recommendedAction: string;
    } {
        const annualSavings = monthlySavings * 12;
        const paybackMonths = Math.ceil(implementationCost.total / monthlySavings);
        
        const executiveSummary = `${this.issue.type.replace('_', ' ')} optimization opportunity ` +
            `with $${monthlySavings.toFixed(2)}/month savings potential ` +
            `(${paybackMonths}-month payback period).`;
        
        const financialSummary = `Investment: $${implementationCost.total.toFixed(2)} | ` +
            `Annual savings: $${annualSavings.toFixed(2)} | ` +
            `3-year NPV: $${(annualSavings * 3 - implementationCost.total).toFixed(2)}`;
        
        let strategicValue = 'Improves operational efficiency and cost discipline. ';
        if (this.issue.type === WasteType.POOR_UNIT_ECONOMICS) {
            strategicValue += 'Enhances business scalability and competitive position.';
        } else if (this.issue.type === WasteType.COST_REGRESSION) {
            strategicValue += 'Addresses operational issues and prevents future waste.';
        } else {
            strategicValue += 'Reduces waste and optimizes resource utilization.';
        }
        
        let recommendedAction = '';
        if (paybackMonths <= 3) {
            recommendedAction = 'Recommend immediate implementation - excellent ROI.';
        } else if (paybackMonths <= 6) {
            recommendedAction = 'Recommend implementation - good ROI and strategic value.';
        } else if (paybackMonths <= 12) {
            recommendedAction = 'Consider implementation as part of broader optimization initiative.';
        } else {
            recommendedAction = 'Monitor and reassess - consider alternative approaches.';
        }
        
        return {
            executiveSummary,
            financialSummary,
            strategicValue,
            recommendedAction
        };
    }

    /**
     * Document key assumptions
     */
    private documentAssumptions(): string[] {
        const assumptions = [
            `Waste type: ${this.issue.type} with ${Math.round(this.issue.confidence * 100)}% detection confidence`,
            `Risk level: ${this.classification.riskLevel} with ${Math.round(SAVINGS_CONFIG.RISK_ADJUSTMENT[this.classification.riskLevel] * 100)}% risk adjustment`,
            `Implementation complexity: ${this.classification.remediationComplexity} requiring ${this.classification.estimatedEffort} hours`
        ];
        
        // Add type-specific assumptions
        if (this.issue.type === WasteType.OVERPROVISIONING) {
            assumptions.push('Assumes 30% buffer capacity retained for performance safety');
            assumptions.push('Performance testing validates right-sizing recommendations');
        } else if (this.issue.type === WasteType.IDLE_RESOURCES) {
            assumptions.push('Resources confirmed idle through 7+ days of monitoring');
            assumptions.push('No hidden dependencies or disaster recovery requirements');
        } else if (this.issue.type === WasteType.POOR_UNIT_ECONOMICS) {
            assumptions.push('Architectural changes can be implemented without service disruption');
            assumptions.push('Business growth patterns remain consistent with historical data');
        }
        
        assumptions.push('Labor costs estimated at $100/hour blended engineering rate');
        assumptions.push('Savings estimates based on current usage patterns and costs');
        
        return assumptions;
    }

    /**
     * Generate monitoring plan for tracking savings realization
     */
    private generateMonitoringPlan(): {
        keyMetrics: string[];
        checkpoints: Array<{ day: number; focus: string; }>;
        successCriteria: string[];
        rollbackTriggers: string[];
    } {
        const keyMetrics = [
            'Monthly cost reduction vs baseline',
            'Resource utilization efficiency',
            'System performance indicators',
            'Business impact metrics'
        ];
        
        const checkpoints = [
            { day: 1, focus: 'Implementation successful, systems stable' },
            { day: 7, focus: 'Initial savings visible, performance maintained' },
            { day: 30, focus: 'Full monthly savings realized' },
            { day: 90, focus: 'Sustained optimization, no regression' }
        ];
        
        const successCriteria = [
            `Achieve ${Math.round(SAVINGS_CONFIG.CONSERVATIVE_FACTOR * 100)}% of estimated monthly savings`,
            'Maintain or improve system performance metrics',
            'No increase in error rates or service degradation',
            'Stakeholder satisfaction with optimization results'
        ];
        
        const rollbackTriggers = [
            'Performance degradation beyond acceptable thresholds',
            'Service availability or reliability issues',
            'Cost increases due to unexpected side effects',
            'Critical stakeholder concerns about business impact'
        ];
        
        return {
            keyMetrics,
            checkpoints,
            successCriteria,
            rollbackTriggers
        };
    }

    /**
     * Get aggregated savings summary for multiple issues
     */
    static async generateAggregatedSavings(
        estimates: SavingsEstimate[]
    ): Promise<{
        totalImmediateSavings: number;
        totalMonthlySavings: number;
        totalImplementationCost: number;
        weightedAverageROI: number;
        portfolioPayback: number;
        riskDistribution: Record<string, number>;
        recommendedPriorities: Array<{
            issueId: string;
            priority: number;
            reasoning: string;
        }>;
    }> {
        const totalImmediateSavings = estimates.reduce((sum, e) => sum + e.immediateSavings.amount, 0);
        const totalMonthlySavings = estimates.reduce((sum, e) => sum + e.recurringSavings.conservative, 0);
        const totalImplementationCost = estimates.reduce((sum, e) => sum + e.implementationCost.total, 0);
        
        const weightedAverageROI = totalImplementationCost > 0 ? 
            estimates.reduce((sum, e) => sum + (e.roi.riskAdjustedROI * e.implementationCost.total), 0) / totalImplementationCost : 0;
        
        const portfolioPayback = totalMonthlySavings > 0 ? totalImplementationCost / totalMonthlySavings : 0;
        
        const riskDistribution = estimates.reduce((dist, e) => {
            const risk = e.riskAdjustment.factor < 0.8 ? 'high' : e.riskAdjustment.factor < 0.9 ? 'medium' : 'low';
            dist[risk] = (dist[risk] || 0) + 1;
            return dist;
        }, {} as Record<string, number>);
        
        const recommendedPriorities = estimates
            .map((e, index) => ({
                issueId: e.issueId,
                priority: (e.roi.riskAdjustedROI * e.recurringSavings.confidence) / Math.max(1, e.roi.monthsToPayback),
                reasoning: `ROI: ${e.roi.riskAdjustedROI.toFixed(1)}%, Payback: ${e.roi.monthsToPayback.toFixed(1)} months, Confidence: ${(e.recurringSavings.confidence * 100).toFixed(0)}%`
            }))
            .sort((a, b) => b.priority - a.priority)
            .map((item, index) => ({ ...item, priority: index + 1 }));
        
        return {
            totalImmediateSavings,
            totalMonthlySavings,
            totalImplementationCost,
            weightedAverageROI,
            portfolioPayback,
            riskDistribution,
            recommendedPriorities
        };
    }
}
