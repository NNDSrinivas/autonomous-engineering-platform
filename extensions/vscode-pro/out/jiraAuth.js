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
exports.JiraOAuth = void 0;
const vscode = __importStar(require("vscode"));
const oauth_1 = require("./oauth");
// Atlassian Cloud OAuth 2.0 (3LO + PKCE)
const AUTHZ = 'https://auth.atlassian.com/authorize';
const TOKEN = 'https://auth.atlassian.com/oauth/token';
const AUDIENCE = 'api.atlassian.com';
// Minimal scopes for read-only feed; add as needed
const SCOPES = [
    'read:jira-user',
    'read:jira-work'
].join(' ');
class JiraOAuth {
    constructor(ctx) {
        this.ctx = ctx;
        this.secrets = ctx.secrets;
    }
    async getAccessToken() {
        const raw = await this.secrets.get(JiraOAuth.KEY);
        if (!raw)
            return;
        const token = JSON.parse(raw);
        if (Date.now() < token.expires_at - 60000)
            return token.access_token;
        if (token.refresh_token) {
            return this.refresh(token.refresh_token);
        }
        return undefined;
    }
    async signOut() {
        await this.secrets.delete(JiraOAuth.KEY);
    }
    async connected() {
        const token = await this.getAccessToken();
        return !!token;
    }
    async start() {
        const cfg = vscode.workspace.getConfiguration('aep');
        const clientId = cfg.get('jira.clientId');
        if (!clientId) {
            vscode.window.showErrorMessage('Set "AEP: Jira Client ID" in Settings first.');
            return;
        }
        const { verifier, challenge } = await (0, oauth_1.pkcePair)();
        const state = (0, oauth_1.cryptoRandom)();
        const redirect = await (0, oauth_1.authCallbackUri)(this.ctx, { provider: 'jira', state });
        const authUrl = new URL(AUTHZ);
        authUrl.searchParams.set('audience', AUDIENCE);
        authUrl.searchParams.set('client_id', clientId);
        authUrl.searchParams.set('scope', SCOPES);
        authUrl.searchParams.set('redirect_uri', redirect.toString());
        authUrl.searchParams.set('state', state);
        authUrl.searchParams.set('response_type', 'code');
        authUrl.searchParams.set('prompt', 'consent');
        authUrl.searchParams.set('code_challenge', challenge);
        authUrl.searchParams.set('code_challenge_method', 'S256');
        // Save PKCE + state
        await this.ctx.globalState.update('aep.jira.pkce', {
            verifier,
            state,
            redirect: redirect.toString(),
            clientId
        });
        await vscode.env.openExternal(vscode.Uri.parse(authUrl.toString()));
    }
    async finish(code, returnedState) {
        const pkce = this.ctx.globalState.get('aep.jira.pkce');
        if (!pkce || pkce.state !== returnedState) {
            throw new Error('State mismatch');
        }
        const body = {
            grant_type: 'authorization_code',
            client_id: pkce.clientId,
            code,
            redirect_uri: pkce.redirect,
            code_verifier: pkce.verifier
        };
        const resp = await fetch(TOKEN, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!resp.ok) {
            const errorText = await resp.text();
            throw new Error(`Jira token error ${resp.status}: ${errorText}`);
        }
        const tok = await resp.json();
        const expires_at = Date.now() + (tok.expires_in * 1000);
        await this.secrets.store(JiraOAuth.KEY, JSON.stringify({
            ...tok,
            expires_at
        }));
        await this.ctx.globalState.update('aep.jira.pkce', undefined);
    }
    async refresh(refreshToken) {
        const clientId = vscode.workspace.getConfiguration('aep').get('jira.clientId');
        if (!clientId)
            return undefined;
        const resp = await fetch(TOKEN, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
                grant_type: 'refresh_token',
                client_id: clientId,
                refresh_token: refreshToken
            })
        });
        if (!resp.ok) {
            await this.secrets.delete(JiraOAuth.KEY);
            return undefined;
        }
        const tok = await resp.json();
        const expires_at = Date.now() + (tok.expires_in * 1000);
        await this.secrets.store(JiraOAuth.KEY, JSON.stringify({
            ...tok,
            expires_at
        }));
        return tok.access_token;
    }
}
exports.JiraOAuth = JiraOAuth;
JiraOAuth.KEY = 'aep.jira.oauth';
//# sourceMappingURL=jiraAuth.js.map