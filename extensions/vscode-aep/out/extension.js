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
        console.log('🔧 Registering webview providers...');
        console.log('🎯 About to register:', {
            chatProviderInstance: !!chat,
            planProviderInstance: !!plan,
            vscodeWindow: !!vscode.window
        });
        const chatProvider = vscode.window.registerWebviewViewProvider('aep.chatView', chat);
        const planProvider = vscode.window.registerWebviewViewProvider('aep.planView', plan);
        console.log('📋 Registered providers:', {
            chatView: 'aep.chatView',
            planView: 'aep.planView',
            chatDisposable: !!chatProvider,
            planDisposable: !!planProvider
        });
        context.subscriptions.push(chatProvider, planProvider, vscode.commands.registerCommand('aep.signIn', async () => {
            await (0, deviceCode_1.ensureAuth)(context, client);
            vscode.window.showInformationMessage('AEP: Signed in');
            chat.refresh();
            plan.refresh();
        }), vscode.commands.registerCommand('aep.startSession', async () => {
            await (0, deviceCode_1.ensureAuth)(context, client);
            await chat.sendHello();
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
    <h3>🚀 AEP Agent - Connection Test</h3>
    <p>This is a test to verify the webview is working properly.</p>
    <button onclick="testMessage()">Test Message</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    function testMessage() {
      vscode.postMessage({ type: 'test', message: 'Hello from webview!' });
    }
  </script>
</body>
</html>`;
            console.log('✅ ChatSidebarProvider webview HTML set successfully');
            // Then call the full render
            setTimeout(() => {
                this.render();
            }, 1000);
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
  <title>AEP Agent</title>
  <style>
    :root {
      --vscode-button-primary-background: #0e639c;
      --vscode-button-primary-foreground: #ffffff;
      --vscode-button-primary-hoverBackground: #1177bb;
      --border-radius: 6px;
      --spacing-xs: 4px;
      --spacing-sm: 8px;
      --spacing-md: 12px;
      --spacing-lg: 16px;
      --spacing-xl: 24px;
    }
    
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      line-height: 1.4;
      font-size: 13px;
    }
    
    .container {
      padding: var(--spacing-lg);
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    
    .header {
      margin-bottom: var(--spacing-xl);
    }
    
    .welcome-section {
      background: var(--vscode-textBlockQuote-background);
      border-left: 3px solid var(--vscode-focusBorder);
      padding: var(--spacing-lg);
      border-radius: var(--border-radius);
      margin-bottom: var(--spacing-xl);
    }
    
    .welcome-title {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: var(--spacing-sm);
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #22c55e;
      animation: pulse 2s infinite;
    }
    
    .welcome-subtitle {
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
      margin-bottom: var(--spacing-md);
    }
    
    .quick-actions {
      display: flex;
      gap: var(--spacing-sm);
      flex-wrap: wrap;
    }
    
    .btn {
      padding: var(--spacing-sm) var(--spacing-md);
      border: none;
      border-radius: var(--border-radius);
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
    }
    
    .btn-primary {
      background: var(--vscode-button-primary-background);
      color: var(--vscode-button-primary-foreground);
    }
    
    .btn-primary:hover {
      background: var(--vscode-button-primary-hoverBackground);
    }
    
    .btn-secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border: 1px solid var(--vscode-contrastBorder);
    }
    
    .btn-secondary:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    
    .section {
      margin-bottom: var(--spacing-xl);
    }
    
    .section-title {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: var(--spacing-md);
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }
    
    .issues-container {
      flex: 1;
      overflow-y: auto;
    }
    
    .issues-list {
      list-style: none;
      gap: var(--spacing-sm);
      display: flex;
      flex-direction: column;
    }
    
    .issue-item {
      background: var(--vscode-list-hoverBackground);
      border: 1px solid var(--vscode-contrastBorder);
      border-radius: var(--border-radius);
      padding: var(--spacing-md);
      cursor: pointer;
      transition: all 0.2s ease;
      position: relative;
    }
    
    .issue-item:hover {
      background: var(--vscode-list-activeSelectionBackground);
      border-color: var(--vscode-focusBorder);
      transform: translateY(-1px);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .issue-header {
      display: flex;
      justify-content: between;
      align-items: flex-start;
      gap: var(--spacing-sm);
      margin-bottom: var(--spacing-xs);
    }
    
    .issue-key {
      background: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    
    .issue-status {
      background: var(--vscode-statusBar-background);
      color: var(--vscode-statusBar-foreground);
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      margin-left: auto;
    }
    
    .issue-title {
      font-weight: 500;
      font-size: 13px;
      line-height: 1.3;
      margin-bottom: var(--spacing-xs);
    }
    
    .issue-meta {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
    }
    
    .chat-input-section {
      margin-top: auto;
      padding-top: var(--spacing-lg);
      border-top: 1px solid var(--vscode-contrastBorder);
    }
    
    .input-container {
      display: flex;
      gap: var(--spacing-sm);
      align-items: flex-end;
    }
    
    .chat-input {
      flex: 1;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      border-radius: var(--border-radius);
      padding: var(--spacing-md);
      font-family: inherit;
      font-size: 13px;
      resize: vertical;
      min-height: 40px;
      max-height: 120px;
    }
    
    .chat-input:focus {
      outline: none;
      border-color: var(--vscode-focusBorder);
      box-shadow: 0 0 0 1px var(--vscode-focusBorder);
    }
    
    .chat-input::placeholder {
      color: var(--vscode-input-placeholderForeground);
    }
    
    .send-btn {
      background: var(--vscode-button-primary-background);
      color: var(--vscode-button-primary-foreground);
      border: none;
      border-radius: var(--border-radius);
      padding: var(--spacing-md);
      cursor: pointer;
      transition: all 0.2s ease;
      min-width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .send-btn:hover:not(:disabled) {
      background: var(--vscode-button-primary-hoverBackground);
    }
    
    .send-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    
    .empty-state {
      text-align: center;
      padding: var(--spacing-xl);
      color: var(--vscode-descriptionForeground);
    }
    
    .empty-state-icon {
      font-size: 32px;
      margin-bottom: var(--spacing-md);
      opacity: 0.5;
    }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    
    .tooltip {
      position: relative;
    }
    
    .tooltip:hover::after {
      content: attr(data-tooltip);
      position: absolute;
      bottom: 100%;
      left: 50%;
      transform: translateX(-50%);
      background: var(--vscode-editorHoverWidget-background);
      color: var(--vscode-editorHoverWidget-foreground);
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      white-space: nowrap;
      z-index: 1000;
      border: 1px solid var(--vscode-contrastBorder);
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="welcome-section">
        <div class="welcome-title">
          <span class="status-indicator"></span>
          ${now}! Welcome to AEP Agent
        </div>
        <div class="welcome-subtitle">
          Your AI-powered development assistant is ready to help
        </div>
        <div class="quick-actions">
          <button class="btn btn-primary" onclick="signIn()">
            🔑 Sign In
          </button>
          <button class="btn btn-secondary" onclick="startSession()">
            🚀 Start Session
          </button>
        </div>
      </div>
    </div>
    
    <div class="section">
      <div class="section-title">
        📋 Available Issues (${issues.length})
      </div>
      <div class="issues-container">
        ${issues.length > 0 ? `
          <ul class="issues-list">
            ${issues.map(issue => `
              <li class="issue-item" data-key="${issue.key}" onclick="selectIssue('${issue.key}')">
                <div class="issue-header">
                  <span class="issue-key">${issue.key}</span>
                  <span class="issue-status">${issue.status}</span>
                </div>
                <div class="issue-title">${issue.summary}</div>
                <div class="issue-meta">
                  <span>🔗 ID: ${issue.id}</span>
                  <span>📋 Status: ${issue.status}</span>
                </div>
              </li>
            `).join('')}
          </ul>
        ` : `
          <div class="empty-state">
            <div class="empty-state-icon">📝</div>
            <div>No issues found. Sign in to load your JIRA issues.</div>
          </div>
        `}
      </div>
    </div>
    
    <div class="chat-input-section">
      <div class="input-container">
        <textarea 
          class="chat-input" 
          id="chatInput"
          placeholder="Ask the agent about your project, request code analysis, or get help with implementation..."
          rows="2"
        ></textarea>
        <button class="send-btn tooltip" data-tooltip="Send message" onclick="sendMessage()" id="sendBtn">
          ➤
        </button>
      </div>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    
    function signIn() {
      vscode.postMessage({ type: 'signin' });
    }
    
    function startSession() {
      vscode.postMessage({ type: 'start-session' });
    }
    
    function selectIssue(key) {
      vscode.postMessage({ type: 'selectIssue', key });
      
      // Visual feedback
      document.querySelectorAll('.issue-item').forEach(item => {
        item.style.background = 'var(--vscode-list-hoverBackground)';
      });
      event.target.closest('.issue-item').style.background = 'var(--vscode-list-activeSelectionBackground)';
    }
    
    function sendMessage() {
      const input = document.getElementById('chatInput');
      const message = input.value.trim();
      
      if (message) {
        vscode.postMessage({ type: 'ask', question: message });
        input.value = '';
        input.style.height = '40px'; // Reset height
        updateSendButton();
      }
    }
    
    function updateSendButton() {
      const input = document.getElementById('chatInput');
      const sendBtn = document.getElementById('sendBtn');
      sendBtn.disabled = !input.value.trim();
    }
    
    // Auto-resize textarea
    document.getElementById('chatInput').addEventListener('input', function() {
      this.style.height = '40px';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
      updateSendButton();
    });
    
    // Enter to send (Shift+Enter for new line)
    document.getElementById('chatInput').addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    
    // Initialize
    updateSendButton();
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
            console.log('📨 ChatSidebar received message:', m);
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
            if (m.type === 'test') {
                vscode.window.showInformationMessage(`✅ Webview test successful: ${m.message}`);
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