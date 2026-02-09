import React, { useState, useEffect, useCallback } from 'react';
import { resolveBackendBase, buildHeaders } from '../../api/navi/client';

interface UserProfile {
  email?: string;
  name?: string;
  picture?: string;
  org?: string;
  role?: string;
}

interface UserPreferences {
  theme: 'dark' | 'light' | 'system';
  responseVerbosity: 'brief' | 'balanced' | 'detailed';
  explanationLevel: 'beginner' | 'intermediate' | 'expert';
  preferredLanguage?: string;
  preferredFramework?: string;
  keyboardShortcuts: boolean;
  soundEffects: boolean;
  autoApprove: 'none' | 'safe' | 'all';
}

interface AccountPanelProps {
  isOpen: boolean;
  onClose: () => void;
  isAuthenticated: boolean;
  user?: UserProfile;
  onSignIn: () => void;
  onSignOut: () => void;
  onOpenEnterpriseProjects?: () => void;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'dark',
  responseVerbosity: 'balanced',
  explanationLevel: 'intermediate',
  keyboardShortcuts: true,
  soundEffects: false,
  autoApprove: 'none',
};

// SVG Icons
const UserIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 6L6 18M6 6l12 12" />
  </svg>
);

const LockIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

const LogOutIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const ChartIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const DownloadIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const BuildingIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
    <path d="M9 22v-4h6v4" />
    <line x1="8" y1="6" x2="8" y2="6.01" />
    <line x1="16" y1="6" x2="16" y2="6.01" />
    <line x1="12" y1="6" x2="12" y2="6.01" />
    <line x1="8" y1="10" x2="8" y2="10.01" />
    <line x1="16" y1="10" x2="16" y2="10.01" />
    <line x1="12" y1="10" x2="12" y2="10.01" />
    <line x1="8" y1="14" x2="8" y2="14.01" />
    <line x1="16" y1="14" x2="16" y2="14.01" />
    <line x1="12" y1="14" x2="12" y2="14.01" />
  </svg>
);

const KeyboardIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="4" width="20" height="16" rx="2" ry="2" />
    <line x1="6" y1="8" x2="6" y2="8" />
    <line x1="10" y1="8" x2="10" y2="8" />
    <line x1="14" y1="8" x2="14" y2="8" />
    <line x1="18" y1="8" x2="18" y2="8" />
    <line x1="6" y1="12" x2="6" y2="12" />
    <line x1="18" y1="12" x2="18" y2="12" />
    <line x1="8" y1="16" x2="16" y2="16" />
  </svg>
);

const RocketIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
    <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
  </svg>
);

const ExternalLinkIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </svg>
);

export const AccountPanel: React.FC<AccountPanelProps> = ({
  isOpen,
  onClose,
  isAuthenticated,
  user,
  onSignIn,
  onSignOut,
  onOpenEnterpriseProjects,
}) => {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'preferences' | 'shortcuts'>('profile');

  // Fetch user preferences from backend
  const fetchPreferences = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const response = await fetch(`${resolveBackendBase()}/api/memory/preferences`, {
        headers: buildHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setPreferences(prev => ({ ...prev, ...data }));
      }
    } catch {
      console.log('Preferences API not available, using defaults');
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  const handlePreferenceChange = async (key: keyof UserPreferences, value: unknown) => {
    const newPrefs = { ...preferences, [key]: value };
    setPreferences(newPrefs);

    // Save to backend
    setSaving(true);
    try {
      await fetch(`${resolveBackendBase()}/api/memory/preferences`, {
        method: 'PUT',
        headers: buildHeaders(),
        body: JSON.stringify(newPrefs),
      });
    } catch {
      console.log('Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const getInitials = (name?: string, email?: string): string => {
    if (name) {
      const parts = name.split(' ');
      return parts.map(p => p[0]).join('').toUpperCase().slice(0, 2);
    }
    if (email) {
      return email[0].toUpperCase();
    }
    return '?';
  };

  if (!isOpen) return null;

  return (
    <div className="navi-overlay" onClick={onClose}>
      <div className="navi-overlay-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="navi-overlay-header">
          <h3>
            <UserIcon />
            Account
          </h3>
          <button className="navi-overlay-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        {/* Content */}
        <div className="navi-overlay-content">
          {!isAuthenticated ? (
            <div className="account-signin">
              <div className="account-signin-icon">
                <LockIcon />
              </div>
              <h4>Sign in to NAVI</h4>
              <p>Access your personalized settings, conversation history, and team features.</p>
              <button className="account-signin-btn" onClick={onSignIn}>
                Sign In
              </button>
            </div>
          ) : (
            <>
              {/* User Profile Card */}
              <div className="account-profile">
                {user?.picture ? (
                  <img
                    src={user.picture}
                    alt={user.name || 'User'}
                    className="account-profile-avatar"
                  />
                ) : (
                  <div className="account-profile-avatar-placeholder">
                    {getInitials(user?.name, user?.email)}
                  </div>
                )}
                <div className="account-profile-info">
                  <span className="account-profile-name">{user?.name || 'User'}</span>
                  <span className="account-profile-email">{user?.email}</span>
                  {user?.org && (
                    <span className="account-profile-org">
                      <BuildingIcon />
                      {user.org}
                      {user.role && <span className="account-profile-role"> • {user.role}</span>}
                    </span>
                  )}
                </div>
              </div>

              {/* Tab Navigation */}
              <div className="account-tabs">
                <button
                  className={`account-tab ${activeTab === 'profile' ? 'active' : ''}`}
                  onClick={() => setActiveTab('profile')}
                >
                  Profile
                </button>
                <button
                  className={`account-tab ${activeTab === 'preferences' ? 'active' : ''}`}
                  onClick={() => setActiveTab('preferences')}
                >
                  Preferences
                </button>
                <button
                  className={`account-tab ${activeTab === 'shortcuts' ? 'active' : ''}`}
                  onClick={() => setActiveTab('shortcuts')}
                >
                  <KeyboardIcon />
                  Shortcuts
                </button>
              </div>

              {/* Tab Content */}
              <div className="account-tab-content">
                {activeTab === 'profile' && (
                  <div className="profile-tab">
                    <div className="profile-stats">
                      <div className="stat-card">
                        <span className="stat-value">42</span>
                        <span className="stat-label">Conversations</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-value">156</span>
                        <span className="stat-label">Commands</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-value">89%</span>
                        <span className="stat-label">Success Rate</span>
                      </div>
                    </div>

                    {/* Enterprise Projects Button */}
                    {onOpenEnterpriseProjects && (
                      <div className="enterprise-projects-section">
                        <button
                          className="enterprise-projects-btn"
                          onClick={onOpenEnterpriseProjects}
                        >
                          <RocketIcon />
                          <span className="enterprise-btn-text">
                            <span className="enterprise-btn-title">Enterprise Projects</span>
                            <span className="enterprise-btn-subtitle">Manage long-running projects</span>
                          </span>
                          <ExternalLinkIcon />
                        </button>
                      </div>
                    )}

                    <div className="profile-actions">
                      <button className="profile-action-btn">
                        <ChartIcon />
                        View Activity
                      </button>
                      <button className="profile-action-btn">
                        <DownloadIcon />
                        Export Data
                      </button>
                    </div>
                  </div>
                )}

                {activeTab === 'preferences' && (
                  <div className="preferences-tab">
                    {saving && <div className="saving-indicator">Saving...</div>}

                    <div className="preference-group">
                      <label className="preference-label">Response Style</label>
                      <div className="preference-options">
                        {(['brief', 'balanced', 'detailed'] as const).map(option => (
                          <button
                            key={option}
                            className={`preference-option ${preferences.responseVerbosity === option ? 'active' : ''}`}
                            onClick={() => handlePreferenceChange('responseVerbosity', option)}
                          >
                            {option.charAt(0).toUpperCase() + option.slice(1)}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="preference-group">
                      <label className="preference-label">Explanation Level</label>
                      <div className="preference-options">
                        {(['beginner', 'intermediate', 'expert'] as const).map(option => (
                          <button
                            key={option}
                            className={`preference-option ${preferences.explanationLevel === option ? 'active' : ''}`}
                            onClick={() => handlePreferenceChange('explanationLevel', option)}
                          >
                            {option.charAt(0).toUpperCase() + option.slice(1)}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="preference-group">
                      <label className="preference-label">Auto-Approve Actions</label>
                      <div className="preference-options">
                        {(['none', 'safe', 'all'] as const).map(option => (
                          <button
                            key={option}
                            className={`preference-option ${preferences.autoApprove === option ? 'active' : ''}`}
                            onClick={() => handlePreferenceChange('autoApprove', option)}
                          >
                            {option === 'none' ? 'Never' : option === 'safe' ? 'Safe Only' : 'All'}
                          </button>
                        ))}
                      </div>
                      <span className="preference-hint">
                        {preferences.autoApprove === 'none' && 'Require approval for all actions'}
                        {preferences.autoApprove === 'safe' && 'Auto-approve read-only operations'}
                        {preferences.autoApprove === 'all' && 'Auto-approve all actions (use with caution)'}
                      </span>
                    </div>

                    <div className="preference-group">
                      <label className="preference-toggle">
                        <span>Keyboard Shortcuts</span>
                        <input
                          type="checkbox"
                          checked={preferences.keyboardShortcuts}
                          onChange={e => handlePreferenceChange('keyboardShortcuts', e.target.checked)}
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>

                    <div className="preference-group">
                      <label className="preference-toggle">
                        <span>Sound Effects</span>
                        <input
                          type="checkbox"
                          checked={preferences.soundEffects}
                          onChange={e => handlePreferenceChange('soundEffects', e.target.checked)}
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                )}

                {activeTab === 'shortcuts' && (
                  <div className="shortcuts-tab">
                    <div className="shortcut-list">
                      <div className="shortcut-item">
                        <span className="shortcut-keys">
                          <kbd>⌘</kbd><kbd>K</kbd>
                        </span>
                        <span className="shortcut-action">Quick Command</span>
                      </div>
                      <div className="shortcut-item">
                        <span className="shortcut-keys">
                          <kbd>⌘</kbd><kbd>Enter</kbd>
                        </span>
                        <span className="shortcut-action">Send Message</span>
                      </div>
                      <div className="shortcut-item">
                        <span className="shortcut-keys">
                          <kbd>⌘</kbd><kbd>L</kbd>
                        </span>
                        <span className="shortcut-action">Clear Chat</span>
                      </div>
                      <div className="shortcut-item">
                        <span className="shortcut-keys">
                          <kbd>⌘</kbd><kbd>Shift</kbd><kbd>N</kbd>
                        </span>
                        <span className="shortcut-action">New Chat</span>
                      </div>
                      <div className="shortcut-item">
                        <span className="shortcut-keys">
                          <kbd>Esc</kbd>
                        </span>
                        <span className="shortcut-action">Cancel Action</span>
                      </div>
                      <div className="shortcut-item">
                        <span className="shortcut-keys">
                          <kbd>⌘</kbd><kbd>.</kbd>
                        </span>
                        <span className="shortcut-action">Toggle Sidebar</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Sign Out Button */}
              <div className="account-signout">
                <button className="account-signout-btn" onClick={onSignOut}>
                  <LogOutIcon />
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <style>{`
        .navi-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.6);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          animation: navi-fade-in 0.2s ease;
        }

        @keyframes navi-fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .navi-overlay-panel {
          width: 90%;
          max-width: 500px;
          max-height: 80vh;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 16px;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: navi-slide-up 0.3s ease;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }

        @keyframes navi-slide-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .navi-overlay-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 20px;
          border-bottom: 1px solid hsl(var(--border));
          background: hsl(var(--secondary) / 0.2);
        }

        .navi-overlay-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
          color: hsl(var(--foreground));
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .navi-overlay-header h3 svg {
          color: hsl(var(--primary));
        }

        .navi-overlay-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
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
          padding: 20px;
        }

        /* Sign In State */
        .account-signin {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 40px 20px;
        }

        .account-signin-icon {
          width: 64px;
          height: 64px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border-radius: 16px;
          margin-bottom: 20px;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .account-signin-icon svg {
          color: white;
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .account-signin-icon:hover {
          transform: translateY(-1px) scale(1.02);
          box-shadow: 0 10px 26px hsl(var(--primary) / 0.35);
        }

        .account-signin-icon:hover svg {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.25));
        }

        .account-signin h4 {
          margin: 0 0 8px;
          font-size: 18px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .account-signin p {
          margin: 0 0 24px;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
          line-height: 1.5;
        }

        .account-signin-btn {
          padding: 12px 32px;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border: none;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 600;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .account-signin-btn:hover {
          box-shadow: 0 8px 24px hsl(var(--primary) / 0.4);
          transform: translateY(-2px);
        }

        /* Profile Section */
        .account-profile {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 16px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          margin-bottom: 20px;
        }

        .account-profile-avatar {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          object-fit: cover;
          border: 2px solid hsl(var(--primary));
        }

        .account-profile-avatar-placeholder {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 20px;
          color: white;
        }

        .account-profile-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }

        .account-profile-name {
          font-size: 16px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .account-profile-email {
          font-size: 13px;
          color: hsl(var(--muted-foreground));
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .account-profile-org {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
        }

        .account-profile-org svg {
          color: hsl(var(--primary));
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .account-profile-org:hover svg {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .account-profile-role {
          color: hsl(var(--muted-foreground) / 0.7);
        }

        /* Tabs */
        .account-tabs {
          display: flex;
          gap: 4px;
          margin-bottom: 16px;
          padding: 4px;
          background: hsl(var(--secondary) / 0.3);
          border-radius: 10px;
        }

        .account-tab {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 10px 12px;
          background: none;
          border: none;
          border-radius: 8px;
          color: hsl(var(--muted-foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .account-tab:hover {
          color: hsl(var(--foreground));
          background: hsl(var(--secondary) / 0.5);
        }

        .account-tab.active {
          color: hsl(var(--foreground));
          background: hsl(var(--secondary) / 0.6);
          box-shadow: inset 0 0 0 1px hsl(var(--primary) / 0.08);
        }

        .account-tab svg {
          width: 14px;
          height: 14px;
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .account-tab:hover svg {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .account-tab-content {
          min-height: 200px;
        }

        /* Profile Tab */
        .profile-tab {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .profile-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
        }

        .stat-card {
          text-align: center;
          padding: 16px 12px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
        }

        .stat-value {
          display: block;
          font-size: 24px;
          font-weight: 700;
          color: hsl(var(--primary));
        }

        .stat-label {
          display: block;
          font-size: 11px;
          color: hsl(var(--muted-foreground));
          margin-top: 4px;
        }

        .profile-actions {
          display: flex;
          gap: 10px;
        }

        .profile-action-btn {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 12px 16px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          color: hsl(var(--foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .profile-action-btn:hover {
          background: hsl(var(--secondary) / 0.5);
          border-color: hsl(var(--primary) / 0.3);
        }

        .profile-action-btn svg {
          color: hsl(var(--primary));
        }

        /* Enterprise Projects Section */
        .enterprise-projects-section {
          margin-bottom: 16px;
        }

        .enterprise-projects-btn {
          display: flex;
          align-items: center;
          gap: 12px;
          width: 100%;
          padding: 14px 16px;
          background: linear-gradient(135deg, hsl(var(--primary) / 0.15), hsl(var(--accent) / 0.1));
          border: 1px solid hsl(var(--primary) / 0.3);
          border-radius: 12px;
          color: hsl(var(--foreground));
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .enterprise-projects-btn:hover {
          background: linear-gradient(135deg, hsl(var(--primary) / 0.25), hsl(var(--accent) / 0.15));
          border-color: hsl(var(--primary) / 0.5);
          transform: translateY(-1px);
          box-shadow: 0 4px 12px hsl(var(--primary) / 0.2);
        }

        .enterprise-projects-btn svg:first-child {
          color: hsl(var(--primary));
          flex-shrink: 0;
        }

        .enterprise-projects-btn svg:last-child {
          color: hsl(var(--muted-foreground));
          flex-shrink: 0;
          margin-left: auto;
        }

        .enterprise-btn-text {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 2px;
          flex: 1;
        }

        .enterprise-btn-title {
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .enterprise-btn-subtitle {
          font-size: 11px;
          color: hsl(var(--muted-foreground));
        }

        /* Preferences Tab */
        .preferences-tab {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .saving-indicator {
          font-size: 11px;
          color: hsl(var(--primary));
          text-align: right;
          margin-bottom: -8px;
        }

        .preference-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .preference-label {
          font-size: 12px;
          font-weight: 500;
          color: hsl(var(--foreground));
        }

        .preference-options {
          display: flex;
          gap: 6px;
        }

        .preference-option {
          flex: 1;
          padding: 10px 12px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
          color: hsl(var(--muted-foreground));
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .preference-option:hover {
          border-color: hsl(var(--primary) / 0.5);
          color: hsl(var(--foreground));
        }

        .preference-option.active {
          background: hsl(var(--primary) / 0.15);
          border-color: hsl(var(--primary));
          color: hsl(var(--primary));
        }

        .preference-hint {
          font-size: 11px;
          color: hsl(var(--muted-foreground));
          font-style: italic;
        }

        .preference-toggle {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 14px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          cursor: pointer;
        }

        .preference-toggle span:first-child {
          font-size: 13px;
          color: hsl(var(--foreground));
        }

        .preference-toggle input {
          display: none;
        }

        .toggle-slider {
          position: relative;
          width: 40px;
          height: 22px;
          background: hsl(var(--secondary));
          border-radius: 11px;
          transition: all 0.2s ease;
        }

        .toggle-slider::after {
          content: '';
          position: absolute;
          top: 3px;
          left: 3px;
          width: 16px;
          height: 16px;
          background: hsl(var(--muted-foreground));
          border-radius: 50%;
          transition: all 0.2s ease;
        }

        .preference-toggle input:checked + .toggle-slider {
          background: hsl(var(--primary) / 0.3);
        }

        .preference-toggle input:checked + .toggle-slider::after {
          left: 21px;
          background: hsl(var(--primary));
        }

        /* Shortcuts Tab */
        .shortcuts-tab {
          display: flex;
          flex-direction: column;
        }

        .shortcut-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .shortcut-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 14px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
        }

        .shortcut-keys {
          display: flex;
          gap: 4px;
        }

        .shortcut-keys kbd {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 28px;
          height: 28px;
          padding: 0 8px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 6px;
          font-size: 11px;
          font-family: inherit;
          color: hsl(var(--foreground));
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .shortcut-action {
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        /* Sign Out */
        .account-signout {
          margin-top: 20px;
          padding-top: 16px;
          border-top: 1px solid hsl(var(--border));
        }

        .account-signout-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          width: 100%;
          padding: 12px 16px;
          background: hsl(var(--destructive) / 0.1);
          border: 1px solid hsl(var(--destructive) / 0.2);
          border-radius: 10px;
          color: hsl(var(--destructive));
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .account-signout-btn:hover {
          background: hsl(var(--destructive) / 0.15);
          border-color: hsl(var(--destructive) / 0.4);
        }
      `}</style>
    </div>
  );
};

export default AccountPanel;
