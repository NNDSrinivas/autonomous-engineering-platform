import React, { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ShieldCheck, ShieldX, TerminalSquare } from "lucide-react";

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

const DANGER_LABEL: Record<CommandConsentRequest["danger_level"], string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export const ConsentDialog: React.FC<ConsentDialogProps> = ({ consent, onDecision }) => {
  const [showAlternativeInput, setShowAlternativeInput] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [alternativeCommand, setAlternativeCommand] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const baseCommand = useMemo(() => consent.command.split(/\s+/).filter(Boolean)[0] || "command", [consent.command]);
  const scopePath = useMemo(
    () => (consent.cwd ? consent.cwd.split(/[/\\]/).filter(Boolean).slice(-2).join("/") : ""),
    [consent.cwd]
  );

  useEffect(() => {
    if (showAlternativeInput && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showAlternativeInput]);

  const handleDecision = (choice: ConsentDecision["choice"]) => {
    if (choice === "alternative") {
      const trimmed = alternativeCommand.trim();
      if (!trimmed) {
        setShowAlternativeInput(true);
        return;
      }
      onDecision(consent.consent_id, { choice, alternative_command: trimmed });
      return;
    }
    onDecision(consent.consent_id, { choice });
  };

  return (
    <div className={`navi-inline-consent navi-inline-consent--${consent.danger_level}`}>
      <div className="navi-inline-consent__header">
        <div className="navi-inline-consent__title-wrap">
          <span className="navi-inline-consent__icon">
            <TerminalSquare className="h-3.5 w-3.5" />
          </span>
          <div className="navi-inline-consent__title-group">
            <div className="navi-inline-consent__title">Command approval required</div>
            <div className="navi-inline-consent__meta">
              {consent.shell ? consent.shell.toUpperCase() : "SHELL"}
              {scopePath ? ` • ${scopePath}` : ""}
            </div>
          </div>
        </div>
        <span className={`navi-inline-consent__risk navi-inline-consent__risk--${consent.danger_level}`}>
          {DANGER_LABEL[consent.danger_level]}
        </span>
      </div>

      <code className="navi-inline-consent__command" title={consent.command}>
        {consent.command}
      </code>

      <div className="navi-inline-consent__warning">
        <AlertTriangle className="h-3.5 w-3.5" />
        <span>{consent.warning}</span>
      </div>

      {(consent.consequences?.length || consent.alternatives?.length) && (
        <button
          type="button"
          className="navi-inline-consent__details-toggle"
          onClick={() => setDetailsOpen((prev) => !prev)}
          aria-expanded={detailsOpen}
        >
          {detailsOpen ? "Hide details" : "Show details"}
        </button>
      )}

      {detailsOpen && (
        <div className="navi-inline-consent__details">
          {consent.consequences && consent.consequences.length > 0 && (
            <div className="navi-inline-consent__list-group">
              <div className="navi-inline-consent__list-title">Possible consequences</div>
              <ul>
                {consent.consequences.map((item, idx) => (
                  <li key={`${consent.consent_id}-c-${idx}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          {consent.alternatives && consent.alternatives.length > 0 && (
            <div className="navi-inline-consent__list-group">
              <div className="navi-inline-consent__list-title">Suggested alternatives</div>
              <ul>
                {consent.alternatives.map((item, idx) => (
                  <li key={`${consent.consent_id}-a-${idx}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {showAlternativeInput ? (
        <div className="navi-inline-consent__alt">
          <input
            ref={inputRef}
            className="navi-inline-consent__alt-input"
            type="text"
            placeholder="Enter alternative command"
            value={alternativeCommand}
            onChange={(e) => setAlternativeCommand(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleDecision("alternative");
              } else if (e.key === "Escape") {
                setShowAlternativeInput(false);
                setAlternativeCommand("");
              }
            }}
          />
          <div className="navi-inline-consent__alt-actions">
            <button
              type="button"
              className="navi-inline-consent__btn navi-inline-consent__btn--primary"
              onClick={() => handleDecision("alternative")}
              disabled={!alternativeCommand.trim()}
            >
              Use alternative
            </button>
            <button
              type="button"
              className="navi-inline-consent__btn navi-inline-consent__btn--ghost"
              onClick={() => {
                setShowAlternativeInput(false);
                setAlternativeCommand("");
              }}
            >
              Back
            </button>
          </div>
        </div>
      ) : (
        <div className="navi-inline-consent__actions navi-inline-consent__actions--grid">
          <button
            type="button"
            className="navi-inline-consent__btn navi-inline-consent__btn--primary"
            onClick={() => handleDecision("allow_once")}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Run once
          </button>
          <button
            type="button"
            className="navi-inline-consent__btn"
            onClick={() => handleDecision("allow_always_exact")}
          >
            Allow exact
          </button>
          <button
            type="button"
            className="navi-inline-consent__btn"
            onClick={() => handleDecision("allow_always_type")}
            title={`Always allow '${baseCommand}' commands`}
          >
            Allow {baseCommand}
          </button>
          <button
            type="button"
            className="navi-inline-consent__btn navi-inline-consent__btn--ghost"
            onClick={() => setShowAlternativeInput(true)}
          >
            Alternative
          </button>
          <button
            type="button"
            className="navi-inline-consent__btn navi-inline-consent__btn--danger"
            onClick={() => handleDecision("deny")}
          >
            <ShieldX className="h-3.5 w-3.5" />
            Deny
          </button>
        </div>
      )}
    </div>
  );
};
