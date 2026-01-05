/**
 * NAVI Cost & Usage Optimization Extension - Core Orchestration
 * 
 * Production-ready FinOps extension that turns NAVI into a Staff Engineer + FinOps advisor.
 * 
 * Key capabilities:
 * - Analyze cloud cost & resource usage across AWS, GCP, Azure
 * - Detect waste, inefficiencies, and cost regressions
 * - Correlate usage with code, deployments, and traffic patterns
 * - Explain why money is being spent with business context
 * - Propose safe, approval-gated optimizations
 * - Never change infrastructure without explicit permission
 * 
 * This extension establishes NAVI as business-aware engineering intelligence
 * that can save real money, not just fix bugs.
 * 
 * @author Navra Labs
 * @version 1.0.0
 */

import * as vscode from 'vscode';
import {
    CostAnalysisRequest,
    CostAnalysisResult,
    CostData,
    UsageData,
    WasteDetectionResult,
    OptimizationType,
    OptimizationProposal,
    SavingsEstimate,
    CostIssue,
    RemediationProposal,
    ImplementationEffort,
    IssuePriority,
    RiskLevel
} from './types';

// Source imports - Multi-cloud cost data collection
import { fetchAWSCostData } from './sources/awsCostExplorer';
import { fetchGCPBillingData } from './sources/gcpBilling';
import { fetchAzureCostData } from './sources/azureCost';
import { fetchK8sUsageData } from './sources/kubernetesUsage';
import { fetchTrafficData } from './sources/traffic';

// Analysis imports - Comprehensive analysis engines
import { WasteDetector } from './analysis/wasteDetector';
import { IdleResourceDetector } from './analysis/idleResourceDetector';
import { OverprovisioningAnalyzer } from './analysis/overProvisioningAnalyzer';
import { CostRegressionDetector } from './analysis/costRegressionDetector';
import { UnitEconomicsAnalyzer } from './analysis/unitEconomicsAnalyzer';

// Diagnosis imports - Business context and impact
import { IssueClassifier } from './diagnosis/classifyIssue';
import { CostExplainer } from './diagnosis/explain';
import { SavingsEstimator } from './diagnosis/savingsEstimate';

// Remediation imports - Safe, approval-gated actions
import { createOptimizationProposalEngine } from './remediation/proposeOptimizations';
import { createSafeActionsEngine } from './remediation/safeActions';

/**
 * Main entry point for the Cost & Usage Optimization extension
 */
export async function onInvoke(request: CostAnalysisRequest, context: vscode.ExtensionContext): Promise<CostAnalysisResult> {
    console.log('🏁 Starting Cost & Usage Optimization analysis...');
    
    try {
        // Initialize remediation engines
        const proposalEngine = createOptimizationProposalEngine(context);
        const safeActionsEngine = createSafeActionsEngine(context);

        // Step 1: Collect cost and usage data from all configured sources
        console.log('💰 Collecting cost and usage data...');
        const [costData, usageData] = await Promise.all([
            collectCostData(request.config),
            collectUsageData(request.config)
        ]);

        console.log(`💰 Collected cost data from ${countDefinedProperties(costData)} sources`);
        console.log(`📊 Collected usage data from ${countDefinedProperties(usageData)} sources`);

        // Initialize analysis engines with collected data
        const wasteDetector = new WasteDetector(costData, usageData);
        const idleResourceDetector = new IdleResourceDetector(costData, usageData);
        const overprovisioningAnalyzer = new OverprovisioningAnalyzer(costData, usageData);
        const costRegressionDetector = new CostRegressionDetector(costData, usageData);
        const unitEconomicsAnalyzer = new UnitEconomicsAnalyzer(costData, usageData);

        // Step 2: Analyze for waste, inefficiencies, and opportunities using class-based engines
        console.log('🔍 Analyzing for cost optimization opportunities...');
        const wasteResults = await analyzeWithEngines(
            costData, 
            usageData, 
            {
                wasteDetector,
                idleResourceDetector,
                overprovisioningAnalyzer,
                costRegressionDetector,
                unitEconomicsAnalyzer
            }
        );
        
        if (wasteResults.length === 0) {
            return {
                sessionId: `cost-analysis-${Date.now()}`,
                timestamp: new Date().toISOString(),
                summary: {
                    totalWasteDetected: 0,
                    potentialSavings: 0,
                    optimizationOpportunities: 0,
                    confidence: 1.0
                },
                message: "✅ No significant cost inefficiencies detected. Your infrastructure appears to be well-optimized!",
                issues: [],
                proposals: [],
                requiresApproval: false,
                nextActions: ['Continue monitoring for cost changes']
            };
        }

        const issueClassifier = new IssueClassifier(wasteResults);

        // Step 3: Classify and diagnose issues with business context using class-based diagnosis
        console.log('🔬 Classifying and diagnosing cost issues...');
        const issues: CostIssue[] = [];
        const savingsEstimates: SavingsEstimate[] = [];
        
        for (const wasteResult of wasteResults) {
            try {
                const classification = await issueClassifier.classifyIssue(wasteResult);
                
                if (classification) {
                    const explainer = new CostExplainer(wasteResult, classification);
                    const explanation = await explainer.generateExplanation();
                    const estimator = new SavingsEstimator(wasteResult, classification, costData);
                    const savings = await estimator.generateSavingsEstimate();
                    
                    // Create comprehensive cost issue
                    const issue: CostIssue = {
                        id: wasteResult.id,
                        type: classification.type,
                        severity: classification.severity,
                        title: explanation.issue.title || `${wasteResult.type} Issue`,
                        description: wasteResult.description,
                        explanation: explanation.rootCause.primaryCause,
                        businessImpact: classification.businessImpact,
                        technicalDetails: classification.technicalDetails,
                        affectedResources: wasteResult.affectedResources,
                        estimatedSavings: wasteResult.wastedAmount,
                        confidence: wasteResult.confidence,
                        priority: classification.priority,
                        detectedAt: wasteResult.detectedAt
                    };
                    
                    issues.push(issue);
                    savingsEstimates.push(savings);
                }
            } catch (error) {
                console.warn(`Failed to process waste result ${wasteResult.id}:`, error);
            }
        }

        console.log(`📋 Classified ${issues.length} cost optimization opportunities`);

        // Step 4: Generate comprehensive optimization proposals with approval requirements
        console.log('🛠️ Generating optimization proposals...');
        const proposals: RemediationProposal[] = await proposalEngine.proposeOptimizations(issues);
        let requiresApproval = false;
        
        // Validate safety and check approval requirements
        for (const proposal of proposals) {
            const safetyValidation = await safeActionsEngine.validateProposalSafety(proposal);
            const approvalStatus = await safeActionsEngine.checkApprovalStatus(proposal);
            
            if (proposal.requiresApproval || approvalStatus.status === 'pending') {
                requiresApproval = true;
            }
        }

        // Step 5: Calculate total savings and build comprehensive response
        const totalPotentialSavings = savingsEstimates.reduce((sum, estimate) => 
            sum + estimate.monthlyAmount, 0
        );
        
        const nextActions = generateNextActions(issues, proposals, requiresApproval);
        
        console.log(`💰 Analysis complete: ${issues.length} opportunities, $${totalPotentialSavings.toFixed(2)}/month potential savings`);

        return {
            sessionId: `cost-analysis-${Date.now()}`,
            timestamp: new Date().toISOString(),
            summary: {
                totalWasteDetected: wasteResults.length,
                potentialSavings: totalPotentialSavings,
                optimizationOpportunities: issues.length,
                confidence: calculateOverallConfidence(issues)
            },
            issues,
            proposals: proposals.map(p => convertToOptimizationProposal(p)),
            savingsEstimates,
            requiresApproval,
            nextActions
        };

    } catch (error) {
        console.error('❌ Cost analysis failed:', error);
        
        return {
            sessionId: `cost-analysis-error-${Date.now()}`,
            timestamp: new Date().toISOString(),
            summary: {
                totalWasteDetected: 0,
                potentialSavings: 0,
                optimizationOpportunities: 0,
                confidence: 0
            },
            error: `Cost analysis failed: ${error instanceof Error ? error.message : String(error)}`,
            issues: [],
            proposals: [createFallbackProposal(error)],
            requiresApproval: false,
            nextActions: [
                '🔧 Configure cost data sources',
                '🔐 Verify IAM permissions',
                '📊 Enable usage metrics collection'
            ]
        };
    }
}

/**
 * Collect cost data from all configured cloud providers
 */
async function collectCostData(config: any): Promise<CostData> {
    const costData: CostData = {
        aws: null,
        gcp: null,
        azure: null,
        consolidated: {
            totalSpend: 0,
            currency: 'USD',
            period: '30d',
            breakdown: []
        }
    };

    try {
        // AWS Cost Explorer
        if (config.aws) {
            console.log('💰 Fetching AWS cost data...');
            costData.aws = await fetchAWSCostData(config.aws);
            costData.consolidated.totalSpend += costData.aws.totalCost;
        }

        // GCP Billing
        if (config.gcp) {
            console.log('💰 Fetching GCP billing data...');
            costData.gcp = await fetchGCPBillingData(config.gcp);
            costData.consolidated.totalSpend += costData.gcp.totalCost;
        }

        // Azure Cost Management
        if (config.azure) {
            console.log('💰 Fetching Azure cost data...');
            costData.azure = await fetchAzureCostData(config.azure);
            costData.consolidated.totalSpend += costData.azure.totalCost;
        }

        console.log(`💰 Total consolidated spend: $${costData.consolidated.totalSpend.toFixed(2)}`);
        return costData;

    } catch (error) {
        console.error('Failed to collect cost data:', error);
        return costData; // Return partial data
    }
}

/**
 * Collect usage data from infrastructure sources
 */
async function collectUsageData(config: any): Promise<UsageData> {
    const usageData: UsageData = {
        kubernetes: null,
        traffic: null,
        summary: {
            totalResources: 0,
            utilizationRate: 0,
            idleResources: 0
        }
    };

    try {
        // Kubernetes usage metrics
        if (config.kubernetes) {
            console.log('📊 Fetching Kubernetes usage data...');
            usageData.kubernetes = await fetchK8sUsageData(config.kubernetes);
        }

        // Traffic and load patterns
        if (config.traffic) {
            console.log('🌐 Fetching traffic data...');
            usageData.traffic = await fetchTrafficData(config.traffic);
        }

        return usageData;

    } catch (error) {
        console.error('Failed to collect usage data:', error);
        return usageData; // Return partial data
    }
}

/**
 * Analyze for waste using class-based analysis engines
 */
async function analyzeWithEngines(
    costData: CostData,
    usageData: UsageData,
    engines: {
        wasteDetector: WasteDetector;
        idleResourceDetector: IdleResourceDetector;
        overprovisioningAnalyzer: OverprovisioningAnalyzer;
        costRegressionDetector: CostRegressionDetector;
        unitEconomicsAnalyzer: UnitEconomicsAnalyzer;
    }
): Promise<WasteDetectionResult[]> {
    const results: WasteDetectionResult[] = [];

    try {
        // General waste detection
        console.log('🔍 Running general waste detection...');
        const wasteResults = await engines.wasteDetector.detectAllWaste();
        results.push(...wasteResults);

        // Idle resource detection
        if (usageData.kubernetes) {
            console.log('💤 Detecting idle resources...');
            const idleResults = await engines.idleResourceDetector.detectIdleResources();
            results.push(...idleResults);
        }

        // Over-provisioning analysis
        console.log('📈 Analyzing over-provisioning...');
        const overprovisioningResults = await engines.overprovisioningAnalyzer.analyzeOverprovisioning();
        results.push(...overprovisioningResults);

        // Cost regression detection
        console.log('📉 Detecting cost regressions...');
        const regressionResults = await engines.costRegressionDetector.detectCostRegressions();
        results.push(...regressionResults);

        // Unit economics analysis
        console.log('💡 Analyzing unit economics...');
        const unitEconomicsResults = await engines.unitEconomicsAnalyzer.analyzeUnitEconomics();
        results.push(...unitEconomicsResults);

        console.log(`✅ Analysis complete: ${results.length} waste patterns detected`);

    } catch (error) {
        console.warn('Some analysis engines failed:', error);
    }

    return results;
}

/**
 * Helper functions
 */
function countDefinedProperties(obj: any): number {
    return Object.values(obj).filter(v => v !== null && v !== undefined).length;
}

function convertToOptimizationProposal(proposal: RemediationProposal): OptimizationProposal {
    return {
        id: proposal.id,
        issueId: proposal.issueId,
        title: proposal.title,
        description: proposal.description,
        type: proposal.type,
        priority: proposal.priority,
        confidence: 0.8, // Default confidence
        estimatedSavings: proposal.estimatedSavings,
        implementationEffort: ImplementationEffort.MEDIUM,
        riskLevel: proposal.riskLevel,
        requiresApproval: proposal.requiresApproval,
        actions: proposal.actions.map(a => ({
            order: 1,
            action: a.description,
            description: a.description,
            command: a.command || '',
            expectedResult: 'Success',
            validation: 'Validate completion',
            rollbackCommand: a.rollbackCommand || '',
            automatable: a.automatable
        })),
        safeActions: {
            immediate: ['Review proposal details'],
            validation: ['Confirm safety checks'],
            rollbackPlan: proposal.rollbackPlan.description,
            monitoring: ['Monitor metrics after implementation']
        },
        timeline: proposal.timeline
    };
}

function createFallbackProposal(error: any): OptimizationProposal {
    return {
        id: `fallback-proposal-${Date.now()}`,
        issueId: 'analysis-failure',
        title: 'Enable Cost Analysis',
        description: `Cost analysis failed: ${error instanceof Error ? error.message : String(error)}`,
        type: OptimizationType.INVESTIGATION,
        priority: IssuePriority.P2,
        confidence: 1.0,
        estimatedSavings: 0,
        implementationEffort: ImplementationEffort.LOW,
        riskLevel: RiskLevel.LOW,
        requiresApproval: false,
        actions: [
            {
                order: 1,
                action: 'Configure cost data sources',
                description: 'Configure cost data sources (AWS Cost Explorer, GCP Billing, Azure Cost Management)',
                command: '',
                expectedResult: 'Data sources configured',
                validation: 'Test API connectivity',
                rollbackCommand: '',
                automatable: false
            }
        ],
        safeActions: {
            immediate: ['Review cost data source configuration'],
            validation: ['Test API connectivity'],
            rollbackPlan: 'N/A - Read-only configuration changes',
            monitoring: ['Monitor cost data collection']
        },
        timeline: {
            estimatedDuration: '30 minutes',
            phases: [
                {
                    phase: 'Configuration',
                    duration: '30 minutes',
                    description: 'Configure cost data sources',
                    dependencies: []
                }
            ],
            milestones: ['Configuration complete']
        }
    };
}

/**
 * Generate next action recommendations
 */
function generateNextActions(
    issues: CostIssue[], 
    proposals: RemediationProposal[], 
    requiresApproval: boolean
): string[] {
    const actions: string[] = [];
    
    if (issues.length === 0) {
        actions.push('✅ Continue monitoring for cost changes');
        return actions;
    }
    
    // Add high-impact actions first
    const highImpactIssues = issues.filter(i => i.priority === 'P0' || i.priority === 'P1' || i.estimatedSavings > 500);
    if (highImpactIssues.length > 0) {
        actions.push(`💰 Review ${highImpactIssues.length} high-impact optimization opportunities`);
    }
    
    // Add approval-required actions
    if (requiresApproval) {
        actions.push('🔐 Review and approve optimization proposals');
    }
    
    // Add monitoring actions
    actions.push('📊 Set up cost monitoring alerts for future changes');
    
    // Add investigation actions for unclear cases
    const investigationIssues = issues.filter(i => i.confidence < 0.7);
    if (investigationIssues.length > 0) {
        actions.push(`🔍 Investigate ${investigationIssues.length} optimization opportunities requiring analysis`);
    }

    return actions;
}

/**
 * Calculate overall confidence in the analysis
 */
function calculateOverallConfidence(issues: CostIssue[]): number {
    if (issues.length === 0) {
        return 1.0;
    }
    
    const totalConfidence = issues.reduce((sum, issue) => sum + (issue.confidence || 0.5), 0);
    return Math.min(0.99, totalConfidence / issues.length);
}
