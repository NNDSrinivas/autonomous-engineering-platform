import React, { useState, useRef, useEffect } from 'react';
import { ExternalLink } from 'lucide-react';
import './NaviInlineCommand.css';
import { stripEchoedCommand } from './stripEchoedCommand';

// =============================================================================
// NAVI INLINE COMMAND
// =============================================================================
// Sleek, professional inline command block for chat messages
// Replaces the old "Bash" blocks with a modern design
// =============================================================================

interface NaviInlineCommandProps {
  commandId?: string;
  command: string;
  output?: string;
  status: 'running' | 'done' | 'error';
  showOutput?: boolean;
  purpose?: string;
  explanation?: string;
  nextAction?: string;
  exitCode?: number;
  onOpenActivity?: (commandId: string) => void;
  highlighted?: boolean;
}

export const NaviInlineCommand: React.FC<NaviInlineCommandProps> = ({
  commandId,
  command,
  output,
  status,
  showOutput = false,
  purpose,
  explanation,
  nextAction,
  exitCode,
  onOpenActivity,
  highlighted = false,
}) => {
  // Auto-expand when running, has output, or has error
  const [expanded, setExpanded] = useState(
    status === 'running' || status === 'error' || (showOutput && !!output)
  );
  const hasOutput = Boolean(output && output.trim());
  const allowOutput = showOutput || status === 'error';
  const outputRef = useRef<HTMLPreElement>(null);

  // Auto-scroll to bottom when output changes
  useEffect(() => {
    if (outputRef.current && output && !allowOutput) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output, allowOutput]);

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <span className="nic-spinner" />;
      case 'done':
        return <span className="nic-check">✓</span>;
      case 'error':
        return <span className="nic-error">✕</span>;
    }
  };

  const formatOutput = () => {
    if (!output) return status === 'running' ? 'Executing...' : 'No output';
    const cleaned = stripEchoedCommand(output, command);
    // NOTE: Returns full cleaned output without truncation. For commands with very
    // large outputs (e.g., npm install, docker build, database dumps), rendering the
    // full output in the DOM could cause performance issues. Consider implementing
    // virtualized scrolling or lazy rendering if performance problems are observed.
    return cleaned.trim() || 'No output';
  };

  // Syntax highlighting for bash commands
  const highlightBashCommand = (cmd: string) => {
    const tokens: { type: string; value: string }[] = [];
    let i = 0;

    while (i < cmd.length) {
      const char = cmd[i];

      // Skip whitespace
      if (/\s/.test(char)) {
        tokens.push({ type: 'whitespace', value: char });
        i++;
        continue;
      }

      // Handle quoted strings
      if (char === '"' || char === "'") {
        const quote = char;
        let str = quote;
        i++;
        while (i < cmd.length && cmd[i] !== quote) {
          if (cmd[i] === '\\' && i + 1 < cmd.length) {
            str += cmd[i] + cmd[i + 1];
            i += 2;
          } else {
            str += cmd[i];
            i++;
          }
        }
        if (i < cmd.length) str += cmd[i++];
        tokens.push({ type: 'string', value: str });
        continue;
      }

      // Handle flags (--flag or -f)
      if (char === '-') {
        let flag = char;
        i++;
        while (i < cmd.length && /[a-zA-Z0-9-]/.test(cmd[i])) {
          flag += cmd[i++];
        }
        tokens.push({ type: 'flag', value: flag });
        continue;
      }

      // Handle regular tokens (commands, paths, etc.)
      let token = '';
      while (i < cmd.length && !/[\s"']/.test(cmd[i])) {
        // Only stop at '-' if it starts a new token (at beginning)
        // This prevents splitting paths like "marketing-website-navra-labs"
        if (cmd[i] === '-' && token.length === 0) {
          break;  // This dash starts a flag token
        }
        token += cmd[i++];
      }

      // Determine token type
      const type = tokens.length === 0 || (tokens.length === 1 && tokens[0].type === 'whitespace')
        ? 'command'
        : token.includes('/') || token.includes('.')
          ? 'path'
          : 'arg';

      tokens.push({ type, value: token });
    }

    return tokens.map((token, idx) => {
      if (token.type === 'whitespace') return token.value;
      return (
        <span key={idx} className={`bash-${token.type}`}>
          {token.value}
        </span>
      );
    });
  };

  return (
    <div className={`nic nic--${status} ${highlighted ? 'nic--highlight' : ''}`} data-command-id={commandId}>
      <div className="nic-header" onClick={() => setExpanded(!expanded)}>
        <div className="nic-status">
          {getStatusIcon()}
        </div>
        <code className="nic-command">{highlightBashCommand(command)}</code>
        {commandId && onOpenActivity && (
          <button
            className="nic-activity-btn"
            title="Open command activity"
            aria-label="Open command activity"
            onClick={(event) => {
              event.stopPropagation();
              onOpenActivity(commandId);
            }}
          >
            <ExternalLink size={12} />
          </button>
        )}
        <span className={`nic-expand ${expanded ? 'is-open' : ''}`}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2.5 3.75L5 6.25L7.5 3.75" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
      </div>

      {expanded && (
        <div className="nic-body">
          {purpose && (
            <div className="nic-meta nic-purpose">
              <span className="nic-meta-label">Purpose</span>
              <span className="nic-meta-text">{purpose}</span>
            </div>
          )}

          {allowOutput ? (
            <div className="nic-output">
              <pre>{formatOutput()}</pre>
            </div>
          ) : hasOutput ? (
            <div className="nic-output">
              <pre ref={outputRef}>{output}</pre>
            </div>
          ) : null}

          {status === 'error' && exitCode !== undefined && (
            <div className="nic-exit">Exit code: {exitCode}</div>
          )}

          {explanation && (
            <div className="nic-meta nic-explanation">
              <span className="nic-meta-label">Result</span>
              <span className="nic-meta-text">{explanation}</span>
            </div>
          )}

          {nextAction && (
            <div className="nic-meta nic-next">
              <span className="nic-meta-label">Next</span>
              <span className="nic-meta-text">{nextAction}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NaviInlineCommand;
