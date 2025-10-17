import { execSync } from 'child_process';
import { mkdir, readFile, writeFile } from 'fs/promises';
import { dirname, join } from 'path';

function sanitizeNote(note: string): string {
  // Remove newlines and comment terminators, and trim whitespace
  return note.replace(/[\r\n]+/g, ' ').replace(/\*\//g, '').trim();
}

export async function applyEdits(workspaceRoot: string, files: string[], note: string) {
  const safeNote = sanitizeNote(note);
  for (const rel of files) {
    const abs = join(workspaceRoot, rel);
    await mkdir(dirname(abs), { recursive: true });
    const old = await readFile(abs).catch(() => Buffer.from(''));
    const next = old.toString('utf8') + `\n// AEP edit: ${safeNote}\n`;
    await writeFile(abs, next, 'utf8');
  }
  return 'Applied MVP edits';
}

function isAllowedCommand(cmd: string): boolean {
  // Define a whitelist of allowed commands for security
  const allowedCommands = [
    /^git\s+/, // git commands
    /^pytest(\s|$)/, // pytest commands
    /^npm(\s|$)/, // npm commands  
    /^pnpm(\s|$)/, // pnpm commands
    /^yarn(\s|$)/, // yarn commands
    /^mvn(\s|$)/, // maven commands
    /^gradle(\s|$)/, // gradle commands
    /^ls(\s|$)/, // list files
    /^pwd(\s|$)/, // print working directory
    /^echo(\s|$)/, // echo command
    /^cat(\s|$)/, // read files
  ];
  return allowedCommands.some((re) => re.test(cmd));
}

export function runCommand(workspaceRoot: string, cmd: string) {
  if (!isAllowedCommand(cmd)) {
    throw new Error(`Command not allowed: ${cmd}`);
  }
  // Only pass essential environment variables to the command, filtering out undefined values
  const filteredEnv: { [key: string]: string } = {};
  if (typeof process.env.PATH !== 'undefined') filteredEnv.PATH = process.env.PATH;
  if (typeof process.env.HOME !== 'undefined') filteredEnv.HOME = process.env.HOME;
  if (typeof process.env.USER !== 'undefined') filteredEnv.USER = process.env.USER;
  
  const out = execSync(cmd, { cwd: workspaceRoot, stdio: 'pipe', env: filteredEnv, encoding: 'utf8' });
  return out.slice(-4000);
}