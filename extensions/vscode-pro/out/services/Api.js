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
exports.Api = void 0;
const vscode = __importStar(require("vscode"));
class Api {
    getBaseUrl() {
        const cfg = vscode.workspace.getConfiguration('aep');
        return cfg.get('api.baseUrl') || 'https://api.navralabs.com';
    }
    async chat(prompt, model, token) {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                },
                body: JSON.stringify({
                    prompt,
                    model,
                    stream: false,
                    max_tokens: 4000,
                    temperature: 0.7
                })
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API ${response.status}: ${errorText}`);
            }
            const data = await response.json();
            return { text: data.response || data.text || data.content || 'No response from API' };
        }
        catch (error) {
            console.error('AEP API Error:', error);
            throw new Error(`API call failed: ${error?.message || String(error)}`);
        }
    }
    async getModels(token) {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/models`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                }
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API ${response.status}: ${errorText}`);
            }
            const data = await response.json();
            return data.models || data.available_models || [];
        }
        catch (error) {
            console.error('AEP Models API Error:', error);
            // Fallback to configured models
            const cfg = vscode.workspace.getConfiguration('aep');
            return cfg.get('model.allowed') || ['gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet'];
        }
    }
    async validateConnection(token) {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/health`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                }
            });
            return response.ok;
        }
        catch (error) {
            console.error('AEP Connection validation failed:', error);
            return false;
        }
    }
    // Method for testing if API is reachable without auth
    async ping() {
        try {
            const baseUrl = this.getBaseUrl();
            const response = await fetch(`${baseUrl}/ping`, {
                method: 'GET',
                headers: {
                    'User-Agent': 'AEP-VSCode-Extension/2.0.0'
                }
            });
            return response.ok;
        }
        catch (error) {
            console.error('AEP Ping failed:', error);
            return false;
        }
    }
}
exports.Api = Api;
//# sourceMappingURL=Api.js.map