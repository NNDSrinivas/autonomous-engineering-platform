import * as vscode from 'vscode';
import { AEPClient } from './api/client';
import type { DeviceCodeToken } from './api/types';

export const DEVICE_POLL_MAX_ATTEMPTS = 90;
export const DEVICE_POLL_INTERVAL_MS = 2000;

export async function pollDeviceCode(
  client: AEPClient,
  deviceCode: string,
  output?: vscode.OutputChannel
): Promise<DeviceCodeToken> {
  // 90 attempts × 2 seconds interval = 180 seconds (3 minutes) total timeout for device authorization.
  let lastError: unknown;
  for (let attempt = 0; attempt < DEVICE_POLL_MAX_ATTEMPTS; attempt++) {
    try {
      const token = await client.pollDeviceCode(deviceCode);
      output?.appendLine('Received access token from device flow.');
      return token;
    } catch (error: any) {
      const message = typeof error?.message === 'string' ? error.message : String(error);
      if (isPendingDeviceAuthorization(message)) {
        await delay(DEVICE_POLL_INTERVAL_MS);
        continue;
      }

      lastError = error;
      break;
    }
  }

  if (lastError) {
    throw lastError;
  }

  throw new Error('Timed out waiting for device authorization.');
}

function isPendingDeviceAuthorization(message: string): boolean {
  const normalized = message.toLowerCase();
  return normalized.includes('428') || normalized.includes('authorization_pending');
}

async function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
