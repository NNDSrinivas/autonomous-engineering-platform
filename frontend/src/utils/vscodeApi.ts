// src/utils/vscodeApi.ts
/* Simple wrapper around VS Code webview messaging.
 * - postMessage(...) → send to extension host
 * - onMessage(cb)   → subscribe to messages from extension
 */

export type VsCodeMessage = any;
type Listener = (message: VsCodeMessage) => void;

const listeners = new Set<Listener>();

export function hasVsCodeHost(): boolean {
    if (typeof window === "undefined") return false;
    const anyWindow = window as any;

    // VS Code webview with iframe bridge: parent is the webview
    if (window.parent && window.parent !== window) {
        return true;
    }

    // Direct webview (no iframe) – dev / fallback
    if (typeof anyWindow.acquireVsCodeApi === "function") {
        return true;
    }

    return false;
}

export function postMessage(message: VsCodeMessage) {
    if (typeof window === 'undefined') return;

    try {
        // When running inside the iframe in the VS Code webview
        if (window.parent && window.parent !== window) {
            window.parent.postMessage(message, '*');
            return;
        }

        // When running directly in a webview without iframe (fallback / dev)
        const anyWindow = window as any;
        if (typeof anyWindow.acquireVsCodeApi === 'function') {
            const vscode = anyWindow.acquireVsCodeApi();
            vscode.postMessage(message);
            return;
        }

        // Plain browser dev: just log
        // eslint-disable-next-line no-console
        console.debug('[vscodeApi] postMessage (no VS Code host):', message);
    } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[vscodeApi] postMessage error', err);
    }
}

export function onMessage(listener: Listener): () => void {
    if (typeof window === 'undefined') {
        return () => undefined;
    }
    listeners.add(listener);
    return () => listeners.delete(listener);
}

/* ----- Clipboard RPC helper ----- */

let nextClipboardReqId = 1;
const pendingClipboardWrites = new Map<number, (success: boolean) => void>();
const pendingClipboardReads = new Map<number, (text: string | null) => void>();

export function writeClipboard(text: string): Promise<boolean> {
    const id = nextClipboardReqId++;
    return new Promise((resolve) => {
        pendingClipboardWrites.set(id, resolve);
        postMessage({
            type: 'clipboard.write',
            id,
            text,
        });
    });
}

// NEW: read from VS Code clipboard
export function readClipboard(): Promise<string | null> {
    const id = nextClipboardReqId++;
    return new Promise((resolve) => {
        pendingClipboardReads.set(id, resolve);
        postMessage({
            type: 'clipboard.read',
            id,
        });
    });
}

// One global handler that fans out to subscribers
if (typeof window !== 'undefined') {
    window.addEventListener('message', (event: MessageEvent) => {
        const data = event.data;
        if (!data || typeof data !== 'object') return;

        // Handle clipboard.write result
        if (data.type === 'clipboard.write.result' && typeof data.id === 'number') {
            const resolver = pendingClipboardWrites.get(data.id);
            if (resolver) {
                pendingClipboardWrites.delete(data.id);
                resolver(Boolean(data.success));
            }
            return;
        }

        // NEW: handle clipboard.read result
        if (data.type === 'clipboard.read.result' && typeof data.id === 'number') {
            const resolver = pendingClipboardReads.get(data.id);
            if (resolver) {
                pendingClipboardReads.delete(data.id);
                resolver(typeof data.text === 'string' ? data.text : null);
            }
            return;
        }

        listeners.forEach((cb) => cb(data));
    });
}
