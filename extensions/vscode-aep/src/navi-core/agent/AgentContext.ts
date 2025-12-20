export interface WorkspaceContext {
    repo: {
        root: string;
        branch: string;
    };
    diff: string;
    files: string[];
    diagnostics: Array<{ type: string; message: string }>;
    timestamp: number;
}

export interface PlanStep {
    executor: string;
    action: string;
}

export interface ExecutionPlan {
    goal: string;
    steps: PlanStep[];
}
