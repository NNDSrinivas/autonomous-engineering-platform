/**
 * Dynamic Action Registry System
 *
 * This provides a plugin-based approach to handling actions from the backend.
 * Instead of hardcoding action types, handlers are registered based on capabilities.
 *
 * Benefits:
 * - Backend can introduce new action types without extension changes
 * - Actions are self-describing based on their structure
 * - Easy to extend with new capabilities
 * - No tight coupling between backend and extension
 */

import * as vscode from 'vscode';

/**
 * Interface for action handlers
 */
export interface ActionHandler {
    /**
     * Unique identifier for this handler
     */
    readonly id: string;

    /**
     * Priority (higher = check first)
     */
    readonly priority: number;

    /**
     * Check if this handler can process the given action
     */
    canHandle(action: any): boolean;

    /**
     * Execute the action
     */
    execute(action: any, context: ActionContext): Promise<ActionResult>;
}

/**
 * Context provided to action handlers
 */
export interface ActionContext {
    workspaceRoot?: string;
    approvedViaChat?: boolean;
    postMessage?: (message: any) => void;
    showMessage?: (message: string) => void;
}

/**
 * Result of action execution
 */
export interface ActionResult {
    success: boolean;
    message?: string;
    data?: any;
    error?: Error;
}

/**
 * Registry for action handlers
 */
export class ActionRegistry {
    private handlers: ActionHandler[] = [];

    /**
     * Register an action handler
     */
    register(handler: ActionHandler): void {
        this.handlers.push(handler);
        // Sort by priority (highest first)
        this.handlers.sort((a, b) => b.priority - a.priority);
        console.log(`[ActionRegistry] Registered handler: ${handler.id} (priority: ${handler.priority})`);
    }

    /**
     * Unregister a handler
     */
    unregister(handlerId: string): void {
        const index = this.handlers.findIndex(h => h.id === handlerId);
        if (index !== -1) {
            this.handlers.splice(index, 1);
            console.log(`[ActionRegistry] Unregistered handler: ${handlerId}`);
        }
    }

    /**
     * Execute an action by finding the appropriate handler
     */
    async execute(action: any, context: ActionContext): Promise<ActionResult> {
        if (!action) {
            return {
                success: false,
                error: new Error('No action provided')
            };
        }

        // Find the first handler that can handle this action
        const handler = this.handlers.find(h => h.canHandle(action));

        if (!handler) {
            console.warn('[ActionRegistry] No handler found for action:', action);
            return {
                success: false,
                error: new Error(`No handler found for action type: ${action.type || 'unknown'}`)
            };
        }

        console.log(`[ActionRegistry] Executing action with handler: ${handler.id}`);

        try {
            return await handler.execute(action, context);
        } catch (error: any) {
            console.error(`[ActionRegistry] Handler ${handler.id} failed:`, error);
            return {
                success: false,
                error: error
            };
        }
    }

    /**
     * Get all registered handlers
     */
    getHandlers(): ReadonlyArray<ActionHandler> {
        return this.handlers;
    }

    /**
     * Get handler by ID
     */
    getHandler(id: string): ActionHandler | undefined {
        return this.handlers.find(h => h.id === id);
    }
}

/**
 * Base class for action handlers
 */
export abstract class BaseActionHandler implements ActionHandler {
    constructor(
        public readonly id: string,
        public readonly priority: number = 50
    ) {}

    abstract canHandle(action: any): boolean;
    abstract execute(action: any, context: ActionContext): Promise<ActionResult>;
}
