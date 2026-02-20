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

export type AuthSignInStatusState =
  | "starting"
  | "browser_opened"
  | "waiting_for_approval"
  | "success"
  | "error";

export interface AuthSignInStatus {
  state: AuthSignInStatusState;
  message: string;
  userCode?: string;
  verificationUri?: string;
  recoverable?: boolean;
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
    this.apiBaseUrl = this.resolveApiBaseUrl();
  }

  private resolveApiBaseUrl(): string {
    const config = vscode.workspace.getConfiguration("aep");
    const raw = (config.get<string>("navi.backendUrl") || "http://127.0.0.1:8787").trim();
    if (!raw) {
      return "http://127.0.0.1:8787";
    }

    try {
      const parsed = new URL(raw);
      parsed.pathname = parsed.pathname
        .replace(/\/api\/navi\/chat\/?$/i, "")
        .replace(/\/api\/chat\/respond\/?$/i, "")
        .replace(/\/+$/, "");
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString().replace(/\/$/, "");
    } catch {
      return "http://127.0.0.1:8787";
    }
  }

  private emitStatus(
    status: AuthSignInStatus,
    onStatus?: (status: AuthSignInStatus) => void
  ): void {
    if (onStatus) {
      onStatus(status);
    }
  }

  private getVerificationTarget(data: DeviceCodeResponse): string {
    const target = (data.verification_uri_complete || data.verification_uri || "").trim();
    if (!target) {
      throw new Error("Sign-in verification URL is missing from backend response.");
    }
    return target;
  }

  /**
   * Start the device code login flow.
   */
  async startLogin(onStatus?: (status: AuthSignInStatus) => void): Promise<void> {
    this.apiBaseUrl = this.resolveApiBaseUrl();

    const emit = (status: AuthSignInStatus) => this.emitStatus(status, onStatus);
    let terminalStatusEmitted = false;

    try {
      emit({
        state: "starting",
        message: "Starting secure sign-in...",
      });

      const response = await fetch(`${this.apiBaseUrl}/oauth/device/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        let detail = "";
        try {
          detail = await response.text();
        } catch {
          detail = response.statusText;
        }
        throw new Error(`Failed to start sign-in (HTTP ${response.status}). ${detail || ""}`.trim());
      }

      const data = (await response.json()) as DeviceCodeResponse;

      const verificationTarget = this.getVerificationTarget(data);
      let browserOpened = false;
      try {
        await vscode.env.openExternal(vscode.Uri.parse(verificationTarget));
        browserOpened = true;
      } catch {
        browserOpened = false;
      }

      if (browserOpened) {
        emit({
          state: "browser_opened",
          message: "Browser opened for NAVI authorization.",
          userCode: data.user_code,
          verificationUri: verificationTarget,
        });
      } else {
        emit({
          state: "error",
          message: "Could not open browser automatically. Use fallback actions to continue sign-in.",
          userCode: data.user_code,
          verificationUri: verificationTarget,
          recoverable: true,
        });

        const action = await vscode.window.showWarningMessage(
          "NAVI could not open your browser. You can retry opening it or copy the authorization code.",
          "Open Browser",
          "Copy Code",
          "Cancel"
        );

        if (action === "Open Browser") {
          await vscode.env.openExternal(vscode.Uri.parse(verificationTarget));
        } else if (action === "Copy Code") {
          await vscode.env.clipboard.writeText(data.user_code);
          vscode.window.showInformationMessage("Device code copied. Open the verification page and authorize.");
          await vscode.env.openExternal(vscode.Uri.parse(data.verification_uri));
        } else {
          throw new Error("Sign-in cancelled before browser authorization.");
        }
      }

      emit({
        state: "waiting_for_approval",
        message: data.verification_uri_complete
          ? "Waiting for browser authorization..."
          : "Waiting for browser authorization. If prompted, enter the device code shown.",
        userCode: data.user_code,
        verificationUri: verificationTarget,
      });

      await this.pollForToken(data.device_code, data.interval, data.expires_in, emit);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Authentication failed due to an unknown error.";

      if (!/cancelled/i.test(message)) {
        if (!terminalStatusEmitted) {
          emit({
            state: "error",
            message,
          });
        }
        vscode.window.showErrorMessage(`Authentication failed: ${message}`);
      }

      throw error;
    }
  }

  /**
   * Poll the backend for token after user authorizes.
   */
  private async pollForToken(
    deviceCode: string,
    interval: number,
    expiresIn: number,
    emit: (status: AuthSignInStatus) => void
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
            const data = (await response.json()) as TokenResponse;
            await this.storeToken(data.access_token, data.expires_in);

            emit({
              state: "success",
              message: "Successfully signed in to NAVI.",
            });

            vscode.window.showInformationMessage("Successfully signed in to NAVI.");
            this.notifyAuthStateChange(true);
            resolve();
            return;
          }

          const isPendingStatus = response.status === 428;
          let pendingFromBody = false;
          let errorText = "";

          try {
            const maybeJson = await response.clone().json();
            const detail = (maybeJson as { detail?: string }).detail;
            const errorCode = (maybeJson as { error_code?: string }).error_code;
            pendingFromBody = detail === "authorization_pending";
            errorText = JSON.stringify(maybeJson);
            if (errorCode && detail && !isPendingStatus) {
              errorText = JSON.stringify({ detail, error_code: errorCode });
            }
          } catch {
            errorText = await response.text();
          }

          if (isPendingStatus || pendingFromBody) {
            emit({
              state: "waiting_for_approval",
              message: "Waiting for browser authorization...",
            });
            if (attempts < maxAttempts) {
              this.pollInterval = setTimeout(poll, interval * 1000);
            } else {
              reject(new Error("Authentication timed out while waiting for approval."));
            }
            return;
          }

          reject(new Error(errorText || `HTTP ${response.status}`));
        } catch (error) {
          reject(error);
        }
      };

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
    if (this.pollInterval) {
      clearTimeout(this.pollInterval);
      this.pollInterval = null;
    }

    await this.context.secrets.delete("aep.authToken");
    await this.context.globalState.update("aep.tokenExpiresAt", undefined);
    vscode.window.showInformationMessage("Signed out of NAVI");

    this.notifyAuthStateChange(false);
  }

  /**
   * Notify the webview of auth state changes.
   */
  private notifyAuthStateChange(isAuthenticated: boolean): void {
    vscode.commands.executeCommand("aep.notifyAuthStateChange", isAuthenticated);
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
      const parts = token.split(".");
      if (parts.length !== 3) return null;

      const payload = JSON.parse(Buffer.from(parts[1], "base64").toString("utf-8"));

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
}
