/**
 * CI Run Fetcher - Interfaces with CI providers to get failure data
 */

import { ExtensionContext, CIFailure } from '../types';

/**
 * Fetch the latest failing CI run for the project
 */
export async function fetchLatestFailure(ctx: ExtensionContext): Promise<CIFailure | null> {
    try {
        // In a real implementation, this would call the CI provider's API
        // For now, we simulate by calling NAVI's backend CI failure engine

        const response = await fetch(`${ctx.navi.apiUrl}/api/ci/failures/latest`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${ctx.user.id}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                project: ctx.project.name,
                repoUrl: ctx.project.repoUrl,
                ciProvider: ctx.ci.provider
            })
        });

        if (!response.ok) {
            if (response.status === 404) {
                return null; // No failures found
            }
            throw new Error(`Failed to fetch CI data: ${response.statusText}`);
        }

        const failure = await response.json();

        return {
            job: failure.job || 'build',
            step: failure.step || 'unknown',
            error_message: failure.error_message || '',
            log_snippet: failure.log_snippet || '',
            file_path: failure.file_path,
            line_number: failure.line_number,
            failure_type: failure.failure_type || 'unknown',
            logs: failure.full_logs || failure.log_snippet || ''
        };

    } catch (error) {
        console.error('[CI-Fixer] Error fetching CI failure:', error);

        // Fallback: return a mock failure for testing
        if (process.env.NODE_ENV === 'development') {
            return createMockFailure();
        }

        throw error;
    }
}

/**
 * Create a mock CI failure for testing
 */
function createMockFailure(): CIFailure {
    return {
        job: 'build',
        step: 'install-dependencies',
        error_message: 'npm ERR! Cannot resolve dependency "react-nonexistent-lib"',
        log_snippet: `npm WARN deprecated package@1.0.0: This package is deprecated
npm ERR! code ERESOLVE
npm ERR! Cannot resolve dependency "react-nonexistent-lib"
npm ERR! Could not resolve dependency:
npm ERR! peer react-nonexistent-lib@"^1.0.0" from the root project`,
        file_path: 'package.json',
        line_number: 15,
        failure_type: 'missing_dependency',
        logs: `[2024-12-25T10:30:00.000Z] Starting npm install...
[2024-12-25T10:30:01.000Z] npm WARN deprecated package@1.0.0: This package is deprecated
[2024-12-25T10:30:02.000Z] npm ERR! code ERESOLVE
[2024-12-25T10:30:02.000Z] npm ERR! Cannot resolve dependency "react-nonexistent-lib"
[2024-12-25T10:30:02.000Z] npm ERR! Could not resolve dependency:
[2024-12-25T10:30:02.000Z] npm ERR! peer react-nonexistent-lib@"^1.0.0" from the root project
[2024-12-25T10:30:02.000Z] npm ERR! 
[2024-12-25T10:30:02.000Z] npm ERR! Fix the upstream dependency conflict, or retry
[2024-12-25T10:30:02.000Z] npm ERR! this command with --force, or --legacy-peer-deps
[2024-12-25T10:30:02.000Z] npm install failed with exit code 1`
    };
}