/**
 * Cost Optimization Explanation Engine
 * 
 * Provides detailed explanations for cost optimization findings,
 * including technical context, business impact, and remediation guidance.
 */

import {
    WasteDetectionResult,
    WasteType,
    IssueClassification,
    CostExplanation,
    CostIssue,
    Evidence,
    DetailedRecommendation,
    ImplementationEffort,
    RootCauseAnalysis,
    BusinessContext,
    TechnicalAnalysis
} from '../types';

type CloudProvider = 'aws' | 'gcp' | 'azure' | 'kubernetes';

type ExplanationTemplate = {
    technical: string;
    business: string;
    remediation: string;
    riskFactors: string[];
};

/**
 * Explanation templates and context for different waste types
 */
const EXPLANATION_TEMPLATES: Record<WasteType, ExplanationTemplate> = {
    [WasteType.IDLE_RESOURCES]: {
        technical: 'Resource showing minimal utilization ({utilizationPct}%) over {observationPeriod} days. CPU usage averaged {avgCpu}% and memory usage {avgMemory}%.',
        business: 'Idle resources consume budget without delivering business value. This represents pure waste that can be eliminated safely.',
        remediation: 'Safe to shutdown after confirming no business dependencies. Can typically be removed immediately with minimal risk.',
        riskFactors: ['Verify no scheduled workloads', 'Check for disaster recovery dependencies', 'Confirm not used for development/testing']
    },
    [WasteType.OVERPROVISIONING]: {
        technical: 'Resource provisioned at {currentSize} but consistently using only {utilizationPct}% of capacity. Peak usage over {observationPeriod} days was {peakUsage}%.',
        business: 'Overprovisioned resources waste money on unused capacity. Right-sizing maintains performance while reducing costs.',
        remediation: 'Right-size to {recommendedSize} for estimated {savingsPct}% cost reduction. Requires testing and gradual implementation.',
        riskFactors: ['Monitor performance after changes', 'Consider burst capacity requirements', 'Plan for gradual scaling down']
    },
    [WasteType.OVERSIZED_INSTANCES]: {
        technical: 'Instance sized at {currentSize} but consistently using only {utilizationPct}% of capacity. Peak usage over {observationPeriod} days was {peakUsage}%.',
        business: 'Oversized instances waste money on unused capacity. Right-sizing maintains performance while reducing costs.',
        remediation: 'Right-size to {recommendedSize} for estimated {savingsPct}% cost reduction. Requires testing and gradual implementation.',
        riskFactors: ['Monitor performance after changes', 'Consider burst capacity requirements', 'Plan for gradual scaling down']
    },
    [WasteType.UNUSED_VOLUMES]: {
        technical: 'Storage volume {volumeId} ({volumeSize}GB) attached but showing {utilizationPct}% space usage with minimal I/O activity.',
        business: 'Unused storage volumes accumulate costs over time. Often forgotten after application changes or migrations.',
        remediation: 'Create backup if needed, then delete unused volume. Quick win with minimal business risk.',
        riskFactors: ['Verify no backup dependencies', 'Check for compliance retention requirements', 'Confirm not used for recovery scenarios']
    },
    [WasteType.COST_REGRESSION]: {
        technical: 'Cost increased {regressionPct}% from ${previousCost} to ${currentCost} over {timeframe}. Detected via {detectionMethod}.',
        business: 'Cost regressions often indicate operational problems, configuration drift, or uncontrolled growth affecting budget.',
        remediation: 'Investigate root cause immediately. May require configuration rollback, capacity adjustments, or process improvements.',
        riskFactors: ['May indicate underlying system problems', 'Could affect service performance', 'Requires investigation before optimization']
    },
    [WasteType.POOR_UNIT_ECONOMICS]: {
        technical: 'Cost per {unitType} is ${costPerUnit}, which is {benchmarkComparison}% above industry benchmark of ${benchmark}.',
        business: 'Poor unit economics reduce business efficiency and limit scalability. Affects profitability and competitive position.',
        remediation: 'Requires architectural analysis and systematic optimization. Medium to long-term effort with high business impact.',
        riskFactors: ['May require architectural changes', 'Could affect service delivery', 'Needs stakeholder alignment']
    },
    [WasteType.SCHEDULING_INEFFICIENCY]: {
        technical: 'Workload scheduling showing {efficiencyPct}% efficiency. Resources idle during {idleHours}h/day due to poor scheduling.',
        business: 'Inefficient scheduling wastes capacity during off-peak hours while potentially causing congestion during peak times.',
        remediation: 'Implement smarter scheduling policies, auto-scaling, or workload distribution strategies.',
        riskFactors: ['May affect workload performance', 'Requires scheduling policy changes', 'Could impact SLA compliance']
    }
};

/**
 * Technical context providers for different cloud resources
 */
const TECHNICAL_CONTEXT: Record<CloudProvider, Record<string, string>> = {
    'aws': {
        instances: 'AWS EC2 instances incur charges for compute capacity whether utilized or not. Idle instances continue billing for CPU, memory, and storage.',
        volumes: 'EBS volumes are billed based on provisioned capacity regardless of actual usage. Unattached volumes still incur charges.',
        database: 'RDS instances bill for allocated compute and storage. Idle databases with minimal connections still consume full resources.'
    },
    'gcp': {
        instances: 'GCP Compute Engine bills for allocated vCPUs and memory. Sustained use discounts apply automatically but idle resources waste these benefits.',
        volumes: 'Persistent disks are charged for provisioned space. Unused or oversized disks represent direct cost waste.',
        database: 'Cloud SQL instances charge for allocated CPU, memory and storage. Idle databases do not benefit from automatic scaling.'
    },
    'azure': {
        instances: 'Azure VMs charge for allocated compute resources. Reserved instance benefits are lost on idle or underutilized resources.',
        volumes: 'Managed disks bill based on provisioned tier and size. Unused storage capacity cannot be reclaimed automatically.',
        database: 'Azure SQL Database charges for compute and storage tiers. Idle databases still consume full allocation.'
    },
    'kubernetes': {
        pods: 'Kubernetes pods reserve cluster resources based on requests. Over-requested pods waste node capacity and prevent efficient scheduling.',
        namespaces: 'Namespace resource quotas may be overallocated, leading to cluster inefficiency and higher infrastructure costs.',
        nodes: 'Cluster nodes incur full costs regardless of pod density. Low utilization suggests overprovisioning or poor scheduling.'
    }
};

/**
 * Generate comprehensive explanations for cost optimization findings
 */
export class CostExplainer {
    private issue: WasteDetectionResult;
    private classification: IssueClassification;
    private timestamp: string;

    constructor(issue: WasteDetectionResult, classification: IssueClassification) {
        this.issue = issue;
        this.classification = classification;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Generate comprehensive explanation
     */
    async generateExplanation(): Promise<CostExplanation> {
        console.log(`📝 Generating explanation for issue: ${this.issue.id}`);
        
        const template = EXPLANATION_TEMPLATES[this.issue.type];
        const context = this.extractTechnicalContext();
        const rootCause = this.generateRootCauseAnalysis();
        
        return {
            issue: this.buildCostIssue(rootCause.primaryCause),
            rootCause,
            businessContext: this.generateBusinessContext(template),
            technicalAnalysis: this.generateTechnicalAnalysis(template, context),
            recommendations: this.generateRecommendations()
        };
    }

    /**
     * Generate issue summary
     */
    private generateSummary(): string {
        const wasteAmount = this.issue.wastedAmount;
        const confidencePercent = Math.round(this.issue.confidence * 100);
        const resourceCount = this.issue.affectedResources.length;
        
        let summary = `${this.issue.type.replace('_', ' ').toLowerCase()} detected with ${confidencePercent}% confidence, `;
        summary += `wasting $${wasteAmount.toFixed(2)}/month across ${resourceCount} resource${resourceCount > 1 ? 's' : ''}. `;
        summary += `Business impact: ${this.classification.businessImpact}, remediation complexity: ${this.classification.remediationComplexity}.`;
        
        return summary;
    }

    private buildCostIssue(rootCause: string): CostIssue {
        const title = `${this.issue.type.replace('_', ' ').toLowerCase()} optimization opportunity`;

        return {
            id: this.issue.id,
            type: this.classification.type,
            severity: this.classification.severity,
            title,
            description: this.issue.description,
            explanation: rootCause,
            businessImpact: this.classification.businessImpact,
            technicalDetails: this.classification.technicalDetails,
            affectedResources: this.issue.affectedResources,
            estimatedSavings: this.issue.wastedAmount,
            confidence: this.issue.confidence,
            priority: this.classification.priority,
            detectedAt: this.issue.detectedAt
        };
    }

    private generateBusinessContext(template: ExplanationTemplate): BusinessContext {
        return {
            impactDescription: this.generateBusinessImpactExplanation(template),
            stakeholders: this.identifyStakeholders(),
            budgetImpact: this.issue.wastedAmount,
            urgency: this.mapBusinessUrgency(),
            businessRisk: this.classification.riskLevel
        };
    }

    private generateTechnicalAnalysis(
        template: ExplanationTemplate,
        context: Record<CloudProvider, Record<string, string>>
    ): TechnicalAnalysis {
        return {
            affectedSystems: this.classification.affectedSystems,
            performanceImpact: this.generateTechnicalDetails(template, context),
            scalabilityImpact: this.generateScalabilityImpact(),
            complexityLevel: this.mapComplexityLevel()
        };
    }

    private mapBusinessUrgency(): BusinessContext['urgency'] {
        switch (this.classification.urgency) {
            case 'critical':
                return 'immediate';
            case 'high':
                return 'high';
            case 'medium':
                return 'medium';
            default:
                return 'low';
        }
    }

    private mapComplexityLevel(): 'low' | 'medium' | 'high' {
        switch (this.classification.remediationComplexity) {
            case 'simple':
                return 'low';
            case 'complex':
                return 'high';
            default:
                return 'medium';
        }
    }

    private generateScalabilityImpact(): string {
        if (this.issue.type === WasteType.POOR_UNIT_ECONOMICS) {
            return 'Scaling efficiency is constrained by current cost structure.';
        }
        if (this.issue.type === WasteType.COST_REGRESSION) {
            return 'Unchecked growth may cause scaling inefficiencies and budget risk.';
        }
        return 'Optimization should improve scaling efficiency without reducing capacity.';
    }

    /**
     * Generate technical details explanation
     */
    private generateTechnicalDetails(template: any, context: any): string {
        let details = template.technical;
        
        // Replace template variables with actual values
        details = this.replaceTemplateVariables(details);
        
        // Add cloud-specific context
        details += ' ' + this.getCloudSpecificContext(context);
        
        // Add evidence summary
        details += ' Evidence includes: ' + this.issue.evidence.map(e => 
            `${e.description} (${e.value}${e.unit})`
        ).join(', ') + '.';
        
        return details;
    }

    /**
     * Generate business impact explanation
     */
    private generateBusinessImpactExplanation(template: any): string {
        let impact = template.business;
        
        const annualWaste = this.issue.wastedAmount * 12;
        
        impact += ` Monthly waste: $${this.issue.wastedAmount.toFixed(2)}, `;
        impact += `annual impact: $${annualWaste.toFixed(2)}. `;
        
        // Add classification-specific context
        if (this.classification.businessImpact === 'critical') {
            impact += 'This represents a critical cost optimization opportunity requiring immediate attention.';
        } else if (this.classification.businessImpact === 'high') {
            impact += 'Significant cost optimization opportunity that should be prioritized.';
        } else {
            impact += 'Moderate optimization opportunity that contributes to overall efficiency.';
        }
        
        return impact;
    }

    /**
     * Generate root cause analysis
     */
    private generateRootCauseAnalysis(): RootCauseAnalysis {
        const contributingFactors = [...this.classification.typicalCauses];

        if (this.issue.evidence.some(e => e.type === 'trend')) {
            contributingFactors.push('Trending data suggests a developing cost pattern');
        }

        if (this.issue.evidence.some(e => e.type === 'usage' && e.value < e.threshold)) {
            contributingFactors.push('Usage patterns indicate sustained underutilization');
        }

        const resourceTypes = [...new Set(this.issue.affectedResources.map(r => r.type))];
        if (resourceTypes.length === 1) {
            contributingFactors.push(`Affected resources are concentrated in ${resourceTypes[0]} workloads`);
        } else if (resourceTypes.length > 1) {
            contributingFactors.push(`Multiple resource types affected: ${resourceTypes.join(', ')}`);
        }

        return {
            primaryCause: this.issue.description,
            contributingFactors,
            evidence: this.issue.evidence,
            confidence: this.issue.confidence,
            timeline: [{
                timestamp: this.issue.detectedAt,
                event: 'Cost inefficiency detected',
                impact: this.issue.description
            }]
        };
    }

    /**
     * Generate remediation guidance
     */
    private generateRemediationGuidance(template: any): string {
        let guidance = template.remediation;
        
        guidance = this.replaceTemplateVariables(guidance);
        
        // Add classification-specific guidance
        if (this.classification.approvalRequired) {
            guidance += ' This change requires stakeholder approval due to potential business impact.';
        }
        
        if (this.classification.remediationComplexity === 'complex') {
            guidance += ' Complex remediation - recommend breaking into phases with careful testing.';
        } else if (this.classification.remediationComplexity === 'simple') {
            guidance += ' Low complexity remediation - can typically be implemented quickly with minimal risk.';
        }
        
        return guidance;
    }

    /**
     * Generate risk assessment
     */
    private generateRiskAssessment(template: any): {
        level: 'low' | 'medium' | 'high';
        factors: string[];
        mitigation: string[];
    } {
        const baseFactors = template.riskFactors;
        const additionalFactors: string[] = [];
        const mitigation: string[] = [];
        
        // Add risk factors based on classification
        if (this.classification.riskLevel === 'high') {
            additionalFactors.push('High business impact requires careful planning');
            mitigation.push('Implement in stages with rollback plan');
        }
        
        if (this.issue.confidence < 0.8) {
            additionalFactors.push('Lower confidence requires additional validation');
            mitigation.push('Gather more data before implementing changes');
        }
        
        if (this.issue.affectedResources.length > 3) {
            additionalFactors.push('Multiple resources increase coordination complexity');
            mitigation.push('Coordinate changes across teams and systems');
        }
        
        // Standard mitigations
        mitigation.push('Monitor key metrics during and after implementation');
        mitigation.push('Prepare rollback procedures');
        mitigation.push('Communicate changes to affected stakeholders');
        
        return {
            level: this.classification.riskLevel,
            factors: [...baseFactors, ...additionalFactors],
            mitigation
        };
    }

    /**
     * Generate cost breakdown
     */
    private generateCostBreakdown(): {
        currentMonthlyCost: number;
        wastedAmount: number;
        potentialSavings: number;
        breakdownByResource: Array<{ resource: string; currentCost: number; wastedCost: number; }>;
    } {
        // Estimate current cost based on waste amount and efficiency
        const wastedAmount = this.issue.wastedAmount;
        let currentMonthlyCost = wastedAmount;
        
        // Adjust based on waste type
        if (this.issue.type === WasteType.IDLE_RESOURCES) {
            currentMonthlyCost = wastedAmount; // 100% waste for idle resources
        } else if (this.issue.type === WasteType.OVERPROVISIONING) {
            currentMonthlyCost = wastedAmount * 2.5; // Assume 40% waste
        } else {
            currentMonthlyCost = wastedAmount * 1.5; // Conservative estimate
        }
        
        const potentialSavings = wastedAmount * 0.8; // 80% of waste is typically recoverable
        
        const breakdownByResource = this.issue.affectedResources.map(resource => {
            const resourceWaste = wastedAmount / this.issue.affectedResources.length;
            return {
                resource: resource.name,
                currentCost: resourceWaste * 1.5,
                wastedCost: resourceWaste
            };
        });
        
        return {
            currentMonthlyCost,
            wastedAmount,
            potentialSavings,
            breakdownByResource
        };
    }

    /**
     * Generate evidence summary
     */
    private generateEvidenceSummary(): string {
        if (this.issue.evidence.length === 0) {
            return 'No specific evidence metrics available.';
        }
        
        let summary = 'Evidence supporting this finding: ';
        
        const evidenceGroups = this.groupEvidenceByType();
        const groupSummaries: string[] = [];
        
        for (const [type, evidence] of Object.entries(evidenceGroups)) {
            const items = evidence.map(e => 
                `${e.description} (${e.value}${e.unit} vs threshold ${e.threshold}${e.unit})`
            ).join(', ');
            
            groupSummaries.push(`${type}: ${items}`);
        }
        
        summary += groupSummaries.join('; ');
        
        return summary;
    }

    /**
     * Generate specific recommendations
     */
    private generateRecommendations(): DetailedRecommendation[] {
        const recommendations: string[] = [...this.classification.recommendedActions];
        
        // Add evidence-based recommendations
        if (this.issue.evidence.some(e => e.type === 'usage' && e.value < e.threshold * 0.5)) {
            recommendations.unshift('Priority: Usage is significantly below threshold - safe for aggressive optimization');
        }
        
        if (this.issue.confidence > 0.9) {
            recommendations.unshift('High confidence - can proceed with implementation');
        }
        
        const effort = this.mapEffort();
        const timeline = this.mapTimeline();
        const prerequisites = [
            'Review affected resources and dependencies',
            'Validate baseline performance metrics'
        ];
        if (this.classification.approvalRequired) {
            prerequisites.push('Obtain required stakeholder approvals');
        }

        return recommendations.map((action): DetailedRecommendation => ({
            action,
            description: action,
            benefits: [
                'Reduce ongoing cloud spend',
                'Improve resource utilization efficiency'
            ],
            risks: [
                `${this.classification.riskLevel} risk of service impact`,
                this.classification.approvalRequired ? 'Requires stakeholder approval' : 'Low change management overhead'
            ],
            effort,
            timeline,
            prerequisites,
            successMetrics: [
                'Monthly cost reduction meets target',
                'Resource utilization within expected range',
                'No performance regressions detected'
            ]
        }));
    }

    /**
     * Generate remediation timeline
     */
    private generateRemediationTimeline(): Array<{
        phase: string;
        duration: string;
        activities: string[];
    }> {
        const timeline: Array<{ phase: string; duration: string; activities: string[]; }> = [];
        
        // Phase 1: Planning
        timeline.push({
            phase: 'Planning & Validation',
            duration: '1-3 days',
            activities: [
                'Review evidence and validate findings',
                'Identify stakeholders and dependencies',
                'Plan implementation approach'
            ]
        });
        
        // Phase 2: Approval (if required)
        if (this.classification.approvalRequired) {
            timeline.push({
                phase: 'Approval Process',
                duration: '3-7 days',
                activities: [
                    'Prepare business case and risk assessment',
                    'Present to stakeholders',
                    'Obtain necessary approvals'
                ]
            });
        }
        
        // Phase 3: Implementation
        const implDuration = this.classification.remediationComplexity === 'simple' ? '1-2 days' :
                            this.classification.remediationComplexity === 'medium' ? '3-5 days' : '1-2 weeks';
        
        timeline.push({
            phase: 'Implementation',
            duration: implDuration,
            activities: [
                'Execute optimization changes',
                'Monitor system performance',
                'Validate cost reductions'
            ]
        });
        
        // Phase 4: Monitoring
        timeline.push({
            phase: 'Monitoring & Validation',
            duration: '2-4 weeks',
            activities: [
                'Monitor system stability',
                'Validate cost savings',
                'Document lessons learned'
            ]
        });
        
        return timeline;
    }

    /**
     * Identify relevant stakeholders
     */
    private identifyStakeholders(): string[] {
        const stakeholders = new Set<string>();
        
        // Always include these
        stakeholders.add('DevOps/SRE Team');
        stakeholders.add('Finance Team');
        
        // Based on affected systems
        for (const system of this.classification.affectedSystems) {
            if (system.includes('database')) {
                stakeholders.add('Database Team');
            }
            if (system.includes('aws') || system.includes('gcp') || system.includes('azure')) {
                stakeholders.add('Cloud Operations Team');
            }
            if (system.includes('kubernetes')) {
                stakeholders.add('Platform Team');
            }
            if (system.includes('production')) {
                stakeholders.add('Application Teams');
            }
        }
        
        // Based on business impact
        if (this.classification.businessImpact === 'critical' || this.classification.businessImpact === 'high') {
            stakeholders.add('Engineering Management');
        }
        
        if (this.classification.approvalRequired) {
            stakeholders.add('Budget Owners');
        }
        
        return Array.from(stakeholders);
    }

    /**
     * Generate monitoring guidance
     */
    private generateMonitoringGuidance(): {
        preImplementation: string[];
        postImplementation: string[];
        alerting: string[];
    } {
        return {
            preImplementation: [
                'Establish baseline metrics for affected resources',
                'Document current performance characteristics',
                'Set up monitoring for key business metrics'
            ],
            postImplementation: [
                'Monitor resource utilization for 2-4 weeks',
                'Track cost reduction realization',
                'Validate performance remains acceptable'
            ],
            alerting: [
                'Set alerts for resource utilization thresholds',
                'Monitor for cost regression',
                'Alert on performance degradation'
            ]
        };
    }

    /**
     * Helper methods
     */
    
    private extractTechnicalContext(): Record<CloudProvider, Record<string, string>> {
        const clouds = [...new Set(this.issue.affectedResources.map(r => r.cloud))] as CloudProvider[];
        return clouds.reduce((context, cloud) => {
            context[cloud] = TECHNICAL_CONTEXT[cloud] || {};
            return context;
        }, {} as Record<CloudProvider, Record<string, string>>);
    }
    
    private replaceTemplateVariables(template: string): string {
        // Mock template variable replacement - would use actual data
        return template
            .replace('{utilizationPct}', '15')
            .replace('{observationPeriod}', '7')
            .replace('{avgCpu}', '8')
            .replace('{avgMemory}', '12')
            .replace('{currentSize}', 't3.large')
            .replace('{recommendedSize}', 't3.medium')
            .replace('{savingsPct}', '35')
            .replace('{peakUsage}', '25');
    }
    
    private getCloudSpecificContext(context: Record<CloudProvider, Record<string, string>>): string {
        const clouds = Object.keys(context);
        if (clouds.length === 0) return '';
        
        const cloud = clouds[0] as CloudProvider;
        const resourceTypes = [...new Set(this.issue.affectedResources.map(r => r.type.toLowerCase()))];
        
        if (resourceTypes.some(t => t.includes('instance') || t.includes('vm'))) {
            return context[cloud]?.instances || '';
        }
        if (resourceTypes.some(t => t.includes('volume') || t.includes('disk'))) {
            return context[cloud]?.volumes || '';
        }
        if (resourceTypes.some(t => t.includes('database'))) {
            return context[cloud]?.database || '';
        }
        if (resourceTypes.some(t => t.includes('pod') || t.includes('namespace'))) {
            return context['kubernetes']?.pods || '';
        }
        
        return '';
    }

    private mapEffort(): ImplementationEffort {
        switch (this.classification.remediationComplexity) {
            case 'simple':
                return ImplementationEffort.LOW;
            case 'complex':
                return ImplementationEffort.HIGH;
            default:
                return ImplementationEffort.MEDIUM;
        }
    }

    private mapTimeline(): string {
        switch (this.classification.remediationComplexity) {
            case 'simple':
                return '1-3 days';
            case 'complex':
                return '2-6 weeks';
            default:
                return '1-2 weeks';
        }
    }
    
    private groupEvidenceByType(): Record<string, Evidence[]> {
        return this.issue.evidence.reduce((groups, evidence) => {
            const type = evidence.type;
            if (!groups[type]) groups[type] = [];
            groups[type].push(evidence);
            return groups;
        }, {} as Record<string, Evidence[]>);
    }
}
