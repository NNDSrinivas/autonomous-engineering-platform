"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.applyEdits = applyEdits;
exports.runCommand = runCommand;
const child_process_1 = require("child_process");
const util_1 = require("util");
const promises_1 = require("fs/promises");
const path_1 = require("path");
const exec = (0, util_1.promisify)(child_process_1.exec);
// Constants for command execution limits
const MAX_OUTPUT_SIZE = 4000; // Maximum characters to return from command output
function sanitizeNote(note) {
    // Remove newlines and comment terminators, and trim whitespace
    return note.replace(/[\r\n]+/g, ' ').replace(/\*\//g, '').trim();
}
async function applyEdits(workspaceRoot, files, note) {
    const safeNote = sanitizeNote(note);
    for (const rel of files) {
        const abs = (0, path_1.join)(workspaceRoot, rel);
        await (0, promises_1.mkdir)((0, path_1.dirname)(abs), { recursive: true });
        const old = await (0, promises_1.readFile)(abs).catch(() => Buffer.from(''));
        const next = old.toString('utf8') + `\n// AEP edit: ${safeNote}\n`;
        await (0, promises_1.writeFile)(abs, next, 'utf8');
    }
    return 'Applied MVP edits';
}
function isAllowedCommand(cmd) {
    // Strict whitelist of allowed commands for maximum security
    const allowedCommands = [
        /^git\s+(status|log|diff|show|branch|checkout|add|commit|push|pull|fetch)\b/, // specific git subcommands only (removed clone for security)
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
    if (cmd.match(/[;&|`$(){}><\\~*\[\]!]/)) {
        return false; // No shell metacharacters allowed
    }
    return allowedCommands.some((re) => re.test(cmd));
}
async function runCommand(workspaceRoot, cmd) {
    if (!isAllowedCommand(cmd)) {
        throw new Error(`Command not allowed: ${cmd}`);
    }
    // Additional security validations
    // Block dangerous privilege escalation and chmod patterns
    const dangerousChmod = /\bchmod\s+([0-7]{3,4}|\+[rwxstugo]+|\-[rwxstugo]+)/i;
    if (cmd.includes('sudo') ||
        /\bsu\b/.test(cmd) ||
        dangerousChmod.test(cmd)) {
        throw new Error('Privileged or unsafe permission-changing commands are not allowed');
    }
    if (cmd.includes('..') || cmd.includes('/etc/') || cmd.includes('/root/')) {
        throw new Error('Path traversal or system directory access not allowed');
    }
    // Strict environment with minimal safe variables
    const safeEnvVars = ['PATH', 'HOME', 'USER', 'LANG', 'PWD'];
    const sanitizedEnv = {};
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
        const { stdout, stderr } = await exec(cmd, {
            cwd: workspaceRoot,
            env: sanitizedEnv,
            encoding: 'utf8',
            timeout: 30000, // 30 second timeout
            maxBuffer: 5 * 1024 * 1024 // 5MB max buffer for legitimate command outputs
        });
        // Sanitize stderr to prevent sensitive information leakage
        const sanitizedStderr = stderr ? stderr.replace(/\/[^\s]+/g, '[PATH]') : '';
        const output = stdout + (sanitizedStderr ? '\n[STDERR]: ' + sanitizedStderr : '');
        return output.slice(-MAX_OUTPUT_SIZE);
    }
    catch (error) {
        // Sanitize error messages to prevent information leakage
        const sanitizedMessage = error.message?.replace(/\/[^\s]+/g, '[PATH]') || 'Command execution failed';
        throw new Error(`Command failed: ${sanitizedMessage}`);
    }
}
