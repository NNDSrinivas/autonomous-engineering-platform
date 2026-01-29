import React, { useState, useMemo } from 'react';
import './NaviProPanel.css';

// =============================================================================
// NAVI PRO PANEL
// =============================================================================
// Sleek, futuristic, professional command panel
// Inspired by: Linear, Vercel, Raycast - clean minimal design
// =============================================================================

export type CommandStatus = 'running' | 'done' | 'error';

export interface TerminalEntry {
  id: string;
  command: string;
  cwd?: string;
  output: string;
  status: CommandStatus;
  startedAt: string;
  exitCode?: number;
  durationMs?: number;
}

interface NaviProPanelProps {
  entries: TerminalEntry[];
  onClear?: () => void;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
  defaultOpen?: boolean;
}

// =============================================================================
// COMMAND ROW COMPONENT
// =============================================================================

interface CommandRowProps {
  entry: TerminalEntry;
  index: number;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
}

const CommandRow: React.FC<CommandRowProps> = ({ entry, index, onOpenInTerminal }) => {
  const [expanded, setExpanded] = useState(entry.status === 'running');

  const getStatusIcon = () => {
    switch (entry.status) {
      case 'running':
        return <span className="status-icon running"><span className="spinner" /></span>;
      case 'done':
        return <span className="status-icon success">✓</span>;
      case 'error':
        return <span className="status-icon error">✕</span>;
    }
  };

  const formatDuration = () => {
    if (entry.status === 'running') {
      const elapsed = Date.now() - new Date(entry.startedAt).getTime();
      return `${(elapsed / 1000).toFixed(1)}s`;
    }
    if (entry.durationMs) {
      return `${(entry.durationMs / 1000).toFixed(2)}s`;
    }
    return '-';
  };

  const formatOutput = () => {
    const lines = entry.output.split('\n').filter(l => l.trim());
    if (lines.length === 0) {
      return entry.status === 'running' ? 'Executing...' : 'No output';
    }
    return lines.slice(-15).join('\n');
  };

  return (
    <div className={`cmd-row cmd-row--${entry.status}`}>
      <div className="cmd-main" onClick={() => setExpanded(!expanded)}>
        <div className="cmd-status">
          {getStatusIcon()}
        </div>
        <div className="cmd-content">
          <code className="cmd-text">{entry.command}</code>
          {entry.cwd && <span className="cmd-cwd">{entry.cwd}</span>}
        </div>
        <div className="cmd-meta">
          <span className="cmd-duration">{formatDuration()}</span>
          <span className={`cmd-expand ${expanded ? 'is-open' : ''}`}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </span>
        </div>
      </div>

      {expanded && (
        <div className="cmd-output">
          <pre>{formatOutput()}</pre>
          {entry.status === 'error' && entry.exitCode !== undefined && (
            <div className="cmd-exit">Exit code: {entry.exitCode}</div>
          )}
          {onOpenInTerminal && (
            <button
              className="cmd-action"
              onClick={(e) => { e.stopPropagation(); onOpenInTerminal(entry); }}
            >
              Open in Terminal
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// MAIN PRO PANEL
// =============================================================================

export const NaviProPanel: React.FC<NaviProPanelProps> = ({
  entries,
  onClear,
  onOpenInTerminal,
  defaultOpen = true,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(!defaultOpen);

  const stats = useMemo(() => ({
    total: entries.length,
    running: entries.filter(e => e.status === 'running').length,
    success: entries.filter(e => e.status === 'done').length,
    failed: entries.filter(e => e.status === 'error').length,
  }), [entries]);

  if (entries.length === 0) return null;

  if (isCollapsed) {
    return (
      <div className="navi-pro collapsed" onClick={() => setIsCollapsed(false)}>
        <div className="pro-collapsed">
          <span className="pro-icon">⌘</span>
          <span className="pro-label">Commands</span>
          <div className="pro-badges">
            {stats.running > 0 && <span className="badge running">{stats.running} running</span>}
            {stats.failed > 0 && <span className="badge failed">{stats.failed} failed</span>}
            {stats.running === 0 && stats.failed === 0 && (
              <span className="badge neutral">{stats.total}</span>
            )}
          </div>
          <span className="pro-expand">›</span>
        </div>
      </div>
    );
  }

  return (
    <div className="navi-pro">
      {/* Header */}
      <div className="pro-header">
        <button className="pro-title" onClick={() => setIsCollapsed(true)}>
          <span className="pro-icon">⌘</span>
          <span className="pro-label">Commands</span>
          <span className="pro-collapse">‹</span>
        </button>

        <div className="pro-stats">
          {stats.running > 0 && (
            <span className="stat running">
              <span className="stat-dot" />
              {stats.running} running
            </span>
          )}
          {stats.success > 0 && (
            <span className="stat success">{stats.success} done</span>
          )}
          {stats.failed > 0 && (
            <span className="stat failed">{stats.failed} failed</span>
          )}
        </div>

        {onClear && (
          <button className="pro-clear" onClick={onClear} title="Clear all">
            Clear
          </button>
        )}
      </div>

      {/* Command List */}
      <div className="pro-list">
        {entries.map((entry, index) => (
          <CommandRow
            key={entry.id}
            entry={entry}
            index={index}
            onOpenInTerminal={onOpenInTerminal}
          />
        ))}
      </div>

      {/* Subtle gradient line at bottom */}
      <div className="pro-gradient" />
    </div>
  );
};

export default NaviProPanel;
