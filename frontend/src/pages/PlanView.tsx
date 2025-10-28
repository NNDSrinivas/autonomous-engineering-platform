/**
 * PlanView - Live collaborative planning page
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { StepList } from '../components/StepList';
import { ParticipantList } from '../components/ParticipantList';
import { usePlan, useAddStep, useArchivePlan, type PlanStep } from '../hooks/useLivePlan';
import { CORE_API, ORG } from '../api/client';

export const PlanView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const { data: plan, isLoading, error } = usePlan(id);
  const addStepMutation = useAddStep();
  const archiveMutation = useArchivePlan();
  
  const [liveSteps, setLiveSteps] = useState<PlanStep[]>([]);
  const [stepText, setStepText] = useState('');
  const [ownerName, setOwnerName] = useState('user');
  const [archiveError, setArchiveError] = useState<string | null>(null);

  // Merge backend steps with live streamed steps
  const allSteps = [...(plan?.steps || []), ...liveSteps];

  // Real-time event stream
  useEffect(() => {
    if (!id) return;

    const eventSource = new EventSource(
      `${CORE_API}/api/plan/${id}/stream?org=${ORG}`,
      { withCredentials: false }
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'connected') {
          console.log('Connected to plan stream:', data.plan_id);
        } else if (data.text && data.owner && data.ts) {
          // New step received
          setLiveSteps((prev) => [...prev, data]);
        }
      } catch (err) {
        console.error('Error parsing SSE message:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [id]);

  const handleAddStep = useCallback(async () => {
    if (!id || !stepText.trim()) return;

    try {
      await addStepMutation.mutateAsync({
        plan_id: id,
        text: stepText.trim(),
        owner: ownerName || 'user',
      });
      setStepText('');
    } catch (err) {
      console.error('Failed to add step:', err);
      alert('Failed to add step. Please try again.');
    }
  }, [id, stepText, ownerName, addStepMutation]);

  const handleArchive = useCallback(async () => {
    if (!id) return;

    if (!confirm('Archive this plan? It will be stored in the memory graph.')) {
      return;
    }

    try {
      setArchiveError(null);
      const result = await archiveMutation.mutateAsync(id);
      alert(`Plan archived successfully! Memory Node ID: ${result.memory_node_id}`);
      navigate('/plans');
    } catch (err) {
      console.error('Failed to archive plan:', err);
      setArchiveError(err instanceof Error ? err.message : 'Failed to archive plan');
    }
  }, [id, archiveMutation, navigate]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-indigo-500 border-t-transparent"></div>
          <p className="mt-4 text-gray-600">Loading plan...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <p className="text-red-800 font-medium">Error loading plan</p>
          <p className="text-red-600 text-sm mt-2">{String(error)}</p>
          <button
            onClick={() => navigate('/plans')}
            className="mt-4 text-sm text-red-600 hover:text-red-800 underline"
          >
            Back to Plans
          </button>
        </div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Plan not found</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900">{plan.title}</h1>
              {plan.description && (
                <p className="text-gray-600 mt-2">{plan.description}</p>
              )}
            </div>
            {plan.archived && (
              <span className="px-3 py-1 bg-gray-200 text-gray-700 rounded-full text-sm font-medium">
                📁 Archived
              </span>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 mb-2">Participants:</p>
              <ParticipantList list={plan.participants} />
            </div>
            <div className="text-sm text-gray-500">
              Created: {new Date(plan.created_at).toLocaleDateString()}
            </div>
          </div>
        </div>

        {/* Archive Error */}
        {archiveError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-red-800 font-medium">Archive failed</p>
                <p className="text-red-600 text-sm mt-1">{archiveError}</p>
              </div>
              <button
                onClick={() => setArchiveError(null)}
                className="text-red-600 hover:text-red-800 text-xl leading-none"
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Steps */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Plan Steps ({allSteps.length})
            </h2>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            <StepList steps={allSteps} />
          </div>
        </div>

        {/* Add Step */}
        {!plan.archived && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h3 className="text-md font-semibold text-gray-900 mb-4">Add New Step</h3>
            <div className="flex gap-3">
              <input
                type="text"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                placeholder="Your name"
                className="w-32 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
              <input
                type="text"
                value={stepText}
                onChange={(e) => setStepText(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddStep()}
                placeholder="Describe the step..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
              <button
                onClick={handleAddStep}
                disabled={!stepText.trim() || addStepMutation.isPending}
                className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {addStepMutation.isPending ? 'Adding...' : 'Add Step'}
              </button>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={() => navigate('/plans')}
            className="px-4 py-2 text-gray-700 hover:text-gray-900 underline"
          >
            ← Back to Plans
          </button>
          {!plan.archived && (
            <button
              onClick={handleArchive}
              disabled={archiveMutation.isPending}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 underline disabled:opacity-50"
            >
              {archiveMutation.isPending ? 'Archiving...' : '📁 Archive Plan'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
