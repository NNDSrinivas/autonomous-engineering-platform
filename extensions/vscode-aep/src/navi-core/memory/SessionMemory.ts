import { Intent } from '../agent/Intent';
import { ExecutionPlan } from '../agent/AgentContext';

export class SessionMemory {
    private history: Array<{ intent: Intent; plan: ExecutionPlan }> = [];

    record(entry: { intent: Intent; plan: ExecutionPlan }) {
        this.history.push(entry);
    }

    last() {
        return this.history[this.history.length - 1];
    }
}
