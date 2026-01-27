/**
 * NaviCommandPanel - Main container for futuristic command execution display
 *
 * Features:
 * - Glassmorphism panel with backdrop blur
 * - Circuit pattern overlay during execution
 * - Collapsible panel with smooth animation
 * - Renders NaviCommandCard for each terminal entry
 */

import React, { useState } from 'react';
import { Terminal, ChevronDown, Trash2 } from 'lucide-react';
import { NaviCommandCard, TerminalEntry } from './NaviCommandCard';
import './NaviCommandPanel.css';

const MAX_DISPLAYED_ENTRIES = 50;

interface NaviCommandPanelProps {
  entries: TerminalEntry[];
  onClear?: () => void;
  onOpenInTerminal?: (id: string) => void;
  defaultOpen?: boolean;
}

export const NaviCommandPanel: React.FC<NaviCommandPanelProps> = ({
  entries,
  onClear,
  onOpenInTerminal,
  defaultOpen = true,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // Check if any command is currently running
  const hasRunningCommand = entries.some((e) => e.status === 'running');

  // Get displayed entries (last N)
  const displayedEntries = entries.slice(-MAX_DISPLAYED_ENTRIES);

  // Count stats
  const stats = {
    total: entries.length,
    running: entries.filter((e) => e.status === 'running').length,
    success: entries.filter((e) => e.status === 'done').length,
    error: entries.filter((e) => e.status === 'error').length,
  };

  if (entries.length === 0) {
    return null; // Don't render panel if no entries
  }

  return (
    <div
      className={`navi-command-panel ${hasRunningCommand ? 'navi-command-panel--running' : ''} ${isOpen ? 'navi-command-panel--open' : 'navi-command-panel--collapsed'}`}
    >
      {/* Panel Header */}
      <div className="navi-command-panel__header">
        <button
          type="button"
          className="navi-command-panel__title"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
        >
          <Terminal className="navi-command-panel__icon" size={16} />
          <span className="navi-command-panel__label">Terminal</span>

          {/* Status badges */}
          <div className="navi-command-panel__badges">
            {stats.running > 0 && (
              <span className="navi-command-badge navi-command-badge--running">
                {stats.running} running
              </span>
            )}
            {stats.error > 0 && (
              <span className="navi-command-badge navi-command-badge--error">
                {stats.error} failed
              </span>
            )}
            {stats.running === 0 && stats.error === 0 && (
              <span className="navi-command-badge navi-command-badge--idle">
                {stats.total} {stats.total === 1 ? 'command' : 'commands'}
              </span>
            )}
          </div>

          <ChevronDown
            className={`navi-command-panel__chevron ${isOpen ? 'navi-command-panel__chevron--open' : ''}`}
            size={16}
          />
        </button>

        <div className="navi-command-panel__actions">
          {onClear && entries.length > 0 && (
            <button
              type="button"
              className="navi-command-panel__action"
              onClick={onClear}
              title="Clear all"
              aria-label="Clear terminal"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Panel Body - expandable */}
      <div className="navi-command-panel__body">
        <div className="navi-command-panel__body-inner">
          {displayedEntries.length === 0 ? (
            <div className="navi-command-panel__empty">
              No terminal activity yet.
            </div>
          ) : (
            <div className="navi-command-panel__entries">
              {displayedEntries.map((entry, index) => (
                <NaviCommandCard
                  key={entry.id}
                  entry={entry}
                  isStreaming={entry.status === 'running'}
                  defaultExpanded={index === displayedEntries.length - 1 && entry.status === 'running'}
                  onOpenInTerminal={onOpenInTerminal}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NaviCommandPanel;
