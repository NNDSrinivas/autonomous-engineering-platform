import * as vscode from 'vscode';
import { AuthService } from './AuthService';
import { ApiClient } from './ApiClient';

export class StatusBarManager {
    private statusBarItem: vscode.StatusBarItem;

    constructor(
        private context: vscode.ExtensionContext,
        private authService: AuthService,
        private apiClient: ApiClient
    ) {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );

        this.context.subscriptions.push(this.statusBarItem);
        this.setupStatusBar();
    }

    private setupStatusBar(): void {
        this.statusBarItem.command = 'aep.status';
        this.updateStatus();

        // Update status when auth state changes
        this.authService.onAuthStateChanged(async () => {
            await this.updateStatus();
        });
    }

    private async updateStatus(): Promise<void> {
        const isAuthenticated = await this.authService.isAuthenticated();

        if (isAuthenticated) {
            this.statusBarItem.text = "$(check) AEP Connected";
            this.statusBarItem.tooltip = "Autonomous Engineering Platform - Connected";
            this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
        } else {
            this.statusBarItem.text = "$(x) AEP";
            this.statusBarItem.tooltip = "Autonomous Engineering Platform - Not Connected";
            this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        }

        this.statusBarItem.show();
    }

    public show(): void {
        this.statusBarItem.show();
    }

    public hide(): void {
        this.statusBarItem.hide();
    }

    public updateWithProgress(message: string): void {
        this.statusBarItem.text = `$(sync~spin) ${message}`;
        this.statusBarItem.tooltip = message;
    }

    public updateWithError(message: string): void {
        this.statusBarItem.text = `$(error) ${message}`;
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');

        // Reset after 5 seconds
        setTimeout(() => {
            this.updateStatus();
        }, 5000);
    }

    public dispose(): void {
        this.statusBarItem.dispose();
    }
}