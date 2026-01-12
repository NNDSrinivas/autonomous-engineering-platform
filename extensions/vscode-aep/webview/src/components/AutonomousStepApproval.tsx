import React, { useState } from 'react';
import { resolveBackendBase } from '../api/navi/client';

interface Step {
  id: string;
  description: string;
  file_path: string;
  operation: 'create' | 'modify' | 'delete';
  content_preview: string;
  diff_preview?: string;
  status: 'pending' | 'approved' | 'rejected' | 'in_progress' | 'completed' | 'failed';
  reasoning?: string;
}

interface AutonomousStepApprovalProps {
  taskId: string;
  steps: Step[];
  currentStepIndex: number;
  workspace: string;
  onStepComplete: (result: any) => void;
  onTaskComplete: () => void;
}

export function AutonomousStepApproval({
  taskId,
  steps,
  currentStepIndex,
  workspace,
  onStepComplete,
  onTaskComplete,
}: AutonomousStepApprovalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const currentStep = steps[currentStepIndex];
  const totalSteps = steps.length;
  const completedSteps = steps.filter(s => s.status === 'completed').length;

  if (!currentStep) {
    return (
      <div className="autonomous-complete">
        <div className="success-message">
          ✅ <strong>All steps completed!</strong>
        </div>
        <div className="summary">
          {completedSteps}/{totalSteps} steps executed successfully
        </div>
        <button onClick={onTaskComplete} className="done-btn">
          Done
        </button>
      </div>
    );
  }

  const handleApprove = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${resolveBackendBase()}/api/autonomous/execute-step`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_id: taskId,
            step_id: currentStep.id,
            user_approved: true,
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to execute step');
      }

      const result = await response.json();
      console.log('[Autonomous] Step executed:', result);

      if (result.status === 'completed') {
        onStepComplete(result);
      } else if (result.status === 'failed') {
        setError(result.error || 'Step execution failed');
      }
    } catch (err) {
      console.error('[Autonomous] Execution error:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${resolveBackendBase()}/api/autonomous/execute-step`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_id: taskId,
            step_id: currentStep.id,
            user_approved: false,
          })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to reject step');
      }

      const result = await response.json();
      onStepComplete(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const getOperationIcon = (operation: string) => {
    switch (operation) {
      case 'create': return '➕';
      case 'modify': return '✏️';
      case 'delete': return '🗑️';
      default: return '📝';
    }
  };

  const getOperationColor = (operation: string) => {
    switch (operation) {
      case 'create': return '#10b981';
      case 'modify': return '#f59e0b';
      case 'delete': return '#ef4444';
      default: return '#6b7280';
    }
  };

  return (
    <div className="autonomous-step-approval" style={styles.container}>
      {/* Progress Bar */}
      <div style={styles.progressContainer}>
        <div style={styles.progressText}>
          Step {currentStepIndex + 1} of {totalSteps} ({completedSteps} completed)
        </div>
        <div style={styles.progressBar}>
          <div
            style={{
              ...styles.progressFill,
              width: `${(completedSteps / totalSteps) * 100}%`
            }}
          />
        </div>
      </div>

      {/* Current Step Info */}
      <div style={styles.stepCard}>
        <div style={styles.stepHeader}>
          <span style={{ fontSize: '1.2em' }}>
            {getOperationIcon(currentStep.operation)}
          </span>
          <span style={styles.stepTitle}>{currentStep.description}</span>
        </div>

        <div style={styles.fileInfo}>
          <div style={styles.filePath}>
            <span style={{ opacity: 0.6 }}>📁</span> {currentStep.file_path}
          </div>
          <div
            style={{
              ...styles.operationBadge,
              backgroundColor: getOperationColor(currentStep.operation)
            }}
          >
            {currentStep.operation}
          </div>
        </div>

        {currentStep.reasoning && (
          <div style={styles.reasoning}>
            <strong>Why:</strong> {currentStep.reasoning}
          </div>
        )}

        {/* Preview Toggle */}
        <button
          onClick={() => setShowPreview(!showPreview)}
          style={styles.previewToggle}
        >
          {showPreview ? '▼' : '▶'} {showPreview ? 'Hide' : 'Show'} Code Preview
        </button>

        {/* Code Preview */}
        {showPreview && (
          <div style={styles.codePreview}>
            {currentStep.diff_preview ? (
              <pre style={styles.diffCode}>{currentStep.diff_preview}</pre>
            ) : (
              <pre style={styles.code}>{currentStep.content_preview}</pre>
            )}
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div style={styles.error}>
            ❌ <strong>Error:</strong> {error}
          </div>
        )}

        {/* Action Buttons */}
        <div style={styles.actions}>
          <button
            onClick={handleApprove}
            disabled={loading}
            style={{
              ...styles.button,
              ...styles.approveButton,
              ...(loading ? styles.buttonDisabled : {})
            }}
          >
            {loading ? '⏳ Executing...' : '✅ Approve & Execute'}
          </button>

          <button
            onClick={handleReject}
            disabled={loading}
            style={{
              ...styles.button,
              ...styles.rejectButton,
              ...(loading ? styles.buttonDisabled : {})
            }}
          >
            ❌ Reject
          </button>

          <button
            onClick={() => window.open(`file://${workspace}/${currentStep.file_path}`)}
            disabled={loading}
            style={{
              ...styles.button,
              ...styles.viewButton,
              ...(loading ? styles.buttonDisabled : {})
            }}
          >
            👁️ View File
          </button>
        </div>

        {/* Help Text */}
        <div style={styles.helpText}>
          💡 Tip: Review the code preview before approving. All changes are backed up in git.
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    margin: '16px 0',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  progressContainer: {
    marginBottom: '16px',
  },
  progressText: {
    fontSize: '0.9em',
    color: '#6b7280',
    marginBottom: '8px',
  },
  progressBar: {
    height: '8px',
    backgroundColor: '#e5e7eb',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#10b981',
    transition: 'width 0.3s ease',
  },
  stepCard: {
    backgroundColor: '#1e1e1e',
    border: '1px solid #333',
    borderRadius: '8px',
    padding: '16px',
  },
  stepHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '12px',
  },
  stepTitle: {
    fontSize: '1.1em',
    fontWeight: 'bold',
    color: '#fff',
  },
  fileInfo: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
    padding: '8px',
    backgroundColor: '#2a2a2a',
    borderRadius: '4px',
  },
  filePath: {
    fontFamily: 'monospace',
    fontSize: '0.9em',
    color: '#a3a3a3',
  },
  operationBadge: {
    padding: '4px 8px',
    borderRadius: '4px',
    fontSize: '0.8em',
    fontWeight: 'bold',
    color: '#fff',
    textTransform: 'uppercase' as const,
  },
  reasoning: {
    padding: '8px',
    backgroundColor: '#2a2a2a',
    borderRadius: '4px',
    marginBottom: '12px',
    fontSize: '0.9em',
    color: '#a3a3a3',
  },
  previewToggle: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    cursor: 'pointer',
    padding: '8px 0',
    fontSize: '0.9em',
    textAlign: 'left' as const,
  },
  codePreview: {
    marginTop: '12px',
    marginBottom: '12px',
    maxHeight: '300px',
    overflow: 'auto',
    backgroundColor: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '4px',
  },
  code: {
    margin: 0,
    padding: '12px',
    fontSize: '0.85em',
    fontFamily: 'monospace',
    color: '#d4d4d4',
    whiteSpace: 'pre-wrap' as const,
  },
  diffCode: {
    margin: 0,
    padding: '12px',
    fontSize: '0.85em',
    fontFamily: 'monospace',
    color: '#d4d4d4',
    whiteSpace: 'pre' as const,
  },
  error: {
    padding: '12px',
    backgroundColor: '#7f1d1d',
    border: '1px solid #991b1b',
    borderRadius: '4px',
    color: '#fca5a5',
    marginBottom: '12px',
  },
  actions: {
    display: 'flex',
    gap: '8px',
    marginTop: '16px',
    flexWrap: 'wrap' as const,
  },
  button: {
    padding: '10px 16px',
    border: 'none',
    borderRadius: '6px',
    fontSize: '0.9em',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s',
    flex: '1',
    minWidth: '120px',
  },
  approveButton: {
    backgroundColor: '#10b981',
    color: '#fff',
  },
  rejectButton: {
    backgroundColor: '#ef4444',
    color: '#fff',
  },
  viewButton: {
    backgroundColor: '#6b7280',
    color: '#fff',
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  helpText: {
    marginTop: '12px',
    fontSize: '0.85em',
    color: '#6b7280',
    fontStyle: 'italic' as const,
  },
};
