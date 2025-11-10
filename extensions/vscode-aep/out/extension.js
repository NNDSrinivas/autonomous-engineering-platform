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
const TOKEN_SECRET = 'aep.token';
class AEPClient {
    constructor(ctx, baseUrl, orgId) {
        this.ctx = ctx;
        this.baseUrl = baseUrl;
        this.orgId = orgId;
    }
    async hydrateToken(output) {
        const existing = await this.ctx.secrets.get(TOKEN_SECRET);
        if (!existing) {
            return;
        }
        const sanitized = this.sanitizeToken(existing);
        if (!sanitized) {
            await this.ctx.secrets.delete(TOKEN_SECRET);
            output?.appendLine('Removed invalid AEP session token from secret storage.');
            return;
        }
        this.token = sanitized;
        output?.appendLine('Restored existing AEP session token.');
    }
    async persistToken(token) {
        const sanitized = this.sanitizeToken(token);
        this.token = sanitized;
        if (sanitized) {
            await this.ctx.secrets.store(TOKEN_SECRET, sanitized);
        }
        else {
            await this.ctx.secrets.delete(TOKEN_SECRET);
        }
    }
    sanitizeToken(token) {
        if (typeof token !== 'string') {
            return undefined;
        }
        const trimmed = token.trim();
        if (trimmed.length === 0 || trimmed === 'undefined') {
            return undefined;
        }
        return trimmed;
    }
    hasToken() {
        return Boolean(this.token);
    }
    async clearToken() {
        await this.persistToken(undefined);
    }
    headers() {
        const headers = {
            'Content-Type': 'application/json',
            'X-Org-Id': this.orgId
        };
        if (this.token) {
            headers.Authorization = `Bearer ${this.token}`;
        }
        return headers;
    }
    async startDeviceCode() {
        const response = await fetch(`${this.baseUrl}/oauth/device/start`, {
            method: 'POST',
            headers: this.headers()
        });
        if (!response.ok) {
            throw new Error(await response.text());
        }
        return (await response.json());
    }
    async pollDeviceCode(deviceCode) {
        const response = await fetch(`${this.baseUrl}/oauth/device/poll`, {
            method: 'POST',
            headers: this.headers(),
            body: JSON.stringify({ device_code: deviceCode })
        });
        if (!response.ok) {
            throw new Error(await response.text());
        }
        const token = (await response.json());
        if (!token.access_token) {
            throw new Error('Device authorization succeeded but did not return an access token.');
        }
        await this.persistToken(token.access_token);
        return token;
    }
    async listMyJiraIssues() {
        const response = await fetch(`${this.baseUrl}/api/integrations/jira/my-issues`, {
            headers: this.headers()
        });
        if (!response.ok) {
            return [];
        }
        return (await response.json());
    }
    async me() {
        const response = await fetch(`${this.baseUrl}/api/me`, { headers: this.headers() });
        if (!response.ok) {
            return {};
        }
        return (await response.json());
    }
    async proposePlan(issueKey) {
        const response = await fetch(`${this.baseUrl}/api/agent/propose`, {
            method: 'POST',
            headers: this.headers(),
            body: JSON.stringify({ issue_key: issueKey })
        });
        if (!response.ok) {
            throw new Error(await response.text());
        }
        return (await response.json());
    }
    async applyPatch(patch) {
        const response = await fetch(`${this.baseUrl}/api/ai/apply-patch`, {
            method: 'POST',
            headers: this.headers(),
            body: JSON.stringify({ diff: patch, dry_run: false })
        });
        const payload = (await response.json());
        if (!response.ok) {
            throw new Error(payload.detail || JSON.stringify(payload));
        }
        return payload;
    }
    async chat(message, type = 'question') {
        const response = await fetch(`${this.baseUrl}/api/chat`, {
            method: 'POST',
            headers: this.headers(),
            body: JSON.stringify({ message, type })
        });
        if (!response.ok) {
            throw new Error(await response.text());
        }
        return (await response.json());
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
    const config = vscode.workspace.getConfiguration('aep');
    return {
        baseUrl: normalize(config.get('baseUrl'), 'http://localhost:8000'),
        orgId: normalize(config.get('orgId'), 'org-dev'),
        llm: normalize(config.get('llm'), 'gpt-4o-mini'),
        portalUrl: normalize(config.get('portalUrl'), 'https://portal.aep.navra.ai')
    };
}
function normalize(value, fallback) {
    if (typeof value !== 'string' || value.trim().length === 0 || value === 'undefined') {
        return fallback;
    }
    return value.trim();
}


/***/ }),

/***/ "./src/deviceFlow.ts":
/*!***************************!*\
  !*** ./src/deviceFlow.ts ***!
  \***************************/
/***/ ((__unused_webpack_module, exports) => {


Object.defineProperty(exports, "__esModule", ({ value: true }));
exports.DEVICE_POLL_INTERVAL_MS = exports.DEVICE_POLL_MAX_ATTEMPTS = void 0;
exports.pollDeviceCode = pollDeviceCode;
exports.DEVICE_POLL_MAX_ATTEMPTS = 90;
exports.DEVICE_POLL_INTERVAL_MS = 2000;
async function pollDeviceCode(client, deviceCode, output) {
    // 90 attempts × 2 seconds interval = 180 seconds (3 minutes) total timeout for device authorization.
    let lastError;
    for (let attempt = 0; attempt < exports.DEVICE_POLL_MAX_ATTEMPTS; attempt++) {
        try {
            const token = await client.pollDeviceCode(deviceCode);
            output?.appendLine('Received access token from device flow.');
            return token;
        }
        catch (error) {
            const message = typeof error?.message === 'string' ? error.message : String(error);
            if (isPendingDeviceAuthorization(message)) {
                await delay(exports.DEVICE_POLL_INTERVAL_MS);
                continue;
            }
            lastError = error;
            break;
        }
    }
    if (lastError) {
        throw lastError;
    }
    throw new Error('Timed out waiting for device authorization.');
}
function isPendingDeviceAuthorization(message) {
    const normalized = message.toLowerCase();
    return normalized.includes('428') || normalized.includes('authorization_pending');
}
async function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
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
const deviceFlow_1 = __webpack_require__(/*! ./deviceFlow */ "./src/deviceFlow.ts");
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
        await client.hydrateToken(output);
        const approvals = new approvals_1.Approvals(context, client, output);
        const chat = new chatSidebar_1.ChatSidebarProvider(context, client, output);
        const plan = new planPanel_1.PlanPanelProvider(context, client, approvals, output);
        const auth = new authPanel_1.AuthPanel(context, client, cfg.portalUrl, output);
        const disposables = [
            vscode.window.registerWebviewViewProvider('aep.chatView', chat, {
                webviewOptions: { retainContextWhenHidden: true }
            }),
            vscode.window.registerWebviewViewProvider('aep.planView', plan, {
                webviewOptions: { retainContextWhenHidden: true }
            }),
            vscode.window.registerWebviewViewProvider('aep.authView', auth, {
                webviewOptions: { retainContextWhenHidden: true }
            }),
            vscode.commands.registerCommand('aep.signIn', () => startDeviceFlow(client, chat, output)),
            vscode.commands.registerCommand('aep.startSession', () => {
                vscode.window.showInformationMessage('Starting an AEP planning session…');
            }),
            vscode.commands.registerCommand('aep.openPortal', () => {
                if (cfg.portalUrl) {
                    vscode.env.openExternal(vscode.Uri.parse(cfg.portalUrl));
                }
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
        vscode.window
            .showInformationMessage(`Open the browser to complete sign-in${codeLabel}`, 'Open Browser')
            .then(selection => {
            if (selection === 'Open Browser' && verificationUrl) {
                vscode.env.openExternal(vscode.Uri.parse(verificationUrl));
            }
        });
        if (!flow.device_code) {
            throw new Error('Device authorization response was missing a device code.');
        }
        await (0, deviceFlow_1.pollDeviceCode)(client, flow.device_code, output);
        vscode.window.showInformationMessage('Signed in to AEP successfully.');
        chat.refresh();
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        output.appendLine(`Sign-in failed: ${message}`);
        await client.clearToken();
        vscode.window.showErrorMessage(`AEP sign-in failed: ${message}`);
    }
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
    constructor(_ctx, _client, output) {
        this._ctx = _ctx;
        this._client = _client;
        this.output = output;
        this.selected = null;
    }
    set(step) {
        this.selected = step;
    }
    async approve(step) {
        this.selected = step;
        await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: `Approving “${step.title}”…` }, async (progress) => {
            progress.report({ increment: 33, message: 'Syncing with AEP…' });
            await vscode.env.clipboard.writeText(step.patch ?? step.details ?? step.description ?? step.title);
            this.output.appendLine(`Approved step ${step.id ?? step.title}`);
            progress.report({ increment: 66, message: 'Ready for execution' });
        });
        vscode.window.showInformationMessage('Step approved and copied to clipboard for quick application.');
    }
    async reject(step) {
        this.selected = step;
        const detail = step.details || step.description || step.title;
        this.output.appendLine(`Rejected step ${step.id ?? step.title}: ${detail}`);
        vscode.window.showWarningMessage(`Rejected plan step: ${step.title}`);
    }
    async approveSelected() {
        if (this.selected) {
            await this.approve(this.selected);
        }
        else {
            vscode.window.showInformationMessage('Select a plan step to approve.');
        }
    }
    async rejectSelected() {
        if (this.selected) {
            await this.reject(this.selected);
        }
        else {
            vscode.window.showInformationMessage('Select a plan step to reject.');
        }
    }
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
const deviceFlow_1 = __webpack_require__(/*! ../deviceFlow */ "./src/deviceFlow.ts");
class AuthPanel {
    constructor(ctx, client, portalUrl, output) {
        this.ctx = ctx;
        this.client = client;
        this.portalUrl = portalUrl;
        this.output = output;
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
        view.webview.onDidReceiveMessage(async (message) => {
            try {
                if (message.type === 'open') {
                    const targetUrl = message.url === 'portal:' ? this.portalUrl : message.url;
                    if (targetUrl) {
                        vscode.env.openExternal(vscode.Uri.parse(targetUrl));
                    }
                    return;
                }
                if (message.type === 'signin') {
                    await this.handleSignIn(view);
                    return;
                }
            }
            catch (error) {
                const messageText = error?.message ?? String(error);
                await this.client.clearToken();
                this.output.appendLine(`Authentication failed: ${messageText}`);
                vscode.window.showErrorMessage(`Authentication failed: ${messageText}`);
                view.webview.postMessage({ type: 'error', message: messageText });
            }
        });
    }
    async handleSignIn(view) {
        this.output.appendLine('Starting authentication from Account panel.');
        const flow = await this.client.startDeviceCode();
        if (!flow.device_code) {
            throw new Error('Device authorization response was missing a device code.');
        }
        view.webview.postMessage({ type: 'flow', flow });
        const verificationUrl = flow.verification_uri_complete || flow.verification_uri;
        if (verificationUrl) {
            vscode.env.openExternal(vscode.Uri.parse(verificationUrl));
        }
        await (0, deviceFlow_1.pollDeviceCode)(this.client, flow.device_code, this.output);
        view.webview.postMessage({ type: 'done' });
        vscode.window.showInformationMessage('Signed in to AEP successfully.');
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
    constructor(ctx, client, output) {
        this.ctx = ctx;
        this.client = client;
        this.output = output;
    }
    resolveWebviewView(view) {
        this.view = view;
        view.webview.options = { enableScripts: true };
        this.render();
        view.webview.onDidReceiveMessage(async (message) => {
            try {
                switch (message.type) {
                    case 'openExternal':
                        if (message.url) {
                            vscode.env.openExternal(vscode.Uri.parse(message.url));
                        }
                        break;
                    case 'openPortal':
                        await vscode.commands.executeCommand('aep.openPortal');
                        break;
                    case 'pickIssue':
                    case 'startSession':
                        await vscode.commands.executeCommand('aep.startSession');
                        break;
                    case 'signIn':
                        await vscode.commands.executeCommand('aep.signIn');
                        setTimeout(() => this.render(), 2000);
                        break;
                    case 'refresh':
                        await this.render();
                        break;
                    case 'chat':
                        if (message.message) {
                            await this.handleChatMessage(message.message);
                        }
                        break;
                    default:
                        this.output.appendLine(`Unknown chat message type: ${message.type}`);
                }
            }
            catch (error) {
                const text = error instanceof Error ? error.message : String(error);
                this.output.appendLine(`ChatSidebar message handling failed: ${text}`);
                vscode.window.showErrorMessage(`AEP Agent chat error: ${text}`);
            }
        });
    }
    refresh() {
        if (this.view) {
            this.render();
        }
    }
    async render() {
        if (!this.view) {
            return;
        }
        try {
            const [me, issues] = await Promise.all([
                this.client.me().catch(() => ({})),
                this.client.listMyJiraIssues().catch(() => [])
            ]);
            const greeting = this.resolveGreeting();
            const body = me?.email ? this.signedInView(greeting, me.email, issues) : this.signedOutView();
            this.view.webview.html = (0, view_1.boilerplate)(this.view.webview, this.ctx, body, ['base.css', 'landing.css'], ['chat.js']);
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.output.appendLine(`ChatSidebar render failed: ${message}`);
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
    resolveGreeting() {
        const hour = new Date().getHours();
        if (hour < 12) {
            return 'Good morning';
        }
        if (hour < 18) {
            return 'Good afternoon';
        }
        return 'Good evening';
    }
    signedInView(greeting, email, issues) {
        const issueCards = issues.length
            ? issues.map(issue => this.renderIssue(issue)).join('')
            : `<div class="empty">No issues found. Check your Jira integration.</div>`;
        return `
      <div class="card">
        <div class="row"><span class="h">${greeting}, welcome to AEP Agent</span></div>
        <div class="row mono">Signed in as ${this.escape(email)}</div>
        <div class="row" style="gap:8px;margin-top:8px;">
          <vscode-button id="start" appearance="primary">Start Session</vscode-button>
          <vscode-button id="refresh" appearance="secondary">Refresh</vscode-button>
        </div>
      </div>
      ${issueCards}`;
    }
    signedOutView() {
        return `
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
    }
    renderIssue(issue) {
        return `
      <div class="card">
        <div class="row"><b>${this.escape(issue.key)}</b> — ${this.escape(issue.summary)} <span class="chip">${this.escape(issue.status)}</span></div>
        <div class="row">
          <vscode-button appearance="secondary" data-url="${issue.url ?? ''}" class="open">Open in Jira</vscode-button>
          <vscode-button class="plan">Plan</vscode-button>
        </div>
      </div>`;
    }
    escape(text) {
        return String(text ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
    async handleChatMessage(message) {
        if (!this.view) {
            return;
        }
        try {
            this.showChatMessage('user', message);
            this.showChatMessage('system', '🤔 Thinking...');
            const response = await this.client.chat(message);
            const answer = response.response || response.message || 'I received your message but had trouble generating a response.';
            this.showChatMessage('assistant', answer);
        }
        catch (error) {
            const text = error instanceof Error ? error.message : String(error);
            this.output.appendLine(`Chat error: ${text}`);
            this.showChatMessage('assistant', 'I encountered an error processing your message. Please check your connection and try again.');
        }
    }
    showChatMessage(role, content) {
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
    constructor(ctx, client, approvals, output) {
        this.ctx = ctx;
        this.client = client;
        this.approvals = approvals;
        this.output = output;
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
                switch (message.type) {
                    case 'load-plan':
                        if (message.issue) {
                            await this.loadPlan(message.issue);
                        }
                        break;
                    case 'load-demo-plan':
                        this.loadDemoPlan();
                        break;
                    case 'select':
                        if (typeof message.index === 'number') {
                            this.selectStep(message.index);
                        }
                        break;
                    case 'approve':
                        await this.approveSelected();
                        break;
                    case 'reject':
                        await this.rejectSelected();
                        break;
                    case 'applyPatch':
                        await vscode.commands.executeCommand('aep.applyPatch');
                        break;
                    default:
                        this.output.appendLine(`Unknown plan message type: ${message.type}`);
                }
            }
            catch (error) {
                this.showError(error);
            }
        });
    }
    refresh() {
        if (this.view) {
            this.render();
        }
    }
    async applySelectedPatch() {
        if (!this.selectedPatch) {
            vscode.window.showWarningMessage('No patch selected');
            return;
        }
        try {
            const result = await this.client.applyPatch(this.selectedPatch);
            vscode.window.showInformationMessage(result.applied ? 'Patch applied' : 'Patch failed');
        }
        catch (error) {
            this.output.appendLine(`Unable to apply patch: ${error?.message ?? error}`);
            vscode.window.showErrorMessage(`Unable to apply patch: ${error?.message ?? error}`);
        }
    }
    async loadPlan(issueKey) {
        this.output.appendLine(`Loading plan for ${issueKey}`);
        const steps = await this.client.proposePlan(issueKey);
        this.steps = steps;
        this.selectStep(0);
    }
    loadDemoPlan() {
        this.steps = this.demoPlan();
        this.selectStep(0);
        vscode.window.showInformationMessage('Demo plan loaded! 🚀');
    }
    selectStep(index) {
        this.selectedIndex = Math.max(0, Math.min(index, this.steps.length - 1));
        const step = this.steps[this.selectedIndex];
        this.selectedPatch = step?.patch || null;
        this.approvals.set(step ?? null);
        this.render();
    }
    async approveSelected() {
        const step = this.steps[this.selectedIndex];
        if (step) {
            await this.approvals.approve(step);
        }
    }
    async rejectSelected() {
        const step = this.steps[this.selectedIndex];
        if (step) {
            await this.approvals.reject(step);
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
              ${this.steps
                .map((step, index) => this.renderStep(step, index === this.selectedIndex, index))
                .join('')}
            </ul>
          </div>
          <div class="details">
            ${this.selectedPatch
                ? `<pre>${this.escape(this.selectedPatch)}</pre>`
                : '<em>Select a step to inspect details</em>'}
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
    renderStep(step, isSelected, index) {
        const classes = isSelected ? 'sel' : '';
        const subtitle = step.details || step.description || '';
        const subtitleHtml = subtitle ? ` <span class="hint">${this.escape(subtitle)}</span>` : '';
        return `<li class="${classes}" data-i="${index}">${this.escape(step.kind)}: ${this.escape(step.title)}${subtitleHtml}</li>`;
    }
    escape(text) {
        return String(text ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
    demoPlan() {
        return [
            {
                id: 'demo-1',
                kind: 'Setup',
                title: 'Analyze requirements and create project structure',
                description: 'Analyze requirements and create project structure',
                status: 'pending',
                patch: '// Demo patch 1\n+ Create new component\n- Remove old file'
            },
            {
                id: 'demo-2',
                kind: 'Implement',
                title: 'Implement core functionality',
                description: 'Implement core functionality',
                status: 'pending',
                patch: '// Demo patch 2\n+ Add main logic\n+ Update tests'
            },
            {
                id: 'demo-3',
                kind: 'Validate',
                title: 'Add error handling and validation',
                description: 'Add error handling and validation',
                status: 'pending',
                patch: '// Demo patch 3\n+ Try-catch blocks\n+ Input validation'
            }
        ];
    }
    showError(error) {
        if (!this.view) {
            return;
        }
        const message = error instanceof Error ? error.message : String(error);
        this.output.appendLine(`Plan panel error: ${message}`);
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