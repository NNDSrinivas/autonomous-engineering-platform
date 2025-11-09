import * as vscode from 'vscode';
import { authCallbackUri, pkcePair, cryptoRandom } from './oauth';

// Atlassian Cloud OAuth 2.0 (3LO + PKCE)
const AUTHZ = 'https://auth.atlassian.com/authorize';
const TOKEN = 'https://auth.atlassian.com/oauth/token';
const AUDIENCE = 'api.atlassian.com';

// Minimal scopes for read-only feed; add as needed
const SCOPES = [
    'read:jira-user',
    'read:jira-work'
].join(' ');

interface TokenData {
    access_token: string;
    refresh_token?: string;
    expires_at: number;
}

export class JiraOAuth {
    private secrets: vscode.SecretStorage;
    private ctx: vscode.ExtensionContext;
    static readonly KEY = 'aep.jira.oauth';

    constructor(ctx: vscode.ExtensionContext) {
        this.ctx = ctx;
        this.secrets = ctx.secrets;
    }

    async getAccessToken(): Promise<string | undefined> {
        const raw = await this.secrets.get(JiraOAuth.KEY);
        if (!raw) return;

        const token = JSON.parse(raw) as TokenData;
        if (Date.now() < token.expires_at - 60_000) return token.access_token;

        if (token.refresh_token) {
            return this.refresh(token.refresh_token);
        }
        return undefined;
    }

    async signOut(): Promise<void> {
        await this.secrets.delete(JiraOAuth.KEY);
    }

    async connected(): Promise<boolean> {
        const token = await this.getAccessToken();
        return !!token;
    }

    async start(): Promise<void> {
        const cfg = vscode.workspace.getConfiguration('aep');
        const clientId = cfg.get<string>('jira.clientId');
        if (!clientId) {
            vscode.window.showErrorMessage('Set "AEP: Jira Client ID" in Settings first.');
            return;
        }

        const { verifier, challenge } = await pkcePair();
        const state = cryptoRandom();

        const redirect = await authCallbackUri(this.ctx, { provider: 'jira', state });
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

    async finish(code: string, returnedState: string): Promise<void> {
        const pkce = this.ctx.globalState.get<{
            verifier: string;
            state: string;
            redirect: string;
            clientId: string;
        }>('aep.jira.pkce');

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

        const tok = await resp.json() as {
            access_token: string;
            refresh_token?: string;
            expires_in: number;
        };

        const expires_at = Date.now() + (tok.expires_in * 1000);
        await this.secrets.store(JiraOAuth.KEY, JSON.stringify({
            ...tok,
            expires_at
        }));

        await this.ctx.globalState.update('aep.jira.pkce', undefined);
    }

    private async refresh(refreshToken: string): Promise<string | undefined> {
        const clientId = vscode.workspace.getConfiguration('aep').get<string>('jira.clientId');
        if (!clientId) return undefined;

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

        const tok = await resp.json() as {
            access_token: string;
            refresh_token?: string;
            expires_in: number;
        };

        const expires_at = Date.now() + (tok.expires_in * 1000);
        await this.secrets.store(JiraOAuth.KEY, JSON.stringify({
            ...tok,
            expires_at
        }));

        return tok.access_token;
    }
}