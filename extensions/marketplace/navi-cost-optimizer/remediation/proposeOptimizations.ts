/**
 * NAVI Cost Optimizer - Optimization Proposal Engine
 * 
 * Generates approval-gated optimization proposals following enterprise security patterns.
 * Creates comprehensive remediation proposals with safety checks, rollback plans,
 * and approval workflows for cost optimization actions.
 * 
 * @module proposeOptimizations
 */

import * as vscode from 'vscode';
import {
    CostIssue,
    RemediationProposal,
    RemediationAction,
    RemediationActionType,
    OptimizationType,
    RiskLevel,
    ImplementationEffort,
    IssuePriority,
    ApprovalWorkflow,
    SafetyCheck,
    RollbackPlan,
    RollbackStep,
    ValidationStep,
    Timeline,
    TimelinePhase,
    Approver,
    AutoApprovalCondition
} from '../types';

/**
 * Core optimization proposal engine
 */
export class OptimizationProposalEngine {
    private context: vscode.ExtensionContext;
    private outputChannel: vscode.OutputChannel;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.outputChannel = vscode.window.createOutputChannel('NAVI Cost Optimizer - Remediation');
    }

    /**
     * Generate comprehensive remediation proposal for a cost issue
     */
    public async proposeRemediation(issue: CostIssue): Promise<RemediationProposal> {
        this.outputChannel.appendLine(`🎯 Generating remediation proposal for issue: ${issue.id}`);
        
        try {
            // Generate core proposal structure
            const proposal: RemediationProposal = {
                id: this.generateProposalId(issue.id),
                issueId: issue.id,
                title: this.generateProposalTitle(issue),
                description: this.generateProposalDescription(issue),
                type: this.mapIssueToOptimizationType(issue),
                priority: issue.priority,
                actions: await this.generateRemediationActions(issue),
                estimatedSavings: issue.estimatedSavings,
                riskLevel: this.assessRiskLevel(issue),
                requiresApproval: this.requiresApproval(issue),
                safetyChecks: this.generateSafetyChecks(issue),
                rollbackPlan: this.generateRollbackPlan(issue),
                timeline: this.generateTimeline(issue)
            };

            // Add approval workflow if required
            if (proposal.requiresApproval) {
                proposal.approvalWorkflow = this.generateApprovalWorkflow(issue, proposal.riskLevel);
            }

            this.outputChannel.appendLine(`✅ Generated proposal with ${proposal.actions.length} actions`);
            return proposal;

        } catch (error) {
            const errorMsg = `Failed to generate remediation proposal: ${error}`;
            this.outputChannel.appendLine(`❌ ${errorMsg}`);
            throw new Error(errorMsg);
        }
    }

    /**
     * Generate multiple optimization proposals for a batch of issues
     */
    public async proposeOptimizations(issues: CostIssue[]): Promise<RemediationProposal[]> {
        this.outputChannel.appendLine(`🚀 Generating optimization proposals for ${issues.length} issues`);
        
        const proposals: RemediationProposal[] = [];
        const errors: string[] = [];

        for (const issue of issues) {
            try {
                const proposal = await this.proposeRemediation(issue);
                proposals.push(proposal);
            } catch (error) {
                errors.push(`Issue ${issue.id}: ${error}`);
                this.outputChannel.appendLine(`⚠️ Failed to generate proposal for ${issue.id}: ${error}`);
            }
        }

        if (errors.length > 0) {
            this.outputChannel.appendLine(`⚠️ Generated ${proposals.length} proposals with ${errors.length} errors`);
        } else {
            this.outputChannel.appendLine(`✅ Successfully generated ${proposals.length} optimization proposals`);
        }

        return proposals;
    }

    /**
     * Generate specific remediation actions based on issue type
     */
    private async generateRemediationActions(issue: CostIssue): Promise<RemediationAction[]> {
        const actions: RemediationAction[] = [];
        
        switch (issue.type) {
            case 'IDLE_RESOURCES':
                actions.push(...this.generateIdleResourceActions(issue));
                break;
            case 'OVERPROVISIONING':
                actions.push(...this.generateOverprovisioningActions(issue));
                break;
            case 'COST_REGRESSION':
                actions.push(...this.generateCostRegressionActions(issue));
                break;
            case 'INEFFICIENT_SCALING':
                actions.push(...this.generateScalingActions(issue));
                break;
            case 'UNUSED_SERVICES':
                actions.push(...this.generateUnusedServiceActions(issue));
                break;
            case 'POOR_RESOURCE_ALLOCATION':
                actions.push(...this.generateResourceAllocationActions(issue));
                break;
            default:
                actions.push(this.generateInvestigationAction(issue));
        }

        return actions;
    }

    /**
     * Generate actions for idle resource issues
     */
    private generateIdleResourceActions(issue: CostIssue): RemediationAction[] {
        const actions: RemediationAction[] = [];

        // Investigation action first
        actions.push({
            id: `${issue.id}-investigate`,
            type: RemediationActionType.INVESTIGATE,
            description: 'Investigate current resource utilization and dependencies',
            validation: this.generateValidationSteps([
                'Confirm resource utilization is below threshold',
                'Verify no active connections or dependencies',
                'Check for scheduled jobs or automation'
            ]),
            rollbackCommand: 'echo "Investigation action - no rollback needed"',
            automatable: true,
            requiresApproval: false,
            estimatedDuration: '15 minutes',
            successCriteria: [
                'Resource utilization confirmed below 5%',
                'No active dependencies found',
                'Safe to proceed with termination'
            ]
        });

        // Termination action for confirmed idle resources
        if (issue.severity === 'HIGH' || issue.severity === 'CRITICAL') {
            actions.push({
                id: `${issue.id}-terminate`,
                type: RemediationActionType.TERMINATE,
                description: 'Safely terminate idle resources after confirmation',
                command: this.generateTerminationCommand(issue),
                validation: this.generateValidationSteps([
                    'Resource successfully terminated',
                    'No service disruption detected',
                    'Cost savings reflected in billing'
                ]),
                rollbackCommand: this.generateRollbackCommand(issue, 'terminate'),
                automatable: false,
                requiresApproval: true,
                estimatedDuration: '30 minutes',
                successCriteria: [
                    'Resource successfully terminated',
                    'Monthly cost reduced by estimated amount',
                    'No alerts or service issues reported'
                ]
            });
        }

        return actions;
    }

    /**
     * Generate actions for overprovisioning issues
     */
    private generateOverprovisioningActions(issue: CostIssue): RemediationAction[] {
        return [
            {
                id: `${issue.id}-analyze`,
                type: RemediationActionType.INVESTIGATE,
                description: 'Analyze current resource requirements vs provisioned capacity',
                validation: this.generateValidationSteps([
                    'Current utilization patterns documented',
                    'Peak usage requirements identified',
                    'Right-sizing recommendations calculated'
                ]),
                automatable: true,
                requiresApproval: false,
                estimatedDuration: '20 minutes',
                successCriteria: ['Utilization analysis complete', 'Right-sizing plan generated']
            },
            {
                id: `${issue.id}-rightsize`,
                type: RemediationActionType.RIGHTSIZE,
                description: 'Resize resources to match actual usage requirements',
                command: this.generateRightsizingCommand(issue),
                validation: this.generateValidationSteps([
                    'Resources resized successfully',
                    'Performance metrics within acceptable range',
                    'Cost reduction achieved'
                ]),
                rollbackCommand: this.generateRollbackCommand(issue, 'rightsize'),
                automatable: false,
                requiresApproval: true,
                estimatedDuration: '45 minutes',
                successCriteria: [
                    'Resources right-sized successfully',
                    'Performance impact < 5%',
                    'Cost reduced by targeted amount'
                ]
            }
        ];
    }

    /**
     * Generate actions for cost regression issues
     */
    private generateCostRegressionActions(issue: CostIssue): RemediationAction[] {
        return [
            {
                id: `${issue.id}-investigate`,
                type: RemediationActionType.INVESTIGATE,
                description: 'Investigate root cause of cost regression',
                validation: this.generateValidationSteps([
                    'Timeline of cost changes documented',
                    'Root cause identified',
                    'Impact scope assessed'
                ]),
                automatable: true,
                requiresApproval: false,
                estimatedDuration: '30 minutes',
                successCriteria: [
                    'Cost regression timeline established',
                    'Root cause identified with high confidence'
                ]
            },
            {
                id: `${issue.id}-optimize`,
                type: RemediationActionType.OPTIMIZE,
                description: 'Apply targeted optimizations to address regression',
                command: this.generateOptimizationCommand(issue),
                validation: this.generateValidationSteps([
                    'Optimization applied successfully',
                    'Cost trend reversed',
                    'Performance maintained'
                ]),
                rollbackCommand: this.generateRollbackCommand(issue, 'optimize'),
                automatable: false,
                requiresApproval: true,
                estimatedDuration: '60 minutes',
                successCriteria: [
                    'Cost regression addressed',
                    'Spending returned to baseline',
                    'Root cause mitigated'
                ]
            }
        ];
    }

    /**
     * Generate actions for scaling inefficiency issues
     */
    private generateScalingActions(issue: CostIssue): RemediationAction[] {
        return [
            {
                id: `${issue.id}-configure`,
                type: RemediationActionType.CONFIGURE,
                description: 'Configure auto-scaling policies for optimal cost efficiency',
                command: this.generateScalingConfigCommand(issue),
                validation: this.generateValidationSteps([
                    'Auto-scaling policies updated',
                    'Scaling metrics configured',
                    'Cost efficiency improved'
                ]),
                rollbackCommand: this.generateRollbackCommand(issue, 'configure'),
                automatable: false,
                requiresApproval: true,
                estimatedDuration: '45 minutes',
                successCriteria: [
                    'Scaling policies optimized',
                    'Response time maintained',
                    'Cost variability reduced'
                ]
            }
        ];
    }

    /**
     * Generate actions for unused service issues
     */
    private generateUnusedServiceActions(issue: CostIssue): RemediationAction[] {
        return [
            {
                id: `${issue.id}-investigate`,
                type: RemediationActionType.INVESTIGATE,
                description: 'Verify service is truly unused and safe to remove',
                validation: this.generateValidationSteps([
                    'Service usage confirmed as zero',
                    'Dependencies checked and cleared',
                    'Stakeholder confirmation received'
                ]),
                automatable: true,
                requiresApproval: false,
                estimatedDuration: '25 minutes',
                successCriteria: ['Usage confirmed as zero', 'Safe for removal']
            },
            {
                id: `${issue.id}-terminate`,
                type: RemediationActionType.TERMINATE,
                description: 'Remove unused service and associated resources',
                command: this.generateServiceRemovalCommand(issue),
                validation: this.generateValidationSteps([
                    'Service successfully removed',
                    'No dependent services affected',
                    'Cost reduction achieved'
                ]),
                rollbackCommand: this.generateRollbackCommand(issue, 'service-removal'),
                automatable: false,
                requiresApproval: true,
                estimatedDuration: '40 minutes',
                successCriteria: [
                    'Service cleanly removed',
                    'No service disruptions',
                    'Expected cost savings realized'
                ]
            }
        ];
    }

    /**
     * Generate actions for resource allocation issues
     */
    private generateResourceAllocationActions(issue: CostIssue): RemediationAction[] {
        return [
            {
                id: `${issue.id}-migrate`,
                type: RemediationActionType.MIGRATE,
                description: 'Migrate workloads to more cost-effective resource allocation',
                command: this.generateMigrationCommand(issue),
                validation: this.generateValidationSteps([
                    'Workload migration completed',
                    'Performance benchmarks met',
                    'Cost reduction achieved'
                ]),
                rollbackCommand: this.generateRollbackCommand(issue, 'migrate'),
                automatable: false,
                requiresApproval: true,
                estimatedDuration: '90 minutes',
                successCriteria: [
                    'Migration completed successfully',
                    'Performance maintained or improved',
                    'Cost efficiency increased'
                ]
            }
        ];
    }

    /**
     * Generate default investigation action
     */
    private generateInvestigationAction(issue: CostIssue): RemediationAction {
        return {
            id: `${issue.id}-investigate`,
            type: RemediationActionType.INVESTIGATE,
            description: `Investigate cost issue: ${issue.title}`,
            validation: this.generateValidationSteps([
                'Issue thoroughly analyzed',
                'Root cause identified',
                'Optimization opportunities documented'
            ]),
            automatable: true,
            requiresApproval: false,
            estimatedDuration: '30 minutes',
            successCriteria: [
                'Investigation completed',
                'Next steps identified'
            ]
        };
    }

    /**
     * Generate command strings for different action types
     */
    private generateTerminationCommand(issue: CostIssue): string {
        const resources = issue.affectedResources.map(r => r.id).join(' ');
        return `echo "Terminate resources: ${resources}" && # Add actual termination logic`;
    }

    private generateRightsizingCommand(issue: CostIssue): string {
        const resources = issue.affectedResources.map(r => r.id).join(' ');
        return `echo "Rightsize resources: ${resources}" && # Add actual rightsizing logic`;
    }

    private generateOptimizationCommand(issue: CostIssue): string {
        return `echo "Apply optimization for issue: ${issue.id}" && # Add actual optimization logic`;
    }

    private generateScalingConfigCommand(issue: CostIssue): string {
        return `echo "Configure scaling for: ${issue.affectedResources.map(r => r.id).join(' ')}" && # Add scaling config logic`;
    }

    private generateServiceRemovalCommand(issue: CostIssue): string {
        const services = issue.affectedResources.map(r => r.name).join(', ');
        return `echo "Remove unused services: ${services}" && # Add service removal logic`;
    }

    private generateMigrationCommand(issue: CostIssue): string {
        return `echo "Migrate workloads for issue: ${issue.id}" && # Add migration logic`;
    }

    private generateRollbackCommand(issue: CostIssue, actionType: string): string {
        return `echo "Rollback ${actionType} for issue: ${issue.id}" && # Add rollback logic`;
    }

    /**
     * Helper methods for proposal generation
     */
    private generateProposalId(issueId: string): string {
        return `proposal-${issueId}-${Date.now()}`;
    }

    private generateProposalTitle(issue: CostIssue): string {
        return `Optimization Proposal: ${issue.title}`;
    }

    private generateProposalDescription(issue: CostIssue): string {
        return `Automated remediation proposal to address ${issue.type.toLowerCase()} issue. ` +
               `Estimated monthly savings: $${issue.estimatedSavings.toFixed(2)}. ` +
               `Confidence: ${Math.round(issue.confidence * 100)}%.`;
    }

    private mapIssueToOptimizationType(issue: CostIssue): OptimizationType {
        const mapping: Record<string, OptimizationType> = {
            'IDLE_RESOURCES': OptimizationType.RIGHTSIZING,
            'OVERPROVISIONING': OptimizationType.RIGHTSIZING,
            'COST_REGRESSION': OptimizationType.INVESTIGATION,
            'INEFFICIENT_SCALING': OptimizationType.AUTOSCALING,
            'UNUSED_SERVICES': OptimizationType.SERVICE_CONSOLIDATION,
            'POOR_RESOURCE_ALLOCATION': OptimizationType.RIGHTSIZING
        };

        return mapping[issue.type] || OptimizationType.INVESTIGATION;
    }

    private assessRiskLevel(issue: CostIssue): RiskLevel {
        if (issue.severity === 'CRITICAL') return RiskLevel.HIGH;
        if (issue.severity === 'HIGH') return RiskLevel.MEDIUM;
        return RiskLevel.LOW;
    }

    private requiresApproval(issue: CostIssue): boolean {
        return issue.estimatedSavings > 100 || 
               issue.severity === 'HIGH' || 
               issue.severity === 'CRITICAL';
    }

    private generateSafetyChecks(issue: CostIssue): SafetyCheck[] {
        return [
            {
                name: 'Resource Health Check',
                description: 'Verify all affected resources are healthy before optimization',
                check: 'resource-health-check',
                expectedResult: { healthy: true, errors: 0 },
                mandatory: true,
                rollbackTrigger: false
            },
            {
                name: 'Dependency Verification',
                description: 'Ensure no critical dependencies will be affected',
                check: 'dependency-verification',
                expectedResult: { criticalDependencies: 0 },
                mandatory: true,
                rollbackTrigger: true
            },
            {
                name: 'Performance Baseline',
                description: 'Establish performance baseline for rollback criteria',
                check: 'performance-baseline',
                expectedResult: { baselineEstablished: true },
                mandatory: false,
                rollbackTrigger: false
            }
        ];
    }

    private generateRollbackPlan(issue: CostIssue): RollbackPlan {
        return {
            description: `Comprehensive rollback plan for ${issue.title} optimization`,
            steps: [
                {
                    order: 1,
                    description: 'Stop optimization process',
                    command: 'echo "Stopping optimization process"',
                    validation: 'process-stopped',
                    timeoutMinutes: 5
                },
                {
                    order: 2,
                    description: 'Restore original resource configuration',
                    command: 'echo "Restoring original configuration"',
                    validation: 'configuration-restored',
                    timeoutMinutes: 15
                },
                {
                    order: 3,
                    description: 'Verify service restoration',
                    command: 'echo "Verifying service health"',
                    validation: 'service-healthy',
                    timeoutMinutes: 10
                }
            ],
            timeLimit: '30 minutes',
            triggerConditions: [
                'Performance degradation > 10%',
                'Error rate increase > 5%',
                'Critical dependency failure'
            ],
            emergencyContacts: ['devops-team@company.com', 'on-call-engineer@company.com']
        };
    }

    private generateTimeline(issue: CostIssue): Timeline {
        const phases: TimelinePhase[] = [
            {
                phase: 'Investigation',
                duration: '15-30 minutes',
                description: 'Analyze issue and verify optimization safety',
                dependencies: []
            },
            {
                phase: 'Approval',
                duration: '1-24 hours',
                description: 'Obtain necessary approvals for optimization',
                dependencies: ['Investigation']
            },
            {
                phase: 'Implementation',
                duration: '30-90 minutes',
                description: 'Execute optimization actions with monitoring',
                dependencies: ['Approval']
            },
            {
                phase: 'Validation',
                duration: '15-30 minutes',
                description: 'Verify optimization success and monitor metrics',
                dependencies: ['Implementation']
            }
        ];

        return {
            estimatedDuration: '2-26 hours',
            phases,
            milestones: [
                'Investigation complete',
                'Approvals obtained',
                'Optimization implemented',
                'Results validated'
            ]
        };
    }

    private generateApprovalWorkflow(issue: CostIssue, riskLevel: RiskLevel): ApprovalWorkflow {
        const approvers: Approver[] = [];
        const autoApproveConditions: AutoApprovalCondition[] = [];

        // Define approvers based on risk level and savings amount
        if (riskLevel === RiskLevel.LOW && issue.estimatedSavings < 500) {
            approvers.push({
                role: 'Team Lead',
                email: 'team-lead@company.com',
                level: 'primary'
            });
            
            autoApproveConditions.push({
                condition: 'savings < 200 AND risk = LOW',
                threshold: 200,
                description: 'Auto-approve low-risk optimizations under $200/month'
            });
        } else if (riskLevel === RiskLevel.MEDIUM || issue.estimatedSavings >= 500) {
            approvers.push(
                {
                    role: 'Team Lead',
                    email: 'team-lead@company.com',
                    level: 'primary'
                },
                {
                    role: 'Engineering Manager',
                    email: 'eng-manager@company.com',
                    level: 'secondary'
                }
            );
        } else {
            approvers.push(
                {
                    role: 'Team Lead',
                    email: 'team-lead@company.com',
                    level: 'primary'
                },
                {
                    role: 'Engineering Manager',
                    email: 'eng-manager@company.com',
                    level: 'secondary'
                },
                {
                    role: 'VP Engineering',
                    email: 'vp-eng@company.com',
                    level: 'escalation'
                }
            );
        }

        const workflow: ApprovalWorkflow = {
            required: true,
            approvers,
            escalationPath: approvers.map(a => a.role),
            timeoutHours: riskLevel === RiskLevel.HIGH ? 2 : 24
        };

        if (autoApproveConditions.length > 0) {
            workflow.autoApproveConditions = autoApproveConditions;
        }

        return workflow;
    }

    private generateValidationSteps(criteria: string[]): ValidationStep[] {
        return criteria.map((criterion, index) => ({
            name: `Validation Step ${index + 1}`,
            description: criterion,
            expectedResult: { success: true },
            timeoutMinutes: 5,
            mandatory: true
        }));
    }

    /**
     * Public API method for VS Code integration
     */
    public async generateOptimizationProposals(context: vscode.ExtensionContext, issues: CostIssue[]): Promise<RemediationProposal[]> {
        return this.proposeOptimizations(issues);
    }
}

/**
 * Factory function for creating the proposal engine
 */
export function createOptimizationProposalEngine(context: vscode.ExtensionContext): OptimizationProposalEngine {
    return new OptimizationProposalEngine(context);
}

/**
 * Main entry point for generating optimization proposals
 */
export async function proposeOptimizations(context: vscode.ExtensionContext, issues: CostIssue[]): Promise<RemediationProposal[]> {
    const engine = createOptimizationProposalEngine(context);
    return engine.proposeOptimizations(issues);
}
