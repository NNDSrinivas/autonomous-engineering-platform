import { useState, useCallback } from 'react';

export type WorkflowPhase = 
  | 'idle'
  | 'start_task'
  | 'create_branch'
  | 'implement_code'
  | 'create_pr'
  | 'link_jira'
  | 'post_slack'
  | 'completed'
  | 'failed';

export interface WorkflowResult {
  phase: WorkflowPhase;
  success: boolean;
  message: string;
  data?: any;
}

export interface WorkflowState {
  currentPhase: WorkflowPhase;
  awaitingApproval: boolean;
  results: WorkflowResult[];
  branchName?: string;
  prUrl?: string;
  prNumber?: number;
  error?: string;
}

export interface JiraTask {
  id: string;
  key: string;
  title: string;
  description?: string;
}

interface UseEndToEndWorkflowOptions {
  owner: string;
  repo: string;
}

export const useEndToEndWorkflow = ({ owner, repo }: UseEndToEndWorkflowOptions) => {
  const [state, setState] = useState<WorkflowState>({
    currentPhase: 'idle',
    awaitingApproval: false,
    results: [],
  });
  const [isLoading, setIsLoading] = useState(false);

  const updateState = useCallback((updates: Partial<WorkflowState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  const addResult = useCallback((result: WorkflowResult) => {
    setState(prev => ({
      ...prev,
      results: [...prev.results, result]
    }));
  }, []);

  const getPhaseInfo = useCallback((phase: WorkflowPhase) => {
    const phaseInfoMap = {
      idle: { label: 'Ready to Start', description: 'Workflow is ready to begin' },
      start_task: { label: 'Initialize Task', description: 'Set up task context and environment' },
      create_branch: { label: 'Create Branch', description: 'Create a new git branch for this task' },
      implement_code: { label: 'Implement Solution', description: 'Write code changes to complete the task' },
      create_pr: { label: 'Create Pull Request', description: 'Submit changes for review' },
      link_jira: { label: 'Link to Jira', description: 'Associate PR with Jira ticket' },
      post_slack: { label: 'Notify Team', description: 'Send update to team Slack channel' },
      completed: { label: 'Completed', description: 'Workflow completed successfully' },
      failed: { label: 'Failed', description: 'Workflow encountered an error' },
    };
    return phaseInfoMap[phase] || { label: phase, description: '' };
  }, []);

  const startTask = useCallback(async (task: JiraTask) => {
    setIsLoading(true);
    updateState({ currentPhase: 'start_task', awaitingApproval: true });
    setIsLoading(false);
  }, [updateState]);

  const approve = useCallback(async () => {
    setIsLoading(true);
    const currentPhase = state.currentPhase;
    
    try {
      // Simulate API call for current phase
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      addResult({
        phase: currentPhase,
        success: true,
        message: `${getPhaseInfo(currentPhase).label} completed successfully`
      });

      // Move to next phase
      const phases: WorkflowPhase[] = [
        'start_task', 'create_branch', 'implement_code', 
        'create_pr', 'link_jira', 'post_slack'
      ];
      
      const currentIndex = phases.indexOf(currentPhase);
      if (currentIndex < phases.length - 1) {
        const nextPhase = phases[currentIndex + 1];
        updateState({ 
          currentPhase: nextPhase, 
          awaitingApproval: true,
          ...(nextPhase === 'create_branch' && { branchName: `feature/${Date.now()}` }),
          ...(nextPhase === 'create_pr' && { 
            prUrl: `https://github.com/${owner}/${repo}/pull/123`,
            prNumber: 123 
          })
        });
      } else {
        updateState({ 
          currentPhase: 'completed', 
          awaitingApproval: false 
        });
      }
    } catch (error) {
      addResult({
        phase: currentPhase,
        success: false,
        message: `Failed to complete ${getPhaseInfo(currentPhase).label}`
      });
      updateState({ 
        currentPhase: 'failed', 
        awaitingApproval: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
    
    setIsLoading(false);
  }, [state.currentPhase, addResult, getPhaseInfo, updateState, owner, repo]);

  const reject = useCallback((skip = false) => {
    if (skip) {
      // Skip to next phase
      approve();
    } else {
      updateState({ 
        currentPhase: 'failed', 
        awaitingApproval: false,
        error: 'User rejected the workflow step'
      });
    }
  }, [approve, updateState]);

  const reset = useCallback(() => {
    setState({
      currentPhase: 'idle',
      awaitingApproval: false,
      results: [],
    });
  }, []);

  return {
    state,
    startTask,
    approve,
    reject,
    reset,
    getPhaseInfo,
    isLoading,
  };
};