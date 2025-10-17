import { readFile } from 'fs/promises';
import { join } from 'path';

export type PolicyDoc = {
  allow?: { commands?: string[]; paths?: string[] };
  deny?: { commands?: string[] };
};

function matchGlobPattern(pattern: string, path: string): boolean {
  // Convert glob pattern to regex safely with explicit escaping
  // ** matches any number of directories
  // * matches any characters within a directory segment
  // ? matches any single character
  
  // Single-pass conversion using replace with callback for maximum performance
  const regexPattern = pattern.replace(/([.+^${}()|[\]\\])|(\*\*)|(\*)|(\?)/g, (match, esc, dblStar, star, q) => {
    if (esc) return '\\' + esc; // Escape regex metacharacters
    if (dblStar) return '.*';   // ** => .*
    if (star) return '[^/]*';   // * => [^/]*
    if (q) return '[^/]';       // ? => [^/]
    return match;
  });
  
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