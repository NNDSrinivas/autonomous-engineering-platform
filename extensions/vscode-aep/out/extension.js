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
        return await r.json();
    }
    async listMyJiraIssues() {
        const r = await fetch(`${this.baseUrl}/api/integrations/jira/my-issues`, { headers: this.headers() });
        if (!r.ok)
            return [];
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

/***/ "./src/auth/deviceCode.ts":
/*!********************************!*\
  !*** ./src/auth/deviceCode.ts ***!
  \********************************/
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
exports.ensureAuth = ensureAuth;
const vscode = __importStar(__webpack_require__(/*! vscode */ "vscode"));
const storage_1 = __webpack_require__(/*! ../util/storage */ "./src/util/storage.ts");
async function ensureAuth(ctx, client) {
    const kv = new storage_1.KV(ctx);
    let token = kv.get('aep.token');
    if (token) {
        client.setToken(token);
        return;
    }
    const pick = await vscode.window.showQuickPick([
        { label: 'Device Code', description: 'Open browser and paste code' }
    ], { placeHolder: 'Choose sign-in method' });
    if (!pick)
        return;
    const flow = await client.startDeviceCode();
    await vscode.env.openExternal(vscode.Uri.parse(flow.verification_uri_complete || flow.verification_uri));
    // Show user code for manual entry if needed
    await vscode.window.showInputBox({
        prompt: 'Device code (pre-filled, press Enter to continue)',
        value: flow.user_code,
        ignoreFocusOut: true
    });
    const tok = await client.pollDeviceCode(flow.device_code);
    await kv.set('aep.token', tok.access_token);
    client.setToken(tok.access_token);
}


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
        llm: String(c.get('llm'))
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
const deviceCode_1 = __webpack_require__(/*! ./auth/deviceCode */ "./src/auth/deviceCode.ts");
const chatSidebar_1 = __webpack_require__(/*! ./features/chatSidebar */ "./src/features/chatSidebar.ts");
const planPanel_1 = __webpack_require__(/*! ./features/planPanel */ "./src/features/planPanel.ts");
const approvals_1 = __webpack_require__(/*! ./features/approvals */ "./src/features/approvals.ts");
const client_1 = __webpack_require__(/*! ./api/client */ "./src/api/client.ts");
const config_1 = __webpack_require__(/*! ./config */ "./src/config.ts");
async function activate(context) {
    console.log('🚀 AEP Extension activating...');
    try {
        // Show activation in VS Code
        vscode.window.showInformationMessage('AEP Extension activated successfully!');
        const cfg = (0, config_1.getConfig)();
        console.log('📊 Extension config:', { baseUrl: cfg.baseUrl, orgId: cfg.orgId });
        const client = new client_1.AEPClient(context, cfg.baseUrl, cfg.orgId);
        const approvals = new approvals_1.Approvals(context, client);
        const chat = new chatSidebar_1.ChatSidebarProvider(context, client);
        const plan = new planPanel_1.PlanPanelProvider(context, client, approvals);
        console.log('🔧 Registering webview providers...');
        context.subscriptions.push(vscode.window.registerWebviewViewProvider('aep.chatView', chat), vscode.window.registerWebviewViewProvider('aep.planView', plan), vscode.commands.registerCommand('aep.signIn', async () => {
            await (0, deviceCode_1.ensureAuth)(context, client);
            vscode.window.showInformationMessage('AEP: Signed in');
            chat.refresh();
            plan.refresh();
        }), vscode.commands.registerCommand('aep.startSession', async () => {
            await (0, deviceCode_1.ensureAuth)(context, client);
            await chat.sendHello();
        }), vscode.commands.registerCommand('aep.plan.approve', async () => approvals.approveSelected()), vscode.commands.registerCommand('aep.plan.reject', async () => approvals.rejectSelected()), vscode.commands.registerCommand('aep.applyPatch', async () => plan.applySelectedPatch()));
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
const time_1 = __webpack_require__(/*! ../util/time */ "./src/util/time.ts");
class ChatSidebarProvider {
    constructor(ctx, client) {
        this.ctx = ctx;
        this.client = client;
    }
    resolveWebviewView(view) {
        console.log('🔧 ChatSidebarProvider resolveWebviewView called');
        try {
            this.view = view;
            view.webview.options = { enableScripts: true };
            this.render();
            console.log('✅ ChatSidebarProvider webview resolved successfully');
        }
        catch (error) {
            console.error('❌ ChatSidebarProvider resolveWebviewView failed:', error);
        }
    }
    refresh() { if (this.view)
        this.render(); }
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
        const now = (0, time_1.greeting)();
        try {
            const issues = await this.client.listMyJiraIssues();
            const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="${this.cssUri('chat.css')}">
</head>
<body>
<div class="wrap">
  <h2>${now}! 👋</h2>
  <p>Select a Jira task to begin, or ask a question.</p>
  <ul class="issues">
    ${issues.map(i => `<li data-key="${i.key}"><b>${i.key}</b> – ${i.summary} <span class="st">${i.status}</span></li>`).join('')}
  </ul>
  <div class="ask">
    <input id="q" placeholder="Ask the agent about your project…" />
    <button id="ask">Ask</button>
  </div>
</div>
<script>${this.script('chat.js')}</script>
</body>
</html>`;
            this.view.webview.html = html;
        }
        catch (error) {
            // Show sign-in UI when not authenticated or backend not available
            const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="${this.cssUri('chat.css')}">
</head>
<body>
<div class="wrap">
  <h2>${now}! 👋</h2>
  <p>Welcome to AEP Agent! Please sign in to get started.</p>
  <div class="signin">
    <button id="signin">🔑 Sign In to AEP</button>
  </div>
  <div class="status">
    <p><small>Backend: <span id="status">Checking...</span></small></p>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('signin')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'signin' });
  });
  
  // Check backend status
  fetch('http://localhost:8000/health').then(r => r.ok ? 'Connected' : 'Error').catch(() => 'Not running')
    .then(status => document.getElementById('status').textContent = status);
</script>
</body>
</html>`;
            this.view.webview.html = html;
        }
        this.view.webview.onDidReceiveMessage(async (m) => {
            if (m.type === 'pick-issue') {
                vscode.commands.executeCommand('revealView', 'aep.planView');
                vscode.commands.executeCommand('aep.startSession');
            }
            if (m.type === 'ask') {
                vscode.window.showInformationMessage('Question sent (wire to backend Q&A endpoint)');
            }
            if (m.type === 'signin') {
                vscode.commands.executeCommand('aep.signIn');
            }
        });
    }
    cssUri(name) { return this.view.webview.asWebviewUri(vscode.Uri.file(`${this.ctx.extensionPath}/media/${name}`)); }
    script(name) {
        // inline minimal script for MVP
        if (name === 'chat.js')
            return `(() => {
      const vscode = acquireVsCodeApi();
      const ul = document.querySelector('.issues');
      ul?.addEventListener('click', (e)=>{
        const li = (e.target as HTMLElement).closest('li');
        if(!li) return; vscode.postMessage({ type:'pick-issue', key: li.getAttribute('data-key') });
      });
      document.getElementById('ask')?.addEventListener('click', ()=>{
        const v = (document.getElementById('q') as HTMLInputElement).value;
        vscode.postMessage({ type:'ask', q: v });
      });
    })();`;
        return '';
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
        try {
            this.view = view;
            view.webview.options = { enableScripts: true };
            this.render();
            console.log('✅ PlanPanelProvider webview resolved successfully');
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
        const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="${this.css('plan.css')}">
</head>
<body>
<div class="wrap">
  <h3>Plan & Act</h3>
  ${this.steps.length > 0 ? `
  <div class="steps">
    <ul>
      ${this.steps.map((s, i) => `<li class="${i === this.selectedIndex ? 'sel' : ''}" data-i="${i}">${s.kind}: ${s.title}</li>`).join('')}
    </ul>
  </div>
  <div class="details">
    ${this.selectedPatch ? `<pre>${this.escape(this.selectedPatch)}</pre>` : '<em>Select a step</em>'}
  </div>
  <div class="actions">
    <button id="approve">Approve</button>
    <button id="reject">Reject</button>
    <button id="apply">Apply Patch</button>
  </div>
  ` : `
  <div class="empty">
    <p>Select a JIRA task from the Agent panel to generate a plan.</p>
    <p><small>Plans break down tasks into reviewable steps with code patches.</small></p>
  </div>
  `}
</div>
<script>${this.script('plan.js')}</script>
</body>
</html>`;
        this.view.webview.html = html;
    }
    css(name) { return this.view.webview.asWebviewUri(vscode.Uri.file(`${this.ctx.extensionPath}/media/${name}`)); }
    escape(s) { return s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }
    script(name) {
        if (name === 'plan.js')
            return `(() => {
    const vscode = acquireVsCodeApi();
    const ul = document.querySelector('.steps ul');
    ul?.addEventListener('click', (e)=>{ const li = (e.target as HTMLElement).closest('li'); if(!li) return; const i = Number(li.getAttribute('data-i')); vscode.postMessage({type:'select', index:i}); });
    document.getElementById('approve')?.addEventListener('click', ()=> vscode.postMessage({type:'approve'}));
    document.getElementById('reject')?.addEventListener('click', ()=> vscode.postMessage({type:'reject'}));
    document.getElementById('apply')?.addEventListener('click', ()=> vscode.postMessage({type:'applyPatch'}));
  })();`;
        return '';
    }
}
exports.PlanPanelProvider = PlanPanelProvider;


/***/ }),

/***/ "./src/util/storage.ts":
/*!*****************************!*\
  !*** ./src/util/storage.ts ***!
  \*****************************/
/***/ ((__unused_webpack_module, exports) => {


Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.KV = void 0;
class KV {
    constructor(ctx) {
        this.ctx = ctx;
    }
    get(k) { return this.ctx.globalState.get(k); }
    set(k, v) { return this.ctx.globalState.update(k, v); }
}
exports.KV = KV;


/***/ }),

/***/ "./src/util/time.ts":
/*!**************************!*\
  !*** ./src/util/time.ts ***!
  \**************************/
/***/ ((__unused_webpack_module, exports) => {


Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.greeting = greeting;
function greeting(now = new Date()) {
    const h = now.getHours();
    if (h < 12)
        return 'Good morning';
    if (h < 18)
        return 'Good afternoon';
    return 'Good evening';
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