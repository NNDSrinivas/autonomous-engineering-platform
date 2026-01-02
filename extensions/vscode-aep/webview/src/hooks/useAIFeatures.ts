import { useState, useEffect } from 'react';
import type { JiraTask } from '@/types';

interface CorrelatedResource {
  id: string;
  type: 'file' | 'pr' | 'commit' | 'branch' | 'slack_thread' | 'confluence_page';
  title: string;
  url?: string;
  description?: string;
  confidence: number;
  lastModified?: string;
  metadata?: Record<string, any>;
}

interface TaskCorrelationData {
  resources: CorrelatedResource[];
  loading: boolean;
  error: string | null;
}

export function useTaskCorrelation(task: JiraTask | null): TaskCorrelationData {
  const [data, setData] = useState<TaskCorrelationData>({
    resources: [],
    loading: false,
    error: null,
  });

  useEffect(() => {
    if (!task) {
      setData({ resources: [], loading: false, error: null });
      return;
    }

    setData(prev => ({ ...prev, loading: true, error: null }));

    // Simulate API call for now - replace with actual implementation
    const mockResources: CorrelatedResource[] = [
      {
        id: '1',
        type: 'file',
        title: 'UserService.tsx',
        description: 'Main user service implementation',
        confidence: 0.92,
        lastModified: '2024-01-15T10:30:00Z',
        metadata: { lines: 245, language: 'typescript' }
      },
      {
        id: '2',
        type: 'pr',
        title: 'Fix user authentication flow',
        url: 'https://github.com/org/repo/pull/123',
        confidence: 0.87,
        lastModified: '2024-01-14T15:45:00Z',
        metadata: { status: 'merged', author: 'john.doe' }
      },
      {
        id: '3',
        type: 'commit',
        title: 'Update user validation logic',
        confidence: 0.78,
        lastModified: '2024-01-13T09:20:00Z',
        metadata: { hash: 'abc123', author: 'jane.smith' }
      }
    ];

    // Simulate async operation
    setTimeout(() => {
      setData({
        resources: mockResources,
        loading: false,
        error: null,
      });
    }, 1000);
  }, [task]);

  return data;
}

export function useMorningBriefing() {
  const [briefing, setBriefing] = useState({
    summary: '',
    priorities: [] as string[],
    blockers: [] as string[],
    suggestions: [] as string[],
    loading: true,
    error: null as string | null,
  });

  useEffect(() => {
    // Simulate loading briefing data
    setTimeout(() => {
      setBriefing({
        summary: 'Good morning! Here\'s what needs your attention today.',
        priorities: [
          'Review PR #456 for the authentication system',
          'Complete user dashboard redesign',
          'Update API documentation'
        ],
        blockers: [
          'Waiting for design approval on landing page',
          'Database migration pending'
        ],
        suggestions: [
          'Consider refactoring the payment service',
          'Update dependencies in package.json',
          'Add error handling to the user service'
        ],
        loading: false,
        error: null,
      });
    }, 1500);
  }, []);

  return briefing;
}

export function useUniversalSearch() {
  const [searchState, setSearchState] = useState({
    query: '',
    results: [] as any[],
    loading: false,
    error: null as string | null,
    filters: {
      files: true,
      commits: true,
      prs: true,
      issues: true,
      docs: true,
    },
  });

  const search = async (query: string) => {
    if (!query.trim()) {
      setSearchState(prev => ({ ...prev, results: [], loading: false }));
      return;
    }

    setSearchState(prev => ({ ...prev, loading: true, error: null }));

    // Simulate search API call
    setTimeout(() => {
      const mockResults = [
        {
          type: 'file',
          title: 'App.tsx',
          description: 'Main application component',
          path: '/src/App.tsx',
          score: 0.95,
        },
        {
          type: 'commit',
          title: 'Add new search functionality',
          description: 'Implemented universal search across codebase',
          hash: 'def456',
          score: 0.88,
        },
        {
          type: 'issue',
          title: 'Improve search performance',
          description: 'Search results are loading too slowly',
          id: '#789',
          score: 0.82,
        },
      ];

      setSearchState(prev => ({
        ...prev,
        results: mockResults,
        loading: false,
      }));
    }, 800);
  };

  return {
    ...searchState,
    search,
    setQuery: (query: string) => setSearchState(prev => ({ ...prev, query })),
    setFilters: (filters: any) => setSearchState(prev => ({ ...prev, filters })),
  };
}