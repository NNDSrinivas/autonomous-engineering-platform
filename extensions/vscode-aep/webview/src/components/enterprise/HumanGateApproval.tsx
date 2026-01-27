/**
 * HumanGateApproval Component
 *
 * Inline approval dialog for human checkpoint gates in enterprise projects.
 * Displays gate details, options with trade-offs, and approve/reject actions.
 */

import React, { useState } from 'react';
import './HumanGateApproval.css';

export type GateType =
  | 'architecture_review'
  | 'security_review'
  | 'cost_approval'
  | 'deployment_approval'
  | 'milestone_review';

export interface GateOption {
  id: string;
  label: string;
  description: string;
  tradeOffs?: string[];
  recommended?: boolean;
  estimatedCost?: string;
  riskLevel?: 'low' | 'medium' | 'high';
}

export interface HumanGateData {
  id: string;
  projectId: string;
  projectName: string;
  gateType: GateType;
  title: string;
  description: string;
  context?: string;
  options: GateOption[];
  blocksProgress: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
  createdAt: string;
  metadata?: {
    affectedFiles?: string[];
    estimatedImpact?: string;
    relatedTasks?: string[];
  };
}

export interface HumanGateApprovalProps {
  gate: HumanGateData;
  onDecision: (gateId: string, decision: GateDecision) => void;
  onDismiss?: (gateId: string) => void;
  isProcessing?: boolean;
}

export interface GateDecision {
  approved: boolean;
  selectedOptionId?: string;
  reason?: string;
  decidedAt: string;
}

const GATE_TYPE_CONFIG: Record<GateType, { icon: string; label: string; color: string }> = {
  architecture_review: { icon: '🏗️', label: 'Architecture Review', color: 'purple' },
  security_review: { icon: '🔒', label: 'Security Review', color: 'red' },
  cost_approval: { icon: '💰', label: 'Cost Approval', color: 'yellow' },
  deployment_approval: { icon: '🚀', label: 'Deployment Approval', color: 'blue' },
  milestone_review: { icon: '🎯', label: 'Milestone Review', color: 'green' },
};

const PRIORITY_CONFIG: Record<string, { label: string; className: string }> = {
  low: { label: 'Low', className: 'priority-low' },
  medium: { label: 'Medium', className: 'priority-medium' },
  high: { label: 'High', className: 'priority-high' },
  critical: { label: 'Critical', className: 'priority-critical' },
};

const RISK_CONFIG: Record<string, { label: string; className: string }> = {
  low: { label: 'Low Risk', className: 'risk-low' },
  medium: { label: 'Medium Risk', className: 'risk-medium' },
  high: { label: 'High Risk', className: 'risk-high' },
};

export const HumanGateApproval: React.FC<HumanGateApprovalProps> = ({
  gate,
  onDecision,
  onDismiss,
  isProcessing = false,
}) => {
  const [selectedOption, setSelectedOption] = useState<string | null>(
    gate.options.find(o => o.recommended)?.id || null
  );
  const [reason, setReason] = useState('');
  const [showDetails, setShowDetails] = useState(true);

  const gateConfig = GATE_TYPE_CONFIG[gate.gateType];
  const priorityConfig = PRIORITY_CONFIG[gate.priority];

  const handleApprove = () => {
    if (gate.options.length > 0 && !selectedOption) {
      return; // Require option selection if options exist
    }

    onDecision(gate.id, {
      approved: true,
      selectedOptionId: selectedOption || undefined,
      reason: reason || undefined,
      decidedAt: new Date().toISOString(),
    });
  };

  const handleReject = () => {
    onDecision(gate.id, {
      approved: false,
      reason: reason || 'Rejected by user',
      decidedAt: new Date().toISOString(),
    });
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className={`human-gate-approval gate-${gateConfig.color} ${gate.blocksProgress ? 'blocking' : ''}`}>
      {/* Header */}
      <div className="gate-header">
        <div className="gate-title-row">
          <span className="gate-icon">{gateConfig.icon}</span>
          <span className="gate-type-label">{gateConfig.label}</span>
          <span className={`priority-badge ${priorityConfig.className}`}>
            {priorityConfig.label}
          </span>
          {gate.blocksProgress && (
            <span className="blocking-badge">Blocking</span>
          )}
        </div>
        <h3 className="gate-title">{gate.title}</h3>
        <div className="gate-meta">
          <span className="project-name">{gate.projectName}</span>
          <span className="gate-time">{formatDate(gate.createdAt)}</span>
        </div>
      </div>

      {/* Description */}
      <div className="gate-description">
        <p>{gate.description}</p>
        {gate.context && (
          <div className="gate-context">
            <button
              className="context-toggle"
              onClick={() => setShowDetails(!showDetails)}
            >
              {showDetails ? '▼' : '▶'} Additional Context
            </button>
            {showDetails && (
              <div className="context-content">
                <pre>{gate.context}</pre>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Metadata */}
      {gate.metadata && (
        <div className="gate-metadata">
          {gate.metadata.affectedFiles && gate.metadata.affectedFiles.length > 0 && (
            <div className="metadata-section">
              <span className="metadata-label">Affected Files:</span>
              <div className="affected-files">
                {gate.metadata.affectedFiles.slice(0, 5).map((file, idx) => (
                  <code key={idx} className="file-path">{file}</code>
                ))}
                {gate.metadata.affectedFiles.length > 5 && (
                  <span className="more-files">
                    +{gate.metadata.affectedFiles.length - 5} more
                  </span>
                )}
              </div>
            </div>
          )}
          {gate.metadata.estimatedImpact && (
            <div className="metadata-section">
              <span className="metadata-label">Estimated Impact:</span>
              <span className="metadata-value">{gate.metadata.estimatedImpact}</span>
            </div>
          )}
        </div>
      )}

      {/* Options */}
      {gate.options.length > 0 && (
        <div className="gate-options">
          <div className="options-label">Select an option:</div>
          <div className="options-list">
            {gate.options.map((option) => (
              <div
                key={option.id}
                className={`option-card ${selectedOption === option.id ? 'selected' : ''} ${option.recommended ? 'recommended' : ''}`}
                onClick={() => !isProcessing && setSelectedOption(option.id)}
              >
                <div className="option-header">
                  <div className="option-radio">
                    <span className={`radio-dot ${selectedOption === option.id ? 'active' : ''}`} />
                  </div>
                  <span className="option-label">{option.label}</span>
                  {option.recommended && (
                    <span className="recommended-badge">Recommended</span>
                  )}
                  {option.riskLevel && (
                    <span className={`risk-badge ${RISK_CONFIG[option.riskLevel].className}`}>
                      {RISK_CONFIG[option.riskLevel].label}
                    </span>
                  )}
                </div>
                <p className="option-description">{option.description}</p>
                {option.tradeOffs && option.tradeOffs.length > 0 && (
                  <div className="option-tradeoffs">
                    <span className="tradeoffs-label">Trade-offs:</span>
                    <ul>
                      {option.tradeOffs.map((tradeoff, idx) => (
                        <li key={idx}>{tradeoff}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {option.estimatedCost && (
                  <div className="option-cost">
                    <span className="cost-label">Est. Cost:</span>
                    <span className="cost-value">{option.estimatedCost}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reason Input */}
      <div className="gate-reason">
        <label htmlFor={`reason-${gate.id}`}>Decision Reason (optional):</label>
        <textarea
          id={`reason-${gate.id}`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Add a note about your decision..."
          disabled={isProcessing}
          rows={2}
        />
      </div>

      {/* Actions */}
      <div className="gate-actions">
        <button
          className="action-button reject"
          onClick={handleReject}
          disabled={isProcessing}
        >
          {isProcessing ? 'Processing...' : '✕ Reject'}
        </button>
        <button
          className="action-button approve"
          onClick={handleApprove}
          disabled={isProcessing || (gate.options.length > 0 && !selectedOption)}
        >
          {isProcessing ? 'Processing...' : '✓ Approve'}
        </button>
        {onDismiss && !gate.blocksProgress && (
          <button
            className="action-button dismiss"
            onClick={() => onDismiss(gate.id)}
            disabled={isProcessing}
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
};

/**
 * Compact version for notification-style display
 */
export interface GateNotificationProps {
  gate: HumanGateData;
  onClick: (gateId: string) => void;
}

export const GateNotification: React.FC<GateNotificationProps> = ({ gate, onClick }) => {
  const gateConfig = GATE_TYPE_CONFIG[gate.gateType];

  return (
    <div
      className={`gate-notification gate-${gateConfig.color} ${gate.blocksProgress ? 'blocking' : ''}`}
      onClick={() => onClick(gate.id)}
    >
      <span className="notification-icon">{gateConfig.icon}</span>
      <div className="notification-content">
        <span className="notification-type">{gateConfig.label}</span>
        <span className="notification-title">{gate.title}</span>
      </div>
      {gate.blocksProgress && (
        <span className="notification-blocking">Blocking</span>
      )}
      <span className="notification-arrow">→</span>
    </div>
  );
};

/**
 * List component for multiple pending gates
 */
export interface PendingGatesListProps {
  gates: HumanGateData[];
  onSelectGate: (gateId: string) => void;
}

export const PendingGatesList: React.FC<PendingGatesListProps> = ({ gates, onSelectGate }) => {
  if (gates.length === 0) {
    return null;
  }

  const blockingGates = gates.filter(g => g.blocksProgress);
  const nonBlockingGates = gates.filter(g => !g.blocksProgress);

  return (
    <div className="pending-gates-list">
      <div className="gates-header">
        <span className="gates-icon">⚠️</span>
        <span className="gates-title">
          {gates.length} Pending Decision{gates.length !== 1 ? 's' : ''}
        </span>
        {blockingGates.length > 0 && (
          <span className="blocking-count">{blockingGates.length} blocking</span>
        )}
      </div>
      <div className="gates-list">
        {blockingGates.map(gate => (
          <GateNotification key={gate.id} gate={gate} onClick={onSelectGate} />
        ))}
        {nonBlockingGates.map(gate => (
          <GateNotification key={gate.id} gate={gate} onClick={onSelectGate} />
        ))}
      </div>
    </div>
  );
};

export default HumanGateApproval;
