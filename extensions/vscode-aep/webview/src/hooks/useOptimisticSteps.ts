/**
 * Custom hook to manage optimistic steps with dual-map structure
 * Encapsulates the complexity of maintaining two synchronized maps:
 * - Primary map indexed by step ID
 * - Secondary lookup map indexed by text+owner key
 * 
 * This ensures consistency and prevents state desynchronization.
 */

import { useState, useRef, useCallback } from 'react';
import type { PlanStep } from './useLivePlan';

interface OptimisticStepsState {
  // Primary map indexed by step ID
  byId: Map<string, PlanStep>;
  // Secondary lookup map indexed by text+owner key
  byKey: Map<string, PlanStep>;
}

export function useOptimisticSteps() {
  const [state, setState] = useState<OptimisticStepsState>({
    byId: new Map(),
    byKey: new Map(),
  });

  // Refs for accessing current state in callbacks without stale closures
  const stateRef = useRef(state);
  stateRef.current = state;

  // Add a new optimistic step
  const add = useCallback((step: PlanStep) => {
    if (!step.id) {
      console.warn('Attempted to add optimistic step without id:', step);
      return;
    }
    const key = `${step.text}|${step.owner}`;
    setState(prev => ({
      byId: new Map(prev.byId).set(step.id!, step),
      byKey: new Map(prev.byKey).set(key, step),
    }));
  }, []);

  // Remove an optimistic step by ID
  const removeById = useCallback((id: string) => {
    setState(prev => {
      const step = prev.byId.get(id);
      if (!step) return prev;

      const newById = new Map(prev.byId);
      newById.delete(id);

      const newByKey = new Map(prev.byKey);
      const key = `${step.text}|${step.owner}`;
      newByKey.delete(key);

      return { byId: newById, byKey: newByKey };
    });
  }, []);

  // Remove an optimistic step by text+owner key
  const removeByKey = useCallback((text: string, owner: string) => {
    const key = `${text}|${owner}`;
    setState(prev => {
      const step = prev.byKey.get(key);
      if (!step || !step.id) return prev;

      const newById = new Map(prev.byId);
      newById.delete(step.id);

      const newByKey = new Map(prev.byKey);
      newByKey.delete(key);

      return { byId: newById, byKey: newByKey };
    });
  }, []);

  // Get step by text+owner key (for matching)
  const getByKey = useCallback((text: string, owner: string): PlanStep | undefined => {
    const key = `${text}|${owner}`;
    return stateRef.current.byKey.get(key);
  }, []);

  // Get step by ID
  const getById = useCallback((id: string): PlanStep | undefined => {
    return stateRef.current.byId.get(id);
  }, []);

  return {
    // State
    pendingSteps: state.byId,
    lookupMap: state.byKey,
    count: state.byId.size,
    // Refs for non-stale access
    pendingStepsRef: stateRef,
    // Operations
    add,
    removeById,
    removeByKey,
    getByKey,
    getById,
  };
}
