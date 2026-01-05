/**
 * VS Code Webview API utilities
 * 
 * Phase 4.0.4: Real VS Code webview communication
 * Handles postMessage sending and message listening
 */

// VS Code webview API
declare global {
  interface Window {
    acquireVsCodeApi?: () => {
      postMessage: (message: any) => void;
      getState: () => any;
      setState: (state: any) => void;
    };
  }
}

// Get the VS Code API instance
const vscode = typeof window !== 'undefined' && window.acquireVsCodeApi ? window.acquireVsCodeApi() : null;

/**
 * Send a message to the VS Code extension
 */
export function postMessage(message: any) {
  if (vscode) {
    console.log('📤 Sending to extension:', message);
    vscode.postMessage(message);
  } else {
    console.warn('⚠️ VS Code API not available, message not sent:', message);
  }
}

/**
 * Listen for messages from the VS Code extension
 * Returns an unsubscribe function
 */
export function onMessage(handler: (message: any) => void): () => void {
  if (typeof window === 'undefined') {
    return () => {}; // No-op for SSR
  }

  const messageHandler = (event: MessageEvent) => {
    console.log('📨 Received from extension:', event.data);
    handler(event.data);
  };

  window.addEventListener('message', messageHandler);
  
  // Return unsubscribe function
  return () => {
    window.removeEventListener('message', messageHandler);
  };
}

/**
 * Get persistent state from VS Code
 */
export function getState() {
  return vscode?.getState();
}

/**
 * Set persistent state in VS Code
 */
export function setState(state: any) {
  vscode?.setState(state);
}