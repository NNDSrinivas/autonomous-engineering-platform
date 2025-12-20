export function useVSCodeAPI() {
  // VS Code injects this global into the webview
  // @ts-ignore
  const vscode = acquireVsCodeApi();

  return {
    postMessage: (msg: any) => vscode.postMessage(msg),
    getState: () => vscode.getState(),
    setState: (state: any) => vscode.setState(state)
  };
}