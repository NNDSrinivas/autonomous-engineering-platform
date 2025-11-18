"use strict";
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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthService = void 0;
const vscode = __importStar(require("vscode"));
const axios_1 = __importDefault(require("axios"));
class AuthService {
    constructor(context) {
        this.context = context;
        this._onAuthStateChanged = new vscode.EventEmitter();
        this.onAuthStateChanged = this._onAuthStateChanged.event;
        this._authState = { isAuthenticated: false };
        this._config = vscode.workspace.getConfiguration('aep');
        this._apiUrl = this._config.get('apiUrl', 'http://localhost:8001');
        this.loadAuthState();
    }
    async isAuthenticated() {
        // Validate current token if exists
        if (this._authState.accessToken) {
            try {
                await this.validateToken();
                return true;
            }
            catch {
                await this.clearAuthState();
                return false;
            }
        }
        return false;
    }
    async signIn() {
        try {
            // Start device flow
            const deviceCode = await this.startDeviceFlow();
            // Show user the verification URL and code
            await this.showDeviceCodePrompt(deviceCode);
            // Poll for token
            const tokens = await this.pollForToken(deviceCode);
            // Get user info
            const user = await this.getUserInfo(tokens.access_token);
            // Save auth state
            this._authState = {
                isAuthenticated: true,
                accessToken: tokens.access_token,
                refreshToken: tokens.refresh_token,
                user
            };
            await this.saveAuthState();
            this._onAuthStateChanged.fire(true);
        }
        catch (error) {
            console.error('Sign in failed:', error);
            throw error;
        }
    }
    async signOut() {
        await this.clearAuthState();
        this._onAuthStateChanged.fire(false);
    }
    getAccessToken() {
        return this._authState.accessToken;
    }
    getUser() {
        return this._authState.user;
    }
    async startDeviceFlow() {
        const response = await axios_1.default.post(`${this._apiUrl}/oauth/device/start`, {}, {
            headers: { 'Content-Type': 'application/json' }
        });
        return response.data;
    }
    async showDeviceCodePrompt(deviceCode) {
        const action = await vscode.window.showInformationMessage(`🔐 Sign in to AEP: Enter code ${deviceCode.user_code}`, { modal: true }, 'Open Browser', 'Copy Code', 'Cancel');
        if (action === 'Open Browser') {
            vscode.env.openExternal(vscode.Uri.parse(deviceCode.verification_uri_complete));
        }
        else if (action === 'Copy Code') {
            vscode.env.clipboard.writeText(deviceCode.user_code);
            vscode.env.openExternal(vscode.Uri.parse(deviceCode.verification_uri));
        }
        else {
            throw new Error('Authentication cancelled by user');
        }
    }
    async pollForToken(deviceCode) {
        const maxAttempts = Math.floor(deviceCode.expires_in / deviceCode.interval);
        let attempts = 0;
        return new Promise((resolve, reject) => {
            const interval = setInterval(async () => {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(interval);
                    reject(new Error('Authentication timeout'));
                    return;
                }
                try {
                    const response = await axios_1.default.post(`${this._apiUrl}/oauth/device/poll`, {
                        device_code: deviceCode.device_code
                    });
                    if (response.status === 200) {
                        clearInterval(interval);
                        resolve(response.data);
                    }
                }
                catch (error) {
                    if (error.response?.status === 428) {
                        // Still waiting for user authorization
                        return;
                    }
                    else {
                        clearInterval(interval);
                        reject(error);
                    }
                }
            }, deviceCode.interval * 1000);
        });
    }
    async getUserInfo(accessToken) {
        const response = await axios_1.default.get(`${this._apiUrl}/api/me`, {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        return response.data;
    }
    async validateToken() {
        if (!this._authState.accessToken) {
            throw new Error('No access token');
        }
        await axios_1.default.get(`${this._apiUrl}/api/me`, {
            headers: { Authorization: `Bearer ${this._authState.accessToken}` }
        });
    }
    async loadAuthState() {
        try {
            const stored = this.context.globalState.get('aep.auth');
            if (stored) {
                this._authState = stored;
            }
        }
        catch (error) {
            console.error('Failed to load auth state:', error);
        }
    }
    async saveAuthState() {
        await this.context.globalState.update('aep.auth', this._authState);
    }
    async clearAuthState() {
        this._authState = { isAuthenticated: false };
        await this.context.globalState.update('aep.auth', undefined);
    }
}
exports.AuthService = AuthService;
//# sourceMappingURL=AuthService.js.map