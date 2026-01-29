import React, { useState, useCallback } from 'react';
import { NaviMissionControlPanel } from './NaviMissionControlPanel';
import { NaviArchaeologyPanel } from './NaviArchaeologyPanel';
import { NaviNeuralPanel } from './NaviNeuralPanel';
import { NaviCommandPanel } from './NaviCommandPanel';
import { TerminalEntry } from './NaviCommandCard';
import './NaviCommandPanelSwitcher.css';

// =============================================================================
// NAVI COMMAND PANEL SWITCHER
// =============================================================================
// Allows switching between different NAVI command panel themes:
// - Mission Control (NASA/SpaceX aesthetic)
// - Code Archaeology (Archaeological dig theme)
// - Neural Pathways (Brain/neuron network theme)
// - Classic (Original terminal style)
// =============================================================================

export type PanelTheme = 'mission-control' | 'archaeology' | 'neural' | 'classic';

interface ThemeOption {
  id: PanelTheme;
  name: string;
  icon: string;
  description: string;
}

const THEME_OPTIONS: ThemeOption[] = [
  {
    id: 'mission-control',
    name: 'Mission Control',
    icon: '🛰️',
    description: 'NASA/SpaceX command center aesthetic',
  },
  {
    id: 'archaeology',
    name: 'Code Archaeology',
    icon: '⛏️',
    description: 'Archaeological dig site with artifact layers',
  },
  {
    id: 'neural',
    name: 'Neural Pathways',
    icon: '🧠',
    description: 'Brain neural network with synaptic connections',
  },
  {
    id: 'classic',
    name: 'Classic Terminal',
    icon: '💻',
    description: 'Original NAVI terminal design',
  },
];

interface NaviCommandPanelSwitcherProps {
  entries: TerminalEntry[];
  onClear?: () => void;
  onOpenInTerminal?: (entry: TerminalEntry) => void;
  defaultOpen?: boolean;
  defaultTheme?: PanelTheme;
  showThemeSwitcher?: boolean;
}

export const NaviCommandPanelSwitcher: React.FC<NaviCommandPanelSwitcherProps> = ({
  entries,
  onClear,
  onOpenInTerminal,
  defaultOpen = true,
  defaultTheme = 'mission-control',
  showThemeSwitcher = true,
}) => {
  const [currentTheme, setCurrentTheme] = useState<PanelTheme>(defaultTheme);
  const [isThemeSelectorOpen, setIsThemeSelectorOpen] = useState(false);

  // Adapter for classic panel (uses id: string instead of entry: TerminalEntry)
  const handleOpenInTerminalClassic = useCallback(
    (id: string) => {
      const entry = entries.find(e => e.id === id);
      if (entry && onOpenInTerminal) {
        onOpenInTerminal(entry);
      }
    },
    [entries, onOpenInTerminal]
  );

  const currentThemeOption = THEME_OPTIONS.find(t => t.id === currentTheme) || THEME_OPTIONS[0];

  // Don't render if no entries
  if (entries.length === 0) {
    return null;
  }

  const renderPanel = () => {
    switch (currentTheme) {
      case 'mission-control':
        return (
          <NaviMissionControlPanel
            entries={entries}
            onClear={onClear}
            onOpenInTerminal={onOpenInTerminal}
            defaultOpen={defaultOpen}
          />
        );
      case 'archaeology':
        return (
          <NaviArchaeologyPanel
            entries={entries}
            onClear={onClear}
            onOpenInTerminal={onOpenInTerminal}
            defaultOpen={defaultOpen}
          />
        );
      case 'neural':
        return (
          <NaviNeuralPanel
            entries={entries}
            onClear={onClear}
            onOpenInTerminal={onOpenInTerminal}
            defaultOpen={defaultOpen}
          />
        );
      case 'classic':
      default:
        return (
          <NaviCommandPanel
            entries={entries}
            onClear={onClear}
            onOpenInTerminal={handleOpenInTerminalClassic}
            defaultOpen={defaultOpen}
          />
        );
    }
  };

  return (
    <div className="navi-panel-switcher">
      {/* Theme Switcher Button */}
      {showThemeSwitcher && (
        <div className="theme-switcher-container">
          <button
            className="theme-switcher-button"
            onClick={() => setIsThemeSelectorOpen(!isThemeSelectorOpen)}
            title="Switch panel theme"
          >
            <span className="theme-icon">{currentThemeOption.icon}</span>
            <span className="theme-name">{currentThemeOption.name}</span>
            <span className="theme-chevron">{isThemeSelectorOpen ? '▲' : '▼'}</span>
          </button>

          {/* Theme Selector Dropdown */}
          {isThemeSelectorOpen && (
            <div className="theme-selector-dropdown">
              <div className="theme-selector-header">
                <span className="header-icon">🎨</span>
                <span className="header-text">SELECT PANEL THEME</span>
              </div>
              <div className="theme-options">
                {THEME_OPTIONS.map(theme => (
                  <button
                    key={theme.id}
                    className={`theme-option ${theme.id === currentTheme ? 'theme-option--active' : ''}`}
                    onClick={() => {
                      setCurrentTheme(theme.id);
                      setIsThemeSelectorOpen(false);
                    }}
                  >
                    <span className="option-icon">{theme.icon}</span>
                    <div className="option-content">
                      <span className="option-name">{theme.name}</span>
                      <span className="option-description">{theme.description}</span>
                    </div>
                    {theme.id === currentTheme && (
                      <span className="option-check">✓</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Active Panel */}
      <div className="panel-container">
        {renderPanel()}
      </div>
    </div>
  );
};

export default NaviCommandPanelSwitcher;
