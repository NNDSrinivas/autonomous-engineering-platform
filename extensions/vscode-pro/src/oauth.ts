import * as vscode from 'vscode';
import * as crypto from 'crypto';

export function base64Url(buf: Buffer | string): string {
    return Buffer.from(buf).toString('base64')
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function pkcePair(): Promise<{ verifier: string, challenge: string }> {
    const verifier = base64Url(crypto.randomBytes(32));
    const challenge = base64Url(crypto.createHash('sha256').update(verifier).digest());
    return { verifier, challenge };
}

export async function authCallbackUri(context: vscode.ExtensionContext, q: Record<string, string> = {}): Promise<vscode.Uri> {
    // vscode://publisher.extensionId/auth-callback?provider=jira&state=...
    const base = vscode.Uri.parse(`${vscode.env.uriScheme}://${context.extension.id}/auth-callback`);
    const withQ = base.with({ query: new URLSearchParams(q).toString() });
    return await vscode.env.asExternalUri(withQ);
}

export function cryptoRandom(): string {
    return [...crypto.getRandomValues(new Uint8Array(16))]
        .map(b => b.toString(16).padStart(2, '0')).join('');
}