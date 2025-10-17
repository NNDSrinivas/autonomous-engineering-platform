import { exec as execCallback } from 'child_process';
import { promisify } from 'util';
import { mkdir, readFile, writeFile } from 'fs/promises';
import { dirname, join } from 'path';

const exec = promisify(execCallback);

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
  // Strict whitelist of allowed commands for maximum security
  const allowedCommands = [
    /^git\s+(status|log|diff|show|branch|checkout|add|commit|push|pull|fetch|clone)\b/, // specific git subcommands only
    /^pytest\s+/, // pytest commands
    /^npm\s+(install|test|run|build|start)\b/, // specific npm subcommands only
    /^pnpm\s+(install|test|run|build|start)\b/, // specific pnpm subcommands only  
    /^yarn\s+(install|test|run|build|start)\b/, // specific yarn subcommands only
    /^mvn\s+(clean|compile|test|package|install)\b/, // specific maven subcommands only
    /^gradle\s+(clean|build|test|assemble)\b/, // specific gradle subcommands only
    /^ls\s*(-[la]*\s*)?[.\w/-]*$/, // ls with basic flags and safe paths only
    /^pwd\s*$/, // pwd with no arguments
    /^echo\s+[\w\s.-]+$/, // echo with alphanumeric content only
    /^cat\s+[\w./-]+$/, // cat with safe file paths only
  ];
  
  // Additional security: reject commands with dangerous patterns
  if (cmd.match(/[;&|`$(){}><]/)) {
    return false; // No shell metacharacters allowed
  }
  
  return allowedCommands.some((re) => re.test(cmd));
}

export async function runCommand(workspaceRoot: string, cmd: string): Promise<string> {
  if (!isAllowedCommand(cmd)) {
    throw new Error(`Command not allowed: ${cmd}`);
  }
  
  // Additional security validations
  if (cmd.includes('sudo') || cmd.includes('su ') || cmd.includes('chmod +x')) {
    throw new Error('Privileged commands are not allowed');
  }
  if (cmd.includes('..') || cmd.includes('/etc/') || cmd.includes('/root/')) {
    throw new Error('Path traversal or system directory access not allowed');
  }
  
  // Strict environment with minimal safe variables
  const safeEnvVars = ['PATH', 'HOME', 'USER', 'LANG', 'PWD'];
  const sanitizedEnv: { [key: string]: string } = {};
  
  for (const key of safeEnvVars) {
    const value = process.env[key];
    if (value != null && typeof value === 'string') {
      // Sanitize environment variable values
      const sanitizedValue = value.replace(/[;&|`$(){}]/g, '');
      if (sanitizedValue.length > 0) {
        sanitizedEnv[key] = sanitizedValue;
      }
    }
  }
  
  try {
    const { stdout } = await exec(cmd, { 
      cwd: workspaceRoot, 
      env: sanitizedEnv, 
      encoding: 'utf8',
      timeout: 30000, // 30 second timeout
      maxBuffer: 1024 * 1024 // 1MB max buffer
    });
    return stdout.slice(-4000);
  } catch (error: any) {
    // Sanitize error messages to prevent information leakage
    const sanitizedMessage = error.message?.replace(/\/[^\s]+/g, '[PATH]') || 'Command execution failed';
    throw new Error(`Command failed: ${sanitizedMessage}`);
  }
}