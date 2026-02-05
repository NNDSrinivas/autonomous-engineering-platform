import { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Loader2, 
  AlertTriangle,
  GitBranch,
  Code,
  GitPullRequest,
  Link,
  MessageSquare,
  RotateCcw,
  ChevronRight,
  Zap,
  SkipForward
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { ScrollArea } from '../ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { useEndToEndWorkflow, WorkflowPhase } from '../../hooks/useEndToEndWorkflow';
import { useWorkflowHistory } from '../../hooks/useWorkflowHistory';
import { cn } from '../../lib/utils';
import type { JiraTask } from '../../types';

const phaseIcons: Record<WorkflowPhase, React.ReactNode> = {
  idle: <Clock className="h-4 w-4" />,
  start_task: <Play className="h-4 w-4" />,
  create_branch: <GitBranch className="h-4 w-4" />,
  implement_code: <Code className="h-4 w-4" />,
  create_pr: <GitPullRequest className="h-4 w-4" />,
  link_jira: <Link className="h-4 w-4" />,
  post_slack: <MessageSquare className="h-4 w-4" />,
  completed: <CheckCircle2 className="h-4 w-4" />,
  failed: <XCircle className="h-4 w-4" />,
};

const phaseOrder: WorkflowPhase[] = [
  'start_task',
  'create_branch',
  'implement_code',
  'create_pr',
  'link_jira',
  'post_slack',
];

export interface EndToEndWorkflowPanelProps {
  task: JiraTask;
  owner?: string;
  repo?: string;
  templateId?: string | null;
  templateName?: string | null;
  onClose?: () => void;
  className?: string;
}

export function EndToEndWorkflowPanel({ 
  task, 
  owner = 'organization', 
  repo = 'repository',
  templateId = null,
  templateName = null,
  onClose,
  className 
}: EndToEndWorkflowPanelProps) {
  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const workflowHistoryIdRef = useRef<string | null>(null);
  
  const {
    state,
    startTask,
    approve,
    reject,
    reset,
    getPhaseInfo,
    isLoading,
  } = useEndToEndWorkflow({ owner, repo });
  
  const {
    startWorkflowEntry,
    updateWorkflowProgress,
    completeWorkflow: completeWorkflowHistory,
  } = useWorkflowHistory();

  // Track workflow completion and record to history
  useEffect(() => {
    const recordCompletion = async () => {
      if (workflowHistoryIdRef.current && (state.currentPhase === 'completed' || state.currentPhase === 'failed')) {
        await completeWorkflowHistory(
          workflowHistoryIdRef.current,
          state.currentPhase === 'completed' ? 'completed' : 'failed',
          state.results,
          state.error || undefined
        );
        workflowHistoryIdRef.current = null;
      }
    };
    recordCompletion();
  }, [state.currentPhase, state.results, state.error, completeWorkflowHistory]);

  // Update progress when phases change
  useEffect(() => {
    const updateProgress = async () => {
      if (workflowHistoryIdRef.current && state.currentPhase !== 'idle' && state.currentPhase !== 'completed' && state.currentPhase !== 'failed') {
        const completedPhases = phaseOrder.filter((phase, idx) => idx < phaseOrder.indexOf(state.currentPhase));
        await updateWorkflowProgress(workflowHistoryIdRef.current, {
          phasesCompleted: completedPhases,
          branchName: state.branchName,
          prUrl: state.prUrl,
          prNumber: state.prNumber,
        });
      }
    };
    updateProgress();
  }, [state.currentPhase, state.branchName, state.prUrl, state.prNumber, updateWorkflowProgress]);

  // Calculate progress
  const currentPhaseIndex = phaseOrder.indexOf(state.currentPhase);
  const progress = state.currentPhase === 'completed' 
    ? 100 
    : state.currentPhase === 'failed' || state.currentPhase === 'idle'
    ? 0
    : ((currentPhaseIndex + 1) / phaseOrder.length) * 100;

  // Get phase status for styling
  const getPhaseStatus = (phase: WorkflowPhase) => {
    const phaseIdx = phaseOrder.indexOf(phase);
    const currentIdx = phaseOrder.indexOf(state.currentPhase);
    
    if (state.currentPhase === 'completed') return 'completed';
    if (state.currentPhase === 'failed') {
      if (phaseIdx <= currentIdx) return 'failed';
      return 'pending';
    }
    if (phaseIdx < currentIdx) return 'completed';
    if (phaseIdx === currentIdx) {
      if (state.awaitingApproval) return 'awaiting';
      return 'executing';
    }
    return 'pending';
  };

  // Handle approval dialog
  const handleApprovalClick = () => {
    if (state.awaitingApproval) {
      setApprovalDialogOpen(true);
    }
  };

  const handleApprove = async () => {
    setApprovalDialogOpen(false);
    await approve();
  };

  const handleReject = () => {
    setApprovalDialogOpen(false);
    reject(true); // Skip to next
  };

  const handleStart = async () => {
    // Create workflow history entry
    const historyId = await startWorkflowEntry(
      task.id,
      task.key,
      task.title,
      templateId,
      templateName
    );
    if (historyId) {
      workflowHistoryIdRef.current = historyId;
    }
    startTask(task);
  };

  return (
    <>
      <Card className={cn("border-border/50", className)}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                End-to-End Workflow
              </CardTitle>
              <CardDescription className="mt-1">
                {task.key}: {task.title}
              </CardDescription>
            </div>
            <Badge 
              variant="outline" 
              className={cn(
                "text-[10px] uppercase",
                state.currentPhase === 'completed' && 'bg-status-success/20 text-status-success border-status-success/30',
                state.currentPhase === 'failed' && 'bg-status-error/20 text-status-error border-status-error/30',
                state.awaitingApproval && 'bg-status-warning/20 text-status-warning border-status-warning/30',
                state.currentPhase !== 'completed' && state.currentPhase !== 'failed' && !state.awaitingApproval && state.currentPhase !== 'idle' && 'bg-primary/20 text-primary border-primary/30',
              )}
            >
              {state.awaitingApproval ? 'Awaiting Approval' : state.currentPhase.replace(/_/g, ' ')}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Progress bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>

          {/* Phase list */}
          <ScrollArea className="h-[280px] pr-4">
            <div className="space-y-2">
              {phaseOrder.map((phase) => {
                const info = getPhaseInfo(phase);
                const status = getPhaseStatus(phase);
                const result = state.results.find(r => r.phase === phase);
                
                return (
                  <div
                    key={phase}
                    className={cn(
                      "p-3 rounded-lg border transition-all",
                      status === 'executing' && 'border-primary bg-primary/5',
                      status === 'awaiting' && 'border-status-warning bg-status-warning/5',
                      status === 'completed' && 'border-status-success/30 bg-status-success/5',
                      status === 'failed' && 'border-status-error/30 bg-status-error/5',
                      status === 'pending' && 'border-border/50 opacity-60',
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "mt-0.5 h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0",
                        status === 'completed' && 'bg-status-success/20 text-status-success',
                        status === 'failed' && 'bg-status-error/20 text-status-error',
                        status === 'executing' && 'bg-primary/20 text-primary',
                        status === 'awaiting' && 'bg-status-warning/20 text-status-warning',
                        status === 'pending' && 'bg-secondary text-muted-foreground',
                      )}>
                        {status === 'executing' && !state.awaitingApproval ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : status === 'awaiting' ? (
                          <AlertTriangle className="h-4 w-4" />
                        ) : status === 'completed' ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : status === 'failed' ? (
                          <XCircle className="h-4 w-4" />
                        ) : (
                          phaseIcons[phase]
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{info.label}</span>
                          {status === 'awaiting' && (
                            <Badge variant="outline" className="text-[9px] px-1.5 bg-status-warning/20 text-status-warning border-status-warning/30">
                              Approval Required
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {info.description}
                        </p>
                        {result && (
                          <p className={cn(
                            "text-xs mt-1",
                            result.success ? 'text-status-success' : 'text-status-error'
                          )}>
                            {result.message}
                          </p>
                        )}
                      </div>
                      {status === 'awaiting' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={handleApprovalClick}
                          className="h-7 text-xs"
                        >
                          Review
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>

          {/* Control buttons */}
          <div className="flex items-center gap-2 pt-2 border-t border-border">
            {state.currentPhase === 'idle' && (
              <Button onClick={handleStart} className="gap-2 flex-1" disabled={isLoading}>
                <Play className="h-4 w-4" />
                Start Workflow
              </Button>
            )}
            
            {state.awaitingApproval && (
              <Button onClick={handleApprovalClick} className="gap-2 flex-1">
                <AlertTriangle className="h-4 w-4" />
                Review & Approve
              </Button>
            )}

            {(state.currentPhase === 'completed' || state.currentPhase === 'failed') && (
              <>
                <Button onClick={reset} variant="outline" className="gap-2 flex-1">
                  <RotateCcw className="h-4 w-4" />
                  Reset
                </Button>
                {onClose && (
                  <Button onClick={onClose} variant="default" className="gap-2">
                    Done
                  </Button>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Approval Dialog */}
      <Dialog open={approvalDialogOpen} onOpenChange={setApprovalDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-status-warning" />
              Approval Required
            </DialogTitle>
            <DialogDescription>
              NAVI needs your approval to proceed with this step
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="p-4 rounded-lg bg-secondary/50 space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  {phaseIcons[state.currentPhase]}
                </div>
                <div>
                  <h4 className="font-medium">{getPhaseInfo(state.currentPhase).label}</h4>
                  <p className="text-xs text-muted-foreground">
                    {getPhaseInfo(state.currentPhase).description}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] bg-status-warning/20 text-status-warning border-status-warning/30">
                Medium Risk
              </Badge>
              <span className="text-xs text-muted-foreground">
                Step {phaseOrder.indexOf(state.currentPhase) + 1} of {phaseOrder.length}
              </span>
            </div>

            <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 border border-border">
              <AlertTriangle className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground">
                This action will make changes to your repository and external services.
                Please review before approving.
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={handleReject} className="gap-2">
              <SkipForward className="h-4 w-4" />
              Skip
            </Button>
            <Button onClick={handleApprove} className="gap-2" disabled={isLoading}>
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              Approve & Execute
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
