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
async function activate(context) {
    console.log('🚀 AEP Extension activating...');
    console.log('🔍 Extension context:', {
        globalState: Object.keys(context.globalState.keys()),
        workspaceState: Object.keys(context.workspaceState.keys()),
        subscriptions: context.subscriptions.length
    });
    // Show immediate activation confirmation
    vscode.window.showInformationMessage('🚀 AEP Extension is ACTIVATING...', 'Show Console').then(selection => {
        if (selection === 'Show Console') {
            vscode.commands.executeCommand('workbench.action.toggleDevTools');
        }
    });
    try {
        // Show activation in VS Code
        vscode.window.showInformationMessage('AEP Extension activated successfully!');
        const cfg = (0, config_1.getConfig)();
        console.log('📊 Extension config:', { baseUrl: cfg.baseUrl, orgId: cfg.orgId });
        const client = new client_1.AEPClient(context, cfg.baseUrl, cfg.orgId);
        const approvals = new approvals_1.Approvals(context, client);
        const chat = new chatSidebar_1.ChatSidebarProvider(context, client);
        const plan = new planPanel_1.PlanPanelProvider(context, client, approvals);
        const auth = new authPanel_1.AuthPanel(context, client, cfg.portalUrl);
        console.log('🔧 Registering webview providers...');
        console.log('🎯 About to register:', {
            chatProviderInstance: !!chat,
            planProviderInstance: !!plan,
            vscodeWindow: !!vscode.window
        });
        const chatProvider = vscode.window.registerWebviewViewProvider('aep.chatView', chat);
        const planProvider = vscode.window.registerWebviewViewProvider('aep.planView', plan);
        const authProvider = vscode.window.registerWebviewViewProvider('aep.authView', auth);
        console.log('📋 Registered providers:', {
            chatView: 'aep.chatView',
            planView: 'aep.planView',
            chatDisposable: !!chatProvider,
            planDisposable: !!planProvider
        });
        context.subscriptions.push(chatProvider, planProvider, authProvider, vscode.commands.registerCommand('aep.signIn', async () => {
            try {
                const flow = await client.startDeviceCode();
                vscode.window.showInformationMessage(`Open browser to complete sign-in. Code: ${flow.user_code}`, 'Open').then(sel => {
                    if (sel === 'Open') {
                        vscode.env.openExternal(vscode.Uri.parse(flow.verification_uri_complete || flow.verification_uri));
                    }
                });
                // Simple poll loop
                const poll = async () => {
                    try {
                        await client.pollDeviceCode(flow.device_code);
                        vscode.window.showInformationMessage('✅ AEP: Successfully signed in');
                        chat.refresh();
                    }
                    catch (e) {
                        if (String(e.message || e).includes('428')) {
                            // Still pending, continue polling
                            setTimeout(poll, 2000);
                        }
                        else {
                            vscode.window.showErrorMessage('AEP sign-in failed: ' + (e.message || e));
                        }
                    }
                };
                poll();
            }
            catch (e) {
                vscode.window.showErrorMessage('AEP sign-in could not start: ' + (e.message || e));
            }
        }), vscode.commands.registerCommand('aep.startSession', async () => {
            vscode.window.showInformationMessage('Session starting…');
            // hook to your existing planning flow
        }), vscode.commands.registerCommand('aep.openPortal', async () => {
            const portal = cfg.portalUrl || 'https://portal.aep.navra.ai';
            vscode.env.openExternal(vscode.Uri.parse(portal));
        }), vscode.commands.registerCommand('aep.plan.approve', async () => approvals.approveSelected()), vscode.commands.registerCommand('aep.plan.reject', async () => approvals.rejectSelected()), vscode.commands.registerCommand('aep.applyPatch', async () => plan.applySelectedPatch()), 
        // Debug command to test webview providers
        vscode.commands.registerCommand('aep.debug.testWebviews', async () => {
            console.log('🧪 Testing webview providers...');
            vscode.window.showInformationMessage('Testing webview providers - check console');
            // Force refresh webviews
            chat.refresh();
            plan.refresh();
            // Try to focus on the AEP views
            await vscode.commands.executeCommand('workbench.view.extension.aep');
        }));
        console.log('✅ AEP Extension activated successfully');
        console.log('Setting up vscode host providers...');
        vscode.window.showInformationMessage('AEP Extension loaded! Check the Activity Bar for AEP icon.');
    }
    catch (error) {
        console.error('❌ AEP Extension activation failed:', error);
        vscode.window.showErrorMessage(`AEP Extension failed to activate: ${error}`);
    }
}
function deactivate() {
    console.log('🛑 AEP Extension deactivating...');
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
        // Check authentication status and load user info
        const [me, issues] = await Promise.all([
            this.client.me().catch(() => ({})),
            this.client.listMyJiraIssues().catch(() => [])
        ]);
        const greeting = (() => {
            const h = new Date().getHours();
            return h < 12 ? 'Good morning' : 'Good afternoon';
        })();
        const makeIssue = (i) => `
      <div class="card">
        <div class="row"><b>${i.key}</b> — ${i.summary} <span class="chip">${i.status}</span></div>
        <div class="row">
          <vscode-button appearance="secondary" data-url="${i.url}" class="open">Open in Jira</vscode-button>
          <vscode-button class="plan">Plan</vscode-button>
        </div>
      </div>`;
        // Show authenticated view if user is signed in, otherwise show sign-in
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
              � Sign In with Auth0
            </vscode-button>
            <vscode-button appearance="secondary" id="getStarted">
              � Demo Mode
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
            <h3>� Chat with AEP Agent</h3>
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
        console.log('🔧 PlanPanelProvider resolveWebviewView called');
        console.log('🔍 Webview details:', {
            viewType: view.viewType,
            title: view.title,
            description: view.description
        });
        try {
            this.view = view;
            view.webview.options = { enableScripts: true };
            // Immediately set simple HTML to test
            view.webview.html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { 
      font-family: var(--vscode-font-family); 
      color: var(--vscode-foreground); 
      background: var(--vscode-editor-background); 
      margin: 16px; 
      padding: 16px;
    }
    .test-message { 
      background: var(--vscode-textBlockQuote-background); 
      padding: 16px; 
      border-radius: 8px; 
      border-left: 4px solid var(--vscode-focusBorder);
      margin-bottom: 16px;
    }
    button { 
      padding: 8px 16px; 
      background: var(--vscode-button-background); 
      color: var(--vscode-button-foreground); 
      border: none; 
      border-radius: 4px; 
      cursor: pointer; 
    }
  </style>
</head>
<body>
  <div class="test-message">
    <h3>📋 Plan & Act - Connection Test</h3>
    <p>This is a test to verify the webview is working properly.</p>
    <button onclick="testDemo()">Load Demo Plan</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    function testDemo() {
      vscode.postMessage({ type: 'load-demo-plan' });
    }
  </script>
</body>
</html>`;
            console.log('✅ PlanPanelProvider webview HTML set successfully');
            // Then call the full render
            setTimeout(() => {
                this.render();
            }, 1000);
        }
        catch (error) {
            console.error('❌ PlanPanelProvider resolveWebviewView failed:', error);
        }
        view.webview.onDidReceiveMessage(async (m) => {
            if (m.type === 'load-plan' && m.issue) {
                this.steps = await this.client.proposePlan(m.issue);
                this.selectedIndex = 0;
                this.selectedPatch = this.steps[0]?.patch || null;
                this.render();
            }
            if (m.type === 'load-demo-plan') {
                // Load demo plan for testing
                this.steps = [
                    { kind: 'setup', title: 'Analyze requirements and create project structure', description: 'Analyze requirements and create project structure', status: 'pending', patch: '// Demo patch 1\n+ Create new component\n- Remove old file' },
                    { kind: 'implement', title: 'Implement core functionality', description: 'Implement core functionality', status: 'pending', patch: '// Demo patch 2\n+ Add main logic\n+ Update tests' },
                    { kind: 'validate', title: 'Add error handling and validation', description: 'Add error handling and validation', status: 'pending', patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation' }
                ];
                this.selectedIndex = 0;
                this.selectedPatch = this.steps[0]?.patch || null;
                this.render();
                vscode.window.showInformationMessage('Demo plan loaded! 🚀');
            }
            if (m.type === 'select' && typeof m.index === 'number') {
                this.selectedIndex = m.index;
                this.selectedPatch = this.steps[m.index]?.patch || null;
                this.render();
            }
            if (m.type === 'approve') {
                this.approvals.approve(this.steps[this.selectedIndex]);
            }
            if (m.type === 'reject') {
                this.approvals.reject(this.steps[this.selectedIndex]);
            }
            if (m.type === 'applyPatch') {
                vscode.commands.executeCommand('aep.applyPatch');
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
        const res = await this.client.applyPatch(this.selectedPatch);
        vscode.window.showInformationMessage(res.applied ? 'Patch applied' : 'Patch failed');
    }
    render() {
        console.log('🎨 PlanPanelProvider render() called with steps:', this.steps.length);
        // Show default content if no steps are loaded
        if (this.steps.length === 0) {
            const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); margin: 16px; }
    .wrap { max-width: 400px; }
    h2 { color: var(--vscode-foreground); margin-bottom: 16px; }
    p { color: var(--vscode-descriptionForeground); margin-bottom: 16px; }
    .placeholder { text-align: center; padding: 40px 20px; border: 2px dashed var(--vscode-contrastBorder); border-radius: 8px; background: var(--vscode-textBlockQuote-background); }
    .placeholder h3 { margin-bottom: 16px; color: var(--vscode-foreground); }
    .sample-issue { background: var(--vscode-list-hoverBackground); padding: 12px; margin: 8px 0; border-radius: 4px; cursor: pointer; border: 1px solid var(--vscode-contrastBorder); }
    .sample-issue:hover { background: var(--vscode-list-activeSelectionBackground); }
    button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; margin: 4px; }
    button:hover { background: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
<div class="wrap">
  <h2>📋 Plan & Act</h2>
  <div class="placeholder">
    <h3>🚀 Ready to Plan!</h3>
    <p>Select a JIRA issue from the Agent tab to generate an execution plan.</p>
    <div style="margin-top: 20px;">
      <p><strong>How it works:</strong></p>
      <ol style="text-align: left; display: inline-block;">
        <li>Choose a JIRA issue in the Agent tab</li>
        <li>AI generates a step-by-step plan</li>
        <li>Review and approve each step</li>
        <li>Apply code changes automatically</li>
      </ol>
    </div>
    <div style="margin-top: 20px;">
      <button id="demo-plan">🧪 Load Demo Plan</button>
    </div>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('demo-plan')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'load-demo-plan' });
  });
</script>
</body>
</html>`;
            this.view.webview.html = html;
            return;
        }
        // Show actual plan content using new boilerplate
        const body = `
      <div class="wrap">
        <div class="card"><div class="h">Plan & Act</div></div>
        <div class="steps">
          <ul>
            ${this.steps.map((s, i) => `<li class="${i === this.selectedIndex ? 'sel' : ''}" data-i="${i}">${s.kind}: ${s.title}</li>`).join('')}
          </ul>
        </div>
        <div class="details">
          ${this.selectedPatch ? `<pre>${this.escape(this.selectedPatch)}</pre>` : '<em>Select a step</em>'}
        </div>
        <div class="actions">
          <vscode-button id="approve">Approve</vscode-button>
          <vscode-button appearance="secondary" id="reject">Reject</vscode-button>
          <vscode-button id="apply">Apply Patch</vscode-button>
        </div>
      </div>`;
        this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, body, ['base.css', 'plan.css'], ['plan.js']);
    }
    escape(text) {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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