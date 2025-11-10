import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { boilerplate } from '../webview/view';

export class AuthPanel implements vscode.WebviewViewProvider {
  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient, private portalUrl: string){}
  private view?: vscode.WebviewView;

  resolveWebviewView(view: vscode.WebviewView){
    this.view = view; view.webview.options = { enableScripts: true };
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

    view.webview.onDidReceiveMessage(async m => {
      try {
        if(m.type==='open') {
          const url = m.url === 'portal:' ? this.portalUrl : m.url;
          vscode.env.openExternal(vscode.Uri.parse(url));
        }
        if(m.type==='signin'){
          const flow = await this.client.startDeviceCode();
          view.webview.postMessage({ type:'flow', flow });
          vscode.env.openExternal(vscode.Uri.parse(flow.verification_uri_complete || flow.verification_uri));
          await this.client.pollDeviceCode(flow.device_code);
          view.webview.postMessage({ type:'done' });
          vscode.window.showInformationMessage('Signed in to AEP successfully.');
        }
      } catch (error: any) {
        const message = error?.message ?? String(error);
        vscode.window.showErrorMessage(`Authentication failed: ${message}`);
        view.webview.postMessage({ type:'error', message });
      }
    });
  }
}