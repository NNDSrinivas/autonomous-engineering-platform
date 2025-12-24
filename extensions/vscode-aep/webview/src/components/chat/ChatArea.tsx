import React, { useState } from 'react';
import { useUIState } from '../../state/uiStore';
import { Message } from '../../state/uiStore';
import { PlanRenderer } from './PlanRenderer';
import { ToolApproval } from '../plan/ToolApproval';

// TEMP: Stub feedback icons until Phase 4.2 feedback system
const FeedbackIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
  </svg>
);

// PHASE 4.0.2 DESIGN TOKENS - NAVI Font System & Colors
const DESIGN_TOKENS = {
  user: {
    bg: 'rgba(40, 42, 48, 0.55)',
    border: 'rgba(255, 255, 255, 0.08)',
    text: '#e8eaf0',
    timestamp: 'rgba(180, 190, 210, 0.45)'
  },
  navi: {
    bg: 'rgba(18, 19, 23, 0.65)',
    border: 'rgba(255, 255, 255, 0.06)',
    text: '#dfe2ea'
  },
  actions: {
    default: 'rgba(190, 195, 210, 0.55)',
    hover: '#e6f0ff',
    glow: '0 0 4px rgba(120, 180, 255, 0.25)'
  },
  fonts: {
    ui: 'Inter, SF Pro Text, Segoe UI, system-ui, sans-serif',
    mono: 'JetBrains Mono, SF Mono, Consolas, monospace',
    chatBody: '13px',
    codeBlocks: '12.5px',
    metaText: '11px',
    composerInput: '13.5px'
  }
};

// System-Grade Action Icons - Aerospace Specification
const CopyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M8 4V16C8 17.1 8.9 18 10 18H18C19.1 18 20 17.1 20 16V7L17 4H10C8.9 4 8 4.9 8 6Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M16 4V8H20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M16 18V20C16 21.1 15.1 22 14 22H6C4.9 22 4 21.1 4 20V9C4 7.9 4.9 7 6 7H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const RetryIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M23 4V10H17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M20.49 15C19.9 16.5 18.7 17.77 17.18 18.6C15.66 19.43 13.91 19.79 12.18 19.62C10.45 19.45 8.82 18.76 7.56 17.64C6.3 16.52 5.48 15.03 5.23 13.37" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M1 20V14H7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ThumbUpIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M7 10V20H21V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 15H7V20H4C2.9 20 2 19.1 2 18V17C2 15.9 2.9 15 4 15Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M21 10C20.18 8.84 18.84 8 17.31 8H14L15 3C15 2.45 14.55 2 14 2C13.45 2 13 2.45 13 3L12 8H7V10H21Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ThumbDownIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M17 14V4H3V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M20 9H17V4H20C21.1 4 22 4.9 22 6V7C22 8.1 21.1 9 20 9Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M3 14C3.82 15.16 5.16 16 6.69 16H10L9 21C9 21.55 9.45 22 10 22C10.55 22 11 21.55 11 21L12 16H17V14H3Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [showActions, setShowActions] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    console.log('Copied message content');
  };

  const handleRetry = () => {
    console.log('Retry message');
    // TODO: Implement retry functionality
  };

  const handleThumbsUp = () => {
    console.log('Thumbs up');
    // TODO: Implement feedback functionality
  };

  const handleThumbsDown = () => {
    console.log('Thumbs down');
    // TODO: Implement feedback functionality
  };

  return (
    <div className={`mb-6 ${message.role === 'user' ? 'flex justify-end' : 'mr-12'}`}>
      {message.role === 'user' ? (
        /* USER MESSAGE - Inline Copy Button (Fixed UX) */
        <div className="flex flex-col items-end max-w-[78%] group relative">
          <div
            className="navi-user-bubble px-4 py-3 pr-12 relative transition-all duration-120 hover:shadow-lg"
            style={{
              background: DESIGN_TOKENS.user.bg,
              backdropFilter: 'blur(16px)',
              border: `1px solid ${DESIGN_TOKENS.user.border}`,
              borderRadius: '14px',
              color: DESIGN_TOKENS.user.text,
              fontSize: DESIGN_TOKENS.fonts.chatBody,
              fontFamily: DESIGN_TOKENS.fonts.ui,
              lineHeight: '1.45'
            }}
          >
            {message.content}

            {/* Inline Copy Button - Top Right Corner */}
            <button
              onClick={handleCopy}
              className="absolute top-2 right-3 p-1.5 rounded opacity-0 group-hover:opacity-100 transition-all duration-150"
              style={{
                color: DESIGN_TOKENS.actions.default,
                minWidth: '28px',
                minHeight: '28px'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = DESIGN_TOKENS.actions.hover;
                e.currentTarget.style.boxShadow = DESIGN_TOKENS.actions.glow;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = DESIGN_TOKENS.actions.default;
                e.currentTarget.style.boxShadow = 'none';
              }}
              title="Copy"
            >
              <CopyIcon />
            </button>
          </div>

          {/* Timestamp outside bubble */}
          <div
            className="mt-1.5 mr-1"
            style={{
              color: DESIGN_TOKENS.user.timestamp,
              fontSize: DESIGN_TOKENS.fonts.metaText,
              fontFamily: DESIGN_TOKENS.fonts.ui
            }}
          >
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      ) : (
        /* NAVI MESSAGE - Right-Aligned Vertical Action Rail */
        <div
          className="flex max-w-[84%] group relative"
          onMouseEnter={() => setShowActions(true)}
          onMouseLeave={() => setShowActions(false)}
        >
          <div
            className="navi-assistant-bubble flex-1 transition-all duration-120"
            style={{
              background: DESIGN_TOKENS.navi.bg,
              backdropFilter: 'blur(14px)',
              border: `1px solid ${DESIGN_TOKENS.navi.border}`,
              borderRadius: '12px',
              color: DESIGN_TOKENS.navi.text,
              fontSize: DESIGN_TOKENS.fonts.chatBody,
              fontFamily: DESIGN_TOKENS.fonts.ui,
              padding: '18px'
            }}
          >
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-[var(--vscode-charts-blue)] flex-shrink-0 flex items-center justify-center text-xs font-medium text-white">
                N
              </div>
              <div className="flex-1">
                {/* DEBUG: Log message details */}
                {console.log('🐛 ChatMessage:', message.id, 'type:', message.type, 'plan:', !!message.plan, 'role:', message.role)}
                {console.log('🐛 ChatMessage full object:', message)}
                {console.log('🐛 ChatMessage type check:', message.type === 'plan', 'plan check:', !!message.plan)}

                {/* VISIBLE DEBUG */}
                {message.type === 'plan' && (
                  <div style={{ background: 'red', color: 'white', padding: '10px', margin: '5px' }}>
                    DEBUG: Plan message detected! Type: {message.type}, Has plan: {message.plan ? 'YES' : 'NO'}
                  </div>
                )}

                {/* Phase 4.1.2: Render structured plans and errors */}
                {message.type === 'plan' && message.plan ? (
                  <PlanRenderer
                    plan={message.plan}
                    reasoning={message.reasoning}
                    session_id={message.session_id}
                  />
                ) : message.type === 'error' && message.error ? (
                  <div className="plan-error p-3 rounded border-l-4 border-red-500 bg-red-500/10">
                    <div className="text-red-400 font-medium mb-1">Error</div>
                    <div className="text-red-300 text-sm">{message.error}</div>
                    <div className="text-gray-400 text-sm mt-2">Message:</div>
                    <div className="whitespace-pre-wrap leading-relaxed mt-1 text-gray-300">
                      {message.content}
                    </div>
                  </div>
                ) : message.plan ? (
                  <PlanRenderer plan={message.plan} />
                ) : message.planError ? (
                  <div className="plan-error p-3 rounded border-l-4 border-red-500 bg-red-500/10">
                    <div className="text-red-400 font-medium mb-1">Plan Generation Failed</div>
                    <div className="text-red-300 text-sm">{message.planError}</div>
                    <div className="text-gray-400 text-sm mt-2">Fallback response:</div>
                    <div className="whitespace-pre-wrap leading-relaxed mt-1 text-gray-300">
                      {message.content}
                    </div>
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap leading-relaxed">
                    {message.content}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right-Aligned Vertical Action Rail - Hover Only */}
          {showActions && (
            <div className="flex flex-col gap-2 ml-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
              <button
                onClick={handleCopy}
                className="navi-action-btn p-2 rounded transition-all duration-120"
                style={{ color: DESIGN_TOKENS.actions.default }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.actions.hover;
                  e.currentTarget.style.boxShadow = DESIGN_TOKENS.actions.glow;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.actions.default;
                  e.currentTarget.style.boxShadow = 'none';
                }}
                title="Copy"
              >
                <CopyIcon />
              </button>
              <button
                onClick={handleRetry}
                className="navi-action-btn p-2 rounded transition-all duration-120"
                style={{ color: DESIGN_TOKENS.actions.default }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.actions.hover;
                  e.currentTarget.style.boxShadow = DESIGN_TOKENS.actions.glow;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.actions.default;
                  e.currentTarget.style.boxShadow = 'none';
                }}
                title="Retry"
              >
                <RetryIcon />
              </button>
              <button
                onClick={() => {
                  console.log('Feedback panel - lightweight');
                  // TODO: Open lightweight feedback panel
                }}
                className="navi-action-btn p-2 rounded transition-all duration-120"
                style={{ color: DESIGN_TOKENS.actions.default }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.actions.hover;
                  e.currentTarget.style.boxShadow = DESIGN_TOKENS.actions.glow;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = DESIGN_TOKENS.actions.default;
                  e.currentTarget.style.boxShadow = 'none';
                }}
                title="Feedback"
              >
                <FeedbackIcon />
              </button>
            </div>
          )}

          {/* Timestamp outside bubble - bottom left, show on hover or last message */}
          <div
            className="ml-1 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
            style={{
              color: DESIGN_TOKENS.user.timestamp,
              fontSize: DESIGN_TOKENS.fonts.metaText,
              fontFamily: DESIGN_TOKENS.fonts.ui
            }}
          >
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      )}
    </div>
  );
};

const ChatArea: React.FC = () => {
  const { state, dispatch } = useUIState();
  const { messages, pendingToolApproval } = state;

  const handleToolApprovalResolve = () => {
    dispatch({ type: 'RESOLVE_TOOL_APPROVAL' });
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}

      {/* Phase 4.1.2: Tool Approval UI */}
      {pendingToolApproval && (
        <ToolApproval
          tool_request={pendingToolApproval.tool_request}
          session_id={pendingToolApproval.session_id}
          onResolve={handleToolApprovalResolve}
        />
      )}

      {messages.length === 0 && (
        <div className="flex items-center justify-center h-full text-[var(--vscode-descriptionForeground)]">
          <div className="text-center">
            <div className="text-lg mb-2">👋</div>
            <div className="text-sm">Start a conversation with NAVI</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatArea;