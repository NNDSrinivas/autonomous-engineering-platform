/**
 * Lint Fix Proposals - Handle code style and linting issues
 */

import { CIFailure, ExtensionContext, FixProposal, FileChange } from '../types';

/**
 * Generate fix proposal for linting issues
 */
export async function lintFix(failure: CIFailure, ctx: ExtensionContext): Promise<FixProposal> {

    // Parse linting errors from the failure
    const lintErrors = parseLintErrors(failure.log_snippet);

    if (lintErrors.length === 0) {
        return {
            fixable: false,
            summary: 'No specific lint errors identified',
            changes: [],
            confidence: 0,
            riskLevel: 'low'
        };
    }

    // Group errors by file for batch fixing
    const fileGroups = groupErrorsByFile(lintErrors);
    const changes: FileChange[] = [];

    for (const [filePath, errors] of fileGroups.entries()) {
        const fixProposal = generateFileFix(filePath, errors);
        if (fixProposal) {
            changes.push(fixProposal);
        }
    }

    if (changes.length === 0) {
        return {
            fixable: false,
            summary: 'Lint errors require manual review',
            changes: [],
            confidence: 0,
            riskLevel: 'low'
        };
    }

    return {
        fixable: true,
        summary: `Fix ${lintErrors.length} linting issues across ${changes.length} files`,
        changes,
        confidence: 0.9, // Lint fixes are usually safe
        riskLevel: 'low'
    };
}

/**
 * Parse lint errors from log snippet
 */
interface LintError {
    file: string;
    line: number;
    column: number;
    rule: string;
    message: string;
    severity: 'error' | 'warning';
}

function parseLintErrors(logSnippet: string): LintError[] {
    const errors: LintError[] = [];
    const lines = logSnippet.split('\n');

    for (const line of lines) {
        // ESLint format: /path/to/file.js:line:col: error/warning message (rule-name)
        const eslintMatch = line.match(/(.+):(\d+):(\d+):\s+(error|warning)\s+(.+?)\s+\(([^)]+)\)/);
        if (eslintMatch) {
            errors.push({
                file: eslintMatch[1],
                line: parseInt(eslintMatch[2]),
                column: parseInt(eslintMatch[3]),
                severity: eslintMatch[4] as 'error' | 'warning',
                message: eslintMatch[5],
                rule: eslintMatch[6]
            });
            continue;
        }

        // Prettier format: [error] path/to/file.js: message
        const prettierMatch = line.match(/\[error\]\s+(.+?):\s+(.+)/);
        if (prettierMatch) {
            errors.push({
                file: prettierMatch[1],
                line: 0,
                column: 0,
                severity: 'error',
                message: prettierMatch[2],
                rule: 'prettier'
            });
            continue;
        }
    }

    return errors;
}

/**
 * Group errors by file path
 */
function groupErrorsByFile(errors: LintError[]): Map<string, LintError[]> {
    const groups = new Map<string, LintError[]>();

    for (const error of errors) {
        const existing = groups.get(error.file) || [];
        existing.push(error);
        groups.set(error.file, existing);
    }

    return groups;
}

/**
 * Generate fix proposal for a specific file
 */
function generateFileFix(filePath: string, errors: LintError[]): FileChange | null {
    const fixableRules = [
        'quotes', 'semi', 'comma-dangle', 'indent', 'space-before-function-paren',
        'object-curly-spacing', 'array-bracket-spacing', 'key-spacing',
        'no-trailing-spaces', 'eol-last', 'prettier'
    ];

    const fixableErrors = errors.filter(error =>
        fixableRules.some(rule => error.rule.includes(rule))
    );

    if (fixableErrors.length === 0) {
        return null; // No auto-fixable errors
    }

    const errorSummary = fixableErrors.map(e => e.rule).join(', ');

    return {
        filePath,
        action: 'update',
        reason: `Auto-fix lint issues: ${errorSummary}`,
        content: '', // Would contain the fixed content
        diff: `Fix ${fixableErrors.length} lint issues:\n${fixableErrors.map(e => `  - Line ${e.line}: ${e.rule}`).join('\n')}`
    };
}