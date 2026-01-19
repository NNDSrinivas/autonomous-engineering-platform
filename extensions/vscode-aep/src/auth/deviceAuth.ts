import * as vscode from "vscode";

interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string;
  interval: number;
  expires_in: number;
}

interface TokenResponse {
  access_token: string;
  expires_in: number;
  token_type: string;
}

/**
 * Device Code Flow authentication service for VSCode extension.
 *
 * This implements OAuth 2.0 Device Authorization Grant (RFC 8628) which is
 * ideal for CLI/desktop applications that can't securely store client secrets.
 */
export class DeviceAuthService {
  private apiBaseUrl: string;
  private context: vscode.ExtensionContext;
  private pollInterval: NodeJS.Timeout | null = null;

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    // Default to 8000 which is the standard AEP backend port
    this.apiBaseUrl =
      vscode.workspace.getConfiguration("aep").get("apiUrl") ||
      "http://localhost:8000";
  }

  /**
   * Start the device code login flow.
   */
  async startLogin(): Promise<void> {
    try {
      // 1. Request device code from backend
      const response = await fetch(`${this.apiBaseUrl}/oauth/device/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        throw new Error(`Failed to start auth: ${response.statusText}`);
      }

      const data = await response.json() as DeviceCodeResponse;

      // 2. Show user code and prompt to open browser
      const action = await vscode.window.showInformationMessage(
        `To sign in, enter code: ${data.user_code}`,
        { modal: true },
        "Open Browser",
        "Copy Code"
      );

      if (action === "Open Browser") {
        await vscode.env.openExternal(
          vscode.Uri.parse(
            data.verification_uri_complete || data.verification_uri
          )
        );
      } else if (action === "Copy Code") {
        await vscode.env.clipboard.writeText(data.user_code);
        vscode.window.showInformationMessage(
          `Code "${data.user_code}" copied to clipboard!`
        );
        await vscode.env.openExternal(
          vscode.Uri.parse(data.verification_uri)
        );
      } else {
        // User cancelled
        return;
      }

      // 3. Poll for completion
      await this.pollForToken(data.device_code, data.interval, data.expires_in);
    } catch (error) {
      vscode.window.showErrorMessage(
        `Authentication failed: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    }
  }

  /**
   * Poll the backend for token after user authorizes.
   */
  private async pollForToken(
    deviceCode: string,
    interval: number,
    expiresIn: number
  ): Promise<void> {
    const maxAttempts = Math.floor(expiresIn / interval);
    let attempts = 0;

    return new Promise((resolve, reject) => {
      const poll = async () => {
        attempts++;

        try {
          const response = await fetch(`${this.apiBaseUrl}/oauth/device/poll`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_code: deviceCode }),
          });

          if (response.status === 200) {
            // Success - got the token
            const data = await response.json() as TokenResponse;
            await this.storeToken(data.access_token, data.expires_in);
            vscode.window.showInformationMessage(
              "Successfully signed in to NAVI!"
            );

            // Notify webview of auth state change
            this.notifyAuthStateChange(true);
            resolve();
            return;
          }

          if (response.status === 428) {
            // Authorization pending, continue polling
            if (attempts < maxAttempts) {
              this.pollInterval = setTimeout(poll, interval * 1000);
            } else {
              reject(new Error("Authentication timed out"));
            }
            return;
          }

          // Other error
          const errorText = await response.text();
          reject(new Error(errorText || `HTTP ${response.status}`));
        } catch (error) {
          reject(error);
        }
      };

      // Start polling
      poll();
    });
  }

  /**
   * Store the auth token securely.
   */
  private async storeToken(token: string, expiresIn: number): Promise<void> {
    const expiresAt = Date.now() + expiresIn * 1000;
    await this.context.secrets.store("aep.authToken", token);
    await this.context.globalState.update("aep.tokenExpiresAt", expiresAt);
  }

  /**
   * Get the current auth token if valid.
   */
  async getToken(): Promise<string | undefined> {
    const expiresAt = this.context.globalState.get<number>("aep.tokenExpiresAt");
    if (expiresAt && Date.now() > expiresAt) {
      // Token expired, clear it
      await this.logout();
      return undefined;
    }
    return await this.context.secrets.get("aep.authToken");
  }

  /**
   * Check if user is currently logged in.
   */
  async isLoggedIn(): Promise<boolean> {
    const token = await this.getToken();
    return !!token;
  }

  /**
   * Log out the current user.
   */
  async logout(): Promise<void> {
    // Clear polling if in progress
    if (this.pollInterval) {
      clearTimeout(this.pollInterval);
      this.pollInterval = null;
    }

    await this.context.secrets.delete("aep.authToken");
    await this.context.globalState.update("aep.tokenExpiresAt", undefined);
    vscode.window.showInformationMessage("Signed out of NAVI");

    // Notify webview of auth state change
    this.notifyAuthStateChange(false);
  }

  /**
   * Notify the webview of auth state changes.
   */
  private notifyAuthStateChange(isAuthenticated: boolean): void {
    // This will be picked up by the extension's webview message handler
    vscode.commands.executeCommand(
      "aep.notifyAuthStateChange",
      isAuthenticated
    );
  }

  /**
   * Get user info from the stored token (JWT decode).
   */
  async getUserInfo(): Promise<{
    sub: string;
    email: string;
    name?: string;
    org?: string;
    roles?: string[];
  } | null> {
    const token = await this.getToken();
    if (!token) return null;

    try {
      // Decode JWT payload (base64)
      const parts = token.split(".");
      if (parts.length !== 3) return null;

      const payload = JSON.parse(
        Buffer.from(parts[1], "base64").toString("utf-8")
      );

      return {
        sub: payload.sub,
        email: payload.email,
        name: payload.name,
        org: payload.org || payload["https://navralabs.com/org"],
        roles: payload.roles || payload["https://navralabs.com/roles"],
      };
    } catch {
      return null;
    }
  }

  /**
   * Add authorization header to fetch options.
   */
  async buildAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getToken();
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
    return {};
  }
}
