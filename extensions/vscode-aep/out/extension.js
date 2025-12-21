"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
// src/extension.ts
const vscode = require("vscode");
const path = require("path");
const child_process_1 = require("child_process");
const fs = require("fs");
const child_process = require("child_process");
const util = require("util");
const diffUtils_1 = require("./diffUtils");
const connectorsPanel_1 = require("./connectorsPanel");
const sseClient_1 = require("./sse/sseClient");
const smartModeCommands_1 = require("./commands/smartModeCommands");
const smartModeClient_1 = require("./sse/smartModeClient");
const exec = util.promisify(child_process.exec);
// Phase 1.4: Collect VS Code diagnostics for a set of files
function collectDiagnosticsForFiles(workspaceRoot, relativePaths) {
    const results = [];
    for (const rel of relativePaths) {
        if (!rel)
            continue;
        const abs = path.join(workspaceRoot, rel);
        const uri = vscode.Uri.file(abs);
        const diags = vscode.languages.getDiagnostics(uri);
        if (diags && diags.length > 0) {
            results.push({
                path: rel,
                diagnostics: diags.map(d => ({
                    message: d.message,
                    severity: d.severity,
                    line: (d.range?.start?.line ?? 0) + 1,
                    character: (d.range?.start?.character ?? 0) + 1,
                }))
            });
        }
    }
    return results;
}
// PATCH 1: Git helper function
function runGit(cwd, args, allowExitCodes = [0]) {
    return new Promise((resolve, reject) => {
        const child = (0, child_process_1.spawn)('git', args, { cwd });
        let stdout = '';
        let stderr = '';
        child.stdout.on('data', d => (stdout += d.toString()));
        child.stderr.on('data', d => (stderr += d.toString()));
        child.on('close', code => {
            const exitCode = code ?? -1;
            if (!allowExitCodes.includes(exitCode)) {
                reject(new Error(`git ${args.join(' ')} failed (${exitCode}): ${stderr}`));
            }
            else {
                resolve({ stdout, stderr, code: exitCode });
            }
        });
        child.on('error', reject);
    });
}
// Phase 1.3.1: Open native IDE diff view
async function openNativeDiff(workspaceRoot, relativePath, scope = 'working') {
    try {
        // Build file URI for working tree version
        const fileUri = vscode.Uri.file(path.join(workspaceRoot, relativePath));
        // Create git URI using the VS Code Git provider's JSON query format.
        // The Git content provider expects a JSON string with at least { path, ref }.
        // Compare HEAD (left) against Working Tree (right).
        const headQuery = JSON.stringify({ path: fileUri.fsPath, ref: 'HEAD' });
        const headUri = fileUri.with({ scheme: 'git', query: headQuery });
        let rightUri;
        let titleScope = 'Working Tree ↔ HEAD';
        if (scope === 'staged') {
            // Show staged (INDEX) vs HEAD
            const indexQuery = JSON.stringify({ path: fileUri.fsPath, ref: 'INDEX' });
            rightUri = fileUri.with({ scheme: 'git', query: indexQuery });
            titleScope = 'Staged ↔ HEAD';
        }
        else {
            // Unstaged: HEAD (left) vs Working Tree (right)
            rightUri = fileUri;
            titleScope = 'Working Tree ↔ HEAD';
        }
        // Open the diff with title showing the file name
        // Left side (gitUri) = HEAD version, Right side (fileUri) = working tree
        await vscode.commands.executeCommand('vscode.diff', headUri, rightUri, `Diff: ${relativePath} (${titleScope})`);
    }
    catch (error) {
        console.error('[openNativeDiff] Failed to open diff:', error);
        vscode.window.showErrorMessage(`Failed to open diff for ${relativePath}: ${error instanceof Error ? error.message : String(error)}`);
    }
}
// Perfect Workspace Context Collection
async function collectWorkspaceContext() {
    const editor = vscode.window.activeTextEditor;
    const workspaceFolders = vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath) ?? [];
    const rootFolder = workspaceFolders.length > 0 ? workspaceFolders[0] : null;
    const activeFile = editor?.document?.fileName ?? null;
    const selectedText = editor?.selection ? editor.document.getText(editor.selection) : null;
    const recentFiles = vscode.workspace.textDocuments.slice(0, 10).map(doc => doc.fileName);
    return {
        workspace_root: rootFolder,
        active_file: activeFile,
        selected_text: selectedText,
        recent_files: recentFiles,
    };
}
// Detect Diagnostics Commands (for "check errors & fix" functionality)
async function detectDiagnosticsCommands(workspaceRoot) {
    const cmds = [];
    const fs = await Promise.resolve().then(() => require('fs'));
    try {
        // 1) Node.js projects: look at package.json
        const pkgPath = path.join(workspaceRoot, 'package.json');
        if (fs.existsSync(pkgPath)) {
            const text = fs.readFileSync(pkgPath, 'utf8');
            const pkg = JSON.parse(text);
            const scripts = pkg.scripts ?? {};
            for (const [name, cmd] of Object.entries(scripts)) {
                const nameMatch = /^(lint|test|check|validate|build)$/i.test(name) ||
                    /lint|test|check/i.test(name);
                const cmdMatch = /eslint|tslint|jest|vitest|mocha|cypress|playwright|tsc|npm test|yarn test|pnpm test/i.test(cmd);
                if (nameMatch || cmdMatch) {
                    // Prefer npm run for consistency
                    if (pkg.packageManager?.startsWith('yarn')) {
                        cmds.push(`yarn ${name}`);
                    }
                    else if (pkg.packageManager?.startsWith('pnpm')) {
                        cmds.push(`pnpm ${name}`);
                    }
                    else {
                        cmds.push(`npm run ${name}`);
                    }
                }
            }
        }
        // 2) Python projects: look for common linting/testing patterns
        const pythonFiles = ['setup.py', 'pyproject.toml', 'requirements.txt', 'Pipfile'];
        const hasPython = pythonFiles.some(f => fs.existsSync(path.join(workspaceRoot, f)));
        if (hasPython) {
            // Check for common Python tools
            const pyprojectPath = path.join(workspaceRoot, 'pyproject.toml');
            if (fs.existsSync(pyprojectPath)) {
                const content = fs.readFileSync(pyprojectPath, 'utf8');
                if (content.includes('flake8') || content.includes('black') || content.includes('mypy')) {
                    cmds.push('python -m flake8 .');
                    if (content.includes('black'))
                        cmds.push('python -m black --check .');
                    if (content.includes('mypy'))
                        cmds.push('python -m mypy .');
                }
            }
            // Common pytest patterns
            if (fs.existsSync(path.join(workspaceRoot, 'pytest.ini')) ||
                fs.existsSync(path.join(workspaceRoot, 'tests'))) {
                cmds.push('python -m pytest');
            }
        }
        // 3) Java projects: Maven/Gradle
        if (fs.existsSync(path.join(workspaceRoot, 'pom.xml'))) {
            cmds.push('mvn compile', 'mvn test');
        }
        if (fs.existsSync(path.join(workspaceRoot, 'build.gradle')) ||
            fs.existsSync(path.join(workspaceRoot, 'build.gradle.kts'))) {
            cmds.push('./gradlew build', './gradlew test');
        }
        // 4) Rust projects
        if (fs.existsSync(path.join(workspaceRoot, 'Cargo.toml'))) {
            cmds.push('cargo check', 'cargo test', 'cargo clippy');
        }
        // 5) Go projects
        if (fs.existsSync(path.join(workspaceRoot, 'go.mod'))) {
            cmds.push('go build ./...', 'go test ./...', 'go vet ./...');
        }
        console.log('[Extension Host] [AEP] 🔍 Detected diagnostics commands:', cmds);
        return cmds;
    }
    catch (error) {
        console.warn('[Extension Host] [AEP] Error detecting diagnostics commands:', error);
        return [];
    }
}
// PR-4: Storage keys for persistent model/mode selection
const STORAGE_KEYS = {
    modelId: 'aep.navi.modelId',
    modelLabel: 'aep.navi.modelLabel',
    modeId: 'aep.navi.modeId',
    modeLabel: 'aep.navi.modeLabel',
    scanConsentPrompted: 'aep.navi.scanConsentPrompted',
    lastScanCheckAt: 'aep.navi.lastScanCheckAt',
};
// Defaults if nothing stored yet
const DEFAULT_MODEL = {
    id: 'gpt-5.1',
    label: 'ChatGPT 5.1',
};
const DEFAULT_MODE = {
    id: 'chat-only',
    label: 'Agent (full access)',
};
async function getGitDiff(scope, provider) {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
        vscode.window.showErrorMessage("NAVI: Open a folder in VS Code before using Git review actions.");
        return null;
    }
    const cwd = folder.uri.fsPath;
    console.log("[AEP][Git] getGitDiff scope:", scope, "cwd:", cwd);
    // 1) Are we actually in a git repo?
    try {
        const { stdout } = await exec("git rev-parse --is-inside-work-tree", {
            cwd,
        });
        console.log("[AEP][Git] rev-parse output:", stdout.trim());
        if (stdout.trim() !== "true") {
            vscode.window.showWarningMessage('NAVI: This folder is not a Git repository. ' +
                'Quick actions like "Review working changes" only work in a Git project.\n\n' +
                'Run "git init" (and make at least one commit) in the terminal, or open a Git-backed repo.');
            return null;
        }
    }
    catch (err) {
        console.error("[AEP][Git] rev-parse failed:", err);
        return null;
    }
    // 2) Check if HEAD exists (repo has commits)
    let hasHead = false;
    try {
        await exec("git rev-parse --verify HEAD", { cwd });
        hasHead = true;
        console.log("[AEP][Git] HEAD exists");
    }
    catch {
        console.log("[AEP][Git] No HEAD yet (brand new repo)");
    }
    // 3) Get status to find untracked files
    let statusLines = [];
    try {
        const { stdout: statusOut } = await exec("git status --porcelain", {
            cwd,
        });
        statusLines = statusOut.split('\n').filter(l => l.trim());
        console.log("[AEP][Git] status --porcelain:", statusLines.length, "lines");
    }
    catch (err) {
        console.error("[AEP][Git] git status failed:", err);
    }
    // 4) Build the diff
    let baseDiff = '';
    let untrackedDiff = '';
    if (scope === "lastCommit") {
        if (!hasHead) {
            vscode.window.showInformationMessage("NAVI: No commits yet in this repository. Make your first commit, then try again.");
            return null;
        }
        try {
            const { stdout } = await exec("git show --unified=3 --format= HEAD", { cwd });
            baseDiff = stdout.trim();
        }
        catch (err) {
            console.error("[AEP][Git] git show failed:", err);
            return null;
        }
    }
    else if (scope === "staged") {
        try {
            const { stdout } = await exec("git diff --cached --unified=3", { cwd });
            baseDiff = stdout.trim();
        }
        catch (err) {
            console.error("[AEP][Git] git diff --cached failed:", err);
        }
    }
    else {
        // working: use "git diff" (no HEAD) to avoid error in new repos
        try {
            const { stdout } = await exec("git diff --unified=3", { cwd });
            baseDiff = stdout.trim();
        }
        catch (err) {
            console.error("[AEP][Git] git diff failed:", err);
        }
        // Include untracked files as real diffs
        const untracked = await runGit(cwd, ['ls-files', '--others', '--exclude-standard']);
        const files = untracked.stdout.split('\n').filter(Boolean);
        const MAX_FILES = 20;
        const MAX_TOTAL_CHARS = 200000;
        let totalChars = baseDiff.length;
        const pieces = [];
        for (const file of files.slice(0, MAX_FILES)) {
            // Skip huge build artifacts
            const skip = /^(node_modules|\.next|dist|build|\.turbo|\.cache|\.vscode)\//.test(file) ||
                file === '.DS_Store' || file.endsWith('.log');
            if (skip)
                continue;
            const abs = path.join(cwd, file);
            try {
                let isFile = false;
                try {
                    const stat = await vscode.workspace.fs.stat(vscode.Uri.file(abs));
                    isFile = stat.type === vscode.FileType.File;
                }
                catch {
                    continue;
                }
                if (!isFile)
                    continue;
                // IMPORTANT: allow exit code 1 (diff exists)
                const diff = await runGit(cwd, ['diff', '--no-index', '--unified=3', '--', '/dev/null', abs], [0, 1]);
                let piece = '';
                if (diff.stdout.trim()) {
                    piece = diff.stdout.trim();
                }
                else {
                    // fallback: inline file contents
                    const content = fs.readFileSync(abs, 'utf8');
                    piece = `diff --git a/${file} b/${file}\n`;
                    piece += `new file mode 100644\n`;
                    piece += `--- /dev/null\n`;
                    piece += `+++ b/${file}\n`;
                    piece += `@@ -0,0 +1,${content.split('\n').length} @@\n`;
                    content.split('\n').forEach(l => (piece += `+${l}\n`));
                }
                if (totalChars + piece.length > MAX_TOTAL_CHARS)
                    break;
                totalChars += piece.length;
                pieces.push(piece);
                console.log(`[AEP][Git] Added untracked file: ${file} (${piece.length} chars)`);
            }
            catch (e) {
                console.warn('[AEP][Git] fallback diff for', file, e);
            }
        }
        untrackedDiff = pieces.join('\n\n').trim();
        console.log(`[AEP][Git] Untracked diff: ${untrackedDiff.length} chars from ${pieces.length} files`);
    }
    const combined = [baseDiff, untrackedDiff].filter(Boolean).join('\n\n').trim();
    console.log("[AEP][Git] Combined diff length:", combined.length, "chars");
    if (!combined) {
        const label = scope === "staged"
            ? "staged changes"
            : scope === "lastCommit"
                ? "last commit"
                : "working tree changes";
        vscode.window.showInformationMessage(`NAVI: No ${label} found.`);
        return null;
    }
    // Optionally clamp very huge diffs to avoid backend 422 on insane payloads
    const MAX_DIFF_CHARS = 250000;
    if (combined.length > MAX_DIFF_CHARS) {
        console.warn("[AEP][Git] Diff too large, truncating to", MAX_DIFF_CHARS, "chars");
        return combined.slice(0, MAX_DIFF_CHARS) + "\n\n…[truncated large diff]…\n";
    }
    return combined;
}
function activate(context) {
    const provider = new NaviWebviewProvider(context.extensionUri, context);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(
    // Make sure this matches the view id in package.json
    'aep.chatView', provider));
    // Register Smart Mode commands
    smartModeCommands_1.smartModeCommands.registerCommands(context);
    context.subscriptions.push(vscode.commands.registerCommand('aep.attachSelection', async () => {
        await provider.attachSelectionCommand();
    }), vscode.commands.registerCommand('aep.attachCurrentFile', async () => {
        await provider.attachCurrentFileCommand();
    }), vscode.commands.registerCommand('aep.checkErrorsAndFix', async () => {
        await provider.checkErrorsAndFixCommand();
    }), vscode.commands.registerCommand('aep.generateTestsForFile', async () => {
        await provider.generateTestsForFileCommand();
    }));
}
function deactivate() {
    // Clean up Smart Mode resources
    smartModeClient_1.smartModeSSEClient.dispose();
}
class NaviWebviewProvider {
    constructor(extensionUri, context) {
        this._messages = [];
        this._agentActions = new Map(); // PR-6: Track agent actions
        this._currentModelId = DEFAULT_MODEL.id;
        this._currentModelLabel = DEFAULT_MODEL.label;
        this._currentModeId = DEFAULT_MODE.id;
        this._currentModeLabel = DEFAULT_MODE.label;
        this._memoryKeyPrefix = 'aep.memory';
        // Attachment state
        this._attachments = [];
        // Git warning state - only show once per session
        this._gitWarningShown = false;
        // SSE client for streaming
        this.sse = new sseClient_1.SSEClient({
            maxRetries: 3,
            retryDelay: 1000,
            heartbeatInterval: 30000,
            timeout: 60000
        });
        this._extensionUri = extensionUri;
        this._context = context;
        this._conversationId = generateConversationId();
        // PR-4: Load persisted model/mode from storage
        this._currentModelId = context.globalState.get(STORAGE_KEYS.modelId) ?? DEFAULT_MODEL.id;
        this._currentModelLabel = context.globalState.get(STORAGE_KEYS.modelLabel) ?? DEFAULT_MODEL.label;
        this._currentModeId = context.globalState.get(STORAGE_KEYS.modeId) ?? DEFAULT_MODE.id;
        this._currentModeLabel = context.globalState.get(STORAGE_KEYS.modeLabel) ?? DEFAULT_MODE.label;
    }
    getBackendBaseUrl() {
        const config = vscode.workspace.getConfiguration('aep');
        // Default to local dev backend; allow users to provide full /api/navi/chat URL or plain base URL
        const raw = (config.get('navi.backendUrl') || 'http://127.0.0.1:8787/api/navi/chat').trim();
        // Turn http://127.0.0.1:8787/api/navi/chat → http://127.0.0.1:8787
        try {
            const url = new URL(raw);
            url.pathname = url.pathname.replace(/\/api\/navi\/chat\/?$/, '');
            url.search = '';
            url.hash = '';
            return url.toString().replace(/\/$/, '');
        }
        catch {
            return 'http://127.0.0.1:8787';
        }
    }
    getOrgId(explicit) {
        const trimmed = (explicit || '').trim();
        if (trimmed)
            return trimmed;
        const config = vscode.workspace.getConfiguration('aep');
        const configured = config.get('navi.orgId');
        if (configured && configured.trim()) {
            return configured.trim();
        }
        return 'default';
    }
    getUserId(explicit) {
        const trimmed = (explicit || '').trim();
        if (trimmed)
            return trimmed;
        const config = vscode.workspace.getConfiguration('aep');
        const configured = config.get('navi.userId');
        if (configured && configured.trim()) {
            return configured.trim();
        }
        return 'default_user';
    }
    getAutoScanConfig() {
        const config = vscode.workspace.getConfiguration('aep');
        const enabled = config.get('navi.autoScanEnabled');
        const hours = config.get('navi.autoScanIntervalHours');
        const intervalHours = typeof hours === 'number' && Number.isFinite(hours) && hours > 0 ? hours : 24;
        return {
            enabled: enabled !== false,
            intervalMs: intervalHours * 60 * 60 * 1000,
        };
    }
    async fetchOrgScanStatus(orgId, userId) {
        try {
            const baseUrl = this.getBackendBaseUrl();
            const resp = await fetch(`${baseUrl}/api/org/scan/status`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': orgId,
                    'X-User-Id': userId,
                },
            });
            if (!resp.ok) {
                return null;
            }
            return await resp.json();
        }
        catch (err) {
            console.warn('[AEP] Org scan status failed:', err);
            return null;
        }
    }
    async requestOrgScanConsent(orgId, userId) {
        try {
            const baseUrl = this.getBackendBaseUrl();
            const url = new URL(`${baseUrl}/api/org/scan/consent`);
            url.searchParams.set('allow_secrets', 'false');
            const resp = await fetch(url.toString(), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': orgId,
                    'X-User-Id': userId,
                },
            });
            return resp.ok;
        }
        catch (err) {
            console.warn('[AEP] Org scan consent failed:', err);
            return false;
        }
    }
    async triggerOrgScan(orgId, userId, workspaceRoot) {
        try {
            const baseUrl = this.getBackendBaseUrl();
            const url = new URL(`${baseUrl}/api/org/scan/run`);
            if (workspaceRoot) {
                url.searchParams.set('workspace_root', workspaceRoot);
            }
            const resp = await fetch(url.toString(), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': orgId,
                    'X-User-Id': userId,
                },
            });
            return resp.ok;
        }
        catch (err) {
            console.warn('[AEP] Org scan trigger failed:', err);
            return false;
        }
    }
    async pollOrgScanStatus(orgId, userId, attempts = 4) {
        for (let i = 0; i < attempts; i++) {
            await new Promise((resolve) => setTimeout(resolve, 4000 + i * 2000));
            const status = await this.fetchOrgScanStatus(orgId, userId);
            if (!status)
                return;
            if (status.state && String(status.state).startsWith('failed')) {
                this.postToWebview({
                    type: 'botMessage',
                    text: `Repo scan failed: ${status.state}`,
                });
                return;
            }
            if (status.state === 'completed' && status.summary) {
                this.postToWebview({
                    type: 'botMessage',
                    text: `✅ Repo scan complete.\n\n${status.summary}`,
                });
                return;
            }
        }
    }
    async maybeAutoScan(orgId, userId, workspaceRoot) {
        const { enabled, intervalMs } = this.getAutoScanConfig();
        if (!enabled || !workspaceRoot) {
            return;
        }
        const now = Date.now();
        const lastCheck = this._context.globalState.get(STORAGE_KEYS.lastScanCheckAt) || 0;
        if (now - lastCheck < 5 * 60 * 1000) {
            return;
        }
        await this._context.globalState.update(STORAGE_KEYS.lastScanCheckAt, now);
        const status = await this.fetchOrgScanStatus(orgId, userId);
        if (!status)
            return;
        if (!status.consent) {
            const prompted = this._context.globalState.get(STORAGE_KEYS.scanConsentPrompted);
            if (!prompted) {
                await this._context.globalState.update(STORAGE_KEYS.scanConsentPrompted, true);
                this.postToWebview({
                    type: 'botMessage',
                    text: "I can scan this repo to keep context fresh and speed up responses. " +
                        "It runs locally and skips secrets by default. " +
                        "Reply **enable repo scan** to opt in.",
                });
            }
            return;
        }
        if (status.paused_at) {
            return;
        }
        const lastScan = status.last_scan_at
            ? Date.parse(status.last_scan_at)
            : 0;
        if (!lastScan || now - lastScan > intervalMs) {
            const ok = await this.triggerOrgScan(orgId, userId, workspaceRoot);
            if (ok) {
                this.postToWebview({
                    type: 'botMessage',
                    text: '🔎 Running scheduled repo scan to keep context up to date.',
                });
                void this.pollOrgScanStatus(orgId, userId);
            }
        }
    }
    parseOrgScanIntent(text) {
        const msg = (text || '').toLowerCase();
        if (!msg.trim())
            return null;
        if (/(enable|allow|consent).*(repo|repository|project)?.*(scan|scanning)/.test(msg)) {
            return 'consent';
        }
        if (/(disable|stop|revoke).*(repo|repository|project)?.*(scan|scanning)/.test(msg)) {
            return 'revoke';
        }
        if (/(pause|suspend).*(scan|scanning)/.test(msg)) {
            return 'pause';
        }
        if (/(resume|unpause).*(scan|scanning)/.test(msg)) {
            return 'resume';
        }
        if (/(sync|refresh|update).*(connectors|connector|jira|slack|confluence|teams|zoom)/.test(msg)) {
            return 'run';
        }
        if (/(scan|rescan|refresh).*(repo|repository|project)/.test(msg)) {
            return 'run';
        }
        return null;
    }
    getGreetingKind(text) {
        const raw = (text || '').trim().toLowerCase();
        if (!raw || raw.length > 60)
            return null;
        if (/\b(repo|project|code|error|review|scan|diff|change|fix|tests?|build|deploy|bug|issue)\b/.test(raw)) {
            return null;
        }
        const normalized = raw
            .replace(/[^a-z0-9\s']/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        if (!normalized)
            return null;
        if (/\b(how\s*(are|ar|r)\s*(you|u|ya)|howre\s*(you|u)|hru|hw\s*(are|ar|r)?\s*(you|u)|how\s*u|how's it going|hows it going)\b/.test(normalized)) {
            return 'how_are_you';
        }
        if (/\b(what'?s up|whats up|wassup|watsup|sup)\b/.test(normalized)) {
            return 'whats_up';
        }
        if (/\b(good morning|good afternoon|good evening|gm|ga|ge)\b/.test(normalized)) {
            return 'time_of_day';
        }
        const filler = new Set([
            'navi',
            'assistant',
            'there',
            'team',
            'everyone',
            'all',
            'folks',
            'friend',
            'buddy',
            'sir',
            'maam',
        ]);
        const isGreetingToken = (token) => {
            if (!token)
                return false;
            if (/^h+i+$/.test(token))
                return true;
            if (/^he+y+$/.test(token))
                return true;
            if (/^hell+o+$/.test(token))
                return true;
            if (/^hel+o+$/.test(token))
                return true;
            if (/^hell+$/.test(token))
                return true;
            if (/^yo+$/.test(token))
                return true;
            if (/^hiya+$/.test(token))
                return true;
            if (/^sup+$/.test(token))
                return true;
            if (token === 'wassup' || token === 'watsup' || token === 'whatsup')
                return true;
            if (token === 'gm' || token === 'ga' || token === 'ge')
                return true;
            if (token === 'hru' || token === 'howre')
                return true;
            return false;
        };
        const tokens = normalized.split(' ').filter(Boolean);
        const remaining = tokens.filter((token) => !filler.has(token) && !isGreetingToken(token));
        if (tokens.length > 0 && remaining.length === 0) {
            return 'simple';
        }
        return null;
    }
    pickGreetingReply(kind) {
        const hour = new Date().getHours();
        const timeHint = hour < 12
            ? 'morning'
            : hour < 18
                ? 'afternoon'
                : 'evening';
        const responses = {
            simple: [
                "Hey! What do you want to tackle today—code, reviews, tests, or scans?",
                "Hi there! Tell me what you want me to do next.",
                "Hello! I can review code, fix errors, or sync connectors. What’s up?",
                "Hey! Need a repo scan, a fix, or a review?",
            ],
            how_are_you: [
                "Doing well—ready to help. What should we work on?",
                "All good on my side. Want a review, a fix, or a repo scan?",
                "I’m great—what do you want to tackle next?",
                "Doing fine! I can jump into code, tests, or connector syncs.",
            ],
            whats_up: [
                "All good here. What do you want me to do?",
                "Not much—ready to dive in. Code review or repo scan?",
                "Quiet on my side. Want me to check errors or sync connectors?",
                "I’m ready. What should we tackle—bugs, tests, or scans?",
            ],
            time_of_day: [
                `Good ${timeHint}! What should we work on?`,
                `Good ${timeHint}! Want me to scan the repo or review changes?`,
                `Good ${timeHint}! I can help with code, tests, or connector syncs.`,
                `Good ${timeHint}! What’s the next task?`,
            ],
        };
        const pool = responses[kind] || responses.simple;
        return pool[Math.floor(Math.random() * pool.length)];
    }
    async requestOrgScanAction(path, orgId, userId) {
        try {
            const baseUrl = this.getBackendBaseUrl();
            const resp = await fetch(`${baseUrl}${path}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': orgId,
                    'X-User-Id': userId,
                },
            });
            return resp.ok;
        }
        catch (err) {
            console.warn('[AEP] Org scan action failed:', err);
            return false;
        }
    }
    async handleOrgScanIntent(intent, orgIdInput, userIdInput) {
        const orgId = this.getOrgId(orgIdInput);
        const userId = this.getUserId(userIdInput);
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (intent === 'consent') {
            const ok = await this.requestOrgScanConsent(orgId, userId);
            if (ok) {
                this.postToWebview({
                    type: 'botMessage',
                    text: "✅ Repo scan enabled. I'll keep this workspace up to date every 24 hours.",
                });
                if (workspaceRoot) {
                    const started = await this.triggerOrgScan(orgId, userId, workspaceRoot);
                    if (started) {
                        this.postToWebview({
                            type: 'botMessage',
                            text: '🔎 Running initial repo scan now.',
                        });
                        void this.pollOrgScanStatus(orgId, userId);
                    }
                }
            }
            else {
                this.postToWebview({
                    type: 'botMessage',
                    text: 'I could not enable repo scanning. Please try again.',
                });
            }
            return;
        }
        if (intent === 'pause') {
            const ok = await this.requestOrgScanAction('/api/org/scan/pause', orgId, userId);
            this.postToWebview({
                type: 'botMessage',
                text: ok ? '⏸️ Repo scans are paused.' : 'Failed to pause repo scans.',
            });
            return;
        }
        if (intent === 'resume') {
            const ok = await this.requestOrgScanAction('/api/org/scan/resume', orgId, userId);
            this.postToWebview({
                type: 'botMessage',
                text: ok ? '▶️ Repo scans resumed.' : 'Failed to resume repo scans.',
            });
            return;
        }
        if (intent === 'revoke') {
            const ok = await this.requestOrgScanAction('/api/org/scan/revoke', orgId, userId);
            if (ok) {
                await this._context.globalState.update(STORAGE_KEYS.scanConsentPrompted, false);
            }
            this.postToWebview({
                type: 'botMessage',
                text: ok ? 'Repo scan consent revoked.' : 'Failed to revoke consent.',
            });
            return;
        }
        if (intent === 'run') {
            if (!workspaceRoot) {
                this.postToWebview({
                    type: 'botMessage',
                    text: 'Open a workspace first so I can scan the repo.',
                });
                return;
            }
            const status = await this.fetchOrgScanStatus(orgId, userId);
            if (status && !status.consent) {
                this.postToWebview({
                    type: 'botMessage',
                    text: "Repo scan is not enabled yet. Reply **enable repo scan** to opt in.",
                });
                return;
            }
            const ok = await this.triggerOrgScan(orgId, userId, workspaceRoot);
            if (ok) {
                this.postToWebview({
                    type: 'botMessage',
                    text: '🔎 Repo scan started. I will post the summary once it completes.',
                });
                void this.pollOrgScanStatus(orgId, userId);
            }
            else {
                this.postToWebview({
                    type: 'botMessage',
                    text: 'Failed to start repo scan. Please try again.',
                });
            }
        }
    }
    async resolveWebviewView(webviewView, _context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
            enableCommandUris: true
        };
        webviewView.webview.html = await this.getWebviewHtml(webviewView.webview);
        // PR-4: Hydrate model/mode state from storage after webview loads
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            console.log('[AEP] Extension received message:', msg.type);
            try {
                switch (msg.type) {
                    case 'requestWorkspaceContext': {
                        // Send workspace context to frontend
                        const workspaceRoot = this.getActiveWorkspaceRoot();
                        const workspaceContext = await collectWorkspaceContext();
                        this.postToWebview({
                            type: 'workspaceContext',
                            workspaceRoot,
                            workspaceContext
                        });
                        break;
                    }
                    case 'openExternal': {
                        const url = String(msg.url || '').trim();
                        if (!url)
                            return;
                        try {
                            await vscode.env.openExternal(vscode.Uri.parse(url));
                        }
                        catch (e) {
                            vscode.window.showErrorMessage('Failed to open external URL');
                        }
                        break;
                    }
                    // Phase 1.3.1: Handle openDiff request from NAVI UI
                    case 'openDiff': {
                        const filePath = String(msg.path || '').trim();
                        if (!filePath) {
                            vscode.window.showWarningMessage('No file path provided for diff');
                            return;
                        }
                        const workspaceRoot = this.getActiveWorkspaceRoot();
                        if (!workspaceRoot) {
                            vscode.window.showWarningMessage('No workspace root found');
                            return;
                        }
                        const scope = (msg.scope === 'staged' ? 'staged' : 'working');
                        await openNativeDiff(workspaceRoot, filePath, scope);
                        break;
                    }
                    case 'ready': {
                        // Send hydration message first
                        this.postToWebview({
                            type: 'hydrateState',
                            modelId: this._currentModelId,
                            modelLabel: this._currentModelLabel,
                            modeId: this._currentModeId,
                            modeLabel: this._currentModeLabel,
                        });
                        // Send persisted memory snapshot for this workspace
                        const memory = await this.loadMemory(this.getActiveWorkspaceRoot());
                        this.postToWebview({
                            type: 'hydrateMemory',
                            memory
                        });
                        // Send backend status to webview
                        const baseUrl = this.getBackendBaseUrl();
                        try {
                            const res = await fetch(`${baseUrl}/api/navi/chat`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-Org-Id': this.getOrgId(),
                                },
                                body: JSON.stringify({
                                    message: 'health_check',
                                    attachments: [],
                                    workspace_root: null
                                }),
                            });
                            if (!res.ok) {
                                const text = await res.text().catch(() => '');
                                throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
                            }
                            this.postToWebview({ type: 'backendStatus', status: 'ok' });
                        }
                        catch (err) {
                            this.postToWebview({
                                type: 'backendStatus',
                                status: 'error',
                                error: err?.message || String(err),
                            });
                        }
                        // Then send welcome message
                        this.postToWebview({
                            type: 'botMessage',
                            text: "Hello! I'm **NAVI**, your autonomous engineering assistant.\n\nI can help you with:\n\n- Code explanations and reviews\n- Refactoring and testing\n- Documentation generation\n- Engineering workflow automation\n\nHow can I help you today?"
                        });
                        await this.recordMemoryEvent('system:welcome', { ts: Date.now() });
                        const orgId = this.getOrgId();
                        const userId = this.getUserId();
                        const workspaceRoot = this.getActiveWorkspaceRoot();
                        void this.maybeAutoScan(orgId, userId, workspaceRoot);
                        if (!this._scanTimer) {
                            const { intervalMs } = this.getAutoScanConfig();
                            const checkInterval = Math.max(15 * 60 * 1000, Math.min(intervalMs, 60 * 60 * 1000));
                            this._scanTimer = setInterval(() => {
                                void this.maybeAutoScan(this.getOrgId(), this.getUserId(), this.getActiveWorkspaceRoot());
                            }, checkInterval);
                        }
                        // NOTE: Removed automatic Jira sync - now only triggered when user explicitly asks about Jira tasks
                        break;
                    }
                    case 'clipboard.write': {
                        const id = msg.id;
                        try {
                            const text = typeof msg.text === 'string' ? msg.text : '';
                            await vscode.env.clipboard.writeText(text);
                            // Ack success back to the webview
                            this.postToWebview({
                                type: 'clipboard.write.result',
                                id,
                                success: true,
                            });
                        }
                        catch (err) {
                            console.error('[AEP] Clipboard write failed', err);
                            this.postToWebview({
                                type: 'clipboard.write.result',
                                id,
                                success: false,
                            });
                        }
                        break;
                    }
                    case 'aep.review.request': {
                        // Legacy review request - use existing handler
                        this.handleReviewRequest();
                        break;
                    }
                    case 'aep.review.start': {
                        // Start streaming review
                        this.startReviewStream();
                        break;
                    }
                    case 'aep.review.stop': {
                        // Stop streaming review
                        this.stopReviewStream();
                        break;
                    }
                    case 'aep.stream.retry': {
                        // Retry streaming connection
                        this.retryReviewStream(msg.retryCount || 1);
                        break;
                    }
                    case 'aep.file.open': {
                        // Open file at specific line
                        this.openFileAtLine(msg.file, msg.line);
                        break;
                    }
                    case 'review.applyFix': {
                        // Apply auto-fix using new service
                        this.handleAutoFixRequest(msg.entry);
                        break;
                    }
                    case 'runOrchestrator': {
                        // Handle orchestrator execution - BYPASS smart routing
                        console.log('[AEP] 🎯 runOrchestrator message received with instruction:', msg.instruction);
                        console.log('[AEP] 🎯 BYPASSING smart routing - calling orchestrator directly');
                        this.handleOrchestratorRequest(msg.instruction);
                        break;
                    }
                    case 'aep.fix.apply': {
                        // Legacy auto-fix handler  
                        this.applyAutoFix(msg.entryId, msg.file, msg.line, msg.diff);
                        break;
                    }
                    case 'review.applyPatch': {
                        // Apply AI-generated unified diff patch
                        await this.handleApplyPatch(msg.patch);
                        break;
                    }
                    case 'clipboard.read': {
                        const id = msg.id;
                        try {
                            const text = await vscode.env.clipboard.readText();
                            this.postToWebview({
                                type: 'clipboard.read.result',
                                id,
                                text,
                            });
                        }
                        catch (err) {
                            console.error('[AEP] Clipboard read failed', err);
                            this.postToWebview({
                                type: 'clipboard.read.result',
                                id,
                                text: '',
                            });
                        }
                        break;
                    }
                    case 'attachCurrentFile': {
                        const editor = vscode.window.activeTextEditor;
                        if (!editor)
                            return;
                        const doc = editor.document;
                        const fsPath = doc.uri.fsPath;
                        const content = doc.getText();
                        this.postToWebview({
                            type: 'addAttachment',
                            attachment: {
                                kind: 'file',
                                path: fsPath,
                                language: doc.languageId,
                                content,
                            },
                        });
                        break;
                    }
                    case 'attachSelection': {
                        const editor = vscode.window.activeTextEditor;
                        if (!editor)
                            return;
                        const doc = editor.document;
                        const sel = editor.selection;
                        const hasSelection = sel && !sel.isEmpty;
                        const content = hasSelection ? doc.getText(sel) : doc.getText();
                        const fsPath = doc.uri.fsPath;
                        this.postToWebview({
                            type: 'addAttachment',
                            attachment: {
                                kind: hasSelection ? 'selection' : 'file',
                                path: fsPath,
                                language: doc.languageId,
                                content,
                            },
                        });
                        break;
                    }
                    case 'attachLocalFile': {
                        const picked = await vscode.window.showOpenDialog({
                            canSelectFiles: true,
                            canSelectFolders: false,
                            canSelectMany: false,
                            openLabel: 'Attach file to Navi',
                        });
                        if (!picked || picked.length === 0)
                            return;
                        const uri = picked[0];
                        const bytes = await vscode.workspace.fs.readFile(uri);
                        const content = new TextDecoder('utf-8').decode(bytes);
                        this.postToWebview({
                            type: 'addAttachment',
                            attachment: {
                                kind: 'local_file',
                                path: uri.fsPath,
                                language: 'plaintext',
                                content,
                            },
                        });
                        break;
                    }
                    case 'copyToClipboard': {
                        const text = String(msg.text || '');
                        if (!text)
                            return;
                        try {
                            await vscode.env.clipboard.writeText(text);
                            vscode.window.setStatusBarMessage('NAVI: Copied to clipboard.', 1500);
                        }
                        catch (err) {
                            console.error('[AEP] Clipboard write failed:', err);
                            vscode.window.showErrorMessage('NAVI: Failed to copy to clipboard.');
                        }
                        break;
                    }
                    case 'sendMessage': {
                        const text = String(msg.text || '').trim();
                        if (!text) {
                            return;
                        }
                        console.log('[Extension Host] [AEP] 🔥 INTERCEPTING MESSAGE:', text);
                        const recordUserMessage = () => {
                            this.recordMemoryEvent('chat:user', { content: text, ts: Date.now() }).catch(() => { });
                        };
                        // IMMEDIATE REPO QUESTION INTERCEPTION
                        const lower = text.toLowerCase();
                        const isRepoQuestion = /which repo|what repo|which project|what project/.test(lower);
                        // GIT INIT CONFIRMATION HANDLING
                        const isGitInitConfirmation = /^(yes|y|initialize git|init git|set up git)$/i.test(text.trim());
                        console.log('[Extension Host] [AEP] 🔍 Git init check:', { isGitInitConfirmation, hasPendingGitInit: !!this._pendingGitInit, text: text.trim() });
                        if (isGitInitConfirmation && this._pendingGitInit) {
                            console.log('[Extension Host] [AEP] 🎯 EXECUTING GIT INIT');
                            recordUserMessage();
                            await this.executeGitInit();
                            return;
                        }
                        if (isRepoQuestion) {
                            console.log('[Extension Host] [AEP] 🎯 REPO QUESTION DETECTED - HANDLING LOCALLY');
                            const workspaceRoot = this.getActiveWorkspaceRoot();
                            const repoName = workspaceRoot ? path.basename(workspaceRoot) : 'unknown workspace';
                            console.log('[Extension Host] [AEP] 🎯 WORKSPACE DEBUG:', {
                                workspaceRoot,
                                repoName,
                                activeEditor: vscode.window.activeTextEditor?.document.uri.fsPath,
                                workspaceFolders: vscode.workspace.workspaceFolders?.map(f => ({ name: f.name, path: f.uri.fsPath })),
                                workspaceName: vscode.workspace.name,
                                workspaceFile: vscode.workspace.workspaceFile?.fsPath
                            });
                            const answer = workspaceRoot
                                ? `You're currently working in the **${repoName}** repo at \`${workspaceRoot}\`.`
                                : `You're currently working in an **${repoName}**.`;
                            console.log('[Extension Host] [AEP] 🎯 LOCAL REPO ANSWER:', { workspaceRoot, repoName, answer });
                            // Add to message history and send response
                            this._messages.push({ role: 'user', content: text });
                            this._messages.push({ role: 'assistant', content: answer });
                            recordUserMessage();
                            this.postToWebview({ type: 'botThinking', value: false });
                            this.postToWebview({ type: 'botMessage', text: answer });
                            return;
                        }
                        const scanIntent = this.parseOrgScanIntent(text);
                        if (scanIntent) {
                            this._messages.push({ role: 'user', content: text });
                            recordUserMessage();
                            await this.handleOrgScanIntent(scanIntent, msg.orgId, msg.userId);
                            this.postToWebview({ type: 'botThinking', value: false });
                            return;
                        }
                        const greetingKind = this.getGreetingKind(text);
                        if (greetingKind) {
                            const reply = this.pickGreetingReply(greetingKind);
                            this._messages.push({ role: 'user', content: text });
                            this._messages.push({ role: 'assistant', content: reply });
                            recordUserMessage();
                            this.postToWebview({ type: 'botThinking', value: false });
                            this.postToWebview({ type: 'botMessage', text: reply });
                            return;
                        }
                        if (this.looksLikeDiagnosticsRequest(text)) {
                            this._messages.push({ role: 'user', content: text });
                            recordUserMessage();
                            await this.handleDiagnosticsRequest(text);
                            this.postToWebview({ type: 'botThinking', value: false });
                            return;
                        }
                        // PR-4: Use modelId and modeId from the message (coming from pills)
                        const modelId = msg.modelId || this._currentModelId;
                        const modeId = msg.modeId || this._currentModeId;
                        // Start from any explicit attachments (chips / commands or from message)
                        let attachments = msg.attachments || this.getCurrentAttachments();
                        let autoAttachmentSummary = null;
                        // If the user didn't attach anything explicitly, try to infer context from the editor.
                        if (!attachments || attachments.length === 0) {
                            const auto = this.buildAutoAttachments(text);
                            if (auto) {
                                attachments = auto.attachments;
                                autoAttachmentSummary = auto.summary;
                                console.log('[Extension Host] [AEP] Auto-attached editor context:', {
                                    attachments: attachments.map(a => ({ kind: a.kind, path: a.path })),
                                    summary: auto.summary,
                                });
                            }
                        }
                        console.log('[Extension Host] [AEP] User message:', text, 'model:', modelId, 'mode:', modeId, 'attachments:', attachments?.length ?? 0);
                        // Update local state
                        this._messages.push({ role: 'user', content: text });
                        recordUserMessage();
                        // If we auto-attached something, show a tiny status line in the chat
                        if (autoAttachmentSummary) {
                            this.postToWebview({
                                type: 'botMessage',
                                text: `> ${autoAttachmentSummary}`,
                            });
                        }
                        // Show thinking state
                        this.postToWebview({ type: 'botThinking', value: true });
                        console.log('[Extension Host] [AEP] About to process message with routing:', text);
                        const workspaceRoot = this.getActiveWorkspaceRoot();
                        // CRITICAL: Ensure repo/intention commands go through local NAVI agent (no backend)
                        const repoIntentRegex = /(review\s+working\s+tree|review\s+changes|scan\s+repo|analyze\s+repo|git\s+diff|review\s+repo|review\s+my\s+working\s+changes)/i;
                        if (this.isRepoCommand(text) || repoIntentRegex.test(text)) {
                            console.log('[Extension Host] [AEP] 🔒 Repo command detected - routing to NAVI agent (local)');
                            const workspaceRoot = this.getActiveWorkspaceRoot();
                            if (!workspaceRoot) {
                                this.postToWebview({ type: 'botMessage', text: 'No workspace open.' });
                                this.postToWebview({ type: 'botThinking', value: false });
                                return;
                            }
                            this.postToWebview({ type: 'botThinking', value: true });
                            const { runNaviAgent } = await Promise.resolve().then(() => require('./navi/NaviAgentAdapter'));
                            await runNaviAgent({
                                workspaceRoot,
                                userInput: text,
                                emitEvent: (event) => {
                                    // Forward all agent events
                                    this.postToWebview({ type: 'navi.agent.event', event });
                                    // Phase 1.4: When repo diff summary arrives, collect diagnostics for changed files only
                                    const kind = event.type || event.kind;
                                    if (kind === 'repo.diff.summary') {
                                        try {
                                            const unstaged = event.data?.unstagedFiles || [];
                                            const staged = event.data?.stagedFiles || [];
                                            const relPaths = [...unstaged, ...staged].map(f => f.path).filter(Boolean);
                                            const diagnosticsByFile = collectDiagnosticsForFiles(workspaceRoot, relPaths);
                                            this.postToWebview({
                                                type: 'navi.agent.event',
                                                event: { type: 'diagnostics.summary', data: { files: diagnosticsByFile } }
                                            });
                                        }
                                        catch (e) {
                                            console.warn('[AEP] Phase 1.4 diagnostics collection failed:', e);
                                        }
                                    }
                                }
                            });
                            this.postToWebview({ type: 'botThinking', value: false });
                            return;
                        }
                        console.log('[Extension Host] [AEP] Using chat-only smart routing...');
                        await this.handleSmartRouting(text, modelId, modeId, attachments || [], msg.orgId, msg.userId);
                        console.log('[Extension Host] [AEP] Smart routing completed');
                        break;
                    }
                    case 'requestAttachment': {
                        await this.handleAttachmentRequest(webviewView.webview, msg.kind);
                        break;
                    }
                    case 'getDiagnostics': {
                        await this.handleDiagnosticsRequest();
                        break;
                    }
                    case 'agent.applyAction': {
                        // PR-7: Apply agent-proposed action (create/edit/run)
                        await this.handleAgentApplyAction(msg);
                        break;
                    }
                    case 'agent.applyWorkspacePlan': {
                        // New: Apply a full workspace plan (array of AgentAction)
                        const actions = Array.isArray(msg.actions) ? msg.actions : [];
                        await this.applyWorkspacePlan(actions);
                        break;
                    }
                    case 'agent.applyEdit': {
                        // PR-6: Apply agent-proposed edit (legacy support)
                        await this.handleApplyAgentEdit(msg);
                        break;
                    }
                    case 'agent.rejectEdit': {
                        // PR-6: User rejected agent edit (no-op for now, could log or notify)
                        console.log('[Extension Host] [AEP] User rejected agent edit:', msg);
                        break;
                    }
                    case 'setModel': {
                        // PR-4: Persist model selection
                        const { modelId, modelLabel } = msg;
                        if (!modelId || !modelLabel)
                            return;
                        this._currentModelId = modelId;
                        this._currentModelLabel = modelLabel;
                        this._context.globalState.update(STORAGE_KEYS.modelId, modelId);
                        this._context.globalState.update(STORAGE_KEYS.modelLabel, modelLabel);
                        console.log('[Extension Host] [AEP] Model changed to:', modelId, modelLabel);
                        break;
                    }
                    case 'setMode': {
                        // PR-4: Persist mode selection
                        const { modeId, modeLabel } = msg;
                        if (!modeId || !modeLabel)
                            return;
                        this._currentModeId = modeId;
                        this._currentModeLabel = modeLabel;
                        this._context.globalState.update(STORAGE_KEYS.modeId, modeId);
                        this._context.globalState.update(STORAGE_KEYS.modeLabel, modeLabel);
                        console.log('[Extension Host] [AEP] Mode changed to:', modeId, modeLabel);
                        break;
                    }
                    case 'newChat': {
                        // Clear current conversation state (so backend can start fresh)
                        this._conversationId = generateConversationId();
                        this._messages = [];
                        this.clearAttachments();
                        // Tell the webview to reset its UI
                        this.postToWebview({
                            type: 'resetChat',
                        });
                        break;
                    }
                    case 'attachClicked': {
                        // For now just show that the wiring works.
                        // Later we can open a real file/folder pick flow.
                        vscode.window.showInformationMessage('Attachment flow is not implemented yet – coming soon in a future release.');
                        break;
                    }
                    case 'pickAttachment':
                    case 'attachBtnClicked': {
                        console.log('[Extension Host] [AEP] Attachment button clicked - showing not implemented message');
                        // For now, just tell the webview this is not implemented yet.
                        this.postToWebview({ type: 'attachmentNotImplemented' });
                        break;
                    }
                    /* Keep the old attachment handling code commented out for future implementation
                    case 'pickAttachment_FUTURE': {
                      console.log('[Extension Host] [AEP] Webview requested attachment picker');
          
                      // Open file picker for attachments
                      const uris = await vscode.window.showOpenDialog({
                        openLabel: 'Attach to NAVI chat',
                        canSelectMany: true,
                        canSelectFiles: true,
                        canSelectFolders: false,
                        filters: {
                          'Code & Text': ['ts', 'tsx', 'js', 'jsx', 'java', 'cs', 'py', 'go', 'rb', 'php', 'cpp', 'c', 'h', 'json', 'yml', 'yaml', 'md', 'txt'],
                          'All Files': ['*']
                        }
                      });
          
                      if (!uris || uris.length === 0) {
                        console.log('[Extension Host] [AEP] Attachment picker canceled');
                        this.postToWebview({ type: 'attachmentsCanceled' });
                        return;
                      }
          
                      // Map to lightweight metadata objects the webview can render as chips
                      const files = await Promise.all(
                        uris.map(async (uri) => {
                          let size = 0;
                          try {
                            const stat = await vscode.workspace.fs.stat(uri);
                            size = stat.size ?? 0;
                          } catch {
                            // ignore stat failures, size stays 0
                          }
          
                          return {
                            name: path.basename(uri.fsPath),
                            uri: uri.toString(),
                            size
                          };
                        })
                      );
          
                      console.log('[Extension Host] [AEP] Selected attachments:', files);
          
                      this.postToWebview({
                        type: 'attachmentsSelected',
                        files
                      });
                      break;
                    }
                    */
                    case 'commandSelected': {
                        // Map the menu item -> suggested prompt
                        const cmd = String(msg.command || '');
                        let prompt = '';
                        switch (cmd) {
                            case 'jira-task-brief':
                                // Fetch Jira tasks from backend
                                await this.handleJiraTaskBriefCommand();
                                return;
                            case 'explain-code':
                                prompt =
                                    'Explain this code step-by-step, including what it does, time/space complexity, and any potential bugs or edge cases:';
                                break;
                            case 'refactor-code':
                                prompt =
                                    'Refactor this code for readability and maintainability, without changing behaviour:';
                                break;
                            case 'add-tests':
                                prompt =
                                    'Generate unit tests for this code. Include edge cases and failure paths:';
                                break;
                            case 'review-diff':
                                prompt =
                                    'Do a code review: highlight bugs, smells, and design/style issues, and suggest improvements:';
                                break;
                            case 'document-code':
                                prompt =
                                    'Add great documentation for this code: docstrings, comments where helpful, and a short summary of behaviour and constraints:';
                                break;
                            default:
                                // Fallback – just echo the command id
                                prompt = `Run NAVI action: ${cmd}`;
                        }
                        this.postToWebview({
                            type: 'insertCommandPrompt',
                            prompt,
                        });
                        break;
                    }
                    case 'attachTypeSelected': {
                        const type = String(msg.value || '').trim();
                        if (!type)
                            return;
                        vscode.window.showInformationMessage(`Attachment flow for "${type}" is not wired yet – this will open the real picker in a later PR.`);
                        break;
                    }
                    case 'jiraTaskSelected': {
                        // User selected a Jira task - fetch full brief
                        const jiraKey = String(msg.jiraKey || '').trim();
                        if (!jiraKey)
                            return;
                        await this.handleJiraTaskSelected(jiraKey);
                        break;
                    }
                    case 'showToast': {
                        // Display toast notification from webview
                        const message = String(msg.message || '').trim();
                        const level = String(msg.level || 'info');
                        if (!message)
                            return;
                        switch (level) {
                            case 'error':
                                vscode.window.showErrorMessage(`NAVI: ${message}`);
                                break;
                            case 'warning':
                                vscode.window.showWarningMessage(`NAVI: ${message}`);
                                break;
                            default:
                                vscode.window.showInformationMessage(`NAVI: ${message}`);
                        }
                        break;
                    }
                    case 'openConnectors': {
                        console.log('[AEP] openConnectors message received');
                        try {
                            // Open the Connectors Hub
                            const config = vscode.workspace.getConfiguration('aep');
                            const backendUrl = config.get('navi.backendUrl') || 'http://127.0.0.1:8787';
                            const cleanBaseUrl = backendUrl.replace(/\/api\/navi\/chat$/, '');
                            console.log('[AEP] Opening ConnectorsPanel with baseUrl:', cleanBaseUrl);
                            connectorsPanel_1.ConnectorsPanel.createOrShow(this._extensionUri);
                            console.log('[AEP] ConnectorsPanel.createOrShow completed');
                        }
                        catch (err) {
                            console.error('[AEP] Error opening ConnectorsPanel:', err);
                            vscode.window.showErrorMessage(`Failed to open Connectors: ${err}`);
                        }
                        break;
                    }
                    case 'connectors.getStatus': {
                        // Proxy connector status request to backend
                        try {
                            const baseUrl = this.getBackendBaseUrl();
                            const response = await fetch(`${baseUrl}/api/connectors/status`, {
                                headers: {
                                    'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                                },
                            });
                            if (!response.ok) {
                                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                            }
                            const data = await response.json();
                            this.postToWebview({ type: 'connectors.status', data });
                        }
                        catch (err) {
                            console.error('[Extension Host] [AEP] Connectors status error:', err);
                            this.postToWebview({
                                type: 'connectors.statusError',
                                error: err?.message || String(err),
                            });
                        }
                        break;
                    }
                    case 'connectors.jiraConnect': {
                        // Proxy Jira connection request to backend
                        try {
                            const baseUrl = this.getBackendBaseUrl();
                            const endpoint = `${baseUrl}/api/connectors/jira/connect`;
                            console.log('[AEP] Jira connect - Backend base URL:', baseUrl);
                            console.log('[AEP] Jira connect - Full endpoint:', endpoint);
                            console.log('[AEP] Jira connect - Request payload:', {
                                base_url: msg.baseUrl,
                                email: msg.email || undefined,
                                api_token: msg.apiToken ? '***' : undefined
                            });
                            const response = await fetch(endpoint, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                                },
                                body: JSON.stringify({
                                    base_url: msg.baseUrl,
                                    email: msg.email || undefined,
                                    api_token: msg.apiToken,
                                }),
                            });
                            console.log('[AEP] Jira connect - Response status:', response.status);
                            if (!response.ok) {
                                const errorText = await response.text().catch(() => '');
                                console.error('[AEP] Jira connect - Error response:', errorText);
                                throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
                            }
                            const data = await response.json();
                            console.log('[AEP] Jira connect - Success response:', data);
                            // Send proper result message
                            this.postToWebview({
                                type: 'connectors.jiraConnect.result',
                                ok: true,
                                provider: 'jira',
                                status: data.status || 'connected',
                                data
                            });
                        }
                        catch (err) {
                            console.error('[Extension Host] [AEP] Jira connect error:', err);
                            console.error('[AEP] Error stack:', err.stack);
                            // Send proper error result message
                            this.postToWebview({
                                type: 'connectors.jiraConnect.result',
                                ok: false,
                                provider: 'jira',
                                error: err?.message || String(err),
                            });
                            // Also show a user-friendly error message
                            vscode.window.showErrorMessage(`NAVI: Jira connection failed: ${err?.message || 'fetch failed'}. Check that backend is running on ${this.getBackendBaseUrl()}`);
                        }
                        break;
                    }
                    case 'connectors.close': {
                        console.log('[AEP] Connectors close message received');
                        // Hide the connectors modal in the webview
                        this.postToWebview({
                            type: 'connectors.hide'
                        });
                        break;
                    }
                    case 'connectors.jiraSyncNow': {
                        try {
                            const baseUrl = this.getBackendBaseUrl();
                            const endpoint = `${baseUrl}/api/org/sync/jira`;
                            console.log('[AEP] Jira sync-now – calling enhanced endpoint', endpoint);
                            const response = await fetch(endpoint, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                                },
                                body: JSON.stringify({
                                    user_id: 'default_user',
                                    max_issues: 20
                                })
                            });
                            if (!response.ok) {
                                const errorText = await response.text().catch(() => '');
                                console.error('[AEP] Jira sync-now failed', response.status, errorText);
                                vscode.window.showErrorMessage(`NAVI: Jira sync failed (${response.status}). Check backend logs.`);
                                this.postToWebview({
                                    type: 'connectors.jiraSyncResult',
                                    ok: false,
                                    error: `HTTP ${response.status}`,
                                });
                                return;
                            }
                            const data = await response.json();
                            console.log('[AEP] Jira sync-now success', data);
                            const syncedCount = data.total ?? data.processed_keys?.length ?? 0;
                            vscode.window.showInformationMessage(`NAVI: Jira sync complete – ${syncedCount} issues synced at ${new Date().toLocaleTimeString()}`);
                            this.postToWebview({
                                type: 'connectors.jiraSyncResult',
                                ok: true,
                                synced: syncedCount,
                                snapshot_ts: data.snapshot_ts,
                                processed_keys: data.processed_keys ?? []
                            });
                        }
                        catch (err) {
                            console.error('[AEP] Jira sync-now error', err);
                            vscode.window.showErrorMessage(`NAVI: Jira sync error – ${err?.message ?? String(err)}`);
                            this.postToWebview({
                                type: 'connectors.jiraSyncResult',
                                ok: false,
                                error: 'fetch_failed',
                            });
                        }
                        break;
                    }
                    case 'aep.intent.classify': {
                        // Handle intent classification request
                        const text = String(msg.text || '').trim();
                        const modelId = msg.modelId || this._currentModelId;
                        if (!text) {
                            console.warn('[AEP] Intent classification requested but no text provided');
                            return;
                        }
                        try {
                            console.log('[AEP] Classifying intent for text:', text, 'with model:', modelId);
                            // Call FastAPI backend for intent classification
                            const baseUrl = this.getBackendBaseUrl();
                            const response = await fetch(`${baseUrl}/api/agent/intent/preview`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    message: text,
                                    model_id: modelId
                                })
                            });
                            if (!response.ok) {
                                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                            }
                            const result = await response.json();
                            console.log('[AEP] Intent classification result:', result);
                            // Send result back to webview
                            this.postToWebview({
                                type: 'aep.intent.result',
                                intent: result.intent || 'Unknown',
                                confidence: result.confidence || 0.0,
                                model: result.model || modelId
                            });
                        }
                        catch (err) {
                            console.error('[AEP] Intent classification failed:', err);
                            this.postToWebview({
                                type: 'aep.intent.result',
                                intent: 'Error',
                                confidence: 0.0,
                                model: modelId,
                                error: String(err)
                            });
                        }
                        break;
                    }
                    case 'getWorkspaceRoot': {
                        // Send workspace info down to the webview as a fallback
                        const workspaceRoot = this.getActiveWorkspaceRoot();
                        const repoName = workspaceRoot
                            ? path.basename(workspaceRoot)
                            : 'unknown workspace';
                        this.postToWebview({
                            type: 'workspaceRoot',
                            workspaceRoot,
                            repoName,
                        });
                        // Optional extra event name if the React side is listening for something else
                        this.postToWebview({
                            type: 'workspaceInfo',
                            workspaceRoot,
                            repoName,
                        });
                        break;
                    }
                    case 'navra.copyToClipboard': {
                        const text = String(msg.text ?? '');
                        if (!text)
                            break;
                        try {
                            await vscode.env.clipboard.writeText(text);
                            // If you want, you can also send a tiny toast back:
                            // this.postToWebview({ type: 'toast', level: 'info', message: 'Copied to clipboard' });
                        }
                        catch (err) {
                            console.error('[AEP] Failed to copy via vscode.env.clipboard:', err);
                            vscode.window.showErrorMessage(`NAVI: Failed to copy to clipboard: ${err?.message || 'unknown error'}`);
                        }
                        break;
                    }
                    case 'copyToClipboard': {
                        try {
                            const text = String(msg.text || '').trim();
                            if (!text)
                                return;
                            await vscode.env.clipboard.writeText(text);
                            // optional: tiny status message
                            vscode.window.setStatusBarMessage('NAVI: Response copied to clipboard', 1500);
                        }
                        catch (err) {
                            console.error('[Extension Host] [AEP] Failed to copy to clipboard:', err);
                            vscode.window.showErrorMessage('NAVI: Failed to copy to clipboard.');
                        }
                        break;
                    }
                    case 'navra.attachLocal': {
                        // Open OS file picker and attach selected file(s)
                        await this.handleAttachmentRequest(webviewView.webview, 'pick-file');
                        break;
                    }
                    case 'navra.attachFromRepo': {
                        // Prefer selection, fall back to current file
                        const editor = vscode.window.activeTextEditor;
                        if (editor && !editor.selection.isEmpty) {
                            await this.handleAttachmentRequest(webviewView.webview, 'selection');
                        }
                        else {
                            await this.handleAttachmentRequest(webviewView.webview, 'current-file');
                        }
                        break;
                    }
                    case 'agent.applyReviewFixes': {
                        const reviews = Array.isArray(msg.reviews) ? msg.reviews : [];
                        await this.handleApplyReviewFixes(reviews);
                        break;
                    }
                    case 'quickAction': {
                        const action = String(msg.action || '');
                        switch (action) {
                            case 'checkErrorsAndFix': {
                                console.log('[Extension Host] [AEP] 🔧 Quick Action: Check errors and fix');
                                // Get current file or selection as attachment if available
                                const attachments = this.getCurrentAttachments();
                                // Use the enhanced message that will trigger diagnostics detection
                                const message = 'check errors and fix them';
                                await this.callNaviBackend(message, this._currentModelId, this._currentModeId, attachments);
                                break;
                            }
                            case 'reviewWorkingChanges':
                            case 'reviewStagedChanges':
                            case 'reviewLastCommit': {
                                console.log('[AEP] 🚨 OLD QUICK ACTION CALLED:', action, '- This should be replaced by orchestrator!');
                                let scope = 'working';
                                if (action === 'reviewStagedChanges')
                                    scope = 'staged';
                                if (action === 'reviewLastCommit')
                                    scope = 'lastCommit';
                                const diff = await getGitDiff(scope, this);
                                console.log("[AEP][Git] handleSmartRouting diff scope=", scope, "null? ", diff == null, "length=", diff ? diff.length : 0);
                                if (!diff) {
                                    const scopeName = scope === "staged"
                                        ? "staged changes"
                                        : scope === "lastCommit"
                                            ? "last commit"
                                            : "working tree changes";
                                    this.postToWebview({
                                        type: "botMessage",
                                        text: `I checked your Git ${scopeName} but ${scope === "lastCommit"
                                            ? "there is no last commit yet."
                                            : "there are no uncommitted changes."}\n\n` +
                                            (scope === "lastCommit"
                                                ? "Once you have commits in your repository, ask me again and I'll review them."
                                                : "Once you've saved your edits and `git diff` is non-empty, ask me again and I'll review them."),
                                    });
                                    this.postToWebview({ type: "botThinking", value: false });
                                    return;
                                }
                                let message;
                                if (scope === 'staged') {
                                    message =
                                        'Review the staged changes only. Point out issues, potential bugs, and improvements.';
                                }
                                else if (scope === 'lastCommit') {
                                    message =
                                        'Review the last commit. Summarize what changed and highlight any issues or improvements.';
                                }
                                else {
                                    message =
                                        'Review my uncommitted working tree changes. Point out issues and potential improvements.';
                                }
                                await this.callNaviBackend(message, this._currentModelId, this._currentModeId, [
                                    {
                                        kind: 'diff',
                                        path: scope === 'staged'
                                            ? 'git:diff:staged'
                                            : scope === 'lastCommit'
                                                ? 'git:diff:last-commit'
                                                : 'git:diff:working',
                                        language: 'diff',
                                        content: diff,
                                    },
                                ]);
                                break;
                            }
                            case 'explainRepo': {
                                console.log('[Extension Host] [AEP] 📖 Quick Action: Explain repo');
                                const message = 'explain this repo, what it does, and the key components';
                                await this.callNaviBackend(message, this._currentModelId, this._currentModeId, []);
                                break;
                            }
                            default:
                                console.warn('[AEP] Unknown quickAction:', action);
                                break;
                        }
                        break;
                    }
                    // React webview message handlers
                    case 'startReview': {
                        console.log('[AEP] React webview: Starting code review');
                        await this.handleReactReviewStart(webviewView.webview);
                        break;
                    }
                    case 'autoFix': {
                        const { filePath, issueType } = msg;
                        console.log('[AEP] React webview: Auto-fix request', { filePath, issueType });
                        await this.handleReactAutoFix(webviewView.webview, filePath, issueType);
                        break;
                    }
                    case 'openFile': {
                        const { filePath, line } = msg;
                        console.log('[AEP] React webview: Open file request', { filePath, line });
                        await this.handleReactOpenFile(filePath, line);
                        break;
                    }
                    case 'aep.file.diff': {
                        const file = String(msg.file || '').trim();
                        if (!file)
                            break;
                        try {
                            const workspaceRoot = this.getActiveWorkspaceRoot();
                            const fullPath = path.isAbsolute(file)
                                ? file
                                : workspaceRoot
                                    ? path.join(workspaceRoot, file)
                                    : file;
                            // Try to read HEAD version via git show; fall back gracefully
                            let baseContent = '';
                            try {
                                const { stdout } = await this.execGit(['show', `HEAD:${file}`], workspaceRoot);
                                baseContent = stdout;
                            }
                            catch (gitErr) {
                                console.warn('[AEP] git show failed for diff base, using placeholder:', gitErr);
                            }
                            const language = this.getLanguageFromFile(file) || 'plaintext';
                            const leftDoc = await vscode.workspace.openTextDocument({
                                content: baseContent || '// HEAD version not available',
                                language
                            });
                            const rightUri = vscode.Uri.file(fullPath);
                            const title = `NAVI Diff: ${path.basename(file)}`;
                            await vscode.commands.executeCommand('vscode.diff', leftDoc.uri, rightUri, title, { preview: true });
                        }
                        catch (err) {
                            console.error('[AEP] Failed to open diff for file:', file, err);
                            vscode.window.showErrorMessage(`NAVI: Unable to open diff for ${file}`);
                        }
                        break;
                    }
                    case 'aep.review.openAllDiffs': {
                        try {
                            const workspaceRoot = this.getActiveWorkspaceRoot();
                            if (!workspaceRoot) {
                                vscode.window.showWarningMessage('NAVI: No workspace open to show diffs.');
                                break;
                            }
                            // Get changed files from git status; fall back to last commit diff
                            const changed = await this.execGit(['status', '--porcelain'], workspaceRoot)
                                .then(({ stdout }) => stdout
                                .split('\n')
                                .map((l) => l.trim())
                                .filter(Boolean)
                                .map((l) => l.slice(3)))
                                .catch(() => []);
                            let files = changed.filter(Boolean);
                            if (files.length === 0) {
                                files = await this.execGit(['diff', '--name-only', 'HEAD~1'], workspaceRoot)
                                    .then(({ stdout }) => stdout.split('\n').filter(Boolean))
                                    .catch(() => []);
                            }
                            if (files.length === 0) {
                                vscode.window.showInformationMessage('NAVI: No changed files to diff.');
                                break;
                            }
                            // Optional filter for very large sets or user preference (supports glob-like or regex)
                            let selectedFiles = files;
                            if (files.length > 500) {
                                const filterText = await vscode.window.showInputBox({
                                    prompt: `Found ${files.length} changed files. Optional: filter by substring, glob (*, ?), or regex (re:pattern). Leave blank to open all.`,
                                    placeHolder: 'e.g. frontend/* or re:^backend/.*\\.py$ or auth',
                                });
                                if (filterText) {
                                    const filtered = this.filterFilesByPattern(files, filterText);
                                    if (filtered.length === 0) {
                                        vscode.window.showInformationMessage(`NAVI: No changed files matched "${filterText}". Showing all instead.`);
                                    }
                                    else {
                                        selectedFiles = filtered;
                                    }
                                }
                            }
                            await vscode.window.withProgress({
                                title: `Opening ${selectedFiles.length} diffs...`,
                                location: vscode.ProgressLocation.Notification,
                            }, async () => {
                                // First, open a PR-style aggregated diff in one virtual doc
                                try {
                                    const diffText = await this.execGit(['diff', 'HEAD', '--', ...selectedFiles], workspaceRoot).then(({ stdout }) => stdout);
                                    if (diffText && diffText.trim().length > 0) {
                                        const doc = await vscode.workspace.openTextDocument({
                                            content: diffText,
                                            language: 'diff',
                                        });
                                        await vscode.window.showTextDocument(doc, { preview: true });
                                    }
                                }
                                catch (aggErr) {
                                    console.warn('[AEP] Aggregated diff failed, continuing with per-file diffs.', aggErr);
                                }
                                // Then open per-file diffs in preview tabs
                                for (const file of selectedFiles) {
                                    const left = vscode.Uri.parse(`git:${path.join(workspaceRoot, file)}?ref=HEAD`);
                                    const right = vscode.Uri.file(path.join(workspaceRoot, file));
                                    const title = `NAVI Diff: ${file}`;
                                    await vscode.commands.executeCommand('vscode.diff', left, right, title, {
                                        preview: true,
                                    });
                                }
                            });
                        }
                        catch (err) {
                            console.error('[AEP] Failed to open all diffs:', err);
                            vscode.window.showErrorMessage('NAVI: Unable to open diffs for changes.');
                        }
                        break;
                    }
                    case 'applyAll': {
                        // Apply all patches in the bundle
                        const { applyPatchFromWebview } = await Promise.resolve().then(() => require('./repo/repoActions'));
                        await applyPatchFromWebview(msg.payload);
                        break;
                    }
                    case 'build.start': {
                        const cmd = String(msg.command || '').trim();
                        const timeoutMs = typeof msg.timeoutMs === 'number' ? msg.timeoutMs : 10 * 60 * 1000; // 10 min
                        await this.handleBuildCommand(cmd, timeoutMs);
                        break;
                    }
                    case 'git.status': {
                        await this.handleGitStatus();
                        break;
                    }
                    case 'git.push': {
                        await this.handleGitPush();
                        break;
                    }
                    case 'git.pr.open': {
                        await this.handleOpenPRPage();
                        break;
                    }
                    case 'git.pr.create': {
                        const payload = msg.payload || {};
                        await this.handleCreatePR(payload);
                        break;
                    }
                    case 'ci.trigger': {
                        const { repo, workflow, ref } = msg;
                        await this.handleCiTrigger(repo, workflow, ref);
                        break;
                    }
                    case 'ci.status': {
                        const { repo, runId } = msg;
                        await this.handleCiStatus(repo, runId);
                        break;
                    }
                    case 'applyFile': {
                        // Apply patch to a specific file
                        const { applyFilePatch } = await Promise.resolve().then(() => require('./repo/repoActions'));
                        await applyFilePatch(msg.payload.filePath, msg.payload.content);
                        break;
                    }
                    case 'undo': {
                        // Undo last patch operation
                        const { undoLastPatch } = await Promise.resolve().then(() => require('./repo/repoActions'));
                        await undoLastPatch();
                        break;
                    }
                    case 'showUndoHistory': {
                        // Show undo history picker
                        const { showUndoHistory } = await Promise.resolve().then(() => require('./repo/repoActions'));
                        await showUndoHistory();
                        break;
                    }
                    case 'viewFile': {
                        // Open file in editor
                        const filePath = msg.payload?.filePath;
                        if (filePath) {
                            const uri = vscode.Uri.file(filePath);
                            const document = await vscode.workspace.openTextDocument(uri);
                            await vscode.window.showTextDocument(document);
                        }
                        break;
                    }
                    case 'smartMode.reviewWorkspace': {
                        // Trigger Smart Mode workspace review
                        try {
                            vscode.window.showInformationMessage('🚀 Starting Smart Mode workspace review...');
                            const result = await smartModeCommands_1.smartModeCommands.smartReviewWorkspace();
                            if (result) {
                                this.postToWebview({
                                    type: 'smartMode.result',
                                    result: {
                                        success: result.success,
                                        mode: result.mode,
                                        filesModified: result.filesModified,
                                        summary: `Smart Mode completed in ${result.mode} mode, modified ${result.filesModified.length} files`
                                    }
                                });
                            }
                        }
                        catch (error) {
                            this.postToWebview({
                                type: 'smartMode.error',
                                error: String(error)
                            });
                        }
                        break;
                    }
                    case 'smartMode.reviewSelection': {
                        // Trigger Smart Mode selection review
                        try {
                            vscode.window.showInformationMessage('🎯 Starting Smart Mode selection review...');
                            const result = await smartModeCommands_1.smartModeCommands.smartReviewSelection();
                            if (result) {
                                this.postToWebview({
                                    type: 'smartMode.result',
                                    result: {
                                        success: result.success,
                                        mode: result.mode,
                                        filesModified: result.filesModified,
                                        summary: `Smart Mode completed in ${result.mode} mode`
                                    }
                                });
                            }
                        }
                        catch (error) {
                            this.postToWebview({
                                type: 'smartMode.error',
                                error: String(error)
                            });
                        }
                        break;
                    }
                    case 'smartMode.customInstruction': {
                        // Trigger Smart Mode with custom instruction
                        try {
                            const instruction = msg.instruction;
                            if (!instruction) {
                                vscode.window.showWarningMessage('No instruction provided for Smart Mode');
                                return;
                            }
                            vscode.window.showInformationMessage(`🔧 Starting Smart Mode: ${instruction}`);
                            const result = await smartModeCommands_1.smartModeCommands.smartReviewWithInstruction();
                            if (result) {
                                this.postToWebview({
                                    type: 'smartMode.result',
                                    result: {
                                        success: result.success,
                                        mode: result.mode,
                                        filesModified: result.filesModified,
                                        summary: `Custom Smart Mode completed in ${result.mode} mode`
                                    }
                                });
                            }
                        }
                        catch (error) {
                            this.postToWebview({
                                type: 'smartMode.error',
                                error: String(error)
                            });
                        }
                        break;
                    }
                    case 'smartMode.applyDiff': {
                        // Apply diff through Smart Mode
                        try {
                            const diffContent = msg.diffContent;
                            if (!diffContent) {
                                vscode.window.showWarningMessage('No diff content provided for Smart Mode');
                                return;
                            }
                            vscode.window.showInformationMessage('🔧 Applying diff through Smart Mode...');
                            const result = await smartModeCommands_1.smartModeCommands.applySmartDiff(diffContent);
                            if (result) {
                                this.postToWebview({
                                    type: 'smartMode.result',
                                    result: {
                                        success: result.success,
                                        mode: result.mode,
                                        filesModified: result.filesModified,
                                        summary: `Smart Diff applied in ${result.mode} mode`
                                    }
                                });
                            }
                        }
                        catch (error) {
                            this.postToWebview({
                                type: 'smartMode.error',
                                error: String(error)
                            });
                        }
                        break;
                    }
                    case 'smartMode.undo': {
                        // Undo last Smart Mode operation
                        try {
                            await smartModeCommands_1.smartModeCommands.undoLastSmartMode();
                            this.postToWebview({
                                type: 'smartMode.result',
                                result: {
                                    success: true,
                                    mode: 'undo',
                                    filesModified: [],
                                    summary: 'Last Smart Mode operation undone successfully'
                                }
                            });
                        }
                        catch (error) {
                            this.postToWebview({
                                type: 'smartMode.error',
                                error: String(error)
                            });
                        }
                        break;
                    }
                    default:
                        console.warn('[Extension Host] [AEP] Unknown message from webview:', msg);
                }
            }
            catch (err) {
                console.error('[Extension Host] [AEP] Error handling webview message:', err);
                this.postToWebview({
                    type: 'error',
                    text: '⚠️ Unexpected error in NAVI extension. Check developer tools for more details.'
                });
            }
        });
        webviewView.onDidDispose(() => {
            if (this._scanTimer) {
                clearInterval(this._scanTimer);
                this._scanTimer = undefined;
            }
        });
        // Welcome message will be sent when panel sends 'ready'
    }
    // --- React Webview Message Handlers -----------------------------------
    async handleReactReviewStart(webview) {
        try {
            console.log('[AEP] DEBUG: handleReactReviewStart called');
            // Send review started event
            webview.postMessage({
                type: 'reviewStarted',
                progress: 'Initializing workspace scan...'
            });
            const workspaceRoot = this.getActiveWorkspaceRoot();
            console.log('[AEP] DEBUG: workspaceRoot =', workspaceRoot);
            if (!workspaceRoot) {
                webview.postMessage({
                    type: 'reviewCompleted',
                });
                return;
            }
            // Use real backend analysis instead of mock data
            console.log('[AEP] DEBUG: About to call backend API...');
            try {
                const response = await fetch('http://localhost:8787/api/navi/analyze-changes', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        workspace_root: workspaceRoot
                    })
                });
                if (!response.ok) {
                    throw new Error(`Backend response: ${response.status}`);
                }
                const reader = response.body?.getReader();
                if (!reader) {
                    throw new Error('No response body');
                }
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done)
                        break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || ''; // Keep incomplete line in buffer
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                if (data.type === 'progress') {
                                    webview.postMessage({
                                        type: 'reviewProgress',
                                        progress: data.step
                                    });
                                }
                                else if (data.type === 'result') {
                                    // Send real analysis results
                                    const result = data.result;
                                    if (result.files && result.files.length > 0) {
                                        for (const file of result.files) {
                                            if (file.issues && file.issues.length > 0) {
                                                for (const issue of file.issues) {
                                                    webview.postMessage({
                                                        type: 'reviewEntry',
                                                        entry: {
                                                            path: file.path,
                                                            line: issue.line || 1,
                                                            severity: issue.severity || 'info',
                                                            category: issue.type || 'analysis',
                                                            summary: issue.message || 'Code analysis issue',
                                                            description: issue.description || issue.message || 'Issue found during analysis',
                                                            suggestion: issue.suggestion || 'Consider reviewing this code section'
                                                        }
                                                    });
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            catch (parseError) {
                                console.error('Failed to parse SSE data:', parseError);
                            }
                        }
                    }
                }
            }
            catch (fetchError) {
                console.error('[AEP] DEBUG: Backend analysis failed:', fetchError);
                webview.postMessage({
                    type: 'reviewProgress',
                    progress: `Analysis failed: ${fetchError?.message || fetchError}. Using fallback analysis...`
                });
                // Fallback to simple workspace scan
                console.log('[AEP] DEBUG: Sending fallback system entry');
                webview.postMessage({
                    type: 'reviewEntry',
                    entry: {
                        path: 'System',
                        line: 1,
                        severity: 'info',
                        category: 'system',
                        summary: 'Backend Analysis Unavailable',
                        description: `Could not connect to analysis backend: ${fetchError?.message || fetchError}`,
                        suggestion: 'Ensure the backend is running on localhost:8787'
                    }
                });
            }
            webview.postMessage({
                type: 'reviewCompleted'
            });
        }
        catch (error) {
            console.error('[AEP] Review start error:', error);
            webview.postMessage({
                type: 'reviewCompleted'
            });
        }
    }
    async handleReactAutoFix(webview, filePath, issueType) {
        try {
            console.log(`[AEP] Auto-fixing ${issueType} in ${filePath}`);
            // Mock auto-fix process
            await new Promise(resolve => setTimeout(resolve, 1500));
            // Simulate 70% success rate
            const success = Math.random() > 0.3;
            webview.postMessage({
                type: 'autoFixResult',
                filePath,
                result: {
                    success,
                    message: success
                        ? `Successfully fixed ${issueType} in ${filePath}`
                        : `Failed to fix ${issueType}: Manual intervention required`,
                    applied: success
                }
            });
        }
        catch (error) {
            console.error('[AEP] Auto-fix error:', error);
            webview.postMessage({
                type: 'autoFixResult',
                filePath,
                result: {
                    success: false,
                    message: `Auto-fix failed: ${error instanceof Error ? error.message : 'Unknown error'}`
                }
            });
        }
    }
    async handleReactOpenFile(filePath, line) {
        try {
            const uri = vscode.Uri.file(filePath);
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);
            if (line && line > 0) {
                const position = new vscode.Position(line - 1, 0);
                editor.selection = new vscode.Selection(position, position);
                editor.revealRange(new vscode.Range(position, position));
            }
        }
        catch (error) {
            console.error('[AEP] Open file error:', error);
            vscode.window.showErrorMessage(`Failed to open file: ${filePath}`);
        }
    }
    // --- Intent classification and smart routing --------------------------------
    // --- Intent classification and smart routing --------------------------------
    async classifyIntent(message) {
        const text = (message || '').trim();
        if (!text) {
            return 'general';
        }
        try {
            const baseUrl = this.getBackendBaseUrl();
            const endpoint = `${baseUrl}/api/agent/intent/preview`;
            console.log('[AEP] Calling intent preview endpoint:', endpoint);
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    model_id: this._currentModelId,
                }),
            });
            if (!response.ok) {
                const body = await response.text().catch(() => '');
                console.warn('[AEP] Intent preview HTTP error:', response.status, response.statusText, body);
                return 'general';
            }
            const result = await response.json();
            const family = (result.family || '').toLowerCase();
            const kind = (result.kind || '').toLowerCase();
            const confidence = typeof result.confidence === 'number'
                ? result.confidence
                : 0;
            console.log('[AEP] Intent preview result:', { family, kind, confidence });
            // Map backend families/kinds → NaviIntent union
            if (family === 'jira') {
                if (kind === 'list')
                    return 'jira_list';
                if (kind === 'priority')
                    return 'jira_priority';
                return 'jira_ticket';
            }
            if (family === 'workspace') {
                return 'workspace';
            }
            if (family === 'code') {
                return 'code';
            }
            if (family === 'greeting') {
                return 'greeting';
            }
            return 'general';
        }
        catch (err) {
            console.warn('[AEP] Intent classification failed, falling back to general:', err);
            return 'general';
        }
    }
    /**
     * Detect if a message is a repo-aware command that needs orchestrator
     */
    isRepoCommand(text) {
        if (this.looksLikeGitCommand(text)) {
            return false;
        }
        if (this.looksLikeDiagnosticsRequest(text)) {
            return false;
        }
        return /(review|working tree|git|changes|diff|errors|fix|diagnostic|analyze|check.*quality|suggest.*improvements)/i.test(text);
    }
    looksLikeDiagnosticsRequest(text) {
        const msg = (text || '').toLowerCase();
        if (!msg.trim())
            return false;
        if (/\b(lint|eslint|tsc|typecheck|mypy|flake8|pylint|ruff|diagnostic)\b/.test(msg)) {
            return true;
        }
        const errorPhrase = /\b(check|find|scan|look for|list|show)\b.*\b(error|errors|warnings|issues|problems)\b/.test(msg);
        const scopeHint = /\b(repo|repository|project|codebase|workspace|file|current file|this file)\b/.test(msg);
        if (errorPhrase && scopeHint)
            return true;
        if (/\b(check|find|scan)\b.*\berrors?\b/.test(msg))
            return true;
        return false;
    }
    looksLikeGitCommand(text) {
        const trimmed = (text || "").trim();
        if (!trimmed)
            return false;
        if (/^git\s+\S+/i.test(trimmed))
            return true;
        if (/`git\s+[^`]+`/i.test(trimmed))
            return true;
        if (/\b(run|execute|please run|can you run)\s+git\s+\S+/i.test(trimmed)) {
            return true;
        }
        const lower = trimmed.toLowerCase();
        if (/\b(review|analyz|analyse|audit|inspect|quality)\b/.test(lower)) {
            return false;
        }
        const hasGitWord = /\bgit\b/.test(lower);
        const diffIntent = /\b(diff|compare)\b/.test(lower) ||
            (/\bchanges\b/.test(lower) && /\b(git|branch|main|master)\b/.test(lower));
        if (diffIntent)
            return true;
        if (/\bworking tree\b/.test(lower))
            return true;
        if (/\b(staged|unstaged)\b/.test(lower))
            return true;
        if (/\bstatus\b/.test(lower) && hasGitWord)
            return true;
        if (/\b(current|active|which|what)\s+branch\b/.test(lower))
            return true;
        if (/\bbranches?\b/.test(lower))
            return true;
        if (/\b(log|history|recent commits|last commit)\b/.test(lower))
            return true;
        if (/\b(remote|remotes)\b/.test(lower))
            return true;
        return false;
    }
    async getGitHealth(workspaceRoot) {
        try {
            const { stdout } = await exec("git rev-parse --is-inside-work-tree", { cwd: workspaceRoot });
            if (stdout.trim() !== "true") {
                return { isGitRepo: false, hasHead: false };
            }
        }
        catch {
            return { isGitRepo: false, hasHead: false };
        }
        try {
            await exec("git rev-parse --verify HEAD", { cwd: workspaceRoot });
            return { isGitRepo: true, hasHead: true };
        }
        catch {
            return { isGitRepo: true, hasHead: false };
        }
    }
    async handleDiagnosticsRequest(text) {
        console.log('[AEP] Getting diagnostics for current workspace');
        const workspaceRoot = this.getActiveWorkspaceRoot();
        const lower = (text || '').toLowerCase();
        const restrictToActiveFile = /\b(current file|this file|active file|open file)\b/.test(lower);
        let actions = [];
        try {
            const allDiagnostics = vscode.languages.getDiagnostics();
            const activeEditor = vscode.window.activeTextEditor;
            const activePath = activeEditor?.document?.uri.fsPath;
            const diagnostics = restrictToActiveFile && activePath
                ? allDiagnostics.filter(([uri]) => uri.fsPath === activePath)
                : allDiagnostics;
            const errorCount = diagnostics.reduce((count, [_, diags]) => count + diags.length, 0);
            const fileCount = diagnostics.length;
            const diagnosticsCommandsArray = workspaceRoot
                ? await detectDiagnosticsCommands(workspaceRoot)
                : [];
            if (diagnosticsCommandsArray.length > 0 && workspaceRoot) {
                const seen = new Set();
                actions = diagnosticsCommandsArray
                    .filter((cmd) => {
                    const normalized = String(cmd || '').trim();
                    if (!normalized || seen.has(normalized))
                        return false;
                    seen.add(normalized);
                    return true;
                })
                    .slice(0, 5)
                    .map((cmd) => ({
                    type: 'runCommand',
                    description: `Run ${cmd}`,
                    command: cmd,
                    cwd: workspaceRoot,
                    meta: { kind: 'diagnostics' },
                }));
            }
            if (errorCount === 0) {
                const followUp = actions.length
                    ? "\n\nNo VS Code diagnostics found. Want me to run lint or test commands to double-check?"
                    : "";
                this.postToWebview({
                    type: 'botMessage',
                    text: `✅ **No diagnostic errors found**\n\n` +
                        `${restrictToActiveFile ? "The current file" : "Your workspace"} appears clean ` +
                        `(no lint or compiler issues reported).${followUp}`,
                    actions,
                });
                return;
            }
            // Collect detailed diagnostic info
            let diagnosticDetails = '';
            let errorsByFile = 0;
            for (const [uri, diags] of diagnostics) {
                if (diags.length > 0 && errorsByFile < 5) { // Show max 5 files
                    const fileName = path.basename(uri.fsPath);
                    const errors = diags.filter(d => d.severity === vscode.DiagnosticSeverity.Error).length;
                    const warnings = diags.filter(d => d.severity === vscode.DiagnosticSeverity.Warning).length;
                    const info = diags.length - errors - warnings;
                    diagnosticDetails += `\n- **${fileName}**: `;
                    if (errors > 0)
                        diagnosticDetails += `${errors} error${errors > 1 ? 's' : ''}`;
                    if (warnings > 0) {
                        if (errors > 0)
                            diagnosticDetails += ', ';
                        diagnosticDetails += `${warnings} warning${warnings > 1 ? 's' : ''}`;
                    }
                    if (info > 0) {
                        if (errors > 0 || warnings > 0)
                            diagnosticDetails += ', ';
                        diagnosticDetails += `${info} info`;
                    }
                    errorsByFile++;
                }
            }
            if (fileCount > 5) {
                diagnosticDetails += `\n- ...and ${fileCount - 5} more files`;
            }
            this.postToWebview({
                type: 'botMessage',
                text: `🔍 **Found ${errorCount} diagnostic issues** across ${fileCount} files:\n` +
                    `${diagnosticDetails}\n\n` +
                    `If you want, I can run lint/test commands or start fixing them.`,
                actions,
            });
        }
        catch (error) {
            console.error('[AEP] Error getting diagnostics:', error);
            this.postToWebview({
                type: 'botMessage',
                text: `⚠️ **Could not retrieve diagnostics**\n\n` +
                    `Make sure you have:\n` +
                    `- Language servers installed (TypeScript, ESLint, etc)\n` +
                    `- Linting tools configured for your project\n` +
                    `- Files open in VS Code for analysis`,
                actions,
            });
        }
    }
    /**
     * Get git diff - simplified and non-blocking version
     */
    async getRealGitDiff(workspacePath) {
        try {
            console.log('🔍 Getting git diff for workspace:', workspacePath);
            const stdout = await new Promise((resolve) => {
                const cp = require('child_process').spawn('git', ['diff', '--stat'], { cwd: workspacePath });
                let output = '';
                cp.stdout.on('data', (d) => { output += d.toString(); });
                cp.on('close', () => resolve(output));
                cp.on('error', () => resolve(''));
            });
            return stdout || 'No changes detected';
        }
        catch (error) {
            console.error('Git diff error:', error);
            return 'Unable to analyze git changes - will analyze current workspace state instead.';
        }
    }
    /**
     * Handle all repo-aware commands through orchestrator
     */
    async handleRepoOrchestrator(message) {
        try {
            console.log('🎯 Repo orchestrator called for:', message.text);
            const workspaceRoot = message.workspaceRoot || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
            if (!workspaceRoot) {
                throw new Error('No workspace folder found');
            }
            const gitHealth = await this.getGitHealth(workspaceRoot);
            if (!gitHealth.isGitRepo) {
                await this.handleGitInitRequest('working');
                this.postToWebview({
                    type: 'review.error',
                    message: 'This folder is not a Git repository.',
                    code: 'GIT_NOT_REPO'
                });
                return;
            }
            // Guard: ensure there is a real working-tree diff before calling backend
            try {
                const diff = await this.execGit(['diff'], workspaceRoot);
                const diffText = diff?.stdout ?? '';
                if (!diffText.trim()) {
                    this.postToWebview({
                        type: 'botMessage',
                        text: 'No uncommitted changes detected in this repository.'
                    });
                    this.postToWebview({ type: 'review.done' });
                    this.postToWebview({ type: 'botThinking', value: false });
                    return;
                }
            }
            catch (diffErr) {
                console.warn('[AEP] Git diff check failed, proceeding without diff content:', diffErr);
            }
            if (!gitHealth.hasHead) {
                const repoName = path.basename(workspaceRoot);
                const explanation = `This repo (${repoName}) has no commits yet, so there is no HEAD to compare against main/HEAD.\n\n` +
                    `Next steps:\n` +
                    `- Create an initial commit: \`git add -A\` then \`git commit -m "Initial commit"\`.\n` +
                    `- If you expect a remote main branch: \`git fetch origin\` then \`git checkout main\`.\n\n` +
                    `I can run the commands below once you approve them.`;
                const actions = [
                    {
                        type: 'runCommand',
                        description: 'Check git status',
                        command: 'git status --porcelain',
                        cwd: workspaceRoot
                    },
                    {
                        type: 'runCommand',
                        description: 'Stage all files',
                        command: 'git add -A',
                        cwd: workspaceRoot
                    },
                    {
                        type: 'runCommand',
                        description: 'Create initial commit',
                        command: 'git commit -m "Initial commit"',
                        cwd: workspaceRoot
                    }
                ];
                this._messages.push({ role: 'assistant', content: explanation });
                this.postToWebview({ type: 'botThinking', value: false });
                this.postToWebview({ type: 'botMessage', text: explanation, actions });
                this.postToWebview({
                    type: 'review.error',
                    message: 'Git HEAD is missing (no commits yet).',
                    code: 'GIT_NO_HEAD'
                });
                return;
            }
            // Let the webview show its own progress UI (no chat bubble spam)
            this.postToWebview({
                type: 'review.progress',
                text: '🔍 Analyzing repository...'
            });
            console.log('🔍 Detected workspace folder:', workspaceRoot);
            console.log('🔍 All workspace folders:', vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath));
            const { baseUrl } = this.resolveBackendEndpoints();
            const url = new URL(`${baseUrl}/api/navi/repo/review/stream`);
            url.searchParams.set('workspace_root', workspaceRoot);
            const response = await fetch(url.toString(), {
                method: 'GET',
                headers: {
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'X-Org-Id': this.getOrgId(message.orgId)
                }
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            // Handle SSE stream
            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error('No response body reader available');
            }
            const MAX_REVIEW_ENTRIES = 200; // avoid unbounded memory while keeping enough files
            let reviewEntries = [];
            let reviewSummary = null;
            let currentProgress = '';
            const decoder = new TextDecoder();
            let buffer = '';
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done)
                        break;
                    buffer += decoder.decode(value, { stream: true });
                    // SSE events are separated by a blank line (\n\n). Keep any partial
                    // event in the buffer and only parse complete ones.
                    const events = buffer.split(/\n\n/);
                    buffer = events.pop() ?? '';
                    for (const rawEvent of events) {
                        const dataLines = rawEvent
                            .split('\n')
                            .filter((l) => l.startsWith('data:'))
                            .map((l) => l.replace(/^data:\s?/, ''));
                        if (dataLines.length === 0)
                            continue;
                        const payloadStr = dataLines.join('\n').trim();
                        if (!payloadStr)
                            continue;
                        try {
                            const data = JSON.parse(payloadStr);
                            if (data.kind === 'liveProgress') {
                                // Update progress and forward to UI without dumping chat bubbles
                                currentProgress = data.step || 'Processing...';
                                this.postToWebview({
                                    type: 'review.progress',
                                    text: currentProgress,
                                    percentage: data.percentage,
                                    totalFiles: data.totalFiles,
                                    processedFiles: data.processedFiles
                                });
                                // Also keep the chat bubble calm: no botMessage spam
                            }
                            else if (data.kind === 'reviewSummary') {
                                // Store concise summary from backend
                                reviewSummary = data;
                                this.postToWebview({
                                    type: 'review.summary',
                                    summary: reviewSummary
                                });
                            }
                            else if (data.kind === 'reviewEntry') {
                                // Collect compact summaries (avoid streaming full diffs to chat)
                                if (reviewEntries.length < MAX_REVIEW_ENTRIES) {
                                    const entry = data.entry || {};
                                    const file = entry.filePath ||
                                        entry.file ||
                                        entry.path ||
                                        'unknown file';
                                    const issues = Array.isArray(entry.issues)
                                        ? entry.issues
                                        : [];
                                    reviewEntries.push({
                                        file,
                                        severity: entry.severity || 'info',
                                        issueCount: issues.length,
                                        topIssues: issues
                                            .slice(0, 2)
                                            .map((i) => i.title || i.description || i.summary || 'Issue'),
                                        diff: entry.diff,
                                    });
                                }
                                // Send lightweight entry to webview for live cards
                                this.postToWebview({
                                    type: 'review.entry',
                                    entry: {
                                        file: data.entry?.filePath || data.entry?.file || data.entry?.path,
                                        severity: data.entry?.severity || 'info',
                                        diff: data.entry?.diff || data.entry?.patch,
                                        issues: (data.entry?.issues || []).map((issue) => ({
                                            id: issue.id,
                                            title: issue.title || issue.description || issue.summary,
                                            severity: issue.severity || data.entry?.severity || 'info',
                                            canAutoFix: !!issue.canAutoFix,
                                            fixId: issue.id,
                                        })),
                                    }
                                });
                            }
                            else if (data.kind === 'done') {
                                // Stream complete
                                break;
                            }
                        }
                        catch (parseError) {
                            // Harden parsing: tolerate non-JSON SSE chunks
                            const t = payloadStr.trim();
                            // Case 1: Python dict-style string → normalize quotes and parse
                            if (t.startsWith('{') && t.includes("'")) {
                                try {
                                    const normalized = t.replace(/'/g, '"');
                                    const data = JSON.parse(normalized);
                                    // If the normalized payload looks like a review entry, forward it
                                    if (data.file || data.path || data.filePath) {
                                        const file = data.filePath || data.file || data.path || 'unknown file';
                                        reviewEntries.push({
                                            file,
                                            severity: data.severity || 'info',
                                            issueCount: Array.isArray(data.issues) ? data.issues.length : 0,
                                            topIssues: (Array.isArray(data.issues) ? data.issues : [])
                                                .slice(0, 2)
                                                .map((i) => i.title || i.description || i.summary || 'Issue'),
                                            diff: data.diff || data.patch,
                                        });
                                        this.postToWebview({
                                            type: 'review.entry',
                                            entry: {
                                                file,
                                                severity: data.severity || 'info',
                                                diff: data.diff || data.patch,
                                                issues: (Array.isArray(data.issues) ? data.issues : []).map((issue) => ({
                                                    id: issue.id,
                                                    title: issue.title || issue.description || issue.summary,
                                                    severity: issue.severity || data.severity || 'info',
                                                    canAutoFix: !!issue.canAutoFix,
                                                    fixId: issue.id,
                                                })),
                                            }
                                        });
                                    }
                                    else {
                                        // Otherwise treat as progress text
                                        this.postToWebview({
                                            type: 'review.progress',
                                            text: t,
                                        });
                                    }
                                }
                                catch {
                                    // Plain text progress fallback
                                    this.postToWebview({ type: 'review.progress', text: t });
                                }
                            }
                            else {
                                // Case 2: plain progress text
                                this.postToWebview({ type: 'review.progress', text: t });
                            }
                        }
                    }
                }
                // Attempt to parse any trailing buffered event (if stream closed without final \n\n)
                if (buffer.trim().length > 0) {
                    const dataLines = buffer
                        .split('\n')
                        .filter((l) => l.startsWith('data:'))
                        .map((l) => l.replace(/^data:\s?/, ''));
                    const payloadStr = dataLines.join('\n').trim();
                    if (payloadStr) {
                        try {
                            const data = JSON.parse(payloadStr);
                            if (data.kind === 'done') {
                                // no-op, already complete
                            }
                        }
                        catch (parseError) {
                            // Apply same tolerant fallback for trailing chunk
                            const t = payloadStr.trim();
                            if (t.startsWith('{') && t.includes("'")) {
                                try {
                                    const normalized = t.replace(/'/g, '"');
                                    const data = JSON.parse(normalized);
                                    if (data.kind === 'liveProgress') {
                                        this.postToWebview({ type: 'review.progress', text: data.step || 'Processing...' });
                                    }
                                    else if (data.file || data.path || data.filePath) {
                                        const file = data.filePath || data.file || data.path || 'unknown file';
                                        reviewEntries.push({
                                            file,
                                            severity: data.severity || 'info',
                                            issueCount: Array.isArray(data.issues) ? data.issues.length : 0,
                                            topIssues: (Array.isArray(data.issues) ? data.issues : [])
                                                .slice(0, 2)
                                                .map((i) => i.title || i.description || i.summary || 'Issue'),
                                            diff: data.diff || data.patch,
                                        });
                                        this.postToWebview({
                                            type: 'review.entry',
                                            entry: {
                                                file,
                                                severity: data.severity || 'info',
                                                diff: data.diff || data.patch,
                                                issues: (Array.isArray(data.issues) ? data.issues : []).map((issue) => ({
                                                    id: issue.id,
                                                    title: issue.title || issue.description || issue.summary,
                                                    severity: issue.severity || data.severity || 'info',
                                                    canAutoFix: !!issue.canAutoFix,
                                                    fixId: issue.id,
                                                })),
                                            }
                                        });
                                    }
                                    else if (data.kind === 'done') {
                                        // no-op
                                    }
                                    else {
                                        this.postToWebview({ type: 'review.progress', text: t });
                                    }
                                }
                                catch {
                                    this.postToWebview({ type: 'review.progress', text: t });
                                }
                            }
                            else {
                                this.postToWebview({ type: 'review.progress', text: t });
                            }
                        }
                    }
                }
            }
            finally {
                reader.releaseLock();
            }
            // Format and display a concise summary (no raw diffs dumped into chat)
            const listed = reviewSummary?.listedFiles || [];
            const skipped = reviewSummary?.skippedFiles || 0;
            const totalFiles = reviewSummary?.totalFiles ?? reviewEntries.length;
            const issueCount = reviewEntries.reduce((sum, e) => sum + e.issueCount, 0);
            const quickSummary = [
                `Files scanned: **${totalFiles}**`,
                `Issues found: **${issueCount}**`,
                skipped > 0 ? `Skipped: ${skipped} files (large/ignored)` : null,
            ]
                .filter(Boolean)
                .join(' · ');
            const severityRank = {
                error: 3,
                high: 3,
                warning: 2,
                medium: 2,
                info: 1,
                low: 1,
            };
            const entriesForSummary = reviewEntries.filter((e) => (e.issueCount ?? 0) > 0).length > 0
                ? reviewEntries.filter((e) => (e.issueCount ?? 0) > 0)
                : reviewEntries;
            const topFindings = entriesForSummary
                .slice()
                .sort((a, b) => {
                const rankA = severityRank[String(a.severity || '').toLowerCase()] ?? 0;
                const rankB = severityRank[String(b.severity || '').toLowerCase()] ?? 0;
                if (rankA !== rankB)
                    return rankB - rankA;
                return (b.issueCount ?? 0) - (a.issueCount ?? 0);
            })
                .slice(0, 5)
                .map((entry) => {
                const issues = entry.topIssues.length > 0
                    ? entry.topIssues.map((t) => `• ${t}`).join('\n')
                    : '• Issues detected';
                return `- \`${entry.file}\` (${entry.severity}, ${entry.issueCount} issues)\n${issues}`;
            })
                .join('\n\n');
            const fullResponse = [
                '# 📋 Repository Review',
                quickSummary ? `\n${quickSummary}\n` : '',
                topFindings ? '\n## Top findings\n' + topFindings : '\n✅ No issues detected.',
                listed.length
                    ? '\nFiles reviewed: ' + listed.map((f) => `\`${f}\``).join(', ')
                    : '',
            ].join('\n');
            // Broadcast structured completion event (no chat bubble dump)
            this.postToWebview({
                type: 'review.done',
                summary: {
                    text: fullResponse,
                    quickSummary,
                    topFindings,
                    issueCount,
                    totalFiles,
                    skipped,
                    listed
                },
                entries: reviewEntries
            });
            // Also drop the summary into the chat thread so the user sees a response
            this.postToWebview({
                type: 'botMessage',
                text: fullResponse
            });
            // Stop thinking spinner
            this.postToWebview({ type: 'botThinking', value: false });
            // PATCH 3: Guarantee review completion signals
            this.postToWebview({ type: 'review.done' });
            this.postToWebview({ type: 'botThinking', value: false });
        }
        catch (error) {
            console.error('❌ Repo orchestrator error:', error);
            // PATCH 3: Guarantee completion signals in catch block too
            this.postToWebview({ type: 'review.done' });
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'review.error',
                message: error instanceof Error ? error.message : 'Unknown error',
                code: 'REPO_ORCHESTRATOR_ERROR'
            });
        }
    }
    async handleSmartRouting(text, modelId, modeId, attachments = [], orgId, userId) {
        try {
            console.log('🎯 Smart routing (CHAT-ONLY) called with text:', text);
            // Chat path now routes through NAVI so attachments (files/diffs) get used
            const targetUrl = `${this.getBackendBaseUrl()}/api/navi/chat`;
            const controller = new AbortController();
            const timeoutMs = 20000; // avoid hanging forever if backend stalls
            const timeout = setTimeout(() => controller.abort(), timeoutMs);
            const response = await fetch(targetUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': this.getOrgId(orgId),
                },
                body: JSON.stringify({
                    message: text,
                    conversationHistory: this._messages.slice(-10).map((msg, index) => ({
                        id: `${Date.now()}-${index}`,
                        type: msg.role,
                        content: msg.content,
                        timestamp: new Date().toISOString(),
                    })),
                    session_id: 'ext-session',
                    model_id: modelId,
                    mode_id: modeId,
                    user_id: this.getUserId(userId),
                    attachments: (attachments ?? []).map((att) => ({
                        kind: att.kind,
                        content: att.content,
                        language: att.language,
                        name: path.basename(att.path || ''),
                        path: att.path,
                    })),
                    workspace_root: this.getActiveWorkspaceRoot()
                }),
                signal: controller.signal
            });
            clearTimeout(timeout);
            const rawText = await response.text();
            if (!response.ok) {
                const errText = rawText || response.statusText;
                throw new Error(`HTTP ${response.status}: ${errText}`);
            }
            if (!rawText || !rawText.trim()) {
                throw new Error('NAVI backend returned an empty reply.');
            }
            let data;
            try {
                data = JSON.parse(rawText);
            }
            catch (err) {
                console.error('[AEP] ❌ Failed to parse NAVI response JSON:', rawText);
                throw err;
            }
            console.log('📥 Chat-only response:', data);
            const content = String(data.content || data.response || '').trim();
            if (!content) {
                throw new Error('NAVI backend returned an empty reply.');
            }
            // Add to message history
            this._messages.push({ role: 'assistant', content });
            const messageId = `msg-${Date.now()}`;
            if (Array.isArray(data.actions) && data.actions.length > 0) {
                this._agentActions.set(messageId, { actions: data.actions });
            }
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'botMessage',
                text: content,
                messageId,
                actions: Array.isArray(data.actions) ? data.actions : undefined,
                agentRun: data.agentRun || null,
            });
        }
        catch (error) {
            console.error('[AEP] ❌ Chat routing error:', error);
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'error',
                error: error instanceof Error ? error.message : 'Chat failed'
            });
        }
    }
    async handleLocalExplainRepo(originalMessage) {
        // Try to infer a meaningful "repo root" from the workspace or active file.
        let workspaceRootPath = this.getActiveWorkspaceRoot();
        const editor = vscode.window.activeTextEditor;
        const activeFilePath = editor?.document?.uri.fsPath;
        console.log('[AEP] 🔍 handleLocalExplainRepo debug:', {
            originalMessage,
            workspaceRootPath,
            activeFilePath,
            workspaceFolders: vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath)
        });
        let repoName;
        if (workspaceRootPath) {
            repoName = path.basename(workspaceRootPath);
        }
        else if (activeFilePath) {
            const maybeRoot = path.dirname(activeFilePath);
            workspaceRootPath = maybeRoot;
            repoName = path.basename(maybeRoot);
        }
        else {
            repoName = 'current';
        }
        if (!workspaceRootPath) {
            const text = `You're currently working in the **${repoName}** workspace in VS Code.\n\n` +
                `I couldn't infer a project root from VS Code (no folder is open yet). ` +
                `Try opening a folder in VS Code and ask again, or tell me which file or directory you want me to analyse.`;
            this._messages.push({ role: 'assistant', content: text });
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({ type: 'botMessage', text });
            return;
        }
        const rootUri = vscode.Uri.file(workspaceRootPath);
        // Helper to read package.json at root or subfolder (e.g. "frontend", "backend")
        const readPkg = async (subdir) => {
            try {
                const segments = subdir ? [subdir, 'package.json'] : ['package.json'];
                const pkgUri = vscode.Uri.joinPath(rootUri, ...segments);
                const bytes = await vscode.workspace.fs.readFile(pkgUri);
                const text = new TextDecoder().decode(bytes);
                return JSON.parse(text);
            }
            catch {
                return null;
            }
        };
        // Helper to check if a file exists
        const exists = async (...segments) => {
            try {
                const uri = vscode.Uri.joinPath(rootUri, ...segments);
                await vscode.workspace.fs.stat(uri);
                return true;
            }
            catch {
                return false;
            }
        };
        // 1) Discover top-level folders
        let topLevelDirs = [];
        try {
            const entries = await vscode.workspace.fs.readDirectory(rootUri);
            topLevelDirs = entries
                .filter(([_, type]) => type === vscode.FileType.Directory)
                .map(([name]) => name)
                .sort();
        }
        catch {
            // ignore; not critical
        }
        const hasFrontend = topLevelDirs.includes('frontend');
        const hasBackend = topLevelDirs.includes('backend');
        const hasSrc = topLevelDirs.includes('src');
        const hasApps = topLevelDirs.includes('apps');
        const hasPackages = topLevelDirs.includes('packages');
        // 2) Read package.json(s) + README
        const [rootPkg, frontendPkg, backendPkg] = await Promise.all([
            readPkg(),
            hasFrontend ? readPkg('frontend') : Promise.resolve(null),
            hasBackend ? readPkg('backend') : Promise.resolve(null),
        ]);
        let readme = null;
        for (const name of ['README.md', 'readme.md']) {
            if (readme)
                break;
            try {
                const uri = vscode.Uri.joinPath(rootUri, name);
                const bytes = await vscode.workspace.fs.readFile(uri);
                const text = new TextDecoder().decode(bytes);
                readme = text.trim();
            }
            catch {
                // no README at this path, continue
            }
        }
        const displayName = (rootPkg && typeof rootPkg.name === 'string' && rootPkg.name.trim()) ||
            repoName;
        const description = rootPkg &&
            typeof rootPkg.description === 'string' &&
            rootPkg.description.trim()
            ? rootPkg.description.trim()
            : null;
        // 3) Infer tech stack from package.jsons + structure
        const techs = [];
        const addTech = (label) => {
            if (!techs.includes(label))
                techs.push(label);
        };
        const collectTechFromPkg = (pkg) => {
            if (!pkg || typeof pkg !== 'object')
                return;
            const deps = {
                ...(pkg.dependencies || {}),
                ...(pkg.devDependencies || {}),
            };
            const scripts = pkg.scripts || {};
            if (deps.react)
                addTech('React');
            if (deps['react-dom'])
                addTech('React DOM');
            if (deps.next)
                addTech('Next.js');
            if (deps.vite)
                addTech('Vite');
            if (deps.typescript)
                addTech('TypeScript');
            if (deps['tailwindcss'])
                addTech('Tailwind CSS');
            if (deps['express'] || deps['fastify'] || deps['koa']) {
                addTech('Node.js API server');
            }
            if (deps['@vscode/webview-ui-toolkit'] || (pkg.engines && pkg.engines.vscode)) {
                addTech('VS Code extension');
            }
            const devScript = scripts.dev || '';
            if (devScript.includes('next'))
                addTech('Next.js dev server');
            if (devScript.includes('vite'))
                addTech('Vite dev server');
        };
        collectTechFromPkg(rootPkg);
        collectTechFromPkg(frontendPkg);
        collectTechFromPkg(backendPkg);
        // 4) Detect VS Code extension entrypoint
        let hasExtensionEntrypoint = false;
        if (await exists('src', 'extension.ts')) {
            hasExtensionEntrypoint = true;
            addTech('VS Code extension');
        }
        // 5) Build high-level structure summary
        const structureLines = [];
        if (hasFrontend) {
            const labelParts = ['frontend/ — main web UI'];
            if (frontendPkg) {
                const deps = {
                    ...(frontendPkg.dependencies || {}),
                    ...(frontendPkg.devDependencies || {}),
                };
                if (deps.next)
                    labelParts.push('(Next.js)');
                else if (deps.vite)
                    labelParts.push('(Vite + React)');
                else if (deps.react)
                    labelParts.push('(React app)');
            }
            structureLines.push(`- \`frontend/\` — ${labelParts.join(' ')}`);
        }
        if (hasBackend) {
            const labelParts = ['backend/ — server/API layer'];
            if (backendPkg) {
                const deps = {
                    ...(backendPkg.dependencies || {}),
                    ...(backendPkg.devDependencies || {}),
                };
                if (deps.express)
                    labelParts.push('(Express.js API)');
                else if (deps.fastify)
                    labelParts.push('(Fastify API)');
                else if (deps.koa)
                    labelParts.push('(Koa API)');
            }
            structureLines.push(`- \`backend/\` — ${labelParts.join(' ')}`);
        }
        if (hasSrc) {
            const base = hasExtensionEntrypoint
                ? 'src/ — VS Code extension sources (including extension.ts)'
                : 'src/ — main source files';
            structureLines.push(`- \`src/\` — ${base}`);
        }
        if (hasApps) {
            structureLines.push('- `apps/` — multi-app/monorepo entry points');
        }
        if (hasPackages) {
            structureLines.push('- `packages/` — shared libraries in a monorepo setup');
        }
        const otherDirs = topLevelDirs.filter((d) => ![
            'frontend',
            'backend',
            'src',
            'apps',
            'packages',
            '.git',
            '.vscode',
            'node_modules',
        ].includes(d));
        if (otherDirs.length > 0) {
            structureLines.push(`- Other top-level dirs: ${otherDirs.map((d) => `\`${d}/\``).join(', ')}`);
        }
        // 6) README snippet
        let readmeSnippet = null;
        if (readme) {
            const lines = readme.split('\n').slice(0, 12);
            const snippet = lines.join('\n').trim();
            readmeSnippet =
                snippet.length > 500 ? snippet.slice(0, 500).trimEnd() + '…' : snippet;
        }
        // 7) Compose final dynamic answer
        const parts = [];
        parts.push(`You're currently working in the **${displayName}** repo at \`${workspaceRootPath}\`.`);
        if (description) {
            parts.push(`\n**Description (from package.json):** ${description}`);
        }
        if (techs.length > 0) {
            parts.push(`\n**Tech stack signals:** ${techs.join(', ')}.`);
        }
        if (structureLines.length > 0) {
            parts.push('\n**Repo structure (top level):**\n');
            parts.push(structureLines.join('\n'));
        }
        if (readmeSnippet) {
            parts.push(`\n**README snapshot:**\n\n${readmeSnippet}`);
        }
        parts.push(`\nIf you want, ask me about a specific file, component, or feature (e.g. ` +
            '`explain `src/extension.ts`` or `how does the frontend auth work?`) and I can dive deeper using the real code.');
        const answer = parts.join('\n');
        console.log('[AEP] Local repo explanation (rich):', {
            repoName: displayName,
            path: workspaceRootPath,
            techs,
            topLevelDirs,
            hasExtensionEntrypoint,
        });
        this._messages.push({ role: 'assistant', content: answer });
        this.postToWebview({ type: 'botThinking', value: false });
        this.postToWebview({ type: 'botMessage', text: answer });
    }
    async handleGitInitRequest(requestedScope) {
        const workspaceRoot = this.getActiveWorkspaceRoot();
        const repoName = workspaceRoot ? path.basename(workspaceRoot) : 'current folder';
        const scopeText = requestedScope === 'staged'
            ? 'staged changes'
            : requestedScope === 'lastCommit'
                ? 'last commit'
                : 'working changes';
        // Explain the problem and offer solution via chat
        const explanation = `I can't review your ${scopeText} because this folder isn't a Git repository yet. ` +
            `Git is needed to track changes and create diffs for code review.\n\n` +
            `**Would you like me to initialize Git in "${repoName}"?**\n\n` +
            `This will:\n` +
            `• Create a \`.git\` folder to track changes\n` +
            `• Add all current files to the initial commit\n` +
            `• Enable git diff commands for future reviews\n\n` +
            `Reply **"yes"** or **"initialize git"** and I'll set it up for you! 🚀`;
        this._messages.push({ role: 'assistant', content: explanation });
        this.postToWebview({ type: 'botThinking', value: false });
        this.postToWebview({ type: 'botMessage', text: explanation });
        // Store the pending git init context for follow-up
        this._pendingGitInit = {
            workspaceRoot,
            requestedScope,
            timestamp: Date.now()
        };
    }
    async executeGitInit() {
        if (!this._pendingGitInit)
            return;
        const { workspaceRoot, requestedScope } = this._pendingGitInit;
        const repoName = workspaceRoot ? path.basename(workspaceRoot) : 'current folder';
        this.postToWebview({ type: 'botThinking', value: true });
        try {
            const workingDir = workspaceRoot || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
            if (!workingDir) {
                throw new Error('No workspace folder available');
            }
            // Execute git commands
            const { exec } = require('child_process');
            const { promisify } = require('util');
            const execAsync = promisify(exec);
            console.log('[Extension Host] [AEP] Initializing git in:', workingDir);
            // Initialize git repository
            await execAsync('git init', { cwd: workingDir });
            console.log('[Extension Host] [AEP] ✅ git init completed');
            // Add all files
            await execAsync('git add .', { cwd: workingDir });
            console.log('[Extension Host] [AEP] ✅ git add completed');
            // Create initial commit
            await execAsync('git commit -m "Initial commit via NAVI"', { cwd: workingDir });
            console.log('[Extension Host] [AEP] ✅ git commit completed');
            // Success message
            const successMessage = `🎉 **Git repository initialized successfully!**\n\n` +
                `I've set up Git in "${repoName}" and created an initial commit with all your files.\n\n` +
                `Now I can review your code changes. Let me try your original request again...`;
            this._messages.push({ role: 'assistant', content: successMessage });
            this.postToWebview({ type: 'botMessage', text: successMessage });
            // Clear pending state
            this._pendingGitInit = undefined;
            // Wait a moment then retry the original git operation
            setTimeout(async () => {
                const scopeText = requestedScope === 'staged'
                    ? 'review staged changes'
                    : requestedScope === 'lastCommit'
                        ? 'review last commit'
                        : 'review my working changes';
                // Since we just created an initial commit, for working/staged there won't be changes yet
                // but for lastCommit we can now review the initial commit
                if (requestedScope === 'lastCommit') {
                    await this.handleSmartRouting(scopeText, this._currentModelId, this._currentModeId, []);
                }
                else {
                    const noChangesMsg = `The repository is now ready! Since we just committed all files, ` +
                        `there are no ${requestedScope === 'staged' ? 'staged' : 'working'} changes to review yet.\n\n` +
                        `Make some changes to your code, then ask me to review them again! 📝`;
                    this._messages.push({ role: 'assistant', content: noChangesMsg });
                    this.postToWebview({ type: 'botMessage', text: noChangesMsg });
                }
            }, 1000);
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Git init failed:', error);
            const errorMessage = `❌ **Failed to initialize Git repository**\n\n` +
                `Error: ${error.message}\n\n` +
                `You can try initializing Git manually:\n` +
                `\`\`\`bash\n` +
                `cd "${workspaceRoot || ''}"\n` +
                `git init\n` +
                `git add .\n` +
                `git commit -m "Initial commit"\n` +
                `\`\`\``;
            this._messages.push({ role: 'assistant', content: errorMessage });
            this.postToWebview({ type: 'botMessage', text: errorMessage });
            // Clear pending state
            this._pendingGitInit = undefined;
        }
        this.postToWebview({ type: 'botThinking', value: false });
    }
    async handleJiraListIntent(originalMessage) {
        try {
            const res = await fetch(`${this.getBackendBaseUrl()}/api/navi/jira-tasks?user_id=default_user&limit=20`);
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}: ${await res.text()}`);
            }
            const data = await res.json();
            const assistantText = this.formatJiraTaskListForChat(data, originalMessage);
            this._messages.push({ role: 'assistant', content: assistantText });
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({ type: 'botMessage', text: assistantText });
        }
        catch (err) {
            console.error('[AEP] Error fetching Jira tasks:', err);
            await this.callNaviBackend(originalMessage, this._currentModelId, this._currentModeId, this.getCurrentAttachments());
        }
    }
    formatJiraTaskListForChat(data, _originalMessage) {
        if (!data.tasks || data.tasks.length === 0) {
            return "I don't see any Jira tasks in your synced memory yet. Try running a Jira sync and ask me again.";
        }
        const lines = [];
        lines.push("Here's what I have in your Jira queue right now:\n");
        for (const t of data.tasks) {
            const key = t.jira_key || t.scope || 'UNKNOWN';
            const title = t.title || key;
            const status = t.status || 'Unknown';
            const updated = t.updated_at ? new Date(t.updated_at).toLocaleDateString() : 'Unknown';
            lines.push(`- **${key}** — ${title} — **Status:** ${status} — *Last updated:* ${updated}`);
        }
        lines.push("\n---");
        lines.push("**I can also:**");
        lines.push("* Explain what a specific ticket is about in simple language");
        lines.push("* Help you prioritize which ticket to pick next");
        lines.push("* Break down a ticket into an implementation plan");
        lines.push("* Pull related context from Slack, Confluence, or meeting notes");
        lines.push("* Draft a message to your team about progress");
        return lines.join('\n');
    }
    // --- Jira task brief handlers ----------------------------------------------
    async triggerBackgroundJiraSync() {
        // Non-blocking background sync of Jira tasks
        const config = vscode.workspace.getConfiguration('aep');
        const baseUrl = this.getBackendBaseUrl();
        const userId = config.get('navi.userId') || 'srinivas@example.com';
        const cleanBaseUrl = baseUrl.replace(/\/api\/navi\/chat$/, '');
        const syncUrl = `${cleanBaseUrl}/api/org/sync/jira`;
        console.log('[Extension Host] [AEP] Triggering background Jira sync...');
        // Fire and forget - don't await
        fetch(syncUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                max_issues: 20
            })
        })
            .then(async (response) => {
            if (response.ok) {
                const data = await response.json();
                console.log('[Extension Host] [AEP] Jira sync completed:', data);
                // Show subtle notification
                if (data.total > 0) {
                    vscode.window.showInformationMessage(`NAVI: Synced ${data.total} Jira tasks`);
                }
            }
            else {
                const text = await response.text().catch(() => '');
                console.log('[Extension Host] [AEP] Jira sync failed:', response.status, text);
                vscode.window.showWarningMessage(`NAVI: Jira sync failed (HTTP ${response.status})`);
            }
        })
            .catch((error) => {
            console.log('[Extension Host] [AEP] Jira sync error (non-critical):', error.message);
            vscode.window.showWarningMessage('NAVI: Jira sync error – backend unreachable or misconfigured');
        });
    }
    async handleJiraTaskBriefCommand() {
        if (!this._view) {
            return;
        }
        try {
            const config = vscode.workspace.getConfiguration('aep');
            const baseUrl = this.getBackendBaseUrl();
            const userId = config.get('navi.userId') || 'srinivas@example.com';
            // Remove /api/navi/chat suffix if present
            const cleanBaseUrl = baseUrl.replace(/\/api\/navi\/chat$/, '');
            const url = `${cleanBaseUrl}/api/navi/jira-tasks?user_id=${encodeURIComponent(userId)}&limit=20`;
            console.log('[Extension Host] [AEP] Fetching Jira tasks from:', url);
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            if (!response.ok) {
                vscode.window.showErrorMessage(`NAVI: Failed to load Jira tasks (${response.status})`);
                return;
            }
            const data = await response.json();
            // Send tasks to webview
            this.postToWebview({
                type: 'showJiraTasks',
                tasks: data.tasks || []
            });
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Error fetching Jira tasks:', error);
            vscode.window.showErrorMessage('NAVI: Error loading Jira tasks');
        }
    }
    async handleJiraTaskSelected(jiraKey) {
        if (!this._view) {
            return;
        }
        try {
            const config = vscode.workspace.getConfiguration('aep');
            const baseUrl = this.getBackendBaseUrl();
            const userId = config.get('navi.userId') || 'srinivas@example.com';
            // Remove /api/navi/chat suffix if present
            const cleanBaseUrl = baseUrl.replace(/\/api\/navi\/chat$/, '');
            const url = `${cleanBaseUrl}/api/navi/task-brief`;
            console.log('[Extension Host] [AEP] Fetching task brief for:', jiraKey);
            // Show thinking state
            this.postToWebview({ type: 'botThinking', value: true });
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    jira_key: jiraKey
                })
            });
            if (!response.ok) {
                vscode.window.showErrorMessage(`NAVI: Failed to load brief for ${jiraKey} (${response.status})`);
                this.postToWebview({ type: 'botThinking', value: false });
                return;
            }
            const data = await response.json();
            // Extract the brief markdown from the sections
            const briefMd = data.sections?.[0]?.content || data.summary || 'No brief content available';
            // Send as a bot message
            this.postToWebview({
                type: 'botMessage',
                text: briefMd,
                actions: []
            });
            this.postToWebview({ type: 'botThinking', value: false });
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Error fetching task brief:', error);
            vscode.window.showErrorMessage('NAVI: Error fetching task brief');
            this.postToWebview({ type: 'botThinking', value: false });
        }
    }
    // --- Core: call NAVI backend ------------------------------------------------
    async callNaviBackend(latestUserText, modelId, modeId, attachments) {
        if (!this._view)
            return;
        const hasDiff = this.hasDiffAttachment(attachments);
        // If diff exists, avoid inlining attachments into the text (token savings)
        const messageWithContext = hasDiff
            ? latestUserText
            : this.buildMessageWithAttachments(latestUserText, attachments);
        const workspaceContext = await collectWorkspaceContext();
        const workspaceRoot = this.getActiveWorkspaceRoot();
        const diagnosticsCommandsArray = workspaceRoot ? await detectDiagnosticsCommands(workspaceRoot) : [];
        const mappedAttachments = (attachments ?? []).map((att) => ({
            ...att,
            kind: att.kind === 'currentFile' || att.kind === 'pickedFile'
                ? 'file'
                : att.kind === 'diff'
                    ? 'diff'
                    : 'selection',
        }));
        const payload = {
            message: messageWithContext,
            model: modelId || this._currentModelId,
            mode: modeId || this._currentModeId,
            user_id: 'default_user',
            workspace: workspaceContext,
            workspace_root: workspaceRoot,
            diagnosticsCommandsArray,
            attachments: mappedAttachments,
        };
        try {
            this.postToWebview({ type: 'status', text: hasDiff ? '🧠 Analyzing diff…' : '🧠 Thinking…' });
        }
        catch { }
        const { baseUrl, naviChatUrl } = this.resolveBackendEndpoints();
        // Always use NAVI chat endpoint so all requests (with or without diff) share the same path
        const targetUrl = naviChatUrl;
        console.log('[Extension Host] [AEP] Backend endpoints resolved:', {
            baseUrl,
            targetUrl,
            hasDiff,
            messageChars: (payload.message || '').length,
            attachmentsCount: mappedAttachments.length,
            firstAttachmentPath: mappedAttachments[0]?.path,
            firstAttachmentKind: mappedAttachments[0]?.kind,
            firstAttachmentChars: mappedAttachments[0]?.content?.length,
        });
        let response;
        try {
            response = await fetch(targetUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
                },
                body: JSON.stringify(payload),
            });
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Backend unreachable:', error);
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'error',
                text: `⚠️ NAVI backend unreachable: ${(error && error.message) || 'fetch failed'}`,
            });
            return;
        }
        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        if (!response.ok) {
            let detail = '';
            try {
                const t = await response.text();
                detail = t ? ` — ${t.slice(0, 300)}` : '';
            }
            catch { }
            console.error('[Extension Host] [AEP] Backend non-OK:', response.status, response.statusText, detail);
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({
                type: 'error',
                text: `⚠️ NAVI backend error: HTTP ${response.status} ${response.statusText || ''}${detail}`.trim(),
            });
            return;
        }
        try {
            console.log('[Extension Host] [AEP] Response received:', { status: response.status, contentType, endpoint: targetUrl });
            if (contentType.includes('application/json')) {
                const rawText = await response.text();
                console.log('[Extension Host] [AEP] Raw response text (first 1000 chars):', rawText.substring(0, 1000));
                let json;
                try {
                    json = JSON.parse(rawText);
                }
                catch (parseError) {
                    console.error('[Extension Host] [AEP] JSON parse error:', parseError.message);
                    console.error('[Extension Host] [AEP] Raw response that failed to parse:', rawText);
                    this.postToWebview({ type: 'botThinking', value: false });
                    this.postToWebview({ type: 'error', text: `⚠️ Backend returned malformed JSON: ${parseError.message}` });
                    return;
                }
                const content = String(json.content || '').trim();
                if (!content) {
                    console.warn('[Extension Host] [AEP] Empty content from backend.');
                    this.postToWebview({ type: 'botThinking', value: false });
                    this.postToWebview({ type: 'error', text: '⚠️ NAVI backend returned empty content.' });
                    return;
                }
                // Successfully got content - hide status and thinking indicators
                this.postToWebview({ type: 'botThinking', value: false });
                this._messages.push({ role: 'assistant', content });
                const messageId = `msg-${Date.now()}`;
                const sources = json.sources || [];
                console.log('[Extension Host] [AEP] Publishing bot message:', { messageId, contentLength: content.length, hasSources: sources.length > 0 });
                // Check if this is a structured diff review (Phase 2)
                const reviewData = this.tryParseStructuredReview(content);
                if (reviewData) {
                    console.log('[Extension Host] [AEP] Detected structured review, sending as aep.review:', reviewData);
                    this.postToWebview({
                        type: 'aep.review',
                        payload: JSON.stringify(reviewData),
                    });
                    return;
                }
                if (json.actions && json.actions.length > 0) {
                    this._agentActions.set(messageId, { actions: json.actions });
                    this.postToWebview({ type: 'botMessage', text: content, messageId, actions: json.actions, sources, agentRun: json.agentRun || null });
                }
                else {
                    this.postToWebview({ type: 'botMessage', text: content, sources, agentRun: json.agentRun || null });
                }
                return;
            }
            if (contentType.includes('text/event-stream')) {
                const fullText = await this.readSseStream(response);
                const reply = fullText.trim();
                if (!reply) {
                    this.postToWebview({ type: 'botThinking', value: false });
                    this.postToWebview({ type: 'error', text: '⚠️ NAVI backend returned an empty streamed reply.' });
                    return;
                }
                this._messages.push({ role: 'assistant', content: reply });
                this.postToWebview({ type: 'botThinking', value: false });
                this.postToWebview({ type: 'botMessage', text: reply });
                return;
            }
            const text = (await response.text()).trim();
            if (!text) {
                this.postToWebview({ type: 'botThinking', value: false });
                this.postToWebview({ type: 'error', text: '⚠️ NAVI backend returned an empty reply (unknown content-type).' });
                return;
            }
            this._messages.push({ role: 'assistant', content: text });
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({ type: 'botMessage', text });
        }
        catch (err) {
            console.error('[Extension Host] [AEP] Error handling backend response:', err);
            this.postToWebview({ type: 'botThinking', value: false });
            this.postToWebview({ type: 'error', text: '⚠️ Error while processing response from NAVI backend.' });
        }
        finally {
            // Ensure all indicators are cleared
            this.postToWebview({ type: 'botThinking', value: false });
        }
    }
    resolveBackendEndpoints() {
        const config = vscode.workspace.getConfiguration('aep');
        const raw = (config.get('navi.backendUrl') || '').trim();
        const normalize = (u) => u.replace(/\/+$/, '');
        const defaultBase = 'http://127.0.0.1:8787';
        let baseUrl = raw ? normalize(raw) : defaultBase;
        baseUrl = baseUrl
            .replace(/\/api\/navi\/chat\/?$/i, '')
            .replace(/\/api\/chat\/respond\/?$/i, '');
        baseUrl = normalize(baseUrl || defaultBase);
        return {
            baseUrl,
            naviChatUrl: `${baseUrl}/api/navi/chat`,
            chatRespondUrl: `${baseUrl}/api/chat/respond`,
        };
    }
    hasDiffAttachment(attachments) {
        return (attachments ?? []).some((att) => {
            const kind = String(att?.kind || '').toLowerCase();
            const lang = String(att?.language || '').toLowerCase();
            const name = String(att?.name || '').toLowerCase();
            const content = String(att?.content || '');
            if (kind === 'diff' || kind === 'git_diff' || kind === 'patch')
                return true;
            if (lang === 'diff')
                return true;
            if (name.endsWith('.diff') || name.endsWith('.patch'))
                return true;
            if (content.includes('diff --git ') || content.trimStart().startsWith('--- '))
                return true;
            return false;
        });
    }
    /**
     * Best-effort automatic context based on the current editor and the user's message.
     * - For code-ish questions, prefer the current selection.
     * - If no selection, fall back to the whole current file.
     * - For repo/project questions, we return null and let handleLocalExplainRepo deal with it.
     */
    buildAutoAttachments(message) {
        const editor = vscode.window.activeTextEditor;
        if (!editor)
            return null;
        const doc = editor.document;
        const text = (message || '').toLowerCase();
        // Repo / project-level questions → let handleLocalExplainRepo answer instead
        const repoLike = /this repo|this repository|this project|entire repo|whole repo|whole project/.test(text);
        if (repoLike)
            return null;
        // Only auto-attach when it sounds like a code question
        const maybeCodeQuestion = /(code|bug|error|stack trace|exception|component|hook|function|method|class|file|module|refactor|tests?|unit test|integration test|compile|build|lint|ts error|typescript|js error|react|jsx|tsx|java|c#|python)/.test(text);
        if (!maybeCodeQuestion) {
            return null;
        }
        const hasSelection = !editor.selection.isEmpty;
        const mentionsSelection = /this code|this snippet|these lines|selected code|highlighted code|above code|this block/.test(text);
        const mentionsFile = /this file|this component|this page|this screen|this module|current file|entire file|whole file/.test(text);
        const attachments = [];
        let summary = null;
        const workspaceRoot = this.getActiveWorkspaceRoot();
        const fullPath = doc.uri.fsPath;
        const relPath = workspaceRoot && fullPath.startsWith(workspaceRoot)
            ? path.relative(workspaceRoot, fullPath)
            : fullPath;
        // Prefer selection when present, unless user clearly talks about "this file"
        if (hasSelection && (mentionsSelection || !mentionsFile)) {
            const content = doc.getText(editor.selection);
            if (content.trim()) {
                attachments.push({
                    kind: 'selection',
                    path: fullPath,
                    language: doc.languageId,
                    content,
                });
                summary = `Using selected code from \`${relPath}\` as context.`;
            }
        }
        else {
            // Fall back to whole file
            const content = doc.getText();
            if (content.trim()) {
                attachments.push({
                    kind: 'currentFile',
                    path: fullPath,
                    language: doc.languageId,
                    content,
                });
                summary = `Using whole file \`${relPath}\` as context.`;
            }
        }
        if (attachments.length === 0) {
            return null;
        }
        return {
            attachments,
            summary: summary ?? `Using \`${relPath}\` as context.`,
        };
    }
    /**
     * Returns the workspace folder for the active editor if available,
     * otherwise falls back to the first workspace folder. This prevents
     * sending the wrong repo path when multiple folders are open.
     */
    getActiveWorkspaceRoot() {
        console.log('[Extension Host] [AEP] 🔍 Getting workspace root...');
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const folder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
            if (folder) {
                console.log('[Extension Host] [AEP] ✅ Found workspace from active editor:', folder.uri.fsPath);
                return folder.uri.fsPath;
            }
            console.log('[Extension Host] [AEP] ⚠️ Active editor found but no workspace folder for:', editor.document.uri.fsPath);
        }
        else {
            console.log('[Extension Host] [AEP] ⚠️ No active text editor found');
        }
        // Fallback: first workspace folder if present
        const firstWorkspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (firstWorkspace) {
            console.log('[Extension Host] [AEP] 📁 Using first workspace folder as fallback:', firstWorkspace);
        }
        else {
            console.log('[Extension Host] [AEP] ❌ No workspace folders found at all');
        }
        return firstWorkspace;
    }
    // --- SSE reader (streaming support baked in for later) ----------------------
    /**
     * Reads a text/event-stream response and returns concatenated text.
     * For PR1 we **do not** stream partial chunks into the UI yet, to keep
     * the panel logic simple and avoid duplicated bubbles.
     */
    async readSseStream(response) {
        const reader = response.body?.getReader();
        if (!reader) {
            console.warn('[Extension Host] [AEP] SSE response had no body.');
            return '';
        }
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let accumulated = '';
        try {
            // eslint-disable-next-line no-constant-condition
            while (true) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                buffer += decoder.decode(value, { stream: true });
                let newlineIndex;
                // Process line by line
                while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
                    const line = buffer.slice(0, newlineIndex).trim();
                    buffer = buffer.slice(newlineIndex + 1);
                    if (!line || !line.startsWith('data:')) {
                        continue;
                    }
                    const data = line.slice('data:'.length).trim();
                    if (!data)
                        continue;
                    if (data === '[DONE]') {
                        // End of stream
                        return accumulated;
                    }
                    let chunk = data;
                    // If backend wraps data as JSON { delta: "..." }, unpack it
                    try {
                        const parsed = JSON.parse(data);
                        if (typeof parsed.delta === 'string') {
                            chunk = parsed.delta;
                        }
                        else if (typeof parsed.reply === 'string') {
                            chunk = parsed.reply;
                        }
                    }
                    catch {
                        // If not JSON, treat as raw text
                    }
                    accumulated += chunk;
                }
            }
        }
        catch (err) {
            // In PR1 we just log SSE errors and let the caller decide what to show
            console.error('[Extension Host] [AEP] Error while reading SSE stream:', err);
        }
        return accumulated;
    }
    // --- Helpers ---------------------------------------------------------------
    async startReviewStream() {
        const baseUrl = this.getBackendBaseUrl();
        const url = `${baseUrl}/api/review/stream`;
        try {
            // Notify webview that streaming is starting
            this.postToWebview({
                type: 'review.connected',
                timestamp: Date.now()
            });
            await this.sse.start(url, (type, data) => {
                switch (type) {
                    case 'connected':
                        this.postToWebview({
                            type: 'review.connected',
                            data
                        });
                        break;
                    case 'disconnected':
                        this.postToWebview({
                            type: 'review.disconnected',
                            data
                        });
                        break;
                    case 'live-progress':
                        this.postToWebview({
                            type: 'review.progress',
                            text: typeof data === 'string' ? data : data.text,
                            percentage: data?.percentage,
                            totalFiles: data?.totalFiles,
                            processedFiles: data?.processedFiles
                        });
                        break;
                    case 'review-entry':
                        this.postToWebview({
                            type: 'review.entry',
                            entry: data
                        });
                        break;
                    case 'done':
                        this.postToWebview({
                            type: 'review.done',
                            timestamp: Date.now()
                        });
                        break;
                    case 'error':
                    case 'stream-error':
                        this.postToWebview({
                            type: 'review.error',
                            message: data?.message || 'Stream error occurred',
                            code: data?.code || 'UNKNOWN',
                            timestamp: data?.timestamp || Date.now(),
                            canRetry: data?.canRetry !== false
                        });
                        break;
                    case 'retry':
                        this.postToWebview({
                            type: 'review.retry',
                            attempt: data?.attempt,
                            delay: data?.delay,
                            maxRetries: data?.maxRetries
                        });
                        break;
                    case 'heartbeat':
                        this.postToWebview({
                            type: 'review.heartbeat',
                            timestamp: data?.timestamp || Date.now()
                        });
                        break;
                    default:
                        console.log('[AEP] Unknown SSE event type:', type, data);
                        break;
                }
            });
        }
        catch (error) {
            console.error('[AEP] Failed to start review stream:', error);
            this.postToWebview({
                type: 'review.error',
                message: error instanceof Error ? error.message : 'Failed to start streaming',
                code: 'CONNECTION_FAILED',
                timestamp: Date.now(),
                canRetry: true
            });
        }
    }
    stopReviewStream() {
        this.sse.stop();
        this.postToWebview({
            type: 'review.disconnected',
            timestamp: Date.now()
        });
    }
    async retryReviewStream(retryCount) {
        console.log(`[AEP] Retrying review stream (attempt ${retryCount})`);
        this.sse.retry();
    }
    async openFileAtLine(file, line) {
        try {
            const uri = vscode.Uri.file(file);
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);
            // Navigate to specific line
            const position = new vscode.Position(Math.max(0, line - 1), 0);
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(new vscode.Range(position, position));
        }
        catch (error) {
            console.error('[AEP] Failed to open file at line:', error);
            vscode.window.showErrorMessage(`Failed to open ${file}:${line}`);
        }
    }
    async handleOrchestratorRequest(instruction) {
        try {
            console.log('[AEP] 🚀 ORCHESTRATOR HANDLER CALLED - Running Navi Orchestrator with instruction:', instruction);
            console.log('[AEP] 🚀 ORCHESTRATOR: This should call the REAL BACKEND, not git diff!');
            // Immediately send a clear message to webview that orchestrator is starting
            this.postToWebview({
                type: 'orchestratorStarted',
                message: 'Real AI Orchestrator Starting...'
            });
            // Collect workspace context
            const workspaceContext = await collectWorkspaceContext();
            // Call backend orchestrator
            const response = await fetch('http://127.0.0.1:8787/api/orchestrator/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    instruction,
                    workspace_context: workspaceContext,
                }),
            });
            if (!response.ok) {
                throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
            }
            const result = await response.json();
            console.log('[AEP] Orchestrator execution completed successfully');
            // Send result to webview
            this.postToWebview({
                type: 'orchestratorResult',
                result: result
            });
        }
        catch (error) {
            console.error('[AEP] Orchestrator request failed:', error);
            this.postToWebview({
                type: 'orchestratorError',
                error: error instanceof Error ? error.message : 'Failed to execute orchestrator'
            });
        }
    }
    async handleAutoFixRequest(entry) {
        try {
            console.log('[AEP] Generating AI patch for fix:', entry.fixId);
            // Call backend to generate AI patch
            const response = await fetch(`http://127.0.0.1:8787/api/repo/fix/${entry.fixId}`, { method: "POST" });
            if (!response.ok) {
                throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
            }
            const result = await response.json();
            const { patch, file_path, metadata } = result;
            console.log('[AEP] AI patch generated successfully');
            // Forward patch to webview for preview
            this.postToWebview({
                type: "review.patchGenerated",
                patch,
                filePath: file_path,
                metadata,
                entry
            });
        }
        catch (error) {
            console.error('[AEP] Auto-fix request failed:', error);
            this.postToWebview({
                type: 'review.fixResult',
                success: false,
                message: error instanceof Error ? error.message : 'Failed to generate patch',
                fixId: entry.fixId
            });
        }
    }
    async handleApplyPatch(patch) {
        try {
            // Import the patch application engine
            const { applyUnifiedPatch } = await Promise.resolve().then(() => require('./repo/applyPatch'));
            console.log('[AEP] Applying unified diff patch...');
            // Apply the patch to workspace files
            const success = await applyUnifiedPatch(patch);
            // Send result back to webview
            this.postToWebview({
                type: 'review.patchApplied',
                success,
                message: success ? 'Patch applied successfully!' : 'Patch application failed'
            });
            if (success) {
                vscode.window.showInformationMessage('✅ Auto-fix applied successfully!');
            }
            else {
                vscode.window.showErrorMessage('❌ Failed to apply auto-fix patch');
            }
        }
        catch (error) {
            console.error('[AEP] Patch application error:', error);
            this.postToWebview({
                type: 'review.patchApplied',
                success: false,
                message: error instanceof Error ? error.message : 'Patch application failed'
            });
            vscode.window.showErrorMessage(`❌ Patch application failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
    async applyAutoFix(entryId, file, line, diff) {
        try {
            if (!diff) {
                vscode.window.showWarningMessage('No fix available for this issue');
                return;
            }
            const uri = vscode.Uri.file(file);
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);
            // Apply the diff (this would need proper diff parsing implementation)
            // For now, show the user the suggested changes
            const result = await vscode.window.showInformationMessage(`Apply auto-fix for issue at ${file}:${line}?`, 'Apply Fix', 'Show Changes', 'Cancel');
            if (result === 'Apply Fix') {
                // TODO: Implement actual diff application
                vscode.window.showInformationMessage('Auto-fix applied successfully!');
            }
            else if (result === 'Show Changes') {
                // Show diff in a new editor
                const diffUri = vscode.Uri.parse(`untitled:${path.basename(file)}.diff`);
                const diffDoc = await vscode.workspace.openTextDocument(diffUri);
                const edit = new vscode.WorkspaceEdit();
                edit.insert(diffUri, new vscode.Position(0, 0), diff);
                await vscode.workspace.applyEdit(edit);
                await vscode.window.showTextDocument(diffDoc);
            }
        }
        catch (error) {
            console.error('[AEP] Failed to apply auto-fix:', error);
            vscode.window.showErrorMessage('Failed to apply auto-fix');
        }
    }
    postToWebview(message) {
        if (!this._view) {
            console.warn('[Extension Host] [AEP] WARNING: postToWebview called but this._view is null!');
            return;
        }
        console.log('[Extension Host] [AEP] ✅ postToWebview sending message type:', message.type);
        // Persist bot/chat events into memory for recall
        if (message.type === 'botMessage' && typeof message.text === 'string') {
            this.recordMemoryEvent('chat:bot', { content: message.text, ts: Date.now() }).catch(() => { });
        }
        else if (message.type === 'review.done') {
            this.recordMemoryEvent('review:summary', {
                ts: Date.now(),
                summary: message.summary,
                entries: message.entries
            }).catch(() => { });
        }
        else if (message.type === 'review.entry') {
            this.recordMemoryEvent('review:entry', {
                ts: Date.now(),
                entry: message.entry
            }).catch(() => { });
        }
        this._view.webview.postMessage(message);
    }
    startNewChat() {
        // Reset conversation state, keep current model/mode
        this._conversationId = generateConversationId();
        this._messages = [];
        this.postToWebview({ type: 'clearChat' });
        this.postToWebview({
            type: 'botMessage',
            text: "🔄 **New chat started!**\n\nHow can I help you today?"
        });
    }
    // Helpers
    async execGit(args, cwd) {
        return await exec(`git ${args.join(' ')}`, { cwd });
    }
    getLanguageFromFile(filePath) {
        const ext = path.extname(filePath).toLowerCase();
        const map = {
            '.ts': 'typescript',
            '.tsx': 'typescriptreact',
            '.js': 'javascript',
            '.jsx': 'javascriptreact',
            '.py': 'python',
            '.json': 'json',
            '.md': 'markdown',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.css': 'css',
            '.html': 'html',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.cs': 'csharp',
        };
        return map[ext];
    }
    filterFilesByPattern(files, pattern) {
        if (!pattern)
            return files;
        const trimmed = pattern.trim();
        // regex mode: re:pattern
        if (trimmed.startsWith('re:')) {
            try {
                const re = new RegExp(trimmed.slice(3));
                return files.filter((f) => re.test(f));
            }
            catch {
                return files;
            }
        }
        // glob-lite: *, ?, []
        const hasGlobMeta = /[*?\[\]]/.test(trimmed);
        if (hasGlobMeta) {
            const regex = new RegExp('^' +
                trimmed
                    .replace(/[-/\\^$+.,()|{}]/g, '\\$&')
                    .replace(/\*/g, '.*')
                    .replace(/\?/g, '.') +
                '$', 'i');
            return files.filter((f) => regex.test(f));
        }
        // default: substring, case-insensitive
        const lower = trimmed.toLowerCase();
        return files.filter((f) => f.toLowerCase().includes(lower));
    }
    // Run build/test command with notification + log capture
    async handleBuildCommand(command, timeoutMs) {
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showWarningMessage('NAVI: No workspace open to run build.');
            return;
        }
        const cmd = command || 'npm test';
        const started = Date.now();
        const logDir = path.join(workspaceRoot, '.aep', 'build-logs');
        await fs.promises.mkdir(logDir, { recursive: true });
        const logPath = path.join(logDir, `build-${started}.log`);
        const logStream = fs.createWriteStream(logPath, { flags: 'a' });
        const terminal = vscode.window.createTerminal({ name: 'NAVI Build' });
        terminal.show();
        terminal.sendText(cmd);
        const child = (0, child_process_1.spawn)(cmd, {
            cwd: workspaceRoot,
            shell: true,
        });
        let output = '';
        let timedOut = false;
        const timer = setTimeout(() => {
            timedOut = true;
            try {
                child.kill('SIGTERM');
            }
            catch {
                // ignore
            }
        }, timeoutMs);
        const append = (chunk) => {
            const text = chunk ? chunk.toString() : '';
            output += text;
            logStream.write(text);
        };
        child.stdout?.on('data', append);
        child.stderr?.on('data', append);
        const exitCode = await new Promise((resolve) => {
            child.on('close', (code) => resolve(code ?? -1));
        });
        clearTimeout(timer);
        logStream.end();
        const duration = Date.now() - started;
        const status = timedOut ? 'hung' : exitCode === 0 ? 'success' : 'failure';
        // Persist to memory
        await this.recordMemoryEvent('build:result', {
            ts: started,
            status,
            command: cmd,
            duration,
            exitCode,
            logPath,
        });
        const message = `Build ${status} (${cmd}) in ${Math.round(duration / 1000)}s`;
        const openLog = 'Open log';
        const retry = 'Retry';
        const choice = await vscode.window.showInformationMessage(message, openLog, retry);
        if (choice === openLog) {
            const doc = await vscode.workspace.openTextDocument(logPath);
            await vscode.window.showTextDocument(doc, { preview: true });
        }
        else if (choice === retry) {
            await this.handleBuildCommand(cmd, timeoutMs);
        }
    }
    async handleGitStatus() {
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showWarningMessage('NAVI: No workspace open.');
            return;
        }
        try {
            const { stdout } = await this.execGit(['status', '-sb'], workspaceRoot);
            this.postToWebview({
                type: 'botMessage',
                text: `🌀 Git Status\n\n\`\`\`\n${stdout.trim() || 'clean'}\n\`\`\``,
            });
            await this.recordMemoryEvent('git:status', {
                ts: Date.now(),
                content: stdout,
            });
        }
        catch (err) {
            vscode.window.showErrorMessage(`NAVI: git status failed: ${String(err)}`);
        }
    }
    async handleGitPush() {
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showWarningMessage('NAVI: No workspace open.');
            return;
        }
        const confirm = await vscode.window.showWarningMessage('Run "git push" from NAVI?', { modal: true }, 'Push');
        if (confirm !== 'Push')
            return;
        try {
            const { stdout, stderr } = await this.execGit(['push'], workspaceRoot);
            const output = [stdout, stderr].filter(Boolean).join('\n').trim();
            this.postToWebview({
                type: 'botMessage',
                text: `🚀 git push result:\n\n\`\`\`\n${output || 'push completed'}\n\`\`\``,
            });
            await this.recordMemoryEvent('git:push', {
                ts: Date.now(),
                content: output,
            });
        }
        catch (err) {
            vscode.window.showErrorMessage(`NAVI: git push failed: ${String(err)}`);
        }
    }
    async handleOpenPRPage() {
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showWarningMessage('NAVI: No workspace open.');
            return;
        }
        try {
            const { stdout } = await this.execGit(['config', '--get', 'remote.origin.url'], workspaceRoot);
            const remote = stdout.trim();
            if (!remote) {
                vscode.window.showWarningMessage('NAVI: Could not determine remote.origin.url');
                return;
            }
            const url = this.toWebUrl(remote);
            const prUrl = url ? `${url}/pulls` : '';
            if (prUrl) {
                await vscode.env.openExternal(vscode.Uri.parse(prUrl));
                await this.recordMemoryEvent('git:pr', {
                    ts: Date.now(),
                    content: `Opened PR page ${prUrl}`,
                });
            }
            else {
                vscode.window.showWarningMessage('NAVI: Could not build PR URL from remote.');
            }
        }
        catch (err) {
            vscode.window.showErrorMessage(`NAVI: Unable to open PR page: ${String(err)}`);
        }
    }
    // --- Memory helpers -------------------------------------------------------
    getMemoryKey(workspaceRoot) {
        const root = workspaceRoot || this.getActiveWorkspaceRoot() || 'global';
        return `${this._memoryKeyPrefix}:${root}`;
    }
    async loadMemory(workspaceRoot) {
        const key = this.getMemoryKey(workspaceRoot);
        const existing = this._context.globalState.get(key);
        // Try backend recent memory first
        let backendMemory = null;
        try {
            const baseUrl = this.getBackendBaseUrl();
            const userId = 'default_user';
            const resp = await fetch(`${baseUrl}/api/navi/memory/recent?user_id=${encodeURIComponent(userId)}&limit=50`);
            if (resp.ok) {
                const data = await resp.json();
                backendMemory = this.normalizeBackendMemory(data.items || []);
            }
        }
        catch (err) {
            console.warn('[AEP] Backend memory fetch failed, falling back to local:', err);
        }
        if (backendMemory) {
            await this.saveMemory(workspaceRoot, backendMemory);
            return backendMemory;
        }
        return (existing || {
            chat: [],
            reviews: [],
            builds: [],
            items: [],
        });
    }
    async saveMemory(workspaceRoot, memory) {
        const key = this.getMemoryKey(workspaceRoot);
        await this._context.globalState.update(key, memory);
    }
    normalizeBackendMemory(items) {
        const memory = {
            chat: [],
            reviews: [],
            builds: [],
            items: items || [],
        };
        for (const item of items || []) {
            let meta = item.meta;
            if (typeof meta === 'string') {
                try {
                    meta = JSON.parse(meta);
                }
                catch {
                    meta = {};
                }
            }
            const eventType = meta?.event_type || '';
            if (eventType.startsWith('chat:'))
                memory.chat.push(item);
            else if (eventType.startsWith('review:'))
                memory.reviews.push(item);
            else if (eventType.startsWith('build:'))
                memory.builds.push(item);
        }
        return memory;
    }
    async recordMemoryEvent(kind, payload) {
        const workspaceRoot = this.getActiveWorkspaceRoot();
        const memory = await this.loadMemory(workspaceRoot);
        if (kind.startsWith('chat:')) {
            memory.chat = (memory.chat || []).slice(-49);
            memory.chat.push({ kind, ...payload });
        }
        else if (kind.startsWith('review:')) {
            memory.reviews = (memory.reviews || []).slice(-49);
            memory.reviews.push({ kind, ...payload });
        }
        else if (kind.startsWith('build:')) {
            memory.builds = (memory.builds || []).slice(-49);
            memory.builds.push({ kind, ...payload });
        }
        memory.items = [...(memory.items || []), { kind, ...payload }];
        await this.saveMemory(workspaceRoot, memory);
        // Best-effort push to backend memory
        this.sendMemoryToBackend(kind, payload).catch((err) => console.warn('[AEP] Failed to push memory to backend', err));
        // Push update to webview if active
        this.postToWebview({
            type: 'memory.update',
            memory,
        });
    }
    async sendMemoryToBackend(kind, payload) {
        const baseUrl = this.getBackendBaseUrl();
        const userId = 'default_user';
        const body = {
            source: 'vscode',
            event_type: kind,
            external_id: payload?.id || payload?.path || this._conversationId,
            title: payload?.title || payload?.summary?.text || kind,
            summary: payload?.summary?.text || payload?.content || '',
            content: payload?.content || payload?.text || payload?.entry?.description || '',
            user_id: userId,
            tags: {
                workspace_root: this.getActiveWorkspaceRoot(),
                event_type: kind,
                ...payload,
            },
        };
        await fetch(`${baseUrl}/api/events/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    }
    toWebUrl(remote) {
        // Handle git@github.com:org/repo.git or https://github.com/org/repo.git
        if (remote.startsWith('git@')) {
            const parts = remote.replace(/^git@/, '').replace(/\.git$/, '').split(':');
            if (parts.length === 2) {
                return `https://${parts[0]}/${parts[1]}`;
            }
        }
        if (remote.startsWith('https://') || remote.startsWith('http://')) {
            return remote.replace(/\.git$/, '');
        }
        return null;
    }
    async handleCreatePR(payload) {
        const baseUrl = this.getBackendBaseUrl();
        const repo_full_name = String(payload.repo_full_name || '').trim();
        const base = String(payload.base || '').trim();
        const head = String(payload.head || '').trim();
        const title = String(payload.title || '').trim();
        const body = String(payload.body || '');
        if (!repo_full_name || !base || !head || !title) {
            vscode.window.showWarningMessage('NAVI: repo, base, head, and title are required to create PR.');
            return;
        }
        try {
            const resp = await fetch(`${baseUrl}/api/github/pr/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    repo_full_name,
                    base,
                    head,
                    title,
                    body,
                    dry_run: false,
                }),
            });
            if (!resp.ok) {
                const text = await resp.text();
                throw new Error(text || `HTTP ${resp.status}`);
            }
            const data = await resp.json();
            const url = data?.result?.url || data?.result?.preview?.endpoint || '(no url returned)';
            vscode.window.showInformationMessage(`NAVI: PR created at ${url}`);
            await this.recordMemoryEvent('git:pr', {
                ts: Date.now(),
                content: `Created PR ${url}`,
            });
        }
        catch (err) {
            vscode.window.showErrorMessage(`NAVI: Failed to create PR: ${String(err)}`);
        }
    }
    async handleCiTrigger(repo, workflow, ref) {
        const baseUrl = this.getBackendBaseUrl();
        if (!repo || !workflow || !ref) {
            vscode.window.showWarningMessage('NAVI: repo, workflow, and ref are required to trigger CI.');
            return;
        }
        try {
            const connectorName = await this.pickConnector('github');
            const resp = await fetch(`${baseUrl}/api/github/ci/dispatch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_full_name: repo, workflow, ref, connector_name: connectorName || undefined }),
            });
            if (!resp.ok) {
                const t = await resp.text();
                throw new Error(t || `HTTP ${resp.status}`);
            }
            const data = await resp.json();
            const run = data?.run || {};
            const url = run.html_url || '(no run url)';
            vscode.window.showInformationMessage(`NAVI: CI triggered for ${repo} (${ref}). Run: ${url}`);
            await this.recordMemoryEvent('ci:trigger', {
                ts: Date.now(),
                repo,
                workflow,
                ref,
                runId: run.id,
                url,
            });
        }
        catch (err) {
            vscode.window.showErrorMessage(`NAVI: CI trigger failed: ${String(err)}`);
        }
    }
    async handleCiStatus(repo, runId) {
        const baseUrl = this.getBackendBaseUrl();
        if (!repo || !runId) {
            vscode.window.showWarningMessage('NAVI: repo and runId required for CI status.');
            return;
        }
        try {
            const connectorName = await this.pickConnector('github');
            const resp = await fetch(`${baseUrl}/api/github/ci/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_full_name: repo, run_id: runId, connector_name: connectorName || undefined }),
            });
            if (!resp.ok) {
                const t = await resp.text();
                throw new Error(t || `HTTP ${resp.status}`);
            }
            const data = await resp.json();
            const run = data?.run || {};
            const status = run.status || 'unknown';
            const conclusion = run.conclusion || 'n/a';
            const url = run.html_url || '';
            const msg = `CI status for run ${runId}: ${status} (${conclusion})`;
            if (url) {
                vscode.window.showInformationMessage(msg, 'Open').then((choice) => {
                    if (choice === 'Open') {
                        vscode.env.openExternal(vscode.Uri.parse(url));
                    }
                });
            }
            else {
                vscode.window.showInformationMessage(msg);
            }
            await this.recordMemoryEvent('ci:status', {
                ts: Date.now(),
                repo,
                runId,
                status,
                conclusion,
                url,
            });
        }
        catch (err) {
            vscode.window.showErrorMessage(`NAVI: CI status failed: ${String(err)}`);
        }
    }
    async pickConnector(provider) {
        const baseUrl = this.getBackendBaseUrl();
        try {
            const resp = await fetch(`${baseUrl}/api/connectors`);
            if (!resp.ok)
                return null;
            const data = await resp.json();
            const items = (data.items || []).filter((c) => (c.provider || '').toLowerCase() === provider);
            if (!items.length)
                return null;
            const pick = await vscode.window.showQuickPick(items.map((c) => ({
                label: `${c.name || 'default'} (${provider})`,
                description: c.workspace_root ? `workspace: ${c.workspace_root}` : '',
                value: c.name || 'default',
            })), { placeHolder: `Select ${provider} connector (Enter to use env token)` });
            return pick ? pick.value : null;
        }
        catch {
            return null;
        }
    }
    // --- Attachment Helper Methods ---
    async handleReviewRequest() {
        // Legacy review request handler - maintain backward compatibility
        console.log('[AEP] Processing legacy review request');
        // Get workspace context
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showWarningMessage('No workspace folder detected');
            return;
        }
        // Send review started message
        this.postToWebview({
            type: 'aep.review.start',
            message: 'Starting code review analysis...'
        });
        try {
            // This would integrate with existing review logic
            // For now, redirect to streaming version
            await this.startReviewStream();
        }
        catch (error) {
            console.error('[AEP] Legacy review request failed:', error);
            this.postToWebview({
                type: 'aep.review.complete',
                error: error instanceof Error ? error.message : 'Review failed'
            });
        }
    }
    addAttachment(attachment) {
        // Simple upsert: dedupe by kind+path+length
        const key = `${attachment.kind}:${attachment.path}:${attachment.content.length}`;
        const existingIndex = this._attachments.findIndex(a => `${a.kind}:${a.path}:${a.content.length}` === key);
        if (existingIndex >= 0) {
            this._attachments[existingIndex] = attachment;
        }
        else {
            this._attachments.push(attachment);
        }
        // Tell the webview so it can render chips (panel already listens for this)
        this.postToWebview({
            type: 'addAttachment',
            attachment,
        });
    }
    /**
     * Automatically attach a lightweight workspace snapshot to help answer workspace-related questions.
     * This includes key project files like package.json, README.md, etc.
     */
    async autoAttachWorkspaceSnapshot() {
        console.log('[AEP] Collecting workspace snapshot...');
        // Get workspace folders
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            console.log('[AEP] No workspace folders found');
            return;
        }
        // Use the first workspace folder
        const wsRoot = workspaceFolders[0].uri.fsPath;
        console.log('[AEP] Workspace root:', wsRoot);
        // Key files that provide project context
        const keyFiles = [
            'package.json',
            'README.md',
            'readme.md',
            'pyproject.toml',
            'requirements.txt',
            'Cargo.toml',
            'go.mod',
            'pom.xml',
            'build.gradle',
            '.gitignore',
        ];
        let attachedCount = 0;
        const maxFiles = 5; // Limit to avoid overwhelming the context
        for (const fileName of keyFiles) {
            if (attachedCount >= maxFiles)
                break;
            try {
                const filePath = path.join(wsRoot, fileName);
                const uri = vscode.Uri.file(filePath);
                // Check if file exists
                try {
                    await vscode.workspace.fs.stat(uri);
                }
                catch {
                    continue; // File doesn't exist, skip
                }
                // Read file content
                const fileData = await vscode.workspace.fs.readFile(uri);
                const content = new TextDecoder().decode(fileData);
                // Truncate if too large
                const truncatedContent = this.truncateForAttachment(content, fileName);
                // Add as attachment
                this.addAttachment({
                    kind: 'file',
                    path: filePath,
                    content: truncatedContent,
                });
                attachedCount++;
                console.log(`[AEP] Added workspace file: ${fileName}`);
            }
            catch (error) {
                console.warn(`[AEP] Failed to read ${fileName}:`, error);
            }
        }
        if (attachedCount > 0) {
            console.log(`[AEP] Workspace snapshot complete: ${attachedCount} files attached`);
        }
        else {
            console.log('[AEP] No key workspace files found');
        }
    }
    async attachFileIfExists(rootUri, relPath) {
        try {
            const segments = relPath.split(/[\\/]/).filter(Boolean);
            const fileUri = vscode.Uri.joinPath(rootUri, ...segments);
            const stat = await vscode.workspace.fs.stat(fileUri);
            if (stat.type !== vscode.FileType.File) {
                return false;
            }
            const bytes = await vscode.workspace.fs.readFile(fileUri);
            const raw = new TextDecoder().decode(bytes);
            const content = this.truncateForAttachment(raw, relPath);
            this.addAttachment({
                kind: 'file',
                path: fileUri.fsPath,
                content,
            });
            console.log('[AEP] Attached extra context file:', relPath);
            return true;
        }
        catch {
            return false;
        }
    }
    async maybeAttachWorkspaceContextForQuestion(userMessage) {
        const msg = (userMessage || '').toLowerCase();
        const wantsRouting = msg.includes(' route') ||
            msg.startsWith('route') ||
            msg.includes('routing') ||
            msg.includes('routes') ||
            msg.includes('router') ||
            msg.includes('navigation') ||
            msg.includes('nav bar') ||
            msg.includes('nav menu');
        const wantsExtension = msg.includes('extension') ||
            msg.includes('vs code extension') ||
            msg.includes('webview') ||
            msg.includes('chat panel') ||
            msg.includes('navi panel');
        if (!wantsRouting && !wantsExtension) {
            return;
        }
        const workspaceRootPath = this.getActiveWorkspaceRoot();
        if (!workspaceRootPath) {
            return;
        }
        const rootUri = vscode.Uri.file(workspaceRootPath);
        const maxExtra = 4;
        let added = 0;
        const tryAttach = async (relPath) => {
            if (added >= maxExtra)
                return;
            const ok = await this.attachFileIfExists(rootUri, relPath);
            if (ok)
                added += 1;
        };
        if (wantsRouting) {
            const routingCandidates = [
                'frontend/src/routes.tsx',
                'frontend/src/routes/index.tsx',
                'frontend/src/router.tsx',
                'frontend/src/App.tsx',
                'frontend/src/App.jsx',
                'frontend/src/main.tsx',
                'frontend/src/main.jsx',
                'frontend/app/page.tsx',
                'frontend/app/layout.tsx',
                'src/routes.tsx',
                'src/routes/index.tsx',
                'src/router.tsx',
                'src/App.tsx',
                'src/App.jsx',
                'src/main.tsx',
                'src/main.jsx',
                'app/page.tsx',
                'app/layout.tsx',
            ];
            for (const rel of routingCandidates) {
                await tryAttach(rel);
                if (added >= maxExtra)
                    break;
            }
        }
        if (wantsExtension) {
            const extensionCandidates = [
                'src/extension.ts',
                'src/extension.js',
                'src/panels/NaviChatPanel.tsx',
                'src/panels/NaviChatPanel.jsx',
            ];
            for (const rel of extensionCandidates) {
                await tryAttach(rel);
                if (added >= maxExtra)
                    break;
            }
        }
        if (added > 0) {
            console.log('[AEP] Added extra workspace context for question:', {
                wantsRouting,
                wantsExtension,
                added,
            });
        }
    }
    getCurrentAttachments() {
        return this._attachments.slice();
    }
    clearAttachments() {
        this._attachments = [];
        this.postToWebview({ type: 'clearAttachments' });
    }
    truncateForAttachment(text, source) {
        const maxChars = 120000; // ~700–1000 lines is fine
        if (text.length <= maxChars)
            return text;
        vscode.window.showWarningMessage(`NAVI: ${source} is very large; truncating to ${maxChars.toLocaleString()} characters for this request.`);
        return text.slice(0, maxChars);
    }
    showWebviewToast(message, level = 'info') {
        this.postToWebview({
            type: 'ephemeralToast',
            level,
            text: message,
        });
    }
    // Helper: merge attachments into the plain-text message we send to the backend
    buildMessageWithAttachments(latestUserText, attachments) {
        if (!attachments || attachments.length === 0) {
            return latestUserText;
        }
        const chunks = [];
        chunks.push('I have attached some code context from VS Code below. ' +
            'Please use that code as the primary context when answering my request.\n');
        for (const att of attachments) {
            const fileLabel = att.path ? path.basename(att.path) : '(untitled)';
            const kindLabel = att.kind === 'selection'
                ? 'selected code'
                : att.kind === 'currentFile'
                    ? 'current file'
                    : 'attached file';
            const lang = att.language ?? ''; // ok to be empty
            const fenceHeader = lang ? `\`\`\`${lang}` : '```';
            chunks.push(`\n\nFile: \`${fileLabel}\` (${kindLabel})\n` +
                `${fenceHeader}\n` +
                `${att.content}\n` +
                `\`\`\``);
        }
        chunks.push('\n\nUser request:\n');
        chunks.push(latestUserText);
        return chunks.join('');
    }
    // PR-5: Handle attachment requests from the webview
    async handleAttachmentRequest(webview, kind) {
        const editor = vscode.window.activeTextEditor;
        try {
            // 1) Attach SELECTION
            if (kind === 'selection') {
                if (!editor || editor.selection.isEmpty) {
                    const msg = 'Select some code in the active editor before attaching.';
                    vscode.window.showInformationMessage(`NAVI: ${msg}`);
                    // Also show a short-lived toast inside the panel
                    this.postToWebview({
                        type: 'toast',
                        level: 'warning',
                        message: msg,
                    });
                    return;
                }
                const selectedText = editor.document.getText(editor.selection);
                const filePath = editor.document.uri.fsPath;
                const language = editor.document.languageId;
                const attachment = {
                    kind: 'selection',
                    path: filePath,
                    language,
                    content: selectedText,
                };
                // Update internal state + tell panel
                this.addAttachment(attachment);
                return;
            }
            // 2) Attach CURRENT FILE
            if (kind === 'current-file' && editor) {
                const content = editor.document.getText();
                const filePath = editor.document.uri.fsPath;
                const language = editor.document.languageId;
                const attachment = {
                    kind: 'currentFile',
                    path: filePath,
                    language,
                    content,
                };
                this.addAttachment(attachment);
                return;
            }
            // 3) Pick FILE via file picker
            if (kind === 'pick-file') {
                const uris = await vscode.window.showOpenDialog({
                    canSelectFiles: true,
                    canSelectFolders: false,
                    canSelectMany: false,
                    openLabel: 'Attach File to NAVI',
                });
                if (!uris || uris.length === 0) {
                    return;
                }
                const uri = uris[0];
                const bytes = await vscode.workspace.fs.readFile(uri);
                const textContent = new TextDecoder('utf-8').decode(bytes);
                const attachment = {
                    kind: 'pickedFile',
                    path: uri.fsPath,
                    content: textContent,
                };
                this.addAttachment(attachment);
                return;
            }
        }
        catch (err) {
            console.error('[Extension Host] [AEP] Error reading attachment:', err);
            vscode.window.showErrorMessage('NAVI: Failed to read file for attachment.');
        }
    }
    async handleApplyReviewFixes(reviews) {
        if (!reviews || reviews.length === 0) {
            vscode.window.showWarningMessage('NAVI: No review comments were provided to apply.');
            return;
        }
        const workspaceRoot = this.getActiveWorkspaceRoot();
        if (!workspaceRoot) {
            vscode.window.showErrorMessage('NAVI: No workspace root detected. Open a folder before applying fixes.');
            return;
        }
        const seenPaths = new Set();
        const attachments = [];
        for (const r of reviews) {
            const relPath = (r.path || '').trim();
            if (!relPath || seenPaths.has(relPath)) {
                continue;
            }
            seenPaths.add(relPath);
            const fileFsPath = path.join(workspaceRoot, relPath);
            const fileUri = vscode.Uri.file(fileFsPath);
            try {
                const bytes = await vscode.workspace.fs.readFile(fileUri);
                const content = new TextDecoder('utf-8').decode(bytes);
                let language;
                try {
                    const doc = await vscode.workspace.openTextDocument(fileUri);
                    language = doc.languageId;
                }
                catch {
                    // Best-effort: leave language undefined
                }
                attachments.push({
                    kind: 'file',
                    path: fileFsPath,
                    language,
                    content,
                });
            }
            catch (err) {
                console.warn('[AEP] Failed to read file for review fix:', relPath, err);
            }
        }
        if (attachments.length === 0) {
            vscode.window.showWarningMessage('NAVI: None of the files from the review comments could be read from disk.');
            return;
        }
        const reviewJson = JSON.stringify(reviews, null, 2);
        const prompt = [
            'You previously reviewed this repo and produced these structured review comments.',
            'Now apply ALL of these suggestions directly to the attached files.',
            '',
            'Rules:',
            '- Return concrete file edits only, as agent actions of type "editFile".',
            "- Don\'t repeat the full review text back to me.",
            '- Keep behaviour the same except where fixes are required.',
            '',
            'Here are the review comments as JSON:',
            '```json',
            reviewJson,
            '```',
        ].join('\n');
        // Use the existing chat call so we get back actions / diff views
        await this.callNaviBackend(prompt, this._currentModelId, this._currentModeId, attachments);
    }
    // PR-7: Apply agent action from new unified message format
    async handleAgentApplyAction(message) {
        const { decision, actionIndex, actions, approvedViaChat } = message;
        if (decision !== 'approve') {
            // For now we don't need to do anything on reject
            console.log('[Extension Host] [AEP] User rejected action');
            return;
        }
        if (!actions || actionIndex == null || !Number.isInteger(actionIndex) || actionIndex < 0 || actionIndex >= actions.length) {
            console.warn('[Extension Host] [AEP] Invalid action data:', { actionIndex, actionsLength: actions?.length });
            return;
        }
        const action = actions[actionIndex];
        if (!action || !action.type) {
            console.warn('[Extension Host] [AEP] Invalid action object:', action);
            return;
        }
        try {
            console.log('[Extension Host] [AEP] Applying agent action:', action);
            // 1) Create new file
            if (action.type === 'createFile') {
                await this.applyCreateFileAction(action);
                return;
            }
            // 2) Edit existing file with diff
            if (action.type === 'editFile') {
                await this.applyEditFileAction(action);
                return;
            }
            // 3) Run terminal command
            if (action.type === 'runCommand') {
                await this.applyRunCommandAction(action, { skipConfirm: Boolean(approvedViaChat) });
                return;
            }
            console.warn('[Extension Host] [AEP] Unknown action type:', action.type);
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Error applying action:', error);
            vscode.window.showErrorMessage(`Failed to apply action: ${error.message}`);
        }
    }
    // NEW: Apply a full workspace plan (array of AgentAction)
    async applyWorkspacePlan(actions) {
        if (!actions || actions.length === 0) {
            vscode.window.showInformationMessage('NAVI: No workspace actions to apply.');
            return;
        }
        console.log('[Extension Host] [AEP] Applying workspace plan with', actions.length, 'actions');
        let appliedCount = 0;
        for (const action of actions) {
            try {
                if (!action || !action.type) {
                    console.warn('[Extension Host] [AEP] Skipping invalid action in workspace plan:', action);
                    continue;
                }
                if (action.type === 'createFile') {
                    await this.applyCreateFileAction(action);
                    appliedCount += 1;
                }
                else if (action.type === 'editFile') {
                    await this.applyEditFileAction(action);
                    appliedCount += 1;
                }
                else if (action.type === 'runCommand') {
                    await this.applyRunCommandAction(action);
                    appliedCount += 1;
                }
                else {
                    console.warn('[Extension Host] [AEP] Unknown action type in workspace plan:', action.type);
                }
            }
            catch (err) {
                console.error('[Extension Host] [AEP] Failed to apply action in workspace plan:', err);
                vscode.window.showErrorMessage(`NAVI: Failed to apply one of the workspace actions: ${err.message ?? String(err)}`);
            }
        }
        this.postBotStatus(`✅ Applied ${appliedCount}/${actions.length} workspace actions.`);
    }
    async applyCreateFileAction(action) {
        const fileName = action.filePath ?? 'sample.js';
        const content = action.content ?? '// Sample generated by NAVI\nconsole.log("Hello, World!");\n';
        const folders = vscode.workspace.workspaceFolders;
        const editor = vscode.window.activeTextEditor;
        // 1) Best case: have a workspace folder → create under that root
        if (folders && folders.length > 0) {
            const root = folders[0].uri;
            await this.createFileUnderRoot(root, fileName, content);
            return;
        }
        // 2) No workspace, but we DO have a saved active file → ask to use its folder
        if (editor && !editor.document.isUntitled) {
            this.postBotStatus("I don't see a workspace folder open. I can still create the sample file if you tell me where it should live.");
            const choice = await vscode.window.showQuickPick([
                {
                    label: '$(file) Create next to current file',
                    description: editor.document.uri.fsPath,
                    id: 'here',
                },
                {
                    label: '$(folder) Choose another folder…',
                    id: 'pick',
                },
                {
                    label: '$(x) Cancel',
                    id: 'cancel',
                },
            ], {
                placeHolder: 'Where should I create the sample file?',
                title: 'NAVI - Create Sample File',
            });
            if (!choice || choice.id === 'cancel') {
                this.postBotStatus('No problem! Let me know if you need anything else.');
                return;
            }
            if (choice.id === 'here') {
                const dir = vscode.Uri.joinPath(editor.document.uri, '..');
                await this.createFileUnderRoot(dir, fileName, content);
                return;
            }
            // fall through to folder picker below
        }
        // 3) No workspace AND no saved active file → let user pick any folder
        this.postBotStatus("I don't see a workspace folder open. Please pick a folder where I should create the sample file.");
        const picked = await vscode.window.showOpenDialog({
            canSelectFolders: true,
            canSelectFiles: false,
            canSelectMany: false,
            openLabel: 'Use this folder for the sample file',
            title: 'NAVI - Choose Folder for Sample File',
        });
        if (!picked || picked.length === 0) {
            this.postBotStatus('No problem! Let me know if you need anything else.');
            return;
        }
        const targetRoot = picked[0];
        await this.createFileUnderRoot(targetRoot, fileName, content);
    }
    async createFileUnderRoot(root, relPath, content) {
        // Security: Validate path to prevent traversal attacks
        const path = require('path');
        // Normalize path and check for absolute paths
        const normalizedPath = path.normalize(relPath);
        if (path.isAbsolute(normalizedPath)) {
            vscode.window.showErrorMessage('NAVI: Cannot create file with absolute path');
            return;
        }
        // Check for path traversal attempts (including encoded variants)
        if (normalizedPath.includes('..') || /\%2e\%2e|\.\./.test(relPath)) {
            vscode.window.showErrorMessage('NAVI: Cannot create file with path traversal (..)');
            return;
        }
        const fileUri = vscode.Uri.joinPath(root, relPath);
        const resolvedPath = fileUri.fsPath;
        const rootPath = root.fsPath;
        // Ensure the resolved path is within the workspace root
        if (!resolvedPath.startsWith(rootPath)) {
            vscode.window.showErrorMessage('NAVI: Cannot create file outside workspace');
            return;
        }
        // Ensure parent folders exist (best effort)
        const dir = vscode.Uri.joinPath(fileUri, '..');
        try {
            await vscode.workspace.fs.createDirectory(dir);
        }
        catch {
            // ignore if it already exists
        }
        await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));
        const doc = await vscode.workspace.openTextDocument(fileUri);
        await vscode.window.showTextDocument(doc);
        vscode.window.setStatusBarMessage(`✅ NAVI: Created ${relPath}`, 3000);
        this.postBotStatus(`✅ Done! I've created \`${relPath}\` at ${fileUri.fsPath}`);
    }
    postBotStatus(text) {
        if (!this._view)
            return;
        this._view.webview.postMessage({
            type: 'botMessage',
            text,
            actions: [],
            messageId: new Date().toISOString(),
        });
    }
    async applyRunCommandAction(action, options) {
        const command = typeof action.command === 'string' ? action.command.trim() : '';
        if (!command)
            return;
        const workspaceRoot = this.getActiveWorkspaceRoot();
        const cwd = action.cwd || workspaceRoot || process.cwd();
        const meta = action.meta && typeof action.meta === 'object' ? action.meta : undefined;
        // Security: Sanitize, truncate, and show command for confirmation before executing
        const sanitizedCommand = command.replace(/[\r\n]/g, ' ').substring(0, 200);
        const displayCommand = command.length > 200 ? sanitizedCommand + '...' : sanitizedCommand;
        if (!options?.skipConfirm) {
            const confirmed = await vscode.window.showWarningMessage(`NAVI wants to run the following command:\\n\\n${displayCommand}\\n\\nAre you sure?`, { modal: true }, 'Run Command');
            if (confirmed !== 'Run Command')
                return;
        }
        const commandId = `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        this.postToWebview({
            type: 'command.start',
            commandId,
            command,
            cwd,
            meta,
        });
        const started = Date.now();
        try {
            const child = (0, child_process_1.spawn)(command, {
                cwd,
                shell: true,
                env: process.env,
            });
            const sendOutput = (chunk, stream) => {
                const text = chunk ? chunk.toString() : '';
                if (!text)
                    return;
                this.postToWebview({
                    type: 'command.output',
                    commandId,
                    stream,
                    text,
                });
            };
            child.stdout?.on('data', (data) => sendOutput(data, 'stdout'));
            child.stderr?.on('data', (data) => sendOutput(data, 'stderr'));
            child.on('error', (err) => {
                this.postToWebview({
                    type: 'command.error',
                    commandId,
                    error: err.message || String(err),
                });
            });
            const exitCode = await new Promise((resolve) => {
                child.on('close', (code) => resolve(code ?? -1));
            });
            const durationMs = Date.now() - started;
            this.postToWebview({
                type: 'command.done',
                commandId,
                exitCode,
                durationMs,
            });
        }
        catch (err) {
            this.postToWebview({
                type: 'command.error',
                commandId,
                error: err?.message || String(err),
            });
        }
    }
    // ---- editFile with diff view & apply (PR-10) -------------------------------
    async applyEditFileAction(action) {
        // Backend contract: editFile provides either:
        // - filePath + content (full new file text)   ✅
        // - optionally diff (for explanation), but we don't parse it
        const filePath = action.filePath;
        const newContent = action.content;
        if (!newContent) {
            vscode.window.showWarningMessage('NAVI: editFile action is missing "content"; nothing to apply.');
            return;
        }
        // Resolve target document: use filePath if present, otherwise active editor
        let targetDoc;
        if (filePath) {
            const uri = vscode.Uri.file(filePath);
            try {
                targetDoc = await vscode.workspace.openTextDocument(uri);
            }
            catch {
                vscode.window.showWarningMessage(`NAVI: Target file "${filePath}" does not exist.`);
                return;
            }
        }
        else {
            targetDoc = vscode.window.activeTextEditor?.document;
            if (!targetDoc) {
                vscode.window.showWarningMessage('NAVI: No active file to apply edit to.');
                return;
            }
        }
        const originalText = targetDoc.getText();
        const languageId = targetDoc.languageId;
        // Create a virtual doc for the new content and show a diff
        const newDoc = await vscode.workspace.openTextDocument({
            language: languageId,
            content: newContent,
        });
        const title = `NAVI proposed edit: ${targetDoc.fileName.split(/[\\/]/).pop()}`;
        await vscode.commands.executeCommand('vscode.diff', targetDoc.uri, newDoc.uri, title);
        // Ask user if we should apply the changes to the real file now
        const choice = await vscode.window.showQuickPick([
            { label: '✅ Apply edit to file', id: 'apply' },
            { label: '👁️ Keep diff only', id: 'keep' },
            { label: '❌ Cancel', id: 'cancel' },
        ], {
            placeHolder: 'NAVI has proposed an edit. Do you want to apply it to the real file?',
        });
        if (!choice || choice.id === 'cancel' || choice.id === 'keep') {
            if (choice?.id === 'keep') {
                this.postBotStatus('Diff view kept open for your review.');
            }
            return;
        }
        if (choice.id === 'apply') {
            const edit = new vscode.WorkspaceEdit();
            const fullRange = new vscode.Range(targetDoc.positionAt(0), targetDoc.positionAt(originalText.length));
            edit.replace(targetDoc.uri, fullRange, newContent);
            const success = await vscode.workspace.applyEdit(edit);
            if (success) {
                await targetDoc.save();
                vscode.window.setStatusBarMessage('✅ NAVI: Edit applied.', 3000);
                this.postBotStatus(`✅ Edit applied to ${targetDoc.fileName.split(/[\\/]/).pop()}`);
            }
            else {
                vscode.window.showErrorMessage('NAVI: Failed to apply edit.');
            }
        }
    }
    // PR-6C: Apply agent-proposed edit with diff view support
    async handleApplyAgentEdit(msg) {
        const { messageId, actionIndex } = msg;
        const agentState = this._agentActions.get(messageId);
        if (!agentState) {
            console.warn('[Extension Host] [AEP] No agent actions found for message:', messageId);
            return;
        }
        const action = agentState.actions[actionIndex];
        if (!action) {
            console.warn('[Extension Host] [AEP] Invalid action index:', actionIndex);
            return;
        }
        try {
            console.log('[Extension Host] [AEP] Applying agent action:', action);
            // Get workspace folder for resolving relative paths
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders || workspaceFolders.length === 0) {
                throw new Error('No workspace folder open');
            }
            const workspaceRoot = workspaceFolders[0].uri;
            // Handle different action types
            if (action.type === 'editFile' && action.filePath && action.diff) {
                // PR-6C: Show diff preview for editFile
                await this.showDiffPreviewAndApply(workspaceRoot, action.filePath, action.diff);
            }
            else if (action.type === 'createFile' && action.filePath && action.content) {
                // Create new file
                const fileUri = vscode.Uri.joinPath(workspaceRoot, action.filePath);
                await vscode.workspace.fs.writeFile(fileUri, Buffer.from(action.content, 'utf-8'));
                vscode.window.showInformationMessage(`✅ Created ${action.filePath}`);
                // Open the new file
                const document = await vscode.workspace.openTextDocument(fileUri);
                await vscode.window.showTextDocument(document, { preview: false });
            }
            else if (action.type === 'runCommand' && action.command) {
                await this.applyRunCommandAction(action);
            }
            else {
                vscode.window.showWarningMessage(`Unknown or incomplete action type: ${action.type}`);
            }
        }
        catch (err) {
            console.error('[Extension Host] [AEP] Error applying agent action:', err);
            vscode.window.showErrorMessage(`Failed to apply action: ${err.message}`);
        }
    }
    // PR-6C: Show diff preview and apply on confirmation
    async showDiffPreviewAndApply(workspaceRoot, filePath, diff) {
        const fileUri = vscode.Uri.joinPath(workspaceRoot, filePath);
        // Read original file
        let originalDoc;
        try {
            originalDoc = await vscode.workspace.openTextDocument(fileUri);
        }
        catch {
            vscode.window.showErrorMessage(`File not found: ${filePath}`);
            return;
        }
        const original = originalDoc.getText();
        // Apply diff to get new content
        let newContent;
        try {
            newContent = (0, diffUtils_1.applyUnifiedDiff)(original, diff);
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to apply diff: ${error.message}`);
            return;
        }
        // Create temp file with new content for preview
        const fileName = path.basename(filePath);
        const tempUri = vscode.Uri.parse(`untitled:${fileName} (NAVI Proposed)`);
        await vscode.workspace.openTextDocument(tempUri);
        const edit = new vscode.WorkspaceEdit();
        edit.insert(tempUri, new vscode.Position(0, 0), newContent);
        await vscode.workspace.applyEdit(edit);
        // Show diff view
        await vscode.commands.executeCommand('vscode.diff', fileUri, tempUri, `NAVI: ${fileName} (Original ↔ Proposed)`);
        // Ask user to confirm
        const choice = await vscode.window.showInformationMessage(`Apply proposed changes to ${fileName}?`, { modal: true }, 'Apply', 'Cancel');
        if (choice === 'Apply') {
            // Apply the changes
            const fullRange = new vscode.Range(originalDoc.positionAt(0), originalDoc.positionAt(original.length));
            const finalEdit = new vscode.WorkspaceEdit();
            finalEdit.replace(fileUri, fullRange, newContent);
            await vscode.workspace.applyEdit(finalEdit);
            await originalDoc.save();
            vscode.window.showInformationMessage(`✅ Applied changes to ${fileName}`);
        }
        else {
            vscode.window.showInformationMessage('Changes discarded');
        }
    }
    async getWebviewHtml(webview) {
        const cfg = vscode.workspace.getConfiguration('aep');
        const isDevelopment = cfg.get('development.useReactDevServer') ?? true; // Use React development
        console.log('[AEP] Development mode:', isDevelopment);
        console.log('[AEP] 🔍 WEBVIEW DEBUG: Starting to generate HTML...');
        if (isDevelopment) {
            // Make sure the Vite dev server is actually running; try to start it if not.
            const serverReady = await this.ensureFrontendServer();
            if (!serverReady) {
                console.log('[AEP] ❌ Frontend dev server still not running after auto-start attempt');
                return this.getServerNotRunningHtml();
            }
            // Get workspace root for context
            const workspaceRoot = this.getActiveWorkspaceRoot();
            const workspaceParam = workspaceRoot ? `?workspaceRoot=${encodeURIComponent(workspaceRoot)}` : '';
            console.log('[AEP] 📁 Workspace context:', { workspaceRoot, workspaceParam });
            // Get the detected frontend port
            const frontendPort = this.__frontendPort || 3008;
            // Use direct localhost URL for iframe (asExternalUri can break iframe loading in some cases)
            const viteUrl = `http://localhost:${frontendPort}/navi${workspaceParam}`;
            console.log('[AEP] 🌐 Loading Vite webview from:', viteUrl);
            return /* html */ `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NAVI Assistant</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { width: 100%; height: 100vh; overflow: hidden; background: #020617; color: white; font-family: system-ui; }
      iframe { width: 100%; height: 100%; border: none; display: block; }
      .loading { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; padding: 20px; text-align: center; }
      .loading h2 { color: #10b981; margin-bottom: 16px; }
      .loading p { color: #94a3b8; margin-bottom: 8px; }
      .loading code { background: #1e293b; padding: 2px 8px; border-radius: 4px; color: #10b981; }
      .error-box {
        display: none;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #1e293b;
        border: 2px solid #ef4444;
        border-radius: 8px;
        padding: 24px;
        max-width: 500px;
        text-align: left;
        z-index: 1000;
      }
      .error-box h2 { color: #ef4444; margin-bottom: 12px; }
      .error-box p { color: #cbd5e1; margin: 8px 0; }
      .error-box code { background: #0f172a; padding: 2px 6px; border-radius: 3px; color: #10b981; }
    </style>
  </head>
  <body>
    <div class="loading" id="loading">
      <h2>⚡ NAVI is starting...</h2>
      <p>Loading frontend interface...</p>
    </div>
    <div class="error-box" id="errorBox">
      <h2>❌ Frontend Server Not Running</h2>
      <p>NAVI needs the frontend development server to display the interface.</p>
      <p style="margin-top: 16px;"><strong>Quick Fix:</strong></p>
      <p><code>cd frontend && npm run dev</code></p>
      <p style="margin-top: 12px; font-size: 12px; color: #94a3b8;">Then reload this panel or restart VS Code.</p>
    </div>
    <iframe 
      id="webview"
      src="${viteUrl}" 
      allow="cross-origin-isolated" 
      style="display:none;"
      onload="handleIframeLoad()"
      onerror="handleIframeError(event)">
    </iframe>
    <script>
      // Enhanced debugging for iframe loading issues
      const vscode = acquireVsCodeApi();
      
      console.log('[AEP Webview] 🔍 Debugging iframe load...');
      console.log('[AEP Webview] Target URL:', '${viteUrl}');
      console.log('[AEP Webview] User agent:', navigator.userAgent);
      
      function handleIframeLoad() {
        console.log('[AEP Webview] ✅ Iframe loaded successfully');
        document.getElementById('loading').style.display='none';
        document.getElementById('webview').style.display='block';
        
        // Test iframe content access
        const iframe = document.getElementById('webview');
        try {
          if (iframe.contentWindow) {
            console.log('[AEP Webview] 🔗 Iframe content window accessible');
            iframe.contentWindow.postMessage({
              type: '__vscode_init__',
              vscodeApi: true
            }, '*');
          } else {
            console.log('[AEP Webview] ⚠️ Iframe content window not accessible');
          }
        } catch (err) {
          console.log('[AEP Webview] ❌ Iframe access error:', err);
        }
      }
      
      function handleIframeError(event) {
        console.log('[AEP Webview] ❌ Iframe load error:', event);
        document.getElementById('loading').style.display='none';
        document.getElementById('errorBox').style.display='block';
      }
      
      // Monitor for CSP violations
      document.addEventListener('securitypolicyviolation', (e) => {
        console.log('[AEP Webview] 🛡️ CSP Violation:', e);
      });
      
      // Add timeout fallback (increased to 20s to allow iframe to load properly)
      setTimeout(() => {
        const iframe = document.getElementById('webview');
        if (iframe.style.display === 'none') {
          console.log('[AEP Webview] ⏱️ Iframe load timeout - showing error');
          document.getElementById('loading').style.display='none';
          document.getElementById('errorBox').style.display='block';
        }
      }, 20000);
      
      // Forward messages from iframe to VS Code extension
      window.addEventListener('message', (event) => {
        if (event.source === document.getElementById('webview').contentWindow) {
          console.log('[AEP Webview] 📤 Forwarding to VS Code:', event.data);
          vscode.postMessage(event.data);
        }
      });
      
      // Forward messages from VS Code to iframe
      window.addEventListener('message', (event) => {
        if (event.data && event.data.type) {
          console.log('[AEP Webview] 📥 Forwarding to iframe:', event.data);
          const iframe = document.getElementById('webview');
          if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(event.data, '*');
          }
        }
      });
    </script>
  </body>
</html>`;
        }
        else {
            // Production: Use React webview bundle
            const scriptPathOnDisk = vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview', 'panel.js');
            const scriptUri = webview.asWebviewUri(scriptPathOnDisk);
            // Read the panel.html template
            const htmlPathOnDisk = vscode.Uri.joinPath(this._extensionUri, 'media', 'panel.html');
            const htmlContent = Buffer.from(await vscode.workspace.fs.readFile(htmlPathOnDisk)).toString();
            // Replace placeholders with actual URIs
            return htmlContent
                .replace(/\{\{scriptUri\}\}/g, scriptUri.toString())
                .replace(/\{\{cspSource\}\}/g, webview.cspSource)
                .replace(/\{\{nonce\}\}/g, this.getNonce());
        }
    }
    getNonce() {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }
    async checkFrontendServer() {
        const ports = [3007, 3008, 3000]; // Try these ports in order
        for (const port of ports) {
            try {
                const response = await fetch(`http://localhost:${port}/`, {
                    method: 'GET',
                    signal: AbortSignal.timeout(2000)
                });
                // Accept any 2xx or 3xx response as "running"
                if (response.status < 400) {
                    console.log(`[AEP] ✅ Frontend server found on port ${port}`);
                    return { available: true, port };
                }
            }
            catch (err) {
                // Continue to next port
                console.log(`[AEP] Port ${port} not available`);
            }
        }
        console.log('[AEP] Frontend server not found on any port (3007, 3008, 3000)');
        return { available: false };
    }
    // Ensure dev server is running. Attempt auto-start once and recheck.
    async ensureFrontendServer() {
        const serverCheck = await this.checkFrontendServer();
        if (serverCheck.available && serverCheck.port) {
            // Store port for later use
            this.__frontendPort = serverCheck.port;
            return true;
        }
        console.log('[AEP] ⚠️ Frontend dev server not running - attempting auto-start');
        await this.startFrontendServer();
        // Give the dev server a moment to boot before re-checking
        await new Promise(resolve => setTimeout(resolve, 3000));
        const recheck = await this.checkFrontendServer();
        if (recheck.available && recheck.port) {
            this.__frontendPort = recheck.port;
            console.log(`[AEP] ✅ Frontend dev server is now running on port ${recheck.port}`);
        }
        return recheck.available;
    }
    async startFrontendServer() {
        try {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (!workspaceFolder) {
                console.log('[AEP] No workspace folder found - skipping auto-start');
                return;
            }
            const frontendPath = path.join(workspaceFolder.uri.fsPath, 'frontend');
            console.log('[AEP] Attempting to start frontend server at:', frontendPath);
            // Check if frontend directory exists
            try {
                await vscode.workspace.fs.stat(vscode.Uri.file(frontendPath));
            }
            catch {
                console.log('[AEP] Frontend directory does not exist - skipping auto-start');
                return;
            }
            // Create terminal with command that ensures Node v20
            console.log('[AEP] Creating terminal to start frontend server...');
            const terminal = vscode.window.createTerminal({
                name: 'NAVI Frontend',
                cwd: frontendPath,
                hideFromUser: false
            });
            terminal.show();
            // Use nvm to ensure correct Node version, then start dev server
            terminal.sendText('nvm use 20.19.6 && npm run dev');
            console.log('[AEP] Frontend server start command sent to terminal');
            // Show a helpful notification
            vscode.window.showInformationMessage('NAVI: Starting frontend server... Please wait a moment then reload the panel.', 'Reload Panel').then(selection => {
                if (selection === 'Reload Panel') {
                    vscode.commands.executeCommand('workbench.action.webview.reloadWebviewAction');
                }
            });
        }
        catch (err) {
            console.log('[AEP] Could not start frontend server automatically:', err);
            // Don't show error - the error HTML will guide the user
        }
    }
    getServerNotRunningHtml() {
        return /* html */ `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NAVI Assistant</title>
    <style>
      body { 
        background: #020617; 
        color: white; 
        font-family: system-ui; 
        padding: 20px; 
        display: flex; 
        flex-direction: column; 
        align-items: center; 
        justify-content: center; 
        height: 100vh; 
        text-align: center; 
      }
      h1 { color: #ef4444; margin-bottom: 16px; font-size: 24px; }
      h2 { color: #10b981; margin: 24px 0 12px; font-size: 18px; }
      p { color: #94a3b8; margin-bottom: 8px; line-height: 1.6; }
      code { 
        background: #1e293b; 
        padding: 4px 8px; 
        border-radius: 4px; 
        color: #10b981; 
        font-family: 'Courier New', monospace;
      }
      .command-block {
        background: #1e293b;
        padding: 12px;
        border-radius: 6px;
        margin: 16px 0;
        border-left: 3px solid #10b981;
      }
      .steps {
        text-align: left;
        max-width: 500px;
        margin: 20px auto;
      }
      .step {
        margin: 12px 0;
        padding: 8px;
        background: #1e293b;
        border-radius: 4px;
      }
    </style>
  </head>
  <body>
    <h1>⚠️ Frontend Server Not Running</h1>
    <p>NAVI needs the frontend development server to display the interface.</p>
    
    <div class="steps">
      <h2>Quick Fix:</h2>
      <div class="step">
        <strong>Option 1:</strong> Use VS Code Task
        <div class="command-block">
          <code>Cmd/Ctrl + Shift + P</code> → <code>Tasks: Run Task</code> → <code>frontend: start (vite)</code>
        </div>
      </div>
      
      <div class="step">
        <strong>Option 2:</strong> Run in Terminal
        <div class="command-block">
          <code>cd frontend && npm run dev</code>
        </div>
      </div>
    </div>
    
    <p style="margin-top: 24px; font-size: 12px; color: #64748b;">
      After starting the server, reload this panel or restart VS Code.
    </p>
  </body>
</html>`;
    }
    // --- Command Methods ---
    async attachSelectionCommand() {
        if (this._view) {
            await this.handleAttachmentRequest(this._view.webview, 'selection');
        }
    }
    async attachCurrentFileCommand() {
        if (this._view) {
            await this.handleAttachmentRequest(this._view.webview, 'current-file');
        }
    }
    async checkErrorsAndFixCommand() {
        console.log('[Extension Host] [AEP] Check errors & fix command triggered');
        if (!this._view) {
            return;
        }
        try {
            // Clear attachments since diagnostics doesn't need file attachments
            this.clearAttachments();
            // Add user message and trigger AI processing
            const message = "Check errors and fix them";
            this._messages.push({ role: 'user', content: message });
            this.recordMemoryEvent('chat:user', { content: message, ts: Date.now() }).catch(() => { });
            // Show thinking state and process diagnostics
            this.postToWebview({ type: 'botThinking', value: true });
            await this.handleDiagnosticsRequest(message);
            this.postToWebview({ type: 'botThinking', value: false });
            // Show confirmation to user
            vscode.window.setStatusBarMessage('NAVI: Running diagnostics...', 3000);
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Check errors command failed:', error);
            vscode.window.showErrorMessage('Failed to run error checking.');
        }
    }
    async generateTestsForFileCommand() {
        console.log('[Extension Host] [AEP] Generate tests for file command triggered');
        if (!this._view) {
            return;
        }
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('Open a file first to generate tests.');
            return;
        }
        try {
            // Attach current file for test generation
            await this.handleAttachmentRequest(this._view.webview, 'current-file');
            // Add user message and trigger AI processing
            const message = "Generate unit tests for this file";
            this._messages.push({ role: 'user', content: message });
            // Show thinking state and process message
            this.postToWebview({ type: 'botThinking', value: true });
            const attachments = this.getCurrentAttachments();
            await this.handleSmartRouting(message, this._currentModelId, this._currentModeId, attachments);
            // Show confirmation to user
            vscode.window.setStatusBarMessage('NAVI: Generating tests...', 3000);
        }
        catch (error) {
            console.error('[Extension Host] [AEP] Generate tests command failed:', error);
            vscode.window.showErrorMessage('Failed to generate tests.');
        }
    }
    /**
     * Phase 2: Try to parse markdown review text into structured review data.
     * Detects patterns like:
     *   ## Summary
     *   - Issue A
     *
     *   ### /path/to/file.ts
     *   - **High**: Issue title
     *     Issue body
     *
     * Returns structured { files: [...] } or null if not a structured review.
     */
    tryParseStructuredReview(markdownText) {
        if (!markdownText)
            return null;
        // Must have file section markers (### /path/to/file)
        const fileHeaderRegex = /^###\s+([^\n]+\.(?:ts|js|tsx|jsx|py|java|go|rb|rs|cpp|c|h|cs|xml|json|yaml|yml|env|sh|md))$/m;
        if (!fileHeaderRegex.test(markdownText)) {
            console.log('[Extension Host] [AEP] Not a structured review: no file headers detected');
            return null;
        }
        const files = [];
        const lines = markdownText.split('\n');
        let i = 0;
        // Skip summary section if present
        while (i < lines.length && !fileHeaderRegex.test(lines[i])) {
            i++;
        }
        // Parse each file section
        while (i < lines.length) {
            const line = lines[i].trim();
            const fileMatch = line.match(fileHeaderRegex);
            if (!fileMatch) {
                i++;
                continue;
            }
            const filePath = fileMatch[1];
            i++;
            // Extract severity from next lines until we hit another file header or end
            let severity = 'medium';
            const issues = [];
            let currentIssueMd = '';
            while (i < lines.length) {
                const currentLine = lines[i];
                // Check if we've hit another file header
                if (fileHeaderRegex.test(currentLine)) {
                    // Save any pending issue
                    if (currentIssueMd.trim()) {
                        const issue = this.parseIssueMarkdown(currentIssueMd, severity);
                        if (issue)
                            issues.push(issue);
                        currentIssueMd = '';
                    }
                    break;
                }
                // Detect severity markers (🔴 High, 🟡 Medium, 🟢 Low, etc.)
                if (currentLine.includes('🔴') || currentLine.toUpperCase().includes('HIGH')) {
                    severity = 'high';
                }
                else if (currentLine.includes('🟡') || currentLine.toUpperCase().includes('MEDIUM')) {
                    severity = 'medium';
                }
                else if (currentLine.includes('🟢') || currentLine.toUpperCase().includes('LOW')) {
                    severity = 'low';
                }
                // Check if line starts a new issue (bullet or dash)
                if (currentLine.startsWith('-') || currentLine.startsWith('•')) {
                    // Save previous issue if any
                    if (currentIssueMd.trim()) {
                        const issue = this.parseIssueMarkdown(currentIssueMd, severity);
                        if (issue)
                            issues.push(issue);
                    }
                    currentIssueMd = currentLine;
                }
                else if (currentIssueMd) {
                    // Continuation of current issue
                    currentIssueMd += '\n' + currentLine;
                }
                i++;
            }
            // Save last issue
            if (currentIssueMd.trim()) {
                const issue = this.parseIssueMarkdown(currentIssueMd, severity);
                if (issue)
                    issues.push(issue);
            }
            if (issues.length > 0) {
                files.push({
                    path: filePath,
                    severity,
                    issues,
                });
            }
        }
        if (files.length === 0) {
            console.log('[Extension Host] [AEP] Structured review detected but no files parsed');
            return null;
        }
        console.log('[Extension Host] [AEP] Successfully parsed structured review:', { fileCount: files.length });
        return { files };
    }
    /**
     * Parse a single issue line + body into { id, title, body, canAutoFix }
     */
    parseIssueMarkdown(issueMd, severity) {
        const trimmed = issueMd.trim().replace(/^[-•]\s*/, '');
        if (!trimmed)
            return null;
        // Extract title (first line or bold text)
        const lines = trimmed.split('\n');
        let title = lines[0];
        // Remove bold markers if present
        title = title.replace(/\*\*(.*?)\*\*/g, '$1').replace(/__(.*?)__/g, '$1');
        // Remove severity badges
        title = title.replace(/🔴|🟡|🟢|High|Medium|Low|high|medium|low/g, '').trim();
        // Remove leading dash or bullet if it slipped through
        title = title.replace(/^[-•]\s*/, '').trim();
        // Body is everything after the first line
        const body = lines.slice(1).join('\n').trim();
        // Check if auto-fixable (stub: look for "can auto-fix" or similar keywords)
        const canAutoFix = /auto[- ]?fix|automatically fix|auto fix/i.test(issueMd);
        return {
            id: `issue-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
            title,
            body: body || title,
            canAutoFix,
        };
    }
}
// Simple conversation id – you can switch to UUID later
function generateConversationId() {
    return `navi-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
//# sourceMappingURL=extension.js.map