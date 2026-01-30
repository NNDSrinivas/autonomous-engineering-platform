import React, { useState, useEffect, useMemo, useRef } from 'react';
import './NaviNeuralPanel.css';

// =============================================================================
// NAVI NEURAL PATHWAYS PANEL
// =============================================================================
// Brain neural network theme - Commands are neurons connected by synapses
// Running commands show active neural firing
// Connections show command dependencies/relationships
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

interface NaviNeuralPanelProps {
  entries: TerminalEntry[];
  onClear?: () => void;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
  defaultOpen?: boolean;
}

// =============================================================================
// NEURON COMPONENT
// =============================================================================

interface NeuronProps {
  entry: TerminalEntry;
  neuronId: number;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
}

const Neuron: React.FC<NeuronProps> = ({
  entry,
  neuronId,
  onOpenInTerminal,
}) => {
  const [expanded, setExpanded] = useState(entry.status === 'running');
  const [pulseCount, setPulseCount] = useState(0);

  // Simulate neural firing for running commands
  useEffect(() => {
    if (entry.status === 'running') {
      const interval = setInterval(() => {
        setPulseCount(p => p + 1);
      }, 800);
      return () => clearInterval(interval);
    }
  }, [entry.status]);

  // Get neuron state
  const getNeuronState = () => {
    switch (entry.status) {
      case 'running':
        return { label: 'FIRING', className: 'firing', symbol: '⚡' };
      case 'done':
        return { label: 'RESTING', className: 'resting', symbol: '◉' };
      case 'error':
        return { label: 'INHIBITED', className: 'inhibited', symbol: '◎' };
      default:
        return { label: 'DORMANT', className: 'dormant', symbol: '○' };
    }
  };

  // Get neurotransmitter type based on command
  const getNeurotransmitter = () => {
    const cmd = entry.command.toLowerCase();
    if (cmd.startsWith('git')) return { type: 'DOPAMINE', color: '#FF6B9D' }; // Version control = reward
    if (cmd.includes('test') || cmd.includes('jest')) return { type: 'SEROTONIN', color: '#6BFFB8' }; // Testing = stability
    if (cmd.includes('build') || cmd.includes('compile')) return { type: 'ADRENALINE', color: '#FFD93D' }; // Build = action
    if (cmd.startsWith('npm') || cmd.startsWith('yarn')) return { type: 'GLUTAMATE', color: '#6BB3FF' }; // Package = excitatory
    if (cmd.includes('deploy') || cmd.includes('push')) return { type: 'NOREPINEPHRINE', color: '#FF8C42' }; // Deploy = alertness
    return { type: 'ACETYLCHOLINE', color: '#B388FF' }; // General = learning
  };

  // Calculate signal strength
  const getSignalStrength = () => {
    if (entry.status !== 'running') return 100;
    const elapsed = Date.now() - new Date(entry.startedAt).getTime();
    return Math.min(95, Math.floor((elapsed / 20000) * 100));
  };

  const state = getNeuronState();
  const transmitter = getNeurotransmitter();
  const signalStrength = getSignalStrength();

  // Format output as neural signals
  const formatSignals = () => {
    const lines = entry.output.split('\n').filter(line => line.trim());
    if (lines.length === 0) return ['Awaiting signal transmission...'];
    return lines.slice(-8);
  };

  return (
    <div className={`neuron neuron-${state.className}`}>
      {/* Dendrites visualization */}
      <div className="dendrites">
        <span className="dendrite d1">╲</span>
        <span className="dendrite d2">│</span>
        <span className="dendrite d3">╱</span>
      </div>

      {/* Cell Body (Soma) */}
      <div className="soma" onClick={() => setExpanded(!expanded)}>
        <div className="nucleus">
          <span className="neuron-symbol">{state.symbol}</span>
        </div>
        <div className="soma-info">
          <div className="neuron-id">N-{String(neuronId).padStart(3, '0')}</div>
          <div className="neuron-command">{entry.command}</div>
        </div>
        <div className="soma-state">
          <span className={`state-badge ${state.className}`}>{state.label}</span>
        </div>
        <span className="expand-indicator">{expanded ? '▾' : '▸'}</span>
      </div>

      {/* Neurotransmitter Badge */}
      <div className="transmitter-badge" style={{ borderColor: transmitter.color }}>
        <span className="transmitter-dot" style={{ background: transmitter.color }} />
        <span className="transmitter-type">{transmitter.type}</span>
      </div>

      {/* Signal Strength (for running) */}
      {entry.status === 'running' && (
        <div className="signal-meter">
          <div className="signal-label">SIGNAL PROPAGATION</div>
          <div className="signal-bar">
            <div
              className="signal-fill"
              style={{ width: `${signalStrength}%` }}
            />
            <div className="signal-pulse" key={pulseCount} />
          </div>
          <div className="signal-value">{signalStrength}%</div>
        </div>
      )}

      {/* Axon Terminal (Output) */}
      {expanded && (
        <div className="axon-terminal">
          <div className="terminal-header">
            <span className="terminal-icon">⟡</span>
            <span className="terminal-title">AXON TERMINAL</span>
            <span className="terminal-icon">⟡</span>
          </div>
          <div className="synaptic-output">
            {formatSignals().map((signal, i) => (
              <div key={i} className="signal-line">
                <span className="signal-prefix">›</span>
                {signal}
              </div>
            ))}
          </div>
          {entry.status === 'error' && entry.exitCode !== undefined && (
            <div className="inhibition-notice">
              ⚠ SYNAPTIC FAILURE: Signal terminated (code {entry.exitCode})
            </div>
          )}
          {entry.status === 'done' && entry.durationMs !== undefined && (
            <div className="transmission-time">
              ✓ Transmission complete: {(entry.durationMs / 1000).toFixed(2)}s
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="neuron-actions">
        {onOpenInTerminal && (
          <button
            className="neuron-action"
            onClick={(e) => {
              e.stopPropagation();
              onOpenInTerminal(entry);
            }}
          >
            ⚡ STIMULATE
          </button>
        )}
      </div>

      {/* Axon leading to next neuron */}
      <div className="axon">
        <span className="axon-line">│</span>
        <span className="axon-hillock">▼</span>
      </div>
    </div>
  );
};

// =============================================================================
// SYNAPSE CONNECTIONS (SVG)
// =============================================================================

interface SynapseConnectionsProps {
  neuronCount: number;
}

const SynapseConnections: React.FC<SynapseConnectionsProps> = ({ neuronCount }) => {
  if (neuronCount < 2) return null;

  // Generate random-looking but deterministic connections
  const connections = useMemo(() => {
    const conns = [];
    for (let i = 0; i < Math.min(neuronCount - 1, 5); i++) {
      conns.push({
        id: i,
        x1: 20 + (i * 15) % 40,
        x2: 60 + (i * 20) % 40,
        delay: i * 0.2,
      });
    }
    return conns;
  }, [neuronCount]);

  return (
    <div className="synapse-overlay">
      <svg className="synapse-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
        {connections.map(conn => (
          <path
            key={conn.id}
            className="synapse-path"
            d={`M ${conn.x1} 0 Q 50 50 ${conn.x2} 100`}
            style={{ animationDelay: `${conn.delay}s` }}
          />
        ))}
      </svg>
    </div>
  );
};

// =============================================================================
// MAIN NEURAL PANEL
// =============================================================================

export const NaviNeuralPanel: React.FC<NaviNeuralPanelProps> = ({
  entries,
  onClear,
  onOpenInTerminal,
  defaultOpen = true,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(!defaultOpen);
  const [brainActivity, setBrainActivity] = useState(0);

  // Simulate brain activity meter
  useEffect(() => {
    const activeCount = entries.filter(e => e.status === 'running').length;
    const targetActivity = activeCount > 0 ? 60 + activeCount * 15 : 20;

    const interval = setInterval(() => {
      setBrainActivity(prev => {
        const diff = targetActivity - prev;
        return prev + diff * 0.1 + (Math.random() * 10 - 5);
      });
    }, 200);

    return () => clearInterval(interval);
  }, [entries]);

  // Calculate neural stats
  const stats = useMemo(() => ({
    total: entries.length,
    firing: entries.filter(e => e.status === 'running').length,
    resting: entries.filter(e => e.status === 'done').length,
    inhibited: entries.filter(e => e.status === 'error').length,
  }), [entries]);

  if (isCollapsed) {
    return (
      <div className="neural-panel collapsed" onClick={() => setIsCollapsed(false)}>
        <div className="collapsed-header">
          <span className="brain-icon">🧠</span>
          <span className="collapsed-title">NAVI NEURAL NETWORK</span>
          <span className="collapsed-stats">
            {stats.total} neurons · {stats.firing} firing
          </span>
          <span className="collapsed-expand">▸</span>
        </div>
      </div>
    );
  }

  return (
    <div className="neural-panel">
      {/* Brain Header */}
      <div className="brain-header">
        <div className="header-title" onClick={() => setIsCollapsed(true)}>
          <span className="brain-icon">🧠</span>
          <span className="title-text">NAVI NEURAL NETWORK</span>
          <span className="collapse-btn">▾</span>
        </div>

        {/* Brain Activity Monitor */}
        <div className="activity-monitor">
          <div className="activity-label">CORTICAL ACTIVITY</div>
          <div className="activity-wave">
            <div
              className="wave-bar"
              style={{ height: `${Math.max(10, Math.min(100, brainActivity))}%` }}
            />
            <div
              className="wave-bar"
              style={{ height: `${Math.max(10, Math.min(100, brainActivity + 10))}%` }}
            />
            <div
              className="wave-bar"
              style={{ height: `${Math.max(10, Math.min(100, brainActivity - 5))}%` }}
            />
            <div
              className="wave-bar"
              style={{ height: `${Math.max(10, Math.min(100, brainActivity + 15))}%` }}
            />
            <div
              className="wave-bar"
              style={{ height: `${Math.max(10, Math.min(100, brainActivity))}%` }}
            />
          </div>
          <div className="activity-value">{Math.floor(brainActivity)}%</div>
        </div>

        {onClear && entries.length > 0 && (
          <button className="clear-btn" onClick={onClear}>
            RESET NETWORK
          </button>
        )}
      </div>

      {/* Neural Stats */}
      <div className="neural-stats">
        <div className="stat firing">
          <span className="stat-symbol">⚡</span>
          <span className="stat-value">{stats.firing}</span>
          <span className="stat-label">FIRING</span>
        </div>
        <div className="stat resting">
          <span className="stat-symbol">◉</span>
          <span className="stat-value">{stats.resting}</span>
          <span className="stat-label">RESTING</span>
        </div>
        <div className="stat inhibited">
          <span className="stat-symbol">◎</span>
          <span className="stat-value">{stats.inhibited}</span>
          <span className="stat-label">INHIBITED</span>
        </div>
        <div className="stat total">
          <span className="stat-symbol">⬡</span>
          <span className="stat-value">{stats.total}</span>
          <span className="stat-label">TOTAL</span>
        </div>
      </div>

      {/* Neural Network Area */}
      <div className="network-area">
        {entries.length === 0 ? (
          <div className="no-neurons">
            <div className="empty-brain">🧠</div>
            <div className="empty-message">Neural network dormant</div>
            <div className="empty-hint">Execute commands to create neurons</div>
          </div>
        ) : (
          <div className="neuron-chain">
            {/* Synapse Background */}
            <SynapseConnections neuronCount={entries.length} />

            {/* Input Signal */}
            <div className="input-signal">
              <span className="signal-arrow">▼</span>
              <span className="signal-text">INPUT STIMULUS</span>
              <span className="signal-arrow">▼</span>
            </div>

            {/* Neurons */}
            {entries.map((entry, index) => (
              <Neuron
                key={entry.id}
                entry={entry}
                neuronId={entries.length - index}
                onOpenInTerminal={onOpenInTerminal}
              />
            ))}

            {/* Output Signal */}
            <div className="output-signal">
              <span className="signal-arrow">▼</span>
              <span className="signal-text">MOTOR OUTPUT</span>
              <span className="signal-arrow">▼</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NaviNeuralPanel;
