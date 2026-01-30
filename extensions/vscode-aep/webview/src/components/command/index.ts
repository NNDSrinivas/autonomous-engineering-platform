/**
 * NAVI Command Panel Components
 * Unique NAVI-themed UIs for command execution display
 *
 * Available Themes:
 * - Mission Control: NASA/SpaceX command center aesthetic
 * - Code Archaeology: Archaeological dig site with artifact layers
 * - Neural Pathways: Brain neural network with synaptic connections
 * - Classic: Original NAVI terminal design
 */

// Classic Components
export { NaviCommandPanel } from './NaviCommandPanel';
export { NaviCommandCard, type TerminalEntry } from './NaviCommandCard';
export { NaviStatusRing, type CommandStatus } from './NaviStatusRing';
export { NaviCommandProgress } from './NaviCommandProgress';

// Unique NAVI Themes
export { NaviMissionControlPanel } from './NaviMissionControlPanel';
export { NaviArchaeologyPanel } from './NaviArchaeologyPanel';
export { NaviNeuralPanel } from './NaviNeuralPanel';

// Pro Panel (sleek, futuristic, professional)
export { NaviProPanel } from './NaviProPanel';

// Inline Command (for chat messages)
export { NaviInlineCommand } from './NaviInlineCommand';

// Theme Switcher (combines all themes)
export { NaviCommandPanelSwitcher, type PanelTheme } from './NaviCommandPanelSwitcher';
