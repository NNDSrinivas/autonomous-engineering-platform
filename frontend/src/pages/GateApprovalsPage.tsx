/**
 * GateApprovalsPage
 *
 * Page for reviewing and approving human checkpoint gates across all enterprise projects.
 */

import React, { useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  GateApprovalQueue,
  GateDecision,
} from '@/components/enterprise/GateApprovalQueue';
import { useGateApprovals } from '@/hooks/useGateApprovals';

export const GateApprovalsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const highlightGateId = searchParams.get('gate');
  const filterProjectId = searchParams.get('project');

  const {
    gates,
    isLoading,
    error,
    refetch,
    submitDecision,
  } = useGateApprovals({ projectId: filterProjectId || undefined });

  const handleDecision = useCallback(async (decision: GateDecision) => {
    await submitDecision(decision);
    refetch();
  }, [submitDecision, refetch]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  // Auto-scroll to highlighted gate if specified
  useEffect(() => {
    if (highlightGateId) {
      setTimeout(() => {
        const element = document.getElementById(`gate-${highlightGateId}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 500);
    }
  }, [highlightGateId, gates]);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-red-600 mb-2">Error Loading Gates</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <GateApprovalQueue
        gates={gates}
        onDecision={handleDecision}
        onRefresh={handleRefresh}
        isLoading={isLoading}
      />
    </div>
  );
};

export default GateApprovalsPage;
