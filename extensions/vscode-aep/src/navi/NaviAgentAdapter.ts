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
import { collectDiffForFile, collectStagedDiffForFile } from '../navi-core/perception/RepoDiffDetailPerception';
import { DiagnosticsPerception } from '../navi-core/perception/DiagnosticsPerception';
import { DiagnosticClassifier } from '../navi-core/perception/DiagnosticClassifier';
import { FixProposalEngine } from '../navi-core/planning/FixProposalEngine';
import { exec as _exec } from 'child_process';
import { FixProposalEngine } from '../navi-core/planning/FixProposalEngine';
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

            // 3.5) Phase 1.3: Emit diff detail for each changed file
            emitEvent({ type: 'liveProgress', data: { step: 'Collecting diffs...', percentage: 50 } });

            // Emit diffs for unstaged files
            for (const file of diff.unstaged) {
                const fileDiff = await collectDiffForFile(workspaceRoot, file.path);
                emitEvent({
                    type: 'repo.diff.detail',
                    data: {
                        path: fileDiff.path,
                        additions: fileDiff.additions,
                        deletions: fileDiff.deletions,
                        diff: fileDiff.diff,
                        scope: 'unstaged'
                    }
                });
            }

            // Emit diffs for staged files
            for (const file of diff.staged) {
                const fileDiff = await collectStagedDiffForFile(workspaceRoot, file.path);
                emitEvent({
                    type: 'repo.diff.detail',
                    data: {
                        path: fileDiff.path,
                        additions: fileDiff.additions,
                        deletions: fileDiff.deletions,
                        diff: fileDiff.diff,
                        scope: 'staged'
                    }
                });
            }

            // Phase 1.3 STEP 1: Collect global diagnostics (all files in workspace)
            emitEvent({ type: 'liveProgress', data: { step: 'Scanning diagnostics...', percentage: 75 } });
            const globalDiagnostics = DiagnosticsPerception.collectWorkspaceDiagnostics();
            console.log('[NaviAgentAdapter] 📊 Global diagnostics collected:', globalDiagnostics.length);
            emitEvent({
                type: 'navi.agent.perception',
                data: {
                    diagnosticsCount: globalDiagnostics.length,
                    diagnostics: globalDiagnostics
                }
            });

            // Phase 1.3 STEP 2: Classify diagnostics (introduced vs preExisting)
            const changedFilesRel = [
                ...diff.unstaged.map(f => f.path),
                ...diff.staged.map(f => f.path)
            ];
            const classified = DiagnosticClassifier.classify(globalDiagnostics, workspaceRoot, changedFilesRel);
            const introducedCount = classified.filter(d => d.impact === 'introduced').length;
            const preExistingCount = classified.filter(d => d.impact === 'preExisting').length;
            emitEvent({
                type: 'navi.agent.classification',
                data: {
                    introducedCount,
                    preExistingCount
                }
            });

            // Phase 1.3 STEP 3: Build assessment summary and emit
            const errors = classified.filter(d => d.severity === 'error').length;
            const warnings = classified.filter(d => d.severity === 'warning').length;
            const filesAffected = new Set(classified.map(d => d.file)).size;

            // Phase 1.4: Scope-aware assessment (changed-files vs global)
            const changedFileDiags = classified.filter(d => d.impact === 'introduced');
            const globalDiagsCount = classified.length;
            const changedFileDiagsCount = changedFileDiags.length;
            const changedFileErrors = changedFileDiags.filter(d => d.severity === 'error').length;
            const changedFileWarnings = changedFileDiags.filter(d => d.severity === 'warning').length;

            emitEvent({
                type: 'navi.agent.assessment',
                data: {
                    // Phase 1.3 totals (for backward compat)
                    totalDiagnostics: classified.length,
                    introduced: introducedCount,
                    preExisting: preExistingCount,
                    errors,
                    warnings,
                    filesAffected,
                    // Phase 1.4: Scope breakdown (for consent decision)
                    scope: 'changed-files', // current scope
                    changedFileDiagsCount,
                    globalDiagsCount,
                    changedFileErrors,
                    changedFileWarnings,
                    hasGlobalIssuesOutsideChanged: preExistingCount > 0
                }
            });

            // Phase 1.5: Emit detailed diagnostic list (grouped by file, for visualization)
            const diagnosticsByFile = new Map<string, typeof classified>();
            for (const diag of classified) {
                const relativePath = diag.file.startsWith(workspaceRoot)
                    ? diag.file.slice(workspaceRoot.length + 1)
                    : diag.file;
                if (!diagnosticsByFile.has(relativePath)) {
                    diagnosticsByFile.set(relativePath, []);
                }
                diagnosticsByFile.get(relativePath)!.push(diag);
            }
            const diagnosticList = Array.from(diagnosticsByFile.entries()).map(([filePath, diags]) => ({
                filePath,
                diagnostics: diags.map(d => ({
                    severity: d.severity,
                    message: d.message,
                    line: d.line,
                    character: 0, // Not available in NaviDiagnostic; default to column 0
                    source: d.source || 'unknown',
                    impact: d.impact // 'introduced' or 'preExisting'
                }))
            }));
            emitEvent({
                type: 'navi.diagnostics.detailed',
                data: { files: diagnosticList }
            });

            // Phase 2.0 STEP 1: Translate diagnostics -> fix proposals (read-only, no UI changes required)
            const fixProposals = FixProposalEngine.generate(classified);
            console.log('[NaviAgentAdapter] 🛠 Fix proposals generated:', fixProposals.length);
            // Group proposals by file for downstream visualization (Phase 2.0 Step 2)
            const proposalsByFile = new Map<string, typeof fixProposals>();
            for (const p of fixProposals) {
                const rel = p.filePath.startsWith(workspaceRoot)
                    ? p.filePath.slice(workspaceRoot.length + 1)
                    : p.filePath;
                if (!proposalsByFile.has(rel)) proposalsByFile.set(rel, []);
                proposalsByFile.get(rel)!.push(p);
            }
            emitEvent({
                type: 'navi.fix.proposals',
                data: {
                    files: Array.from(proposalsByFile.entries()).map(([filePath, proposals]) => ({ filePath, proposals }))
                }
            });

            // Phase 2.0: Generate fix proposals (read-only, no execution)
            const proposals = FixProposalEngine.generate(classified);
            const proposalsByFile = new Map<string, typeof proposals>();
            for (const p of proposals) {
                const relativePath = p.filePath.startsWith(workspaceRoot)
                    ? p.filePath.slice(workspaceRoot.length + 1)
                    : p.filePath;
                if (!proposalsByFile.has(relativePath)) proposalsByFile.set(relativePath, []);
                proposalsByFile.get(relativePath)!.push(p);
            }
            const proposalList = Array.from(proposalsByFile.entries()).map(([filePath, items]) => ({
                filePath,
                proposals: items.map(p => ({
                    id: p.id,
                    line: p.line,
                    severity: p.severity,
                    issue: p.issue,
                    rootCause: p.rootCause,
                    suggestedChange: p.suggestedChange,
                    confidence: p.confidence,
                    impact: p.impact,
                    canAutoFixLater: p.canAutoFixLater,
                    source: p.source || 'unknown',
                }))
            }));
            emitEvent({ type: 'navi.fix.proposals', data: { files: proposalList } });

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
