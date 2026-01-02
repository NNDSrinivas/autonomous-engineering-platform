/**
 * TypeScript Fix Proposals - Handle type checking errors
 */

import { CIFailure, ExtensionContext, FixProposal, FileChange } from '../types';

/**
 * Generate fix proposal for TypeScript type errors
 */
export async function typesFix(failure: CIFailure, ctx: ExtensionContext): Promise<FixProposal> {

    const typeErrors = parseTypeErrors(failure.log_snippet);

    if (typeErrors.length === 0) {
        return {
            fixable: false,
            summary: 'No specific type errors identified',
            changes: [],
            confidence: 0,
            riskLevel: 'medium'
        };
    }

    // Only auto-fix low-risk type issues
    const safelyFixableErrors = typeErrors.filter(isTypeErrorSafelyFixable);

    if (safelyFixableErrors.length === 0) {
        return {
            fixable: false,
            summary: `${typeErrors.length} type errors require manual review`,
            changes: [],
            confidence: 0,
            riskLevel: 'high'
        };
    }

    // Generate changes for safely fixable errors
    const changes: FileChange[] = safelyFixableErrors
        .map(error => generateTypeFix(error))
        .filter(change => change !== null) as FileChange[];

    return {
        fixable: changes.length > 0,
        summary: `Fix ${changes.length} type issues (${typeErrors.length - changes.length} require manual review)`,
        changes,
        confidence: 0.75,
        riskLevel: 'medium' // Type fixes can change behavior
    };
}

/**
 * Parse TypeScript errors from log snippet
 */
interface TypeError {
    file: string;
    line: number;
    column: number;
    code: string; // e.g., "TS2304"
    message: string;
    type: 'missing-property' | 'type-mismatch' | 'missing-import' | 'unknown';
}

function parseTypeErrors(logSnippet: string): TypeError[] {
    const errors: TypeError[] = [];
    const lines = logSnippet.split('\n');

    for (const line of lines) {
        // TypeScript format: path/to/file.ts(line,col): error TS2304: message
        const tsMatch = line.match(/(.+\.tsx?)\((\d+),(\d+)\):\s+error\s+(TS\d+):\s+(.+)/);
        if (tsMatch) {
            const message = tsMatch[5];
            let type: TypeError['type'] = 'unknown';

            if (message.includes('Property') && message.includes('does not exist')) {
                type = 'missing-property';
            } else if (message.includes('not assignable to type')) {
                type = 'type-mismatch';
            } else if (message.includes('Cannot find')) {
                type = 'missing-import';
            }

            errors.push({
                file: tsMatch[1],
                line: parseInt(tsMatch[2]),
                column: parseInt(tsMatch[3]),
                code: tsMatch[4],
                message,
                type
            });
        }
    }

    return errors;
}

/**
 * Determine if a type error can be safely auto-fixed
 */
function isTypeErrorSafelyFixable(error: TypeError): boolean {
    // Missing imports are usually safe to fix
    if (error.type === 'missing-import' && error.code === 'TS2304') {
        return true;
    }

    // Simple property additions to interfaces (with caution)
    if (error.type === 'missing-property' && error.message.includes('optional')) {
        return true;
    }

    // Some common type mismatches that are safe
    if (error.type === 'type-mismatch') {
        // string/number conversions
        if (error.message.includes('string') && error.message.includes('number')) {
            return false; // Don't auto-fix these, they're often meaningful
        }
    }

    return false; // Most type errors need human review
}

/**
 * Generate fix for a safely fixable type error
 */
function generateTypeFix(error: TypeError): FileChange | null {

    if (error.type === 'missing-import' && error.code === 'TS2304') {
        const typeName = extractTypeNameFromError(error.message);
        if (typeName) {
            return {
                filePath: error.file,
                action: 'update',
                reason: `Add missing import for type: ${typeName}`,
                diff: `+ import { ${typeName} } from './${typeName.toLowerCase()}'; // Auto-imported missing type`
            };
        }
    }

    if (error.type === 'missing-property') {
        const propertyName = extractPropertyNameFromError(error.message);
        if (propertyName) {
            return {
                filePath: error.file,
                action: 'update',
                reason: `Add optional property: ${propertyName}`,
                diff: `+ ${propertyName}?: any; // Auto-added optional property`
            };
        }
    }

    return null;
}

/**
 * Extract type name from error message
 */
function extractTypeNameFromError(message: string): string | null {
    const match = message.match(/Cannot find name '([^']+)'/);
    return match ? match[1] : null;
}

/**
 * Extract property name from error message
 */
function extractPropertyNameFromError(message: string): string | null {
    const match = message.match(/Property '([^']+)' does not exist/);
    return match ? match[1] : null;
}