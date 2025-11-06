import * as vscode from 'vscode';
export function getConfig(){
  const c = vscode.workspace.getConfiguration('aep');
  return {
    baseUrl: String(c.get('baseUrl')),
    orgId: String(c.get('orgId')),
    llm: String(c.get('llm')),
    portalUrl: String(c.get('portalUrl'))
  };
}