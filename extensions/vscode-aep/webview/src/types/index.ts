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

// VS Code API singleton
export const vscode: VsCodeApi = (() => {
  if (typeof acquireVsCodeApi !== 'undefined') {
    return acquireVsCodeApi();
  }
  // Fallback for development
  return {
    postMessage: (message: any) => console.log('Mock VS Code API:', message),
    getState: () => null,
    setState: () => {}
  };
})();
