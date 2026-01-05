// Deprecated duplicate file. Forward to canonical implementation.
import { applyUnifiedPatch as applyUnifiedPatchBase } from './applyPatch';

export async function applyUnifiedPatch(patch: string): Promise<boolean> {
  return applyUnifiedPatchBase(patch);
}