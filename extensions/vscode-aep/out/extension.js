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
        const chatProvider = vscode.window.registerWebviewViewProvider('aep.chatView', chat);
        const planProvider = vscode.window.registerWebviewViewProvider('aep.planView', plan);
        console.log('📋 Registered providers:', {
            chatView: 'aep.chatView',
            planView: 'aep.planView'
        });
        context.subscriptions.push(chatProvider, planProvider, vscode.commands.registerCommand('aep.signIn', async () => {
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
        console.log('🎨 ChatSidebarProvider render() called');
        try {
            console.log('🔍 Attempting to fetch JIRA issues...');
            const issues = await this.client.listMyJiraIssues();
            console.log('✅ Successfully fetched issues:', issues.length);
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
    .issues { list-style: none; padding: 0; margin: 16px 0; }
    .issues li { background: var(--vscode-list-hoverBackground); padding: 12px; margin: 8px 0; border-radius: 4px; cursor: pointer; border: 1px solid var(--vscode-contrastBorder); }
    .issues li:hover { background: var(--vscode-list-activeSelectionBackground); }
    .ask { margin-top: 16px; display: flex; gap: 8px; }
    .ask input { flex: 1; padding: 8px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; }
    .ask button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; }
    .st { float: right; font-size: 0.8em; opacity: 0.7; }
  </style>
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
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('ask')?.addEventListener('click', () => {
    const input = document.getElementById('q');
    const question = input.value.trim();
    if (question) {
      vscode.postMessage({ type: 'ask', question });
      input.value = '';
    }
  });
  document.querySelectorAll('.issues li').forEach(li => {
    li.addEventListener('click', () => {
      const key = li.getAttribute('data-key');
      vscode.postMessage({ type: 'selectIssue', key });
    });
  });
</script>
</body>
</html>`;
            this.view.webview.html = html;
        }
        catch (error) {
            console.warn('⚠️ Could not fetch issues, showing sign-in UI:', error);
            // Show sign-in UI when not authenticated or backend not available
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
    .signin button { padding: 12px 24px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    .signin button:hover { background: var(--vscode-button-hoverBackground); }
    .status { margin-top: 16px; padding: 12px; background: var(--vscode-textBlockQuote-background); border-left: 4px solid var(--vscode-textBlockQuote-border); border-radius: 4px; }
    .error { color: var(--vscode-errorForeground); font-family: monospace; font-size: 12px; margin-top: 8px; }
  </style>
</head>
<body>
<div class="wrap">
  <h2>${now}! 👋</h2>
  <p>Welcome to AEP Agent! Please sign in to get started.</p>
  <div class="signin">
    <button id="signin">🔑 Sign In to AEP</button>
  </div>
  <div class="status">
    <p><strong>Status:</strong> <span id="status">Not authenticated</span></p>
    <div class="error">Error: ${error instanceof Error ? error.message : String(error)}</div>
  </div>
  <div style="margin-top: 20px;">
    <p><strong>Getting Started:</strong></p>
    <ol>
      <li>Click "Sign In to AEP" above</li>
      <li>Complete the OAuth flow</li>
      <li>Start working with JIRA issues</li>
    </ol>
  </div>
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.getElementById('signin')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'signin' });
  });
</script>
</body>
</html>`;
            this.view.webview.html = html;
        }
        // Set up message handling
        this.view.webview.onDidReceiveMessage(async (m) => {
            if (m.type === 'selectIssue') {
                vscode.commands.executeCommand('workbench.view.extension.aep');
                vscode.window.showInformationMessage(`Selected issue: ${m.key}`);
            }
            if (m.type === 'ask') {
                vscode.window.showInformationMessage(`Question: ${m.question}`);
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
            if (m.type === 'load-demo-plan') {
                // Load demo plan for testing
                this.steps = [
                    { description: 'Analyze requirements and create project structure', status: 'pending', patch: '// Demo patch 1\n+ Create new component\n- Remove old file' },
                    { description: 'Implement core functionality', status: 'pending', patch: '// Demo patch 2\n+ Add main logic\n+ Update tests' },
                    { description: 'Add error handling and validation', status: 'pending', patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation' }
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
        // Show actual plan content
        const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); margin: 16px; }
    .wrap { max-width: 500px; }
    h2 { color: var(--vscode-foreground); margin-bottom: 16px; }
    .steps { list-style: none; padding: 0; }
    .step { background: var(--vscode-list-hoverBackground); padding: 12px; margin: 8px 0; border-radius: 4px; cursor: pointer; border: 1px solid var(--vscode-contrastBorder); }
    .step.selected { background: var(--vscode-list-activeSelectionBackground); border-color: var(--vscode-focusBorder); }
    .step:hover { background: var(--vscode-list-activeSelectionBackground); }
    .actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
    button { padding: 8px 16px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; cursor: pointer; }
    button:hover { background: var(--vscode-button-hoverBackground); }
    button.approve { background: var(--vscode-testing-iconPassed); }
    button.reject { background: var(--vscode-testing-iconFailed); }
    .patch { margin-top: 16px; padding: 12px; background: var(--vscode-textCodeBlock-background); border-radius: 4px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; border: 1px solid var(--vscode-contrastBorder); }
  </style>
</head>
<body>
<div class="wrap">
  <h2>📋 Execution Plan (${this.steps.length} steps)</h2>
  <ol class="steps">
    ${this.steps.map((step, i) => `
      <li class="step ${i === this.selectedIndex ? 'selected' : ''}" data-index="${i}">
        <strong>Step ${i + 1}:</strong> ${step.description || step.task || 'Untitled step'}
        ${step.status ? `<span style="float: right; color: var(--vscode-descriptionForeground);">${step.status}</span>` : ''}
      </li>
    `).join('')}
  </ol>
  <div class="actions">
    <button class="approve" id="approve">✅ Approve Step</button>
    <button class="reject" id="reject">❌ Reject Step</button>
    ${this.selectedPatch ? '<button id="apply-patch">🔧 Apply Patch</button>' : ''}
  </div>
  ${this.selectedPatch ? `<div class="patch"><strong>Selected Patch:</strong><br><pre>${this.selectedPatch.substring(0, 500)}${this.selectedPatch.length > 500 ? '...' : ''}</pre></div>` : ''}
</div>
<script>
  const vscode = acquireVsCodeApi();
  document.querySelectorAll('.step').forEach((step, index) => {
    step.addEventListener('click', () => {
      vscode.postMessage({ type: 'select', index });
    });
  });
  document.getElementById('approve')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'approve' });
  });
  document.getElementById('reject')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'reject' });
  });
  document.getElementById('apply-patch')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'applyPatch' });
  });
</script>
</body>
</html>`;
        this.view.webview.html = html;
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