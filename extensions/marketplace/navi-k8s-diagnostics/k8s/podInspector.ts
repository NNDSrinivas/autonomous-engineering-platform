/**
 * Kubernetes Pod Inspector Module
 * 
 * Inspects pod status, health, and issues with security controls.
 * Focuses on common failure modes: CrashLoopBackOff, ImagePullBackOff, etc.
 */

import { Pod, ContainerStatus, ExtensionContext } from '../types';

export async function inspectPods(
    ctx: ExtensionContext,
    namespace?: string
): Promise<Pod[]> {
    try {
        const args = ['get', 'pods', '-o', 'json'];
        if (namespace) {
            args.push('-n', namespace);
        } else {
            args.push('--all-namespaces');
        }

        const output = await executeKubectl(args);
        const podList = JSON.parse(output);

        return podList.items.map((pod: any) => transformPod(pod));
    } catch (error) {
        console.error('Failed to inspect pods:', error);
        return [];
    }
}

export async function inspectProblemPods(
    ctx: ExtensionContext,
    namespace?: string
): Promise<Pod[]> {
    const allPods = await inspectPods(ctx, namespace);

    return allPods.filter(pod => {
        // Filter for pods with issues
        return isPodUnhealthy(pod);
    });
}

export function isPodUnhealthy(pod: Pod): boolean {
    // Check pod phase
    if (pod.status.phase === 'Failed' || pod.status.phase === 'Unknown') {
        return true;
    }

    // Check for pending pods that should be running
    if (pod.status.phase === 'Pending') {
        // Pod is unhealthy if pending for more than reasonable time
        const createdTime = new Date(pod.metadata.creationTimestamp).getTime();
        const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
        if (createdTime < fiveMinutesAgo) {
            return true;
        }
    }

    // Check container statuses
    if (pod.status.containerStatuses) {
        for (const containerStatus of pod.status.containerStatuses) {
            if (isContainerUnhealthy(containerStatus)) {
                return true;
            }
        }
    }

    // Check pod conditions
    const readyCondition = pod.status.conditions?.find(c => c.type === 'Ready');
    if (readyCondition && readyCondition.status === 'False') {
        return true;
    }

    return false;
}

export function isContainerUnhealthy(containerStatus: ContainerStatus): boolean {
    // High restart count indicates crash loops
    if (containerStatus.restartCount > 5) {
        return true;
    }

    // Container not ready
    if (!containerStatus.ready) {
        return true;
    }

    // Check container state
    if (containerStatus.state.waiting) {
        const reason = containerStatus.state.waiting.reason;
        const problematicReasons = [
            'CrashLoopBackOff',
            'ImagePullBackOff',
            'ErrImagePull',
            'CreateContainerConfigError',
            'InvalidImageName'
        ];

        if (problematicReasons.includes(reason)) {
            return true;
        }
    }

    if (containerStatus.state.terminated) {
        // Non-zero exit code indicates failure
        if (containerStatus.state.terminated.exitCode !== 0) {
            return true;
        }
    }

    return false;
}

export async function getPodLogs(
    ctx: ExtensionContext,
    podName: string,
    namespace: string,
    container?: string,
    tailLines: number = 100
): Promise<string> {
    try {
        const args = ['logs', podName, '-n', namespace, '--tail', tailLines.toString()];
        if (container) {
            args.push('-c', container);
        }

        return await executeKubectl(args);
    } catch (error) {
        console.error(`Failed to get logs for pod ${podName}:`, error);
        return `Error retrieving logs: ${error}`;
    }
}

export async function getPodEvents(
    ctx: ExtensionContext,
    podName: string,
    namespace: string
): Promise<string> {
    try {
        const args = [
            'get', 'events',
            '-n', namespace,
            '--field-selector', `involvedObject.name=${podName}`,
            '--sort-by', '.firstTimestamp'
        ];

        return await executeKubectl(args);
    } catch (error) {
        console.error(`Failed to get events for pod ${podName}:`, error);
        return `Error retrieving events: ${error}`;
    }
}

export function categorizePodIssue(pod: Pod): {
    category: string;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    reason: string;
} {
    if (pod.status.phase === 'Failed') {
        return {
            category: 'POD_FAILED',
            severity: 'CRITICAL',
            reason: 'Pod has failed completely'
        };
    }

    if (pod.status.containerStatuses) {
        for (const containerStatus of pod.status.containerStatuses) {
            if (containerStatus.state.waiting) {
                const reason = containerStatus.state.waiting.reason;

                switch (reason) {
                    case 'CrashLoopBackOff':
                        return {
                            category: 'CRASH_LOOP',
                            severity: 'CRITICAL',
                            reason: `Container ${containerStatus.name} is crash looping`
                        };

                    case 'ImagePullBackOff':
                    case 'ErrImagePull':
                        return {
                            category: 'IMAGE_PULL_ERROR',
                            severity: 'HIGH',
                            reason: `Cannot pull image for container ${containerStatus.name}`
                        };

                    case 'CreateContainerConfigError':
                        return {
                            category: 'CONFIG_ERROR',
                            severity: 'HIGH',
                            reason: `Configuration error for container ${containerStatus.name}`
                        };
                }
            }

            // High restart count
            if (containerStatus.restartCount > 10) {
                return {
                    category: 'HIGH_RESTART_COUNT',
                    severity: 'HIGH',
                    reason: `Container ${containerStatus.name} has ${containerStatus.restartCount} restarts`
                };
            }
        }
    }

    // Pending for too long
    if (pod.status.phase === 'Pending') {
        const createdTime = new Date(pod.metadata.creationTimestamp).getTime();
        const tenMinutesAgo = Date.now() - (10 * 60 * 1000);
        if (createdTime < tenMinutesAgo) {
            return {
                category: 'STUCK_PENDING',
                severity: 'MEDIUM',
                reason: 'Pod has been pending for over 10 minutes'
            };
        }
    }

    return {
        category: 'HEALTHY',
        severity: 'LOW',
        reason: 'Pod appears healthy'
    };
}

function transformPod(k8sPod: any): Pod {
    return {
        metadata: {
            name: k8sPod.metadata.name,
            namespace: k8sPod.metadata.namespace,
            labels: k8sPod.metadata.labels || {},
            annotations: k8sPod.metadata.annotations || {},
            creationTimestamp: k8sPod.metadata.creationTimestamp
        },
        spec: {
            containers: k8sPod.spec.containers.map((c: any) => ({
                name: c.name,
                image: c.image,
                resources: c.resources,
                env: c.env
            })),
            restartPolicy: k8sPod.spec.restartPolicy,
            nodeName: k8sPod.spec.nodeName
        },
        status: {
            phase: k8sPod.status.phase,
            conditions: k8sPod.status.conditions || [],
            containerStatuses: k8sPod.status.containerStatuses?.map((cs: any) => ({
                name: cs.name,
                ready: cs.ready,
                restartCount: cs.restartCount,
                state: cs.state
            })),
            podIP: k8sPod.status.podIP
        }
    };
}

// Security: Execute kubectl with validation (reusing from clusterInfo.ts pattern)
async function executeKubectl(args: string[]): Promise<string> {
    // Validate args to prevent command injection
    const allowedCommands = ['get', 'logs', 'describe'];

    if (!args.length || !args[0] || !allowedCommands.includes(args[0])) {
        throw new Error(`kubectl command not allowed: ${args[0]}`);
    }

    // Validate all args are safe (no shell metacharacters)
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

// Mock implementation - would be provided by NAVI extension runtime
async function executeSecureCommand(
    command: string,
    args: string[],
    options: { timeout: number; workingDirectory: string }
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
    console.log(`Would execute: ${command} ${args.join(' ')}`);

    // Mock pod list response
    if (args[0] === 'get' && args[1] === 'pods' && args.includes('-o') && args.includes('json')) {
        return {
            stdout: JSON.stringify({
                items: [
                    {
                        metadata: {
                            name: 'payments-deployment-6c8f7b9d4-abc123',
                            namespace: 'default',
                            labels: { app: 'payments' },
                            annotations: {},
                            creationTimestamp: new Date().toISOString()
                        },
                        spec: {
                            containers: [
                                {
                                    name: 'payments',
                                    image: 'payments:v1.2.3',
                                    resources: {
                                        requests: { memory: '256Mi', cpu: '250m' },
                                        limits: { memory: '512Mi', cpu: '500m' }
                                    }
                                }
                            ],
                            restartPolicy: 'Always',
                            nodeName: 'worker-1'
                        },
                        status: {
                            phase: 'Running',
                            conditions: [
                                {
                                    type: 'Ready',
                                    status: 'False',
                                    reason: 'ContainersNotReady',
                                    message: 'containers with unready status: [payments]'
                                }
                            ],
                            containerStatuses: [
                                {
                                    name: 'payments',
                                    ready: false,
                                    restartCount: 15,
                                    state: {
                                        waiting: {
                                            reason: 'CrashLoopBackOff',
                                            message: 'back-off 5m0s restarting failed container=payments pod=payments-deployment-6c8f7b9d4-abc123_default'
                                        }
                                    }
                                }
                            ],
                            podIP: '10.244.1.5'
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