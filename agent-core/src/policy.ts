import { readFile } from 'fs/promises';
import { join } from 'path';

export type PolicyDoc = {
  allow?: { commands?: string[]; paths?: string[] };
  deny?: { commands?: string[] };
};

function matchGlobPattern(pattern: string, path: string): boolean {
  // Convert glob pattern to regex
  // ** matches any number of directories
  // * matches any characters within a directory segment
  const regexPattern = pattern
    .replace(/\*\*/g, '.*') // ** becomes .*
    .replace(/(?<!\*)\*(?!\*)/g, '[^/]*') // single * becomes [^/]*
    .replace(/\//g, '\\/'); // escape forward slashes
  
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