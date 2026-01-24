/// <reference types="vite/client" />

/**
 * Global type declarations for the VS Code webview
 */

// VS Code API types
interface VSCodeAPI {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

// Extend Window interface
declare global {
  interface Window {
    vscode?: VSCodeAPI;
    acquireVsCodeApi?: () => VSCodeAPI;
  }

  // Extend ImportMeta for Vite environment variables
  interface ImportMetaEnv {
    readonly VITE_SUPABASE_URL?: string;
    readonly VITE_SUPABASE_ANON_KEY?: string;
    readonly VITE_API_URL?: string;
    readonly VITE_ORG_ID?: string;
    readonly VITE_USER_ID?: string;
    readonly DEV?: boolean;
    readonly PROD?: boolean;
    readonly MODE?: string;
    readonly BASE_URL?: string;
    readonly SSR?: boolean;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

export {};
