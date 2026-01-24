/**
 * Actions Module - Dynamic Action Handling System
 *
 * This module provides a plugin-based action execution system.
 * Handlers are registered based on capabilities, not hardcoded types.
 */

export { ActionRegistry, ActionHandler, ActionContext, ActionResult, BaseActionHandler, DiffStats } from './ActionRegistry';
export { FileActionHandler } from './handlers/FileActionHandler';
export { CommandActionHandler } from './handlers/CommandActionHandler';
export { NotificationActionHandler } from './handlers/NotificationActionHandler';
export { NavigationActionHandler } from './handlers/NavigationActionHandler';
export { PortActionHandler } from './handlers/PortActionHandler';
export { ToolActionHandler } from './handlers/ToolActionHandler';

import { ActionRegistry } from './ActionRegistry';
import { FileActionHandler } from './handlers/FileActionHandler';
import { CommandActionHandler } from './handlers/CommandActionHandler';
import { NotificationActionHandler } from './handlers/NotificationActionHandler';
import { NavigationActionHandler } from './handlers/NavigationActionHandler';
import { PortActionHandler } from './handlers/PortActionHandler';
import { ToolActionHandler } from './handlers/ToolActionHandler';

/**
 * Create and configure the default action registry
 */
export function createDefaultActionRegistry(): ActionRegistry {
    const registry = new ActionRegistry();

    // Register all default handlers
    // Priority order: Port (95) > Tool (85) > Command (90) > File > Others
    registry.register(new PortActionHandler());
    registry.register(new ToolActionHandler());
    registry.register(new FileActionHandler());
    registry.register(new CommandActionHandler());
    registry.register(new NotificationActionHandler());
    registry.register(new NavigationActionHandler());

    console.log('[ActionRegistry] Initialized with default handlers');

    return registry;
}
