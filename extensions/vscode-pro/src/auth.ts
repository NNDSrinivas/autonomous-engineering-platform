import * as vscode from 'vscode';
import * as crypto from 'crypto';
import * as http from 'http';
import * as url from 'url';

const AUTH0_DOMAIN = (process.env.AUTH0_DOMAIN || vscode.workspace.getConfiguration('aep').get('auth0Domain')) as string || 'auth.navralabs.com';
const CLIENT_ID = (process.env.AUTH0_CLIENT_ID || vscode.workspace.getConfiguration('aep').get('auth0ClientId')) as string || '6aJ5nY80nZmZKvTiv6PxLIZ8EiFEdqT3';
const AUDIENCE = (process.env.AUTH0_AUDIENCE || vscode.workspace.getConfiguration('aep').get('auth0Audience')) as string || 'https://api.navralabs.com';
const REDIRECT_VSC = 'vscode://navralabs.aep-professional/auth/callback';
const REDIRECT_LB = 'http://127.0.0.1:8765/callback';

export async function signIn(context: vscode.ExtensionContext) {
    const codeVerifier = base64url(crypto.randomBytes(32));
    const codeChallenge = base64url(crypto.createHash('sha256').update(codeVerifier).digest());

    // Prefer VS Code URI handler; fallback to loopback if blocked by environment.
    const useLoopback = vscode.env.appHost === 'web';
    const redirectUri = useLoopback ? REDIRECT_LB : REDIRECT_VSC;

    const authUrl = new URL(`https://${AUTH0_DOMAIN}/authorize`);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('client_id', CLIENT_ID);
    authUrl.searchParams.set('audience', AUDIENCE);
    authUrl.searchParams.set('scope', 'openid profile email offline_access');
    authUrl.searchParams.set('code_challenge', codeChallenge);
    authUrl.searchParams.set('code_challenge_method', 'S256');
    authUrl.searchParams.set('redirect_uri', redirectUri);

    let codePromise: Promise<string>;

    if (useLoopback) {
        codePromise = waitForCodeOnLoopback();
    } else {
        codePromise = waitForCodeFromUriHandler(context);
    }

    await vscode.env.openExternal(vscode.Uri.parse(authUrl.toString()));

    try {
        const code = await codePromise;
        const token = await exchangeCodeForToken(code, codeVerifier, redirectUri);

        await context.secrets.store('aep.accessToken', token.access_token);
        await context.secrets.store('aep.refreshToken', token.refresh_token || '');

        vscode.commands.executeCommand('aep.refreshView');
        vscode.window.showInformationMessage('Signed in to AEP.');
    } catch (error) {
        vscode.window.showErrorMessage(`Sign in failed: ${error}`);
        throw error;
    }
}

function waitForCodeFromUriHandler(context: vscode.ExtensionContext) {
    return new Promise<string>((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('Authentication timeout'));
        }, 120000); // 2 minutes

        const disposable = vscode.window.registerUriHandler({
            handleUri(uri: vscode.Uri) {
                clearTimeout(timeout);
                disposable.dispose();

                const q = new URLSearchParams(uri.query);
                const code = q.get('code');
                const error = q.get('error');

                if (error) {
                    reject(new Error(`Auth0 error: ${error}`));
                } else if (code) {
                    resolve(code);
                } else {
                    reject(new Error('Missing authorization code'));
                }
            }
        });

        context.subscriptions.push(disposable);
    });
}

function waitForCodeOnLoopback(): Promise<string> {
    return new Promise((resolve, reject) => {
        const server = http.createServer((req, res) => {
            try {
                const reqUrl = new url.URL(req.url || '', 'http://127.0.0.1:8765');
                const q = reqUrl.searchParams;
                const code = q.get('code');
                const error = q.get('error');

                res.statusCode = 200;
                res.setHeader('Content-Type', 'text/html');

                if (error) {
                    res.end(`<h2>Authentication Error: ${error}</h2><p>You may close this window and return to VS Code.</p>`);
                    reject(new Error(`Auth0 error: ${error}`));
                } else if (code) {
                    res.end('<h2>Authentication Successful!</h2><p>You may close this window and return to VS Code.</p>');
                    resolve(code);
                } else {
                    res.end('<h2>Missing authorization code</h2><p>You may close this window and return to VS Code.</p>');
                    reject(new Error('Missing authorization code'));
                }
            } catch (err) {
                res.statusCode = 500;
                res.end('<h2>Server Error</h2><p>You may close this window and return to VS Code.</p>');
                reject(err);
            } finally {
                server.close();
            }
        }).listen(8765, '127.0.0.1', () => {
            console.log('Auth callback server listening on http://127.0.0.1:8765');
        });

        server.on('error', (err) => {
            reject(new Error(`Callback server error: ${err.message}`));
        });
    });
}

interface TokenResponse {
    access_token: string;
    refresh_token?: string;
    token_type: string;
    expires_in: number;
}

async function exchangeCodeForToken(code: string, verifier: string, redirectUri: string): Promise<TokenResponse> {
    const tokenUrl = `https://${AUTH0_DOMAIN}/oauth/token`;
    const body = {
        grant_type: 'authorization_code',
        client_id: CLIENT_ID,
        code_verifier: verifier,
        code,
        redirect_uri: redirectUri,
        audience: AUDIENCE
    };

    const resp = await fetch(tokenUrl, {
        method: 'POST',
        headers: {
            'content-type': 'application/json'
        },
        body: JSON.stringify(body)
    });

    if (!resp.ok) {
        const errorText = await resp.text();
        throw new Error(`Token exchange failed (${resp.status}): ${errorText}`);
    }

    return resp.json() as Promise<TokenResponse>;
}

export async function getAccessToken(context: vscode.ExtensionContext): Promise<string | undefined> {
    return await context.secrets.get('aep.accessToken');
}

export async function signOut(context: vscode.ExtensionContext): Promise<void> {
    await context.secrets.delete('aep.accessToken');
    await context.secrets.delete('aep.refreshToken');
    vscode.commands.executeCommand('aep.refreshView');
    vscode.window.showInformationMessage('Signed out of AEP.');
}

function base64url(b: Buffer): string {
    return b.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}