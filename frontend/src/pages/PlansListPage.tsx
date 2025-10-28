/**
 * PlansListPage - List all plans with create functionality
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePlanList, useStartPlan } from '../hooks/useLivePlan';

export const PlansListPage: React.FC = () => {
  const navigate = useNavigate();
  const [showArchived, setShowArchived] = useState(false);
  
  const { data, isLoading, error } = usePlanList(showArchived);
  const startPlanMutation = useStartPlan();
  
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newPlanTitle, setNewPlanTitle] = useState('');
  const [newPlanDescription, setNewPlanDescription] = useState('');

  const handleCreatePlan = async () => {
    if (!newPlanTitle.trim()) {
      alert('Please enter a plan title');
      return;
    }

    try {
      const result = await startPlanMutation.mutateAsync({
        title: newPlanTitle.trim(),
        description: newPlanDescription.trim() || undefined,
        participants: ['user'],
      });
      
      // Navigate to the new plan
      navigate(`/plan/${result.plan_id}`);
    } catch (err) {
      console.error('Failed to create plan:', err);
      alert('Failed to create plan. Please try again.');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-indigo-500 border-t-transparent"></div>
          <p className="mt-4 text-gray-600">Loading plans...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <p className="text-red-800 font-medium">Error loading plans</p>
          <p className="text-red-600 text-sm mt-2">{String(error)}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Live Plans</h1>
          <p className="text-gray-600 mt-1">
            Collaborative planning sessions with real-time updates
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowArchived(!showArchived)}
              className={`px-4 py-2 rounded-md transition-colors ${
                showArchived
                  ? 'bg-gray-200 text-gray-700'
                  : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {showArchived ? '📁 Showing Archived' : '📋 Show Archived'}
            </button>
          </div>

          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors font-medium"
          >
            + New Plan
          </button>
        </div>

        {/* Create Form */}
        {showCreateForm && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Create New Plan</h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
                  Title *
                </label>
                <input
                  id="title"
                  type="text"
                  value={newPlanTitle}
                  onChange={(e) => setNewPlanTitle(e.target.value)}
                  placeholder="e.g., Feature X Implementation"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                  Description (optional)
                </label>
                <textarea
                  id="description"
                  value={newPlanDescription}
                  onChange={(e) => setNewPlanDescription(e.target.value)}
                  placeholder="Describe the plan's goals and scope..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleCreatePlan}
                  disabled={!newPlanTitle.trim() || startPlanMutation.isPending}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
                >
                  {startPlanMutation.isPending ? 'Creating...' : 'Create Plan'}
                </button>
                <button
                  onClick={() => {
                    setShowCreateForm(false);
                    setNewPlanTitle('');
                    setNewPlanDescription('');
                  }}
                  className="px-6 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Plans List */}
        {data && data.plans.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <p className="text-gray-500 mb-4">
              {showArchived ? 'No archived plans' : 'No active plans'}
            </p>
            {!showArchived && (
              <button
                onClick={() => setShowCreateForm(true)}
                className="text-indigo-600 hover:text-indigo-800 underline"
              >
                Create your first plan
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data?.plans.map((plan) => (
              <div
                key={plan.id}
                onClick={() => navigate(`/plan/${plan.id}`)}
                className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer p-6"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-semibold text-gray-900 line-clamp-2">
                    {plan.title}
                  </h3>
                  {plan.archived && (
                    <span className="text-xs bg-gray-200 text-gray-700 px-2 py-1 rounded">
                      📁
                    </span>
                  )}
                </div>
                
                {plan.description && (
                  <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                    {plan.description}
                  </p>
                )}

                <div className="flex items-center justify-between text-xs text-gray-500">
                  <div>
                    <span className="font-medium">{plan.steps.length}</span> steps
                  </div>
                  <div>
                    <span className="font-medium">{plan.participants.length}</span> participants
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200 text-xs text-gray-400">
                  Updated {new Date(plan.updated_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
