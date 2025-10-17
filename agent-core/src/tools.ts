import { execSync } from 'child_process';
import { mkdir, readFile, writeFile } from 'fs/promises';
import { dirname, join } from 'path';

export async function applyEdits(workspaceRoot: string, files: string[], note: string) {
  for (const rel of files) {
    const abs = join(workspaceRoot, rel);
    await mkdir(dirname(abs), { recursive: true });
    const old = await readFile(abs).catch(() => Buffer.from(''));
    const next = old.toString('utf8') + `\n// AEP edit: ${note}\n`;
    await writeFile(abs, next, 'utf8');
  }
  return 'Applied MVP edits';
}
export function runCommand(workspaceRoot: string, cmd: string) {
  const out = execSync(cmd, { cwd: workspaceRoot, stdio: 'pipe', env: process.env, encoding: 'utf8' });
  return out.slice(-4000);
}