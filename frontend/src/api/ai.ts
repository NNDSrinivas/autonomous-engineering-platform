/**
 * AI Code Generation API helpers.
 * Provides functions for generating context-aware diffs and applying patches.
 */

export interface GenerateDiffRequest {
  intent: string;
  files: string[];
}

export interface GenerateDiffResponse {
  diff: string;
  stats: {
    files: number;
    additions: number;
    deletions: number;
    size_kb: number;
  };
}

export interface ApplyPatchRequest {
  diff: string;
  dry_run?: boolean;
}

export interface ApplyPatchResponse {
  applied: boolean;
  output: string;
  dry_run: boolean;
}

/**
 * Generate a context-aware unified diff from plan intent.
 * 
 * @param intent - Description of what to implement
 * @param files - Target file paths to modify (max 5)
 * @returns Generated diff with statistics
 * @throws Error if generation fails
 */
export async function generateDiff(intent: string, files: string[]): Promise<GenerateDiffResponse> {
  const response = await fetch("/api/ai/generate-diff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent, files }),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to generate diff: ${errorText}`);
  }
  
  return await response.json();
}

/**
 * Apply a unified diff to the repository.
 * 
 * @param diff - Unified diff to apply
 * @param dryRun - If true, validates without applying (default: false)
 * @returns Application result with git output
 * @throws Error if application fails
 */
export async function applyPatch(diff: string, dryRun = false): Promise<ApplyPatchResponse> {
  const response = await fetch("/api/ai/apply-patch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ diff, dry_run: dryRun }),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to apply patch: ${errorText}`);
  }
  
  return await response.json();
}
