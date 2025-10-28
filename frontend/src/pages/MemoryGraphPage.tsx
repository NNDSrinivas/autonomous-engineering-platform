/**
 * MemoryGraphPage - Main page for Memory Graph UI
 * Combines GraphView, TimelineView, and Query Overlay
 */

import React, { useState } from 'react';
import { GraphView } from '../components/GraphView';
import { TimelineView } from '../components/TimelineView';
import { 
  useNodeNeighborhood, 
  useTimeline, 
  useGraphQuery,
  GraphQueryResponse 
} from '../hooks/useMemoryGraph';

export const MemoryGraphPage: React.FC = () => {
  const [rootId, setRootId] = useState('ENG-102');
  const [windowDays, setWindowDays] = useState('30d');
  const [question, setQuestion] = useState('why was ENG-102 reopened?');
  const [overlay, setOverlay] = useState<GraphQueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Data hooks
  const { data: baseData, isLoading: loadingBase, error: errorBase } = useNodeNeighborhood(rootId);
  const { data: baseTimeline, isLoading: loadingTimeline } = useTimeline(rootId, windowDays);
  const graphQuery = useGraphQuery();

  const handleExplain = () => {
    if (!question.trim()) return;
    
    setQueryError(null); // Clear previous errors
    
    graphQuery.mutate(
      {
        query: question,
        depth: 2,
        k: 10,
      },
      {
        onSuccess: (data) => {
          setOverlay(data);
        },
        onError: (err) => {
          console.error('Graph query failed:', err);
          setQueryError(err instanceof Error ? err.message : 'Failed to explain. Please try again.');
        },
      }
    );
  };

  const handleNodeClick = (foreignId: string) => {
    setRootId(foreignId);
    setOverlay(null); // Clear overlay when changing root
    setQueryError(null); // Clear error when changing root
  };

  const handleWindowChange = (newWindow: string) => {
    setWindowDays(newWindow);
    setOverlay(null); // Clear overlay when changing window
    setQueryError(null); // Clear error when changing window
  };

  const handleOpenLink = (url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  // Determine which data to display
  // IMPORTANT: Include root node in graph so it can be clicked
  const displayNodes = overlay?.nodes || (baseData ? [baseData.node, ...baseData.neighbors] : []);
  const displayEdges = overlay?.edges || baseData?.edges || [];
  const displayTimeline = overlay?.timeline || baseTimeline || [];

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Memory Graph</h1>
          <p className="text-gray-600 mt-1">
            Explore entity relationships and timeline events
          </p>
        </div>

        {/* Controls Row */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label htmlFor="rootId" className="block text-sm font-medium text-gray-700 mb-1">
                Root Entity
              </label>
              <input
                id="rootId"
                type="text"
                value={rootId}
                onChange={(e) => setRootId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., ENG-102"
              />
            </div>

            <div>
              <label htmlFor="window" className="block text-sm font-medium text-gray-700 mb-1">
                Time Window
              </label>
              <select
                id="window"
                value={windowDays}
                onChange={(e) => handleWindowChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={() => {
                  setOverlay(null);
                  setQueryError(null);
                }}
                disabled={!overlay}
                className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Clear Overlay
              </button>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label htmlFor="question" className="block text-sm font-medium text-gray-700 mb-1">
                Question
              </label>
              <textarea
                id="question"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ask a question about this entity..."
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={handleExplain}
                disabled={!question.trim() || graphQuery.isPending}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {graphQuery.isPending ? 'Explaining...' : 'Explain'}
              </button>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {errorBase && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800 font-medium">Error loading graph data</p>
            <p className="text-red-600 text-sm mt-1">{String(errorBase)}</p>
          </div>
        )}

        {/* Query Error Display */}
        {queryError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-red-800 font-medium">Query failed</p>
                <p className="text-red-600 text-sm mt-1">{queryError}</p>
              </div>
              <button
                onClick={() => setQueryError(null)}
                className="text-red-600 hover:text-red-800 text-xl leading-none"
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loadingBase && !overlay && (
          <div className="bg-white rounded-lg shadow p-12 text-center mb-6">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
            <p className="mt-4 text-gray-600">Loading graph data...</p>
          </div>
        )}

        {/* Graph View */}
        {!loadingBase && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                {overlay ? 'Query Result Graph' : 'Entity Graph'}
              </h2>
              <div className="text-sm text-gray-500">
                {displayNodes.length} nodes · {displayEdges.length} edges
              </div>
            </div>
            <GraphView
              nodes={displayNodes}
              edges={displayEdges}
              onSelectNode={handleNodeClick}
            />
          </div>
        )}

        {/* Two-column layout: Timeline + Narrative */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Timeline Panel */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                {overlay ? 'Query Timeline' : 'Timeline'}
              </h2>
              {loadingTimeline && !overlay && (
                <span className="text-sm text-gray-500">Loading...</span>
              )}
            </div>
            <div className="max-h-[600px] overflow-y-auto pr-2">
              <TimelineView items={displayTimeline} onOpenLink={handleOpenLink} />
            </div>
          </div>

          {/* Narrative Panel */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Narrative</h2>
            {overlay?.narrative ? (
              <div className="prose prose-sm max-w-none">
                <p className="text-gray-700 whitespace-pre-wrap">{overlay.narrative}</p>
                {overlay.paths && overlay.paths.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">Paths Explored:</h3>
                    <ul className="space-y-2">
                      {overlay.paths.map((path, idx) => (
                        <li key={idx} className="text-xs text-gray-600">
                          <span className="font-medium">Weight {path.weight?.toFixed(2) || 'N/A'}:</span>{' '}
                          {path.node_sequence?.join(' → ') || 'N/A'}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                <div className="text-center">
                  <p className="text-gray-500 mb-2">No narrative available</p>
                  <p className="text-xs text-gray-400">Ask a question and click "Explain" to generate insights</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
