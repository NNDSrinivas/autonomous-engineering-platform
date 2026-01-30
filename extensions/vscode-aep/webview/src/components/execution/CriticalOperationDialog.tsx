/**
 * Critical Operation Confirmation Dialog
 *
 * A safety dialog that shows warnings before executing dangerous operations.
 * Supports multiple risk levels with appropriate visual styling.
 */

import React, { useState, useEffect, useCallback } from 'react';
import './CriticalOperationDialog.css';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface ExecutionWarning {
  level: RiskLevel;
  title: string;
  message: string;
  details?: string[];
  mitigation?: string;
  rollbackAvailable?: boolean;
  rollbackInstructions?: string;
}

export interface ExecutionRequest {
  id: string;
  operation: string;
  category: string;
  riskLevel: RiskLevel;
  description: string;
  warnings: ExecutionWarning[];
  parameters: Record<string, unknown>;
  estimatedDuration?: string;
  affectedResources: string[];
  rollbackPlan?: string;
  requiresConfirmation: boolean;
  confirmationPhrase?: string;
  expiresAt?: string;
  uiConfig: {
    color: string;
    icon: string;
    bannerStyle: string;
    requireScroll: boolean;
    buttonStyle: string;
    confirmDelaySeconds?: number;
    requireCheckbox?: boolean;
    checkboxText?: string;
    pulsingBorder?: boolean;
  };
}

interface CriticalOperationDialogProps {
  request: ExecutionRequest;
  onApprove: (requestId: string, confirmationInput?: string) => void;
  onReject: (requestId: string, reason?: string) => void;
  isLoading?: boolean;
}

export const CriticalOperationDialog: React.FC<CriticalOperationDialogProps> = ({
  request,
  onApprove,
  onReject,
  isLoading = false,
}) => {
  const [confirmationInput, setConfirmationInput] = useState('');
  const [checkboxChecked, setCheckboxChecked] = useState(false);
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false);
  const [countdown, setCountdown] = useState(request.uiConfig.confirmDelaySeconds || 0);
  const [showDetails, setShowDetails] = useState(false);

  const { uiConfig, warnings, riskLevel } = request;

  // Countdown timer for critical operations
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Handle scroll detection
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement;
    const isAtBottom = target.scrollHeight - target.scrollTop <= target.clientHeight + 10;
    if (isAtBottom) {
      setHasScrolledToBottom(true);
    }
  }, []);

  // Check if approval is allowed
  const canApprove = () => {
    if (isLoading) return false;
    if (uiConfig.requireScroll && !hasScrolledToBottom) return false;
    if (uiConfig.requireCheckbox && !checkboxChecked) return false;
    if (request.confirmationPhrase && confirmationInput.toUpperCase() !== request.confirmationPhrase.toUpperCase()) return false;
    if (countdown > 0) return false;
    return true;
  };

  // Get icon based on risk level
  const getIcon = () => {
    switch (riskLevel) {
      case 'critical':
        return (
          <svg className="icon critical" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 2 22 22 22" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <circle cx="12" cy="17" r="1" />
          </svg>
        );
      case 'high':
        return (
          <svg className="icon high" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        );
      case 'medium':
        return (
          <svg className="icon medium" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        );
      default:
        return (
          <svg className="icon low" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        );
    }
  };

  return (
    <div className={`critical-operation-overlay ${riskLevel}`}>
      <div
        className={`critical-operation-dialog ${riskLevel} ${uiConfig.pulsingBorder ? 'pulsing' : ''}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        aria-describedby="dialog-description"
      >
        {/* Header */}
        <div className={`dialog-header ${riskLevel}`}>
          <div className="header-icon">
            {getIcon()}
          </div>
          <div className="header-content">
            <h2 id="dialog-title" className="dialog-title">
              {riskLevel === 'critical' ? '⚠️ CRITICAL OPERATION ⚠️' :
               riskLevel === 'high' ? '⚠️ High Risk Operation' :
               riskLevel === 'medium' ? 'Confirm Operation' :
               'Confirm Action'}
            </h2>
            <p className="operation-name">{request.operation}</p>
          </div>
        </div>

        {/* Risk Banner */}
        <div className={`risk-banner ${riskLevel}`}>
          <span className="risk-label">Risk Level:</span>
          <span className={`risk-badge ${riskLevel}`}>
            {riskLevel.toUpperCase()}
          </span>
          <span className="category-badge">{request.category}</span>
        </div>

        {/* Scrollable Content */}
        <div
          className="dialog-content"
          onScroll={handleScroll}
        >
          {/* Description */}
          <p id="dialog-description" className="description">
            {request.description}
          </p>

          {/* Warnings */}
          <div className="warnings-section">
            <h3>Warnings</h3>
            {warnings.map((warning, index) => (
              <div key={index} className={`warning-item ${warning.level}`}>
                <div className="warning-header">
                  <span className="warning-icon">⚠️</span>
                  <strong>{warning.title}</strong>
                </div>
                <p className="warning-message">{warning.message}</p>
                {warning.details && warning.details.length > 0 && (
                  <ul className="warning-details">
                    {warning.details.map((detail, i) => (
                      <li key={i}>{detail}</li>
                    ))}
                  </ul>
                )}
                {warning.mitigation && (
                  <p className="warning-mitigation">
                    <strong>Mitigation:</strong> {warning.mitigation}
                  </p>
                )}
                {warning.rollbackAvailable && (
                  <p className="rollback-info">
                    ✅ Rollback available: {warning.rollbackInstructions}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Affected Resources */}
          {request.affectedResources.length > 0 && (
            <div className="affected-resources">
              <h3>Affected Resources</h3>
              <ul>
                {request.affectedResources.map((resource, index) => (
                  <li key={index}>{resource}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Parameters */}
          <div className="parameters-section">
            <button
              className="toggle-details"
              onClick={() => setShowDetails(!showDetails)}
            >
              {showDetails ? '▼ Hide Details' : '▶ Show Details'}
            </button>
            {showDetails && (
              <pre className="parameters-code">
                {JSON.stringify(request.parameters, null, 2)}
              </pre>
            )}
          </div>

          {/* Rollback Plan */}
          {request.rollbackPlan && (
            <div className="rollback-plan">
              <h3>🔄 Rollback Plan</h3>
              <p>{request.rollbackPlan}</p>
            </div>
          )}

          {/* Duration Estimate */}
          {request.estimatedDuration && (
            <p className="duration-estimate">
              <strong>Estimated Duration:</strong> {request.estimatedDuration}
            </p>
          )}

          {/* Scroll Indicator */}
          {uiConfig.requireScroll && !hasScrolledToBottom && (
            <div className="scroll-indicator">
              ↓ Scroll down to review all warnings ↓
            </div>
          )}
        </div>

        {/* Confirmation Section */}
        <div className="confirmation-section">
          {/* Checkbox for critical operations */}
          {uiConfig.requireCheckbox && (
            <label className="confirmation-checkbox">
              <input
                type="checkbox"
                checked={checkboxChecked}
                onChange={(e) => setCheckboxChecked(e.target.checked)}
              />
              <span>{uiConfig.checkboxText || 'I understand this action may be irreversible'}</span>
            </label>
          )}

          {/* Confirmation phrase input */}
          {request.confirmationPhrase && (
            <div className="confirmation-phrase">
              <label htmlFor="confirmation-input">
                Type <strong className="phrase-highlight">{request.confirmationPhrase}</strong> to confirm:
              </label>
              <input
                id="confirmation-input"
                type="text"
                value={confirmationInput}
                onChange={(e) => setConfirmationInput(e.target.value)}
                placeholder={request.confirmationPhrase}
                className={`phrase-input ${
                  confirmationInput.toUpperCase() === request.confirmationPhrase.toUpperCase()
                    ? 'valid'
                    : confirmationInput.length > 0
                    ? 'invalid'
                    : ''
                }`}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="dialog-actions">
          <button
            className="btn-cancel"
            onClick={() => onReject(request.id, 'User cancelled')}
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            className={`btn-approve ${riskLevel}`}
            onClick={() => onApprove(request.id, confirmationInput)}
            disabled={!canApprove()}
          >
            {isLoading ? (
              <span className="loading-spinner">Processing...</span>
            ) : countdown > 0 ? (
              `Wait ${countdown}s...`
            ) : riskLevel === 'critical' ? (
              '🚨 Execute Operation'
            ) : riskLevel === 'high' ? (
              '⚠️ Proceed'
            ) : (
              'Confirm'
            )}
          </button>
        </div>

        {/* Expiry Warning */}
        {request.expiresAt && (
          <p className="expiry-warning">
            This approval request expires at {new Date(request.expiresAt).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
};

export default CriticalOperationDialog;
