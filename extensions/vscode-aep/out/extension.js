/******/ (() => { // webpackBootstrap
/******/ 	"use strict";
/******/ 	var __webpack_modules__ = ({

/***/ "./src/api/client.ts":
/*!***************************!*\
  !*** ./src/api/client.ts ***!
  \***************************/
/***/ ((__unused_webpack_module, exports) => {


Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.AEPClient = void 0;
class AEPClient {
    constructor(ctx, baseUrl, orgId) {
        this.ctx = ctx;
        this.baseUrl = baseUrl;
        this.orgId = orgId;
    }
    setToken(t) { this.token = t; }
    headers() {
        const h = { 'Content-Type': 'application/json', 'X-Org-Id': this.orgId };
        if (this.token)
            h['Authorization'] = `Bearer ${this.token}`;
        return h;
    }
    async startDeviceCode() {
        const r = await fetch(`${this.baseUrl}/oauth/device/start`, { method: 'POST', headers: this.headers() });
        if (!r.ok)
            throw new Error(await r.text());
        return await r.json();
    }
    async pollDeviceCode(deviceCode) {
        const r = await fetch(`${this.baseUrl}/oauth/device/poll`, { method: 'POST', headers: this.headers(), body: JSON.stringify({ device_code: deviceCode }) });
        if (!r.ok)
            throw new Error(await r.text());
        const tok = await r.json();
        this.setToken(tok.access_token);
        return tok;
    }
    async listMyJiraIssues() {
        const r = await fetch(`${this.baseUrl}/api/integrations/jira/my-issues`, { headers: this.headers() });
        if (!r.ok)
            return [];
        return await r.json();
    }
    async me() {
        const r = await fetch(`${this.baseUrl}/api/me`, { headers: this.headers() });
        if (!r.ok)
            return {};
        return await r.json();
    }
    async proposePlan(issueKey) {
        const r = await fetch(`${this.baseUrl}/api/agent/propose`, { method: 'POST', headers: this.headers(), body: JSON.stringify({ issue_key: issueKey }) });
        if (!r.ok)
            throw new Error(await r.text());
        return await r.json();
    }
    async applyPatch(patch) {
        const r = await fetch(`${this.baseUrl}/api/ai/apply-patch`, { method: 'POST', headers: this.headers(), body: JSON.stringify({ diff: patch, dry_run: false }) });
        const j = await r.json();
        if (!r.ok)
            throw new Error(j.detail || JSON.stringify(j));
        return j;
    }
}
exports.AEPClient = AEPClient;


/***/ }),

/***/ "./src/config.ts":
/*!***********************!*\
  !*** ./src/config.ts ***!
  \***********************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.getConfig = getConfig;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
function getConfig() {
    const c = vscode.workspace.getConfiguration('aep');
    return {
        baseUrl: String(c.get('baseUrl')),
        orgId: String(c.get('orgId')),
        llm: String(c.get('llm')),
        portalUrl: String(c.get('portalUrl'))
    };
}


/***/ }),

/***/ "./src/extension.ts":
/*!**************************!*\
  !*** ./src/extension.ts ***!
  \**************************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
const chatSidebar_1 = __webpack_require__(/*! ./features/chatSidebar */ "./src/features/chatSidebar.ts");
const planPanel_1 = __webpack_require__(/*! ./features/planPanel */ "./src/features/planPanel.ts");
const approvals_1 = __webpack_require__(/*! ./features/approvals */ "./src/features/approvals.ts");
const authPanel_1 = __webpack_require__(/*! ./features/authPanel */ "./src/features/authPanel.ts");
const client_1 = __webpack_require__(/*! ./api/client */ "./src/api/client.ts");
const config_1 = __webpack_require__(/*! ./config */ "./src/config.ts");
const OUTPUT_CHANNEL = 'AEP Agent';
let outputChannel;
async function activate(context) {
    outputChannel = vscode.window.createOutputChannel(OUTPUT_CHANNEL);
    const output = outputChannel;
    output.appendLine('Activating AEP Agent extension…');
    try {
        const cfg = (0, config_1.getConfig)();
        output.appendLine(`Using backend ${cfg.baseUrl} for org ${cfg.orgId}`);
        const client = new client_1.AEPClient(context, cfg.baseUrl, cfg.orgId);
        const approvals = new approvals_1.Approvals(context, client);
        const chat = new chatSidebar_1.ChatSidebarProvider(context, client);
        const plan = new planPanel_1.PlanPanelProvider(context, client, approvals);
        const auth = new authPanel_1.AuthPanel(context, client, cfg.portalUrl);
        const disposables = [
            vscode.window.registerWebviewViewProvider('aep.chatView', chat, { webviewOptions: { retainContextWhenHidden: true } }),
            vscode.window.registerWebviewViewProvider('aep.planView', plan, { webviewOptions: { retainContextWhenHidden: true } }),
            vscode.window.registerWebviewViewProvider('aep.authView', auth, { webviewOptions: { retainContextWhenHidden: true } }),
            vscode.commands.registerCommand('aep.signIn', () => startDeviceFlow(client, chat, output)),
            vscode.commands.registerCommand('aep.startSession', () => {
                vscode.window.showInformationMessage('Starting an AEP planning session…');
            }),
            vscode.commands.registerCommand('aep.openPortal', () => {
                const portal = cfg.portalUrl || 'https://portal.aep.navra.ai';
                vscode.env.openExternal(vscode.Uri.parse(portal));
            }),
            vscode.commands.registerCommand('aep.plan.approve', () => approvals.approveSelected()),
            vscode.commands.registerCommand('aep.plan.reject', () => approvals.rejectSelected()),
            vscode.commands.registerCommand('aep.applyPatch', () => plan.applySelectedPatch())
        ];
        context.subscriptions.push(...disposables, output);
        output.appendLine('AEP Agent extension activated successfully.');
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        output.appendLine(`Activation failed: ${message}`);
        vscode.window.showErrorMessage('AEP Agent extension failed to activate. Check the AEP Agent output channel for details.');
        throw error;
    }
}
async function startDeviceFlow(client, chat, output) {
    try {
        const flow = await client.startDeviceCode();
        output.appendLine('Device flow started. Opening browser for verification.');
        const verificationUrl = flow.verification_uri_complete || flow.verification_uri;
        const codeLabel = flow.user_code ? ` (code: ${flow.user_code})` : '';
        vscode.window.showInformationMessage(`Open the browser to complete sign-in${codeLabel}`, 'Open Browser').then(sel => {
            if (sel === 'Open Browser' && verificationUrl) {
                vscode.env.openExternal(vscode.Uri.parse(verificationUrl));
            }
        });
        if (!flow.device_code) {
            throw new Error('Device authorization response was missing a device code.');
        }
        await pollDeviceCode(client, flow.device_code, output);
        vscode.window.showInformationMessage('Signed in to AEP successfully.');
        chat.refresh();
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        output.appendLine(`Sign-in failed: ${message}`);
        vscode.window.showErrorMessage(`AEP sign-in failed: ${message}`);
    }
}
async function pollDeviceCode(client, deviceCode, output) {
    const maxAttempts = 90;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            await client.pollDeviceCode(deviceCode);
            output.appendLine('Received access token from device flow.');
            return;
        }
        catch (error) {
            const message = typeof error?.message === 'string' ? error.message : String(error);
            if (message.includes('428')) {
                await new Promise(resolve => setTimeout(resolve, 2000));
                continue;
            }
            throw error;
        }
    }
    throw new Error('Timed out waiting for device authorization.');
}
function deactivate() {
    outputChannel?.appendLine('AEP Agent extension deactivated.');
}


/***/ }),

/***/ "./src/features/approvals.ts":
/*!***********************************!*\
  !*** ./src/features/approvals.ts ***!
  \***********************************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.Approvals = void 0;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
class Approvals {
    constructor(ctx, client) {
        this.ctx = ctx;
        this.client = client;
        this.selected = null;
    }
    set(step) { this.selected = step; }
    async approve(step) { this.selected = step; await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Approving step…' }, async () => { }); }
    async reject(step) { this.selected = step; vscode.window.showInformationMessage('Step rejected'); }
    async approveSelected() { if (this.selected)
        await this.approve(this.selected); }
    async rejectSelected() { if (this.selected)
        await this.reject(this.selected); }
}
exports.Approvals = Approvals;


/***/ }),

/***/ "./src/features/authPanel.ts":
/*!***********************************!*\
  !*** ./src/features/authPanel.ts ***!
  \***********************************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.AuthPanel = void 0;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
const view_1 = __webpack_require__(/*! ../webview/view */ "./src/webview/view.ts");
class AuthPanel {
    constructor(ctx, client, portalUrl) {
        this.ctx = ctx;
        this.client = client;
        this.portalUrl = portalUrl;
    }
    resolveWebviewView(view) {
        this.view = view;
        view.webview.options = { enableScripts: true };
        const body = `
      <div class="card">
        <div class="row"><span class="h">Welcome to AEP Agent</span></div>
        <p>Sign in to connect your IDE with AEP. New here? <a class="link" id="signup">Create an account</a>.</p>
        <div class="row">
          <vscode-button id="signin">Sign In</vscode-button>
          <vscode-button appearance="secondary" id="openPortal">Open Portal</vscode-button>
        </div>
      </div>
      <div class="card" id="device" style="display:none;">
        <div class="h">Device Code</div>
        <p>We opened your browser. If asked, paste this code:</p>
        <pre class="mono" id="code"></pre>
        <div class="row"><vscode-button id="copy">Copy Code</vscode-button></div>
      </div>`;
        view.webview.html = (0, view_1.boilerplate)(view.webview, this.ctx, body, ['base.css'], ['auth.js']);
        view.webview.onDidReceiveMessage(async (m) => {
            try {
                if (m.type === 'open') {
                    const url = m.url === 'portal:' ? this.portalUrl : m.url;
                    vscode.env.openExternal(vscode.Uri.parse(url));
                }
                if (m.type === 'signin') {
                    const flow = await this.client.startDeviceCode();
                    view.webview.postMessage({ type: 'flow', flow });
                    vscode.env.openExternal(vscode.Uri.parse(flow.verification_uri_complete || flow.verification_uri));
                    await this.client.pollDeviceCode(flow.device_code);
                    view.webview.postMessage({ type: 'done' });
                    vscode.window.showInformationMessage('Signed in to AEP successfully.');
                }
            }
            catch (error) {
                const message = error?.message ?? String(error);
                vscode.window.showErrorMessage(`Authentication failed: ${message}`);
                view.webview.postMessage({ type: 'error', message });
            }
        });
    }
}
exports.AuthPanel = AuthPanel;


/***/ }),

/***/ "./src/features/chatSidebar.ts":
/*!*************************************!*\
  !*** ./src/features/chatSidebar.ts ***!
  \*************************************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.ChatSidebarProvider = void 0;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
const view_1 = __webpack_require__(/*! ../webview/view */ "./src/webview/view.ts");
class ChatSidebarProvider {
    constructor(ctx, client) {
        this.ctx = ctx;
        this.client = client;
    }
    resolveWebviewView(view) {
        this.view = view;
        view.webview.options = { enableScripts: true };
        this.render();
        view.webview.onDidReceiveMessage(async (m) => {
            console.log('ChatSidebar received message:', m);
            if (m.type === 'openExternal') {
                vscode.env.openExternal(vscode.Uri.parse(m.url));
            }
            else if (m.type === 'openPortal') {
                vscode.commands.executeCommand('aep.openPortal');
            }
            else if (m.type === 'pickIssue') {
                vscode.commands.executeCommand('aep.startSession');
            }
            else if (m.type === 'signIn') {
                vscode.commands.executeCommand('aep.signIn');
                // Refresh after sign in attempt
                setTimeout(() => this.render(), 2000);
            }
            else if (m.type === 'startSession') {
                vscode.commands.executeCommand('aep.startSession');
            }
            else if (m.type === 'refresh') {
                await this.render();
            }
            else if (m.type === 'chat' && m.message) {
                await this.handleChatMessage(m.message);
            }
        });
    }
    refresh() {
        if (this.view)
            this.render();
    }
    async sendHello() {
        const issues = await this.client.listMyJiraIssues();
        this.post({ type: 'hello', issues });
    }
    post(message) {
        if (this.view) {
            this.view.webview.postMessage(message);
        }
    }
    async render() {
        try {
            const [me, issues] = await Promise.all([
                this.client.me().catch(() => ({})),
                this.client.listMyJiraIssues().catch(() => [])
            ]);
            const greeting = (() => {
                const h = new Date().getHours();
                if (h < 12)
                    return 'Good morning';
                if (h < 18)
                    return 'Good afternoon';
                return 'Good evening';
            })();
            const makeIssue = (i) => `
      <div class="card">
        <div class="row"><b>${i.key}</b> — ${i.summary} <span class="chip">${i.status}</span></div>
        <div class="row">
          <vscode-button appearance="secondary" data-url="${i.url}" class="open">Open in Jira</vscode-button>
          <vscode-button class="plan">Plan</vscode-button>
        </div>
      </div>`;
            const body = me?.email ? `
      <div class="card">
        <div class="row"><span class="h">${greeting}, welcome to AEP Agent</span></div>
        <div class="row mono">Signed in as ${me.email}</div>
        <div class="row" style="gap:8px;margin-top:8px;">
          <vscode-button id="start" appearance="primary">Start Session</vscode-button>
          <vscode-button id="refresh" appearance="secondary">Refresh</vscode-button>
        </div>
      </div>
      ${issues.length ? issues.map(makeIssue).join('') : `<div class="empty">No issues found. Check your Jira integration.</div>`}
    ` : `
      <div class="landing-container">
        <div class="hero-section">
          <div class="logo-area">
            <div class="logo">🤖</div>
            <h1>AEP Agent</h1>
            <p class="tagline">Your AI-powered development assistant</p>
            <div class="status-indicator status-disconnected">
              ⚠️ Not connected - Authentication required
            </div>
          </div>

          <div class="auth-section">
            <vscode-button appearance="primary" id="signIn">
              🔐 Sign In with Auth0
            </vscode-button>
            <vscode-button appearance="secondary" id="getStarted">
              🧪 Demo Mode
            </vscode-button>
            <p style="margin-top: 1rem; font-size: 0.85em; color: var(--vscode-descriptionForeground); text-align: center;">
              ℹ️ Requires AEP backend server for authentication
            </p>
          </div>
        </div>

        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">💻</div>
            <h3>Code Analysis</h3>
            <p>Get instant AI-powered code reviews and suggestions</p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">📋</div>
            <h3>Task Planning</h3>
            <p>Break down JIRA issues into actionable steps</p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">🔧</div>
            <h3>Auto Patches</h3>
            <p>Apply AI-generated code changes with confidence</p>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">👥</div>
            <h3>Team Collaboration</h3>
            <p>Share insights and collaborate with your team</p>
          </div>
        </div>

        <div class="quick-start">
          <h3>Quick Start</h3>
          <div class="quick-actions">
            <button class="action-btn" id="tryDemo">
              <span class="action-icon">🎯</span>
              <div>
                <div class="action-title">Try Demo</div>
                <div class="action-desc">Explore features without signing in</div>
              </div>
            </button>
            
            <button class="action-btn" id="loadSample">
              <span class="action-icon">📝</span>
              <div>
                <div class="action-title">Load Sample Tasks</div>
                <div class="action-desc">See how AEP handles real projects</div>
              </div>
            </button>
          </div>
        </div>

        <div class="demo-chat" id="demoChat" style="display: none;">
          <div class="chat-header">
            <h3>💬 Chat with AEP Agent</h3>
            <button class="close-btn" id="closeDemo">×</button>
          </div>
          <div class="chat-messages" id="chatMessages"></div>
          <div class="chat-input-area">
            <textarea id="chatInput" placeholder="Ask me anything about your code..."></textarea>
            <button id="sendMessage" class="send-btn">Send</button>
          </div>
        </div>
      </div>`;
            this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, body, ['base.css', 'landing.css'], ['chat.js']);
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            console.error('ChatSidebar render failed:', message);
            const fallback = `
        <div class="landing-container">
          <div class="hero-section">
            <div class="logo-area">
              <div class="logo">⚠️</div>
              <h1>AEP Agent</h1>
              <p class="tagline">We couldn't load your workspace right now.</p>
            </div>
            <p style="color: var(--vscode-descriptionForeground);">${this.escape(message)}</p>
            <vscode-button appearance="secondary" id="retry">Retry</vscode-button>
          </div>
        </div>`;
            this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, fallback, ['base.css', 'landing.css'], ['chat.js']);
        }
    }
    escape(text) {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    async handleChatMessage(message) {
        try {
            // Show user message immediately
            this.showChatMessage('user', message);
            // Show typing indicator
            this.showChatMessage('system', '🤔 Thinking...');
            // Send to AI backend
            const response = await fetch(`${this.client['baseUrl']}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, type: 'question' })
            });
            if (response.ok) {
                const result = await response.json();
                this.showChatMessage('assistant', result.response || result.message || 'I received your message but had trouble generating a response.');
            }
            else {
                this.showChatMessage('assistant', 'Sorry, I\'m having trouble connecting right now. Please try again later.');
            }
        }
        catch (error) {
            console.error('Chat error:', error);
            this.showChatMessage('assistant', 'I encountered an error processing your message. Please check your connection and try again.');
        }
    }
    showChatMessage(role, content) {
        // Send message to webview for display
        if (this.view) {
            this.view.webview.postMessage({
                type: 'chatMessage',
                role,
                content,
                timestamp: new Date().toLocaleTimeString()
            });
        }
    }
}
exports.ChatSidebarProvider = ChatSidebarProvider;


/***/ }),

/***/ "./src/features/planPanel.ts":
/*!***********************************!*\
  !*** ./src/features/planPanel.ts ***!
  \***********************************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.PlanPanelProvider = void 0;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
const view_1 = __webpack_require__(/*! ../webview/view */ "./src/webview/view.ts");
class PlanPanelProvider {
    constructor(ctx, client, approvals) {
        this.ctx = ctx;
        this.client = client;
        this.approvals = approvals;
        this.steps = [];
        this.selectedIndex = 0;
        this.selectedPatch = null;
    }
    resolveWebviewView(view) {
        this.view = view;
        view.webview.options = { enableScripts: true };
        this.render();
        view.webview.onDidReceiveMessage(async (message) => {
            try {
                if (message.type === 'load-plan' && message.issue) {
                    this.steps = await this.client.proposePlan(message.issue);
                    this.selectedIndex = 0;
                    this.selectedPatch = this.steps[0]?.patch || null;
                    this.render();
                    return;
                }
                if (message.type === 'load-demo-plan') {
                    this.steps = this.demoPlan();
                    this.selectedIndex = 0;
                    this.selectedPatch = this.steps[0]?.patch || null;
                    this.render();
                    vscode.window.showInformationMessage('Demo plan loaded! 🚀');
                    return;
                }
                if (message.type === 'select' && typeof message.index === 'number') {
                    this.selectedIndex = message.index;
                    this.selectedPatch = this.steps[message.index]?.patch || null;
                    this.render();
                    return;
                }
                if (message.type === 'approve') {
                    await this.approvals.approve(this.steps[this.selectedIndex]);
                    return;
                }
                if (message.type === 'reject') {
                    await this.approvals.reject(this.steps[this.selectedIndex]);
                    return;
                }
                if (message.type === 'applyPatch') {
                    await vscode.commands.executeCommand('aep.applyPatch');
                    return;
                }
            }
            catch (error) {
                this.showError(error);
            }
        });
    }
    refresh() { if (this.view)
        this.render(); }
    async applySelectedPatch() {
        if (!this.selectedPatch) {
            vscode.window.showWarningMessage('No patch selected');
            return;
        }
        try {
            const res = await this.client.applyPatch(this.selectedPatch);
            vscode.window.showInformationMessage(res.applied ? 'Patch applied' : 'Patch failed');
        }
        catch (error) {
            vscode.window.showErrorMessage(`Unable to apply patch: ${error?.message ?? error}`);
        }
    }
    render() {
        if (!this.view) {
            return;
        }
        try {
            if (this.steps.length === 0) {
                const body = `
          <div class="plan-placeholder">
            <div class="card">
              <div class="h">Plan &amp; Act</div>
              <p class="lead">Select an issue from the Agent view to generate an execution plan.</p>
              <vscode-button id="demo-plan" appearance="secondary">🧪 Load Demo Plan</vscode-button>
            </div>
            <ul class="how-it-works">
              <li>Pick a JIRA issue from the Agent tab</li>
              <li>AEP drafts a reviewable plan</li>
              <li>Approve or reject each step</li>
              <li>Apply AI-generated patches with one click</li>
            </ul>
          </div>`;
                this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
                return;
            }
            const body = `
        <div class="wrap">
          <div class="card"><div class="h">Plan &amp; Act</div></div>
          <div class="steps">
            <ul>
              ${this.steps.map((s, i) => `<li class="${i === this.selectedIndex ? 'sel' : ''}" data-i="${i}">${this.escape(s.kind)}: ${this.escape(s.title)}</li>`).join('')}
            </ul>
          </div>
          <div class="details">
            ${this.selectedPatch ? `<pre>${this.escape(this.selectedPatch)}</pre>` : '<em>Select a step to inspect details</em>'}
          </div>
          <div class="actions">
            <vscode-button id="approve">Approve</vscode-button>
            <vscode-button appearance="secondary" id="reject">Reject</vscode-button>
            <vscode-button id="apply">Apply Patch</vscode-button>
          </div>
        </div>`;
            this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
        }
        catch (error) {
            this.showError(error);
        }
    }
    escape(text) {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    demoPlan() {
        return [
            { kind: 'Setup', title: 'Analyze requirements and create project structure', description: 'Analyze requirements and create project structure', status: 'pending', patch: '// Demo patch 1\n+ Create new component\n- Remove old file' },
            { kind: 'Implement', title: 'Implement core functionality', description: 'Implement core functionality', status: 'pending', patch: '// Demo patch 2\n+ Add main logic\n+ Update tests' },
            { kind: 'Validate', title: 'Add error handling and validation', description: 'Add error handling and validation', status: 'pending', patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation' }
        ];
    }
    showError(error) {
        if (!this.view) {
            return;
        }
        const message = error instanceof Error ? error.message : String(error);
        const body = `
      <div class="card error">
        <div class="h">We hit a snag</div>
        <p>${this.escape(message)}</p>
        <vscode-button id="demo-plan" appearance="secondary">Try Demo Plan</vscode-button>
      </div>`;
        this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
    }
}
exports.PlanPanelProvider = PlanPanelProvider;


/***/ }),

/***/ "./src/webview/view.ts":
/*!*****************************!*\
  !*** ./src/webview/view.ts ***!
  \*****************************/
/***/ (function(__unused_webpack_module, exports, __webpack_require__) {


var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.boilerplate = boilerplate;
exports.asset = asset;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
function boilerplate(view, ctx, body, styles = [], scripts = []) {
    const nonce = Math.random().toString(36).slice(2);
    const cssLinks = styles.map(s => `<link rel="stylesheet" href="${asset(view, ctx, s)}">`).join('');
    const jsLinks = scripts.map(s => `<script nonce="${nonce}" src="${asset(view, ctx, s)}"></script>`).join('');
    return `<!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${view.cspSource} https:; style-src ${view.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'; font-src ${view.cspSource} https:;">
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link href="https://microsoft.github.io/vscode-webview-ui-toolkit/dist/toolkit.min.css" rel="stylesheet" />
    ${cssLinks}
  </head>
  <body>
    ${body}
    ${jsLinks}
  </body>
  </html>`;
}
function asset(view, ctx, pathRel) {
    return view.asWebviewUri(vscode.Uri.joinPath(ctx.extensionUri, 'media', pathRel));
}


/***/ }),

/***/ "vscode":
/*!*************************!*\
  !*** external "vscode" ***!
  \*************************/
/***/ ((module) => {

module.exports = require("vscode");

/***/ })

/******/ 	});
/************************************************************************/
/******/ 	// The module cache
/******/ 	var __webpack_module_cache__ = {};
/******/ 	
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/ 		// Check if module is in cache
/******/ 		var cachedModule = __webpack_module_cache__[moduleId];
/******/ 		if (cachedModule !== undefined) {
/******/ 			return cachedModule.exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = __webpack_module_cache__[moduleId] = {
/******/ 			// no module.id needed
/******/ 			// no module.loaded needed
/******/ 			exports: {}
/******/ 		};
/******/ 	
/******/ 		// Execute the module function
/******/ 		__webpack_modules__[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/ 	
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/ 	
/************************************************************************/
/******/ 	
/******/ 	// startup
/******/ 	// Load entry module and return exports
/******/ 	// This entry module is referenced by other modules so it can't be inlined
/******/ 	var __webpack_exports__ = __webpack_require__("./src/extension.ts");
/******/ 	module.exports = __webpack_exports__;
/******/ 	
/******/ })()
;
//# sourceMappingURL=extension.js.map