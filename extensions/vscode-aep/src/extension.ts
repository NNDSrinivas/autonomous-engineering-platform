// src/extension.ts
import * as vscode from 'vscode';
import * as path from 'path';
import * as child_process from 'child_process';
import * as util from 'util';
import { applyUnifiedDiff } from './diffUtils';
import { ConnectorsPanel } from './connectorsPanel';

const exec = util.promisify(child_process.exec);

// Perfect Workspace Context Collection
async function collectWorkspaceContext(): Promise<any> {
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
async function detectDiagnosticsCommands(workspaceRoot: string): Promise<string[]> {
  const cmds: string[] = [];
  const fs = await import('fs');

  try {
    // 1) Node.js projects: look at package.json
    const pkgPath = path.join(workspaceRoot, 'package.json');
    if (fs.existsSync(pkgPath)) {
      const text = fs.readFileSync(pkgPath, 'utf8');
      const pkg = JSON.parse(text);
      const scripts = pkg.scripts ?? {};

      for (const [name, cmd] of Object.entries<string>(scripts)) {
        const nameMatch = /^(lint|test|check|validate|build)$/i.test(name) ||
          /lint|test|check/i.test(name);
        const cmdMatch = /eslint|tslint|jest|vitest|mocha|cypress|playwright|tsc|npm test|yarn test|pnpm test/i.test(cmd);

        if (nameMatch || cmdMatch) {
          // Prefer npm run for consistency
          if (pkg.packageManager?.startsWith('yarn')) {
            cmds.push(`yarn ${name}`);
          } else if (pkg.packageManager?.startsWith('pnpm')) {
            cmds.push(`pnpm ${name}`);
          } else {
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
          if (content.includes('black')) cmds.push('python -m black --check .');
          if (content.includes('mypy')) cmds.push('python -m mypy .');
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
  } catch (error) {
    console.warn('[Extension Host] [AEP] Error detecting diagnostics commands:', error);
    return [];
  }
}

type Role = 'user' | 'assistant' | 'system';

interface NaviMessage {
  role: Role;
  content: string;
}

// Intent classification types
type NaviIntent =
  | 'greeting'
  | 'jira_list'
  | 'jira_ticket'
  | 'jira_priority'
  | 'code'
  | 'workspace'
  | 'general'
  | 'other';

// interface IntentResponse {
//   intent: NaviIntent;
// }

// PR-5: File attachment interface for type safety
interface FileAttachment {
  kind: 'selection' | 'currentFile' | 'pickedFile' | 'file' | 'diff';
  path: string;
  language?: string;
  content: string;
}

// Review comment structure from backend
interface ReviewCommentFromBackend {
  path: string;
  line?: number | null;
  summary: string;
  comment: string;
  level?: 'nit' | 'suggestion' | 'issue' | 'critical';
  suggestion?: string;
}

// Diff scope types
type DiffScope = 'working' | 'staged' | 'lastCommit';

// interface NaviChatRequest {
//   id: string;
//   model: string;
//   mode: string;
//   messages: NaviMessage[];
//   stream: boolean;
//   attachments?: FileAttachment[]; // PR-5: Strongly-typed file attachments
// }

interface AgentAction {
  type: 'editFile' | 'createFile' | 'runCommand';
  filePath?: string;
  description?: string;
  content?: string;  // For createFile
  diff?: string;     // For editFile
  command?: string;  // For runCommand
}

interface NaviChatResponseJson {
  role: string;
  content: string;
  actions?: AgentAction[]; // PR-6C: Agent-proposed actions
  agentRun?: any; // Present only when real multi-step agent ran
  sources?: Array<{ name: string; type: string; url: string; connector?: string }>; // Sources for provenance
}

// PR-4: Storage keys for persistent model/mode selection
const STORAGE_KEYS = {
  modelId: 'aep.navi.modelId',
  modelLabel: 'aep.navi.modelLabel',
  modeId: 'aep.navi.modeId',
  modeLabel: 'aep.navi.modeLabel',
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

async function getGitDiff(
  scope: DiffScope,
  provider?: NaviWebviewProvider,
): Promise<string | null> {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showErrorMessage(
      "NAVI: Open a folder in VS Code before using Git review actions.",
    );
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
      vscode.window.showWarningMessage(
        'NAVI: This folder is not a Git repository. ' +
          'Quick actions like "Review working changes" only work in a Git project.\n\n' +
          'Run "git init" (and make at least one commit) in the terminal, or open a Git-backed repo.',
      );
      return null;
    }
  } catch (err) {
    console.error("[AEP][Git] rev-parse failed:", err);
    return null;
  }

  // 2) Show status so we can see what Git thinks has changed
  try {
    const { stdout: statusOut } = await exec("git status --porcelain=v1", {
      cwd,
    });
    console.log(
      "[AEP][Git] status --porcelain:\n" + (statusOut || "<empty>"),
    );

    if (!statusOut.trim()) {
      // No tracked or untracked changes at all
      console.log("[AEP][Git] Working tree is clean (no changes).");
    }
  } catch (err) {
    console.error("[AEP][Git] git status failed:", err);
  }

  // 3) Build the actual diff command
  let cmd: string;
  switch (scope) {
    case "staged":
      cmd = "git diff --cached --unified=3";
      break;
    case "lastCommit":
      cmd = "git show --patch --unified=3 HEAD";
      break;
    case "working":
    default:
      // HEAD vs working tree (staged + unstaged)
      cmd = "git diff HEAD --unified=3";
      break;
  }

  console.log("[AEP][Git] Running diff command:", cmd);

  try {
    const { stdout } = await exec(cmd, { cwd });
    const diff = stdout.trim();

    console.log(
      `[AEP][Git] ${cmd} length:`,
      diff.length,
      "chars",
    );

    if (!diff) {
      const label =
        scope === "staged"
          ? "staged changes"
          : scope === "lastCommit"
            ? "last commit"
            : "working tree changes";

      vscode.window.showInformationMessage(
        `NAVI: No ${label} found (git ${
          scope === "lastCommit" ? "show" : "diff"
        } is empty).`,
      );
      return null;
    }

    // Optionally clamp very huge diffs to avoid backend 422 on insane payloads
    const MAX_DIFF_CHARS = 250_000;
    if (diff.length > MAX_DIFF_CHARS) {
      console.warn(
        "[AEP][Git] Diff too large, truncating to",
        MAX_DIFF_CHARS,
        "chars",
      );
      return diff.slice(0, MAX_DIFF_CHARS) + "\n\n…[truncated large diff]…\n";
    }

    return diff;
  } catch (err) {
    console.error("[AEP][Git] Diff command failed:", err);
    return null;
  }
}

export function activate(context: vscode.ExtensionContext) {
  const provider = new NaviWebviewProvider(context.extensionUri, context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      // Make sure this matches the view id in package.json
      'aep.chatView',
      provider
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('aep.attachSelection', async () => {
      await provider.attachSelectionCommand();
    }),
    vscode.commands.registerCommand('aep.attachCurrentFile', async () => {
      await provider.attachCurrentFileCommand();
    }),
    vscode.commands.registerCommand('aep.checkErrorsAndFix', async () => {
      await provider.checkErrorsAndFixCommand();
    }),
    vscode.commands.registerCommand('aep.generateTestsForFile', async () => {
      await provider.generateTestsForFileCommand();
    })
  );
}

export function deactivate() {
  // nothing yet
}

class NaviWebviewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private _extensionUri: vscode.Uri;
  private _context: vscode.ExtensionContext;

  // Conversation state
  private _conversationId: string;
  private _messages: NaviMessage[] = [];
  private _agentActions = new Map<string, { actions: AgentAction[] }>(); // PR-6: Track agent actions
  private _currentModelId: string = DEFAULT_MODEL.id;
  private _currentModelLabel: string = DEFAULT_MODEL.label;
  private _currentModeId: string = DEFAULT_MODE.id;
  private _currentModeLabel: string = DEFAULT_MODE.label;

  // Git initialization state
  private _pendingGitInit?: {
    workspaceRoot: string | undefined;
    requestedScope: DiffScope;
    timestamp: number;
  };

  // Attachment state
  private _attachments: FileAttachment[] = [];

  // Git warning state - only show once per session
  public _gitWarningShown: boolean = false;

  constructor(extensionUri: vscode.Uri, context: vscode.ExtensionContext) {
    this._extensionUri = extensionUri;
    this._context = context;
    this._conversationId = generateConversationId();

    // PR-4: Load persisted model/mode from storage
    this._currentModelId = context.globalState.get<string>(STORAGE_KEYS.modelId) ?? DEFAULT_MODEL.id;
    this._currentModelLabel = context.globalState.get<string>(STORAGE_KEYS.modelLabel) ?? DEFAULT_MODEL.label;
    this._currentModeId = context.globalState.get<string>(STORAGE_KEYS.modeId) ?? DEFAULT_MODE.id;
    this._currentModeLabel = context.globalState.get<string>(STORAGE_KEYS.modeLabel) ?? DEFAULT_MODE.label;
  }

  private getBackendBaseUrl(): string {
    const config = vscode.workspace.getConfiguration('aep');
    const raw = (config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000/api/navi/chat').trim();

    // Turn http://127.0.0.1:8000/api/navi/chat → http://127.0.0.1:8000
    try {
      const url = new URL(raw);
      url.pathname = url.pathname.replace(/\/api\/navi\/chat\/?$/, '');
      url.search = '';
      url.hash = '';
      return url.toString().replace(/\/$/, '');
    } catch {
      return 'http://127.0.0.1:8000';
    }
  }

  public async resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
      enableCommandUris: true
    };

    webviewView.webview.html = await this.getWebviewHtml(webviewView.webview);

    // PR-4: Hydrate model/mode state from storage after webview loads
    webviewView.webview.onDidReceiveMessage(async (msg: any) => {
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
            if (!url) return;
            try {
              await vscode.env.openExternal(vscode.Uri.parse(url));
            } catch (e) {
              vscode.window.showErrorMessage('Failed to open external URL');
            }
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

            // Then send welcome message
            this.postToWebview({
              type: 'botMessage',
              text: "Hello! I'm **NAVI**, your autonomous engineering assistant.\n\nI can help you with:\n\n- Code explanations and reviews\n- Refactoring and testing\n- Documentation generation\n- Engineering workflow automation\n\nHow can I help you today?"
            });

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
            } catch (err) {
              console.error('[AEP] Clipboard write failed', err);
              this.postToWebview({
                type: 'clipboard.write.result',
                id,
                success: false,
              });
            }
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
            } catch (err) {
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
            if (!editor) return;

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
            if (!editor) return;

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
            if (!picked || picked.length === 0) return;

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
            if (!text) return;

            try {
              await vscode.env.clipboard.writeText(text);
              vscode.window.setStatusBarMessage('NAVI: Copied to clipboard.', 1500);
            } catch (err) {
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

            // IMMEDIATE REPO QUESTION INTERCEPTION
            const lower = text.toLowerCase();
            const isRepoQuestion = /which repo|what repo|which project|what project/.test(lower);

            // GIT INIT CONFIRMATION HANDLING
            const isGitInitConfirmation = /^(yes|y|initialize git|init git|set up git)$/i.test(text.trim());
            console.log('[Extension Host] [AEP] 🔍 Git init check:', { isGitInitConfirmation, hasPendingGitInit: !!this._pendingGitInit, text: text.trim() });
            if (isGitInitConfirmation && this._pendingGitInit) {
              console.log('[Extension Host] [AEP] 🎯 EXECUTING GIT INIT');
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
              this.postToWebview({ type: 'botThinking', value: false });
              this.postToWebview({ type: 'botMessage', text: answer });
              return;
            }

            // PR-4: Use modelId and modeId from the message (coming from pills)
            const modelId = msg.modelId || this._currentModelId;
            const modeId = msg.modeId || this._currentModeId;

            // Start from any explicit attachments (chips / commands or from message)
            let attachments: FileAttachment[] = msg.attachments || this.getCurrentAttachments();
            let autoAttachmentSummary: string | null = null;

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

            console.log(
              '[Extension Host] [AEP] User message:',
              text,
              'model:',
              modelId,
              'mode:',
              modeId,
              'attachments:',
              attachments?.length ?? 0,
            );

            // Update local state
            this._messages.push({ role: 'user', content: text });

            // If we auto-attached something, show a tiny status line in the chat
            if (autoAttachmentSummary) {
              this.postToWebview({
                type: 'botMessage',
                text: `> ${autoAttachmentSummary}`,
              });
            }

            // Show thinking state
            this.postToWebview({ type: 'botThinking', value: true });

            console.log('[Extension Host] [AEP] About to process message with smart routing:', text);
            console.log('[Extension Host] [AEP] Using smart intent-based routing...');
            await this.handleSmartRouting(text, modelId, modeId, attachments || []);
            console.log('[Extension Host] [AEP] Smart routing completed');
            break;
          }

          case 'requestAttachment': {
            await this.handleAttachmentRequest(webviewView.webview, msg.kind);
            break;
          }

          case 'getDiagnostics': {
            console.log('[AEP] 🔍 Getting diagnostics for current workspace');
            try {
              const diagnostics = vscode.languages.getDiagnostics();
              const errorCount = diagnostics.reduce((count, [uri, diags]) => count + diags.length, 0);
              const fileCount = diagnostics.length;

              if (errorCount === 0) {
                this.postToWebview({
                  type: 'botMessage',
                  text: `✅ **No diagnostic errors found!**\n\nYour workspace appears to be clean with no linting errors or compiler issues detected.`
                });
              } else {
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
                    if (errors > 0) diagnosticDetails += `${errors} error${errors > 1 ? 's' : ''}`;
                    if (warnings > 0) {
                      if (errors > 0) diagnosticDetails += ', ';
                      diagnosticDetails += `${warnings} warning${warnings > 1 ? 's' : ''}`;
                    }
                    if (info > 0) {
                      if (errors > 0 || warnings > 0) diagnosticDetails += ', ';
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
                  text: `🔍 **Found ${errorCount} diagnostic issues** across ${fileCount} files:\n${diagnosticDetails}\n\nWould you like me to help you review and fix these issues?`
                });
              }
            } catch (error) {
              console.error('[AEP] Error getting diagnostics:', error);
              this.postToWebview({
                type: 'botMessage',
                text: `⚠️ **Could not retrieve diagnostics**\n\nMake sure you have:\n- Language servers installed (e.g., TypeScript, ESLint)\n- Linting tools configured for your project\n- Files open in VS Code for analysis`
              });
            }
            break;
          }

          case 'agent.applyAction': {
            // PR-7: Apply agent-proposed action (create/edit/run)
            await this.handleAgentApplyAction(msg);
            break;
          }

          case 'agent.applyWorkspacePlan': {
            // New: Apply a full workspace plan (array of AgentAction)
            const actions: AgentAction[] = Array.isArray(msg.actions) ? msg.actions : [];
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
            if (!modelId || !modelLabel) return;

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
            if (!modeId || !modeLabel) return;

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
            vscode.window.showInformationMessage(
              'Attachment flow is not implemented yet – coming soon in a future release.'
            );
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
            if (!type) return;
            vscode.window.showInformationMessage(
              `Attachment flow for "${type}" is not wired yet – this will open the real picker in a later PR.`
            );
            break;
          }

          case 'jiraTaskSelected': {
            // User selected a Jira task - fetch full brief
            const jiraKey = String(msg.jiraKey || '').trim();
            if (!jiraKey) return;
            await this.handleJiraTaskSelected(jiraKey);
            break;
          }

          case 'showToast': {
            // Display toast notification from webview
            const message = String(msg.message || '').trim();
            const level = String(msg.level || 'info');
            if (!message) return;

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
              const backendUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8787';
              const cleanBaseUrl = backendUrl.replace(/\/api\/navi\/chat$/, '');

              console.log('[AEP] Opening ConnectorsPanel with baseUrl:', cleanBaseUrl);
              ConnectorsPanel.createOrShow(this._extensionUri);
              console.log('[AEP] ConnectorsPanel.createOrShow completed');
            } catch (err) {
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
            } catch (err: any) {
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

              const data = await response.json() as { status?: string;[key: string]: any };
              console.log('[AEP] Jira connect - Success response:', data);

              // Send proper result message
              this.postToWebview({
                type: 'connectors.jiraConnect.result',
                ok: true,
                provider: 'jira',
                status: data.status || 'connected',
                data
              });
            } catch (err: any) {
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
              vscode.window.showErrorMessage(
                `NAVI: Jira connection failed: ${err?.message || 'fetch failed'}. Check that backend is running on http://127.0.0.1:8000`
              );
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
                vscode.window.showErrorMessage(
                  `NAVI: Jira sync failed (${response.status}). Check backend logs.`
                );
                this.postToWebview({
                  type: 'connectors.jiraSyncResult',
                  ok: false,
                  error: `HTTP ${response.status}`,
                });
                return;
              }

              const data = await response.json() as {
                processed_keys?: string[];
                total?: number;
                snapshot_ts?: string;
                success?: boolean;
                [key: string]: any
              };
              console.log('[AEP] Jira sync-now success', data);

              const syncedCount = data.total ?? data.processed_keys?.length ?? 0;
              vscode.window.showInformationMessage(
                `NAVI: Jira sync complete – ${syncedCount} issues synced at ${new Date().toLocaleTimeString()}`
              );

              this.postToWebview({
                type: 'connectors.jiraSyncResult',
                ok: true,
                synced: syncedCount,
                snapshot_ts: data.snapshot_ts,
                processed_keys: data.processed_keys ?? []
              });
            } catch (err: any) {
              console.error('[AEP] Jira sync-now error', err);
              vscode.window.showErrorMessage(
                `NAVI: Jira sync error – ${err?.message ?? String(err)}`
              );
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
                intent: (result as any).intent || 'Unknown',
                confidence: (result as any).confidence || 0.0,
                model: (result as any).model || modelId
              });

            } catch (err) {
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
            if (!text) break;

            try {
              await vscode.env.clipboard.writeText(text);
              // If you want, you can also send a tiny toast back:
              // this.postToWebview({ type: 'toast', level: 'info', message: 'Copied to clipboard' });
            } catch (err: any) {
              console.error('[AEP] Failed to copy via vscode.env.clipboard:', err);
              vscode.window.showErrorMessage(
                `NAVI: Failed to copy to clipboard: ${err?.message || 'unknown error'}`
              );
            }
            break;
          }

          case 'copyToClipboard': {
            try {
              const text = String(msg.text || '').trim();
              if (!text) return;

              await vscode.env.clipboard.writeText(text);
              // optional: tiny status message
              vscode.window.setStatusBarMessage('NAVI: Response copied to clipboard', 1500);
            } catch (err) {
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
            } else {
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
                let scope: DiffScope = 'working';
                if (action === 'reviewStagedChanges') scope = 'staged';
                if (action === 'reviewLastCommit') scope = 'lastCommit';

                const diff = await getGitDiff(scope, this);
                console.log(
                  "[AEP][Git] handleSmartRouting diff scope=",
                  scope,
                  "null? ",
                  diff == null,
                  "length=",
                  diff ? diff.length : 0,
                );

                if (!diff) {
                  const scopeName =
                    scope === "staged"
                      ? "staged changes"
                      : scope === "lastCommit"
                        ? "last commit"
                        : "working tree changes";

                  this.postToWebview({
                    type: "botMessage",
                    text:
                      `I checked your Git ${scopeName} but ${
                        scope === "lastCommit"
                          ? "there is no last commit yet."
                          : "there are no uncommitted changes."
                      }\n\n` +
                      (scope === "lastCommit"
                        ? "Once you have commits in your repository, ask me again and I'll review them."
                        : "Once you've saved your edits and `git diff` is non-empty, ask me again and I'll review them."),
                  });
                  this.postToWebview({ type: "botThinking", value: false });
                  return;
                }

                let message: string;
                if (scope === 'staged') {
                  message =
                    'Review the staged changes only. Point out issues, potential bugs, and improvements.';
                } else if (scope === 'lastCommit') {
                  message =
                    'Review the last commit. Summarize what changed and highlight any issues or improvements.';
                } else {
                  message =
                    'Review my uncommitted working tree changes. Point out issues and potential improvements.';
                }

                await this.callNaviBackend(message, this._currentModelId, this._currentModeId, [
                  {
                    kind: 'diff',
                    path:
                      scope === 'staged'
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

          default:
            console.warn('[Extension Host] [AEP] Unknown message from webview:', msg);
        }
      } catch (err) {
        console.error('[Extension Host] [AEP] Error handling webview message:', err);
        this.postToWebview({
          type: 'error',
          text: '⚠️ Unexpected error in NAVI extension. Check developer tools for more details.'
        });
      }
    });

    // Welcome message will be sent when panel sends 'ready'
  }

  // --- Intent classification and smart routing --------------------------------

  // --- Intent classification and smart routing --------------------------------

  private async classifyIntent(message: string): Promise<NaviIntent> {
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
        console.warn(
          '[AEP] Intent preview HTTP error:',
          response.status,
          response.statusText,
          body,
        );
        return 'general';
      }

      const result = await response.json() as {
        family?: string;
        kind?: string;
        intent?: string;
        confidence?: number;
        model?: string;
      };

      const family = (result.family || '').toLowerCase();
      const kind = (result.kind || '').toLowerCase();
      const confidence = typeof result.confidence === 'number'
        ? result.confidence
        : 0;

      console.log('[AEP] Intent preview result:', { family, kind, confidence });

      // Map backend families/kinds → NaviIntent union
      if (family === 'jira') {
        if (kind === 'list') return 'jira_list';
        if (kind === 'priority') return 'jira_priority';
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
    } catch (err) {
      console.warn('[AEP] Intent classification failed, falling back to general:', err);
      return 'general';
    }
  }

  private async handleSmartRouting(
    text: string,
    modelId: string,
    modeId: string,
    attachments: FileAttachment[],
  ): Promise<void> {
    console.log('[AEP] 🚀 ENTERING handleSmartRouting with text:', text);
    const lower = (text || '').toLowerCase();

    // 0) Natural-language Git review triggers (before everything else)

    const wantsReviewWorkingExplicit =
      /review (my )?(current )?(working( tree)? )?changes/.test(lower) ||
      /review my changes\b/.test(lower);

    const wantsReviewStagedExplicit =
      /review (my )?staged changes/.test(lower) ||
      /review what i staged/.test(lower);

    const wantsReviewLastCommitExplicit =
      /review (the )?last commit/.test(lower) ||
      /explain (the )?last commit/.test(lower);

    // New: generic "git diff / show diff / what changed" style triggers
    const wantsGenericGitDiff =
      /\bgit diff\b/.test(lower) ||
      /do (a )?git diff/.test(lower) ||
      /run (a )?git diff/.test(lower) ||
      /show (me )?(the )?diff\b/.test(lower) ||
      /show (me )?(what )?changed\b/.test(lower) ||
      /compare (my )?changes\b/.test(lower);

    let scope: DiffScope | null = null;

    if (wantsReviewWorkingExplicit) {
      scope = 'working';
    } else if (wantsReviewStagedExplicit) {
      scope = 'staged';
    } else if (wantsReviewLastCommitExplicit) {
      scope = 'lastCommit';
    } else if (wantsGenericGitDiff) {
      // For generic "git diff / what changed" questions, default to working tree
      scope = 'working';
    }

    if (scope) {
      console.log(`[AEP] Selected scope: ${scope} for text: "${text}"`);
      const diff = await getGitDiff(scope, this);
      console.log(
        "[AEP][Git] handleSmartRouting diff scope=",
        scope,
        "null? ",
        diff == null,
        "length=",
        diff ? diff.length : 0,
      );

      if (!diff) {
        const scopeName =
          scope === "staged"
            ? "staged changes"
            : scope === "lastCommit"
              ? "last commit"
              : "working tree changes";

        this.postToWebview({
          type: "botMessage",
          text:
            `I checked your Git ${scopeName} but ${
              scope === "lastCommit"
                ? "there is no last commit yet."
                : "there are no uncommitted changes."
            }\n\n` +
            (scope === "lastCommit"
              ? "Once you have commits in your repository, ask me again and I'll review them."
              : "Once you've saved your edits and `git diff` is non-empty, ask me again and I'll review them."),
        });
        this.postToWebview({ type: "botThinking", value: false });
        return;
      }

      let message: string;
      if (scope === 'staged') {
        message =
          'Review the staged changes only. Point out bugs, potential issues, and improvements.';
      } else if (scope === 'lastCommit') {
        message =
          'Review the last commit. Summarize what changed and highlight any issues or improvements.';
      } else {
        // working
        message =
          'Review my uncommitted working tree changes. Point out issues, potential bugs, and improvements.';
      }

      await this.callNaviBackend(message, modelId, modeId, [
        {
          kind: 'diff',
          path:
            scope === 'staged'
              ? 'git:diff:staged'
              : scope === 'lastCommit'
                ? 'git:diff:last-commit'
                : 'git:diff:working',
          language: 'diff',
          content: diff,
        },
      ]);
      return;
    }

    // 1) Repo "what is this project?" style questions → local explanation
    console.log('[AEP] 🔍 Checking for repo question. Input text:', { text, lower });

    const isRepoQuestion = /which repo|what repo|which project|what project|explain.*repo|explain.*project|tell me about.*repo/.test(
      lower,
    );

    console.log('[AEP] 🔍 Repo question test result:', {
      isRepoQuestion,
      pattern:
        'which repo|what repo|which project|what project|explain.*repo|explain.*project|tell me about.*repo',
    });

    if (isRepoQuestion) {
      const workspaceRoot = this.getActiveWorkspaceRoot();
      console.log(
        '[AEP] 🎯 Repo question detected, handling locally (bypassing backend):',
        {
          text,
          workspaceRoot,
          repoName: workspaceRoot ? path.basename(workspaceRoot) : 'no-workspace-root',
        },
      );
      await this.handleLocalExplainRepo(text);
      return;
    }

    console.log('[AEP] 🔍 Not a repo question, proceeding to intent classification');

    // 2) Classify intent (for all other questions)
    const intent = await this.classifyIntent(text);
    console.log('[AEP] Detected intent:', intent, 'for message:', text);

    let effectiveAttachments = attachments;

    // 3) For workspace/code questions, enrich context with smart attachments
    if (intent === 'workspace' || intent === 'code') {
      await this.maybeAttachWorkspaceContextForQuestion(text);
      effectiveAttachments = this.getCurrentAttachments();

      // If we still have no context, attach a small workspace snapshot
      if (!effectiveAttachments || effectiveAttachments.length === 0) {
        console.log(
          '[AEP] Workspace/code intent with no attachments → auto-attaching snapshot',
        );
        await this.autoAttachWorkspaceSnapshot();
        effectiveAttachments = this.getCurrentAttachments();
      }
    }

    // 3) Route based on intent
    try {
      switch (intent) {
        case 'jira_list': {
          await this.handleJiraListIntent(text);
          break;
        }

        case 'jira_priority':
        case 'jira_ticket': {
          await this.callNaviBackend(text, modelId, modeId, effectiveAttachments);
          break;
        }

        case 'greeting':
        case 'code':
        case 'workspace':
        case 'general':
        case 'other':
        default: {
          await this.callNaviBackend(text, modelId, modeId, effectiveAttachments);
          break;
        }
      }
    } catch (err) {
      console.error('[AEP] Error handling message with intent:', intent, err);
      this.postToWebview({
        type: 'botMessage',
        text: 'Sorry, something went wrong while processing this message.',
      });
    }
  }

  private async handleLocalExplainRepo(originalMessage: string): Promise<void> {
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

    let repoName: string;

    if (workspaceRootPath) {
      repoName = path.basename(workspaceRootPath);
    } else if (activeFilePath) {
      const maybeRoot = path.dirname(activeFilePath);
      workspaceRootPath = maybeRoot;
      repoName = path.basename(maybeRoot);
    } else {
      repoName = 'current';
    }

    if (!workspaceRootPath) {
      const text =
        `You're currently working in the **${repoName}** workspace in VS Code.\n\n` +
        `I couldn't infer a project root from VS Code (no folder is open yet). ` +
        `Try opening a folder in VS Code and ask again, or tell me which file or directory you want me to analyse.`;

      this._messages.push({ role: 'assistant', content: text });
      this.postToWebview({ type: 'botThinking', value: false });
      this.postToWebview({ type: 'botMessage', text });
      return;
    }

    const rootUri = vscode.Uri.file(workspaceRootPath);

    // Helper to read package.json at root or subfolder (e.g. "frontend", "backend")
    const readPkg = async (subdir?: string): Promise<any | null> => {
      try {
        const segments = subdir ? [subdir, 'package.json'] : ['package.json'];
        const pkgUri = vscode.Uri.joinPath(rootUri, ...segments);
        const bytes = await vscode.workspace.fs.readFile(pkgUri);
        const text = new TextDecoder().decode(bytes);
        return JSON.parse(text);
      } catch {
        return null;
      }
    };

    // Helper to check if a file exists
    const exists = async (...segments: string[]): Promise<boolean> => {
      try {
        const uri = vscode.Uri.joinPath(rootUri, ...segments);
        await vscode.workspace.fs.stat(uri);
        return true;
      } catch {
        return false;
      }
    };

    // 1) Discover top-level folders
    let topLevelDirs: string[] = [];
    try {
      const entries = await vscode.workspace.fs.readDirectory(rootUri);
      topLevelDirs = entries
        .filter(([_, type]) => type === vscode.FileType.Directory)
        .map(([name]) => name)
        .sort();
    } catch {
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

    let readme: string | null = null;
    for (const name of ['README.md', 'readme.md']) {
      if (readme) break;
      try {
        const uri = vscode.Uri.joinPath(rootUri, name);
        const bytes = await vscode.workspace.fs.readFile(uri);
        const text = new TextDecoder().decode(bytes);
        readme = text.trim();
      } catch {
        // no README at this path, continue
      }
    }

    const displayName: string =
      (rootPkg && typeof rootPkg.name === 'string' && rootPkg.name.trim()) ||
      repoName;

    const description: string | null =
      rootPkg &&
        typeof rootPkg.description === 'string' &&
        rootPkg.description.trim()
        ? rootPkg.description.trim()
        : null;

    // 3) Infer tech stack from package.jsons + structure
    const techs: string[] = [];
    const addTech = (label: string) => {
      if (!techs.includes(label)) techs.push(label);
    };

    const collectTechFromPkg = (pkg: any | null) => {
      if (!pkg || typeof pkg !== 'object') return;
      const deps = {
        ...(pkg.dependencies || {}),
        ...(pkg.devDependencies || {}),
      };
      const scripts = pkg.scripts || {};

      if (deps.react) addTech('React');
      if (deps['react-dom']) addTech('React DOM');
      if (deps.next) addTech('Next.js');
      if (deps.vite) addTech('Vite');
      if (deps.typescript) addTech('TypeScript');
      if (deps['tailwindcss']) addTech('Tailwind CSS');
      if (deps['express'] || deps['fastify'] || deps['koa']) {
        addTech('Node.js API server');
      }
      if (deps['@vscode/webview-ui-toolkit'] || (pkg.engines && pkg.engines.vscode)) {
        addTech('VS Code extension');
      }

      const devScript: string = scripts.dev || '';
      if (devScript.includes('next')) addTech('Next.js dev server');
      if (devScript.includes('vite')) addTech('Vite dev server');
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
    const structureLines: string[] = [];

    if (hasFrontend) {
      const labelParts: string[] = ['frontend/ — main web UI'];
      if (frontendPkg) {
        const deps = {
          ...(frontendPkg.dependencies || {}),
          ...(frontendPkg.devDependencies || {}),
        };
        if (deps.next) labelParts.push('(Next.js)');
        else if (deps.vite) labelParts.push('(Vite + React)');
        else if (deps.react) labelParts.push('(React app)');
      }
      structureLines.push(`- \`frontend/\` — ${labelParts.join(' ')}`);
    }

    if (hasBackend) {
      const labelParts: string[] = ['backend/ — server/API layer'];
      if (backendPkg) {
        const deps = {
          ...(backendPkg.dependencies || {}),
          ...(backendPkg.devDependencies || {}),
        };
        if (deps.express) labelParts.push('(Express.js API)');
        else if (deps.fastify) labelParts.push('(Fastify API)');
        else if (deps.koa) labelParts.push('(Koa API)');
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

    const otherDirs = topLevelDirs.filter(
      (d) =>
        ![
          'frontend',
          'backend',
          'src',
          'apps',
          'packages',
          '.git',
          '.vscode',
          'node_modules',
        ].includes(d),
    );
    if (otherDirs.length > 0) {
      structureLines.push(
        `- Other top-level dirs: ${otherDirs.map((d) => `\`${d}/\``).join(', ')}`,
      );
    }

    // 6) README snippet
    let readmeSnippet: string | null = null;
    if (readme) {
      const lines = readme.split('\n').slice(0, 12);
      const snippet = lines.join('\n').trim();
      readmeSnippet =
        snippet.length > 500 ? snippet.slice(0, 500).trimEnd() + '…' : snippet;
    }

    // 7) Compose final dynamic answer
    const parts: string[] = [];

    parts.push(
      `You're currently working in the **${displayName}** repo at \`${workspaceRootPath}\`.`,
    );

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

    parts.push(
      `\nIf you want, ask me about a specific file, component, or feature (e.g. ` +
      '`explain `src/extension.ts`` or `how does the frontend auth work?`) and I can dive deeper using the real code.',
    );

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

  private async handleGitInitRequest(requestedScope: DiffScope): Promise<void> {
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

  private async executeGitInit(): Promise<void> {
    if (!this._pendingGitInit) return;

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
        } else {
          const noChangesMsg = `The repository is now ready! Since we just committed all files, ` +
            `there are no ${requestedScope === 'staged' ? 'staged' : 'working'} changes to review yet.\n\n` +
            `Make some changes to your code, then ask me to review them again! 📝`;
          this._messages.push({ role: 'assistant', content: noChangesMsg });
          this.postToWebview({ type: 'botMessage', text: noChangesMsg });
        }
      }, 1000);

    } catch (error: any) {
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

  private async handleJiraListIntent(originalMessage: string): Promise<void> {
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
    } catch (err) {
      console.error('[AEP] Error fetching Jira tasks:', err);
      await this.callNaviBackend(
        originalMessage,
        this._currentModelId,
        this._currentModeId,
        this.getCurrentAttachments()
      );
    }
  }

  private formatJiraTaskListForChat(data: any, _originalMessage: string): string {
    if (!data.tasks || data.tasks.length === 0) {
      return "I don't see any Jira tasks in your synced memory yet. Try running a Jira sync and ask me again.";
    }

    const lines: string[] = [];
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

  private async triggerBackgroundJiraSync(): Promise<void> {
    // Non-blocking background sync of Jira tasks
    const config = vscode.workspace.getConfiguration('aep');
    const baseUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000';
    const userId = config.get<string>('navi.userId') || 'srinivas@example.com';

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
          if ((data as any).total > 0) {
            vscode.window.showInformationMessage(
              `NAVI: Synced ${(data as any).total} Jira tasks`
            );
          }
        } else {
          const text = await response.text().catch(() => '');
          console.log('[Extension Host] [AEP] Jira sync failed:', response.status, text);
          vscode.window.showWarningMessage(
            `NAVI: Jira sync failed (HTTP ${response.status})`
          );
        }
      })
      .catch((error) => {
        console.log('[Extension Host] [AEP] Jira sync error (non-critical):', error.message);
        vscode.window.showWarningMessage('NAVI: Jira sync error – backend unreachable or misconfigured');
      });
  }

  private async handleJiraTaskBriefCommand(): Promise<void> {
    if (!this._view) {
      return;
    }

    try {
      const config = vscode.workspace.getConfiguration('aep');
      const baseUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000';
      const userId = config.get<string>('navi.userId') || 'srinivas@example.com';

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
        vscode.window.showErrorMessage(
          `NAVI: Failed to load Jira tasks (${response.status})`
        );
        return;
      }

      const data = await response.json();

      // Send tasks to webview
      this.postToWebview({
        type: 'showJiraTasks',
        tasks: (data as any).tasks || []
      });
    } catch (error: any) {
      console.error('[Extension Host] [AEP] Error fetching Jira tasks:', error);
      vscode.window.showErrorMessage('NAVI: Error loading Jira tasks');
    }
  }

  private async handleJiraTaskSelected(jiraKey: string): Promise<void> {
    if (!this._view) {
      return;
    }

    try {
      const config = vscode.workspace.getConfiguration('aep');
      const baseUrl = config.get<string>('navi.backendUrl') || 'http://127.0.0.1:8000';
      const userId = config.get<string>('navi.userId') || 'srinivas@example.com';

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
        vscode.window.showErrorMessage(
          `NAVI: Failed to load brief for ${jiraKey} (${response.status})`
        );
        this.postToWebview({ type: 'botThinking', value: false });
        return;
      }

      const data = await response.json();

      // Extract the brief markdown from the sections
      const briefMd = (data as any).sections?.[0]?.content || (data as any).summary || 'No brief content available';

      // Send as a bot message
      this.postToWebview({
        type: 'botMessage',
        text: briefMd,
        actions: []
      });

      this.postToWebview({ type: 'botThinking', value: false });
    } catch (error: any) {
      console.error('[Extension Host] [AEP] Error fetching task brief:', error);
      vscode.window.showErrorMessage('NAVI: Error fetching task brief');
      this.postToWebview({ type: 'botThinking', value: false });
    }
  }

  // --- Core: call NAVI backend ------------------------------------------------

  private async callNaviBackend(
    latestUserText: string,
    modelId?: string,
    modeId?: string,
    attachments?: FileAttachment[]
  ): Promise<void> {
    if (!this._view) {
      return;
    }

    // Merge attachments into the plain-text message for the LLM
    const messageWithContext = this.buildMessageWithAttachments(
      latestUserText,
      attachments
    );

    // Perfect Workspace Context Collection
    const workspaceContext = await collectWorkspaceContext();

    // Detect the most relevant workspace root (prefer the one of the active file)
    const workspaceRoot = this.getActiveWorkspaceRoot();

    // 🔧 NEW: Detect diagnostics commands for "check errors & fix" functionality
    const diagnosticsCommandsArray = workspaceRoot ? await detectDiagnosticsCommands(workspaceRoot) : [];

    const payload = {
      message: messageWithContext,
      model: modelId || this._currentModelId,
      mode: modeId || this._currentModeId,
      user_id: 'default_user',
      workspace: workspaceContext,  // 🚀 Perfect workspace awareness
      workspace_root: workspaceRoot, // NEW: VS Code workspace root path
      diagnosticsCommandsArray, // 🔧 NEW: Commands for error checking
      // Map attachment kinds to match backend expectations
      attachments: (attachments ?? []).map(att => ({
        ...att,
        kind:
          att.kind === 'currentFile' || att.kind === 'pickedFile'
            ? 'file'
            : att.kind === 'diff'
              ? 'diff'
              : 'selection',
      })),
    };

    console.log('[Extension Host] [AEP] Workspace debug:', {
      workspaceRoot,
      workspaceContextRoot: workspaceContext?.workspace_root,
    });

    let response: Response;
    try {
      // Read backend URL from configuration with fallback
      const config = vscode.workspace.getConfiguration('aep');
      const configValue = config.get<string>('navi.backendUrl');
      const backendUrl = configValue || 'http://127.0.0.1:8787/api/navi/chat';

      console.log('[Extension Host] [AEP] Configuration debug:');
      console.log('[Extension Host] [AEP] - Raw config value:', configValue);
      console.log('[Extension Host] [AEP] - Final backend URL:', backendUrl);
      console.log('[Extension Host] [AEP] - Payload:', {
        ...payload,
        // don't spam the log with the whole file
        attachmentsCount: payload.attachments.length,
        firstAttachmentPath: payload.attachments[0]?.path,
        firstAttachmentChars: payload.attachments[0]?.content?.length,
      });
      console.log('[Extension Host] [AEP] Calling NAVI backend now...');

      response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Org-Id': 'org_aep_platform_4538597546e6fec6',
        },
        body: JSON.stringify(payload)
      });
    } catch (error: any) {
      console.error('[Extension Host] [AEP] NAVI backend unreachable:', error);
      console.error('[Extension Host] [AEP] Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
      this.postToWebview({ type: 'botThinking', value: false });
      this.postToWebview({
        type: 'error',
        text: `⚠️ NAVI backend error: ${(error && error.message) || 'fetch failed'}`
      });
      return;
    }

    const contentType = (response.headers.get('content-type') || '').toLowerCase();

    // Non-2xx: show a clean error bubble, no empty reply above it.
    if (!response.ok) {
      console.error(
        '[Extension Host] [AEP] NAVI backend non-OK response:',
        response.status,
        response.statusText
      );
      this.postToWebview({ type: 'botThinking', value: false });
      this.postToWebview({
        type: 'error',
        text: `⚠️ NAVI backend error: HTTP ${response.status} ${response.statusText || ''}`.trim()
      });
      return;
    }

    try {
      console.log('[Extension Host] [AEP] Response received. Status:', response.status, 'Content-Type:', contentType);

      if (contentType.includes('application/json')) {
        // PR-6B: Handle new response format
        const json = (await response.json()) as NaviChatResponseJson;
        console.log('[Extension Host] [AEP] JSON response:', json);
        const content = (json.content || '').trim();

        if (!content) {
          console.warn('[Extension Host] [AEP] Empty content from NAVI backend.');
          this.postToWebview({
            type: 'error',
            text: '⚠️ NAVI backend returned empty content.'
          });
          return;
        }

        this._messages.push({ role: 'assistant', content: content });

        // PR-6C: Handle agent actions if present
        const messageId = `msg-${Date.now()}`;
        const sources = json.sources || [];

        if (json.actions && json.actions.length > 0) {
          this._agentActions.set(messageId, { actions: json.actions });
          this.postToWebview({
            type: 'botMessage',
            text: content,
            messageId: messageId,
            actions: json.actions,
            sources: sources,
            agentRun: json.agentRun || null
          });
        } else {
          this.postToWebview({
            type: 'botMessage',
            text: content,
            sources: sources,
            agentRun: json.agentRun || null
          });
        }
        return;
      } if (contentType.includes('text/event-stream')) {
        // ⚡ Streaming path (SSE) – we still send a single final botMessage for now
        const fullText = await this.readSseStream(response);
        const reply = fullText.trim();

        if (!reply) {
          this.postToWebview({
            type: 'error',
            text: '⚠️ NAVI backend returned an empty streamed reply.'
          });
          return;
        }

        this._messages.push({ role: 'assistant', content: reply });
        this.postToWebview({ type: 'botMessage', text: reply });
        return;
      }

      // Fallback: treat as plain text
      const text = (await response.text()).trim();
      if (!text) {
        this.postToWebview({
          type: 'error',
          text: '⚠️ NAVI backend returned an empty reply (unknown content-type).'
        });
        return;
      }
      this._messages.push({ role: 'assistant', content: text });
      this.postToWebview({ type: 'botMessage', text });
    } catch (err) {
      console.error('[Extension Host] [AEP] Error handling NAVI backend response:', err);
      this.postToWebview({
        type: 'error',
        text: '⚠️ Error while processing response from NAVI backend.'
      });
    }
  }

  /**
   * Best-effort automatic context based on the current editor and the user's message.
   * - For code-ish questions, prefer the current selection.
   * - If no selection, fall back to the whole current file.
   * - For repo/project questions, we return null and let handleLocalExplainRepo deal with it.
   */
  private buildAutoAttachments(
    message: string
  ): { attachments: FileAttachment[]; summary: string } | null {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return null;

    const doc = editor.document;
    const text = (message || '').toLowerCase();

    // Repo / project-level questions → let handleLocalExplainRepo answer instead
    const repoLike =
      /this repo|this repository|this project|entire repo|whole repo|whole project/.test(
        text,
      );
    if (repoLike) return null;

    // Only auto-attach when it sounds like a code question
    const maybeCodeQuestion =
      /(code|bug|error|stack trace|exception|component|hook|function|method|class|file|module|refactor|tests?|unit test|integration test|compile|build|lint|ts error|typescript|js error|react|jsx|tsx|java|c#|python)/.test(
        text,
      );

    if (!maybeCodeQuestion) {
      return null;
    }

    const hasSelection = !editor.selection.isEmpty;
    const mentionsSelection =
      /this code|this snippet|these lines|selected code|highlighted code|above code|this block/.test(
        text,
      );
    const mentionsFile =
      /this file|this component|this page|this screen|this module|current file|entire file|whole file/.test(
        text,
      );

    const attachments: FileAttachment[] = [];
    let summary: string | null = null;

    const workspaceRoot = this.getActiveWorkspaceRoot();
    const fullPath = doc.uri.fsPath;
    const relPath =
      workspaceRoot && fullPath.startsWith(workspaceRoot)
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
    } else {
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
  private getActiveWorkspaceRoot(): string | undefined {
    console.log('[Extension Host] [AEP] 🔍 Getting workspace root...');

    const editor = vscode.window.activeTextEditor;
    if (editor) {
      const folder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
      if (folder) {
        console.log('[Extension Host] [AEP] ✅ Found workspace from active editor:', folder.uri.fsPath);
        return folder.uri.fsPath;
      }
      console.log('[Extension Host] [AEP] ⚠️ Active editor found but no workspace folder for:', editor.document.uri.fsPath);
    } else {
      console.log('[Extension Host] [AEP] ⚠️ No active text editor found');
    }

    // Fallback: first workspace folder if present
    const firstWorkspace = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (firstWorkspace) {
      console.log('[Extension Host] [AEP] 📁 Using first workspace folder as fallback:', firstWorkspace);
    } else {
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
  private async readSseStream(response: Response): Promise<string> {
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
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let newlineIndex: number;
        // Process line by line
        while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);

          if (!line || !line.startsWith('data:')) {
            continue;
          }

          const data = line.slice('data:'.length).trim();
          if (!data) continue;

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
            } else if (typeof parsed.reply === 'string') {
              chunk = parsed.reply;
            }
          } catch {
            // If not JSON, treat as raw text
          }

          accumulated += chunk;
        }
      }
    } catch (err: any) {
      // In PR1 we just log SSE errors and let the caller decide what to show
      console.error('[Extension Host] [AEP] Error while reading SSE stream:', err);
    }

    return accumulated;
  }

  // --- Helpers ---------------------------------------------------------------

  private postToWebview(message: any) {
    if (!this._view) return;
    this._view.webview.postMessage(message);
  }

  private startNewChat() {
    // Reset conversation state, keep current model/mode
    this._conversationId = generateConversationId();
    this._messages = [];

    this.postToWebview({ type: 'clearChat' });
    this.postToWebview({
      type: 'botMessage',
      text: "🔄 **New chat started!**\n\nHow can I help you today?"
    });
  }

  // --- Attachment Helper Methods ---

  private addAttachment(attachment: FileAttachment) {
    // Simple upsert: dedupe by kind+path+length
    const key = `${attachment.kind}:${attachment.path}:${attachment.content.length}`;
    const existingIndex = this._attachments.findIndex(a =>
      `${a.kind}:${a.path}:${a.content.length}` === key
    );

    if (existingIndex >= 0) {
      this._attachments[existingIndex] = attachment;
    } else {
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
  private async autoAttachWorkspaceSnapshot(): Promise<void> {
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
      if (attachedCount >= maxFiles) break;

      try {
        const filePath = path.join(wsRoot, fileName);
        const uri = vscode.Uri.file(filePath);

        // Check if file exists
        try {
          await vscode.workspace.fs.stat(uri);
        } catch {
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
      } catch (error) {
        console.warn(`[AEP] Failed to read ${fileName}:`, error);
      }
    }

    if (attachedCount > 0) {
      console.log(`[AEP] Workspace snapshot complete: ${attachedCount} files attached`);
    } else {
      console.log('[AEP] No key workspace files found');
    }
  }

  private async attachFileIfExists(rootUri: vscode.Uri, relPath: string): Promise<boolean> {
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
    } catch {
      return false;
    }
  }

  private async maybeAttachWorkspaceContextForQuestion(userMessage: string): Promise<void> {
    const msg = (userMessage || '').toLowerCase();

    const wantsRouting =
      msg.includes(' route') ||
      msg.startsWith('route') ||
      msg.includes('routing') ||
      msg.includes('routes') ||
      msg.includes('router') ||
      msg.includes('navigation') ||
      msg.includes('nav bar') ||
      msg.includes('nav menu');

    const wantsExtension =
      msg.includes('extension') ||
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

    const tryAttach = async (relPath: string) => {
      if (added >= maxExtra) return;
      const ok = await this.attachFileIfExists(rootUri, relPath);
      if (ok) added += 1;
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
        if (added >= maxExtra) break;
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
        if (added >= maxExtra) break;
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

  private getCurrentAttachments(): FileAttachment[] {
    return this._attachments.slice();
  }

  private clearAttachments() {
    this._attachments = [];
    this.postToWebview({ type: 'clearAttachments' });
  }

  private truncateForAttachment(text: string, source: string): string {
    const maxChars = 120_000; // ~700–1000 lines is fine
    if (text.length <= maxChars) return text;

    vscode.window.showWarningMessage(
      `NAVI: ${source} is very large; truncating to ${maxChars.toLocaleString()} characters for this request.`
    );
    return text.slice(0, maxChars);
  }

  private showWebviewToast(message: string, level: 'info' | 'warning' | 'error' = 'info') {
    this.postToWebview({
      type: 'ephemeralToast',
      level,
      text: message,
    });
  }

  // Helper: merge attachments into the plain-text message we send to the backend
  private buildMessageWithAttachments(
    latestUserText: string,
    attachments?: FileAttachment[]
  ): string {
    if (!attachments || attachments.length === 0) {
      return latestUserText;
    }

    const chunks: string[] = [];

    chunks.push(
      'I have attached some code context from VS Code below. ' +
      'Please use that code as the primary context when answering my request.\n'
    );

    for (const att of attachments) {
      const fileLabel = att.path ? path.basename(att.path) : '(untitled)';
      const kindLabel =
        att.kind === 'selection'
          ? 'selected code'
          : att.kind === 'currentFile'
            ? 'current file'
            : 'attached file';

      const lang = att.language ?? ''; // ok to be empty
      const fenceHeader = lang ? `\`\`\`${lang}` : '```';

      chunks.push(
        `\n\nFile: \`${fileLabel}\` (${kindLabel})\n` +
        `${fenceHeader}\n` +
        `${att.content}\n` +
        `\`\`\``
      );
    }

    chunks.push('\n\nUser request:\n');
    chunks.push(latestUserText);

    return chunks.join('');
  }

  // PR-5: Handle attachment requests from the webview
  private async handleAttachmentRequest(webview: vscode.Webview, kind: string): Promise<void> {
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

        const attachment: FileAttachment = {
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

        const attachment: FileAttachment = {
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

        const attachment: FileAttachment = {
          kind: 'pickedFile',
          path: uri.fsPath,
          content: textContent,
        };

        this.addAttachment(attachment);
        return;
      }

    } catch (err) {
      console.error('[Extension Host] [AEP] Error reading attachment:', err);
      vscode.window.showErrorMessage('NAVI: Failed to read file for attachment.');
    }
  }

  private async handleApplyReviewFixes(
    reviews: ReviewCommentFromBackend[],
  ): Promise<void> {
    if (!reviews || reviews.length === 0) {
      vscode.window.showWarningMessage(
        'NAVI: No review comments were provided to apply.'
      );
      return;
    }

    const workspaceRoot = this.getActiveWorkspaceRoot();
    if (!workspaceRoot) {
      vscode.window.showErrorMessage(
        'NAVI: No workspace root detected. Open a folder before applying fixes.'
      );
      return;
    }

    const seenPaths = new Set<string>();
    const attachments: FileAttachment[] = [];

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

        let language: string | undefined;
        try {
          const doc = await vscode.workspace.openTextDocument(fileUri);
          language = doc.languageId;
        } catch {
          // Best-effort: leave language undefined
        }

        attachments.push({
          kind: 'file',
          path: fileFsPath,
          language,
          content,
        });
      } catch (err) {
        console.warn('[AEP] Failed to read file for review fix:', relPath, err);
      }
    }

    if (attachments.length === 0) {
      vscode.window.showWarningMessage(
        'NAVI: None of the files from the review comments could be read from disk.'
      );
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
    await this.callNaviBackend(
      prompt,
      this._currentModelId,
      this._currentModeId,
      attachments,
    );
  }

  // PR-7: Apply agent action from new unified message format
  private async handleAgentApplyAction(message: any): Promise<void> {
    const { decision, actionIndex, actions } = message;

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
        await this.applyRunCommandAction(action);
        return;
      }

      console.warn('[Extension Host] [AEP] Unknown action type:', action.type);
    } catch (error: any) {
      console.error('[Extension Host] [AEP] Error applying action:', error);
      vscode.window.showErrorMessage(`Failed to apply action: ${error.message}`);
    }
  }

  // NEW: Apply a full workspace plan (array of AgentAction)
  private async applyWorkspacePlan(actions: AgentAction[]): Promise<void> {
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
        } else if (action.type === 'editFile') {
          await this.applyEditFileAction(action);
          appliedCount += 1;
        } else if (action.type === 'runCommand') {
          await this.applyRunCommandAction(action);
          appliedCount += 1;
        } else {
          console.warn('[Extension Host] [AEP] Unknown action type in workspace plan:', action.type);
        }
      } catch (err: any) {
        console.error('[Extension Host] [AEP] Failed to apply action in workspace plan:', err);
        vscode.window.showErrorMessage(`NAVI: Failed to apply one of the workspace actions: ${err.message ?? String(err)}`);
      }
    }

    this.postBotStatus(`✅ Applied ${appliedCount}/${actions.length} workspace actions.`);
  }

  private async applyCreateFileAction(action: any): Promise<void> {
    const fileName: string = action.filePath ?? 'sample.js';
    const content: string = action.content ?? '// Sample generated by NAVI\nconsole.log("Hello, World!");\n';

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
      this.postBotStatus(
        "I don't see a workspace folder open. I can still create the sample file if you tell me where it should live."
      );

      const choice = await vscode.window.showQuickPick(
        [
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
        ],
        {
          placeHolder: 'Where should I create the sample file?',
          title: 'NAVI - Create Sample File',
        }
      );

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
    this.postBotStatus(
      "I don't see a workspace folder open. Please pick a folder where I should create the sample file."
    );

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

  private async createFileUnderRoot(root: vscode.Uri, relPath: string, content: string): Promise<void> {
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
    } catch {
      // ignore if it already exists
    }

    await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));

    const doc = await vscode.workspace.openTextDocument(fileUri);
    await vscode.window.showTextDocument(doc);

    vscode.window.setStatusBarMessage(`✅ NAVI: Created ${relPath}`, 3000);

    this.postBotStatus(`✅ Done! I've created \`${relPath}\` at ${fileUri.fsPath}`);
  }

  private postBotStatus(text: string): void {
    if (!this._view) return;
    this._view.webview.postMessage({
      type: 'botMessage',
      text,
      actions: [],
      messageId: new Date().toISOString(),
    });
  }

  private async applyRunCommandAction(action: any): Promise<void> {
    const command = action.command;
    if (!command) return;

    // Security: Sanitize, truncate, and show command for confirmation before executing
    const sanitizedCommand = command.replace(/[\r\n]/g, ' ').substring(0, 200);
    const displayCommand = command.length > 200 ? sanitizedCommand + '...' : sanitizedCommand;

    const confirmed = await vscode.window.showWarningMessage(
      `NAVI wants to run the following command:\\n\\n${displayCommand}\\n\\nAre you sure?`,
      { modal: true },
      'Run Command'
    );
    if (confirmed !== 'Run Command') return;

    const terminal = vscode.window.createTerminal('NAVI Agent');
    terminal.show();
    terminal.sendText(command);

    vscode.window.showInformationMessage(`🚀 Running: ${command}`);
  }

  // ---- editFile with diff view & apply (PR-10) -------------------------------
  private async applyEditFileAction(action: any): Promise<void> {
    // Backend contract: editFile provides either:
    // - filePath + content (full new file text)   ✅
    // - optionally diff (for explanation), but we don't parse it
    const filePath: string | undefined = action.filePath;
    const newContent: string | undefined = action.content;

    if (!newContent) {
      vscode.window.showWarningMessage(
        'NAVI: editFile action is missing "content"; nothing to apply.'
      );
      return;
    }

    // Resolve target document: use filePath if present, otherwise active editor
    let targetDoc: vscode.TextDocument | undefined;
    if (filePath) {
      const uri = vscode.Uri.file(filePath);
      try {
        targetDoc = await vscode.workspace.openTextDocument(uri);
      } catch {
        vscode.window.showWarningMessage(
          `NAVI: Target file "${filePath}" does not exist.`
        );
        return;
      }
    } else {
      targetDoc = vscode.window.activeTextEditor?.document;
      if (!targetDoc) {
        vscode.window.showWarningMessage(
          'NAVI: No active file to apply edit to.'
        );
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
    await vscode.commands.executeCommand(
      'vscode.diff',
      targetDoc.uri,
      newDoc.uri,
      title
    );

    // Ask user if we should apply the changes to the real file now
    const choice = await vscode.window.showQuickPick(
      [
        { label: '✅ Apply edit to file', id: 'apply' },
        { label: '👁️ Keep diff only', id: 'keep' },
        { label: '❌ Cancel', id: 'cancel' },
      ],
      {
        placeHolder:
          'NAVI has proposed an edit. Do you want to apply it to the real file?',
      }
    );

    if (!choice || choice.id === 'cancel' || choice.id === 'keep') {
      if (choice?.id === 'keep') {
        this.postBotStatus('Diff view kept open for your review.');
      }
      return;
    }

    if (choice.id === 'apply') {
      const edit = new vscode.WorkspaceEdit();
      const fullRange = new vscode.Range(
        targetDoc.positionAt(0),
        targetDoc.positionAt(originalText.length)
      );
      edit.replace(targetDoc.uri, fullRange, newContent);
      const success = await vscode.workspace.applyEdit(edit);
      if (success) {
        await targetDoc.save();
        vscode.window.setStatusBarMessage('✅ NAVI: Edit applied.', 3000);
        this.postBotStatus(`✅ Edit applied to ${targetDoc.fileName.split(/[\\/]/).pop()}`);
      } else {
        vscode.window.showErrorMessage('NAVI: Failed to apply edit.');
      }
    }
  }

  // PR-6C: Apply agent-proposed edit with diff view support
  private async handleApplyAgentEdit(msg: { messageId: string; actionIndex: number }): Promise<void> {
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

      } else if (action.type === 'createFile' && action.filePath && action.content) {
        // Create new file
        const fileUri = vscode.Uri.joinPath(workspaceRoot, action.filePath);
        await vscode.workspace.fs.writeFile(fileUri, Buffer.from(action.content, 'utf-8'));
        vscode.window.showInformationMessage(`✅ Created ${action.filePath}`);

        // Open the new file
        const document = await vscode.workspace.openTextDocument(fileUri);
        await vscode.window.showTextDocument(document, { preview: false });

      } else if (action.type === 'runCommand' && action.command) {
        // PR-6C: Run terminal command
        const terminal = vscode.window.createTerminal('NAVI Agent');
        terminal.show();
        terminal.sendText(action.command);
        vscode.window.showInformationMessage(`🔧 Running: ${action.command}`);

      } else {
        vscode.window.showWarningMessage(`Unknown or incomplete action type: ${action.type}`);
      }

    } catch (err: any) {
      console.error('[Extension Host] [AEP] Error applying agent action:', err);
      vscode.window.showErrorMessage(`Failed to apply action: ${err.message}`);
    }
  }

  // PR-6C: Show diff preview and apply on confirmation
  private async showDiffPreviewAndApply(
    workspaceRoot: vscode.Uri,
    filePath: string,
    diff: string
  ): Promise<void> {
    const fileUri = vscode.Uri.joinPath(workspaceRoot, filePath);

    // Read original file
    let originalDoc: vscode.TextDocument;
    try {
      originalDoc = await vscode.workspace.openTextDocument(fileUri);
    } catch {
      vscode.window.showErrorMessage(`File not found: ${filePath}`);
      return;
    }

    const original = originalDoc.getText();

    // Apply diff to get new content
    let newContent: string;
    try {
      newContent = applyUnifiedDiff(original, diff);
    } catch (error: any) {
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
    await vscode.commands.executeCommand(
      'vscode.diff',
      fileUri,
      tempUri,
      `NAVI: ${fileName} (Original ↔ Proposed)`
    );

    // Ask user to confirm
    const choice = await vscode.window.showInformationMessage(
      `Apply proposed changes to ${fileName}?`,
      { modal: true },
      'Apply',
      'Cancel'
    );

    if (choice === 'Apply') {
      // Apply the changes
      const fullRange = new vscode.Range(
        originalDoc.positionAt(0),
        originalDoc.positionAt(original.length)
      );

      const finalEdit = new vscode.WorkspaceEdit();
      finalEdit.replace(fileUri, fullRange, newContent);
      await vscode.workspace.applyEdit(finalEdit);
      await originalDoc.save();

      vscode.window.showInformationMessage(`✅ Applied changes to ${fileName}`);
    } else {
      vscode.window.showInformationMessage('Changes discarded');
    }
  }

  private async getWebviewHtml(webview: vscode.Webview): Promise<string> {
    const cfg = vscode.workspace.getConfiguration('aep');
    const isDevelopment = cfg.get<boolean>('development.useReactDevServer') ?? true;

    console.log('[AEP] Development mode:', isDevelopment);
    console.log('[AEP] 🔍 WEBVIEW DEBUG: Starting to generate HTML...');

    if (isDevelopment) {
      // Get workspace root for context
      const workspaceRoot = this.getActiveWorkspaceRoot();
      const workspaceParam = workspaceRoot ? `?workspaceRoot=${encodeURIComponent(workspaceRoot)}` : '';

      console.log('[AEP] 📁 Workspace context:', { workspaceRoot, workspaceParam });

      // Load from Vite dev server - use /navi route for NaviRoot component
      const viteUrl = await vscode.env.asExternalUri(
        vscode.Uri.parse(`http://localhost:3007/navi${workspaceParam}`)
      );
      console.log('[AEP] 🌐 Loading Vite webview from:', viteUrl.toString());

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
      onload="document.getElementById('loading').style.display='none'; this.style.display='block';"
      onerror="document.getElementById('loading').style.display='none'; document.getElementById('errorBox').style.display='block';">
    </iframe>
    <script>
      // Bridge VS Code API to iframe
      const vscode = acquireVsCodeApi();
      
      // Forward messages from iframe to VS Code extension
      window.addEventListener('message', (event) => {
        if (event.source === document.getElementById('webview').contentWindow) {
          // Message from iframe, forward to VS Code
          vscode.postMessage(event.data);
        }
      });
      
      // Forward messages from VS Code to iframe
      window.addEventListener('message', (event) => {
        if (event.data && event.data.type) {
          // Message from VS Code, forward to iframe
          const iframe = document.getElementById('webview');
          if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(event.data, '*');
          }
        }
      });
      
      // Inject vscode-like API into iframe when it loads
      document.getElementById('webview').onload = function() {
        document.getElementById('loading').style.display='none'; 
        this.style.display='block';
        
        // Inject vscode API into iframe
        const iframe = this;
        if (iframe.contentWindow) {
          iframe.contentWindow.postMessage({
            type: '__vscode_init__',
            vscodeApi: true
          }, '*');
        }
      };
    </script>
  </body>
</html>`;
    } else {
      // Production: Load bundled React app
      // TODO: Implement production build path
      return /* html */ `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NAVI Assistant</title>
    <style>
      body { background: #020617; color: white; font-family: system-ui; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; text-align: center; }
      h1 { color: #10b981; margin-bottom: 16px; }
      p { color: #94a3b8; margin-bottom: 8px; }
      code { background: #1e293b; padding: 2px 8px; border-radius: 4px; color: #10b981; }
    </style>
  </head>
  <body>
    <h1>🚧 Production Mode</h1>
    <p>The bundled React app is not built yet.</p>
    <p style="margin-top: 16px;">To use NAVI, enable development mode in settings:</p>
    <p><code>"aep.development.useReactDevServer": true</code></p>
    <p style="margin-top: 16px;">Then start the frontend dev server:</p>
    <p><code>cd frontend && npm run dev</code></p>
  </body>
</html>`;
    }
  }

  private async checkFrontendServer(): Promise<boolean> {
    try {
      // Try GET request first (more reliable than HEAD for some servers)
      const response = await fetch('http://localhost:3007/', {
        method: 'GET',
        signal: AbortSignal.timeout(3000)
      });
      // Accept any 2xx or 3xx response as "running"
      return response.status < 400;
    } catch (err) {
      console.log('[AEP] Frontend server check failed:', err instanceof Error ? err.message : 'unknown error');
      return false;
    }
  }

  private async startFrontendServer(): Promise<void> {
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
      } catch {
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
      vscode.window.showInformationMessage(
        'NAVI: Starting frontend server... Please wait a moment then reload the panel.',
        'Reload Panel'
      ).then(selection => {
        if (selection === 'Reload Panel') {
          vscode.commands.executeCommand('workbench.action.webview.reloadWebviewAction');
        }
      });
    } catch (err) {
      console.log('[AEP] Could not start frontend server automatically:', err);
      // Don't show error - the error HTML will guide the user
    }
  }

  private getServerNotRunningHtml(): string {
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

  public async attachSelectionCommand(): Promise<void> {
    if (this._view) {
      await this.handleAttachmentRequest(this._view.webview, 'selection');
    }
  }

  public async attachCurrentFileCommand(): Promise<void> {
    if (this._view) {
      await this.handleAttachmentRequest(this._view.webview, 'current-file');
    }
  }

  public async checkErrorsAndFixCommand(): Promise<void> {
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

      // Show thinking state and process message
      this.postToWebview({ type: 'botThinking', value: true });

      await this.handleSmartRouting(
        message,
        this._currentModelId,
        this._currentModeId,
        []
      );

      // Show confirmation to user
      vscode.window.setStatusBarMessage('NAVI: Running diagnostics...', 3000);
    } catch (error) {
      console.error('[Extension Host] [AEP] Check errors command failed:', error);
      vscode.window.showErrorMessage('Failed to run error checking.');
    }
  }

  public async generateTestsForFileCommand(): Promise<void> {
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
      await this.handleSmartRouting(
        message,
        this._currentModelId,
        this._currentModeId,
        attachments
      );

      // Show confirmation to user
      vscode.window.setStatusBarMessage('NAVI: Generating tests...', 3000);
    } catch (error) {
      console.error('[Extension Host] [AEP] Generate tests command failed:', error);
      vscode.window.showErrorMessage('Failed to generate tests.');
    }
  }


}

// Simple conversation id – you can switch to UUID later
function generateConversationId(): string {
  return `navi-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function getNonce() {
  let text = '';
  const possible =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}
