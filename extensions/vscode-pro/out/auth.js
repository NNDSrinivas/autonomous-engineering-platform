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
exports.signIn = signIn;
exports.getAccessToken = getAccessToken;
exports.signOut = signOut;
const vscode = __importStar(require("vscode"));
const crypto = __importStar(require("crypto"));
const http = __importStar(require("http"));
const url = __importStar(require("url"));
const AUTH0_DOMAIN = (process.env.AUTH0_DOMAIN || vscode.workspace.getConfiguration('aep').get('auth0Domain')) || 'auth.navralabs.com';
const CLIENT_ID = (process.env.AUTH0_CLIENT_ID || vscode.workspace.getConfiguration('aep').get('auth0ClientId')) || '6aJ5nY80nZmZKvTiv6PxLIZ8EiFEdqT3';
const AUDIENCE = (process.env.AUTH0_AUDIENCE || vscode.workspace.getConfiguration('aep').get('auth0Audience')) || 'https://api.navralabs.com';
const REDIRECT_VSC = 'vscode://navralabs.aep-professional/auth/callback';
const REDIRECT_LB = 'http://127.0.0.1:8765/callback';
async function signIn(context) {
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
    let codePromise;
    if (useLoopback) {
        codePromise = waitForCodeOnLoopback();
    }
    else {
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
    }
    catch (error) {
        vscode.window.showErrorMessage(`Sign in failed: ${error}`);
        throw error;
    }
}
function waitForCodeFromUriHandler(context) {
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            reject(new Error('Authentication timeout'));
        }, 120000); // 2 minutes
        const disposable = vscode.window.registerUriHandler({
            handleUri(uri) {
                clearTimeout(timeout);
                disposable.dispose();
                const q = new URLSearchParams(uri.query);
                const code = q.get('code');
                const error = q.get('error');
                if (error) {
                    reject(new Error(`Auth0 error: ${error}`));
                }
                else if (code) {
                    resolve(code);
                }
                else {
                    reject(new Error('Missing authorization code'));
                }
            }
        });
        context.subscriptions.push(disposable);
    });
}
function waitForCodeOnLoopback() {
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
                }
                else if (code) {
                    res.end('<h2>Authentication Successful!</h2><p>You may close this window and return to VS Code.</p>');
                    resolve(code);
                }
                else {
                    res.end('<h2>Missing authorization code</h2><p>You may close this window and return to VS Code.</p>');
                    reject(new Error('Missing authorization code'));
                }
            }
            catch (err) {
                res.statusCode = 500;
                res.end('<h2>Server Error</h2><p>You may close this window and return to VS Code.</p>');
                reject(err);
            }
            finally {
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
async function exchangeCodeForToken(code, verifier, redirectUri) {
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
    return resp.json();
}
async function getAccessToken(context) {
    return await context.secrets.get('aep.accessToken');
}
async function signOut(context) {
    await context.secrets.delete('aep.accessToken');
    await context.secrets.delete('aep.refreshToken');
    vscode.commands.executeCommand('aep.refreshView');
    vscode.window.showInformationMessage('Signed out of AEP.');
}
function base64url(b) {
    return b.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
//# sourceMappingURL=auth.js.map