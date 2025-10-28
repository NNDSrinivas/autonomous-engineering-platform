/**
 * StepList - Display list of plan steps
 */

import React from 'react';
import dayjs from 'dayjs';
import type { PlanStep } from '../hooks/useLivePlan';

interface StepListProps {
  steps: PlanStep[];
}

export const StepList: React.FC<StepListProps> = ({ steps }) => {
  if (steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
        <p className="text-gray-500 text-sm">No steps yet. Add the first step below!</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-200">
      {steps.map((step, idx) => (
        <div
          key={step.id ?? `${step.ts}-${idx}`}
          className="py-3 px-4 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm text-gray-900">
                <span className="font-semibold text-indigo-600">{step.owner}</span>: {step.text}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {dayjs(step.ts).format('MMM D, YYYY HH:mm:ss')}
              </div>
            </div>
            <div className="text-xs text-gray-400 font-mono">
              #{idx + 1}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
