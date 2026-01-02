import { AgentEvent } from './AgentEvent';

type Listener = (event: AgentEvent) => void;

export class AgentEventBus {
    private listeners: Set<Listener> = new Set();

    subscribe(listener: Listener) {
        this.listeners.add(listener);
    }

    unsubscribe(listener: Listener) {
        this.listeners.delete(listener);
    }

    emit(event: AgentEvent) {
        for (const listener of this.listeners) {
            try {
                listener(event);
            } catch (err) {
                // Keep the bus resilient; log and continue.
                console.warn('[NAVI][EventBus] listener threw', err);
            }
        }
    }
}
