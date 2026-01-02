// extensions/vscode-aep/src/navi-core/planning/FeaturePlanEngine.ts
/**
 * Phase 3 Step 1: Autonomous Feature Planning
 * 
 * Analyzes repository architecture and creates detailed implementation plans
 * for new features, matching Copilot/Cline capability for complex multi-file changes.
 * 
 * Core Capabilities:
 * - Stack detection (React, Next.js, Vue, etc.)
 * - Architecture pattern recognition
 * - Multi-file change planning
 * - Risk assessment and assumptions
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export type TechStack =
    | 'react'
    | 'nextjs'
    | 'vue'
    | 'angular'
    | 'svelte'
    | 'express'
    | 'fastapi'
    | 'django'
    | 'unknown';

export interface RepositoryAnalysis {
    stack: TechStack;
    packageManager: 'npm' | 'yarn' | 'pnpm' | 'unknown';
    buildTool: 'webpack' | 'vite' | 'rollup' | 'unknown';
    testFramework: 'jest' | 'vitest' | 'cypress' | 'unknown';
    styling: 'css' | 'scss' | 'tailwind' | 'styled-components' | 'unknown';
    stateManagement: 'redux' | 'zustand' | 'context' | 'unknown';
}

export interface ImplementationStep {
    order: number;
    title: string;
    description: string;
    files: string[];
    estimatedComplexity: 'low' | 'medium' | 'high';
    dependencies?: string[];
}

export interface FeaturePlan {
    featureTitle: string;
    summary: string;
    repositoryAnalysis: RepositoryAnalysis;
    implementationSteps: ImplementationStep[];
    risks: string[];
    assumptions: string[];
    estimatedTimeMinutes: number;
    confidence: number; // 0-100
}

/**
 * Analyzes repository structure and generates detailed feature implementation plans.
 * 
 * This is the core intelligence that makes NAVI capable of autonomous feature coding,
 * understanding project architecture and generating step-by-step implementation strategies.
 */
export class FeaturePlanEngine {

    /**
     * Generates a complete feature implementation plan based on user request and repo analysis.
     * 
     * @param featureRequest User's natural language feature description
     * @param workspaceRoot Path to workspace root directory
     * @returns Detailed implementation plan with steps and analysis
     */
    static async generatePlan(featureRequest: string, workspaceRoot: string): Promise<FeaturePlan> {
        console.log(`[FeaturePlanEngine] Generating plan for: "${featureRequest}"`);

        // Step 1: Analyze repository architecture
        const repoAnalysis = await this.analyzeRepository(workspaceRoot);
        console.log(`[FeaturePlanEngine] Detected stack: ${repoAnalysis.stack}`);

        // Step 2: Generate implementation steps based on request + architecture
        const steps = await this.planImplementationSteps(featureRequest, repoAnalysis, workspaceRoot);

        // Step 3: Assess risks and make assumptions
        const risks = this.assessRisks(featureRequest, repoAnalysis, steps);
        const assumptions = this.identifyAssumptions(featureRequest, repoAnalysis);

        // Step 4: Estimate complexity and time
        const estimatedTime = this.estimateImplementationTime(steps);
        const confidence = this.calculateConfidence(repoAnalysis, steps);

        const plan: FeaturePlan = {
            featureTitle: this.extractFeatureTitle(featureRequest),
            summary: this.generateSummary(featureRequest, repoAnalysis),
            repositoryAnalysis: repoAnalysis,
            implementationSteps: steps,
            risks,
            assumptions,
            estimatedTimeMinutes: estimatedTime,
            confidence
        };

        console.log(`[FeaturePlanEngine] Generated plan with ${steps.length} steps, ${confidence}% confidence`);
        return plan;
    }

    /**
     * Analyzes repository structure to detect technology stack and patterns.
     */
    private static async analyzeRepository(workspaceRoot: string): Promise<RepositoryAnalysis> {
        const analysis: RepositoryAnalysis = {
            stack: 'unknown',
            packageManager: 'unknown',
            buildTool: 'unknown',
            testFramework: 'unknown',
            styling: 'unknown',
            stateManagement: 'unknown'
        };

        try {
            // Detect package manager
            if (fs.existsSync(path.join(workspaceRoot, 'package-lock.json'))) {
                analysis.packageManager = 'npm';
            } else if (fs.existsSync(path.join(workspaceRoot, 'yarn.lock'))) {
                analysis.packageManager = 'yarn';
            } else if (fs.existsSync(path.join(workspaceRoot, 'pnpm-lock.yaml'))) {
                analysis.packageManager = 'pnpm';
            }

            // Read package.json to detect dependencies
            const packageJsonPath = path.join(workspaceRoot, 'package.json');
            if (fs.existsSync(packageJsonPath)) {
                const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
                const allDeps = {
                    ...packageJson.dependencies,
                    ...packageJson.devDependencies
                };

                // Detect framework/stack
                if (allDeps['next']) {
                    analysis.stack = 'nextjs';
                } else if (allDeps['react']) {
                    analysis.stack = 'react';
                } else if (allDeps['vue']) {
                    analysis.stack = 'vue';
                } else if (allDeps['@angular/core']) {
                    analysis.stack = 'angular';
                } else if (allDeps['svelte']) {
                    analysis.stack = 'svelte';
                } else if (allDeps['express']) {
                    analysis.stack = 'express';
                } else if (allDeps['fastapi']) {
                    analysis.stack = 'fastapi';
                } else if (allDeps['django']) {
                    analysis.stack = 'django';
                }

                // Detect build tools
                if (allDeps['vite']) {
                    analysis.buildTool = 'vite';
                } else if (allDeps['webpack']) {
                    analysis.buildTool = 'webpack';
                } else if (allDeps['rollup']) {
                    analysis.buildTool = 'rollup';
                }

                // Detect test framework
                if (allDeps['jest']) {
                    analysis.testFramework = 'jest';
                } else if (allDeps['vitest']) {
                    analysis.testFramework = 'vitest';
                } else if (allDeps['cypress']) {
                    analysis.testFramework = 'cypress';
                }

                // Detect styling approach
                if (allDeps['tailwindcss']) {
                    analysis.styling = 'tailwind';
                } else if (allDeps['styled-components']) {
                    analysis.styling = 'styled-components';
                } else if (allDeps['sass'] || allDeps['scss']) {
                    analysis.styling = 'scss';
                } else {
                    analysis.styling = 'css';
                }

                // Detect state management
                if (allDeps['@reduxjs/toolkit'] || allDeps['redux']) {
                    analysis.stateManagement = 'redux';
                } else if (allDeps['zustand']) {
                    analysis.stateManagement = 'zustand';
                } else if (analysis.stack === 'react' || analysis.stack === 'nextjs') {
                    analysis.stateManagement = 'context'; // Assume Context API
                }
            }

        } catch (error) {
            console.error(`[FeaturePlanEngine] Repository analysis failed: ${error}`);
        }

        return analysis;
    }

    /**
     * Plans implementation steps based on feature request and repository analysis.
     */
    private static async planImplementationSteps(
        featureRequest: string,
        repoAnalysis: RepositoryAnalysis,
        workspaceRoot: string
    ): Promise<ImplementationStep[]> {

        // This is a simplified implementation - in production, this would use LLM
        // to generate contextual steps based on the specific request and repo structure

        const steps: ImplementationStep[] = [];

        if (repoAnalysis.stack === 'react' || repoAnalysis.stack === 'nextjs') {
            steps.push(
                {
                    order: 1,
                    title: 'Create Component Structure',
                    description: 'Create React component files with proper TypeScript interfaces',
                    files: ['src/components/', 'src/types/'],
                    estimatedComplexity: 'medium',
                    dependencies: []
                },
                {
                    order: 2,
                    title: 'Implement Core Logic',
                    description: 'Add business logic and state management',
                    files: ['src/hooks/', 'src/utils/'],
                    estimatedComplexity: 'high',
                    dependencies: ['Create Component Structure']
                },
                {
                    order: 3,
                    title: 'Add Styling',
                    description: `Style components using ${repoAnalysis.styling}`,
                    files: ['src/styles/', 'src/components/'],
                    estimatedComplexity: 'low',
                    dependencies: ['Create Component Structure']
                },
                {
                    order: 4,
                    title: 'Integration & Testing',
                    description: 'Integrate with existing app and add tests',
                    files: ['src/pages/', '__tests__/'],
                    estimatedComplexity: 'medium',
                    dependencies: ['Implement Core Logic', 'Add Styling']
                }
            );
        } else {
            // Generic implementation steps for unknown stacks
            steps.push(
                {
                    order: 1,
                    title: 'Analyze Feature Requirements',
                    description: 'Break down the feature into implementable components',
                    files: [],
                    estimatedComplexity: 'low',
                    dependencies: []
                },
                {
                    order: 2,
                    title: 'Create Core Implementation',
                    description: 'Implement main feature functionality',
                    files: ['src/'],
                    estimatedComplexity: 'high',
                    dependencies: ['Analyze Feature Requirements']
                },
                {
                    order: 3,
                    title: 'Add Tests and Documentation',
                    description: 'Ensure feature is well-tested and documented',
                    files: ['tests/', 'docs/'],
                    estimatedComplexity: 'medium',
                    dependencies: ['Create Core Implementation']
                }
            );
        }

        return steps;
    }

    /**
     * Assesses potential risks in the implementation plan.
     */
    private static assessRisks(
        featureRequest: string,
        repoAnalysis: RepositoryAnalysis,
        steps: ImplementationStep[]
    ): string[] {
        const risks: string[] = [];

        if (repoAnalysis.stack === 'unknown') {
            risks.push('Unknown technology stack may require manual adjustments');
        }

        if (steps.some(step => step.estimatedComplexity === 'high')) {
            risks.push('High complexity steps may require additional debugging time');
        }

        if (featureRequest.toLowerCase().includes('database') || featureRequest.toLowerCase().includes('api')) {
            risks.push('External dependencies (database/API) may require additional configuration');
        }

        if (repoAnalysis.testFramework === 'unknown') {
            risks.push('No test framework detected - testing step may need manual setup');
        }

        return risks;
    }

    /**
     * Identifies assumptions made in the implementation plan.
     */
    private static identifyAssumptions(
        featureRequest: string,
        repoAnalysis: RepositoryAnalysis
    ): string[] {
        const assumptions: string[] = [];

        assumptions.push('Existing code quality and architecture patterns will be maintained');
        assumptions.push('No breaking changes to existing functionality are required');

        if (repoAnalysis.stack !== 'unknown') {
            assumptions.push(`Implementation will follow ${repoAnalysis.stack} best practices`);
        }

        if (repoAnalysis.styling !== 'unknown') {
            assumptions.push(`Styling will be consistent with existing ${repoAnalysis.styling} approach`);
        }

        return assumptions;
    }

    /**
     * Estimates implementation time based on step complexity.
     */
    private static estimateImplementationTime(steps: ImplementationStep[]): number {
        const complexityMinutes = {
            low: 15,
            medium: 45,
            high: 90
        };

        return steps.reduce((total, step) => {
            return total + complexityMinutes[step.estimatedComplexity];
        }, 0);
    }

    /**
     * Calculates confidence score based on repository analysis completeness.
     */
    private static calculateConfidence(
        repoAnalysis: RepositoryAnalysis,
        steps: ImplementationStep[]
    ): number {
        let confidence = 50; // Base confidence

        // Boost confidence for known stack
        if (repoAnalysis.stack !== 'unknown') confidence += 20;
        if (repoAnalysis.packageManager !== 'unknown') confidence += 10;
        if (repoAnalysis.buildTool !== 'unknown') confidence += 10;
        if (repoAnalysis.testFramework !== 'unknown') confidence += 10;

        return Math.min(confidence, 100);
    }

    /**
     * Extracts a concise feature title from the user request.
     */
    private static extractFeatureTitle(featureRequest: string): string {
        // Simple extraction - in production this could use NLP
        const words = featureRequest.split(' ');
        if (words.length <= 4) {
            return featureRequest;
        }
        return words.slice(0, 4).join(' ') + '...';
    }

    /**
     * Generates a plan summary combining request and analysis.
     */
    private static generateSummary(
        featureRequest: string,
        repoAnalysis: RepositoryAnalysis
    ): string {
        return `Implementing "${featureRequest}" in ${repoAnalysis.stack} project using ${repoAnalysis.packageManager} and ${repoAnalysis.buildTool}.`;
    }
}