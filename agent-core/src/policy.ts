import { readFile } from 'fs/promises';
import { join } from 'path';

export type PolicyDoc = {
  allow?: { commands?: string[]; paths?: string[] };
  deny?: { commands?: string[] };
};

// Escape RegExp metacharacters in the pattern, except for glob tokens (to be replaced)
function escapeRegExp(s: string): string {
  // Escape special regex characters to prevent ReDoS and injection, but do NOT escape * or ? (glob tokens)
  return s.replace(/[.+^${}()|[\]\\]/g, (match) => '\\' + match);
}

function matchGlobPattern(pattern: string, path: string): boolean {
  // Convert glob pattern to regex safely with explicit escaping
  // ** matches any number of directories
  // * matches any characters within a directory segment
  
  // Replace '**' with a placeholder to avoid confusion with single '*'
  const DOUBLE_STAR_PLACEHOLDER = '__DOUBLE_STAR_PLACEHOLDER__';
  let regexPattern = escapeRegExp(pattern)
    .replace(/\\\*\\\*/g, DOUBLE_STAR_PLACEHOLDER) // ** becomes placeholder
    .replace(/\\\*/g, '[^/]*') // single * becomes [^/]*
    .replace(new RegExp(escapeRegExp(DOUBLE_STAR_PLACEHOLDER), 'g'), '.*'); // restore ** to .*
  
  const regex = new RegExp(`^${regexPattern}$`);
  return regex.test(path);
}

export async function checkPolicy(
  workspaceRoot: string | undefined,
  step: { command?: string; files?: string[] },
  policyFile = '.aepolicy.json'
): Promise<boolean> {
  if (!workspaceRoot) return false;
  const path = join(workspaceRoot, policyFile);
  let doc: PolicyDoc = { allow: {} };
  try { doc = JSON.parse((await readFile(path)).toString('utf8')); } catch {}

  if (step.command) {
    if (doc.deny?.commands?.some(d => step.command!.startsWith(d))) return false;
    if (doc.allow?.commands && !doc.allow.commands.some(a => step.command!.startsWith(a))) return false;
  }
  if (step.files?.length && doc.allow?.paths?.length) {
    const ok = step.files.every(f => doc.allow!.paths!.some(p => matchGlobPattern(p, f)));
    if (!ok) return false;
  }
  return true;
}