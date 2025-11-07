import * as vscode from 'vscode';
import { AEPClient } from '../api/client';

export class Approvals {
  constructor(private ctx: vscode.ExtensionContext, private client: AEPClient){}
  private selected: any | null = null;

  set(step: any){ this.selected = step; }
  async approve(step: any){ this.selected = step; await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Approving step…' }, async ()=>{}); }
  async reject(step: any){ this.selected = step; vscode.window.showInformationMessage('Step rejected'); }
  async approveSelected(){ if(this.selected) await this.approve(this.selected); }
  async rejectSelected(){ if(this.selected) await this.reject(this.selected); }
}