/**
 * Issue Classification for Cost Optimization
 * 
 * Classifies cost optimization issues by type, severity, business impact,
 * and remediation complexity following NAVI diagnostic patterns.
 */

import {
    WasteDetectionResult,
    WasteType,
    IssueClassification,
    BusinessImpact,
    RemediationComplexity,
    IssueType,
    IssueSeverity,
    IssuePriority,
    TechnicalDetails,
    TechnicalMetric
} from '../types';

/**
 * Classification configuration
 */
const CLASSIFICATION_CONFIG = {
    HIGH_IMPACT_THRESHOLD: 200,        // $200+/month = high business impact
    CRITICAL_IMPACT_THRESHOLD: 500,    // $500+/month = critical business impact
    COMPLEX_REMEDIATION_THRESHOLD: 0.7, // < 70% confidence = complex remediation
    URGENT_SEVERITY_DAYS: 7,           // Issues active for 7+ days are urgent
    PATTERN_RECOGNITION_THRESHOLD: 3   // 3+ similar issues = pattern
};

type BusinessImpactLevel = Extract<BusinessImpact, string>;

type IssueTypeMetadata = {
    category: string;
    typicalCauses: string[];
    businessRisk: BusinessImpactLevel;
    remediationSpeed: 'fast' | 'medium' | 'slow';
    approvalRequired: boolean;
};

/**
 * Issue type classifications with remediation guidance
 */
const ISSUE_TYPE_METADATA: Record<WasteType, IssueTypeMetadata> = {
    [WasteType.IDLE_RESOURCES]: {
        category: 'Resource Management',
        typicalCauses: ['Over-provisioning', 'Development environments left running', 'Seasonal workload changes'],
        businessRisk: 'low',
        remediationSpeed: 'fast',
        approvalRequired: false
    },
    [WasteType.OVERPROVISIONING]: {
        category: 'Capacity Planning',
        typicalCauses: ['Conservative sizing', 'Workload changes', 'Inefficient resource requests'],
        businessRisk: 'medium',
        remediationSpeed: 'medium',
        approvalRequired: true
    },
    [WasteType.UNUSED_VOLUMES]: {
        category: 'Storage Management',
        typicalCauses: ['Forgotten storage', 'Incomplete cleanup', 'Orphaned volumes'],
        businessRisk: 'low',
        remediationSpeed: 'fast',
        approvalRequired: false
    },
    [WasteType.OVERSIZED_INSTANCES]: {
        category: 'Capacity Planning',
        typicalCauses: ['Legacy sizing', 'Workload decreases', 'Overestimated peak demand'],
        businessRisk: 'medium',
        remediationSpeed: 'medium',
        approvalRequired: true
    },
    [WasteType.COST_REGRESSION]: {
        category: 'Operational Efficiency',
        typicalCauses: ['Configuration changes', 'Workload increases', 'Service degradation'],
        businessRisk: 'high',
        remediationSpeed: 'medium',
        approvalRequired: true
    },
    [WasteType.POOR_UNIT_ECONOMICS]: {
        category: 'Business Efficiency',
        typicalCauses: ['Architectural inefficiencies', 'Scaling issues', 'Service design problems'],
        businessRisk: 'high',
        remediationSpeed: 'slow',
        approvalRequired: true
    },
    [WasteType.SCHEDULING_INEFFICIENCY]: {
        category: 'Workload Management',
        typicalCauses: ['Poor scheduling policies', 'Resource contention', 'Inefficient scaling'],
        businessRisk: 'medium',
        remediationSpeed: 'medium',
        approvalRequired: true
    }
};

const ISSUE_TYPE_MAP: Record<WasteType, IssueType> = {
    [WasteType.IDLE_RESOURCES]: IssueType.IDLE_RESOURCES,
    [WasteType.OVERPROVISIONING]: IssueType.OVERPROVISIONING,
    [WasteType.UNUSED_VOLUMES]: IssueType.UNUSED_SERVICES,
    [WasteType.OVERSIZED_INSTANCES]: IssueType.OVERPROVISIONING,
    [WasteType.COST_REGRESSION]: IssueType.COST_REGRESSION,
    [WasteType.POOR_UNIT_ECONOMICS]: IssueType.POOR_RESOURCE_ALLOCATION,
    [WasteType.SCHEDULING_INEFFICIENCY]: IssueType.INEFFICIENT_SCALING
};

/**
 * Classify cost optimization issues for prioritization and remediation planning
 */
export class IssueClassifier {
    private detectionResults: WasteDetectionResult[];
    private timestamp: string;

    constructor(detectionResults: WasteDetectionResult[]) {
        this.detectionResults = detectionResults;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Classify all detected issues
     */
    async classifyAllIssues(): Promise<IssueClassification[]> {
        console.log('🔍 Classifying cost optimization issues...');
        
        const classifications: IssueClassification[] = [];
        
        for (const issue of this.detectionResults) {
            const classification = await this.classifyIssue(issue);
            classifications.push(classification);
        }

        // Identify patterns across issues
        const patternsDetected = this.identifyIssuePatterns(classifications);
        
        // Update classifications with pattern information
        this.enrichWithPatterns(classifications, patternsDetected);
        
        // Sort by priority (business impact + urgency)
        classifications.sort((a, b) => this.calculatePriority(b) - this.calculatePriority(a));
        
        const totalIssues = classifications.length;
        const criticalIssues = classifications.filter(c => c.businessImpact === 'critical').length;
        const highImpactIssues = classifications.filter(c => c.businessImpact === 'high').length;
        
        console.log(`📋 Issue classification complete: ${totalIssues} issues (${criticalIssues} critical, ${highImpactIssues} high impact)`);
        
        return classifications;
    }

    /**
     * Classify a single issue
     */
    async classifyIssue(issue: WasteDetectionResult): Promise<IssueClassification> {
        const metadata = ISSUE_TYPE_METADATA[issue.type];
        const severity = this.determineSeverity(issue);
        const priority = this.determinePriority(severity, issue);
        const recommendations = this.generateRecommendedActions(issue, metadata);
        
        return {
            type: ISSUE_TYPE_MAP[issue.type] || IssueType.POOR_RESOURCE_ALLOCATION,
            severity,
            priority,
            confidence: issue.confidence,
            reasoning: issue.description,
            issueId: issue.id,
            wasteType: issue.type,
            category: metadata.category,
            businessImpact: this.determineBusinessImpact(issue),
            remediationComplexity: this.determineRemediationComplexity(issue),
            urgency: this.determineUrgency(issue),
            riskLevel: this.determineRiskLevel(issue, metadata),
            affectedSystems: this.extractAffectedSystems(issue),
            estimatedEffort: this.estimateRemediationEffort(issue, metadata),
            approvalRequired: metadata.approvalRequired && issue.wastedAmount > 100,
            businessJustification: this.generateBusinessJustification(issue),
            typicalCauses: metadata.typicalCauses,
            recommendedActions: recommendations,
            technicalDetails: this.buildTechnicalDetails(issue, recommendations),
            nextSteps: recommendations,
            classifiedAt: this.timestamp
        };
    }

    private determineSeverity(issue: WasteDetectionResult): IssueSeverity {
        if (issue.wastedAmount >= CLASSIFICATION_CONFIG.CRITICAL_IMPACT_THRESHOLD) {
            return IssueSeverity.CRITICAL;
        }
        if (issue.wastedAmount >= CLASSIFICATION_CONFIG.HIGH_IMPACT_THRESHOLD) {
            return IssueSeverity.HIGH;
        }
        if (issue.wastedAmount >= 75) {
            return IssueSeverity.MEDIUM;
        }
        return IssueSeverity.LOW;
    }

    private determinePriority(severity: IssueSeverity, issue: WasteDetectionResult): IssuePriority {
        if (severity === IssueSeverity.CRITICAL || issue.wastedAmount >= 500) {
            return IssuePriority.P0;
        }
        if (severity === IssueSeverity.HIGH || issue.wastedAmount >= 200) {
            return IssuePriority.P1;
        }
        if (severity === IssueSeverity.MEDIUM || issue.wastedAmount >= 75) {
            return IssuePriority.P2;
        }
        return IssuePriority.P3;
    }

    private buildTechnicalDetails(issue: WasteDetectionResult, recommendations: string[]): TechnicalDetails {
        const metrics: TechnicalMetric[] = issue.evidence.map((evidence) => ({
            name: evidence.type,
            value: evidence.value,
            unit: evidence.unit,
            threshold: evidence.threshold,
            status: evidence.value > evidence.threshold ? 'critical' : 'warning'
        }));

        return {
            rootCause: issue.description,
            symptoms: [issue.description],
            metrics,
            recommendations
        };
    }

    /**
     * Determine business impact level
     */
    private determineBusinessImpact(issue: WasteDetectionResult): BusinessImpact {
        const monthlyImpact = issue.wastedAmount;
        
        if (monthlyImpact >= CLASSIFICATION_CONFIG.CRITICAL_IMPACT_THRESHOLD) {
            return 'critical';
        }
        if (monthlyImpact >= CLASSIFICATION_CONFIG.HIGH_IMPACT_THRESHOLD) {
            return 'high';
        }
        if (monthlyImpact >= 75) {
            return 'medium';
        }
        return 'low';
    }

    /**
     * Determine remediation complexity
     */
    private determineRemediationComplexity(issue: WasteDetectionResult): RemediationComplexity {
        // Low confidence suggests complex remediation
        if (issue.confidence < CLASSIFICATION_CONFIG.COMPLEX_REMEDIATION_THRESHOLD) {
            return 'complex';
        }
        
        // Multiple affected resources = more complexity
        if (issue.affectedResources.length > 3) {
            return 'medium';
        }
        
        // High confidence, single resource = simple
        if (issue.confidence > 0.85 && issue.affectedResources.length === 1) {
            return 'simple';
        }
        
        return 'medium';
    }

    /**
     * Determine urgency level
     */
    private determineUrgency(issue: WasteDetectionResult): 'low' | 'medium' | 'high' | 'critical' {
        const daysSinceDetection = this.calculateDaysSinceDetection(issue.detectedAt);
        const monthlyImpact = issue.wastedAmount;
        
        // Critical urgency for high-impact issues that have been ongoing
        if (monthlyImpact >= CLASSIFICATION_CONFIG.CRITICAL_IMPACT_THRESHOLD && daysSinceDetection >= CLASSIFICATION_CONFIG.URGENT_SEVERITY_DAYS) {
            return 'critical';
        }
        
        // High urgency for cost regressions (they indicate problems)
        if (issue.type === WasteType.COST_REGRESSION) {
            return 'high';
        }
        
        // High urgency for significant ongoing waste
        if (monthlyImpact >= CLASSIFICATION_CONFIG.HIGH_IMPACT_THRESHOLD && daysSinceDetection >= 3) {
            return 'high';
        }
        
        if (monthlyImpact >= 100) {
            return 'medium';
        }
        
        return 'low';
    }

    /**
     * Determine risk level for remediation
     */
    private determineRiskLevel(issue: WasteDetectionResult, metadata: IssueTypeMetadata): 'low' | 'medium' | 'high' {
        // Assess risk based on business impact and affected resources
        const businessRisk = metadata.businessRisk;
        const affectedCriticalResources = issue.affectedResources.filter(r => 
            r.type.toLowerCase().includes('database') || 
            r.type.toLowerCase().includes('production')
        ).length;
        
        if (businessRisk === 'high' || affectedCriticalResources > 0) {
            return 'high';
        }
        
        if (businessRisk === 'medium' || issue.confidence < 0.8) {
            return 'medium';
        }
        
        return 'low';
    }

    /**
     * Extract affected systems and environments
     */
    private extractAffectedSystems(issue: WasteDetectionResult): string[] {
        const systems = new Set<string>();
        
        for (const resource of issue.affectedResources) {
            // Add cloud provider
            systems.add(resource.cloud);
            
            // Add namespace/environment if available
            if (resource.tags?.namespace) {
                systems.add(`namespace:${resource.tags.namespace}`);
            }
            
            // Add resource type category
            if (resource.type.toLowerCase().includes('database')) {
                systems.add('database');
            } else if (resource.type.toLowerCase().includes('compute')) {
                systems.add('compute');
            } else if (resource.type.toLowerCase().includes('storage')) {
                systems.add('storage');
            } else if (resource.type.toLowerCase().includes('network')) {
                systems.add('networking');
            }
        }
        
        return Array.from(systems);
    }

    /**
     * Estimate remediation effort in hours
     */
    private estimateRemediationEffort(issue: WasteDetectionResult, metadata: IssueTypeMetadata): number {
        const baseEffort = {
            'fast': 1,      // 1 hour
            'medium': 4,    // 4 hours (half day)
            'slow': 16      // 16 hours (2 days)
        };
        
        let effort = baseEffort[metadata.remediationSpeed] || 4;
        
        // Multiply by number of affected resources
        effort *= Math.min(issue.affectedResources.length, 5); // Cap at 5x
        
        // Add complexity multiplier
        if (issue.confidence < 0.7) {
            effort *= 1.5; // 50% more effort for low confidence
        }
        
        // Add approval overhead
        if (metadata.approvalRequired && issue.wastedAmount > 100) {
            effort += 2; // 2 hours for approval process
        }
        
        return Math.round(effort);
    }

    /**
     * Generate business justification
     */
    private generateBusinessJustification(issue: WasteDetectionResult): string {
        const monthlyWaste = issue.wastedAmount;
        const annualWaste = monthlyWaste * 12;
        const confidencePercent = Math.round(issue.confidence * 100);
        
        let justification = `Optimization opportunity identified with ${confidencePercent}% confidence. `;
        justification += `Monthly waste: $${monthlyWaste.toFixed(2)}, Annual impact: $${annualWaste.toFixed(2)}. `;
        
        if (issue.type === WasteType.IDLE_RESOURCES) {
            justification += 'Idle resources provide no business value and can be safely optimized.';
        } else if (issue.type === WasteType.OVERPROVISIONING) {
            justification += 'Right-sizing will improve cost efficiency while maintaining performance.';
        } else if (issue.type === WasteType.COST_REGRESSION) {
            justification += 'Cost regression indicates potential operational issues requiring investigation.';
        } else if (issue.type === WasteType.POOR_UNIT_ECONOMICS) {
            justification += 'Improving unit economics will enhance overall business efficiency and scalability.';
        } else {
            justification += 'Addressing this waste will improve operational efficiency and reduce costs.';
        }
        
        return justification;
    }

    /**
     * Generate recommended actions
     */
    private generateRecommendedActions(issue: WasteDetectionResult, metadata: IssueTypeMetadata): string[] {
        const actions: string[] = [];
        
        // Type-specific actions
        if (issue.type === WasteType.IDLE_RESOURCES) {
            actions.push('Verify resource is truly idle by checking usage patterns over 7+ days');
            actions.push('Confirm no business processes depend on this resource');
            actions.push('Schedule safe shutdown during maintenance window');
        } else if (issue.type === WasteType.OVERPROVISIONING) {
            actions.push('Analyze resource utilization patterns and peak usage');
            actions.push('Test performance with recommended right-sized configuration');
            actions.push('Implement gradual right-sizing with monitoring');
        } else if (issue.type === WasteType.COST_REGRESSION) {
            actions.push('Investigate root cause of cost increase');
            actions.push('Review recent configuration changes or deployments');
            actions.push('Implement cost monitoring alerts to prevent future regressions');
        } else if (issue.type === WasteType.POOR_UNIT_ECONOMICS) {
            actions.push('Analyze cost drivers and optimization opportunities');
            actions.push('Review service architecture for efficiency improvements');
            actions.push('Benchmark against industry standards and best practices');
        }
        
        // Common actions based on complexity
        if (metadata.approvalRequired) {
            actions.push('Obtain stakeholder approval before implementing changes');
        }
        
        actions.push('Monitor metrics after optimization to ensure effectiveness');
        actions.push('Document changes and update capacity planning assumptions');
        
        return actions;
    }

    /**
     * Identify patterns across issues
     */
    private identifyIssuePatterns(classifications: IssueClassification[]): Array<{
        pattern: string;
        count: number;
        totalImpact: number;
        affectedIssues: string[];
    }> {
        const patterns: Record<string, {
            count: number;
            totalImpact: number;
            affectedIssues: string[];
        }> = {};
        
        for (const classification of classifications) {
            // Pattern by waste type
            const typePattern = `type:${classification.wasteType}`;
            if (!patterns[typePattern]) {
                patterns[typePattern] = { count: 0, totalImpact: 0, affectedIssues: [] };
            }
            patterns[typePattern].count++;
            patterns[typePattern].affectedIssues.push(classification.issueId);
            
            // Pattern by affected system
            for (const system of classification.affectedSystems) {
                const systemPattern = `system:${system}`;
                if (!patterns[systemPattern]) {
                    patterns[systemPattern] = { count: 0, totalImpact: 0, affectedIssues: [] };
                }
                patterns[systemPattern].count++;
                patterns[systemPattern].affectedIssues.push(classification.issueId);
            }
        }
        
        // Return patterns with significant occurrence
        return Object.entries(patterns)
            .filter(([_, data]) => data.count >= CLASSIFICATION_CONFIG.PATTERN_RECOGNITION_THRESHOLD)
            .map(([pattern, data]) => ({
                pattern,
                count: data.count,
                totalImpact: data.totalImpact,
                affectedIssues: data.affectedIssues
            }));
    }

    /**
     * Enrich classifications with pattern information
     */
    private enrichWithPatterns(classifications: IssueClassification[], patterns: Array<{
        pattern: string;
        count: number;
        totalImpact: number;
        affectedIssues: string[];
    }>): void {
        for (const classification of classifications) {
            const relatedPatterns = patterns.filter(p => 
                p.affectedIssues.includes(classification.issueId)
            );
            
            if (relatedPatterns.length > 0) {
                // Add pattern information to business justification
                const patternInfo = relatedPatterns.map(p => 
                    `Part of ${p.pattern} pattern (${p.count} similar issues)`
                ).join(', ');
                
                classification.businessJustification += ` ${patternInfo}.`;
                
                // Increase urgency if part of a significant pattern
                if (relatedPatterns.some(p => p.count >= 5)) {
                    if (classification.urgency === 'low') classification.urgency = 'medium';
                    else if (classification.urgency === 'medium') classification.urgency = 'high';
                }
            }
        }
    }

    /**
     * Calculate priority score for sorting
     */
    private calculatePriority(classification: IssueClassification): number {
        const impactScore = {
            'critical': 100,
            'high': 75,
            'medium': 50,
            'low': 25
        };
        
        const urgencyScore = {
            'critical': 100,
            'high': 75,
            'medium': 50,
            'low': 25
        };
        
        const businessImpact = this.normalizeBusinessImpact(classification.businessImpact);
        const businessImpactPoints = impactScore[businessImpact];
        const urgencyPoints = urgencyScore[classification.urgency];
        
        // Weighted priority: 60% business impact, 40% urgency
        return (businessImpactPoints * 0.6) + (urgencyPoints * 0.4);
    }

    /**
     * Calculate days since detection
     */
    private calculateDaysSinceDetection(detectedAt: string): number {
        const now = new Date();
        const detected = new Date(detectedAt);
        const diffMs = now.getTime() - detected.getTime();
        return Math.floor(diffMs / (1000 * 60 * 60 * 24));
    }

    /**
     * Get classification summary
     */
    getClassificationSummary(classifications: IssueClassification[]): {
        totalIssues: number;
        byBusinessImpact: Record<BusinessImpactLevel, number>;
        byComplexity: Record<RemediationComplexity, number>;
        byUrgency: Record<string, number>;
        totalEstimatedEffort: number;
        approvalRequired: number;
        topPatterns: Array<{ pattern: string; count: number; }>;
    } {
        const summary = {
            totalIssues: classifications.length,
            byBusinessImpact: { 'critical': 0, 'high': 0, 'medium': 0, 'low': 0 } as Record<BusinessImpactLevel, number>,
            byComplexity: { 'simple': 0, 'medium': 0, 'complex': 0 } as Record<RemediationComplexity, number>,
            byUrgency: { 'critical': 0, 'high': 0, 'medium': 0, 'low': 0 },
            totalEstimatedEffort: 0,
            approvalRequired: 0,
            topPatterns: [] as Array<{ pattern: string; count: number; }>
        };
        
        for (const classification of classifications) {
            const businessImpact = this.normalizeBusinessImpact(classification.businessImpact);
            summary.byBusinessImpact[businessImpact]++;
            summary.byComplexity[classification.remediationComplexity]++;
            summary.byUrgency[classification.urgency]++;
            summary.totalEstimatedEffort += classification.estimatedEffort;
            
            if (classification.approvalRequired) {
                summary.approvalRequired++;
            }
        }
        
        return summary;
    }

    private normalizeBusinessImpact(impact: BusinessImpact): BusinessImpactLevel {
        if (typeof impact === 'string') {
            return impact;
        }

        const monthlyWaste = impact.monthlyWaste ?? 0;
        if (monthlyWaste >= CLASSIFICATION_CONFIG.CRITICAL_IMPACT_THRESHOLD) {
            return 'critical';
        }
        if (monthlyWaste >= CLASSIFICATION_CONFIG.HIGH_IMPACT_THRESHOLD) {
            return 'high';
        }
        if (monthlyWaste >= 75) {
            return 'medium';
        }
        return 'low';
    }
}
