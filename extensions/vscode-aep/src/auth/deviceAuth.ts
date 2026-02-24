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
  refresh_token?: string;
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

  private parseJsonSafe(value: string): unknown {
    const trimmed = value.trim();
    if (!trimmed) {
      return undefined;
    }
    try {
      return JSON.parse(trimmed);
    } catch {
      return undefined;
    }
  }

  private extractAuthErrorShape(
    value: unknown
  ): { error?: string; errorDescription?: string; hint?: string } {
    if (!value || typeof value !== "object") {
      return {};
    }
    const obj = value as Record<string, unknown>;

    if (
      typeof obj.error === "string" ||
      typeof obj.error_description === "string" ||
      typeof obj.errorDescription === "string"
    ) {
      return {
        error: typeof obj.error === "string" ? obj.error : undefined,
        errorDescription:
          typeof obj.error_description === "string"
            ? obj.error_description
            : typeof obj.errorDescription === "string"
            ? obj.errorDescription
            : undefined,
        hint: typeof obj.hint === "string" ? obj.hint : undefined,
      };
    }

    if (typeof obj.detail === "string") {
      const nested = this.parseJsonSafe(obj.detail);
      if (nested) {
        return this.extractAuthErrorShape(nested);
      }
    }
    if (obj.detail && typeof obj.detail === "object") {
      return this.extractAuthErrorShape(obj.detail);
    }

    return {};
  }

  private buildStartLoginErrorMessage(status: number, detailText: string): string {
    const parsed = this.parseJsonSafe(detailText);
    const authError = this.extractAuthErrorShape(parsed);
    const errorCode = (authError.error || "").toLowerCase();

    if (errorCode === "unauthorized_client") {
      return (
        "NAVI sign-in is blocked by Auth0 configuration. " +
        "Enable Device Authorization Grant for this Auth0 application, and verify AUTH0_CLIENT_ID and AUTH0_AUDIENCE in backend environment settings."
      );
    }

    if (errorCode === "invalid_client") {
      return (
        "NAVI sign-in is blocked by invalid Auth0 client settings. " +
        "Verify AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET in backend environment settings."
      );
    }
    if (errorCode === "auth0_configuration_error") {
      return (
        "NAVI sign-in is blocked by backend Auth0 configuration. " +
        (authError.errorDescription || "Verify AUTH0_DOMAIN, AUTH0_CLIENT_ID, and AUTH0_AUDIENCE.")
      );
    }
    if (errorCode === "auth0_unreachable") {
      return (
        "NAVI sign-in could not reach Auth0 from the backend. " +
        (authError.errorDescription ||
          "Verify AUTH0_DOMAIN DNS resolution and outbound network access.")
      );
    }

    const description = (authError.errorDescription || "").trim();
    if (description) {
      return `Failed to start sign-in (HTTP ${status}). ${description}`;
    }

    const fallbackDetail = detailText.trim();
    if (fallbackDetail) {
      return `Failed to start sign-in (HTTP ${status}). ${fallbackDetail}`;
    }

    return `Failed to start sign-in (HTTP ${status}).`;
  }

  /**
   * Start the device code login flow.
   */
  async startLogin(onStatus?: (status: AuthSignInStatus) => void): Promise<void> {
    this.apiBaseUrl = this.resolveApiBaseUrl();

    let terminalStatusEmitted = false;
    const emit = (status: AuthSignInStatus) => {
      // Mark when a terminal status (success, error) has been emitted
      if (status.state === "success" || status.state === "error") {
        terminalStatusEmitted = true;
      }
      this.emitStatus(status, onStatus);
    };

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
        throw new Error(this.buildStartLoginErrorMessage(response.status, detail));
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
    // Use defaults if Auth0 doesn't return these values
    const actualInterval = interval || 5;  // Default 5 seconds
    const actualExpiresIn = expiresIn || 600;  // Default 10 minutes
    const maxAttempts = Math.floor(actualExpiresIn / actualInterval);

    console.log(`[AEP] Device flow polling: expires_in=${actualExpiresIn}s, interval=${actualInterval}s, maxAttempts=${maxAttempts}`);

    let attempts = 0;
    let lastEmitTime = 0;
    let currentInterval = actualInterval;  // Track current interval (increases on slow_down)
    const EMIT_THROTTLE_MS = 10000; // Only emit waiting status every 10 seconds

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
            await this.storeToken(data.access_token, data.expires_in, data.refresh_token);

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
          let isSlowDown = false;
          let errorText = "";

          try {
            const maybeJson = await response.clone().json();
            const detail = (maybeJson as { detail?: any }).detail;
            const errorCode = (maybeJson as { error_code?: string }).error_code;
            // Backend returns detail as object: {"error": "authorization_pending", ...}
            const authError = typeof detail === "object" ? detail?.error : detail;
            isSlowDown = authError === "slow_down";
            pendingFromBody = authError === "authorization_pending" || isSlowDown;
            errorText = JSON.stringify(maybeJson);
            if (errorCode && detail && !isPendingStatus) {
              errorText = JSON.stringify({ detail, error_code: errorCode });
            }
          } catch {
            errorText = await response.text();
          }

          if (isPendingStatus || pendingFromBody) {
            // Per RFC 8628: slow_down requires increasing polling interval
            if (isSlowDown) {
              currentInterval = Math.min(currentInterval + 5, 30);  // +5s per RFC, cap at 30s
              console.log(`[AEP] Received slow_down, increasing interval to ${currentInterval}s`);
            }

            // Throttle "waiting_for_approval" emissions to avoid spamming webview
            const now = Date.now();
            if (attempts === 1 || now - lastEmitTime >= EMIT_THROTTLE_MS) {
              emit({
                state: "waiting_for_approval",
                message: "Waiting for browser authorization...",
              });
              lastEmitTime = now;
            }

            if (attempts < maxAttempts) {
              this.pollInterval = setTimeout(poll, currentInterval * 1000);
            } else {
              reject(new Error(`Authentication timed out after ${actualExpiresIn}s while waiting for approval.`));
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
  private async storeToken(token: string, expiresIn: number, refreshToken?: string): Promise<void> {
    const expiresAt = Date.now() + expiresIn * 1000;
    await this.context.secrets.store("aep.authToken", token);
    await this.context.globalState.update("aep.tokenExpiresAt", expiresAt);

    // Store Auth0 refresh token for token refresh flow
    if (refreshToken) {
      await this.context.secrets.store("aep.auth0RefreshToken", refreshToken);
    } else {
      // Log warning if refresh token is missing (should have offline_access scope)
      console.warn(
        "Auth0 did not return refresh_token. Ensure offline_access scope is requested " +
        "and Refresh Token grant is enabled in Auth0 application settings."
      );
    }
  }

  /**
   * Get the current auth token if valid.
   * If token is expired, attempts to refresh using stored Auth0 refresh token.
   * If refresh fails, forces re-authentication.
   */
  async getToken(): Promise<string | undefined> {
    const expiresAt = this.context.globalState.get<number>("aep.tokenExpiresAt");
    if (expiresAt && Date.now() > expiresAt) {
      // Try to refresh before logging out
      const refreshed = await this.refreshSession();
      if (refreshed) {
        return refreshed;
      }

      // Refresh failed, force re-auth
      await this.logout();
      return undefined;
    }
    return await this.context.secrets.get("aep.authToken");
  }

  /**
   * Get the stored Auth0 refresh token for token refresh flow.
   */
  async getRefreshToken(): Promise<string | undefined> {
    return await this.context.secrets.get("aep.auth0RefreshToken");
  }

  /**
   * Attempt to refresh the expired AEP session using stored Auth0 refresh token.
   * Returns the new AEP session token if successful, undefined if refresh fails.
   */
  private async refreshSession(): Promise<string | undefined> {
    const refreshToken = await this.getRefreshToken();
    if (!refreshToken) {
      return undefined;
    }

    try {
      const response = await fetch(`${this.apiBaseUrl}/oauth/device/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        console.warn(`Token refresh failed: HTTP ${response.status}`);
        return undefined;
      }

      const data = (await response.json()) as TokenResponse;

      // Store new AEP session token and rotated refresh token (if provided)
      await this.storeToken(data.access_token, data.expires_in, data.refresh_token);

      console.log("Token refreshed successfully");
      return data.access_token;
    } catch (err) {
      console.error("Token refresh failed:", err);
      return undefined;
    }
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
    await this.context.secrets.delete("aep.auth0RefreshToken");
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
