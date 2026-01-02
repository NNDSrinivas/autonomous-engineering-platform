import { vscode } from '../types';

export function useVSCodeAPI() {
  // Use the singleton VS Code API instance to avoid multiple acquisitions
  return {
    postMessage: (msg: any) => vscode.postMessage(msg),
    getState: () => vscode.getState(),
    setState: (state: any) => vscode.setState(state)
  };
}