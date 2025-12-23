export interface ReviewEntry {
  path: string;
  line?: number;
  severity: 'error' | 'warning' | 'info';
  category: string;
  summary: string;
  description?: string;
  suggestion?: string;
  diff?: {
    before: string;
    after: string;
  };
}

export interface AutoFixResult {
  success: boolean;
  message: string;
  applied?: boolean;
}

// VS Code API interface
interface VsCodeApi {
  postMessage: (message: any) => void;
  getState: () => any;
  setState: (state: any) => void;
}

declare global {
  function acquireVsCodeApi(): VsCodeApi;
}

// VS Code API singleton - ensure it's only acquired once
let vsCodeApiInstance: VsCodeApi | null = null;

export const vscode: VsCodeApi = (() => {
  if (vsCodeApiInstance) {
    return vsCodeApiInstance;
  }

  if (typeof acquireVsCodeApi !== 'undefined') {
    try {
      vsCodeApiInstance = acquireVsCodeApi();
      return vsCodeApiInstance;
    } catch (error) {
      console.warn('Failed to acquire VS Code API, using fallback:', error);
    }
  }

  // Fallback for development or if acquisition fails
  const fallbackApi = {
    postMessage: (message: any) => console.log('Mock VS Code API:', message),
    getState: () => null,
    setState: () => { }
  };

  vsCodeApiInstance = fallbackApi;
  return fallbackApi;
})();
