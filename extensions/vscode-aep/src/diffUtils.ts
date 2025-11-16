/**
 * Apply unified diff to original text
 * Uses 'diff' npm package for robust patch application
 * 
 * Install: npm install diff @types/diff
 */

import * as Diff from 'diff';

export function applyUnifiedDiff(original: string, unifiedDiff: string): string {
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
  } catch (error: any) {
    throw new Error(`Diff application failed: ${error.message}`);
  }
}

/**
 * Generate a unified diff between two strings
 * Useful for creating diffs on the fly
 */
export function createUnifiedDiff(
  original: string,
  modified: string,
  filename: string = 'file'
): string {
  const patch = Diff.createPatch(
    filename,
    original,
    modified,
    'original',
    'modified'
  );
  return patch;
}
