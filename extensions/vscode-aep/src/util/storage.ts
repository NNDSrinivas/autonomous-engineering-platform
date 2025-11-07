import * as vscode from 'vscode';
export class KV {
  constructor(private ctx: vscode.ExtensionContext) {}
  get<T>(k: string): T|undefined { return this.ctx.globalState.get(k) as T|undefined; }
  set<T>(k: string, v: T){ return this.ctx.globalState.update(k, v); }
}