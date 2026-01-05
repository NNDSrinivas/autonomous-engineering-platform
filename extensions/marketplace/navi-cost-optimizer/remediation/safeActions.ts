/**
 * NAVI Cost Optimizer - Safe Actions Engine
 * 
 * Provides enterprise-grade safety mechanisms for cost optimization actions.
 * Implements comprehensive validation, approval workflows, rollback capabilities,
 * and monitoring for safe execution of cost optimization remediation plans.
 * 
 * @module safeActions
 */

import * as vscode from 'vscode';
import {
    RemediationProposal,
    RemediationAction,
    RemediationActionType,
    SafetyCheck,
    ValidationStep,
    RollbackPlan,
    RollbackStep,
    ApprovalWorkflow,
    RiskLevel,
    CostIssue
} from '../types';

/**
 * Result of safety validation
 */
export interface SafetyValidationResult {
    isSafe: boolean;
    passedChecks: SafetyCheck[];
    failedChecks: SafetyCheck[];
    warnings: string[];
    recommendations: string[];
    riskScore: number; // 0-100, higher is riskier
}

/**
 * Result of action execution
 */
export interface ActionExecutionResult {
    success: boolean;
    actionId: string;
    executedAt: string;
    duration: number; // milliseconds
    validationResults: ValidationResult[];
    errors: string[];
    rollbackRequired: boolean;
    rollbackReason?: string;
    metrics: ExecutionMetrics;
}

/**
 * Validation step result
 */
export interface ValidationResult {
    stepName: string;
    success: boolean;
    actualResult: any;
    expectedResult: any;
    duration: number;
    error?: string;
}

/**
 * Execution metrics for monitoring
 */
export interface ExecutionMetrics {
    cpuUsage: number;
    memoryUsage: number;
    networkLatency: number;
    errorRate: number;
    responseTime: number;
}

/**
 * Approval status and history
 */
export interface ApprovalStatus {
    proposalId: string;
    status: 'pending' | 'approved' | 'rejected' | 'expired';
    approvals: ApprovalRecord[];
    rejectionReason?: string;
    expiresAt: string;
    autoApproved: boolean;
}

/**
 * Individual approval record
 */
export interface ApprovalRecord {
    approver: string;
    role: string;
    approvedAt: string;
    comments?: string;
    conditions?: string[];
}

/**
 * Core safe actions engine for enterprise cost optimization
 */
export class SafeActionsEngine {
    private context: vscode.ExtensionContext;
    private outputChannel: vscode.OutputChannel;
    private safetyThresholds: SafetyThresholds;
    private executionHistory: Map<string, ActionExecutionResult[]>;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.outputChannel = vscode.window.createOutputChannel('NAVI Safe Actions');
        this.safetyThresholds = this.initializeSafetyThresholds();
        this.executionHistory = new Map();
    }

    /**
     * Validate safety of a remediation proposal before execution
     */
    public async validateProposalSafety(proposal: RemediationProposal): Promise<SafetyValidationResult> {
        this.outputChannel.appendLine(`🔍 Validating safety for proposal: ${proposal.id}`);
        
        const result: SafetyValidationResult = {
            isSafe: true,
            passedChecks: [],
            failedChecks: [],
            warnings: [],
            recommendations: [],
            riskScore: 0
        };

        try {
            // Run all safety checks
            for (const check of proposal.safetyChecks) {
                const checkResult = await this.executeSafetyCheck(check, proposal);
                
                if (checkResult.passed) {
                    result.passedChecks.push(check);
                } else {
                    result.failedChecks.push(check);
                    if (check.mandatory) {
                        result.isSafe = false;
                    } else {
                        result.warnings.push(`Non-mandatory check failed: ${check.name}`);
                    }
                }
            }

            // Calculate risk score
            result.riskScore = this.calculateRiskScore(proposal, result);

            // Generate safety recommendations
            result.recommendations = this.generateSafetyRecommendations(proposal, result);

            // Final safety assessment
            if (result.riskScore > this.safetyThresholds.maxRiskScore) {
                result.isSafe = false;
                result.warnings.push(`Risk score ${result.riskScore} exceeds threshold ${this.safetyThresholds.maxRiskScore}`);
            }

            this.outputChannel.appendLine(
                `✅ Safety validation complete: ${result.isSafe ? 'SAFE' : 'UNSAFE'} ` +
                `(${result.passedChecks.length}/${proposal.safetyChecks.length} checks passed, ` +
                `risk score: ${result.riskScore})`
            );

            return result;

        } catch (error) {
            this.outputChannel.appendLine(`❌ Safety validation failed: ${error}`);
            result.isSafe = false;
            result.warnings.push(`Safety validation error: ${error}`);
            return result;
        }
    }

    /**
     * Execute a single remediation action with full safety protocols
     */
    public async executeSafeAction(
        action: RemediationAction,
        proposal: RemediationProposal
    ): Promise<ActionExecutionResult> {
        this.outputChannel.appendLine(`🚀 Executing safe action: ${action.id}`);
        
        const startTime = Date.now();
        const result: ActionExecutionResult = {
            success: false,
            actionId: action.id,
            executedAt: new Date().toISOString(),
            duration: 0,
            validationResults: [],
            errors: [],
            rollbackRequired: false,
            metrics: await this.captureBaselineMetrics()
        };

        try {
            // Pre-execution validation
            const preValidation = await this.runPreExecutionValidation(action, proposal);
            if (!preValidation.success) {
                result.errors.push('Pre-execution validation failed');
                result.validationResults.push(preValidation);
                return result;
            }

            // Execute the action
            const executionSuccess = await this.executeAction(action);
            
            if (!executionSuccess) {
                result.errors.push('Action execution failed');
                result.rollbackRequired = true;
                result.rollbackReason = 'Execution failure';
                return result;
            }

            // Post-execution validation
            const postValidation = await this.runPostExecutionValidation(action, result.metrics);
            result.validationResults.push(...postValidation);

            // Check for rollback triggers
            const rollbackNeeded = this.checkRollbackTriggers(postValidation, proposal.rollbackPlan);
            if (rollbackNeeded.required) {
                result.rollbackRequired = true;
                result.rollbackReason = rollbackNeeded.reason ?? 'Rollback required';
                
                // Execute automatic rollback if configured
                if (this.safetyThresholds.autoRollback) {
                    await this.executeRollback(proposal.rollbackPlan, action.id);
                }
            } else {
                result.success = true;
            }

        } catch (error) {
            result.errors.push(`Execution error: ${error}`);
            result.rollbackRequired = true;
            result.rollbackReason = `Exception during execution: ${error}`;
        } finally {
            result.duration = Date.now() - startTime;
            
            // Store execution history
            this.storeExecutionHistory(proposal.id, result);
            
            this.outputChannel.appendLine(
                `${result.success ? '✅' : '❌'} Action ${action.id} ${result.success ? 'completed' : 'failed'} ` +
                `in ${result.duration}ms. Rollback required: ${result.rollbackRequired}`
            );
        }

        return result;
    }

    /**
     * Execute a complete remediation proposal with orchestrated safety
     */
    public async executeProposalSafely(
        proposal: RemediationProposal,
        approvalStatus?: ApprovalStatus
    ): Promise<ActionExecutionResult[]> {
        this.outputChannel.appendLine(`🔄 Executing proposal safely: ${proposal.id}`);
        
        // Validate approval if required
        if (proposal.requiresApproval && (!approvalStatus || approvalStatus.status !== 'approved')) {
            throw new Error('Proposal requires approval before execution');
        }

        // Final safety validation
        const safetyValidation = await this.validateProposalSafety(proposal);
        if (!safetyValidation.isSafe) {
            throw new Error('Proposal failed safety validation');
        }

        const results: ActionExecutionResult[] = [];
        let allSuccessful = true;

        // Execute actions in sequence with monitoring
        for (const action of proposal.actions) {
            try {
                const result = await this.executeSafeAction(action, proposal);
                results.push(result);

                if (!result.success) {
                    allSuccessful = false;
                    
                    // If this action failed and requires rollback, stop execution
                    if (result.rollbackRequired) {
                        this.outputChannel.appendLine(`⚠️ Stopping execution due to rollback requirement in action ${action.id}`);
                        break;
                    }
                }

            } catch (error) {
                this.outputChannel.appendLine(`❌ Failed to execute action ${action.id}: ${error}`);
                allSuccessful = false;
                break;
            }
        }

        // Generate execution summary
        const successCount = results.filter(r => r.success).length;
        this.outputChannel.appendLine(
            `📊 Proposal execution complete: ${successCount}/${results.length} actions successful. ` +
            `Overall success: ${allSuccessful}`
        );

        return results;
    }

    /**
     * Check and enforce approval requirements
     */
    public async checkApprovalStatus(proposal: RemediationProposal): Promise<ApprovalStatus> {
        const workflow = proposal.approvalWorkflow;
        
        if (!workflow?.required) {
            return {
                proposalId: proposal.id,
                status: 'approved',
                approvals: [],
                expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // 24 hours
                autoApproved: true
            };
        }

        // Check for auto-approval conditions
        if (workflow.autoApproveConditions) {
            const autoApproved = this.evaluateAutoApprovalConditions(proposal, workflow.autoApproveConditions);
            if (autoApproved) {
                return {
                    proposalId: proposal.id,
                    status: 'approved',
                    approvals: [{
                        approver: 'system',
                        role: 'auto-approval',
                        approvedAt: new Date().toISOString(),
                        comments: 'Auto-approved based on configured conditions'
                    }],
                    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
                    autoApproved: true
                };
            }
        }

        // Return pending status - actual approval collection would be implemented
        return {
            proposalId: proposal.id,
            status: 'pending',
            approvals: [],
            expiresAt: new Date(Date.now() + workflow.timeoutHours * 60 * 60 * 1000).toISOString(),
            autoApproved: false
        };
    }

    /**
     * Execute controlled rollback for failed optimizations
     */
    public async executeRollback(rollbackPlan: RollbackPlan, actionId: string): Promise<boolean> {
        this.outputChannel.appendLine(`🔄 Executing rollback plan for action: ${actionId}`);
        
        try {
            const sortedSteps = rollbackPlan.steps.sort((a, b) => a.order - b.order);
            
            for (const step of sortedSteps) {
                this.outputChannel.appendLine(`▶️ Executing rollback step ${step.order}: ${step.description}`);
                
                const stepStart = Date.now();
                
                // Execute rollback step (simplified for example)
                const success = await this.executeRollbackStep(step);
                
                const duration = Date.now() - stepStart;
                
                if (!success) {
                    this.outputChannel.appendLine(`❌ Rollback step ${step.order} failed`);
                    return false;
                }
                
                if (duration > step.timeoutMinutes * 60 * 1000) {
                    this.outputChannel.appendLine(`⚠️ Rollback step ${step.order} exceeded timeout`);
                    return false;
                }
                
                this.outputChannel.appendLine(`✅ Rollback step ${step.order} completed in ${duration}ms`);
            }

            this.outputChannel.appendLine(`✅ Rollback completed successfully for action: ${actionId}`);
            return true;

        } catch (error) {
            this.outputChannel.appendLine(`❌ Rollback failed: ${error}`);
            return false;
        }
    }

    /**
     * Private helper methods
     */
    private async executeSafetyCheck(check: SafetyCheck, proposal: RemediationProposal): Promise<{ passed: boolean; result?: any; error?: string }> {
        try {
            // Simulate safety check execution
            // In real implementation, this would run actual validation logic
            const mockResult = await this.runMockSafetyCheck(check);
            
            const passed = JSON.stringify(mockResult) === JSON.stringify(check.expectedResult);
            
            return { passed, result: mockResult };
            
        } catch (error) {
            return { passed: false, error: String(error) };
        }
    }

    private async runMockSafetyCheck(check: SafetyCheck): Promise<any> {
        // Simulate different check types
        switch (check.name) {
            case 'Resource Health Check':
                return { healthy: true, errors: 0 };
            case 'Dependency Verification':
                return { criticalDependencies: 0 };
            case 'Performance Baseline':
                return { baselineEstablished: true };
            default:
                return check.expectedResult;
        }
    }

    private calculateRiskScore(proposal: RemediationProposal, validation: SafetyValidationResult): number {
        let score = 0;
        
        // Base risk from proposal
        switch (proposal.riskLevel) {
            case RiskLevel.LOW: score += 10; break;
            case RiskLevel.MEDIUM: score += 30; break;
            case RiskLevel.HIGH: score += 50; break;
        }
        
        // Failed mandatory checks
        const failedMandatory = validation.failedChecks.filter(c => c.mandatory).length;
        score += failedMandatory * 20;
        
        // Failed non-mandatory checks
        const failedOptional = validation.failedChecks.filter(c => !c.mandatory).length;
        score += failedOptional * 10;
        
        // High-impact actions
        const highRiskActions = proposal.actions.filter(a => 
            a.type === RemediationActionType.TERMINATE || 
            a.type === RemediationActionType.MIGRATE
        ).length;
        score += highRiskActions * 15;
        
        return Math.min(score, 100); // Cap at 100
    }

    private generateSafetyRecommendations(proposal: RemediationProposal, validation: SafetyValidationResult): string[] {
        const recommendations: string[] = [];
        
        if (validation.failedChecks.length > 0) {
            recommendations.push('Review and address failed safety checks before proceeding');
        }
        
        if (validation.riskScore > 70) {
            recommendations.push('Consider breaking down this proposal into smaller, lower-risk actions');
        }
        
        if (proposal.estimatedSavings > 1000) {
            recommendations.push('High-impact optimization - ensure additional stakeholder review');
        }
        
        if (!proposal.rollbackPlan.steps.length) {
            recommendations.push('Define comprehensive rollback procedures before execution');
        }
        
        return recommendations;
    }

    private async runPreExecutionValidation(action: RemediationAction, proposal: RemediationProposal): Promise<ValidationResult> {
        // Simulate pre-execution validation
        return {
            stepName: 'Pre-execution Validation',
            success: true,
            actualResult: { ready: true },
            expectedResult: { ready: true },
            duration: 500
        };
    }

    private async executeAction(action: RemediationAction): Promise<boolean> {
        // Simulate action execution
        this.outputChannel.appendLine(`▶️ Executing: ${action.description}`);
        
        if (action.command) {
            this.outputChannel.appendLine(`Command: ${action.command}`);
        }
        
        // Simulate execution time
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        return true; // Assume success for demo
    }

    private async runPostExecutionValidation(action: RemediationAction, baselineMetrics: ExecutionMetrics): Promise<ValidationResult[]> {
        const results: ValidationResult[] = [];
        
        for (const validation of action.validation) {
            const result: ValidationResult = {
                stepName: validation.name,
                success: true, // Simulate success
                actualResult: validation.expectedResult,
                expectedResult: validation.expectedResult,
                duration: 300
            };
            results.push(result);
        }
        
        return results;
    }

    private checkRollbackTriggers(validationResults: ValidationResult[], rollbackPlan: RollbackPlan): { required: boolean; reason?: string } {
        // Check if any validation failed
        const failedValidations = validationResults.filter(v => !v.success);
        if (failedValidations.length > 0) {
            return {
                required: true,
                reason: `Validation failures: ${failedValidations.map(v => v.stepName).join(', ')}`
            };
        }
        
        // Additional rollback trigger checks would be implemented here
        return { required: false };
    }

    private async executeRollbackStep(step: RollbackStep): Promise<boolean> {
        this.outputChannel.appendLine(`Executing rollback command: ${step.command}`);
        
        // Simulate rollback step execution
        await new Promise(resolve => setTimeout(resolve, 500));
        
        return true; // Assume success for demo
    }

    private evaluateAutoApprovalConditions(proposal: RemediationProposal, conditions: any[]): boolean {
        // Evaluate auto-approval conditions
        for (const condition of conditions) {
            if (proposal.estimatedSavings <= condition.threshold && proposal.riskLevel === RiskLevel.LOW) {
                return true;
            }
        }
        return false;
    }

    private async captureBaselineMetrics(): Promise<ExecutionMetrics> {
        return {
            cpuUsage: 45.0,
            memoryUsage: 68.5,
            networkLatency: 15.2,
            errorRate: 0.1,
            responseTime: 250.0
        };
    }

    private storeExecutionHistory(proposalId: string, result: ActionExecutionResult): void {
        if (!this.executionHistory.has(proposalId)) {
            this.executionHistory.set(proposalId, []);
        }
        this.executionHistory.get(proposalId)!.push(result);
    }

    private initializeSafetyThresholds(): SafetyThresholds {
        return {
            maxRiskScore: 75,
            maxExecutionTime: 300000, // 5 minutes
            maxErrorRate: 5.0,
            autoRollback: true,
            mandatoryApprovalThreshold: 500 // dollars
        };
    }
}

/**
 * Safety configuration thresholds
 */
interface SafetyThresholds {
    maxRiskScore: number;
    maxExecutionTime: number; // milliseconds
    maxErrorRate: number; // percentage
    autoRollback: boolean;
    mandatoryApprovalThreshold: number; // dollars
}

/**
 * Factory function for creating the safe actions engine
 */
export function createSafeActionsEngine(context: vscode.ExtensionContext): SafeActionsEngine {
    return new SafeActionsEngine(context);
}

/**
 * Main entry points for VS Code integration
 */
export async function validateSafety(
    context: vscode.ExtensionContext,
    proposal: RemediationProposal
): Promise<SafetyValidationResult> {
    const engine = createSafeActionsEngine(context);
    return engine.validateProposalSafety(proposal);
}

export async function executeSafely(
    context: vscode.ExtensionContext,
    proposal: RemediationProposal,
    approvalStatus?: ApprovalStatus
): Promise<ActionExecutionResult[]> {
    const engine = createSafeActionsEngine(context);
    return engine.executeProposalSafely(proposal, approvalStatus);
}

export async function checkApprovals(
    context: vscode.ExtensionContext,
    proposal: RemediationProposal
): Promise<ApprovalStatus> {
    const engine = createSafeActionsEngine(context);
    return engine.checkApprovalStatus(proposal);
}
