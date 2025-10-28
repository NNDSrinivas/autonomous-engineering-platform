/**
 * React Query hooks for Live Plan API
 */

import { useQuery, useMutation, useQueryClient, UseQueryResult, UseMutationResult } from '@tanstack/react-query';
import { api } from '../api/client';

export interface PlanStep {
  // id may be absent for transient/local steps before the server assigns one
  id?: string;
  text: string;
  owner: string;
  ts: string;
}

export interface LivePlan {
  id: string;
  org_id: string;
  title: string;
  description?: string;
  steps: PlanStep[];
  participants: string[];
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface StartPlanRequest {
  title: string;
  description?: string;
  participants?: string[];
}

export interface AddStepRequest {
  plan_id: string;
  text: string;
  owner?: string;
}

/**
 * Hook to fetch a single plan
 */
export function usePlan(planId?: string): UseQueryResult<LivePlan, Error> {
  return useQuery({
    queryKey: ['plan', planId],
    queryFn: async () => {
      if (!planId) throw new Error('planId required');
      const response = await api.get<LivePlan>(`/api/plan/${planId}`);
      return response.data;
    },
    enabled: !!planId,
    staleTime: 60000, // 60 seconds - SSE provides real-time updates
    retry: 1,
  });
}

/**
 * Hook to list plans
 */
export function usePlanList(archived?: boolean): UseQueryResult<{ plans: LivePlan[]; count: number }, Error> {
  return useQuery({
    queryKey: ['plans', archived],
    queryFn: async () => {
      const params = archived !== undefined ? { archived } : {};
      const response = await api.get('/api/plan/list', { params });
      return response.data;
    },
    staleTime: 10000, // 10 seconds
  });
}

/**
 * Hook to start a new plan
 */
export function useStartPlan(): UseMutationResult<{ plan_id: string; status: string }, Error, StartPlanRequest> {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (req: StartPlanRequest) => {
      const response = await api.post('/api/plan/start', req);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
    },
  });
}

/**
 * Hook to add a step to a plan
 */
export function useAddStep(): UseMutationResult<{ status: string; step: PlanStep }, Error, AddStepRequest> {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (req: AddStepRequest) => {
      const response = await api.post('/api/plan/step', req);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['plan', variables.plan_id] });
    },
  });
}

/**
 * Hook to archive a plan
 */
export function useArchivePlan(): UseMutationResult<
  { status: string; plan_id: string; memory_node_id: number },
  Error,
  string
> {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (planId: string) => {
      const response = await api.post(`/api/plan/${planId}/archive`);
      return response.data;
    },
    onSuccess: (_, planId) => {
      queryClient.invalidateQueries({ queryKey: ['plan', planId] });
      queryClient.invalidateQueries({ queryKey: ['plans'] });
    },
  });
}
