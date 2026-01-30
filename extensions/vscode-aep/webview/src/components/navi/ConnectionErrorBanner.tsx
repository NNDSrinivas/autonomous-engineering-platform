/**
 * ConnectionErrorBanner - Graceful error handling UI for stream interruptions
 *
 * Shows when streaming connection is lost with options to:
 * - Retry the request
 * - Resume from checkpoint
 * - Dismiss and start fresh
 */

import React, { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, X, Clock, FileText, Terminal } from 'lucide-react';
import { TaskCheckpoint } from '../../utils/chatSessions';

interface ConnectionErrorBannerProps {
  error: string;
  checkpoint?: TaskCheckpoint | null;
  onRetry: () => void;
  onResume?: () => void;
  onDismiss: () => void;
  retryCount?: number;
  maxRetries?: number;
  isRetrying?: boolean;
  nextRetryIn?: number; // seconds until next auto-retry
}

export const ConnectionErrorBanner: React.FC<ConnectionErrorBannerProps> = ({
  error,
  checkpoint,
  onRetry,
  onResume,
  onDismiss,
  retryCount = 0,
  maxRetries = 3,
  isRetrying = false,
  nextRetryIn,
}) => {
  const [countdown, setCountdown] = useState(nextRetryIn || 0);

  // Countdown timer for auto-retry
  useEffect(() => {
    if (nextRetryIn && nextRetryIn > 0) {
      setCountdown(nextRetryIn);
      const interval = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            clearInterval(interval);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [nextRetryIn]);

  const canRetry = retryCount < maxRetries;
  const hasCheckpoint = checkpoint && checkpoint.status === 'interrupted';

  // Format the progress info from checkpoint
  const getProgressInfo = () => {
    if (!checkpoint) return null;

    const completedSteps = checkpoint.steps.filter(s => s.status === 'completed').length;
    const filesModified = checkpoint.modifiedFiles.length;
    const commandsRun = checkpoint.executedCommands.length;

    return {
      completedSteps,
      totalSteps: checkpoint.totalSteps,
      filesModified,
      commandsRun,
      partialContent: checkpoint.partialContent?.length || 0,
    };
  };

  const progress = getProgressInfo();

  return (
    <div className="navi-connection-error-banner">
      <div className="navi-error-banner-header">
        <div className="navi-error-banner-icon">
          <AlertTriangle size={20} />
        </div>
        <div className="navi-error-banner-content">
          <div className="navi-error-banner-title">
            Connection Lost
          </div>
          <div className="navi-error-banner-message">
            {error || 'The connection to NAVI was interrupted.'}
          </div>
        </div>
        <button
          className="navi-error-banner-close"
          onClick={onDismiss}
          title="Dismiss"
          aria-label="Dismiss error"
        >
          <X size={16} />
        </button>
      </div>

      {/* Progress saved indicator */}
      {hasCheckpoint && progress && (
        <div className="navi-error-banner-progress">
          <div className="navi-error-progress-title">
            <Clock size={14} />
            Progress saved - you can resume where you left off
          </div>
          <div className="navi-error-progress-stats">
            {progress.totalSteps > 0 && (
              <span className="navi-error-stat">
                <span className="navi-error-stat-value">{progress.completedSteps}/{progress.totalSteps}</span>
                <span className="navi-error-stat-label">steps</span>
              </span>
            )}
            {progress.filesModified > 0 && (
              <span className="navi-error-stat">
                <FileText size={12} />
                <span className="navi-error-stat-value">{progress.filesModified}</span>
                <span className="navi-error-stat-label">files saved</span>
              </span>
            )}
            {progress.commandsRun > 0 && (
              <span className="navi-error-stat">
                <Terminal size={12} />
                <span className="navi-error-stat-value">{progress.commandsRun}</span>
                <span className="navi-error-stat-label">commands</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="navi-error-banner-actions">
        {hasCheckpoint && onResume && (
          <button
            className="navi-error-action navi-error-action--resume"
            onClick={onResume}
            disabled={isRetrying}
          >
            <RefreshCw size={14} className={isRetrying ? 'navi-spin' : ''} />
            Resume Task
          </button>
        )}

        {canRetry && (
          <button
            className="navi-error-action navi-error-action--retry"
            onClick={onRetry}
            disabled={isRetrying}
          >
            <RefreshCw size={14} className={isRetrying ? 'navi-spin' : ''} />
            {isRetrying ? 'Retrying...' : countdown > 0 ? `Retry (${countdown}s)` : 'Retry Now'}
          </button>
        )}

        <button
          className="navi-error-action navi-error-action--dismiss"
          onClick={onDismiss}
        >
          Start Fresh
        </button>
      </div>

      {/* Retry info */}
      {retryCount > 0 && (
        <div className="navi-error-banner-retry-info">
          Retry attempt {retryCount} of {maxRetries}
          {!canRetry && ' - Maximum retries reached'}
        </div>
      )}

      <style>{`
        .navi-connection-error-banner {
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(185, 28, 28, 0.1) 100%);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 12px;
          padding: 16px;
          margin: 12px 0;
          backdrop-filter: blur(8px);
        }

        .navi-error-banner-header {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }

        .navi-error-banner-icon {
          color: #ef4444;
          flex-shrink: 0;
          margin-top: 2px;
        }

        .navi-error-banner-content {
          flex: 1;
          min-width: 0;
        }

        .navi-error-banner-title {
          font-weight: 600;
          color: #fca5a5;
          font-size: 14px;
          margin-bottom: 4px;
        }

        .navi-error-banner-message {
          color: rgba(255, 255, 255, 0.7);
          font-size: 13px;
          line-height: 1.4;
        }

        .navi-error-banner-close {
          background: transparent;
          border: none;
          color: rgba(255, 255, 255, 0.5);
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          transition: all 0.2s;
        }

        .navi-error-banner-close:hover {
          background: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.8);
        }

        .navi-error-banner-progress {
          margin-top: 12px;
          padding: 12px;
          background: rgba(34, 197, 94, 0.1);
          border: 1px solid rgba(34, 197, 94, 0.2);
          border-radius: 8px;
        }

        .navi-error-progress-title {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #4ade80;
          font-size: 13px;
          font-weight: 500;
          margin-bottom: 8px;
        }

        .navi-error-progress-stats {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
        }

        .navi-error-stat {
          display: flex;
          align-items: center;
          gap: 4px;
          color: rgba(255, 255, 255, 0.6);
          font-size: 12px;
        }

        .navi-error-stat-value {
          color: rgba(255, 255, 255, 0.9);
          font-weight: 600;
        }

        .navi-error-stat-label {
          color: rgba(255, 255, 255, 0.5);
        }

        .navi-error-banner-actions {
          display: flex;
          gap: 8px;
          margin-top: 16px;
        }

        .navi-error-action {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 16px;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
        }

        .navi-error-action:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .navi-error-action--resume {
          background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
          color: white;
        }

        .navi-error-action--resume:hover:not(:disabled) {
          background: linear-gradient(135deg, #9f7aea 0%, #8b5cf6 100%);
          transform: translateY(-1px);
        }

        .navi-error-action--retry {
          background: rgba(59, 130, 246, 0.2);
          color: #60a5fa;
          border: 1px solid rgba(59, 130, 246, 0.3);
        }

        .navi-error-action--retry:hover:not(:disabled) {
          background: rgba(59, 130, 246, 0.3);
        }

        .navi-error-action--dismiss {
          background: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.7);
        }

        .navi-error-action--dismiss:hover {
          background: rgba(255, 255, 255, 0.15);
          color: rgba(255, 255, 255, 0.9);
        }

        .navi-error-banner-retry-info {
          margin-top: 12px;
          font-size: 11px;
          color: rgba(255, 255, 255, 0.4);
          text-align: center;
        }

        .navi-spin {
          animation: navi-spin 1s linear infinite;
        }

        @keyframes navi-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default ConnectionErrorBanner;
