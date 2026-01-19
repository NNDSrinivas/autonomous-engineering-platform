import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Terminal, Play, Copy, Trash2, ChevronUp, ChevronDown, X } from 'lucide-react';

interface TerminalEntry {
  id: string;
  command: string;
  cwd?: string;
  output: string;
  status: 'running' | 'done' | 'error';
  exitCode?: number;
  durationMs?: number;
  startedAt?: string;
}

interface TerminalInputProps {
  entries: TerminalEntry[];
  onExecuteCommand: (command: string) => void;
  onClear: () => void;
  isOpen: boolean;
  onToggle: () => void;
  maxEntries?: number;
}

export const TerminalInput: React.FC<TerminalInputProps> = ({
  entries,
  onExecuteCommand,
  onClear,
  isOpen,
  onToggle,
  maxEntries = 50,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  // Common commands for suggestions
  const commonCommands = [
    'npm test',
    'npm run build',
    'npm install',
    'git status',
    'git diff',
    'git log --oneline -10',
    'git branch',
    'git pull',
    'git push',
    'ls -la',
    'pwd',
    'cat package.json',
    'python -m pytest',
    'pip install -r requirements.txt',
  ];

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [entries]);

  // Filter suggestions based on input
  useEffect(() => {
    if (inputValue.trim()) {
      const filtered = [
        ...commandHistory.filter(cmd => cmd.startsWith(inputValue)),
        ...commonCommands.filter(
          cmd => cmd.startsWith(inputValue) && !commandHistory.includes(cmd)
        ),
      ].slice(0, 5);
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [inputValue, commandHistory]);

  const handleSubmit = useCallback(() => {
    const command = inputValue.trim();
    if (!command) return;

    onExecuteCommand(command);

    // Add to history (avoid duplicates)
    setCommandHistory(prev => {
      const filtered = prev.filter(c => c !== command);
      return [command, ...filtered].slice(0, 50);
    });

    setInputValue('');
    setHistoryIndex(-1);
    setShowSuggestions(false);
  }, [inputValue, onExecuteCommand]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (commandHistory.length > 0) {
        const newIndex = Math.min(historyIndex + 1, commandHistory.length - 1);
        setHistoryIndex(newIndex);
        setInputValue(commandHistory[newIndex]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setInputValue(commandHistory[newIndex]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInputValue('');
      }
    } else if (e.key === 'Tab' && suggestions.length > 0) {
      e.preventDefault();
      setInputValue(suggestions[0]);
      setShowSuggestions(false);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const copyOutput = useCallback((output: string) => {
    navigator.clipboard.writeText(output);
  }, []);

  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  const isRunning = entries.some(e => e.status === 'running');
  const displayEntries = entries.slice(-maxEntries);

  return (
    <div className="terminal-enhanced-panel">
      {/* Terminal Header */}
      <div className="terminal-header">
        <div className="terminal-title">
          <Terminal className="h-4 w-4" />
          <span>Terminal</span>
          <span className={`terminal-status ${isRunning ? 'running' : 'idle'}`}>
            {isRunning ? 'Running' : 'Idle'}
          </span>
        </div>
        <div className="terminal-actions">
          <button
            className="terminal-action-btn"
            onClick={onClear}
            title="Clear terminal"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            className="terminal-action-btn"
            onClick={onToggle}
            title={isOpen ? 'Collapse' : 'Expand'}
          >
            {isOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronUp className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>

      {isOpen && (
        <>
          {/* Terminal Output */}
          <div className="terminal-output" ref={outputRef}>
            {displayEntries.length === 0 ? (
              <div className="terminal-empty">
                <Terminal className="h-8 w-8 opacity-30" />
                <p>No terminal activity yet.</p>
                <p className="text-xs opacity-60">
                  Type a command below or wait for NAVI to execute commands.
                </p>
              </div>
            ) : (
              displayEntries.map(entry => (
                <div
                  key={entry.id}
                  className={`terminal-entry terminal-entry--${entry.status}`}
                >
                  <div className="terminal-entry-header">
                    <div className="terminal-entry-command">
                      <span className="terminal-prompt">$</span>
                      <span className="terminal-cmd">{entry.command}</span>
                    </div>
                    <div className="terminal-entry-meta">
                      {entry.durationMs !== undefined && (
                        <span className="terminal-duration">
                          {formatDuration(entry.durationMs)}
                        </span>
                      )}
                      {entry.exitCode !== undefined && entry.exitCode !== 0 && (
                        <span className="terminal-exit-code">
                          exit {entry.exitCode}
                        </span>
                      )}
                      <span className={`terminal-status-badge ${entry.status}`}>
                        {entry.status === 'running' && (
                          <span className="terminal-spinner"></span>
                        )}
                        {entry.status}
                      </span>
                      <button
                        className="terminal-copy-btn"
                        onClick={() => copyOutput(entry.output)}
                        title="Copy output"
                      >
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                  {entry.cwd && (
                    <div className="terminal-cwd">in {entry.cwd}</div>
                  )}
                  <pre className="terminal-entry-output">
                    {entry.output || (
                      entry.status === 'running'
                        ? 'Running...'
                        : 'No output'
                    )}
                  </pre>
                </div>
              ))
            )}
          </div>

          {/* Command Input */}
          <div className="terminal-input-container">
            <div className="terminal-input-wrapper">
              <span className="terminal-input-prompt">$</span>
              <input
                ref={inputRef}
                type="text"
                className="terminal-input"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a command..."
                disabled={isRunning}
              />
              <button
                className="terminal-submit-btn"
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isRunning}
                title="Execute command"
              >
                <Play className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Suggestions Dropdown */}
            {showSuggestions && (
              <div className="terminal-suggestions">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    className="terminal-suggestion"
                    onClick={() => handleSuggestionClick(suggestion)}
                  >
                    <span className="suggestion-icon">$</span>
                    <span className="suggestion-text">{suggestion}</span>
                    {commandHistory.includes(suggestion) && (
                      <span className="suggestion-badge">history</span>
                    )}
                  </button>
                ))}
              </div>
            )}

            <div className="terminal-hints">
              <span>↑↓ History</span>
              <span>Tab Autocomplete</span>
              <span>Enter Execute</span>
            </div>
          </div>
        </>
      )}

      <style>{`
        .terminal-enhanced-panel {
          display: flex;
          flex-direction: column;
          background: var(--navi-terminal-bg, hsl(220 15% 5%));
          border: 1px solid var(--navi-border, hsl(220 15% 20%));
          border-radius: 12px;
          overflow: hidden;
          font-family: 'JetBrains Mono', 'Fira Code', monospace;
        }

        .terminal-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: var(--navi-terminal-header, hsl(220 15% 8%));
          border-bottom: 1px solid var(--navi-border, hsl(220 15% 20%));
        }

        .terminal-title {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          font-weight: 500;
          color: var(--navi-text-primary, hsl(220 10% 92%));
        }

        .terminal-status {
          font-size: 10px;
          padding: 2px 8px;
          border-radius: 10px;
          font-weight: 500;
        }

        .terminal-status.running {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
          animation: pulse 1.5s ease-in-out infinite;
        }

        .terminal-status.idle {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .terminal-actions {
          display: flex;
          gap: 4px;
        }

        .terminal-action-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          background: transparent;
          border: none;
          border-radius: 6px;
          color: var(--navi-text-muted, hsl(220 10% 55%));
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .terminal-action-btn:hover {
          background: var(--navi-bg-hover, hsl(220 15% 14%));
          color: var(--navi-text-primary, hsl(220 10% 92%));
        }

        .terminal-output {
          flex: 1;
          min-height: 120px;
          max-height: 300px;
          overflow-y: auto;
          padding: 12px;
        }

        .terminal-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 8px;
          height: 120px;
          color: var(--navi-text-muted, hsl(220 10% 55%));
          text-align: center;
        }

        .terminal-entry {
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--navi-border, hsl(220 15% 15%));
        }

        .terminal-entry:last-child {
          margin-bottom: 0;
          padding-bottom: 0;
          border-bottom: none;
        }

        .terminal-entry-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 6px;
        }

        .terminal-entry-command {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
        }

        .terminal-prompt {
          color: var(--navi-accent, #10b981);
          font-weight: 600;
        }

        .terminal-cmd {
          color: var(--navi-text-primary, hsl(220 10% 92%));
          font-size: 12px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .terminal-entry-meta {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 10px;
          flex-shrink: 0;
        }

        .terminal-duration {
          color: var(--navi-text-muted, hsl(220 10% 55%));
        }

        .terminal-exit-code {
          color: var(--navi-error, #ef4444);
        }

        .terminal-status-badge {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 9px;
          text-transform: uppercase;
          font-weight: 600;
        }

        .terminal-status-badge.running {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }

        .terminal-status-badge.done {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .terminal-status-badge.error {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .terminal-spinner {
          width: 8px;
          height: 8px;
          border: 1.5px solid transparent;
          border-top-color: currentColor;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .terminal-copy-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 4px;
          background: transparent;
          border: none;
          border-radius: 4px;
          color: var(--navi-text-muted, hsl(220 10% 55%));
          cursor: pointer;
          opacity: 0;
          transition: all 0.15s ease;
        }

        .terminal-entry:hover .terminal-copy-btn {
          opacity: 1;
        }

        .terminal-copy-btn:hover {
          background: var(--navi-bg-hover, hsl(220 15% 14%));
          color: var(--navi-primary, #00d4ff);
        }

        .terminal-cwd {
          font-size: 10px;
          color: var(--navi-text-muted, hsl(220 10% 45%));
          margin-bottom: 6px;
          padding-left: 16px;
        }

        .terminal-entry-output {
          margin: 0;
          padding: 8px 12px;
          background: var(--navi-bg-dark, hsl(220 15% 4%));
          border-radius: 6px;
          font-size: 11px;
          line-height: 1.5;
          color: var(--navi-terminal-text, hsl(140 70% 65%));
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 200px;
          overflow-y: auto;
        }

        .terminal-entry--error .terminal-entry-output {
          color: var(--navi-error, #ef4444);
        }

        .terminal-input-container {
          position: relative;
          padding: 12px;
          border-top: 1px solid var(--navi-border, hsl(220 15% 20%));
          background: var(--navi-terminal-header, hsl(220 15% 7%));
        }

        .terminal-input-wrapper {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background: var(--navi-bg-dark, hsl(220 15% 4%));
          border: 1px solid var(--navi-border, hsl(220 15% 20%));
          border-radius: 8px;
          transition: border-color 0.2s ease;
        }

        .terminal-input-wrapper:focus-within {
          border-color: var(--navi-primary, #00d4ff);
          box-shadow: 0 0 0 2px rgba(0, 212, 255, 0.1);
        }

        .terminal-input-prompt {
          color: var(--navi-accent, #10b981);
          font-weight: 600;
          font-size: 13px;
        }

        .terminal-input {
          flex: 1;
          background: none;
          border: none;
          outline: none;
          color: var(--navi-text-primary, hsl(220 10% 92%));
          font-family: inherit;
          font-size: 12px;
        }

        .terminal-input::placeholder {
          color: var(--navi-text-muted, hsl(220 10% 40%));
        }

        .terminal-input:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .terminal-submit-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          background: var(--navi-primary, #00d4ff);
          border: none;
          border-radius: 6px;
          color: var(--navi-bg-dark, hsl(220 15% 8%));
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .terminal-submit-btn:hover:not(:disabled) {
          background: var(--navi-primary-light, #33ddff);
          transform: scale(1.05);
        }

        .terminal-submit-btn:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }

        .terminal-suggestions {
          position: absolute;
          bottom: 100%;
          left: 12px;
          right: 12px;
          margin-bottom: 4px;
          background: var(--navi-bg-panel, hsl(220 15% 10%));
          border: 1px solid var(--navi-border, hsl(220 15% 20%));
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.3);
        }

        .terminal-suggestion {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          padding: 8px 12px;
          background: none;
          border: none;
          color: var(--navi-text-primary, hsl(220 10% 92%));
          font-family: inherit;
          font-size: 12px;
          text-align: left;
          cursor: pointer;
          transition: background 0.15s ease;
        }

        .terminal-suggestion:hover {
          background: var(--navi-bg-hover, hsl(220 15% 14%));
        }

        .suggestion-icon {
          color: var(--navi-accent, #10b981);
          font-weight: 600;
        }

        .suggestion-text {
          flex: 1;
        }

        .suggestion-badge {
          font-size: 9px;
          padding: 2px 6px;
          background: rgba(124, 58, 237, 0.2);
          color: var(--navi-secondary, #7c3aed);
          border-radius: 10px;
        }

        .terminal-hints {
          display: flex;
          gap: 16px;
          margin-top: 8px;
          font-size: 10px;
          color: var(--navi-text-muted, hsl(220 10% 45%));
        }

        .terminal-hints span {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
};

export default TerminalInput;
