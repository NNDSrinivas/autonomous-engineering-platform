import { useState, useCallback } from 'react';

export interface WorkflowHistoryEntry {
  id: string;
  taskId: string;
  taskKey: string;
  taskTitle: string;
  templateId?: string | null;
  templateName?: string | null;
  status: 'running' | 'completed' | 'failed';
  startedAt: Date;
  completedAt?: Date;
  phasesCompleted: string[];
  branchName?: string;
  prUrl?: string;
  prNumber?: number;
  results?: any[];
  error?: string;
}

export const useWorkflowHistory = () => {
  const [history, setHistory] = useState<WorkflowHistoryEntry[]>([]);

  const startWorkflowEntry = useCallback(async (
    taskId: string,
    taskKey: string,
    taskTitle: string,
    templateId?: string | null,
    templateName?: string | null
  ): Promise<string | null> => {
    try {
      const entry: WorkflowHistoryEntry = {
        id: `workflow-${Date.now()}`,
        taskId,
        taskKey,
        taskTitle,
        templateId,
        templateName,
        status: 'running',
        startedAt: new Date(),
        phasesCompleted: [],
      };

      setHistory(prev => [entry, ...prev]);
      return entry.id;
    } catch (error) {
      console.error('Failed to start workflow entry:', error);
      return null;
    }
  }, []);

  const updateWorkflowProgress = useCallback(async (
    historyId: string,
    progress: {
      phasesCompleted: string[];
      branchName?: string;
      prUrl?: string;
      prNumber?: number;
    }
  ) => {
    try {
      setHistory(prev => prev.map(entry =>
        entry.id === historyId
          ? { ...entry, ...progress }
          : entry
      ));
    } catch (error) {
      console.error('Failed to update workflow progress:', error);
    }
  }, []);

  const completeWorkflow = useCallback(async (
    historyId: string,
    status: 'completed' | 'failed',
    results?: any[],
    error?: string
  ) => {
    try {
      setHistory(prev => prev.map(entry =>
        entry.id === historyId
          ? {
              ...entry,
              status,
              completedAt: new Date(),
              results,
              error,
            }
          : entry
      ));
    } catch (error) {
      console.error('Failed to complete workflow:', error);
    }
  }, []);

  const getWorkflowHistory = useCallback(() => {
    return history;
  }, [history]);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return {
    startWorkflowEntry,
    updateWorkflowProgress,
    completeWorkflow,
    getWorkflowHistory,
    clearHistory,
  };
};