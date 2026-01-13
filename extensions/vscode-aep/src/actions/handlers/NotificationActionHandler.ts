/**
 * Notification Action Handler
 * Handles actions that show notifications, messages, or UI feedback
 */

import * as vscode from 'vscode';
import { BaseActionHandler, ActionContext, ActionResult } from '../ActionRegistry';

export class NotificationActionHandler extends BaseActionHandler {
    constructor() {
        super('notifications', 70);
    }

    canHandle(action: any): boolean {
        // Can handle if action has message/notification fields
        return !!(
            action.message ||
            action.notification ||
            action.toast ||
            action.alert ||
            action.type === 'notify'
        );
    }

    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        const message = action.message || action.notification || action.toast || action.alert;
        const level = action.level || action.severity || 'info';
        const modal = action.modal === true;

        try {
            await this.showNotification(message, level, modal, action);

            return {
                success: true,
                message: `Notification shown: ${message}`
            };
        } catch (error: any) {
            return {
                success: false,
                error: error,
                message: `Failed to show notification: ${error.message}`
            };
        }
    }

    private async showNotification(
        message: string,
        level: string,
        modal: boolean,
        action: any
    ): Promise<void> {
        const options: vscode.MessageOptions = { modal };
        const actions = action.actions || [];

        let response: string | undefined;

        switch (level.toLowerCase()) {
            case 'error':
            case 'danger':
                response = await vscode.window.showErrorMessage(message, options, ...actions);
                break;

            case 'warning':
            case 'warn':
                response = await vscode.window.showWarningMessage(message, options, ...actions);
                break;

            case 'info':
            case 'information':
            default:
                response = await vscode.window.showInformationMessage(message, options, ...actions);
                break;
        }

        // If user clicked an action, could handle it here
        if (response && action.onAction) {
            console.log(`[NotificationHandler] User clicked: ${response}`);
        }
    }
}
