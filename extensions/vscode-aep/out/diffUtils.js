"use strict";
/**
 * Apply unified diff to original text
 * Uses 'diff' npm package for robust patch application
 *
 * Install: npm install diff @types/diff
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.applyUnifiedDiff = applyUnifiedDiff;
exports.createUnifiedDiff = createUnifiedDiff;
const Diff = require("diff");
function applyUnifiedDiff(original, unifiedDiff) {
    try {
        // Parse the unified diff
        const patches = Diff.parsePatch(unifiedDiff);
        if (!patches || patches.length === 0) {
            throw new Error('Invalid or empty diff provided');
        }
        // Apply the first patch (assuming single-file diff)
        const result = Diff.applyPatch(original, patches[0]);
        if (result === false) {
            throw new Error('Failed to apply patch - diff may not match original content');
        }
        return result;
    }
    catch (error) {
        throw new Error(`Diff application failed: ${error.message}`);
    }
}
/**
 * Generate a unified diff between two strings
 * Useful for creating diffs on the fly
 */
function createUnifiedDiff(original, modified, filename = 'file') {
    const patch = Diff.createPatch(filename, original, modified, 'original', 'modified');
    return patch;
}
//# sourceMappingURL=diffUtils.js.map