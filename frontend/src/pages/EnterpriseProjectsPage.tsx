/**
 * EnterpriseProjectsPage
 *
 * Main page for managing enterprise-level projects.
 * Wraps the EnterpriseProjectDashboard component with data fetching and state management.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  EnterpriseProjectDashboard,
  EnterpriseProject,
} from '@/components/enterprise/EnterpriseProjectDashboard';
import { useEnterpriseProjects } from '@/hooks/useEnterpriseProjects';
import { CreateProjectDialog } from '@/components/enterprise/CreateProjectDialog';

export const EnterpriseProjectsPage: React.FC = () => {
  const navigate = useNavigate();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const {
    projects,
    isLoading,
    error,
    refetch,
    pauseProject,
    resumeProject,
  } = useEnterpriseProjects();

  const handleSelectProject = useCallback((projectId: string) => {
    navigate(`/enterprise/projects/${projectId}`);
  }, [navigate]);

  const handlePauseProject = useCallback(async (projectId: string) => {
    await pauseProject(projectId);
  }, [pauseProject]);

  const handleResumeProject = useCallback(async (projectId: string) => {
    await resumeProject(projectId);
  }, [resumeProject]);

  const handleCreateProject = useCallback(() => {
    setCreateDialogOpen(true);
  }, []);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleReviewGate = useCallback((projectId: string, gateId: string) => {
    navigate(`/enterprise/approvals?project=${projectId}&gate=${gateId}`);
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-red-600 mb-2">Error Loading Projects</h2>
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
      <EnterpriseProjectDashboard
        projects={projects}
        onSelectProject={handleSelectProject}
        onPauseProject={handlePauseProject}
        onResumeProject={handleResumeProject}
        onCreateProject={handleCreateProject}
        onRefresh={handleRefresh}
        onReviewGate={handleReviewGate}
        isLoading={isLoading}
      />

      <CreateProjectDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onProjectCreated={() => {
          setCreateDialogOpen(false);
          refetch();
        }}
      />
    </div>
  );
};

export default EnterpriseProjectsPage;
