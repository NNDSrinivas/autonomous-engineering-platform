/**
 * Kubernetes Service Inspector Module
 * 
 * Inspects service configurations, endpoint readiness, and connectivity issues.
 * Identifies service discovery and load balancer problems.
 */

import { Service, ExtensionContext } from '../types';

export async function inspectServices(
    ctx: ExtensionContext,
    namespace?: string
): Promise<Service[]> {
    try {
        const args = ['get', 'services', '-o', 'json'];
        if (namespace) {
            args.push('-n', namespace);
        } else {
            args.push('--all-namespaces');
        }

        const output = await executeKubectl(args);
        const serviceList = JSON.parse(output);

        return serviceList.items.map((service: any) => transformService(service));
    } catch (error) {
        console.error('Failed to inspect services:', error);
        return [];
    }
}

export async function inspectProblemServices(
    ctx: ExtensionContext,
    namespace?: string
): Promise<Service[]> {
    const allServices = await inspectServices(ctx, namespace);

    return allServices.filter(service => {
        return isServiceUnhealthy(service);
    });
}

export function isServiceUnhealthy(service: Service): boolean {
    // LoadBalancer services without external IP after reasonable time
    if (service.spec.type === 'LoadBalancer') {
        const hasExternalIP = service.status?.loadBalancer?.ingress?.some(
            ingress => ingress.ip || ingress.hostname
        );

        if (!hasExternalIP) {
            return true; // LoadBalancer stuck provisioning
        }
    }

    // Services with no selector (can't route traffic)
    if (!service.spec.selector || Object.keys(service.spec.selector).length === 0) {
        return true;
    }

    // Services with no ports
    if (!service.spec.ports || service.spec.ports.length === 0) {
        return true;
    }

    return false;
}

export async function checkServiceEndpoints(
    ctx: ExtensionContext,
    serviceName: string,
    namespace: string
): Promise<{
    hasEndpoints: boolean;
    endpointCount: number;
    readyEndpoints: number;
    details: string;
}> {
    try {
        const args = ['get', 'endpoints', serviceName, '-n', namespace, '-o', 'json'];
        const output = await executeKubectl(args);
        const endpoints = JSON.parse(output);

        let endpointCount = 0;
        let readyEndpoints = 0;

        if (endpoints.subsets) {
            for (const subset of endpoints.subsets) {
                if (subset.addresses) {
                    endpointCount += subset.addresses.length;
                    readyEndpoints += subset.addresses.length;
                }
                if (subset.notReadyAddresses) {
                    endpointCount += subset.notReadyAddresses.length;
                }
            }
        }

        return {
            hasEndpoints: endpointCount > 0,
            endpointCount,
            readyEndpoints,
            details: `Service ${serviceName} has ${readyEndpoints}/${endpointCount} ready endpoints`
        };

    } catch (error) {
        console.error(`Failed to check endpoints for service ${serviceName}:`, error);
        return {
            hasEndpoints: false,
            endpointCount: 0,
            readyEndpoints: 0,
            details: `Error checking endpoints: ${error}`
        };
    }
}

export function categorizeServiceIssue(service: Service): {
    category: string;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    reason: string;
} {
    // LoadBalancer stuck provisioning
    if (service.spec.type === 'LoadBalancer') {
        const hasExternalIP = service.status?.loadBalancer?.ingress?.some(
            ingress => ingress.ip || ingress.hostname
        );

        if (!hasExternalIP) {
            return {
                category: 'LOADBALANCER_PROVISIONING',
                severity: 'HIGH',
                reason: `LoadBalancer service ${service.metadata.name} has no external IP`
            };
        }
    }

    // Service with no selector
    if (!service.spec.selector || Object.keys(service.spec.selector).length === 0) {
        return {
            category: 'NO_SELECTOR',
            severity: 'MEDIUM',
            reason: `Service ${service.metadata.name} has no selector and cannot route traffic`
        };
    }

    // Service with no ports
    if (!service.spec.ports || service.spec.ports.length === 0) {
        return {
            category: 'NO_PORTS',
            severity: 'HIGH',
            reason: `Service ${service.metadata.name} has no ports defined`
        };
    }

    // Check for common port misconfigurations
    const invalidPorts = service.spec.ports.filter(port => {
        return port.port < 1 || port.port > 65535;
    });

    if (invalidPorts.length > 0) {
        return {
            category: 'INVALID_PORT_CONFIG',
            severity: 'HIGH',
            reason: `Service ${service.metadata.name} has invalid port configurations`
        };
    }

    return {
        category: 'HEALTHY',
        severity: 'LOW',
        reason: 'Service appears healthy'
    };
}

export async function getServiceEvents(
    ctx: ExtensionContext,
    serviceName: string,
    namespace: string
): Promise<string> {
    try {
        const args = [
            'get', 'events',
            '-n', namespace,
            '--field-selector', `involvedObject.name=${serviceName}`,
            '--sort-by', '.firstTimestamp'
        ];

        return await executeKubectl(args);
    } catch (error) {
        console.error(`Failed to get events for service ${serviceName}:`, error);
        return `Error retrieving events: ${error}`;
    }
}

export async function testServiceConnectivity(
    ctx: ExtensionContext,
    serviceName: string,
    namespace: string,
    port: number
): Promise<{
    reachable: boolean;
    responseTime?: number;
    error?: string;
}> {
    // Note: This would require network access permissions and careful implementation
    // For now, we'll return a mock response
    console.log(`Would test connectivity to ${serviceName}.${namespace}:${port}`);

    return {
        reachable: false,
        error: 'Connectivity testing not implemented in mock version'
    };
}

export function analyzeServiceNetworkPolicy(service: Service): {
    likelyBlocked: boolean;
    analysis: string;
} {
    // Basic analysis - would be enhanced with actual NetworkPolicy inspection
    if (service.spec.type === 'ClusterIP') {
        return {
            likelyBlocked: false,
            analysis: 'ClusterIP service accessible within cluster by default'
        };
    }

    if (service.spec.type === 'NodePort') {
        return {
            likelyBlocked: false,
            analysis: 'NodePort service accessible from outside cluster'
        };
    }

    if (service.spec.type === 'LoadBalancer') {
        const hasExternalAccess = (service.status?.loadBalancer?.ingress?.length || 0) > 0;
        return {
            likelyBlocked: !hasExternalAccess,
            analysis: hasExternalAccess
                ? 'LoadBalancer has external access configured'
                : 'LoadBalancer may be blocked or provisioning'
        };
    }

    return {
        likelyBlocked: false,
        analysis: 'Standard service configuration'
    };
}

function transformService(k8sService: any): Service {
    return {
        metadata: {
            name: k8sService.metadata.name,
            namespace: k8sService.metadata.namespace
        },
        spec: {
            type: k8sService.spec.type,
            ports: k8sService.spec.ports?.map((port: any) => ({
                name: port.name,
                port: port.port,
                targetPort: port.targetPort,
                protocol: port.protocol || 'TCP'
            })) || [],
            selector: k8sService.spec.selector || {}
        },
        status: k8sService.status
    };
}

// Security: Execute kubectl with validation
async function executeKubectl(args: string[]): Promise<string> {
    const allowedCommands = ['get', 'describe'];

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

    // Mock service list response
    if (args[0] === 'get' && args[1] === 'services' && args.includes('-o') && args.includes('json')) {
        return {
            stdout: JSON.stringify({
                items: [
                    {
                        metadata: {
                            name: 'payments-service',
                            namespace: 'default'
                        },
                        spec: {
                            type: 'LoadBalancer',
                            ports: [
                                {
                                    name: 'http',
                                    port: 80,
                                    targetPort: 8080,
                                    protocol: 'TCP'
                                }
                            ],
                            selector: {
                                app: 'payments'
                            }
                        },
                        status: {
                            loadBalancer: {
                                // No ingress - simulating stuck LoadBalancer
                            }
                        }
                    },
                    {
                        metadata: {
                            name: 'api-service',
                            namespace: 'default'
                        },
                        spec: {
                            type: 'ClusterIP',
                            ports: [
                                {
                                    name: 'http',
                                    port: 8000,
                                    targetPort: 8000,
                                    protocol: 'TCP'
                                }
                            ],
                            selector: {
                                app: 'api'
                            }
                        },
                        status: {}
                    }
                ]
            }),
            stderr: '',
            exitCode: 0
        };
    }

    // Mock endpoints response
    if (args[0] === 'get' && args[1] === 'endpoints') {
        const serviceName = args[2];
        return {
            stdout: JSON.stringify({
                metadata: {
                    name: serviceName,
                    namespace: 'default'
                },
                subsets: [
                    {
                        addresses: [], // No ready endpoints
                        notReadyAddresses: [
                            {
                                ip: '10.244.1.5',
                                targetRef: {
                                    kind: 'Pod',
                                    name: 'payments-deployment-6c8f7b9d4-abc123'
                                }
                            }
                        ],
                        ports: [
                            {
                                port: 8080,
                                protocol: 'TCP'
                            }
                        ]
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