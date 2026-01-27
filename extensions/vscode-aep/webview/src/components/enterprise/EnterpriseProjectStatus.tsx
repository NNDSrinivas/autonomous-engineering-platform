/**
 * Enterprise Project Status Component
 *
 * Displays the current status of an enterprise project in the VS Code chat panel.
 * Shows progress, current task, milestones, and pending human gates.
 */

import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Circle,
  Clock,
  GitBranch,
  Layers,
  Loader2,
  Pause,
  Play,
  Target,
  XCircle,
} from 'lucide-react';
import './EnterpriseProjectStatus.css';

export interface ProjectMilestone {
  id: string;
  title: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  progress: number;
  tasksCompleted: number;
  totalTasks: number;
}

export interface PendingGate {
  id: string;
  type: 'architecture' | 'security' | 'cost' | 'deployment' | 'milestone';
  title: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  blocksProgress: boolean;
  createdAt: string;
}

export interface EnterpriseProjectData {
  id: string;
  name: string;
  description: string;
  status: 'planning' | 'active' | 'paused' | 'blocked' | 'completed' | 'failed';
  progress: number;
  currentPhase: string;
  currentTask?: {
    id: string;
    title: string;
    status: string;
  };
  milestones: ProjectMilestone[];
  pendingGates: PendingGate[];
  stats: {
    totalTasks: number;
    completedTasks: number;
    failedTasks: number;
    activeAgents: number;
    iterationCount: number;
    runtimeHours: number;
  };
  startedAt?: string;
  estimatedCompletionDate?: string;
}

interface EnterpriseProjectStatusProps {
  project: EnterpriseProjectData;
  onPause?: () => void;
  onResume?: () => void;
  onViewGate?: (gateId: string) => void;
  onViewDetails?: () => void;
  compact?: boolean;
}

export const EnterpriseProjectStatus: React.FC<EnterpriseProjectStatusProps> = ({
  project,
  onPause,
  onResume,
  onViewGate,
  onViewDetails,
  compact = false,
}) => {
  const [expanded, setExpanded] = useState(!compact);

  const statusConfig = {
    planning: { icon: Clock, color: 'status-planning', label: 'Planning' },
    active: { icon: Activity, color: 'status-active', label: 'Active' },
    paused: { icon: Pause, color: 'status-paused', label: 'Paused' },
    blocked: { icon: AlertTriangle, color: 'status-blocked', label: 'Blocked' },
    completed: { icon: CheckCircle, color: 'status-completed', label: 'Completed' },
    failed: { icon: XCircle, color: 'status-failed', label: 'Failed' },
  };

  const gateTypeIcons = {
    architecture: Layers,
    security: AlertTriangle,
    cost: Target,
    deployment: GitBranch,
    milestone: CheckCircle,
  };

  const config = statusConfig[project.status];
  const StatusIcon = config.icon;

  const formatRuntime = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    return `${(hours / 24).toFixed(1)}d`;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className={`enterprise-project-status ${config.color} ${compact ? 'compact' : ''}`}>
      {/* Header */}
      <div className="project-header" onClick={() => setExpanded(!expanded)}>
        <div className="project-title-row">
          <StatusIcon className="status-icon" size={18} />
          <span className="project-name">{project.name}</span>
          <span className={`status-badge ${config.color}`}>{config.label}</span>
        </div>

        {/* Progress Bar */}
        <div className="progress-container">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${project.progress}%` }}
            />
          </div>
          <span className="progress-text">{project.progress}%</span>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="project-details">
          {/* Current Task */}
          {project.currentTask && (
            <div className="current-task">
              <span className="section-label">Current Task</span>
              <div className="task-info">
                <Loader2 className="spinning" size={14} />
                <span className="task-title">{project.currentTask.title}</span>
              </div>
            </div>
          )}

          {/* Stats Row */}
          <div className="stats-row">
            <div className="stat">
              <span className="stat-value">{project.stats.completedTasks}</span>
              <span className="stat-label">/ {project.stats.totalTasks} tasks</span>
            </div>
            <div className="stat">
              <span className="stat-value">{project.stats.activeAgents}</span>
              <span className="stat-label">agents</span>
            </div>
            <div className="stat">
              <span className="stat-value">{formatRuntime(project.stats.runtimeHours)}</span>
              <span className="stat-label">runtime</span>
            </div>
            <div className="stat">
              <span className="stat-value">{project.stats.iterationCount}</span>
              <span className="stat-label">iterations</span>
            </div>
          </div>

          {/* Pending Gates */}
          {project.pendingGates.length > 0 && (
            <div className="pending-gates">
              <span className="section-label">
                <AlertTriangle size={14} />
                Pending Decisions ({project.pendingGates.length})
              </span>
              <div className="gates-list">
                {project.pendingGates.slice(0, 3).map((gate) => {
                  const GateIcon = gateTypeIcons[gate.type];
                  return (
                    <div
                      key={gate.id}
                      className={`gate-item ${gate.blocksProgress ? 'blocking' : ''}`}
                      onClick={() => onViewGate?.(gate.id)}
                    >
                      <GateIcon size={14} />
                      <span className="gate-title">{gate.title}</span>
                      {gate.blocksProgress && (
                        <span className="blocking-badge">Blocking</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Milestones */}
          {project.milestones.length > 0 && (
            <div className="milestones">
              <span className="section-label">Milestones</span>
              <div className="milestones-list">
                {project.milestones.map((milestone) => (
                  <div key={milestone.id} className={`milestone-item ${milestone.status}`}>
                    {milestone.status === 'completed' ? (
                      <CheckCircle size={14} className="milestone-icon completed" />
                    ) : milestone.status === 'in_progress' ? (
                      <Loader2 size={14} className="milestone-icon spinning" />
                    ) : milestone.status === 'blocked' ? (
                      <AlertTriangle size={14} className="milestone-icon blocked" />
                    ) : (
                      <Circle size={14} className="milestone-icon pending" />
                    )}
                    <span className="milestone-title">{milestone.title}</span>
                    <span className="milestone-progress">
                      {milestone.tasksCompleted}/{milestone.totalTasks}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="project-actions">
            {project.status === 'active' && onPause && (
              <button className="action-button secondary" onClick={onPause}>
                <Pause size={14} />
                Pause
              </button>
            )}
            {project.status === 'paused' && onResume && (
              <button className="action-button primary" onClick={onResume}>
                <Play size={14} />
                Resume
              </button>
            )}
            {onViewDetails && (
              <button className="action-button secondary" onClick={onViewDetails}>
                View Details
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default EnterpriseProjectStatus;
