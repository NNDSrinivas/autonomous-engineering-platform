/**
 * Execution Progress Component
 *
 * Shows real-time progress of deployments, migrations, and other operations
 * with streaming logs and status updates.
 */

import React, { useState, useEffect, useRef } from 'react';
import './ExecutionProgress.css';

export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

export interface ExecutionLog {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
}

export interface ExecutionProgressData {
  id: string;
  operation: string;
  status: ExecutionStatus;
  progress: number; // 0-100
  currentStep: string;
  steps: {
    name: string;
    status: ExecutionStatus;
    duration?: number;
  }[];
  logs: ExecutionLog[];
  startedAt?: string;
  completedAt?: string;
  error?: string;
  result?: {
    deploymentUrl?: string;
    outputs?: Record<string, unknown>;
    rollbackCommand?: string;
  };
}

interface ExecutionProgressProps {
  execution: ExecutionProgressData;
  onCancel?: (id: string) => void;
  onRetry?: (id: string) => void;
  onClose?: () => void;
  minimized?: boolean;
  onToggleMinimize?: () => void;
}

export const ExecutionProgress: React.FC<ExecutionProgressProps> = ({
  execution,
  onCancel,
  onRetry,
  onClose,
  minimized = false,
  onToggleMinimize,
}) => {
  const [showLogs, setShowLogs] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  const { status, progress, currentStep, steps, logs, error, result } = execution;

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Handle scroll to detect if user scrolled up
  const handleLogsScroll = () => {
    if (logsContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
      const isAtBottom = scrollHeight - scrollTop <= clientHeight + 50;
      setAutoScroll(isAtBottom);
    }
  };

  // Calculate elapsed time
  const getElapsedTime = () => {
    if (!execution.startedAt) return '0s';
    const start = new Date(execution.startedAt).getTime();
    const end = execution.completedAt
      ? new Date(execution.completedAt).getTime()
      : Date.now();
    const seconds = Math.floor((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  // Get status icon
  const getStatusIcon = (stepStatus: ExecutionStatus) => {
    switch (stepStatus) {
      case 'success':
        return <span className="status-icon success">✓</span>;
      case 'failed':
        return <span className="status-icon failed">✗</span>;
      case 'running':
        return <span className="status-icon running">⟳</span>;
      case 'cancelled':
        return <span className="status-icon cancelled">⊘</span>;
      default:
        return <span className="status-icon pending">○</span>;
    }
  };

  // Get log level icon
  const getLogIcon = (level: ExecutionLog['level']) => {
    switch (level) {
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'debug':
        return '🔍';
      default:
        return 'ℹ️';
    }
  };

  if (minimized) {
    return (
      <div className={`execution-progress-minimized ${status}`} onClick={onToggleMinimize}>
        <div className="minimized-content">
          {getStatusIcon(status)}
          <span className="minimized-operation">{execution.operation}</span>
          <span className="minimized-progress">{progress}%</span>
          {status === 'running' && (
            <div className="minimized-bar">
              <div className="minimized-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`execution-progress ${status}`}>
      {/* Header */}
      <div className="progress-header">
        <div className="header-left">
          {getStatusIcon(status)}
          <div className="header-info">
            <h3 className="operation-title">{execution.operation}</h3>
            <span className="current-step">{currentStep}</span>
          </div>
        </div>
        <div className="header-right">
          <span className="elapsed-time">{getElapsedTime()}</span>
          {onToggleMinimize && (
            <button className="btn-minimize" onClick={onToggleMinimize} title="Minimize">
              ─
            </button>
          )}
          {onClose && status !== 'running' && (
            <button className="btn-close" onClick={onClose} title="Close">
              ×
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="progress-bar-container">
        <div className="progress-bar">
          <div
            className={`progress-bar-fill ${status}`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="progress-percentage">{progress}%</span>
      </div>

      {/* Steps */}
      <div className="steps-container">
        {steps.map((step, index) => (
          <div key={index} className={`step-item ${step.status}`}>
            {getStatusIcon(step.status)}
            <span className="step-name">{step.name}</span>
            {step.duration !== undefined && (
              <span className="step-duration">{step.duration}s</span>
            )}
          </div>
        ))}
      </div>

      {/* Error Message */}
      {error && (
        <div className="error-container">
          <div className="error-header">
            <span className="error-icon">❌</span>
            <strong>Error</strong>
          </div>
          <pre className="error-message">{error}</pre>
        </div>
      )}

      {/* Success Result */}
      {status === 'success' && result && (
        <div className="result-container">
          {result.deploymentUrl && (
            <div className="result-item">
              <span className="result-label">🌐 Deployment URL:</span>
              <a
                href={result.deploymentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="result-link"
              >
                {result.deploymentUrl}
              </a>
            </div>
          )}
          {result.rollbackCommand && (
            <div className="result-item">
              <span className="result-label">↩️ Rollback:</span>
              <code className="result-code">{result.rollbackCommand}</code>
            </div>
          )}
          {result.outputs && Object.keys(result.outputs).length > 0 && (
            <div className="result-item">
              <span className="result-label">📤 Outputs:</span>
              <pre className="result-outputs">
                {JSON.stringify(result.outputs, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Logs Toggle */}
      <button
        className="logs-toggle"
        onClick={() => setShowLogs(!showLogs)}
      >
        {showLogs ? '▼ Hide Logs' : '▶ Show Logs'} ({logs.length})
      </button>

      {/* Logs */}
      {showLogs && (
        <div
          className="logs-container"
          ref={logsContainerRef}
          onScroll={handleLogsScroll}
        >
          {logs.map((log, index) => (
            <div key={index} className={`log-entry ${log.level}`}>
              <span className="log-timestamp">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className="log-icon">{getLogIcon(log.level)}</span>
              <span className="log-message">{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
          {!autoScroll && (
            <button
              className="scroll-to-bottom"
              onClick={() => {
                setAutoScroll(true);
                logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              ↓ Scroll to bottom
            </button>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="progress-actions">
        {status === 'running' && onCancel && (
          <button className="btn-cancel" onClick={() => onCancel(execution.id)}>
            Cancel
          </button>
        )}
        {status === 'failed' && onRetry && (
          <button className="btn-retry" onClick={() => onRetry(execution.id)}>
            Retry
          </button>
        )}
        {status === 'success' && result?.deploymentUrl && (
          <a
            href={result.deploymentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-open"
          >
            Open Deployment
          </a>
        )}
      </div>
    </div>
  );
};

export default ExecutionProgress;
