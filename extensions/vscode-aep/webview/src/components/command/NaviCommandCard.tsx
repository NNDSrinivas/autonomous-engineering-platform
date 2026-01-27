/**
 * NaviCommandCard - Futuristic individual command entry card
 *
 * Features:
 * - Glassmorphism design with animated borders
 * - Expandable output section with smooth animation
 * - Status-based visual states (running, success, error)
 * - Copy command/output functionality
 * - Auto-expand on error, auto-scroll when streaming
 */

import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown, Copy, Check, ExternalLink } from 'lucide-react';
import { NaviStatusRing, CommandStatus } from './NaviStatusRing';
import { NaviCommandProgress } from './NaviCommandProgress';

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

interface NaviCommandCardProps {
  entry: TerminalEntry;
  isStreaming?: boolean;
  defaultExpanded?: boolean;
  onOpenInTerminal?: (id: string) => void;
}

export const NaviCommandCard: React.FC<NaviCommandCardProps> = ({
  entry,
  isStreaming = false,
  defaultExpanded,
  onOpenInTerminal,
}) => {
  // Auto-expand on error or when running
  const [expanded, setExpanded] = useState(
    defaultExpanded ?? (entry.status === 'running' || entry.status === 'error')
  );
  const [copied, setCopied] = useState(false);
  const outputRef = useRef<HTMLPreElement>(null);

  // Auto-expand when error occurs
  useEffect(() => {
    if (entry.status === 'error') {
      setExpanded(true);
    }
  }, [entry.status]);

  // Auto-scroll output when streaming
  useEffect(() => {
    if (isStreaming && outputRef.current && expanded) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [entry.output, isStreaming, expanded]);

  // Map status for CSS class
  const statusClass = entry.status === 'done' ? 'success' : entry.status;

  // Format duration
  const formatDuration = (ms?: number) => {
    if (ms === undefined) return null;
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  // Handle copy
  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const textToCopy = entry.output || entry.command;
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Handle expand toggle
  const handleToggle = () => {
    setExpanded(!expanded);
  };

  // Detect command type for visual hints
  const getCommandType = (cmd: string): string => {
    const lower = cmd.toLowerCase();
    if (lower.startsWith('git ')) return 'git';
    if (lower.startsWith('npm ') || lower.startsWith('yarn ') || lower.startsWith('pnpm ')) return 'npm';
    if (lower.includes('test') || lower.includes('jest') || lower.includes('pytest')) return 'test';
    if (lower.includes('build') || lower.includes('compile')) return 'build';
    return 'default';
  };

  const commandType = getCommandType(entry.command);

  return (
    <div
      className={`navi-command-card navi-command-card--${statusClass} navi-command-card--${commandType} ${expanded ? 'navi-command-card--expanded' : ''}`}
    >
      {/* Progress bar for running commands */}
      {entry.status === 'running' && (
        <NaviCommandProgress isActive={true} />
      )}

      {/* Header - always visible */}
      <div className="navi-command-header" onClick={handleToggle}>
        <div className="navi-command-header__left">
          <NaviStatusRing status={entry.status} size="md" />
          <div className="navi-command-header__info">
            <code className="navi-command-header__command">
              <span className="navi-command-prompt">$</span> {entry.command}
            </code>
            {entry.cwd && (
              <span className="navi-command-header__cwd">{entry.cwd}</span>
            )}
          </div>
        </div>

        <div className="navi-command-header__right">
          {formatDuration(entry.durationMs) && (
            <span className="navi-command-header__duration">
              {formatDuration(entry.durationMs)}
            </span>
          )}

          <div className="navi-command-actions">
            <button
              className={`navi-command-action-btn navi-command-copy-btn ${copied ? 'navi-command-copy-btn--copied' : ''}`}
              onClick={handleCopy}
              title={copied ? 'Copied!' : 'Copy output'}
              aria-label={copied ? 'Copied!' : 'Copy output'}
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>

            {onOpenInTerminal && (
              <button
                className="navi-command-action-btn navi-command-terminal-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenInTerminal(entry.id);
                }}
                title="Open in terminal"
                aria-label="Open in terminal"
              >
                <ExternalLink size={14} />
              </button>
            )}

            <button
              className="navi-command-action-btn navi-command-expand-btn"
              aria-label={expanded ? 'Collapse' : 'Expand'}
              aria-expanded={expanded}
            >
              <ChevronDown size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Expandable body with smooth animation */}
      <div className="navi-command-card__body">
        <div className="navi-command-card__body-inner">
          <pre
            ref={outputRef}
            className={`navi-command-output ${isStreaming ? 'navi-command-output--streaming' : ''}`}
          >
            {entry.output || (entry.status === 'running' ? 'Running...' : 'No output')}
            {entry.exitCode !== undefined && entry.exitCode !== 0 && (
              <span className="navi-output-error">
                {'\n'}Exit code: {entry.exitCode}
              </span>
            )}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default NaviCommandCard;
