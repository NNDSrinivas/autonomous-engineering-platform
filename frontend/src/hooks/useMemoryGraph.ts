/**
 * React Query hooks for Memory Graph API
 */

import { useQuery, useMutation, UseQueryResult, UseMutationResult } from '@tanstack/react-query';
import { api } from '../api/client';

interface Node {
  id: number;
  foreign_id: string;
  kind: string;
  title: string;
  summary?: string;
  created_at: string;
}

interface Edge {
  id: number;
  src_id: number;
  dst_id: number;
  relation: string;
  weight: number;
  confidence: number;
}

interface NodeNeighborhoodResponse {
  node: Node;
  neighbors: Node[];
  edges: Edge[];
  elapsed_ms: number;
}

interface TimelineItem {
  id: number;
  ts: string;
  created_at: string;
  title: string;
  kind: string;
  foreign_id: string;
  link?: string;
  summary?: string;
}

interface GraphQueryRequest {
  query: string;
  depth?: number;
  k?: number;
}

interface GraphQueryResponse {
  nodes: Node[];
  edges: Edge[];
  timeline: TimelineItem[];
  narrative: string;
  paths?: any[];
}

/**
 * Fetch node and its 1-hop neighborhood
 */
export function useNodeNeighborhood(foreignId?: string): UseQueryResult<NodeNeighborhoodResponse, Error> {
  return useQuery({
    queryKey: ['node-neighborhood', foreignId],
    queryFn: async () => {
      if (!foreignId) throw new Error('foreignId required');
      const response = await api.get<NodeNeighborhoodResponse>(
        `/api/memory/graph/node/${foreignId}`
      );
      return response.data;
    },
    enabled: !!foreignId,
    staleTime: 30_000, // 30 seconds
    retry: 1,
  });
}

/**
 * Fetch timeline for an entity
 */
export function useTimeline(
  entityId?: string,
  window: string = '30d'
): UseQueryResult<TimelineItem[], Error> {
  return useQuery({
    queryKey: ['timeline', entityId, window],
    queryFn: async () => {
      if (!entityId) throw new Error('entityId required');
      const response = await api.get<TimelineItem[]>('/api/memory/timeline', {
        params: { entity_id: entityId, window },
      });
      return response.data;
    },
    enabled: !!entityId,
    staleTime: 30_000,
    retry: 1,
  });
}

/**
 * Execute graph query with natural language
 */
export function useGraphQuery(): UseMutationResult<GraphQueryResponse, Error, GraphQueryRequest> {
  return useMutation({
    mutationFn: async (request: GraphQueryRequest) => {
      const response = await api.post<GraphQueryResponse>('/api/memory/graph/query', {
        query: request.query,
        depth: request.depth || 3,
        k: request.k || 12,
      });
      return response.data;
    },
  });
}
