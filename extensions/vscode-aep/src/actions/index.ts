/**
 * Actions Module - Dynamic Action Handling System
 *
 * This module provides a plugin-based action execution system.
 * Handlers are registered based on capabilities, not hardcoded types.
 */

export { ActionRegistry, ActionHandler, ActionContext, ActionResult, BaseActionHandler } from './ActionRegistry';
export { FileActionHandler } from './handlers/FileActionHandler';
export { CommandActionHandler } from './handlers/CommandActionHandler';
export { NotificationActionHandler } from './handlers/NotificationActionHandler';
export { NavigationActionHandler } from './handlers/NavigationActionHandler';

import { ActionRegistry } from './ActionRegistry';
import { FileActionHandler } from './handlers/FileActionHandler';
import { CommandActionHandler } from './handlers/CommandActionHandler';
import { NotificationActionHandler } from './handlers/NotificationActionHandler';
import { NavigationActionHandler } from './handlers/NavigationActionHandler';

/**
 * Create and configure the default action registry
 */
export function createDefaultActionRegistry(): ActionRegistry {
    const registry = new ActionRegistry();

    // Register all default handlers
    registry.register(new FileActionHandler());
    registry.register(new CommandActionHandler());
    registry.register(new NotificationActionHandler());
    registry.register(new NavigationActionHandler());

    console.log('[ActionRegistry] Initialized with default handlers');

    return registry;
}
