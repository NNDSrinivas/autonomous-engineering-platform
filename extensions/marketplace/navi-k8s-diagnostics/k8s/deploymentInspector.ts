/**
 * Kubernetes Deployment Inspector Module
 * 
 * Inspects deployment status, replica readiness, and rollout issues.
 * Identifies common deployment problems and scaling issues.
 */

import { Deployment, ExtensionContext } from '../types';

export async function inspectDeployments(
    ctx: ExtensionContext,
    namespace?: string
): Promise<Deployment[]> {
    try {
        const args = ['get', 'deployments', '-o', 'json'];
        if (namespace) {
            args.push('-n', namespace);
        } else {
            args.push('--all-namespaces');
        }

        const output = await executeKubectl(args);
        const deploymentList = JSON.parse(output);

        return deploymentList.items.map((deployment: any) => transformDeployment(deployment));
    } catch (error) {
        console.error('Failed to inspect deployments:', error);
        return [];
    }
}

export async function inspectProblemDeployments(
    ctx: ExtensionContext,
    namespace?: string
): Promise<Deployment[]> {
    const allDeployments = await inspectDeployments(ctx, namespace);

    return allDeployments.filter(deployment => {
        return isDeploymentUnhealthy(deployment);
    });
}

export function isDeploymentUnhealthy(deployment: Deployment): boolean {
    // No available replicas
    if (deployment.status.availableReplicas === 0 && deployment.spec.replicas > 0) {
        return true;
    }

    // Not all replicas are ready
    if (deployment.status.readyReplicas < deployment.spec.replicas) {
        return true;
    }

    // Check deployment conditions
    const progressingCondition = deployment.status.conditions?.find(c => c.type === 'Progressing');
    if (progressingCondition) {
        if (progressingCondition.status === 'False') {
            return true;
        }

        // Deployment stuck progressing
        if (progressingCondition.reason === 'ProgressDeadlineExceeded') {
            return true;
        }
    }

    const availableCondition = deployment.status.conditions?.find(c => c.type === 'Available');
    if (availableCondition && availableCondition.status === 'False') {
        return true;
    }

    return false;
}

export function categorizeDeploymentIssue(deployment: Deployment): {
    category: string;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    reason: string;
} {
    // Complete outage
    if (deployment.status.availableReplicas === 0 && deployment.spec.replicas > 0) {
        return {
            category: 'DEPLOYMENT_DOWN',
            severity: 'CRITICAL',
            reason: `Deployment ${deployment.metadata.name} has 0 available replicas`
        };
    }

    // Partial outage
    if (deployment.status.readyReplicas < deployment.spec.replicas) {
        const missingReplicas = deployment.spec.replicas - deployment.status.readyReplicas;
        const percentDown = Math.round((missingReplicas / deployment.spec.replicas) * 100);

        if (percentDown >= 50) {
            return {
                category: 'DEPLOYMENT_DEGRADED',
                severity: 'HIGH',
                reason: `Deployment ${deployment.metadata.name} is ${percentDown}% down (${missingReplicas}/${deployment.spec.replicas} replicas unavailable)`
            };
        } else {
            return {
                category: 'DEPLOYMENT_PARTIAL_OUTAGE',
                severity: 'MEDIUM',
                reason: `Deployment ${deployment.metadata.name} has ${missingReplicas} unavailable replicas`
            };
        }
    }

    // Check for rollout issues
    const progressingCondition = deployment.status.conditions?.find(c => c.type === 'Progressing');
    if (progressingCondition && progressingCondition.status === 'False') {
        if (progressingCondition.reason === 'ProgressDeadlineExceeded') {
            return {
                category: 'ROLLOUT_STUCK',
                severity: 'HIGH',
                reason: `Deployment ${deployment.metadata.name} rollout has exceeded progress deadline`
            };
        }

        return {
            category: 'ROLLOUT_FAILED',
            severity: 'MEDIUM',
            reason: `Deployment ${deployment.metadata.name} rollout is not progressing`
        };
    }

    return {
        category: 'HEALTHY',
        severity: 'LOW',
        reason: 'Deployment appears healthy'
    };
}

export async function getDeploymentEvents(
    ctx: ExtensionContext,
    deploymentName: string,
    namespace: string
): Promise<string> {
    try {
        const args = [
            'get', 'events',
            '-n', namespace,
            '--field-selector', `involvedObject.name=${deploymentName}`,
            '--sort-by', '.firstTimestamp'
        ];

        return await executeKubectl(args);
    } catch (error) {
        console.error(`Failed to get events for deployment ${deploymentName}:`, error);
        return `Error retrieving events: ${error}`;
    }
}

export async function getReplicaSetStatus(
    ctx: ExtensionContext,
    deploymentName: string,
    namespace: string
): Promise<string> {
    try {
        const args = [
            'get', 'replicasets',
            '-n', namespace,
            '-l', `app=${deploymentName}`, // Assuming standard labeling
            '-o', 'wide'
        ];

        return await executeKubectl(args);
    } catch (error) {
        console.error(`Failed to get ReplicaSets for deployment ${deploymentName}:`, error);
        return `Error retrieving ReplicaSets: ${error}`;
    }
}

export function getDeploymentHealthMetrics(deployment: Deployment): {
    availabilityPercent: number;
    readinessPercent: number;
    isScaling: boolean;
    replicaStatus: string;
} {
    const target = deployment.spec.replicas;
    const available = deployment.status.availableReplicas;
    const ready = deployment.status.readyReplicas;
    const total = deployment.status.replicas;

    const availabilityPercent = target > 0 ? Math.round((available / target) * 100) : 0;
    const readinessPercent = target > 0 ? Math.round((ready / target) * 100) : 0;
    const isScaling = total !== target;

    const replicaStatus = `${ready}/${target} ready, ${available} available${isScaling ? `, scaling to ${target}` : ''}`;

    return {
        availabilityPercent,
        readinessPercent,
        isScaling,
        replicaStatus
    };
}

export async function getDeploymentRolloutHistory(
    ctx: ExtensionContext,
    deploymentName: string,
    namespace: string
): Promise<string> {
    try {
        const args = [
            'rollout', 'history',
            'deployment', deploymentName,
            '-n', namespace
        ];

        return await executeKubectl(args);
    } catch (error) {
        console.error(`Failed to get rollout history for deployment ${deploymentName}:`, error);
        return `Error retrieving rollout history: ${error}`;
    }
}

function transformDeployment(k8sDeployment: any): Deployment {
    return {
        metadata: {
            name: k8sDeployment.metadata.name,
            namespace: k8sDeployment.metadata.namespace,
            labels: k8sDeployment.metadata.labels || {}
        },
        spec: {
            replicas: k8sDeployment.spec.replicas,
            selector: k8sDeployment.spec.selector
        },
        status: {
            availableReplicas: k8sDeployment.status.availableReplicas || 0,
            readyReplicas: k8sDeployment.status.readyReplicas || 0,
            replicas: k8sDeployment.status.replicas || 0,
            conditions: k8sDeployment.status.conditions || []
        }
    };
}

// Security: Execute kubectl with validation
async function executeKubectl(args: string[]): Promise<string> {
    const allowedCommands = ['get', 'rollout', 'describe'];

    if (!args.length || !args[0] || !allowedCommands.includes(args[0])) {
        throw new Error(`kubectl command not allowed: ${args[0]}`);
    }

    const unsafeChars = /[;&|`$(){}[\]]/;
    for (const arg of args) {
        if (unsafeChars.test(arg)) {
            throw new Error(`Unsafe kubectl argument: ${arg}`);
        }
    }

    try {
        const result = await executeSecureCommand('kubectl', args, {
            timeout: 30000,
            workingDirectory: process.cwd()
        });

        return result.stdout;
    } catch (error: any) {
        throw new Error(`kubectl execution failed: ${error.message}`);
    }
}

// Mock implementation
async function executeSecureCommand(
    command: string,
    args: string[],
    options: { timeout: number; workingDirectory: string }
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
    console.log(`Would execute: ${command} ${args.join(' ')}`);

    // Mock deployment list response
    if (args[0] === 'get' && args[1] === 'deployments' && args.includes('-o') && args.includes('json')) {
        return {
            stdout: JSON.stringify({
                items: [
                    {
                        metadata: {
                            name: 'payments-deployment',
                            namespace: 'default',
                            labels: { app: 'payments', version: 'v1' }
                        },
                        spec: {
                            replicas: 3,
                            selector: {
                                matchLabels: { app: 'payments' }
                            }
                        },
                        status: {
                            availableReplicas: 0, // Simulating a problem
                            readyReplicas: 0,
                            replicas: 3,
                            conditions: [
                                {
                                    type: 'Progressing',
                                    status: 'False',
                                    reason: 'ProgressDeadlineExceeded',
                                    message: 'ReplicaSet "payments-deployment-6c8f7b9d4" has timed out progressing.',
                                    lastTransitionTime: new Date().toISOString()
                                },
                                {
                                    type: 'Available',
                                    status: 'False',
                                    reason: 'MinimumReplicasUnavailable',
                                    message: 'Deployment does not have minimum availability.',
                                    lastTransitionTime: new Date().toISOString()
                                }
                            ]
                        }
                    },
                    {
                        metadata: {
                            name: 'api-deployment',
                            namespace: 'default',
                            labels: { app: 'api', version: 'v2' }
                        },
                        spec: {
                            replicas: 2,
                            selector: {
                                matchLabels: { app: 'api' }
                            }
                        },
                        status: {
                            availableReplicas: 2,
                            readyReplicas: 2,
                            replicas: 2,
                            conditions: [
                                {
                                    type: 'Progressing',
                                    status: 'True',
                                    reason: 'NewReplicaSetAvailable',
                                    message: 'ReplicaSet "api-deployment-abc123" has successfully progressed.',
                                    lastTransitionTime: new Date().toISOString()
                                },
                                {
                                    type: 'Available',
                                    status: 'True',
                                    reason: 'MinimumReplicasAvailable',
                                    message: 'Deployment has minimum availability.',
                                    lastTransitionTime: new Date().toISOString()
                                }
                            ]
                        }
                    }
                ]
            }),
            stderr: '',
            exitCode: 0
        };
    }

    return {
        stdout: 'Mock response',
        stderr: '',
        exitCode: 0
    };
}