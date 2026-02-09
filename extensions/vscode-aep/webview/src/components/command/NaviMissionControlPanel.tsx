/**
 * NaviMissionControlPanel - NASA/SpaceX Mission Control aesthetic
 *
 * Commands are "missions" with:
 * - Mission numbers (MISSION-001, MISSION-002, etc.)
 * - Telemetry strip showing data flow waveform
 * - Status: ORBIT ACHIEVED (success), IN FLIGHT (running), ABORT (error)
 * - Signal strength indicator
 * - Mission clock (T+00:03.2s elapsed time)
 */

import React, { useState, useEffect, useRef } from 'react';
import { Rocket, ChevronDown, Trash2, Copy, Check, ExternalLink } from 'lucide-react';
import './NaviMissionControlPanel.css';

// Re-export the interface for compatibility
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

interface NaviMissionControlPanelProps {
  entries: TerminalEntry[];
  onClear?: () => void;
  onOpenInTerminal?: (id: string) => void;
  defaultOpen?: boolean;
}

const MAX_DISPLAYED_ENTRIES = 50;

// Generate telemetry waveform data
const generateTelemetryData = (output: string, status: CommandStatus): number[] => {
  // Create a pseudo-random waveform based on output length and content
  const data: number[] = [];
  const seed = output.length;
  for (let i = 0; i < 20; i++) {
    if (status === 'running') {
      // Active waveform for running commands
      data.push(Math.sin(i * 0.5 + Date.now() / 200) * 0.5 + 0.5);
    } else if (status === 'error') {
      // Erratic waveform for errors
      data.push(Math.random() * 0.3);
    } else {
      // Stable waveform for completed
      data.push(0.7 + Math.sin(i * 0.3) * 0.2);
    }
  }
  return data;
};

// Mission Card Component
const MissionCard: React.FC<{
  entry: TerminalEntry;
  missionNumber: number;
  isStreaming?: boolean;
  defaultExpanded?: boolean;
  onOpenInTerminal?: (id: string) => void;
}> = ({ entry, missionNumber, isStreaming = false, defaultExpanded, onOpenInTerminal }) => {
  const [expanded, setExpanded] = useState(
    defaultExpanded ?? (entry.status === 'running' || entry.status === 'error')
  );
  const [copied, setCopied] = useState(false);
  const outputRef = useRef<HTMLPreElement>(null);
  const [telemetryData, setTelemetryData] = useState<number[]>([]);

  // Update telemetry data periodically when running
  useEffect(() => {
    if (entry.status === 'running') {
      const interval = setInterval(() => {
        setTelemetryData(generateTelemetryData(entry.output, entry.status));
      }, 100);
      return () => clearInterval(interval);
    } else {
      setTelemetryData(generateTelemetryData(entry.output, entry.status));
    }
  }, [entry.output, entry.status]);

  // Auto-expand on error
  useEffect(() => {
    if (entry.status === 'error') {
      setExpanded(true);
    }
  }, [entry.status]);

  // Auto-scroll when streaming (only if user is near bottom)
  useEffect(() => {
    if (isStreaming && outputRef.current && expanded) {
      const el = outputRef.current;
      const isNearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 100;
      if (isNearBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }
  }, [entry.output, isStreaming, expanded]);

  // Format duration as mission clock
  const formatMissionClock = (ms?: number) => {
    if (ms === undefined) return 'T+00:00.0s';
    const seconds = ms / 1000;
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `T+${mins.toString().padStart(2, '0')}:${secs.padStart(4, '0')}s`;
  };

  // Calculate signal strength (0-100)
  const getSignalStrength = () => {
    if (entry.status === 'error') return 25;
    if (entry.status === 'running') return 50 + Math.random() * 30;
    return 100;
  };

  // Get status label
  const getStatusLabel = () => {
    switch (entry.status) {
      case 'running': return 'IN FLIGHT';
      case 'done': return 'ORBIT ACHIEVED';
      case 'error': return 'MISSION ABORT';
    }
  };

  // Handle copy
  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(entry.output || entry.command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const signalStrength = getSignalStrength();

  return (
    <div className={`mission-card mission-card--${entry.status}`}>
      {/* Mission Header */}
      <div className="mission-card__header" onClick={() => setExpanded(!expanded)}>
        <div className="mission-card__title">
          <span className="mission-card__number">MISSION-{missionNumber.toString().padStart(3, '0')}</span>
          <span className="mission-card__arrow">▸</span>
          <span className="mission-card__command">{entry.command}</span>
        </div>
        <ChevronDown
          className={`mission-card__chevron ${expanded ? 'mission-card__chevron--open' : ''}`}
          size={16}
        />
      </div>

      {/* Telemetry Strip */}
      <div className="mission-card__telemetry">
        <div className="telemetry-strip">
          <div className="telemetry-waveform">
            {telemetryData.map((value, i) => (
              <div
                key={i}
                className="telemetry-bar"
                style={{ height: `${value * 100}%` }}
              />
            ))}
          </div>
          <div className="telemetry-rocket">
            {entry.status === 'running' ? '🚀→→→○' : entry.status === 'done' ? '🚀→→→◎' : '🚀✕'}
          </div>
          <div className="telemetry-signal">
            {entry.status === 'running' && <span className="signal-dots">● ● ●</span>}
            {entry.status === 'done' && <span className="signal-dots signal-dots--success">● ● ●</span>}
            {entry.status === 'error' && <span className="signal-dots signal-dots--error">○ ○ ○</span>}
          </div>
          <div className="telemetry-clock">{formatMissionClock(entry.durationMs)}</div>
        </div>
      </div>

      {/* Status Row */}
      <div className="mission-card__status-row">
        <div className="mission-status">
          <span className="mission-status__label">STATUS:</span>
          <div className={`mission-status__badge mission-status__badge--${entry.status}`}>
            {getStatusLabel()}
          </div>
        </div>
        <div className="mission-signal">
          <span className="mission-signal__label">SIGNAL:</span>
          <div className="mission-signal__bar">
            <div
              className={`mission-signal__fill mission-signal__fill--${entry.status}`}
              style={{ width: `${signalStrength}%` }}
            />
          </div>
          <span className="mission-signal__percent">{Math.round(signalStrength)}%</span>
        </div>
      </div>

      {/* Expandable Output */}
      {expanded && (
        <div className="mission-card__output-section">
          <div className="mission-output">
            <div className="mission-output__header">
              <span className="mission-output__title">TRANSMISSION LOG</span>
              <div className="mission-output__actions">
                <button
                  className="mission-action-btn"
                  onClick={handleCopy}
                  title="Copy output"
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                </button>
                {onOpenInTerminal && (
                  <button
                    className="mission-action-btn"
                    onClick={(e) => { e.stopPropagation(); onOpenInTerminal(entry.id); }}
                    title="Open in terminal"
                  >
                    <ExternalLink size={12} />
                  </button>
                )}
              </div>
            </div>
            <pre ref={outputRef} className="mission-output__content">
              {entry.output || '> Awaiting telemetry...'}
              {entry.status === 'running' && <span className="mission-cursor">█</span>}
            </pre>
          </div>

          {/* Mission Data Footer */}
          <div className="mission-card__footer">
            <span className="mission-data">EXIT: {entry.exitCode ?? '-'}</span>
            <span className="mission-data">DURATION: {formatMissionClock(entry.durationMs)}</span>
            {entry.cwd && <span className="mission-data">CWD: {entry.cwd}</span>}
          </div>
        </div>
      )}

      {/* Abort Hazard Stripe (for errors) */}
      {entry.status === 'error' && <div className="mission-card__hazard-stripe" />}
    </div>
  );
};

// Main Panel Component
export const NaviMissionControlPanel: React.FC<NaviMissionControlPanelProps> = ({
  entries,
  onClear,
  onOpenInTerminal,
  defaultOpen = true,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [systemTime, setSystemTime] = useState(new Date());
  const toggleOpen = () => setIsOpen((prev) => !prev);

  // Update system time every second
  useEffect(() => {
    const interval = setInterval(() => setSystemTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const hasRunningCommand = entries.some((e) => e.status === 'running');
  const displayedEntries = entries.slice(-MAX_DISPLAYED_ENTRIES);

  const stats = {
    total: entries.length,
    active: entries.filter((e) => e.status === 'running').length,
    completed: entries.filter((e) => e.status === 'done').length,
    aborted: entries.filter((e) => e.status === 'error').length,
  };

  if (entries.length === 0) return null;

  const formatSystemTime = () => {
    return systemTime.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }) + ' UTC';
  };

  return (
    <div className={`mission-control-panel ${hasRunningCommand ? 'mission-control-panel--active' : ''} ${isOpen ? 'mission-control-panel--open' : ''}`}>
      {/* Panel Header */}
      <div className="mission-control-panel__header">
        <button
          type="button"
          className="mission-control-panel__title-btn"
          onClick={toggleOpen}
          aria-expanded={isOpen}
        >
          <div className="mission-control-panel__title">
            <span className="mission-control-panel__icon">◉</span>
            <span className="mission-control-panel__label">NAVI MISSION CONTROL</span>
          </div>
          <div className="mission-control-panel__time">
            <span className="mission-control-panel__time-icon">⏱</span>
            <span className="mission-control-panel__time-value">SYSTEM: {formatSystemTime()}</span>
          </div>
        </button>

        <div className="mission-control-panel__stats">
          <span className="mission-stat">ACTIVE: {stats.active}</span>
          <span className="mission-stat-divider">│</span>
          <span className="mission-stat">COMPLETED: {stats.completed}</span>
          <span className="mission-stat-divider">│</span>
          <span className="mission-stat mission-stat--error">ABORTED: {stats.aborted}</span>
        </div>

        <div className="mission-control-panel__actions">
          {onClear && entries.length > 0 && (
            <button
              type="button"
              className="mission-control-action"
              onClick={onClear}
              title="Clear mission log"
            >
              <Trash2 size={14} />
            </button>
          )}
          <button
            type="button"
            className="mission-control-panel__chevron-btn"
            onClick={toggleOpen}
            aria-expanded={isOpen}
            aria-label={isOpen ? 'Collapse mission control panel' : 'Expand mission control panel'}
            title={isOpen ? 'Collapse' : 'Expand'}
          >
            <ChevronDown
              className={`mission-control-panel__chevron ${isOpen ? 'mission-control-panel__chevron--open' : ''}`}
              size={16}
            />
          </button>
        </div>
      </div>

      {/* Panel Body */}
      {isOpen && (
        <div className="mission-control-panel__body">
          {displayedEntries.length === 0 ? (
            <div className="mission-control-panel__empty">
              No active missions. Standing by...
            </div>
          ) : (
            <div className="mission-control-panel__missions">
              {displayedEntries.map((entry, index) => (
                <MissionCard
                  key={entry.id}
                  entry={entry}
                  missionNumber={entries.length - displayedEntries.length + index + 1}
                  isStreaming={entry.status === 'running'}
                  defaultExpanded={index === displayedEntries.length - 1 && entry.status === 'running'}
                  onOpenInTerminal={onOpenInTerminal}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NaviMissionControlPanel;
