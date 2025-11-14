import * as vscode from 'vscode';
import axios from 'axios';

export interface AuthState {
    isAuthenticated: boolean;
    accessToken?: string;
    refreshToken?: string;
    user?: {
        id: string;
        email: string;
        name: string;
    };
}

export interface DeviceCodeResponse {
    device_code: string;
    user_code: string;
    verification_uri: string;
    verification_uri_complete: string;
    expires_in: number;
    interval: number;
}

export interface TokenResponse {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
    token_type: string;
}

export class AuthService {
    private _onAuthStateChanged = new vscode.EventEmitter<boolean>();
    public readonly onAuthStateChanged = this._onAuthStateChanged.event;

    private _authState: AuthState = { isAuthenticated: false };
    private _config = vscode.workspace.getConfiguration('aep');
    private _apiUrl: string;

    constructor(private context: vscode.ExtensionContext) {
        this._apiUrl = this._config.get('apiUrl', 'http://localhost:8001');
        this.loadAuthState();
    }

    public async isAuthenticated(): Promise<boolean> {
        // Validate current token if exists
        if (this._authState.accessToken) {
            try {
                await this.validateToken();
                return true;
            } catch {
                await this.clearAuthState();
                return false;
            }
        }
        return false;
    }

    public async signIn(): Promise<void> {
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

        } catch (error) {
            console.error('Sign in failed:', error);
            throw error;
        }
    }

    public async signOut(): Promise<void> {
        await this.clearAuthState();
        this._onAuthStateChanged.fire(false);
    }

    public getAccessToken(): string | undefined {
        return this._authState.accessToken;
    }

    public getUser(): AuthState['user'] {
        return this._authState.user;
    }

    private async startDeviceFlow(): Promise<DeviceCodeResponse> {
        const response = await axios.post(`${this._apiUrl}/oauth/device/start`, {}, {
            headers: { 'Content-Type': 'application/json' }
        });

        return response.data;
    }

    private async showDeviceCodePrompt(deviceCode: DeviceCodeResponse): Promise<void> {
        const action = await vscode.window.showInformationMessage(
            `🔐 Sign in to AEP: Enter code ${deviceCode.user_code}`,
            { modal: true },
            'Open Browser', 'Copy Code', 'Cancel'
        );

        if (action === 'Open Browser') {
            vscode.env.openExternal(vscode.Uri.parse(deviceCode.verification_uri_complete));
        } else if (action === 'Copy Code') {
            vscode.env.clipboard.writeText(deviceCode.user_code);
            vscode.env.openExternal(vscode.Uri.parse(deviceCode.verification_uri));
        } else {
            throw new Error('Authentication cancelled by user');
        }
    }

    private async pollForToken(deviceCode: DeviceCodeResponse): Promise<TokenResponse> {
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
                    const response = await axios.post(`${this._apiUrl}/oauth/device/poll`, {
                        device_code: deviceCode.device_code
                    });

                    if (response.status === 200) {
                        clearInterval(interval);
                        resolve(response.data);
                    }
                } catch (error: any) {
                    if (error.response?.status === 428) {
                        // Still waiting for user authorization
                        return;
                    } else {
                        clearInterval(interval);
                        reject(error);
                    }
                }
            }, deviceCode.interval * 1000);
        });
    }

    private async getUserInfo(accessToken: string): Promise<AuthState['user']> {
        const response = await axios.get(`${this._apiUrl}/api/me`, {
            headers: { Authorization: `Bearer ${accessToken}` }
        });

        return response.data;
    }

    private async validateToken(): Promise<void> {
        if (!this._authState.accessToken) {
            throw new Error('No access token');
        }

        await axios.get(`${this._apiUrl}/api/me`, {
            headers: { Authorization: `Bearer ${this._authState.accessToken}` }
        });
    }

    private async loadAuthState(): Promise<void> {
        try {
            const stored = this.context.globalState.get<AuthState>('aep.auth');
            if (stored) {
                this._authState = stored;
            }
        } catch (error) {
            console.error('Failed to load auth state:', error);
        }
    }

    private async saveAuthState(): Promise<void> {
        await this.context.globalState.update('aep.auth', this._authState);
    }

    private async clearAuthState(): Promise<void> {
        this._authState = { isAuthenticated: false };
        await this.context.globalState.update('aep.auth', undefined);
    }
}