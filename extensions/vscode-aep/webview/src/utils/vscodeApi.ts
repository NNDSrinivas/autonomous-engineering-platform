/**
 * VS Code webview API utilities.
 * Handles postMessage, message listeners, and clipboard helpers.
 */

export type VsCodeMessage = any;
type Listener = (message: VsCodeMessage) => void;

// Extend Window for the cached API instance (not redefining acquireVsCodeApi)
declare global {
  interface Window {
    __AEP_VSCODE_API__?: {
      postMessage: (message: unknown) => void;
      getState: () => unknown;
      setState: (state: unknown) => void;
    };
  }
}

const listeners = new Set<Listener>();

let vscode: {
  postMessage: (message: any) => void;
  getState: () => any;
  setState: (state: any) => void;
} | null = null;

if (typeof window !== "undefined") {
  if (window.__AEP_VSCODE_API__) {
    vscode = window.__AEP_VSCODE_API__;
  } else if (window.acquireVsCodeApi) {
    try {
      vscode = window.acquireVsCodeApi();
      window.__AEP_VSCODE_API__ = vscode;
    } catch (err) {
      console.error("[vscodeApi] acquireVsCodeApi failed", err);
      vscode = null;
    }
  }
}

export function hasVsCodeHost(): boolean {
  if (typeof window === "undefined") return false;
  const anyWindow = window as any;
  if (window.parent && window.parent !== window) return true;
  if (typeof anyWindow.acquireVsCodeApi === "function") return true;
  return false;
}

export function postMessage(message: VsCodeMessage) {
  if (typeof window === "undefined") return;
  try {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage(message, "*");
      return;
    }
    if (vscode) {
      vscode.postMessage(message);
      return;
    }
  } catch (err) {
    console.error("[vscodeApi] postMessage error", err);
  }
}

export function onMessage(listener: Listener): () => void {
  if (typeof window === "undefined") return () => undefined;
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let nextClipboardReqId = 1;
const pendingClipboardWrites = new Map<number, (success: boolean) => void>();
const pendingClipboardReads = new Map<number, (text: string | null) => void>();

export function writeClipboard(text: string): Promise<boolean> {
  const id = nextClipboardReqId++;
  return new Promise((resolve) => {
    pendingClipboardWrites.set(id, resolve);
    postMessage({ type: "clipboard.write", id, text });
  });
}

export function readClipboard(): Promise<string | null> {
  const id = nextClipboardReqId++;
  return new Promise((resolve) => {
    pendingClipboardReads.set(id, resolve);
    postMessage({ type: "clipboard.read", id });
  });
}

if (typeof window !== "undefined") {
  window.addEventListener("message", (event: MessageEvent) => {
    const data = event.data;
    if (!data || typeof data !== "object") return;

    if (data.type === "clipboard.write.result" && typeof data.id === "number") {
      const resolver = pendingClipboardWrites.get(data.id);
      if (resolver) {
        pendingClipboardWrites.delete(data.id);
        resolver(Boolean(data.success));
      }
      return;
    }

    if (data.type === "clipboard.read.result" && typeof data.id === "number") {
      const resolver = pendingClipboardReads.get(data.id);
      if (resolver) {
        pendingClipboardReads.delete(data.id);
        resolver(typeof data.text === "string" ? data.text : null);
      }
      return;
    }

    listeners.forEach((cb) => cb(data));
  });
}

export function getState() {
  return vscode?.getState();
}

export function setState(state: any) {
  vscode?.setState(state);
}
