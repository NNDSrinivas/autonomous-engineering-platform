import React, { useState } from 'react';
import { useUIState } from '../../state/uiStore';

/**
 * HeaderBar - Clean Copilot-style header
 * 
 * Phase 4.0 UI Parity:
 * - Single compact header (no duplicate)
 * - Status-only display
 * - No mode toggle (moved to composer)
 * - Minimal, professional look
 */
interface HeaderBarProps {
  onOpenConnectors?: () => void;
}

export function HeaderBar({ onOpenConnectors }: HeaderBarProps) {
  const { state } = useUIState();
  const agentStatus = state.workflow?.agentStatus ?? "idle";
  const [menuOpen, setMenuOpen] = useState(false);
  
  const getStatusColor = () => {
    switch (agentStatus) {
      case 'idle': return 'bg-blue-500';
      case 'running': return 'bg-yellow-500'; 
      case 'awaiting_approval': return 'bg-orange-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-blue-500';
    }
  };

  const getStatusText = () => {
    switch (agentStatus) {
      case 'idle': return 'Idle';
      case 'running': return 'Thinking';
      case 'awaiting_approval': return 'Awaiting Approval';
      case 'error': return 'Error';
      default: return 'Idle';
    }
  };

  const shouldPulse = agentStatus === 'running';

  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--vscode-panel-border)] bg-[var(--vscode-sideBar-background)]">
      {/* Left: NAVI logo + status */}
      <div className="flex items-center gap-2">
        <span className="font-semibold tracking-wide text-[var(--vscode-foreground)]">NAVI</span>
        
        {/* Refined status dot with pulse */}
        <div className="relative flex h-2 w-2">
          {shouldPulse && (
            <span className={`absolute inline-flex h-full w-full rounded-full ${getStatusColor()} opacity-75 animate-pulse-ring`} />
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${getStatusColor()}`} />
        </div>
        
        <span className="text-xs opacity-70 text-[var(--vscode-descriptionForeground)]">
          {getStatusText()}
        </span>
      </div>

      {/* Right: New Chat, History, Settings + overflow with hover states */}
      <div className="relative flex items-center gap-1">
        {/* New Chat Button */}
        <button 
          onClick={() => {
            // New Chat - for now just log (no dispatch until messaging works)
            console.log('🆕 New chat clicked - clearing messages');
            // TODO: Wire to actual message clearing once dispatch is working
          }}
          title="New Chat"
          className="p-1.5 rounded opacity-70 hover:opacity-100 hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-all duration-150 text-[var(--vscode-foreground)]"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </button>
        
        {/* History Button */}
        <button 
          onClick={() => {
            console.log('History button clicked - feature placeholder');
            // TODO: Implement history panel
          }}
          title="Chat History"
          className="p-1.5 rounded opacity-70 hover:opacity-100 hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-all duration-150 text-[var(--vscode-foreground)]"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
        
        {/* Settings Button */}
        <button 
          onClick={() => {
            setMenuOpen((prev) => !prev);
          }}
          title="Settings"
          className="p-1.5 rounded opacity-70 hover:opacity-100 hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-all duration-150 text-[var(--vscode-foreground)]"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
        
        {/* Ellipsis Menu Button */}
        <button 
          onClick={() => {
            console.log('Menu button clicked - feature placeholder');
            // TODO: Implement dropdown menu
          }}
          title="More Options"
          className="p-1.5 rounded opacity-70 hover:opacity-100 hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-all duration-150 text-[var(--vscode-foreground)]"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
          </svg>
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-9 z-50 w-44 rounded-lg border border-[var(--vscode-panel-border)] bg-[var(--vscode-editorWidget-background)] shadow-lg">
            <button
              onClick={() => {
                setMenuOpen(false);
                onOpenConnectors?.();
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-[var(--vscode-foreground)] hover:bg-[var(--vscode-list-hoverBackground)]"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 7v10M7 12h10" />
              </svg>
              Connectors
            </button>
            <button
              onClick={() => setMenuOpen(false)}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-[var(--vscode-descriptionForeground)] hover:bg-[var(--vscode-list-hoverBackground)]"
            >
              Preferences
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
