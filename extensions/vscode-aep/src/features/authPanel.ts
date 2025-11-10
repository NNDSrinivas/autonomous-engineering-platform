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
      <div class="card">
        <div class="row"><span class="h">Welcome to AEP Agent</span></div>
        <p>Sign in to connect your IDE with AEP. New here? <a class="link" id="signup">Create an account</a>.</p>
        <div class="row">
          <vscode-button id="signin">Sign In</vscode-button>
          <vscode-button appearance="secondary" id="openPortal">Open Portal</vscode-button>
        </div>
      </div>
      <div class="card" id="device" style="display:none;">
        <div class="h">Device Code</div>
        <p>We opened your browser. If asked, paste this code:</p>
        <pre class="mono" id="code"></pre>
        <div class="row"><vscode-button id="copy">Copy Code</vscode-button></div>
      </div>`;

    view.webview.html = boilerplate(view.webview, this.ctx, body, ['base.css'], ['auth.js']);

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
