export type AgentEvent =
    | { type: 'perceptionComplete'; context: any }
    | { type: 'intentDetected'; intent: string; confidence: number }
    | { type: 'planCreated'; plan: any }
    | { type: 'stepStart'; step: any }
    | { type: 'stepComplete'; step: any; result: any }
    | { type: 'aborted'; reason: string }
    | { type: 'done'; message: string };
