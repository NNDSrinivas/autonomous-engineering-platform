import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { pollDeviceCode } from '../deviceFlow';
import { KV } from '../util/storage';

export async function ensureAuth(ctx: vscode.ExtensionContext, client: AEPClient){
  const kv = new KV(ctx);
  let token = kv.get<string>('aep.token');
  if (token) { 
    client.setToken(token); 
    // Verify token is still valid by trying to fetch issues
    try {
      await client.listMyJiraIssues();
      return; // Token is valid
    } catch {
      // Token expired, remove it and continue with auth flow
      await kv.set('aep.token', null);
    }
  }

  const pick = await vscode.window.showQuickPick([
    { label: 'Device Code', description: 'Open browser and paste code' },
    { label: 'Cancel', description: 'Skip authentication for now' }
  ], { placeHolder: 'Choose sign-in method' });
  
  if (!pick || pick.label === 'Cancel') {
    throw new Error('Authentication cancelled by user');
  }

  try {
    const flow = await client.startDeviceCode();
    if (!flow.device_code) {
      throw new Error('Device authorization response was missing a device code.');
    }

    const verificationUri = flow.verification_uri_complete || flow.verification_uri;
    if (!verificationUri) {
      throw new Error('Device authorization response was missing a verification URL.');
    }

    await vscode.env.openExternal(vscode.Uri.parse(verificationUri));
    
    // Show user code for manual entry if needed
    const userInput = await vscode.window.showInputBox({ 
      prompt: 'Device code (pre-filled, press Enter to continue)', 
      value: flow.user_code,
      ignoreFocusOut: true 
    });
    
    if (!userInput) {
      throw new Error('Authentication cancelled by user');
    }
    
    const tok = await pollDeviceCode(client, flow.device_code);
    await kv.set('aep.token', tok.access_token);
    client.setToken(tok.access_token);

  } catch (error) {
    console.error('Authentication error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    throw new Error(`Authentication failed: ${errorMessage}`);
  }
}