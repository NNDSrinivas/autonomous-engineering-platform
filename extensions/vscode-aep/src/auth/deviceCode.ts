import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { KV } from '../util/storage';

export async function ensureAuth(ctx: vscode.ExtensionContext, client: AEPClient){
  const kv = new KV(ctx);
  let token = kv.get<string>('aep.token');
  if (token) { client.setToken(token); return; }

  const pick = await vscode.window.showQuickPick([
    { label: 'Device Code', description: 'Open browser and paste code' }
  ], { placeHolder: 'Choose sign-in method' });
  if (!pick) return;

  const flow = await client.startDeviceCode();
  await vscode.env.openExternal(vscode.Uri.parse(flow.verification_uri_complete || flow.verification_uri));
  // Show user code for manual entry if needed
  await vscode.window.showInputBox({ 
    prompt: 'Device code (pre-filled, press Enter to continue)', 
    value: flow.user_code,
    ignoreFocusOut: true 
  });
  const tok = await client.pollDeviceCode(flow.device_code);
  await kv.set('aep.token', tok.access_token);
  client.setToken(tok.access_token);
}