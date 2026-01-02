/**
 * Dependency Fix Proposals - Handle missing/conflicting dependencies
 */

import { CIFailure, ExtensionContext, FixProposal, FileChange } from '../types';

/**
 * Generate fix proposal for dependency issues
 */
export async function dependencyFix(failure: CIFailure, ctx: ExtensionContext): Promise<FixProposal> {
    const changes: FileChange[] = [];
    let confidence = 0.7;

    // Parse error message to extract package name
    const packageName = extractPackageName(failure.error_message);

    if (!packageName) {
        return {
            fixable: false,
            summary: 'Unable to identify missing package',
            changes: [],
            confidence: 0,
            riskLevel: 'high'
        };
    }

    // Check if it's a peer dependency issue
    if (failure.error_message.includes('peer')) {
        return handlePeerDependency(packageName, failure, ctx);
    }

    // Check if it's a missing dependency
    if (failure.error_message.includes('Cannot resolve') || failure.error_message.includes('Module not found')) {
        return handleMissingDependency(packageName, failure, ctx);
    }

    // Check if it's a version conflict
    if (failure.error_message.includes('conflicting') || failure.error_message.includes('version')) {
        return handleVersionConflict(packageName, failure, ctx);
    }

    return {
        fixable: false,
        summary: 'Dependency issue type not recognized',
        changes: [],
        confidence: 0,
        riskLevel: 'medium'
    };
}

/**
 * Extract package name from error message
 */
function extractPackageName(errorMessage: string): string | null {
    // Common patterns for package names in error messages
    const patterns = [
        /Cannot resolve dependency ['""]([^'""]+)['""]/,
        /Module not found: ['""]([^'""]+)['""]/,
        /Cannot find module ['""]([^'""]+)['""]/,
        /peer ([^@\s]+)@/,
        /dependency ['""]([^'""]+)['""]/
    ];

    for (const pattern of patterns) {
        const match = errorMessage.match(pattern);
        if (match) {
            return match[1];
        }
    }

    return null;
}

/**
 * Handle peer dependency conflicts
 */
function handlePeerDependency(packageName: string, failure: CIFailure, ctx: ExtensionContext): FixProposal {
    const changes: FileChange[] = [{
        filePath: 'package.json',
        action: 'update',
        reason: `Add missing peer dependency: ${packageName}`,
        diff: `+ "${packageName}": "^1.0.0" // Added to resolve peer dependency`
    }];

    return {
        fixable: true,
        summary: `Install missing peer dependency: ${packageName}`,
        changes,
        confidence: 0.8,
        riskLevel: 'medium' // Peer deps can have compatibility issues
    };
}

/**
 * Handle missing dependencies
 */
function handleMissingDependency(packageName: string, failure: CIFailure, ctx: ExtensionContext): FixProposal {
    const changes: FileChange[] = [{
        filePath: 'package.json',
        action: 'update',
        reason: `Install missing dependency: ${packageName}`,
        diff: `+ "${packageName}": "latest" // Auto-install missing dependency`
    }];

    return {
        fixable: true,
        summary: `Install missing dependency: ${packageName}`,
        changes,
        confidence: 0.85,
        riskLevel: 'medium' // New deps always have some risk
    };
}

/**
 * Handle version conflicts
 */
function handleVersionConflict(packageName: string, failure: CIFailure, ctx: ExtensionContext): FixProposal {
    const changes: FileChange[] = [{
        filePath: 'package.json',
        action: 'update',
        reason: `Resolve version conflict for: ${packageName}`,
        diff: `~ "${packageName}": "^latest" // Updated to resolve version conflict`
    }];

    return {
        fixable: true,
        summary: `Resolve version conflict: ${packageName}`,
        changes,
        confidence: 0.7,
        riskLevel: 'high' // Version changes can break things
    };
}