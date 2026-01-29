import React, { useState, useEffect, useMemo } from 'react';
import './NaviArchaeologyPanel.css';

// =============================================================================
// NAVI CODE ARCHAEOLOGY PANEL
// =============================================================================
// Archaeological dig theme - Commands are "artifacts" at depth layers
// Older commands sink deeper into the stratum
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

interface NaviArchaeologyPanelProps {
  entries: TerminalEntry[];
  onClear?: () => void;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
  defaultOpen?: boolean;
}

// =============================================================================
// ARTIFACT CARD COMPONENT
// =============================================================================

interface ArtifactCardProps {
  entry: TerminalEntry;
  artifactNumber: number;
  depth: number;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
}

const ArtifactCard: React.FC<ArtifactCardProps> = ({
  entry,
  artifactNumber,
  depth,
  onOpenInTerminal,
}) => {
  const [expanded, setExpanded] = useState(entry.status === 'running');

  // Determine artifact condition based on status
  const getCondition = () => {
    switch (entry.status) {
      case 'running':
        return { label: 'ANALYZING...', symbol: '◐', className: 'analyzing' };
      case 'done':
        return { label: 'PRISTINE', symbol: '✓', className: 'pristine' };
      case 'error':
        return { label: 'FRAGMENTED', symbol: '✗', className: 'fragmented' };
      default:
        return { label: 'UNKNOWN', symbol: '?', className: 'unknown' };
    }
  };

  // Get artifact classification based on command
  const getClassification = () => {
    const cmd = entry.command.toLowerCase();
    if (cmd.startsWith('git')) return 'VERSION_CONTROL';
    if (cmd.startsWith('npm') || cmd.startsWith('yarn') || cmd.startsWith('pnpm')) return 'PACKAGE_MANAGER';
    if (cmd.includes('test') || cmd.includes('jest') || cmd.includes('pytest')) return 'TESTING';
    if (cmd.includes('build') || cmd.includes('compile')) return 'BUILD';
    if (cmd.includes('deploy') || cmd.includes('push')) return 'DEPLOYMENT';
    if (cmd.startsWith('docker') || cmd.startsWith('kubectl')) return 'CONTAINER';
    if (cmd.startsWith('cd') || cmd.startsWith('ls') || cmd.startsWith('mkdir')) return 'FILESYSTEM';
    return 'GENERAL';
  };

  // Calculate progress for running commands
  const getProgress = () => {
    if (entry.status !== 'running') return 100;
    const elapsed = Date.now() - new Date(entry.startedAt).getTime();
    return Math.min(95, Math.floor((elapsed / 30000) * 100));
  };

  const condition = getCondition();
  const classification = getClassification();
  const progress = getProgress();

  // Get artifact symbol based on condition
  const getArtifactSymbol = () => {
    switch (entry.status) {
      case 'running':
        return '◈'; // Diamond - being analyzed
      case 'done':
        return '◇'; // Empty diamond - catalogued
      case 'error':
        return '○'; // Circle - damaged
      default:
        return '◈';
    }
  };

  // Format output for display
  const formatOutput = () => {
    const lines = entry.output.split('\n').filter(line => line.trim());
    if (lines.length === 0) return ['Unearthing data...'];
    return lines.slice(-10); // Show last 10 lines
  };

  return (
    <div className={`artifact-card artifact-${condition.className}`}>
      <div className="artifact-header" onClick={() => setExpanded(!expanded)}>
        <span className="artifact-symbol">{getArtifactSymbol()}</span>
        <span className="artifact-id">ARTIFACT #{String(artifactNumber).padStart(3, '0')}</span>
        <span className="artifact-divider">│</span>
        <span className="artifact-command">{entry.command}</span>
        <span className="artifact-expand">{expanded ? '▾' : '▸'}</span>
      </div>

      <div className="artifact-classification">
        CLASSIFICATION: {classification}
      </div>

      <div className="artifact-condition">
        <span className="condition-label">CONDITION:</span>
        <span className={`condition-value ${condition.className}`}>
          {condition.symbol} {condition.label}
        </span>
      </div>

      {entry.status === 'running' && (
        <div className="artifact-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="progress-text">{progress}%</span>
        </div>
      )}

      {expanded && (
        <div className="artifact-findings">
          <div className="findings-header">─── EXCAVATION LOG ───</div>
          <div className="findings-content">
            {formatOutput().map((line, i) => (
              <div key={i} className="finding-line">{line}</div>
            ))}
          </div>
          {entry.status === 'error' && entry.exitCode !== undefined && (
            <div className="artifact-damage">
              DAMAGE REPORT: Exit code {entry.exitCode}
            </div>
          )}
          {entry.status === 'done' && entry.durationMs !== undefined && (
            <div className="artifact-age">
              ANALYSIS TIME: {(entry.durationMs / 1000).toFixed(1)}s
            </div>
          )}
        </div>
      )}

      <div className="artifact-actions">
        {onOpenInTerminal && (
          <button
            className="artifact-action"
            onClick={(e) => {
              e.stopPropagation();
              onOpenInTerminal(entry);
            }}
            title="Open in Terminal"
          >
            ⛏ EXCAVATE
          </button>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// STRATUM LAYER COMPONENT
// =============================================================================

interface StratumLayerProps {
  depth: number;
  depthLabel: string;
  stratumIndex: number;
  children: React.ReactNode;
}

const StratumLayer: React.FC<StratumLayerProps> = ({
  depth,
  depthLabel,
  stratumIndex,
  children,
}) => {
  // Different stratum patterns based on depth
  const getStratumPattern = () => {
    const patterns = ['░', '▒', '▓', '█'];
    return patterns[Math.min(stratumIndex, patterns.length - 1)];
  };

  return (
    <div className={`stratum-layer stratum-${stratumIndex}`}>
      <div className="stratum-ruler">
        <div className="depth-marker">{depthLabel}</div>
        <div className="stratum-index">
          {stratumIndex > 0 && <span className="stratum-number">{stratumIndex}</span>}
        </div>
      </div>
      <div className="stratum-divider" />
      <div className="stratum-content">
        <div className="stratum-pattern">
          {getStratumPattern().repeat(60)}
        </div>
        {children}
      </div>
    </div>
  );
};

// =============================================================================
// MAIN ARCHAEOLOGY PANEL
// =============================================================================

export const NaviArchaeologyPanel: React.FC<NaviArchaeologyPanelProps> = ({
  entries,
  onClear,
  onOpenInTerminal,
  defaultOpen = true,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(!defaultOpen);

  // Group entries by "stratum" (time periods)
  const stratifiedEntries = useMemo(() => {
    if (entries.length === 0) return [];

    // Calculate depth for each entry (newer = shallower)
    const sorted = [...entries].reverse(); // Oldest first for display
    const now = Date.now();

    return sorted.map((entry, index) => {
      const entryTime = new Date(entry.startedAt).getTime();
      const age = now - entryTime;

      // Calculate stratum based on age (in minutes)
      const ageMinutes = age / 60000;
      let stratumIndex = 0;
      let depthLabel = '0.0m';

      if (ageMinutes < 1) {
        stratumIndex = 0;
        depthLabel = '0.0m';
      } else if (ageMinutes < 5) {
        stratumIndex = 1;
        depthLabel = `${(ageMinutes * 0.3).toFixed(1)}m`;
      } else if (ageMinutes < 15) {
        stratumIndex = 2;
        depthLabel = `${(ageMinutes * 0.2).toFixed(1)}m`;
      } else {
        stratumIndex = 3;
        depthLabel = `${(ageMinutes * 0.15).toFixed(1)}m`;
      }

      return {
        entry,
        artifactNumber: entries.length - index,
        stratumIndex,
        depthLabel,
        depth: index,
      };
    }).reverse(); // Back to newest first
  }, [entries]);

  // Count artifacts by condition
  const stats = useMemo(() => {
    return {
      total: entries.length,
      pristine: entries.filter(e => e.status === 'done').length,
      analyzing: entries.filter(e => e.status === 'running').length,
      fragmented: entries.filter(e => e.status === 'error').length,
    };
  }, [entries]);

  // Get current excavation depth
  const maxDepth = useMemo(() => {
    if (stratifiedEntries.length === 0) return '0.0m';
    return stratifiedEntries[stratifiedEntries.length - 1]?.depthLabel || '0.0m';
  }, [stratifiedEntries]);

  if (isCollapsed) {
    return (
      <div className="archaeology-panel collapsed" onClick={() => setIsCollapsed(false)}>
        <div className="collapsed-header">
          <span className="collapsed-icon">⛏</span>
          <span className="collapsed-title">NAVI EXCAVATION SITE</span>
          <span className="collapsed-stats">
            {stats.total} artifacts · Depth: {maxDepth}
          </span>
          <span className="collapsed-expand">▸</span>
        </div>
      </div>
    );
  }

  return (
    <div className="archaeology-panel">
      {/* Site Header */}
      <div className="site-header">
        <div className="site-title" onClick={() => setIsCollapsed(true)}>
          <span className="site-icon">⛏</span>
          <span className="title-text">NAVI EXCAVATION SITE</span>
          <span className="collapse-btn">▾</span>
        </div>
        <div className="site-info">
          <span className="depth-badge">◈ SURFACE</span>
          <span className="info-divider">│</span>
          <span className="depth-current">DEPTH: {maxDepth}</span>
          <span className="info-divider">│</span>
          <span className="artifact-count">{stats.total} artifacts</span>
        </div>
        {onClear && entries.length > 0 && (
          <button className="site-clear" onClick={onClear} title="Clear excavation site">
            BACKFILL
          </button>
        )}
      </div>

      {/* Legend */}
      <div className="site-legend">
        <div className="legend-item pristine">
          <span className="legend-symbol">◇</span>
          <span className="legend-label">Pristine ({stats.pristine})</span>
        </div>
        <div className="legend-item analyzing">
          <span className="legend-symbol">◈</span>
          <span className="legend-label">Analyzing ({stats.analyzing})</span>
        </div>
        <div className="legend-item fragmented">
          <span className="legend-symbol">○</span>
          <span className="legend-label">Fragmented ({stats.fragmented})</span>
        </div>
      </div>

      {/* Excavation Area */}
      <div className="excavation-area">
        {entries.length === 0 ? (
          <div className="no-artifacts">
            <div className="dig-icon">⛏</div>
            <div className="dig-message">No artifacts discovered yet</div>
            <div className="dig-hint">Begin excavation to uncover command artifacts</div>
          </div>
        ) : (
          <>
            {/* Surface Layer */}
            <div className="surface-marker">
              <span className="surface-line">═══════════════════════════════</span>
              <span className="surface-label">▲ SURFACE LEVEL ▲</span>
              <span className="surface-line">═══════════════════════════════</span>
            </div>

            {/* Artifact Layers */}
            {stratifiedEntries.map((item, index) => (
              <StratumLayer
                key={item.entry.id}
                depth={item.depth}
                depthLabel={item.depthLabel}
                stratumIndex={item.stratumIndex}
              >
                <ArtifactCard
                  entry={item.entry}
                  artifactNumber={item.artifactNumber}
                  depth={item.depth}
                  onOpenInTerminal={onOpenInTerminal}
                />
              </StratumLayer>
            ))}

            {/* Bedrock */}
            <div className="bedrock-marker">
              <span className="bedrock-pattern">████████████████████████████████████████</span>
              <span className="bedrock-label">▼▼▼ BEDROCK (Session Start) ▼▼▼</span>
              <span className="bedrock-pattern">████████████████████████████████████████</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default NaviArchaeologyPanel;
