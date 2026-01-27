/**
 * useGateApprovals Hook
 *
 * Manages human checkpoint gate state and approval interactions.
 */

import { useState, useEffect, useCallback } from 'react';
import type { HumanGate, GateDecision } from '@/components/enterprise/GateApprovalQueue';

interface UseGateApprovalsOptions {
  projectId?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

interface UseGateApprovalsResult {
  gates: HumanGate[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  submitDecision: (decision: GateDecision) => Promise<void>;
  getGate: (gateId: string) => HumanGate | undefined;
}

const API_BASE = '/api/navi/enterprise';

export function useGateApprovals(
  options: UseGateApprovalsOptions = {}
): UseGateApprovalsResult {
  const { projectId, autoRefresh = true, refreshInterval = 15000 } = options;

  const [gates, setGates] = useState<HumanGate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGates = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch from specific project or all projects
      const url = projectId
        ? `${API_BASE}/projects/${projectId}/gates`
        : `${API_BASE}/gates/pending`;

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch gates: ${response.statusText}`);
      }

      const data = await response.json();

      // Transform backend data to frontend format
      const transformedGates: HumanGate[] = data.map((g: any) => ({
        id: g.id,
        projectId: g.project_id,
        projectName: g.project_name || 'Unknown Project',
        gateType: g.gate_type,
        title: g.title,
        description: g.description,
        context: g.context,
        options: (g.options || []).map((o: any) => ({
          id: o.id,
          label: o.label,
          description: o.description,
          tradeOffs: o.trade_offs,
          recommended: o.recommended,
          estimatedCost: o.estimated_cost,
          riskLevel: o.risk_level,
        })),
        blocksProgress: g.blocks_progress ?? true,
        priority: g.priority || 'medium',
        createdAt: g.created_at,
        metadata: g.metadata
          ? {
              affectedFiles: g.metadata.affected_files,
              estimatedImpact: g.metadata.estimated_impact,
              relatedTasks: g.metadata.related_tasks,
              requestedBy: g.metadata.requested_by,
            }
          : undefined,
      }));

      setGates(transformedGates);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  const submitDecision = useCallback(
    async (decision: GateDecision) => {
      try {
        // Find the gate to get its project ID
        const gate = gates.find((g) => g.id === decision.gateId);
        if (!gate) {
          throw new Error('Gate not found');
        }

        const response = await fetch(
          `${API_BASE}/projects/${gate.projectId}/gates/${decision.gateId}/decide`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              approved: decision.approved,
              chosen_option_id: decision.selectedOptionId,
              decision_reason: decision.reason,
            }),
          }
        );

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to submit decision');
        }

        // Remove the gate from local state
        setGates((prev) => prev.filter((g) => g.id !== decision.gateId));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to submit decision');
        throw err;
      }
    },
    [gates]
  );

  const getGate = useCallback(
    (gateId: string) => {
      return gates.find((g) => g.id === gateId);
    },
    [gates]
  );

  // Initial fetch
  useEffect(() => {
    fetchGates();
  }, [fetchGates]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchGates, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchGates]);

  return {
    gates,
    isLoading,
    error,
    refetch: fetchGates,
    submitDecision,
    getGate,
  };
}

/**
 * Hook for watching gate notifications (for VS Code extension use)
 */
export function useGateNotifications(onNewGate?: (gate: HumanGate) => void) {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE}/gates/notifications`);

    eventSource.onopen = () => {
      setConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_gate' && onNewGate) {
          onNewGate(data.gate);
        }
      } catch (err) {
        console.error('Failed to parse gate notification:', err);
      }
    };

    eventSource.onerror = () => {
      setConnected(false);
    };

    return () => {
      eventSource.close();
    };
  }, [onNewGate]);

  return { connected };
}

export default useGateApprovals;
