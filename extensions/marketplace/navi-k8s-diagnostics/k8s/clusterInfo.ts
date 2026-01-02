/**
 * Kubernetes Cluster Information Module
 * 
 * Provides cluster-level information and resource discovery for diagnostics.
 * Uses kubectl commands with proper error handling and security controls.
 */

import { ClusterInfo, ExtensionContext } from '../types';

export async function getClusterInfo(ctx: ExtensionContext): Promise<ClusterInfo> {
    try {
        // Get cluster version
        const version = await executeKubectl(['version', '--client=false', '--short=true']);
        const serverVersion = extractServerVersion(version);

        // Get node count
        const nodes = await executeKubectl(['get', 'nodes', '--no-headers']);
        const nodeCount = nodes.trim().split('\n').filter(line => line.trim()).length;

        // Get all namespaces
        const namespacesOutput = await executeKubectl(['get', 'namespaces', '--no-headers', '-o', 'custom-columns=NAME:.metadata.name']);
        const namespaces = namespacesOutput.trim().split('\n').filter(line => line.trim());

        return {
            version: serverVersion,
            nodeCount,
            namespaces: namespaces
        };

    } catch (error) {
        console.error('Failed to get cluster info:', error);
        return {
            version: 'unknown',
            nodeCount: 0,
            namespaces: ['default']
        };
    }
}

export async function checkKubectlAccess(): Promise<boolean> {
    try {
        await executeKubectl(['cluster-info']);
        return true;
    } catch (error) {
        console.error('kubectl access check failed:', error);
        return false;
    }
}

export async function getCurrentContext(): Promise<string> {
    try {
        const context = await executeKubectl(['config', 'current-context']);
        return context.trim();
    } catch (error) {
        console.error('Failed to get current context:', error);
        return 'unknown';
    }
}

export async function getNamespaceResourceCounts(namespace: string): Promise<{
    pods: number;
    deployments: number;
    services: number;
    configMaps: number;
    secrets: number;
}> {
    try {
        const [pods, deployments, services, configMaps, secrets] = await Promise.all([
            countResources('pods', namespace),
            countResources('deployments', namespace),
            countResources('services', namespace),
            countResources('configmaps', namespace),
            countResources('secrets', namespace)
        ]);

        return { pods, deployments, services, configMaps, secrets };
    } catch (error) {
        console.error(`Failed to get resource counts for namespace ${namespace}:`, error);
        return { pods: 0, deployments: 0, services: 0, configMaps: 0, secrets: 0 };
    }
}

async function countResources(resourceType: string, namespace?: string): Promise<number> {
    try {
        const args = ['get', resourceType, '--no-headers'];
        if (namespace) {
            args.push('-n', namespace);
        }

        const output = await executeKubectl(args);
        const lines = output.trim().split('\n').filter(line => line.trim());
        return lines.length;
    } catch (error) {
        console.error(`Failed to count ${resourceType}:`, error);
        return 0;
    }
}

function extractServerVersion(versionOutput: string): string {
    try {
        // Parse kubectl version output to extract server version
        const lines = versionOutput.split('\n');
        for (const line of lines) {
            if (line.includes('Server Version:')) {
                const match = line.match(/v(\d+\.\d+\.\d+)/);
                return match?.[1] || 'unknown';
            }
        }
        return 'unknown';
    } catch (error) {
        console.error('Failed to extract server version:', error);
        return 'unknown';
    }
}

// Security: Execute kubectl with timeout and validation
async function executeKubectl(args: string[]): Promise<string> {
    // Validate args to prevent command injection
    const allowedCommands = [
        'version', 'cluster-info', 'config', 'get', 'describe', 'logs'
    ];

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
        // This would be implemented by the NAVI runtime to execute kubectl
        // with proper timeouts, logging, and security controls
        const result = await executeSecureCommand('kubectl', args, {
            timeout: 30000, // 30 second timeout
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
    // This is a mock - the real implementation would be provided by NAVI
    console.log(`Would execute: ${command} ${args.join(' ')}`);

    // Mock successful response for demonstration
    if (command === 'kubectl' && args[0] === 'version') {
        return {
            stdout: 'Client Version: v1.28.2\\nServer Version: v1.28.0',
            stderr: '',
            exitCode: 0
        };
    }

    if (command === 'kubectl' && args[0] === 'get' && args[1] === 'nodes') {
        return {
            stdout: 'node-1   Ready    control-plane   10d   v1.28.0\\nnode-2   Ready    <none>          10d   v1.28.0',
            stderr: '',
            exitCode: 0
        };
    }

    if (command === 'kubectl' && args[0] === 'get' && args[1] === 'namespaces') {
        return {
            stdout: 'default\\nkube-system\\nkube-public\\nkube-node-lease',
            stderr: '',
            exitCode: 0
        };
    }

    return {
        stdout: '',
        stderr: 'Mock implementation',
        exitCode: 0
    };
}