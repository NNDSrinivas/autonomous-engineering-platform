import React from 'react';
import { useUIState } from '../../state/uiStore';

/**
 * WorkflowTimeline - Enhanced workflow transparency with Copilot polish
 * 
 * Phase 4.0.3 enhancements:
 * - Connected to UI state machine
 * - Real-time step progression
 * - Deterministic status updates
 * - Proper icons and animations
 */
export function WorkflowTimeline() {
  const { state } = useUIState();
  
  // ⭐ CRITICAL: Only render if workflow exists (no phantom progress!)
  if (!state.workflow) {
    return null;
  }
  
  const workflow = state.workflow;
  const stepEntries = Object.entries(workflow.steps);
  const totalSteps = stepEntries.length;
  const completedSteps = stepEntries.filter(([, status]) => status === 'completed').length;
  const progressPercent = totalSteps === 0 ? 0 : Math.round((completedSteps / totalSteps) * 100);

  const statusLabel = workflow.agentStatus === 'awaiting_approval'
    ? 'Awaiting approval'
    : workflow.agentStatus === 'error'
      ? 'Action required'
      : workflow.agentStatus === 'running'
        ? 'Running'
        : 'Idle';

  const statusTone = workflow.agentStatus === 'awaiting_approval'
    ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
    : workflow.agentStatus === 'error'
      ? 'bg-red-500/20 text-red-300 border-red-500/30'
      : workflow.agentStatus === 'running'
        ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
        : 'bg-gray-500/10 text-gray-400 border-gray-500/30';
  
  // Map canonical step names to display labels
  const stepLabels: Record<string, string> = {
    scan: 'Scanned workspace',
    plan: 'Built plan', 
    diff: 'Generating diff…',
    validate: 'Validation',
    apply: 'Ready to apply',
    pr: 'Create PR',
    ci: 'CI/CD Pipeline',
    heal: 'Self-heal',
  };
  
  const stepIcons: Record<string, string> = {
    scan: 'folder',
    plan: 'document',
    diff: 'code',
    validate: 'check',
    apply: 'play',
    pr: 'git',
    ci: 'workflow',
    heal: 'shield',
  };
  
  // Only show steps that are not pending (unless agent is running)
  const visibleSteps = stepEntries.filter(([stepId, status]) => {
    return status !== 'pending' || workflow.agentStatus === 'running' || workflow.currentStep === stepId;
  });

  const getIcon = (icon: string, status: string) => {
    const iconClass = "w-3 h-3";
    const isActive = status === 'active';
    
    switch (icon) {
      case 'folder':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
        );
      case 'document':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
      case 'code':
        return (
          <svg className={`${iconClass} ${isActive ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
        );
      case 'check':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'play':
        return (
          <svg className={iconClass} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1.586a1 1 0 01.707.293l2.414 2.414a1 1 0 00.707.293H15M6 20l4-16m4 4l4 4-4 4" />
          </svg>
        );
      default:
        return <div className={`${iconClass} bg-gray-400 rounded`} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-400';
      case 'active': return 'text-blue-400';
      case 'failed': return 'text-red-400';
      case 'pending': return 'text-gray-400';
      default: return 'text-gray-400';
    }
  };

  const getOpacity = (status: string) => {
    switch (status) {
      case 'completed': return 'opacity-60';
      case 'active': return 'opacity-100';
      case 'failed': return 'opacity-80';
      case 'pending': return 'opacity-40';
      default: return 'opacity-40';
    }
  };

  return (
    <div className="bg-[var(--vscode-editor-background)] border border-[var(--vscode-panel-border)] rounded-lg p-3">
      <div className="text-sm font-medium mb-3 opacity-90 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          Workflow Progress
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${statusTone}`}>
          {statusLabel}
        </span>
      </div>
      
      <div className="text-xs space-y-2">
        {visibleSteps.map(([stepId, status]) => (
          <div key={stepId} className={`flex items-center gap-3 transition-all duration-300 ${getOpacity(status)}`}>
            <div className={`flex items-center justify-center w-5 h-5 rounded-full transition-all duration-200 ${
              status === 'completed' ? 'bg-green-500/20 border border-green-500/50' :
              status === 'active' ? 'bg-blue-500/20 border border-blue-500/50 animate-pulse-ring' :
              status === 'failed' ? 'bg-red-500/20 border border-red-500/50' :
              'bg-gray-500/10 border border-gray-500/30'
            }`}>
              <div className={getStatusColor(status)}>
                {getIcon(stepIcons[stepId] || 'document', status)}
              </div>
            </div>
            <span className={`flex-1 ${status === 'active' ? 'font-medium' : ''}`}>
              {stepLabels[stepId] || stepId}
            </span>
            {status === 'completed' && (
              <span className="text-green-400">✓</span>
            )}
            {status === 'active' && (
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
            )}
            {status === 'failed' && (
              <span className="text-red-400">✖</span>
            )}
          </div>
        ))}
      </div>
      
      {/* Progress indicator */}
      <div className="mt-3 pt-3 border-t border-[var(--vscode-panel-border)]">
        <div className="flex items-center justify-between text-xs text-[var(--vscode-descriptionForeground)] mb-2">
          <span>Progress</span>
          <span>{completedSteps}/{totalSteps}</span>
        </div>
        <div className="w-full bg-[var(--vscode-input-background)] rounded-full h-1.5">
          <div 
            className="bg-gradient-to-r from-green-400 to-blue-400 h-1.5 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
