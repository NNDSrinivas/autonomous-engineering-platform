import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { boilerplate } from '../webview/view';
import { pollDeviceCode } from '../deviceFlow';

export class AuthPanel implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;

  constructor(
    private readonly ctx: vscode.ExtensionContext,
    private readonly client: AEPClient,
    private readonly portalUrl: string,
    private readonly output: vscode.OutputChannel
  ) {}

  resolveWebviewView(view: vscode.WebviewView) {
    this.view = view;
    view.webview.options = { enableScripts: true };

    const body = `
      <div class="aep-shell">
        <section class="panel aurora hero">
          <div class="panel-header">
            <span class="badge badge-offline">Sign in required</span>
            <h1>Connect VS Code to AEP</h1>
            <p class="lead">Authenticate with your organization to unlock chat, planning, and automated code execution.</p>
          </div>
          <div class="panel-actions">
            <vscode-button id="signin" appearance="primary">Start sign-in</vscode-button>
            <vscode-button id="openPortal" appearance="secondary">Open Portal</vscode-button>
            <vscode-button id="signup" appearance="secondary">Create an account</vscode-button>
          </div>
        </section>

        <section class="module auth-status" id="device" data-visible="false" aria-hidden="true">
          <header>
            <div>
              <h2>Device code authentication</h2>
              <p>Follow the prompt in your browser. Enter the code below if requested.</p>
            </div>
          </header>
          <div class="code-display">
            <span id="code" class="code-value">••••••</span>
            <vscode-button id="copy" appearance="secondary">Copy code</vscode-button>
          </div>
          <p class="hint">We keep polling every few seconds until your login completes.</p>
        </section>
      </div>`;

    view.webview.html = boilerplate(view.webview, this.ctx, body, ['base.css', 'aurora.css'], ['auth.js']);

    view.webview.onDidReceiveMessage(async message => {
      try {
        if (message.type === 'open') {
          const targetUrl = message.url === 'portal:' ? this.portalUrl : message.url;
          if (targetUrl) {
            vscode.env.openExternal(vscode.Uri.parse(targetUrl));
          }
          return;
        }

        if (message.type === 'signin') {
          await this.handleSignIn(view);
          return;
        }
      } catch (error: any) {
        const messageText = error?.message ?? String(error);
        await this.client.clearToken();
        this.output.appendLine(`Authentication failed: ${messageText}`);
        vscode.window.showErrorMessage(`Authentication failed: ${messageText}`);
        view.webview.postMessage({ type: 'error', message: messageText });
      }
    });
  }

  private async handleSignIn(view: vscode.WebviewView) {
    this.output.appendLine('Starting authentication from Account panel.');
    const flow = await this.client.startDeviceCode();

    if (!flow.device_code) {
      throw new Error('Device authorization response was missing a device code.');
    }

    view.webview.postMessage({ type: 'flow', flow });

    const verificationUrl = flow.verification_uri_complete || flow.verification_uri;
    if (verificationUrl) {
      vscode.env.openExternal(vscode.Uri.parse(verificationUrl));
    }

    await pollDeviceCode(this.client, flow.device_code, this.output);
    view.webview.postMessage({ type: 'done' });
    vscode.window.showInformationMessage('Signed in to AEP successfully.');
  }
}
