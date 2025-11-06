import * as vscode from 'vscode';
import axios from 'axios';

/**
 * Authentication Manager for AEP Extension
 * 
 * Implements OAuth Device Code flow for secure authentication without
 * storing client secrets in the extension.
 */

interface DeviceCodeResponse {
    device_code: string;
    user_code: string;
    verification_uri: string;
    verification_uri_complete: string;
    expires_in: number;
    interval: number;
}

interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
    scope: string;
}

interface UserInfo {
    id: string;
    username: string;
    email: string;
    name: string;
    organizations: string[];
}

export class AuthManager {
    private context: vscode.ExtensionContext;
    private accessToken: string | undefined;
    private refreshToken: string | undefined;
    private userInfo: UserInfo | undefined;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.loadStoredTokens();
    }

    /**
     * Start OAuth device code authentication flow
     */
    async authenticate(): Promise<boolean> {
        try {
            const config = vscode.workspace.getConfiguration('aep');
            const coreApiUrl = config.get<string>('coreApi') || 'http://localhost:8002';

            // Step 1: Request device code
            const deviceCodeResponse = await axios.post<DeviceCodeResponse>(
                `${coreApiUrl}/api/auth/device/code`,
                {
                    client_id: 'aep-vscode-extension',
                    scope: 'read write jira confluence slack teams zoom'
                }
            );

            const { device_code, user_code, verification_uri_complete, expires_in, interval } = deviceCodeResponse.data;

            // Step 2: Show user code and open browser
            const openBrowser = await vscode.window.showInformationMessage(
                `Please visit the following URL to authenticate:\n\nUser Code: ${user_code}`,
                { modal: true },
                'Open Browser',
                'I\'ve completed authentication'
            );

            if (openBrowser === 'Open Browser') {
                vscode.env.openExternal(vscode.Uri.parse(verification_uri_complete));
            }

            // Step 3: Poll for token
            const token = await this.pollForToken(coreApiUrl, device_code, interval, expires_in);
            
            if (token) {
                await this.storeTokens(token);
                await this.loadUserInfo();
                return true;
            }

            return false;
        } catch (error) {
            console.error('Authentication failed:', error);
            throw new Error(`Authentication failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }

    /**
     * Check if user is currently authenticated
     */
    async isAuthenticated(): Promise<boolean> {
        if (!this.accessToken) {
            return false;
        }

        try {
            // Validate token with a simple API call
            const config = vscode.workspace.getConfiguration('aep');
            const coreApiUrl = config.get<string>('coreApi') || 'http://localhost:8002';

            const response = await axios.get(`${coreApiUrl}/api/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${this.accessToken}`
                }
            });

            this.userInfo = response.data;
            return true;
        } catch (error) {
            // Token might be expired, try to refresh
            if (this.refreshToken) {
                return await this.refreshAccessToken();
            }
            return false;
        }
    }

    /**
     * Get current access token for API calls
     */
    getAccessToken(): string | undefined {
        return this.accessToken;
    }

    /**
     * Get current user information
     */
    getUserInfo(): UserInfo | undefined {
        return this.userInfo;
    }

    /**
     * Sign out and clear stored tokens
     */
    async signOut(): Promise<void> {
        this.accessToken = undefined;
        this.refreshToken = undefined;
        this.userInfo = undefined;

        await this.context.secrets.delete('aep.access_token');
        await this.context.secrets.delete('aep.refresh_token');
        await this.context.globalState.update('aep.user_info', undefined);

        vscode.window.showInformationMessage('Successfully signed out of AEP.');
    }

    /**
     * Dispose resources
     */
    dispose(): void {
        // Clean up if needed
    }

    /**
     * Poll for token after device code authorization
     */
    private async pollForToken(
        coreApiUrl: string, 
        deviceCode: string, 
        interval: number, 
        expiresIn: number
    ): Promise<TokenResponse | null> {
        const startTime = Date.now();
        const maxDuration = expiresIn * 1000; // Convert to milliseconds

        return new Promise((resolve) => {
            const poll = async () => {
                if (Date.now() - startTime > maxDuration) {
                    vscode.window.showErrorMessage('Authentication timed out. Please try again.');
                    resolve(null);
                    return;
                }

                try {
                    const response = await axios.post<TokenResponse>(
                        `${coreApiUrl}/api/auth/device/token`,
                        {
                            client_id: 'aep-vscode-extension',
                            device_code: deviceCode,
                            grant_type: 'urn:ietf:params:oauth:grant-type:device_code'
                        }
                    );

                    resolve(response.data);
                } catch (error: any) {
                    if (error.response?.status === 400) {
                        const errorCode = error.response.data?.error;
                        if (errorCode === 'authorization_pending') {
                            // Continue polling
                            setTimeout(poll, interval * 1000);
                        } else if (errorCode === 'slow_down') {
                            // Increase polling interval
                            setTimeout(poll, (interval + 5) * 1000);
                        } else {
                            vscode.window.showErrorMessage(`Authentication failed: ${errorCode}`);
                            resolve(null);
                        }
                    } else {
                        vscode.window.showErrorMessage('Authentication failed due to network error.');
                        resolve(null);
                    }
                }
            };

            // Start polling
            poll();
        });
    }

    /**
     * Refresh access token using refresh token
     */
    private async refreshAccessToken(): Promise<boolean> {
        if (!this.refreshToken) {
            return false;
        }

        try {
            const config = vscode.workspace.getConfiguration('aep');
            const coreApiUrl = config.get<string>('coreApi') || 'http://localhost:8002';

            const response = await axios.post<TokenResponse>(
                `${coreApiUrl}/api/auth/token/refresh`,
                {
                    refresh_token: this.refreshToken,
                    grant_type: 'refresh_token'
                }
            );

            await this.storeTokens(response.data);
            return true;
        } catch (error) {
            console.error('Token refresh failed:', error);
            // Clear invalid tokens
            await this.signOut();
            return false;
        }
    }

    /**
     * Store tokens securely in VS Code secret storage
     */
    private async storeTokens(tokens: TokenResponse): Promise<void> {
        this.accessToken = tokens.access_token;
        this.refreshToken = tokens.refresh_token;

        await this.context.secrets.store('aep.access_token', tokens.access_token);
        if (tokens.refresh_token) {
            await this.context.secrets.store('aep.refresh_token', tokens.refresh_token);
        }
    }

    /**
     * Load stored tokens from VS Code secret storage
     */
    private async loadStoredTokens(): Promise<void> {
        this.accessToken = await this.context.secrets.get('aep.access_token');
        this.refreshToken = await this.context.secrets.get('aep.refresh_token');
        this.userInfo = this.context.globalState.get('aep.user_info');
    }

    /**
     * Load user information and cache it
     */
    private async loadUserInfo(): Promise<void> {
        if (!this.accessToken) {
            return;
        }

        try {
            const config = vscode.workspace.getConfiguration('aep');
            const coreApiUrl = config.get<string>('coreApi') || 'http://localhost:8002';

            const response = await axios.get<UserInfo>(`${coreApiUrl}/api/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${this.accessToken}`
                }
            });

            this.userInfo = response.data;
            await this.context.globalState.update('aep.user_info', this.userInfo);
        } catch (error) {
            console.error('Failed to load user info:', error);
        }
    }
}