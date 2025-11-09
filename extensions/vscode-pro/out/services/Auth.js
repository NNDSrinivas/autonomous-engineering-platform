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
Object.defineProperty(exports, "__esModule", { value: true });
exports.Auth = void 0;
const vscode = __importStar(require("vscode"));
class Auth {
    constructor(ctx) {
        this.ctx = ctx;
        this.tokenKey = 'aep.token';
    }
    async isSignedIn() {
        const token = await this.ctx.secrets.get(this.tokenKey);
        return !!token;
    }
    async signIn() {
        try {
            const cfg = vscode.workspace.getConfiguration('aep');
            const domain = cfg.get('auth.domain') || 'auth.navralabs.com';
            const audience = cfg.get('auth.audience') || 'https://api.navralabs.com';
            // Open the authorization URL in the browser
            const authUrl = `https://${domain}/authorize?audience=${encodeURIComponent(audience)}&device=true&response_type=code&scope=openid%20profile%20email`;
            await vscode.env.openExternal(vscode.Uri.parse(authUrl));
            vscode.window.showInformationMessage('🔐 Complete sign-in in the browser, then paste your access token below.', { modal: false });
            // For now, ask user to paste token directly
            // In a full implementation, you'd implement the device code flow
            const token = await vscode.window.showInputBox({
                prompt: '🔑 Paste your AEP access token (you can get it from the browser after sign-in)',
                password: true,
                ignoreFocusOut: true,
                validateInput: (value) => {
                    if (!value || value.trim().length < 10) {
                        return 'Please enter a valid access token';
                    }
                    return undefined;
                }
            });
            if (token && token.trim()) {
                await this.ctx.secrets.store(this.tokenKey, token.trim());
                vscode.window.showInformationMessage('✅ Successfully signed in to AEP Professional!');
            }
            else {
                vscode.window.showWarningMessage('⚠️ Sign-in cancelled');
            }
        }
        catch (error) {
            vscode.window.showErrorMessage(`❌ Sign-in failed: ${error?.message || String(error)}`);
        }
    }
    async signOut() {
        try {
            await this.ctx.secrets.delete(this.tokenKey);
            vscode.window.showInformationMessage('👋 Successfully signed out from AEP Professional');
        }
        catch (error) {
            vscode.window.showErrorMessage(`❌ Sign-out failed: ${error?.message || String(error)}`);
        }
    }
    async getAccessToken() {
        return this.ctx.secrets.get(this.tokenKey);
    }
    // Method to validate if the stored token is still valid
    async validateToken() {
        const token = await this.getAccessToken();
        if (!token)
            return false;
        try {
            // Try to decode the JWT token to check expiration
            const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64').toString());
            const currentTime = Math.floor(Date.now() / 1000);
            if (payload.exp && payload.exp < currentTime) {
                // Token expired, remove it
                await this.ctx.secrets.delete(this.tokenKey);
                return false;
            }
            return true;
        }
        catch {
            // Invalid token format, remove it
            await this.ctx.secrets.delete(this.tokenKey);
            return false;
        }
    }
}
exports.Auth = Auth;
//# sourceMappingURL=Auth.js.map