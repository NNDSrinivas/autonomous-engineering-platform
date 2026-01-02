/**
 * Test Fix Proposals - Handle failing unit/integration tests
 */

import { CIFailure, ExtensionContext, FixProposal, FileChange } from '../types';

/**
 * Generate fix proposal for test failures
 * NOTE: Test fixes are high-risk and should usually require manual review
 */
export async function testFix(failure: CIFailure, ctx: ExtensionContext): Promise<FixProposal> {

    const testFailures = parseTestFailures(failure.log_snippet);

    if (testFailures.length === 0) {
        return {
            fixable: false,
            summary: 'No specific test failures identified',
            changes: [],
            confidence: 0,
            riskLevel: 'high'
        };
    }

    // Only auto-fix very safe test changes
    const safelyFixableTests = testFailures.filter(isSafelyFixable);

    if (safelyFixableTests.length === 0) {
        return {
            fixable: false,
            summary: `${testFailures.length} test failures require manual review`,
            changes: [],
            confidence: 0,
            riskLevel: 'high'
        };
    }

    // Generate changes only for safely fixable tests
    const changes: FileChange[] = safelyFixableTests
        .map(test => generateTestFix(test))
        .filter(change => change !== null) as FileChange[];

    return {
        fixable: changes.length > 0,
        summary: `Fix ${changes.length} safe test issues (${testFailures.length - changes.length} require manual review)`,
        changes,
        confidence: 0.6, // Even safe test fixes have some risk
        riskLevel: 'high' // Tests are always high-risk to auto-fix
    };
}

/**
 * Parse test failures from log snippet
 */
interface TestFailure {
    file: string;
    testName: string;
    error: string;
    type: 'assertion' | 'timeout' | 'setup' | 'unknown';
    line?: number;
}

function parseTestFailures(logSnippet: string): TestFailure[] {
    const failures: TestFailure[] = [];
    const lines = logSnippet.split('\n');

    let currentTest: Partial<TestFailure> = {};

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Jest format: FAIL path/to/test.js
        const failMatch = line.match(/FAIL\s+(.+\.(?:test|spec)\.[jt]s)/);
        if (failMatch) {
            currentTest = { file: failMatch[1] };
            continue;
        }

        // Test name: ● Test Suite › test name
        const testMatch = line.match(/●\s+(.+?)\s+›\s+(.+)/);
        if (testMatch && currentTest.file) {
            currentTest.testName = testMatch[2];
            continue;
        }

        // Error message
        if (line.trim().startsWith('Error:') || line.trim().startsWith('AssertionError:')) {
            currentTest.error = line.trim();

            // Classify error type
            if (line.includes('AssertionError') || line.includes('expect')) {
                currentTest.type = 'assertion';
            } else if (line.includes('timeout') || line.includes('Timeout')) {
                currentTest.type = 'timeout';
            } else if (line.includes('beforeAll') || line.includes('beforeEach')) {
                currentTest.type = 'setup';
            } else {
                currentTest.type = 'unknown';
            }

            // If we have enough info, add to failures
            if (currentTest.file && currentTest.testName && currentTest.error) {
                failures.push(currentTest as TestFailure);
                currentTest = { file: currentTest.file }; // Reset for next test in same file
            }
        }
    }

    return failures;
}

/**
 * Determine if a test failure can be safely auto-fixed
 */
function isSafelyFixable(failure: TestFailure): boolean {
    // Only fix very specific, low-risk issues

    // Timeout issues with reasonable increases
    if (failure.type === 'timeout' && failure.error.includes('5000ms')) {
        return true; // Can safely increase timeout
    }

    // Simple assertion updates for obvious changes
    if (failure.type === 'assertion') {
        // Only fix snapshot updates or very obvious value changes
        if (failure.error.includes('snapshot') || failure.error.includes('Snapshot')) {
            return true;
        }
    }

    // Setup issues that are clearly environment-related
    if (failure.type === 'setup' && failure.error.includes('ECONNREFUSED')) {
        return false; // Don't auto-fix connection issues
    }

    return false; // Most test failures require human judgment
}

/**
 * Generate fix for a safely fixable test
 */
function generateTestFix(failure: TestFailure): FileChange | null {
    if (failure.type === 'timeout') {
        return {
            filePath: failure.file,
            action: 'update',
            reason: `Increase timeout for flaky test: ${failure.testName}`,
            diff: `- jest.setTimeout(5000);\n+ jest.setTimeout(10000); // Increased timeout for stability`
        };
    }

    if (failure.type === 'assertion' && failure.error.includes('snapshot')) {
        return {
            filePath: failure.file,
            action: 'update',
            reason: `Update snapshot for test: ${failure.testName}`,
            diff: `Update snapshot to match current output`
        };
    }

    return null;
}