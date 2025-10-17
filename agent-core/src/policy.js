"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkPolicy = checkPolicy;
const promises_1 = require("fs/promises");
const path_1 = require("path");
/**
 * Matches a path against a glob pattern.
 *
 * Supported glob syntax:
 * - `*` matches any sequence of characters within a single path segment (does not cross `/`).
 * - `**` matches any sequence of characters across multiple path segments (can cross `/`).
 * - `?` matches any single character within a path segment (does not match `/`).
 *
 * @param pattern The glob pattern to match, supporting `*`, `**`, and `?`.
 * @param path The path string to test against the pattern.
 * @returns `true` if the path matches the pattern, `false` otherwise.
 */
function matchGlobPattern(pattern, path) {
    // Convert glob pattern to regex safely with explicit escaping
    // ** matches any number of directories
    // * matches any characters within a directory segment
    // ? matches any single character
    // Single-pass conversion using replace with callback for maximum performance
    const regexPattern = pattern.replace(/([.+^${}()|[\]\\])|(\*\*)|(\*)|(\?)/g, (match, esc, dblStar, star, q) => {
        if (esc)
            return '\\' + esc; // Escape regex metacharacters
        if (dblStar)
            return '.*'; // ** => .*
        if (star)
            return '[^/]*'; // * => [^/]*
        if (q)
            return '[^/]'; // ? => [^/]
        return match;
    });
    const regex = new RegExp(`^${regexPattern}$`);
    return regex.test(path);
}
async function checkPolicy(workspaceRoot, step, policyFile = '.aepolicy.json') {
    if (!workspaceRoot)
        return false;
    const path = (0, path_1.join)(workspaceRoot, policyFile);
    let doc;
    try {
        doc = JSON.parse((await (0, promises_1.readFile)(path)).toString('utf8'));
    }
    catch (err) {
        console.error(`Failed to load or parse policy file at ${path}:`, err);
        return false; // Deny by default if policy cannot be loaded
    }
    if (step.command) {
        if (doc.deny?.commands?.some(d => step.command.startsWith(d)))
            return false;
        if (doc.allow?.commands && !doc.allow.commands.some(a => step.command.startsWith(a)))
            return false;
    }
    if (step.files?.length && doc.allow?.paths?.length) {
        const ok = step.files.every(f => doc.allow.paths.some(p => matchGlobPattern(p, f)));
        if (!ok)
            return false;
    }
    return true;
}
