import React, { useState, useEffect } from "react";
import { Trash2, Lock, Unlock, Search, RefreshCw, AlertCircle } from "lucide-react";

interface ConsentPreference {
  id: string;
  preference_type: "exact_command" | "command_type";
  command_pattern: string;
  created_at: string;
  created_by_task_id?: string;
}

interface ConsentAuditEntry {
  id: string;
  consent_id: string;
  command: string;
  shell: string;
  cwd?: string;
  danger_level?: string;
  decision: string;
  alternative_command?: string;
  requested_at: string;
  responded_at: string;
  response_time_ms?: number;
  task_id?: string;
  session_id?: string;
}

interface ConsentPreferencesProps {
  apiBaseUrl: string;
  authHeaders: Record<string, string>;
  onClose?: () => void;
  embedded?: boolean;
}

export const ConsentPreferences: React.FC<ConsentPreferencesProps> = ({
  apiBaseUrl,
  authHeaders,
  onClose,
  embedded = false,
}) => {
  const [preferences, setPreferences] = useState<ConsentPreference[]>([]);
  const [auditLog, setAuditLog] = useState<ConsentAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"preferences" | "audit">("preferences");

  const fetchPreferences = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/navi/consent-preferences`, {
        headers: authHeaders,
      });

      if (!res.ok) {
        throw new Error(`Failed to fetch preferences: ${res.statusText}`);
      }

      const data = await res.json();
      setPreferences(data.preferences || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditLog = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/navi/consent-audit?limit=50`, {
        headers: authHeaders,
      });

      if (!res.ok) {
        throw new Error(`Failed to fetch audit log: ${res.statusText}`);
      }

      const data = await res.json();
      setAuditLog(data.audit_log || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "preferences") {
      fetchPreferences();
    } else {
      fetchAuditLog();
    }
  }, [activeTab]);

  const handleDeletePreference = async (preferenceId: string) => {
    if (!confirm("Are you sure you want to delete this always-allow rule?")) {
      return;
    }

    try {
      const res = await fetch(
        `${apiBaseUrl}/api/navi/consent-preferences/${preferenceId}`,
        {
          method: "DELETE",
          headers: authHeaders,
        }
      );

      if (!res.ok) {
        throw new Error(`Failed to delete preference: ${res.statusText}`);
      }

      // Remove from local state
      setPreferences((prev) => prev.filter((p) => p.id !== preferenceId));
    } catch (err) {
      alert(`Error deleting preference: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const filteredPreferences = preferences.filter((pref) =>
    pref.command_pattern.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredAuditLog = auditLog.filter((entry) =>
    entry.command.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString();
    } catch {
      return isoString;
    }
  };

  const getDecisionBadgeStyle = (decision: string) => {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
      allow_once: { bg: "#0e639c20", text: "#0e639c", border: "#0e639c" },
      allow_always_exact: { bg: "#4caf5020", text: "#4caf50", border: "#4caf50" },
      allow_always_type: { bg: "#ff980020", text: "#ff9800", border: "#ff9800" },
      deny: { bg: "#f4433620", text: "#f44336", border: "#f44336" },
      alternative: { bg: "#9c27b020", text: "#9c27b0", border: "#9c27b0" },
    };

    return colors[decision] || colors.deny;
  };

  return (
    <div className={`consent-preferences-container ${embedded ? "consent-preferences-container--embedded" : ""}`}>
      {!embedded && (
        <div className="consent-prefs-header">
          <h2>Command Consent Settings</h2>
          {onClose && (
            <button onClick={onClose} className="consent-close-btn">
              ✕
            </button>
          )}
        </div>
      )}

      <div className="consent-tabs">
        <button
          className={`consent-tab ${activeTab === "preferences" ? "active" : ""}`}
          onClick={() => setActiveTab("preferences")}
        >
          <Lock size={16} />
          Always-Allow Rules ({preferences.length})
        </button>
        <button
          className={`consent-tab ${activeTab === "audit" ? "active" : ""}`}
          onClick={() => setActiveTab("audit")}
        >
          <AlertCircle size={16} />
          Audit Log ({auditLog.length})
        </button>
      </div>

      <div className="consent-search-bar">
        <Search size={16} className="consent-search-icon" />
        <input
          type="text"
          placeholder={
            activeTab === "preferences"
              ? "Search command patterns..."
              : "Search commands in audit log..."
          }
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="consent-search-input"
        />
        <button
          onClick={() => (activeTab === "preferences" ? fetchPreferences() : fetchAuditLog())}
          className="consent-refresh-btn"
          title="Refresh"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      {loading && (
        <div className="consent-loading-state">
          <RefreshCw size={24} className="consent-spinning" />
          <p>Loading...</p>
        </div>
      )}

      {error && (
        <div className="consent-error-state">
          <AlertCircle size={20} />
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && activeTab === "preferences" && (
        <div className="consent-preferences-list">
          {filteredPreferences.length === 0 ? (
            <div className="consent-empty-state">
              <Lock size={48} className="consent-empty-icon" />
              <h3>No Always-Allow Rules</h3>
              <p>
                You haven't created any auto-approval rules yet. When you choose "Allow This
                Command Always" or "Allow All Commands" in a consent dialog, they'll appear here.
              </p>
            </div>
          ) : (
            filteredPreferences.map((pref) => (
              <div key={pref.id} className="consent-preference-card">
                <div className="consent-pref-header">
                  <div className="consent-pref-icon">
                    {pref.preference_type === "exact_command" ? (
                      <Lock size={18} />
                    ) : (
                      <Unlock size={18} />
                    )}
                  </div>
                  <div className="consent-pref-info">
                    <div className="consent-pref-type">
                      {pref.preference_type === "exact_command"
                        ? "Exact Command"
                        : "Command Type"}
                    </div>
                    <code className="consent-pref-command">{pref.command_pattern}</code>
                    <div className="consent-pref-meta">
                      Created {formatDate(pref.created_at)}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeletePreference(pref.id)}
                    className="consent-delete-btn"
                    title="Delete this rule"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {!loading && !error && activeTab === "audit" && (
        <div className="consent-audit-list">
          {filteredAuditLog.length === 0 ? (
            <div className="consent-empty-state">
              <AlertCircle size={48} className="consent-empty-icon" />
              <h3>No Audit History</h3>
              <p>Your consent decisions will appear here for review and compliance.</p>
            </div>
          ) : (
            filteredAuditLog.map((entry) => (
              <div key={entry.id} className="consent-audit-card">
                <div className="consent-audit-header">
                  <span
                    className="consent-decision-badge"
                    style={getDecisionBadgeStyle(entry.decision)}
                  >
                    {entry.decision.replace(/_/g, " ").toUpperCase()}
                  </span>
                  <span className="consent-audit-time">{formatDate(entry.requested_at)}</span>
                </div>
                <code className="consent-audit-command">{entry.command}</code>
                {entry.alternative_command && (
                  <div className="consent-alternative-info">
                    <strong>Alternative:</strong> <code>{entry.alternative_command}</code>
                  </div>
                )}
                <div className="consent-audit-meta">
                  {entry.danger_level && (
                    <span className="consent-meta-item">Danger: {entry.danger_level}</span>
                  )}
                  {entry.response_time_ms && (
                    <span className="consent-meta-item">
                      Response time: {entry.response_time_ms}ms
                    </span>
                  )}
                  {entry.cwd && <span className="consent-meta-item">CWD: {entry.cwd}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      <style>{`
        .consent-preferences-container {
          width: 100%;
          max-width: 900px;
          margin: 0 auto;
          padding: 20px;
          background: var(--vscode-editor-background, #1e1e1e);
          color: var(--vscode-foreground, #cccccc);
          font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
        }

        .consent-preferences-container--embedded {
          max-width: none;
          margin: 0;
          padding: 0;
          background: transparent;
          color: inherit;
        }

        .consent-prefs-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .consent-prefs-header h2 {
          margin: 0;
          font-size: 20px;
          font-weight: 600;
        }

        .consent-close-btn {
          background: transparent;
          border: none;
          color: var(--vscode-foreground, #cccccc);
          font-size: 24px;
          cursor: pointer;
          padding: 4px 8px;
          opacity: 0.7;
          transition: opacity 0.2s;
        }

        .consent-close-btn:hover {
          opacity: 1;
        }

        .consent-tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 20px;
          border-bottom: 1px solid var(--vscode-panel-border, #3c3c3c);
        }

        .consent-tab {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 16px;
          background: transparent;
          border: none;
          color: var(--vscode-foreground, #cccccc);
          cursor: pointer;
          font-size: 14px;
          font-weight: 500;
          border-bottom: 2px solid transparent;
          opacity: 0.7;
          transition: all 0.2s;
          font-family: inherit;
        }

        .consent-tab:hover {
          opacity: 1;
        }

        .consent-tab.active {
          opacity: 1;
          border-bottom-color: var(--vscode-button-background, #0e639c);
        }

        .consent-search-bar {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 20px;
          background: var(--vscode-input-background, #3c3c3c);
          border: 1px solid var(--vscode-input-border, #464646);
          border-radius: 4px;
          padding: 8px 12px;
        }

        .consent-search-icon {
          color: var(--vscode-descriptionForeground, #999);
          flex-shrink: 0;
        }

        .consent-search-input {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: var(--vscode-input-foreground, #cccccc);
          font-size: 13px;
          font-family: inherit;
        }

        .consent-refresh-btn {
          background: transparent;
          border: none;
          color: var(--vscode-button-foreground, #cccccc);
          cursor: pointer;
          padding: 4px;
          display: flex;
          align-items: center;
          opacity: 0.7;
          transition: opacity 0.2s;
        }

        .consent-refresh-btn:hover {
          opacity: 1;
        }

        .consent-loading-state,
        .consent-error-state,
        .consent-empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 60px 20px;
          text-align: center;
        }

        .consent-loading-state p,
        .consent-error-state p,
        .consent-empty-state p {
          margin-top: 12px;
          color: var(--vscode-descriptionForeground, #999);
        }

        .consent-empty-state h3 {
          margin: 12px 0 8px;
          font-size: 18px;
        }

        .consent-empty-icon {
          opacity: 0.3;
        }

        .consent-spinning {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .consent-preferences-list,
        .consent-audit-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .consent-preference-card,
        .consent-audit-card {
          background: var(--vscode-editorWidget-background, #252526);
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          border-radius: 6px;
          padding: 16px;
          transition: all 0.2s;
        }

        .consent-preference-card:hover,
        .consent-audit-card:hover {
          border-color: var(--vscode-focusBorder, #007fd4);
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }

        .consent-pref-header,
        .consent-audit-header {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }

        .consent-pref-icon {
          flex-shrink: 0;
          color: var(--vscode-button-background, #0e639c);
          margin-top: 2px;
        }

        .consent-pref-info {
          flex: 1;
        }

        .consent-pref-type {
          font-size: 11px;
          text-transform: uppercase;
          color: var(--vscode-descriptionForeground, #999);
          margin-bottom: 4px;
          letter-spacing: 0.5px;
        }

        .consent-pref-command,
        .consent-audit-command {
          display: block;
          font-family: var(--vscode-editor-font-family, 'SF Mono', Monaco, monospace);
          font-size: 13px;
          color: var(--vscode-terminal-foreground, #e0e0e0);
          background: var(--vscode-textCodeBlock-background, #1a1a1a);
          padding: 6px 10px;
          border-radius: 3px;
          margin: 6px 0;
        }

        .consent-pref-meta,
        .consent-audit-meta {
          font-size: 11px;
          color: var(--vscode-descriptionForeground, #6c6c6c);
          margin-top: 6px;
        }

        .consent-delete-btn {
          flex-shrink: 0;
          background: transparent;
          border: 1px solid var(--vscode-panel-border, #3c3c3c);
          color: var(--vscode-errorForeground, #f44336);
          cursor: pointer;
          padding: 8px;
          border-radius: 4px;
          display: flex;
          align-items: center;
          transition: all 0.2s;
        }

        .consent-delete-btn:hover {
          background: var(--vscode-errorBackground, rgba(244, 67, 54, 0.1));
          border-color: var(--vscode-errorForeground, #f44336);
        }

        .consent-decision-badge {
          padding: 4px 10px;
          border-radius: 3px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.5px;
          border: 1px solid;
        }

        .consent-audit-time {
          font-size: 11px;
          color: var(--vscode-descriptionForeground, #999);
          margin-left: auto;
        }

        .consent-alternative-info {
          margin: 8px 0;
          padding: 8px 12px;
          background: var(--vscode-inputValidation-infoBackground, rgba(33, 150, 243, 0.1));
          border-left: 2px solid var(--vscode-inputValidation-infoBorder, #2196f3);
          border-radius: 3px;
          font-size: 12px;
        }

        .consent-alternative-info code {
          font-family: var(--vscode-editor-font-family, monospace);
          font-size: 12px;
        }

        .consent-meta-item {
          margin-right: 16px;
          display: inline-block;
        }
      `}</style>
    </div>
  );
};
