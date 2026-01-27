/**
 * useEnterpriseProjects Hook
 *
 * Manages enterprise project state and API interactions.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { EnterpriseProject } from '@/components/enterprise/EnterpriseProjectDashboard';

interface UseEnterpriseProjectsOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseEnterpriseProjectsResult {
  projects: EnterpriseProject[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  pauseProject: (projectId: string) => Promise<void>;
  resumeProject: (projectId: string) => Promise<void>;
  getProject: (projectId: string) => EnterpriseProject | undefined;
}

const API_BASE = '/api/navi/enterprise';

export function useEnterpriseProjects(
  options: UseEnterpriseProjectsOptions = {}
): UseEnterpriseProjectsResult {
  const { autoRefresh = true, refreshInterval = 30000 } = options;

  const [projects, setProjects] = useState<EnterpriseProject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/projects`);
      if (!response.ok) {
        throw new Error(`Failed to fetch projects: ${response.statusText}`);
      }

      const data = await response.json();

      // Transform backend data to frontend format
      const transformedProjects: EnterpriseProject[] = data.map((p: any) => ({
        id: p.id,
        name: p.name,
        description: p.description,
        projectType: p.project_type,
        status: p.status,
        progress: p.progress_percentage,
        createdAt: p.created_at,
        updatedAt: p.updated_at,
        stats: {
          totalTasks: p.stats?.total_tasks || 0,
          completedTasks: p.stats?.completed_tasks || 0,
          failedTasks: p.stats?.failed_tasks || 0,
          pendingGates: p.stats?.pending_gates || 0,
          activeAgents: p.stats?.active_agents || 0,
          iterationCount: p.stats?.iteration_count || 0,
          runtimeHours: p.stats?.runtime_hours || 0,
        },
        currentTask: p.current_task
          ? {
              id: p.current_task.id,
              title: p.current_task.title,
              status: p.current_task.status,
            }
          : undefined,
        milestones: (p.milestones || []).map((m: any) => ({
          id: m.id,
          title: m.title,
          completedTasks: m.completed_tasks,
          totalTasks: m.total_tasks,
          status: m.status,
        })),
        pendingGates: (p.pending_gates || []).map((g: any) => ({
          id: g.id,
          type: g.gate_type,
          title: g.title,
          blocksProgress: g.blocks_progress,
          priority: g.priority,
          createdAt: g.created_at,
        })),
        recentTasks: (p.recent_tasks || []).map((t: any) => ({
          id: t.id,
          title: t.title,
          status: t.status,
          priority: t.priority,
          dependencies: t.dependencies || [],
          assignedAgent: t.assigned_agent,
        })),
      }));

      setProjects(transformedProjects);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const pauseProject = useCallback(async (projectId: string) => {
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/pause`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to pause project');
      }

      // Update local state
      setProjects((prev) =>
        prev.map((p) =>
          p.id === projectId ? { ...p, status: 'paused' as const } : p
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause project');
      throw err;
    }
  }, []);

  const resumeProject = useCallback(async (projectId: string) => {
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/start`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to resume project');
      }

      // Update local state
      setProjects((prev) =>
        prev.map((p) =>
          p.id === projectId ? { ...p, status: 'active' as const } : p
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume project');
      throw err;
    }
  }, []);

  const getProject = useCallback(
    (projectId: string) => {
      return projects.find((p) => p.id === projectId);
    },
    [projects]
  );

  // Initial fetch
  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchProjects, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchProjects]);

  return {
    projects,
    isLoading,
    error,
    refetch: fetchProjects,
    pauseProject,
    resumeProject,
    getProject,
  };
}

/**
 * Hook for a single enterprise project with real-time updates
 */
export function useEnterpriseProject(projectId: string | null) {
  const [project, setProject] = useState<EnterpriseProject | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProject = useCallback(async () => {
    if (!projectId) {
      setProject(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/projects/${projectId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch project');
      }

      const data = await response.json();

      // Transform to frontend format
      const transformed: EnterpriseProject = {
        id: data.id,
        name: data.name,
        description: data.description,
        projectType: data.project_type,
        status: data.status,
        progress: data.progress_percentage,
        createdAt: data.created_at,
        updatedAt: data.updated_at,
        stats: {
          totalTasks: data.stats?.total_tasks || 0,
          completedTasks: data.stats?.completed_tasks || 0,
          failedTasks: data.stats?.failed_tasks || 0,
          pendingGates: data.stats?.pending_gates || 0,
          activeAgents: data.stats?.active_agents || 0,
          iterationCount: data.stats?.iteration_count || 0,
          runtimeHours: data.stats?.runtime_hours || 0,
        },
        currentTask: data.current_task,
        milestones: data.milestones || [],
        pendingGates: data.pending_gates || [],
        recentTasks: data.recent_tasks || [],
      };

      setProject(transformed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProject();
  }, [fetchProject]);

  // SSE for real-time updates
  useEffect(() => {
    if (!projectId) return;

    const eventSource = new EventSource(
      `${API_BASE}/projects/${projectId}/stream`
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'project_update') {
          setProject((prev) => (prev ? { ...prev, ...data.project } : null));
        }
      } catch (err) {
        console.error('Failed to parse SSE message:', err);
      }
    };

    eventSource.onerror = () => {
      console.warn('SSE connection error, will retry...');
    };

    return () => {
      eventSource.close();
    };
  }, [projectId]);

  return {
    project,
    isLoading,
    error,
    refetch: fetchProject,
  };
}

/**
 * Hook for executing/resuming enterprise projects with streaming events
 */
export interface EnterpriseExecutionEvent {
  type: string;
  [key: string]: any;
}

export interface UseEnterpriseExecutionOptions {
  onEvent?: (event: EnterpriseExecutionEvent) => void;
  onProjectCreated?: (project: { id: string; name: string; estimated_tasks: number }) => void;
  onGateTriggered?: (gate: any) => void;
  onComplete?: (summary: any) => void;
  onError?: (error: string) => void;
}

export function useEnterpriseExecution(options: UseEnterpriseExecutionOptions = {}) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [events, setEvents] = useState<EnterpriseExecutionEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const executeProject = useCallback(
    async (message: string, opts?: { forceEnterprise?: boolean; executionMode?: string }) => {
      setIsExecuting(true);
      setEvents([]);
      setError(null);

      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(`${API_BASE.replace('/enterprise', '')}/chat/enterprise`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message,
            force_enterprise: opts?.forceEnterprise ?? true,
            execution_mode: opts?.executionMode ?? 'hybrid',
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim();
              if (data === '[DONE]') continue;

              try {
                const event = JSON.parse(data) as EnterpriseExecutionEvent;
                setEvents((prev) => [...prev, event]);
                options.onEvent?.(event);

                // Handle specific event types
                if (event.type === 'project_created') {
                  setCurrentProjectId(event.project_id);
                  options.onProjectCreated?.({
                    id: event.project_id,
                    name: event.name,
                    estimated_tasks: event.estimated_tasks,
                  });
                }
                if (event.type === 'gate_triggered') {
                  options.onGateTriggered?.(event.gate);
                }
                if (event.type === 'complete' || event.type === 'project_completed') {
                  options.onComplete?.(event.summary);
                }
                if (event.type === 'error' || event.type === 'failed') {
                  setError(event.error || event.message || 'Unknown error');
                  options.onError?.(event.error || event.message || 'Unknown error');
                }
              } catch (parseErr) {
                console.warn('Failed to parse SSE event:', data);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          const errorMsg = err.message || 'Execution failed';
          setError(errorMsg);
          options.onError?.(errorMsg);
        }
      } finally {
        setIsExecuting(false);
        abortControllerRef.current = null;
      }
    },
    [options]
  );

  const resumeProject = useCallback(
    async (projectId: string, checkpointId?: string) => {
      setIsExecuting(true);
      setCurrentProjectId(projectId);
      setEvents([]);
      setError(null);

      abortControllerRef.current = new AbortController();

      try {
        const url = new URL(`${API_BASE.replace('/enterprise', '')}/chat/enterprise/resume/${projectId}`);
        if (checkpointId) {
          url.searchParams.set('checkpoint_id', checkpointId);
        }

        const response = await fetch(url.toString(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim();
              if (data === '[DONE]') continue;

              try {
                const event = JSON.parse(data) as EnterpriseExecutionEvent;
                setEvents((prev) => [...prev, event]);
                options.onEvent?.(event);

                if (event.type === 'complete' || event.type === 'project_completed') {
                  options.onComplete?.(event.summary);
                }
                if (event.type === 'error') {
                  setError(event.error || 'Unknown error');
                  options.onError?.(event.error || 'Unknown error');
                }
              } catch (parseErr) {
                console.warn('Failed to parse SSE event:', data);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          const errorMsg = err.message || 'Resume failed';
          setError(errorMsg);
          options.onError?.(errorMsg);
        }
      } finally {
        setIsExecuting(false);
        abortControllerRef.current = null;
      }
    },
    [options]
  );

  const cancelExecution = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsExecuting(false);
  }, []);

  return {
    executeProject,
    resumeProject,
    cancelExecution,
    isExecuting,
    currentProjectId,
    events,
    error,
  };
}

export default useEnterpriseProjects;
