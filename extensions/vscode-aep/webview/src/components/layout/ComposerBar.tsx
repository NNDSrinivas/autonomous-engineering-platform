import React, { useState } from 'react';
import { useUIState } from '../../state/uiStore';
import { postMessage } from '../../utils/vscodeApi';
import { ModeSelector, type Mode } from '../input/ModeSelector';
import { ModelSelector, type Model } from '../input/ModelSelector';

// PHASE 4.0.2 DESIGN TOKENS - NAVI Font System & Composer
const DESIGN_TOKENS = {
  composer: {
    bg: 'rgba(20, 20, 22, 0.65)',
    border: 'rgba(255, 255, 255, 0.06)',
    text: '#e6e7ea',
    placeholder: 'rgba(200, 205, 215, 0.55)',
    minHeight: '44px',
    maxHeight: '160px'
  },
  icons: {
    default: 'rgba(200, 205, 215, 0.6)',
    active: '#9cc3ff',
    hover: '#e6f0ff',
    disabled: 'rgba(200, 205, 215, 0.35)',
    glow: '0 0 4px rgba(120, 180, 255, 0.25)'
  },
  fonts: {
    ui: 'Inter, SF Pro Text, Segoe UI, system-ui, sans-serif',
    composerInput: '13.5px'
  }
};

// System-Grade Icons - Aerospace Specification
const AttachIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path
      d="M7.5 12.5L13.8 6.2C15.3 4.7 17.8 4.7 19.3 6.2C20.8 7.7 20.8 10.2 19.3 11.7L10.8 20.2C8.8 22.2 5.6 22.2 3.6 20.2C1.6 18.2 1.6 15 3.6 13L11.5 5.1"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M4 12H20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M14 6L20 12L14 18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ThinkingSpinner = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="animate-spin">
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="60 40" />
  </svg>
);

/**
 * ComposerBar - Copilot-style composer with mode and model selection
 * 
 * Phase 4.0.5 CRITICAL FIX:
 * - NO DISPATCH USAGE (causing ReferenceError)
 * - Simple local state only
 * - Direct postMessage to extension
 * - Compact Copilot-style dropdowns
 */
export function ComposerBar() {
  const { state, dispatch } = useUIState();
  const [message, setMessage] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [mode, setMode] = useState<Mode>('agent');
  const [model, setModel] = useState<Model>('auto');

  // Check if thinking (from UI state)
  const isThinking = state.isThinking;
  const isDisabled = isThinking;

  const getPlaceholder = () => {
    if (isThinking) return 'NAVI is thinking...';
    switch (mode) {
      case 'agent': return 'Ask NAVI to help with your code...';
      case 'plan': return 'Describe what you want to build...';
      case 'ask': return 'Ask a question about your code...';
      case 'edit': return 'Describe the change you want to make...';
      default: return 'Ask NAVI to help with your code...';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isDisabled) {
      // Add user message to UI immediately (optimistic)
      dispatch({ type: 'ADD_USER_MESSAGE', content: message.trim() });
      
      // CANONICAL PIPELINE: Always use extension backend
      postMessage({
        type: 'navi.user.message',
        content: message.trim(),
        mode,
        model
      });
      
      console.log('✅ User message sent:', { message: message.trim(), mode, model });
      setMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (e.shiftKey) {
        // Shift+Enter: Allow new line (default behavior)
        return;
      } else {
        // Enter: Send message
        e.preventDefault();
        handleSubmit(e);
      }
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    
    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    const newHeight = Math.min(Math.max(textarea.scrollHeight, 36), 120);
    textarea.style.height = `${newHeight}px`;
  };

  return (
    <div className="border-t border-[var(--vscode-panel-border)] bg-[var(--vscode-sideBar-background)]" data-composer-panel>
      {/* NAVI Command Surface - Frosted Command Capsule */}
      <div className="p-4">
        <form onSubmit={handleSubmit}>
          <div 
            className="navi-composer relative rounded-[14px] transition-all duration-150"
            style={{
              background: DESIGN_TOKENS.composer.bg,
              backdropFilter: 'blur(14px)',
              border: `1px solid ${DESIGN_TOKENS.composer.border}`,
              padding: '12px 12px 40px 12px',
              minHeight: DESIGN_TOKENS.composer.minHeight
            }}
          >
            <textarea
              value={message}
              onChange={(e) => {
                setMessage(e.target.value);
                // Auto-resize with proper limits
                const textarea = e.target as HTMLTextAreaElement;
                textarea.style.height = 'auto';
                textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 44), 160)}px`;
              }}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder={getPlaceholder()}
              disabled={isDisabled}
              rows={1}
              className="navi-input w-full bg-transparent border-none outline-none resize-none placeholder-composer-text"
              style={{
                minHeight: DESIGN_TOKENS.composer.minHeight,
                maxHeight: DESIGN_TOKENS.composer.maxHeight,
                color: DESIGN_TOKENS.composer.text,
                fontSize: DESIGN_TOKENS.fonts.composerInput,
                fontFamily: DESIGN_TOKENS.fonts.ui,
                lineHeight: '1.5'
              }}
            />
            
            {/* Bottom-Pinned Icon Rail */}
            <div 
              className="absolute bottom-0 left-0 right-0 flex justify-between items-center px-3 pb-3"
            >
              {/* Left: Attachment */}
              <button
                type="button"
                onClick={() => {
                  console.log('Context injection clicked');
                  // TODO: Open context picker
                }}
                title="Add context"
                className="navi-icon-btn transition-all duration-120"
                style={{
                  color: DESIGN_TOKENS.icons.default
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.icons.hover;
                  e.currentTarget.style.boxShadow = DESIGN_TOKENS.icons.glow;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.icons.default;
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <AttachIcon />
              </button>
              
              {/* Right: Send */}
              <button
                type="submit"
                disabled={!message.trim() || isDisabled}
                title="Execute"
                className="navi-icon-btn navi-send transition-all duration-120"
                style={{
                  color: message.trim() && !isDisabled 
                    ? DESIGN_TOKENS.icons.active 
                    : DESIGN_TOKENS.icons.disabled,
                  opacity: message.trim() && !isDisabled ? 1 : 0.35,
                  cursor: message.trim() && !isDisabled ? 'pointer' : 'default'
                }}
                onMouseEnter={(e) => {
                  if (message.trim() && !isDisabled) {
                    e.currentTarget.style.color = DESIGN_TOKENS.icons.hover;
                    e.currentTarget.style.boxShadow = DESIGN_TOKENS.icons.glow;
                  }
                }}
                onMouseLeave={(e) => {
                  if (message.trim() && !isDisabled) {
                    e.currentTarget.style.color = DESIGN_TOKENS.icons.active;
                    e.currentTarget.style.boxShadow = 'none';
                  }
                }}
              >
                {isThinking ? <ThinkingSpinner /> : <SendIcon />}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Footer - ONLY place for controls (Copilot parity) */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--vscode-panel-border)] bg-[var(--vscode-editor-background)]/30 text-xs text-[var(--vscode-descriptionForeground)]">
        <div className="flex items-center gap-2">
          <div className="h-[28px]">
            <ModeSelector value={mode} onChange={setMode} />
          </div>
          <div className="h-[28px]">
            <ModelSelector value={model} onChange={setModel} />
          </div>
          
          {/* Context indicator (only if files actually selected) */}
          {/* TODO: Replace with real contextFiles count */}
          {false && (
            <div className="flex items-center gap-1 px-2 py-1 rounded text-[var(--vscode-descriptionForeground)] hover:text-[var(--vscode-foreground)] cursor-pointer transition-colors">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="text-xs">3 files</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}