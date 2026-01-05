import React from 'react';

/**
 * Phase 4.1.2 Plan Renderer Component
 * 
 * Renders structured execution plans with steps, reasoning, and approval UI
 */

interface PlanStep {
  id: string;
  title: string;
  rationale?: string;
  requires_approval: boolean;
  tool?: string;
  input?: any;
  verify: string[];
  status: "pending" | "active" | "completed" | "failed" | "skipped";
}

interface Plan {
  id: string;
  goal: string;
  steps: PlanStep[];
  requires_approval: boolean;
  confidence: number;
  reasoning?: string;
}

interface PlanRendererProps {
  plan: Plan;
  reasoning?: string;
  session_id?: string;
}

export function PlanRenderer({ plan, reasoning, session_id }: PlanRendererProps) {
  const getStepIcon = (step: PlanStep) => {
    switch (step.status) {
      case 'completed': return '✅';
      case 'active': return '🔄';
      case 'failed': return '❌';
      case 'skipped': return '⏭️';
      default: return '⏳';
    }
  };

  const getStepColor = (step: PlanStep) => {
    switch (step.status) {
      case 'completed': return 'text-green-400';
      case 'active': return 'text-blue-400';
      case 'failed': return 'text-red-400';
      case 'skipped': return 'text-gray-400';
      default: return 'text-gray-300';
    }
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 mb-4">
      {/* Plan Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white mb-1">
            📋 {plan.goal}
          </h3>
          <div className="flex items-center gap-3 text-sm text-gray-400">
            <span>Confidence: {Math.round(plan.confidence * 100)}%</span>
            <span>•</span>
            <span>{plan.steps.length} steps</span>
            {plan.requires_approval && (
              <>
                <span>•</span>
                <span className="text-yellow-400">Requires approval</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Reasoning */}
      {reasoning && (
        <div className="bg-gray-900 rounded p-3 mb-4">
          <p className="text-sm text-gray-300">
            <strong className="text-blue-400">Reasoning:</strong> {reasoning}
          </p>
        </div>
      )}

      {/* Steps */}
      <div className="space-y-3">
        {plan.steps.map((step, index) => (
          <div
            key={step.id}
            className={`flex items-start gap-3 p-3 rounded-lg border ${
              step.status === 'active' 
                ? 'bg-blue-950 border-blue-600' 
                : 'bg-gray-900 border-gray-700'
            }`}
          >
            <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-gray-700 rounded-full text-xs font-bold text-gray-300">
              {index + 1}
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">{getStepIcon(step)}</span>
                <h4 className={`font-medium ${getStepColor(step)}`}>
                  {step.title}
                </h4>
                {step.requires_approval && (
                  <span className="px-2 py-1 text-xs bg-yellow-900 text-yellow-300 rounded">
                    Approval needed
                  </span>
                )}
                {step.tool && (
                  <span className="px-2 py-1 text-xs bg-purple-900 text-purple-300 rounded">
                    {step.tool}
                  </span>
                )}
              </div>
              
              {step.rationale && (
                <p className="text-sm text-gray-400 mt-1">
                  {step.rationale}
                </p>
              )}
              
              {step.verify.length > 0 && (
                <div className="mt-2">
                  <span className="text-xs text-gray-500">Verifies:</span>
                  <ul className="text-xs text-gray-400 ml-2">
                    {step.verify.map((check, i) => (
                      <li key={i}>• {check}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Plan Actions */}
      {plan.requires_approval && session_id && (
        <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-gray-700">
          <button
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
            onClick={() => {
              // TODO: Send rejection
              console.log('Plan rejected');
            }}
          >
            ❌ Reject Plan
          </button>
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors"
            onClick={() => {
              // TODO: Send approval  
              console.log('Plan approved');
            }}
          >
            ✅ Approve & Execute
          </button>
        </div>
      )}
    </div>
  );
}