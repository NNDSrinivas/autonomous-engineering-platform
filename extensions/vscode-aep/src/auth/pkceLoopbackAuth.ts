import * as vscode from "vscode";
import * as http from "http";
import * as crypto from "crypto";
import { URL } from "url";

interface PKCEAuthConfig {
  auth0Domain: string;
  clientId: string;
  audience: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  id_token?: string;
}

interface UserInfo {
  sub: string;
  name?: string;
  email?: string;
  picture?: string;
  org?: string;
  roles?: string[];
}

export class PKCELoopbackAuthService {
  private readonly loopbackHost = "127.0.0.1";
  private readonly loopbackPort = 4312;
  private readonly redirectUri: string;
  private readonly auth0Domain: string;
  private readonly clientId: string;
  private readonly audience: string;
  private readonly context: vscode.ExtensionContext;

  private server?: http.Server;
  private refreshTimer?: NodeJS.Timeout;

  constructor(context: vscode.ExtensionContext, config: PKCEAuthConfig) {
    this.context = context;
    this.auth0Domain = config.auth0Domain;
    this.clientId = config.clientId;
    this.audience = config.audience;
    this.redirectUri = `http://${this.loopbackHost}:${this.loopbackPort}/callback`;
  }

  /**
   * Generate base64url-encoded string (for PKCE)
   */
  private base64Url(buffer: Buffer): string {
    return buffer
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=/g, "");
  }

  /**
   * Start the local HTTP server to capture OAuth callback
   */
  private async startLoopbackServer(): Promise<{ code: string; state: string }> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.stopLoopbackServer();
        reject(new Error("Login timed out after 2 minutes"));
      }, 120000); // 2 minute timeout

      this.server = http.createServer((req, res) => {
        const url = new URL(req.url || "", this.redirectUri);

        if (url.pathname === "/callback") {
          const code = url.searchParams.get("code");
          const state = url.searchParams.get("state");
          const error = url.searchParams.get("error");
          const errorDescription = url.searchParams.get("error_description");

          clearTimeout(timeout);

          if (error) {
            res.writeHead(400, { "Content-Type": "text/html" });
            res.end(`
              <!DOCTYPE html>
              <html>
                <head>
                  <meta charset="utf-8">
                  <title>Sign in failed</title>
                  <style>
                    body {
                      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      height: 100vh;
                      margin: 0;
                      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white;
                    }
                    .container {
                      text-align: center;
                      padding: 2rem;
                      background: rgba(255, 255, 255, 0.1);
                      border-radius: 16px;
                      backdrop-filter: blur(10px);
                    }
                    h1 { margin: 0 0 1rem 0; }
                    p { margin: 0.5rem 0; opacity: 0.9; }
                  </style>
                </head>
                <body>
                  <div class="container">
                    <h1>❌ Sign in failed</h1>
                    <p>${this.escapeHtml(errorDescription || error)}</p>
                    <p style="margin-top: 1.5rem; font-size: 0.9rem;">You can close this tab and try again.</p>
                  </div>
                </body>
              </html>
            `);
            this.stopLoopbackServer();
            reject(new Error(errorDescription || error));
            return;
          }

          if (!code || !state) {
            res.writeHead(400, { "Content-Type": "text/html" });
            res.end(`
              <!DOCTYPE html>
              <html>
                <head>
                  <meta charset="utf-8">
                  <title>Invalid callback</title>
                </head>
                <body>
                  <h1>Invalid callback</h1>
                  <p>Missing code or state parameter</p>
                </body>
              </html>
            `);
            this.stopLoopbackServer();
            reject(new Error("Missing code or state parameter"));
            return;
          }

          // Return success page
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(`
            <!DOCTYPE html>
            <html>
              <head>
                <meta charset="utf-8">
                <title>Signed in</title>
                <style>
                  body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                  }
                  .container {
                    text-align: center;
                    padding: 2rem;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    backdrop-filter: blur(10px);
                  }
                  .checkmark {
                    width: 80px;
                    height: 80px;
                    margin: 0 auto 1.5rem;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.2);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 3rem;
                  }
                  h1 { margin: 0 0 0.5rem 0; }
                  p { margin: 0.5rem 0; opacity: 0.9; }
                </style>
              </head>
              <body>
                <div class="container">
                  <div class="checkmark">✓</div>
                  <h1>Signed in successfully</h1>
                  <p id="message">This tab will close automatically...</p>
                </div>
                <script>
                  // Attempt to auto-close after 2.5 seconds
                  setTimeout(() => {
                    window.close();
                    // If close fails (browser blocks it), update message
                    setTimeout(() => {
                      const msg = document.getElementById('message');
                      if (msg) msg.textContent = 'You can close this tab and return to VS Code';
                    }, 500);
                  }, 2500);
                </script>
              </body>
            </html>
          `);

          this.stopLoopbackServer();
          resolve({ code, state });
        } else {
          res.writeHead(404);
          res.end();
        }
      });

      this.server.listen(this.loopbackPort, this.loopbackHost, () => {
        console.log(`Loopback server listening on ${this.redirectUri}`);
      });

      this.server.on("error", (err) => {
        clearTimeout(timeout);
        reject(err);
      });
    });
  }

  /**
   * Stop the local HTTP server
   */
  private stopLoopbackServer(): void {
    if (this.server) {
      this.server.close();
      this.server = undefined;
    }
  }

  /**
   * Escape HTML to prevent XSS
   */
  private escapeHtml(text: string): string {
    const map: { [key: string]: string } = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  /**
   * Exchange authorization code for tokens
   */
  private async exchangeCodeForTokens(
    code: string,
    codeVerifier: string
  ): Promise<TokenResponse> {
    const response = await fetch(`${this.auth0Domain}/oauth/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        grant_type: "authorization_code",
        client_id: this.clientId,
        code,
        code_verifier: codeVerifier,
        redirect_uri: this.redirectUri,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Token exchange failed: ${error}`);
    }

    return response.json() as Promise<TokenResponse>;
  }

  /**
   * Refresh access token using refresh token
   */
  private async refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
    const response = await fetch(`${this.auth0Domain}/oauth/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        grant_type: "refresh_token",
        client_id: this.clientId,
        refresh_token: refreshToken,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Token refresh failed: ${error}`);
    }

    return response.json() as Promise<TokenResponse>;
  }

  /**
   * Get user info from Auth0
   */
  private async getUserInfo(accessToken: string): Promise<UserInfo> {
    const response = await fetch(`${this.auth0Domain}/userinfo`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to get user info: ${error}`);
    }

    return response.json() as Promise<UserInfo>;
  }

  /**
   * Schedule token refresh before expiry
   */
  private scheduleTokenRefresh(expiresIn: number): void {
    // Clear existing timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }

    // Refresh 60 seconds before expiry
    const refreshIn = Math.max(0, (expiresIn - 60) * 1000);

    this.refreshTimer = setTimeout(async () => {
      try {
        const refreshToken = await this.context.secrets.get("auth0_refresh_token");
        if (refreshToken) {
          const tokens = await this.refreshAccessToken(refreshToken);
          await this.storeTokens(tokens);
          this.scheduleTokenRefresh(tokens.expires_in);
        }
      } catch (error) {
        console.error("Auto-refresh failed:", error);
        vscode.window
          .showErrorMessage(
            "Session expired. Please sign in again.",
            "Sign in"
          )
          .then((action) => {
            if (action === "Sign in") {
              vscode.commands.executeCommand("aep.signIn");
            }
          });
      }
    }, refreshIn);
  }

  /**
   * Store tokens securely
   */
  private async storeTokens(tokens: TokenResponse): Promise<void> {
    await this.context.secrets.store("auth0_access_token", tokens.access_token);

    if (tokens.refresh_token) {
      await this.context.secrets.store("auth0_refresh_token", tokens.refresh_token);
    }

    if (tokens.id_token) {
      await this.context.secrets.store("auth0_id_token", tokens.id_token);
    }

    // Store expiry timestamp
    const expiryTime = Date.now() + tokens.expires_in * 1000;
    await this.context.secrets.store("auth0_token_expiry", expiryTime.toString());

    // Schedule refresh
    this.scheduleTokenRefresh(tokens.expires_in);
  }

  /**
   * Perform login with PKCE flow
   */
  public async login(): Promise<void> {
    try {
      // Generate PKCE values
      const codeVerifier = this.base64Url(crypto.randomBytes(32));
      const codeChallenge = this.base64Url(
        crypto.createHash("sha256").update(codeVerifier).digest()
      );
      const state = this.base64Url(crypto.randomBytes(24));

      // Start loopback server
      const callbackPromise = this.startLoopbackServer();

      // Build authorization URL
      const authorizeUrl = new URL(`${this.auth0Domain}/authorize`);
      authorizeUrl.searchParams.set("response_type", "code");
      authorizeUrl.searchParams.set("client_id", this.clientId);
      authorizeUrl.searchParams.set("redirect_uri", this.redirectUri);
      authorizeUrl.searchParams.set("scope", "openid profile email offline_access");
      authorizeUrl.searchParams.set("audience", this.audience);
      authorizeUrl.searchParams.set("code_challenge", codeChallenge);
      authorizeUrl.searchParams.set("code_challenge_method", "S256");
      authorizeUrl.searchParams.set("state", state);

      // Open browser
      await vscode.env.openExternal(vscode.Uri.parse(authorizeUrl.toString()));

      // Wait for callback
      const { code, state: returnedState } = await callbackPromise;

      // Validate state (CSRF protection)
      if (returnedState !== state) {
        throw new Error("State mismatch (possible CSRF attack)");
      }

      // Exchange code for tokens
      const tokens = await this.exchangeCodeForTokens(code, codeVerifier);

      // Store tokens
      await this.storeTokens(tokens);

      // Get user info
      const userInfo = await this.getUserInfo(tokens.access_token);

      // Show success message
      const userName = userInfo.name || userInfo.email || "User";
      vscode.window.showInformationMessage(`✓ Connected as ${userName}`);
    } catch (error) {
      this.stopLoopbackServer();
      throw error;
    }
  }

  /**
   * Get valid access token (with auto-refresh if needed)
   */
  public async getToken(): Promise<string | undefined> {
    const accessToken = await this.context.secrets.get("auth0_access_token");
    const expiryStr = await this.context.secrets.get("auth0_token_expiry");

    if (!accessToken) {
      return undefined;
    }

    // Check if token is expired or will expire soon (within 60 seconds)
    if (expiryStr) {
      const expiry = parseInt(expiryStr, 10);
      const now = Date.now();
      const expiresIn = (expiry - now) / 1000;

      if (expiresIn < 60) {
        // Token expired or expiring soon, refresh it
        const refreshToken = await this.context.secrets.get("auth0_refresh_token");
        if (refreshToken) {
          try {
            const tokens = await this.refreshAccessToken(refreshToken);
            await this.storeTokens(tokens);
            return tokens.access_token;
          } catch (error) {
            console.error("Token refresh failed:", error);
            // Clear invalid tokens
            await this.logout();
            return undefined;
          }
        }
      }
    }

    return accessToken;
  }

  /**
   * Check if user is authenticated
   */
  public async isAuthenticated(): Promise<boolean> {
    const token = await this.getToken();
    return !!token;
  }

  /**
   * Logout (clear tokens)
   */
  public async logout(): Promise<void> {
    await this.context.secrets.delete("auth0_access_token");
    await this.context.secrets.delete("auth0_refresh_token");
    await this.context.secrets.delete("auth0_id_token");
    await this.context.secrets.delete("auth0_token_expiry");

    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = undefined;
    }

    vscode.window.showInformationMessage("Signed out successfully");
  }

  /**
   * Get current user info
   */
  public async getCurrentUser(): Promise<UserInfo | undefined> {
    const token = await this.getToken();
    if (!token) {
      return undefined;
    }

    try {
      return await this.getUserInfo(token);
    } catch (error) {
      console.error("Failed to get user info:", error);
      return undefined;
    }
  }
}
