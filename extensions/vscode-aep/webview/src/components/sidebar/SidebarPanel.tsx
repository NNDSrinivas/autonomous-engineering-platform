import React, { useState, useEffect } from 'react';
import { McpToolsPanel } from './McpToolsPanel';
import { ConnectorsPanel } from './ConnectorsPanel';
import { AccountPanel } from './AccountPanel';
import '../../styles/futuristic.css';
import { McpExecutionResult } from '../../api/navi/client';

// Organization Rule interface
interface OrganizationRule {
  id: string;
  name: string;
  description: string;
  type: 'coding_standard' | 'naming_convention' | 'security' | 'testing' | 'custom';
  enabled: boolean;
  priority: 'low' | 'medium' | 'high';
}

// AI Behavior Setting interface
interface AiBehaviorSetting {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
}

// Premium animated icons with gradient support
const ToolsIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="sidebar-icon">
    <defs>
      <linearGradient id="toolsGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#00d4ff" />
        <stop offset="100%" stopColor="#7c3aed" />
      </linearGradient>
    </defs>
    <path
      d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
      stroke="url(#toolsGrad)"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const ConnectorsIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="sidebar-icon">
    <defs>
      <linearGradient id="connectGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#10b981" />
        <stop offset="100%" stopColor="#00d4ff" />
      </linearGradient>
    </defs>
    <circle cx="6" cy="6" r="3" stroke="url(#connectGrad)" strokeWidth="2" />
    <circle cx="18" cy="18" r="3" stroke="url(#connectGrad)" strokeWidth="2" />
    <path d="M8.5 8.5L15.5 15.5" stroke="url(#connectGrad)" strokeWidth="2" strokeLinecap="round" />
    <circle cx="18" cy="6" r="3" stroke="url(#connectGrad)" strokeWidth="2" />
    <circle cx="6" cy="18" r="3" stroke="url(#connectGrad)" strokeWidth="2" />
    <path d="M15.5 8.5L8.5 15.5" stroke="url(#connectGrad)" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const UserIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="sidebar-icon">
    <defs>
      <linearGradient id="userGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#ef4444" />
      </linearGradient>
    </defs>
    <circle cx="12" cy="8" r="4" stroke="url(#userGrad)" strokeWidth="2" />
    <path d="M4 20c0-4 4-6 8-6s8 2 8 6" stroke="url(#userGrad)" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const RulesIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="sidebar-icon">
    <defs>
      <linearGradient id="rulesGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#ec4899" />
        <stop offset="100%" stopColor="#8b5cf6" />
      </linearGradient>
    </defs>
    <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="url(#rulesGrad)" strokeWidth="2" strokeLinejoin="round" />
    <path d="M2 17l10 5 10-5" stroke="url(#rulesGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M2 12l10 5 10-5" stroke="url(#rulesGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ArrowIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="arrow-icon">
    <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ExpandIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

type PanelType = 'mcp' | 'connectors' | 'account' | 'rules' | null;

interface SidebarPanelProps {
  isAuthenticated: boolean;
  user?: {
    email?: string;
    name?: string;
    picture?: string;
    role?: string;
  };
  onSignIn: () => void;
  onSignOut: () => void;
  onExecuteMcpTool: (toolName: string, args: Record<string, unknown>, serverId?: string | number) => Promise<McpExecutionResult>;
  onOpenFullPanel?: () => void;
  onOpenEnterpriseProjects?: () => void;
  externalPanelRequest?: PanelType;
  onClearExternalPanelRequest?: () => void;
}

interface MenuItemProps {
  icon: React.ReactNode;
  label: string;
  description: string;
  badge?: string;
  badgeColor?: string;
  isActive?: boolean;
  hasStatus?: boolean;
  onClick: () => void;
}

const MenuItem: React.FC<MenuItemProps> = ({
  icon,
  label,
  description,
  badge,
  badgeColor = 'primary',
  isActive,
  hasStatus,
  onClick,
}) => (
  <button
    className={`navi-menu-item ${isActive ? 'active' : ''}`}
    onClick={onClick}
  >
    <div className="navi-menu-item__icon-container">
      <div className="navi-menu-item__icon-bg" />
      <div className="navi-menu-item__icon">
        {icon}
      </div>
      <div className="navi-menu-item__icon-glow" />
    </div>
    <div className="navi-menu-item__content">
      <div className="navi-menu-item__header">
        <span className="navi-menu-item__label">{label}</span>
        {badge && (
          <span className={`navi-menu-item__badge navi-menu-item__badge--${badgeColor}`}>
            {badge}
          </span>
        )}
        {hasStatus && <span className="navi-menu-item__status" />}
      </div>
      <span className="navi-menu-item__description">{description}</span>
    </div>
    <div className="navi-menu-item__arrow">
      <ArrowIcon />
    </div>
  </button>
);

// Default AI behavior settings
const defaultAiSettings: AiBehaviorSetting[] = [
  {
    id: 'approval_destructive',
    label: 'Require approval for destructive operations',
    description: 'Git force push, database migrations, file deletions',
    enabled: true,
  },
  {
    id: 'follow_standards',
    label: 'Follow organization coding standards',
    description: 'Enforce naming conventions, file structure',
    enabled: true,
  },
  {
    id: 'auto_execute_safe',
    label: 'Auto-execute safe operations',
    description: 'Skip confirmation for read-only commands',
    enabled: false,
  },
  {
    id: 'explain_changes',
    label: 'Explain changes before executing',
    description: 'Provide detailed explanation of what will be changed',
    enabled: true,
  },
  {
    id: 'prefer_local_context',
    label: 'Prefer local codebase patterns',
    description: 'Match existing code style in the repository',
    enabled: true,
  },
];

export const SidebarPanel: React.FC<SidebarPanelProps> = ({
  isAuthenticated,
  user,
  onSignIn,
  onSignOut,
  onExecuteMcpTool,
  onOpenFullPanel,
  onOpenEnterpriseProjects,
  externalPanelRequest,
  onClearExternalPanelRequest,
}) => {
  const [openPanel, setOpenPanel] = useState<PanelType>(null);

  // Handle external panel requests from extension
  useEffect(() => {
    if (externalPanelRequest) {
      setOpenPanel(externalPanelRequest);
      onClearExternalPanelRequest?.();
    }
  }, [externalPanelRequest, onClearExternalPanelRequest]);

  // Organization Rules state
  const [orgRules, setOrgRules] = useState<OrganizationRule[]>([]);
  const [showAddRuleModal, setShowAddRuleModal] = useState(false);
  const [newRule, setNewRule] = useState<Partial<OrganizationRule>>({
    name: '',
    description: '',
    type: 'custom',
    priority: 'medium',
    enabled: true,
  });
  const [addingRule, setAddingRule] = useState(false);

  // AI Behavior Settings state
  const [aiSettings, setAiSettings] = useState<AiBehaviorSetting[]>(defaultAiSettings);

  const handleClosePanel = () => setOpenPanel(null);

  // Organization rules handlers
  const handleAddRule = async () => {
    if (!newRule.name) return;

    setAddingRule(true);
    await new Promise(resolve => setTimeout(resolve, 500));

    const rule: OrganizationRule = {
      id: `rule-${Date.now()}`,
      name: newRule.name!,
      description: newRule.description || '',
      type: newRule.type || 'custom',
      priority: newRule.priority || 'medium',
      enabled: true,
    };

    setOrgRules(prev => [...prev, rule]);
    setNewRule({ name: '', description: '', type: 'custom', priority: 'medium', enabled: true });
    setShowAddRuleModal(false);
    setAddingRule(false);
  };

  const handleRemoveRule = (ruleId: string) => {
    setOrgRules(prev => prev.filter(r => r.id !== ruleId));
  };

  const handleToggleRule = (ruleId: string) => {
    setOrgRules(prev =>
      prev.map(r => r.id === ruleId ? { ...r, enabled: !r.enabled } : r)
    );
  };

  const handleToggleAiSetting = (settingId: string) => {
    setAiSettings(prev =>
      prev.map(s => s.id === settingId ? { ...s, enabled: !s.enabled } : s)
    );
  };

  const getRuleTypeIcon = (type: OrganizationRule['type']) => {
    switch (type) {
      case 'coding_standard':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M16 18l2-2-2-2M8 18l-2-2 2-2M12 2v20" />
          </svg>
        );
      case 'naming_convention':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 7V4h16v3M9 20h6M12 4v16" />
          </svg>
        );
      case 'security':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        );
      case 'testing':
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
          </svg>
        );
      default:
        return (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
        );
    }
  };

  return (
    <div className="navi-sidebar">
      {/* Modern Header with Gradient */}
      <div className="navi-sidebar__header-modern">
        <div className="navi-sidebar__header-glow" />
        <div className="navi-sidebar__header-content">
          <div className="navi-sidebar__header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="url(#cmdGrad)" />
              <defs>
                <linearGradient id="cmdGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#00d4ff" />
                  <stop offset="100%" stopColor="#7c3aed" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div className="navi-sidebar__header-text">
            <span className="navi-sidebar__header-title">Command Center</span>
            <span className="navi-sidebar__header-sub">AI Workspace</span>
          </div>
          {onOpenFullPanel && (
            <button
              className="navi-sidebar__header-expand"
              onClick={onOpenFullPanel}
              title="Open in full panel"
            >
              <ExpandIcon />
            </button>
          )}
        </div>
      </div>

      {/* Menu Items */}
      <div className="navi-sidebar__menu">
        <MenuItem
          icon={<ToolsIcon />}
          label="MCP Tools"
          description="Git, Database, Debug & Analysis"
          badge="27"
          badgeColor="primary"
          onClick={() => setOpenPanel('mcp')}
        />

        <MenuItem
          icon={<ConnectorsIcon />}
          label="Integrations"
          description="Connect external services"
          badge="6"
          badgeColor="success"
          onClick={() => setOpenPanel('connectors')}
        />

        <MenuItem
          icon={<UserIcon />}
          label="Account"
          description="Profile & preferences"
          hasStatus={isAuthenticated}
          onClick={() => setOpenPanel('account')}
        />

        <MenuItem
          icon={<RulesIcon />}
          label="NAVI Rules"
          description="Customize AI behavior"
          badge="NEW"
          badgeColor="accent"
          onClick={() => setOpenPanel('rules')}
        />
      </div>

      {/* Spacer to push footer down */}
      <div className="navi-sidebar__spacer" />

      {/* Footer - Minimal */}
      <div className="navi-sidebar__footer-minimal">
        <span className="navi-sidebar__version-badge">v3.0</span>
      </div>

      {/* Overlay Panels */}
      <McpToolsPanel
        isOpen={openPanel === 'mcp'}
        onClose={handleClosePanel}
        onExecuteTool={onExecuteMcpTool}
        canManageServers={user?.role === 'admin'}
      />

      <ConnectorsPanel
        isOpen={openPanel === 'connectors'}
        onClose={handleClosePanel}
      />

      <AccountPanel
        isOpen={openPanel === 'account'}
        onClose={handleClosePanel}
        isAuthenticated={isAuthenticated}
        user={user}
        onSignIn={onSignIn}
        onSignOut={onSignOut}
        onOpenEnterpriseProjects={onOpenEnterpriseProjects}
      />

      {/* Rules Panel - Full featured */}
      {openPanel === 'rules' && (
        <div className="navi-overlay" onClick={handleClosePanel}>
          <div className="navi-overlay-panel navi-overlay-panel--large" onClick={e => e.stopPropagation()}>
            <div className="navi-overlay-header">
              <div className="navi-overlay-header__title">
                <RulesIcon />
                <h3>NAVI Rules & Configuration</h3>
              </div>
              <button className="navi-overlay-close" onClick={handleClosePanel}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="navi-overlay-content">
              {/* Organization Rules Section */}
              <div className="navi-rules-section">
                <div className="navi-rules-section__header">
                  <div>
                    <h4 className="navi-rules-section__title">Organization Rules</h4>
                    <p className="navi-rules-section__description">
                      Define coding standards and guidelines that NAVI will follow for your organization.
                    </p>
                  </div>
                  <button className="navi-rules-section__add" onClick={() => setShowAddRuleModal(true)}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 8v8M8 12h8" />
                    </svg>
                    Add Rule
                  </button>
                </div>

                {orgRules.length === 0 ? (
                  <div className="navi-rules-empty">
                    <div className="navi-rules-empty__icon">
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                        <rect x="9" y="3" width="6" height="4" rx="1" />
                        <path d="M9 12h6M9 16h6" />
                      </svg>
                    </div>
                    <p>No organization rules configured yet.</p>
                    <span className="navi-rules-empty__hint">Add rules to customize how NAVI writes and reviews code</span>
                    <button className="navi-btn navi-btn--primary" onClick={() => setShowAddRuleModal(true)}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 5v14M5 12h14" />
                      </svg>
                      Add Your First Rule
                    </button>
                  </div>
                ) : (
                  <div className="navi-rules-list">
                    {orgRules.map((rule) => (
                      <div key={rule.id} className={`navi-rule-card ${!rule.enabled ? 'navi-rule-card--disabled' : ''}`}>
                        <div className="navi-rule-card__header">
                          <div className="navi-rule-card__icon">
                            {getRuleTypeIcon(rule.type)}
                          </div>
                          <div className="navi-rule-card__info">
                            <span className="navi-rule-card__name">{rule.name}</span>
                            <span className={`navi-rule-card__priority navi-rule-card__priority--${rule.priority}`}>
                              {rule.priority}
                            </span>
                          </div>
                          <div className="navi-rule-card__actions">
                            <button
                              className="navi-rule-card__btn"
                              onClick={() => handleToggleRule(rule.id)}
                              title={rule.enabled ? 'Disable' : 'Enable'}
                            >
                              {rule.enabled ? (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="1" y="5" width="22" height="14" rx="7" />
                                  <circle cx="16" cy="12" r="3" fill="currentColor" />
                                </svg>
                              ) : (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="1" y="5" width="22" height="14" rx="7" />
                                  <circle cx="8" cy="12" r="3" />
                                </svg>
                              )}
                            </button>
                            <button
                              className="navi-rule-card__btn navi-rule-card__btn--danger"
                              onClick={() => handleRemoveRule(rule.id)}
                              title="Remove"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        {rule.description && (
                          <p className="navi-rule-card__description">{rule.description}</p>
                        )}
                        <div className="navi-rule-card__type">
                          {rule.type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* AI Behavior Settings Section */}
              <div className="navi-rules-section">
                <h4 className="navi-rules-section__title">AI Behavior Settings</h4>
                <p className="navi-rules-section__description">
                  Customize how NAVI responds and interacts with your codebase.
                </p>
                <div className="navi-rules-options">
                  {aiSettings.map((setting) => (
                    <label key={setting.id} className="navi-rules-option">
                      <input
                        type="checkbox"
                        checked={setting.enabled}
                        onChange={() => handleToggleAiSetting(setting.id)}
                      />
                      <span className="navi-rules-option__checkmark" />
                      <div className="navi-rules-option__content">
                        <span className="navi-rules-option__label">{setting.label}</span>
                        <span className="navi-rules-option__hint">{setting.description}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Quick Tips Section */}
              <div className="navi-rules-section navi-rules-tips">
                <div className="navi-rules-tips__icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                </div>
                <div className="navi-rules-tips__content">
                  <h5>Pro Tips</h5>
                  <ul>
                    <li>Create rules for your team's coding standards to ensure consistency</li>
                    <li>Use high priority for critical security rules</li>
                    <li>Rules are applied automatically when NAVI generates code</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Rule Modal */}
      {showAddRuleModal && (
        <div className="navi-modal-overlay" onClick={() => setShowAddRuleModal(false)}>
          <div className="navi-modal" onClick={e => e.stopPropagation()}>
            <div className="navi-modal__header">
              <h3>Add Organization Rule</h3>
              <button className="navi-modal__close" onClick={() => setShowAddRuleModal(false)}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="navi-modal__content">
              <p className="navi-modal__description">
                Define a rule that NAVI will follow when writing or reviewing code for your organization.
              </p>

              <div className="navi-modal__field">
                <label>Rule Name *</label>
                <input
                  type="text"
                  placeholder="e.g., Use TypeScript strict mode"
                  value={newRule.name}
                  onChange={(e) => setNewRule(prev => ({ ...prev, name: e.target.value }))}
                />
              </div>

              <div className="navi-modal__field">
                <label>Description</label>
                <textarea
                  placeholder="Describe when and how this rule should be applied..."
                  value={newRule.description}
                  onChange={(e) => setNewRule(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                />
              </div>

              <div className="navi-modal__row">
                <div className="navi-modal__field">
                  <label>Rule Type</label>
                  <select
                    value={newRule.type}
                    onChange={(e) => setNewRule(prev => ({ ...prev, type: e.target.value as OrganizationRule['type'] }))}
                  >
                    <option value="coding_standard">Coding Standard</option>
                    <option value="naming_convention">Naming Convention</option>
                    <option value="security">Security</option>
                    <option value="testing">Testing</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>

                <div className="navi-modal__field">
                  <label>Priority</label>
                  <select
                    value={newRule.priority}
                    onChange={(e) => setNewRule(prev => ({ ...prev, priority: e.target.value as OrganizationRule['priority'] }))}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="navi-modal__footer">
              <button className="navi-modal__btn navi-modal__btn--secondary" onClick={() => setShowAddRuleModal(false)}>
                Cancel
              </button>
              <button
                className="navi-modal__btn navi-modal__btn--primary"
                onClick={handleAddRule}
                disabled={!newRule.name || addingRule}
              >
                {addingRule ? (
                  <>
                    <div className="navi-modal__spinner" />
                    Adding...
                  </>
                ) : (
                  'Add Rule'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        /* ============================================
           NAVI SIDEBAR - Premium Design System
           ============================================ */

        .navi-sidebar {
          display: flex;
          flex-direction: column;
          height: 100%;
          padding: 16px;
          gap: 16px;
          background: linear-gradient(
            180deg,
            hsl(var(--background)) 0%,
            hsl(var(--card) / 0.5) 100%
          );
          overflow-y: auto;
          overflow-x: hidden;
        }

        .navi-sidebar::-webkit-scrollbar {
          width: 4px;
        }

        .navi-sidebar::-webkit-scrollbar-track {
          background: transparent;
        }

        .navi-sidebar::-webkit-scrollbar-thumb {
          background: hsl(var(--primary) / 0.3);
          border-radius: 2px;
        }

        /* Modern Header */
        .navi-sidebar__header-modern {
          position: relative;
          padding: 16px;
          border-radius: 12px;
          background: linear-gradient(135deg, hsl(var(--primary) / 0.08), hsl(var(--accent) / 0.05));
          border: 1px solid hsl(var(--primary) / 0.15);
          overflow: hidden;
        }

        .navi-sidebar__header-glow {
          position: absolute;
          top: -50%;
          left: -50%;
          width: 200%;
          height: 200%;
          background: radial-gradient(circle at 30% 30%, hsl(var(--primary) / 0.1), transparent 50%);
          animation: headerGlow 8s ease-in-out infinite;
          pointer-events: none;
        }

        @keyframes headerGlow {
          0%, 100% { transform: translate(0, 0); }
          50% { transform: translate(10%, 10%); }
        }

        .navi-sidebar__header-content {
          position: relative;
          display: flex;
          align-items: center;
          gap: 12px;
          z-index: 1;
        }

        .navi-sidebar__header-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: linear-gradient(135deg, hsl(var(--primary) / 0.2), hsl(var(--accent) / 0.15));
          border: 1px solid hsl(var(--primary) / 0.2);
        }

        .navi-sidebar__header-icon svg {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-sidebar__header-content:hover .navi-sidebar__header-icon svg {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.25));
        }

        .navi-sidebar__header-text {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .navi-sidebar__header-title {
          font-size: 15px;
          font-weight: 700;
          color: hsl(var(--foreground));
          letter-spacing: -0.02em;
        }

        .navi-sidebar__header-sub {
          font-size: 11px;
          color: hsl(var(--primary));
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .navi-sidebar__header-expand {
          margin-left: auto;
          padding: 8px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border) / 0.3);
          border-radius: 8px;
          color: hsl(var(--muted-foreground));
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .navi-sidebar__header-expand svg {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-sidebar__header-expand:hover {
          background: hsl(var(--primary) / 0.15);
          border-color: hsl(var(--primary) / 0.3);
          color: hsl(var(--primary));
          transform: scale(1.05);
          box-shadow: 0 0 20px hsl(var(--primary) / 0.2);
        }

        .navi-sidebar__header-expand:hover svg {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .navi-sidebar__header-expand:active {
          transform: scale(0.95);
        }

        /* Spacer */
        .navi-sidebar__spacer {
          flex: 1;
        }

        /* Minimal Footer */
        .navi-sidebar__footer-minimal {
          display: flex;
          justify-content: center;
          padding: 8px 0;
        }

        .navi-sidebar__version-badge {
          font-size: 10px;
          font-weight: 600;
          color: hsl(var(--muted-foreground));
          background: hsl(var(--secondary) / 0.5);
          padding: 4px 10px;
          border-radius: 12px;
          letter-spacing: 0.03em;
        }

        /* Menu Container */
        .navi-sidebar__menu {
          display: flex;
          flex-direction: column;
          gap: 8px;
          flex: 1;
        }

        /* ============================================
           MENU ITEM - Advanced Card Design
           ============================================ */

        .navi-menu-item {
          position: relative;
          display: flex;
          align-items: center;
          gap: 14px;
          width: 100%;
          padding: 14px 16px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border) / 0.5);
          border-radius: 14px;
          color: hsl(var(--foreground));
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
          text-align: left;
        }

        .navi-menu-item::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: linear-gradient(
            135deg,
            hsl(var(--primary) / 0) 0%,
            hsl(var(--primary) / 0.05) 100%
          );
          opacity: 0;
          transition: opacity 0.3s ease;
        }

        .navi-menu-item:hover {
          border-color: hsl(var(--primary) / 0.4);
          transform: translateY(-2px);
          box-shadow:
            0 8px 30px hsl(var(--primary) / 0.15),
            0 0 0 1px hsl(var(--primary) / 0.1);
        }

        .navi-menu-item:hover::before {
          opacity: 1;
        }

        .navi-menu-item:active {
          transform: translateY(0);
        }

        /* Icon Container with Glow Effect */
        .navi-menu-item__icon-container {
          position: relative;
          width: 44px;
          height: 44px;
          flex-shrink: 0;
        }

        .navi-menu-item__icon-bg {
          position: absolute;
          inset: 0;
          background: hsl(var(--secondary) / 0.5);
          border-radius: 12px;
          transition: all 0.3s ease;
        }

        .navi-menu-item:hover .navi-menu-item__icon-bg {
          background: hsl(var(--secondary) / 0.8);
          transform: scale(1.05);
        }

        .navi-menu-item__icon {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1;
        }

        .navi-menu-item__icon .sidebar-icon {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-menu-item:hover .navi-menu-item__icon .sidebar-icon {
          transform: translateY(-1px) scale(1.1);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.22));
        }

        .navi-menu-item__icon-glow {
          position: absolute;
          inset: -4px;
          background: radial-gradient(
            circle at center,
            hsl(var(--primary) / 0.3) 0%,
            transparent 70%
          );
          opacity: 0;
          filter: blur(8px);
          transition: opacity 0.3s ease;
          z-index: 0;
        }

        .navi-menu-item:hover .navi-menu-item__icon-glow {
          opacity: 1;
        }

        /* Content */
        .navi-menu-item__content {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .navi-menu-item__header {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .navi-menu-item__label {
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .navi-menu-item__description {
          font-size: 11px;
          color: hsl(var(--muted-foreground));
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        /* Badge */
        .navi-menu-item__badge {
          padding: 2px 8px;
          font-size: 10px;
          font-weight: 700;
          border-radius: 20px;
          letter-spacing: 0.02em;
        }

        .navi-menu-item__badge--primary {
          background: hsl(var(--primary) / 0.15);
          color: hsl(var(--primary));
          border: 1px solid hsl(var(--primary) / 0.3);
        }

        .navi-menu-item__badge--success {
          background: hsl(142 76% 36% / 0.15);
          color: hsl(142 76% 46%);
          border: 1px solid hsl(142 76% 36% / 0.3);
        }

        .navi-menu-item__badge--accent {
          background: linear-gradient(135deg, hsl(var(--accent) / 0.2), hsl(var(--primary) / 0.2));
          color: hsl(var(--accent));
          border: 1px solid hsl(var(--accent) / 0.3);
          animation: badge-pulse 2s ease-in-out infinite;
        }

        @keyframes badge-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }

        /* Status Indicator */
        .navi-menu-item__status {
          width: 8px;
          height: 8px;
          background: hsl(142 76% 46%);
          border-radius: 50%;
          box-shadow: 0 0 8px hsl(142 76% 46% / 0.6);
          animation: status-pulse 2s ease-in-out infinite;
        }

        @keyframes status-pulse {
          0%, 100% {
            transform: scale(1);
            box-shadow: 0 0 8px hsl(142 76% 46% / 0.6);
          }
          50% {
            transform: scale(1.1);
            box-shadow: 0 0 12px hsl(142 76% 46% / 0.8);
          }
        }

        /* Arrow */
        .navi-menu-item__arrow {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border-radius: 8px;
          background: hsl(var(--secondary) / 0.3);
          color: hsl(var(--muted-foreground));
          transition: all 0.3s ease;
          flex-shrink: 0;
        }

        .navi-menu-item:hover .navi-menu-item__arrow {
          background: hsl(var(--primary) / 0.15);
          color: hsl(var(--primary));
          transform: translateX(4px);
        }

        .navi-menu-item__arrow .arrow-icon {
          transition: transform 0.3s ease;
        }

        .navi-menu-item:hover .navi-menu-item__arrow .arrow-icon {
          transform: translateX(2px);
        }

        /* ============================================
           STATS SECTION
           ============================================ */

        .navi-sidebar__stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          padding: 12px;
          background: hsl(var(--card) / 0.5);
          border: 1px solid hsl(var(--border) / 0.3);
          border-radius: 12px;
        }

        .navi-sidebar__stat {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          padding: 8px 4px;
        }

        .navi-sidebar__stat-value {
          font-size: 20px;
          font-weight: 700;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .navi-sidebar__stat-label {
          font-size: 10px;
          color: hsl(var(--muted-foreground));
          text-align: center;
        }

        /* ============================================
           FOOTER
           ============================================ */

        .navi-sidebar__footer {
          padding: 8px 4px;
          border-top: 1px solid hsl(var(--border) / 0.3);
        }

        .navi-sidebar__version {
          font-size: 10px;
          color: hsl(var(--muted-foreground) / 0.7);
          text-align: center;
          letter-spacing: 0.05em;
        }

        /* ============================================
           OVERLAY PANELS - Enhanced
           ============================================ */

        .navi-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: hsl(var(--background) / 0.8);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          animation: overlay-fade-in 0.2s ease;
        }

        @keyframes overlay-fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .navi-overlay-panel {
          width: 90%;
          max-width: 560px;
          max-height: 85vh;
          background: linear-gradient(
            180deg,
            hsl(var(--card)) 0%,
            hsl(var(--background)) 100%
          );
          border: 1px solid hsl(var(--border) / 0.5);
          border-radius: 20px;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: panel-slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow:
            0 25px 50px -12px hsl(var(--background) / 0.8),
            0 0 0 1px hsl(var(--primary) / 0.1),
            0 0 100px hsl(var(--primary) / 0.1);
        }

        .navi-overlay-panel--large {
          max-width: 700px;
        }

        @keyframes panel-slide-up {
          from {
            opacity: 0;
            transform: translateY(20px) scale(0.98);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        .navi-overlay-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px 24px;
          border-bottom: 1px solid hsl(var(--border) / 0.3);
          background: hsl(var(--card) / 0.5);
        }

        .navi-overlay-header__title {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .navi-overlay-header__title h3 {
          margin: 0;
          font-size: 18px;
          font-weight: 700;
          color: hsl(var(--foreground));
        }

        .navi-overlay-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border) / 0.3);
          border-radius: 10px;
          color: hsl(var(--muted-foreground));
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-overlay-close:hover {
          background: hsl(var(--destructive) / 0.1);
          border-color: hsl(var(--destructive) / 0.3);
          color: hsl(var(--destructive));
        }

        .navi-overlay-content {
          flex: 1;
          overflow-y: auto;
          padding: 24px;
        }

        /* ============================================
           RULES PANEL STYLES
           ============================================ */

        .navi-rules-section {
          margin-bottom: 28px;
        }

        .navi-rules-section:last-child {
          margin-bottom: 0;
        }

        .navi-rules-section__title {
          margin: 0 0 6px;
          font-size: 15px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-rules-section__description {
          margin: 0 0 16px;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
          line-height: 1.5;
        }

        .navi-rules-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          padding: 32px 24px;
          background: hsl(var(--secondary) / 0.2);
          border: 1px dashed hsl(var(--border));
          border-radius: 12px;
          text-align: center;
        }

        .navi-rules-empty__icon {
          font-size: 32px;
          opacity: 0.6;
        }

        .navi-rules-empty p {
          margin: 0;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-btn {
          padding: 10px 20px;
          font-size: 13px;
          font-weight: 600;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-btn--primary {
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border: none;
          color: white;
        }

        .navi-btn--primary:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 20px hsl(var(--primary) / 0.4);
        }

        .navi-btn--secondary {
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          color: hsl(var(--foreground));
        }

        .navi-btn--secondary:hover {
          background: hsl(var(--secondary));
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-rules-options {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .navi-rules-option {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 14px 16px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border) / 0.5);
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-rules-option:hover {
          background: hsl(var(--secondary) / 0.3);
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-rules-option input {
          display: none;
        }

        .navi-rules-option__checkmark {
          width: 20px;
          height: 20px;
          border: 2px solid hsl(var(--border));
          border-radius: 6px;
          transition: all 0.2s ease;
          position: relative;
          flex-shrink: 0;
          margin-top: 2px;
        }

        .navi-rules-option input:checked + .navi-rules-option__checkmark {
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border-color: transparent;
        }

        .navi-rules-option input:checked + .navi-rules-option__checkmark::after {
          content: '';
          position: absolute;
          top: 3px;
          left: 6px;
          width: 5px;
          height: 9px;
          border: solid white;
          border-width: 0 2px 2px 0;
          transform: rotate(45deg);
        }

        .navi-rules-option__content {
          flex: 1;
        }

        .navi-rules-option__label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: hsl(var(--foreground));
          margin-bottom: 2px;
        }

        .navi-rules-option__hint {
          display: block;
          font-size: 11px;
          color: hsl(var(--muted-foreground));
        }

        /* ============================================
           RULES SECTION ENHANCEMENTS
           ============================================ */

        .navi-rules-section__header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 16px;
        }

        .navi-rules-section__add {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          background: hsl(var(--primary) / 0.1);
          border: 1px solid hsl(var(--primary) / 0.3);
          border-radius: 8px;
          font-size: 12px;
          font-weight: 600;
          color: hsl(var(--primary));
          cursor: pointer;
          transition: all 0.2s ease;
          white-space: nowrap;
        }

        .navi-rules-section__add:hover {
          background: hsl(var(--primary) / 0.15);
          border-color: hsl(var(--primary) / 0.5);
        }

        .navi-rules-empty__hint {
          font-size: 12px;
          color: hsl(var(--muted-foreground) / 0.7);
          margin-bottom: 4px;
        }

        .navi-rules-empty .navi-btn {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        /* ============================================
           RULES LIST & CARDS
           ============================================ */

        .navi-rules-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .navi-rule-card {
          padding: 14px 16px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border) / 0.4);
          border-radius: 12px;
          transition: all 0.2s ease;
        }

        .navi-rule-card:hover {
          border-color: hsl(var(--primary) / 0.3);
          box-shadow: 0 4px 20px hsl(var(--primary) / 0.08);
        }

        .navi-rule-card--disabled {
          opacity: 0.5;
        }

        .navi-rule-card__header {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .navi-rule-card__icon {
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: hsl(var(--secondary) / 0.5);
          border-radius: 8px;
          color: hsl(var(--primary));
        }

        .navi-rule-card__info {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }

        .navi-rule-card__name {
          font-size: 13px;
          font-weight: 600;
          color: hsl(var(--foreground));
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .navi-rule-card__priority {
          padding: 2px 8px;
          border-radius: 10px;
          font-size: 9px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        .navi-rule-card__priority--low {
          background: hsl(var(--muted-foreground) / 0.15);
          color: hsl(var(--muted-foreground));
        }

        .navi-rule-card__priority--medium {
          background: hsl(45 93% 47% / 0.15);
          color: hsl(45 93% 47%);
        }

        .navi-rule-card__priority--high {
          background: hsl(var(--destructive) / 0.15);
          color: hsl(var(--destructive));
        }

        .navi-rule-card__actions {
          display: flex;
          gap: 6px;
        }

        .navi-rule-card__btn {
          padding: 6px;
          background: hsl(var(--secondary) / 0.4);
          border: 1px solid hsl(var(--border) / 0.3);
          border-radius: 6px;
          color: hsl(var(--muted-foreground));
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .navi-rule-card__btn:hover {
          background: hsl(var(--secondary) / 0.8);
          color: hsl(var(--foreground));
        }

        .navi-rule-card__btn--danger:hover {
          background: hsl(var(--destructive) / 0.15);
          border-color: hsl(var(--destructive) / 0.3);
          color: hsl(var(--destructive));
        }

        .navi-rule-card__description {
          margin: 10px 0 0;
          padding-left: 44px;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
          line-height: 1.4;
        }

        .navi-rule-card__type {
          margin-top: 8px;
          padding-left: 44px;
          font-size: 10px;
          color: hsl(var(--muted-foreground) / 0.7);
        }

        /* ============================================
           TIPS SECTION
           ============================================ */

        .navi-rules-tips {
          display: flex;
          gap: 14px;
          padding: 16px;
          background: hsl(var(--primary) / 0.05);
          border: 1px solid hsl(var(--primary) / 0.15);
          border-radius: 12px;
        }

        .navi-rules-tips__icon {
          flex-shrink: 0;
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: hsl(var(--primary) / 0.1);
          border-radius: 10px;
          color: hsl(var(--primary));
        }

        .navi-rules-tips__content h5 {
          margin: 0 0 8px;
          font-size: 13px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-rules-tips__content ul {
          margin: 0;
          padding-left: 16px;
        }

        .navi-rules-tips__content li {
          font-size: 11px;
          color: hsl(var(--muted-foreground));
          margin-bottom: 4px;
          line-height: 1.4;
        }

        .navi-rules-tips__content li:last-child {
          margin-bottom: 0;
        }

        /* ============================================
           MODAL STYLES
           ============================================ */

        .navi-modal-overlay {
          position: fixed;
          inset: 0;
          background: hsl(0 0% 0% / 0.7);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1100;
          animation: overlay-fade-in 0.15s ease;
        }

        .navi-modal {
          width: 90%;
          max-width: 480px;
          background: linear-gradient(
            165deg,
            hsl(var(--card)) 0%,
            hsl(var(--background)) 100%
          );
          border: 1px solid hsl(var(--border) / 0.5);
          border-radius: 20px;
          overflow: hidden;
          animation: panel-slide-up 0.25s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow:
            0 0 0 1px hsl(var(--primary) / 0.1),
            0 25px 80px -12px hsl(0 0% 0% / 0.6);
        }

        .navi-modal__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 18px 22px;
          background: hsl(var(--card) / 0.5);
          border-bottom: 1px solid hsl(var(--border) / 0.3);
        }

        .navi-modal__header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 700;
          color: hsl(var(--foreground));
        }

        .navi-modal__close {
          padding: 8px;
          background: hsl(var(--secondary) / 0.4);
          border: 1px solid hsl(var(--border) / 0.3);
          border-radius: 8px;
          color: hsl(var(--muted-foreground));
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .navi-modal__close:hover {
          background: hsl(var(--destructive) / 0.15);
          border-color: hsl(var(--destructive) / 0.3);
          color: hsl(var(--destructive));
        }

        .navi-modal__content {
          padding: 22px;
        }

        .navi-modal__description {
          margin: 0 0 20px;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
          line-height: 1.5;
        }

        .navi-modal__field {
          margin-bottom: 16px;
        }

        .navi-modal__field:last-of-type {
          margin-bottom: 0;
        }

        .navi-modal__field label {
          display: block;
          margin-bottom: 6px;
          font-size: 12px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-modal__field input,
        .navi-modal__field select,
        .navi-modal__field textarea {
          width: 100%;
          padding: 11px 14px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border) / 0.4);
          border-radius: 10px;
          font-size: 13px;
          font-family: inherit;
          color: hsl(var(--foreground));
          outline: none;
          transition: all 0.2s ease;
          resize: vertical;
        }

        .navi-modal__field input:focus,
        .navi-modal__field select:focus,
        .navi-modal__field textarea:focus {
          background: hsl(var(--secondary) / 0.5);
          border-color: hsl(var(--primary) / 0.5);
          box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
        }

        .navi-modal__field input::placeholder,
        .navi-modal__field textarea::placeholder {
          color: hsl(var(--muted-foreground) / 0.7);
        }

        .navi-modal__field select {
          cursor: pointer;
        }

        .navi-modal__row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .navi-modal__footer {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          padding: 16px 22px;
          background: hsl(var(--card) / 0.3);
          border-top: 1px solid hsl(var(--border) / 0.3);
        }

        .navi-modal__btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 11px 20px;
          font-size: 13px;
          font-weight: 600;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-modal__btn--secondary {
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border) / 0.5);
          color: hsl(var(--muted-foreground));
        }

        .navi-modal__btn--secondary:hover {
          background: hsl(var(--secondary));
          color: hsl(var(--foreground));
        }

        .navi-modal__btn--primary {
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border: none;
          color: white;
        }

        .navi-modal__btn--primary:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 20px hsl(var(--primary) / 0.4);
        }

        .navi-modal__btn--primary:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .navi-modal__spinner {
          width: 14px;
          height: 14px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: status-pulse 0.8s linear infinite;
        }

        @keyframes status-pulse {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default SidebarPanel;
