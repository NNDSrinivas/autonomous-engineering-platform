import { AgentLoop } from '../navi-core/agent/AgentLoop';
import { Perception } from '../navi-core/agent/Perception';
import { Planner } from '../navi-core/agent/Planner';
import { AgentEventBus } from '../navi-core/events/AgentEventBus';
import { ApprovalManager } from '../navi-core/approvals/ApprovalManager';
import { SessionMemory } from '../navi-core/memory/SessionMemory';
import { ExecutorRegistry } from '../navi-core/execution/ExecutorRegistry';
import { GitExecutor } from '../navi-core/execution/GitExecutor';
import { DiagnosticExecutor } from '../navi-core/execution/DiagnosticExecutor';
import { collectRepoDiff } from '../navi-core/perception/RepoDiffPerception';
import { exec as _exec } from 'child_process';
import { promisify } from 'util';

const exec = promisify(_exec);

export async function runNaviAgent({
    workspaceRoot,
    userInput,
    emitEvent
}: {
    workspaceRoot: string;
    userInput: string;
    emitEvent: (e: any) => void;
}) {
    // Check if this is a review command
    const isReviewCommand = /(review\s+working\s+tree|review\s+changes|scan\s+repo|analyze\s+repo|review\s+repo|review\s+my\s+working)/i.test(userInput);

    if (isReviewCommand) {
        // Phase 1.2 CORRECT: Emit authoritative repo diff summary (single source of truth)
        try {
            // 1) Verify git repo
            console.log('[NaviAgentAdapter] 🔥 VERSION CHECK: Using NEW branch-based comparison code (v2.0)');
            emitEvent({ type: 'liveProgress', data: { step: 'Verifying Git repository...', percentage: 5 } });
            await exec(`git -C "${workspaceRoot}" rev-parse --is-inside-work-tree`);

            // 2) Collect REAL repo diff (single source of truth)
            emitEvent({ type: 'liveProgress', data: { step: 'Analyzing working tree...', percentage: 15 } });
            const diff = await collectRepoDiff(workspaceRoot);

            // 3) Emit authoritative repo diff summary event
            console.log('[NaviAgentAdapter] ✅ Emitting repo.diff.summary with real git data');
            emitEvent({
                type: 'repo.diff.summary',
                data: {
                    base: diff.base,
                    unstagedCount: diff.unstagedCount,
                    stagedCount: diff.stagedCount,
                    unstagedFiles: diff.unstaged,
                    stagedFiles: diff.staged,
                    totalChanges: diff.unstaged.length + diff.staged.length
                }
            });

            // 4) Signal completion
            emitEvent({ type: 'liveProgress', data: { step: 'Analysis complete', percentage: 100 } });
            emitEvent({ type: 'done', data: {} });
            return;
        } catch (err) {
            console.error('[NaviAgentAdapter] ❌ Repo diff analysis failed:', err);
            emitEvent({ 
                type: 'error', 
                data: { message: `Failed to analyze working tree: ${err instanceof Error ? err.message : String(err)}` } 
            });
            return;
        }
    }

    // Otherwise use local agent loop
    const events = new AgentEventBus();
    events.subscribe(emitEvent);

    const agent = new AgentLoop(
        new Perception(workspaceRoot),
        new Planner(),
        new ExecutorRegistry([
            ['git', new GitExecutor()],
            ['diagnostics', new DiagnosticExecutor()]
        ]),
        new ApprovalManager(),
        events,
        new SessionMemory()
    );

    await agent.run(userInput);
}
