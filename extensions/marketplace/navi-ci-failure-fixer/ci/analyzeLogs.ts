/**
 * Log Analysis - Leverages NAVI's existing CI failure analysis
 */

import { FailureAnalysis } from '../types';

/**
 * Analyze CI failure logs using NAVI's intelligence
 */
export async function analyzeLogs(logs: string): Promise<FailureAnalysis> {
    // Extract key patterns from the logs
    const lines = logs.split('\n');
    const errorLines = lines.filter(line =>
        line.includes('ERR!') ||
        line.includes('ERROR') ||
        line.includes('FAIL') ||
        line.includes('AssertionError') ||
        line.includes('TypeError')
    );

    const warningLines = lines.filter(line =>
        line.includes('WARN') ||
        line.includes('deprecated')
    );

    // Analyze patterns for error classification
    const patterns = [];
    let errorType = 'unknown';
    let confidence = 0.5;

    // Dependency errors
    if (logs.includes('Cannot resolve dependency') || logs.includes('Module not found')) {
        patterns.push('dependency_missing');
        errorType = 'dependency';
        confidence = 0.9;
    }

    // Build errors
    if (logs.includes('compilation failed') || logs.includes('Build failed')) {
        patterns.push('build_failure');
        errorType = 'build';
        confidence = 0.85;
    }

    // Test failures
    if (logs.includes('failing') || logs.includes('AssertionError')) {
        patterns.push('test_failure');
        errorType = 'test';
        confidence = 0.8;
    }

    // Lint errors
    if (logs.includes('eslint') || logs.includes('prettier')) {
        patterns.push('lint_failure');
        errorType = 'lint';
        confidence = 0.75;
    }

    // Type errors
    if (logs.includes('TS') || logs.includes('Type') || logs.includes('is not assignable')) {
        patterns.push('type_error');
        errorType = 'types';
        confidence = 0.8;
    }

    // Generate contextual suggestions
    const suggestions = generateSuggestions(errorType, logs);

    return {
        patterns,
        confidence,
        errorType,
        context: errorLines.slice(0, 5), // Top 5 error lines for context
        suggestions
    };
}

/**
 * Generate actionable suggestions based on error type
 */
function generateSuggestions(errorType: string, logs: string): string[] {
    const suggestions = [];

    switch (errorType) {
        case 'dependency':
            suggestions.push('Install missing dependencies');
            if (logs.includes('peer')) {
                suggestions.push('Resolve peer dependency conflicts');
            }
            if (logs.includes('deprecated')) {
                suggestions.push('Update deprecated packages');
            }
            break;

        case 'build':
            suggestions.push('Fix compilation errors');
            suggestions.push('Check TypeScript configuration');
            suggestions.push('Verify import statements');
            break;

        case 'test':
            suggestions.push('Update failing test expectations');
            suggestions.push('Check test environment setup');
            suggestions.push('Review test data and mocks');
            break;

        case 'lint':
            suggestions.push('Run linter with --fix flag');
            suggestions.push('Update code formatting');
            suggestions.push('Fix style violations');
            break;

        case 'types':
            suggestions.push('Add missing type definitions');
            suggestions.push('Fix type assignments');
            suggestions.push('Update TypeScript configuration');
            break;

        default:
            suggestions.push('Review logs for specific error details');
            suggestions.push('Check recent code changes');
            suggestions.push('Verify environment configuration');
    }

    return suggestions;
}