import * as vscode from 'vscode';
import { AEPClient } from '../api/client';
import { pollDeviceCode } from '../deviceFlow';
export async function ensureAuth(_ctx: vscode.ExtensionContext, client: AEPClient) {
  await client.hydrateToken();

  if (client.hasToken()) {
    try {
      await client.listMyJiraIssues();
      return;
    } catch {
      await client.clearToken();
    }
  }

  const pick = await vscode.window.showQuickPick(
    [
      { label: 'Device Code', description: 'Open browser and paste code' },
      { label: 'Cancel', description: 'Skip authentication for now' }
    ],
    { placeHolder: 'Choose sign-in method' }
  );

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

    const userInput = await vscode.window.showInputBox({
      prompt: 'Device code (pre-filled, press Enter to continue)',
      value: flow.user_code,
      ignoreFocusOut: true
    });

    if (!userInput) {
      throw new Error('Authentication cancelled by user');
    }

    await pollDeviceCode(client, flow.device_code);
  } catch (error: unknown) {
    console.error('Authentication error:', error);
    const message = error instanceof Error ? error.message : 'Unknown error';
    throw new Error(`Authentication failed: ${message}`);
  }
}
