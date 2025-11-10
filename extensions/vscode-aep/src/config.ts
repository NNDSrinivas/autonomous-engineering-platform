import * as vscode from 'vscode';

type Config = {
  baseUrl: string;
  orgId: string;
  llm: string;
  portalUrl: string;
};

export function getConfig(): Config {
  const config = vscode.workspace.getConfiguration('aep');

  return {
    baseUrl: normalize(config.get<string>('baseUrl'), 'http://localhost:8000'),
    orgId: normalize(config.get<string>('orgId'), 'org-dev'),
    llm: normalize(config.get<string>('llm'), 'gpt-4o-mini'),
    portalUrl: normalize(config.get<string>('portalUrl'), 'https://portal.aep.navra.ai')
  };
}

function normalize(value: string | undefined, fallback: string): string {
  if (typeof value !== 'string' || value.trim().length === 0 || value === 'undefined') {
    return fallback;
  }

  return value.trim();
}