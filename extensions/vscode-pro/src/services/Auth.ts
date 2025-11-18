import * as vscode from 'vscode';

export class Auth {
    constructor(private ctx: vscode.ExtensionContext) { }

    private tokenKey = 'aep.token';

    async isSignedIn(): Promise<boolean> {
        const token = await this.ctx.secrets.get(this.tokenKey);
        return !!token;
    }

    async signIn(): Promise<void> {
        try {
            const cfg = vscode.workspace.getConfiguration('aep');
            const domain = cfg.get<string>('auth.domain') || 'auth.navralabs.com';
            const audience = cfg.get<string>('auth.audience') || 'https://api.navralabs.com';

            // Open the authorization URL in the browser
            const authUrl = `https://${domain}/authorize?audience=${encodeURIComponent(audience)}&device=true&response_type=code&scope=openid%20profile%20email`;

            await vscode.env.openExternal(vscode.Uri.parse(authUrl));

            vscode.window.showInformationMessage(
                '🔐 Complete sign-in in the browser, then paste your access token below.',
                { modal: false }
            );

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
            } else {
                vscode.window.showWarningMessage('⚠️ Sign-in cancelled');
            }
        } catch (error: any) {
            vscode.window.showErrorMessage(`❌ Sign-in failed: ${error?.message || String(error)}`);
        }
    }

    async signOut(): Promise<void> {
        try {
            await this.ctx.secrets.delete(this.tokenKey);
            vscode.window.showInformationMessage('👋 Successfully signed out from AEP Professional');
        } catch (error: any) {
            vscode.window.showErrorMessage(`❌ Sign-out failed: ${error?.message || String(error)}`);
        }
    }

    async getAccessToken(): Promise<string | undefined> {
        return this.ctx.secrets.get(this.tokenKey);
    }

    // Method to validate if the stored token is still valid
    async validateToken(): Promise<boolean> {
        const token = await this.getAccessToken();
        if (!token) return false;

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
        } catch {
            // Invalid token format, remove it
            await this.ctx.secrets.delete(this.tokenKey);
            return false;
        }
    }
}