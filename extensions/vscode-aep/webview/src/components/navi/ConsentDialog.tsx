import React, { useState, useEffect, useRef } from "react";

export interface CommandConsentRequest {
  consent_id: string;
  command: string;
  shell: string;
  cwd?: string;
  danger_level: "low" | "medium" | "high" | "critical";
  warning: string;
  consequences?: string[];
  alternatives?: string[];
  rollback_possible?: boolean;
  timestamp: string;
}

export interface ConsentDecision {
  choice: "allow_once" | "allow_always_exact" | "allow_always_type" | "deny" | "alternative";
  alternative_command?: string;
}

interface ConsentDialogProps {
  consent: CommandConsentRequest;
  onDecision: (consentId: string, decision: ConsentDecision) => void;
}

export const ConsentDialog: React.FC<ConsentDialogProps> = ({
  consent,
  onDecision,
}) => {
  const [showAlternativeInput, setShowAlternativeInput] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [alternativeCommand, setAlternativeCommand] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const baseCommand = consent.command.split(" ")[0];
  const metaParts = [
    consent.shell ? consent.shell.toUpperCase() : "",
    consent.cwd ? consent.cwd.split(/[/\\]/).filter(Boolean).slice(-2).join("/") : "",
  ].filter(Boolean);
  const metaLabel = metaParts.join(" · ");

  useEffect(() => {
    // Focus alternative input when shown
    if (showAlternativeInput && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showAlternativeInput]);

  const handleDecision = (choice: ConsentDecision["choice"]) => {
    if (choice === "alternative") {
      if (!alternativeCommand.trim()) {
        setShowAlternativeInput(true);
        return;
      }
      onDecision(consent.consent_id, { choice, alternative_command: alternativeCommand });
    } else {
      onDecision(consent.consent_id, { choice });
    }
  };

  const getDangerColor = () => {
    switch (consent.danger_level) {
      case "critical":
        return "#f44336";  // Red
      case "high":
        return "#ff9800";  // Orange
      case "medium":
        return "#ffc107";  // Amber
      default:
        return "#2196f3";  // Blue
    }
  };

  const getDangerBadgeStyle = () => {
    const color = getDangerColor();
    return {
      backgroundColor: `${color}20`,
      color: color,
      border: `1px solid ${color}`,
    };
  };

  return (
    <div className="consent-inline" style={{ borderLeftColor: getDangerColor() }}>
      <div className="consent-box">
        <div className="consent-header">
          <div className="consent-title">
            <span className="consent-icon">🛡️</span>
            <strong>Command approval</strong>
            {metaLabel && <span className="consent-meta">{metaLabel}</span>}
          </div>
          <div className="consent-header-actions">
            <span className="danger-badge" style={getDangerBadgeStyle()}>
              {consent.danger_level.toUpperCase()}
            </span>
            <button
              type="button"
              className="consent-details-toggle"
              onClick={() => setDetailsOpen((prev) => !prev)}
              aria-expanded={detailsOpen}
            >
              {detailsOpen ? "Hide" : "Details"}
            </button>
          </div>
        </div>

        <code className="consent-command" title={consent.command}>
          {consent.command}
        </code>

        <div className="consent-warning">
          <span className="warning-icon">⚠️</span>
          <span className="consent-warning-text">{consent.warning}</span>
        </div>

        {detailsOpen && consent.consequences && consent.consequences.length > 0 && (
          <ul className="consent-consequences">
            {consent.consequences.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}

        {showAlternativeInput ? (
          <div className="alternative-input-section">
            <label htmlFor="alt-cmd-input">Enter alternative command:</label>
            <input
              id="alt-cmd-input"
              ref={inputRef}
              type="text"
              placeholder="e.g., ls -la instead of rm -rf"
              value={alternativeCommand}
              onChange={(e) => setAlternativeCommand(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && alternativeCommand.trim()) {
                  handleDecision("alternative");
                } else if (e.key === "Escape") {
                  setShowAlternativeInput(false);
                  setAlternativeCommand("");
                }
              }}
              className="alternative-input"
            />
            <div className="alternative-actions">
              <button
                onClick={() => handleDecision("alternative")}
                disabled={!alternativeCommand.trim()}
                className="btn-submit"
              >
                Submit Alternative
              </button>
              <button
                onClick={() => {
                  setShowAlternativeInput(false);
                  setAlternativeCommand("");
                }}
                className="btn-cancel"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="consent-actions">
            <button
              onClick={() => handleDecision("allow_once")}
              className="consent-btn consent-btn-primary"
              title="Execute this command once, ask again next time"
            >
              <span className="btn-icon">✅</span>
              <span className="btn-text">
                <span className="btn-label">Once</span>
                <span className="btn-hint">1</span>
              </span>
            </button>

            <button
              onClick={() => handleDecision("allow_always_exact")}
              className="consent-btn consent-btn-success"
              title="Always allow this exact command without asking"
            >
              <span className="btn-icon">🔒</span>
              <span className="btn-text">
                <span className="btn-label">Always exact</span>
                <span className="btn-hint">2</span>
              </span>
            </button>

            <button
              onClick={() => handleDecision("allow_always_type")}
              className="consent-btn consent-btn-warning"
              title={`Always allow all '${baseCommand}' commands without asking`}
            >
              <span className="btn-icon">🔓</span>
              <span className="btn-text">
                <span className="btn-label">Always type</span>
                <span className="btn-hint">3</span>
              </span>
            </button>

            <button
              onClick={() => handleDecision("deny")}
              className="consent-btn consent-btn-danger"
              title="Don't execute, skip this command"
            >
              <span className="btn-icon">❌</span>
              <span className="btn-text">
                <span className="btn-label">Deny</span>
                <span className="btn-hint">4</span>
              </span>
            </button>

            <button
              onClick={() => setShowAlternativeInput(true)}
              className="consent-btn consent-btn-secondary"
              title="Provide a different command to execute instead"
            >
              <span className="btn-icon">💬</span>
              <span className="btn-text">
                <span className="btn-label">Alt</span>
                <span className="btn-hint">5</span>
              </span>
            </button>
          </div>
        )}

        <div className="consent-hint">
          Press 1–5 or Esc
        </div>
      </div>

      <style>{`
        .consent-inline {
          margin: 6px 0;
          border-left: 3px solid var(--vscode-button-background, #0e639c);
          background: linear-gradient(180deg, rgba(24, 24, 24, 0.92), rgba(18, 18, 18, 0.88));
          border-radius: 12px;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
          max-width: 720px;
        }

        .consent-box {
          padding: 8px 10px;
        }

        .consent-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;
          gap: 8px;
        }

        .consent-title {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 600;
          color: var(--vscode-foreground, #cccccc);
          flex-wrap: wrap;
        }

        .consent-icon {
          font-size: 14px;
          line-height: 1;
        }

        .consent-meta {
          font-size: 10px;
          font-weight: 500;
          color: var(--vscode-descriptionForeground, #9aa0a6);
          background: rgba(255, 255, 255, 0.04);
          padding: 2px 6px;
          border-radius: 999px;
        }

        .consent-header-actions {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .danger-badge {
          padding: 2px 7px;
          border-radius: 999px;
          font-size: 9px;
          font-weight: 700;
          letter-spacing: 0.4px;
          text-transform: uppercase;
        }

        .consent-command {
          display: block;
          background: rgba(0, 0, 0, 0.32);
          padding: 5px 7px;
          border-radius: 8px;
          font-family: var(--vscode-editor-font-family, 'SF Mono', Monaco, 'Courier New', monospace);
          font-size: 11px;
          color: var(--vscode-terminal-foreground, #e0e0e0);
          margin: 4px 0 6px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .consent-details-toggle {
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: rgba(255, 255, 255, 0.04);
          color: var(--vscode-foreground, #cfcfcf);
          font-size: 10px;
          padding: 4px 7px;
          border-radius: 999px;
          cursor: pointer;
        }

        .consent-details-toggle:hover {
          border-color: rgba(255, 255, 255, 0.2);
          background: rgba(255, 255, 255, 0.08);
        }

        .consent-warning {
          display: flex;
          align-items: flex-start;
          gap: 6px;
          font-size: 11px;
          color: var(--vscode-descriptionForeground, #bdbdbd);
          margin: 4px 0 6px;
          line-height: 1.3;
          background: rgba(255, 193, 7, 0.12);
          padding: 5px 7px;
          border-radius: 8px;
          border-left: 2px solid var(--vscode-inputValidation-warningBorder, #ffc107);
        }

        .consent-warning-text {
          flex: 1;
        }

        .warning-icon {
          font-size: 12px;
          flex-shrink: 0;
        }

        .consent-consequences {
          list-style: none;
          padding: 0;
          margin: 4px 0 2px;
          font-size: 10px;
          color: var(--vscode-descriptionForeground, #a3a3a3);
          display: grid;
          gap: 4px;
        }

        .consent-consequences li {
          padding-left: 10px;
          position: relative;
        }

        .consent-consequences li::before {
          content: "•";
          position: absolute;
          left: 0;
          opacity: 0.6;
        }

        .consent-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin: 4px 0 2px;
        }

        .consent-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          background: rgba(255, 255, 255, 0.06);
          color: var(--vscode-button-secondaryForeground, #d6d6d6);
          border: 1px solid rgba(255, 255, 255, 0.08);
          padding: 4px 8px;
          border-radius: 999px;
          font-size: 11px;
          cursor: pointer;
          transition: background 0.15s ease, border-color 0.15s ease;
          text-align: left;
          font-family: inherit;
          min-height: 26px;
        }

        .consent-btn:hover {
          background: rgba(255, 255, 255, 0.12);
          border-color: rgba(0, 127, 212, 0.6);
        }

        .btn-icon {
          flex-shrink: 0;
          font-size: 12px;
          line-height: 1;
        }

        .btn-text {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          flex: 1;
        }

        .btn-label {
          font-weight: 600;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .btn-hint {
          font-size: 9px;
          opacity: 0.75;
          background: rgba(255, 255, 255, 0.1);
          padding: 1px 5px;
          border-radius: 6px;
        }

        .consent-btn-primary:hover {
          background: #0e639c;
          color: white;
        }

        .consent-btn-success:hover {
          background: #4caf50;
          color: white;
        }

        .consent-btn-warning:hover {
          background: #ff9800;
          color: white;
        }

        .consent-btn-danger:hover {
          background: #f44336;
          color: white;
        }

        .consent-btn-secondary:hover {
          background: #6c757d;
          color: white;
        }

        .alternative-input-section {
          margin: 6px 0;
          padding: 8px;
          background: rgba(255, 255, 255, 0.04);
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .alternative-input-section label {
          display: block;
          font-size: 10px;
          font-weight: 600;
          color: var(--vscode-foreground, #cccccc);
          margin-bottom: 4px;
        }

        .alternative-input {
          width: 100%;
          padding: 5px 7px;
          font-size: 11px;
          font-family: var(--vscode-editor-font-family, 'SF Mono', Monaco, monospace);
          background: var(--vscode-input-background, #3c3c3c);
          color: var(--vscode-input-foreground, #cccccc);
          border: 1px solid var(--vscode-input-border, #464646);
          border-radius: 8px;
          outline: none;
          margin-bottom: 8px;
        }

        .alternative-input:focus {
          border-color: var(--vscode-focusBorder, #007fd4);
          box-shadow: 0 0 0 1px var(--vscode-focusBorder, #007fd4);
        }

        .alternative-actions {
          display: flex;
          gap: 6px;
        }

        .btn-submit,
        .btn-cancel {
          padding: 5px 9px;
          font-size: 11px;
          border-radius: 8px;
          border: none;
          cursor: pointer;
          font-family: inherit;
          font-weight: 600;
          transition: all 0.15s ease;
        }

        .btn-submit {
          background: var(--vscode-button-background, #0e639c);
          color: var(--vscode-button-foreground, #ffffff);
        }

        .btn-submit:hover:not(:disabled) {
          background: var(--vscode-button-hoverBackground, #1177bb);
        }

        .btn-submit:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-cancel {
          background: var(--vscode-button-secondaryBackground, #3a3d41);
          color: var(--vscode-button-secondaryForeground, #cccccc);
        }

        .btn-cancel:hover {
          background: var(--vscode-button-secondaryHoverBackground, #45494e);
        }

        .consent-hint {
          font-size: 9px;
          color: var(--vscode-descriptionForeground, #8a8a8a);
          margin-top: 2px;
          text-align: center;
          opacity: 0.8;
        }
      `}</style>
    </div>
  );
};
