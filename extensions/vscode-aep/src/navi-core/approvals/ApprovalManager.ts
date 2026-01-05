import { ExecutionPlan } from '../agent/AgentContext';

export class ApprovalManager {
    // Phase 1.2: auto-approve while preserving interface
    async request(_plan: ExecutionPlan): Promise<boolean> {
        return true;
    }
}
