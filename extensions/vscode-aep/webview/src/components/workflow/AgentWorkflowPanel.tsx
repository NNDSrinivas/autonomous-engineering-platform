import React, { useState } from 'react';
import { useUIState, TodoItem, FileChangeSummary } from '../../state/uiStore';

/**
 * AgentWorkflowPanel - Live todos, file changes, and permissions (Copilot-style)
 * 
 * Phase 4.0: Shows the "what I'm doing now" experience that makes agents feel alive.
 * Only appears when agent workflow is active. Collapsible to save space.
 */
export function AgentWorkflowPanel() {
  const { state } = useUIState();
  const [isExpanded, setIsExpanded] = useState(true);
  
  // Only render if agent workflow is active
  if (!state.agentWorkflow?.isActive) {
    return null;
  }
  
  const { todos, filesChanged } = state.agentWorkflow;
  const activeTodos = todos.filter(t => t.status === 'active' || t.status === 'pending');
  const completedTodos = todos.filter(t => t.status === 'completed');
  const failedTodos = todos.filter(t => t.status === 'failed');
  
  return (
    <div className="border-b border-[var(--vscode-panel-border)] bg-[var(--vscode-sideBar-background)]">
      {/* Collapsible header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />
          <span className="text-sm font-medium text-[var(--vscode-foreground)]">Agent Working</span>
          <span className="text-xs text-[var(--vscode-descriptionForeground)]">
            {activeTodos.length} active, {completedTodos.length} done
          </span>
        </div>
        <svg 
          className={`w-4 h-4 text-[var(--vscode-foreground)] transition-transform ${
            isExpanded ? 'rotate-90' : ''
          }`}
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
      
      {/* Expandable content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-2">
          {/* Active/Pending Todos */}
          {activeTodos.map(todo => (
            <TodoItemComponent key={todo.id} todo={todo} />
          ))}
          
          {/* Completed todos (collapsed) */}
          {completedTodos.length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-[var(--vscode-descriptionForeground)] cursor-pointer hover:text-[var(--vscode-foreground)]">
                ✅ {completedTodos.length} completed
              </summary>
              <div className="mt-1 ml-4 space-y-1">
                {completedTodos.map(todo => (
                  <TodoItemComponent key={todo.id} todo={todo} />
                ))}
              </div>
            </details>
          )}
          
          {/* Failed todos */}
          {failedTodos.map(todo => (
            <TodoItemComponent key={todo.id} todo={todo} />
          ))}
          
          {/* File changes */}
          {filesChanged.length > 0 && (
            <div className="mt-3 pt-2 border-t border-[var(--vscode-panel-border)]">
              <div className="text-xs font-medium text-[var(--vscode-foreground)] mb-2">
                Files Changed ({filesChanged.length})
              </div>
              {filesChanged.map((file, index) => (
                <FileChangeComponent key={index} file={file} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Individual todo item with status indicator
 */
function TodoItemComponent({ todo }: { todo: TodoItem }) {
  const getStatusIcon = () => {
    switch (todo.status) {
      case 'pending': return <div className="w-2 h-2 border border-[var(--vscode-descriptionForeground)] rounded-full" />;
      case 'active': return <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />;
      case 'completed': return <div className="text-green-500 text-xs">✓</div>;
      case 'failed': return <div className="text-red-500 text-xs">✗</div>;
      default: return null;
    }
  };
  
  const getTextStyle = () => {
    switch (todo.status) {
      case 'completed': return 'text-[var(--vscode-descriptionForeground)] line-through';
      case 'failed': return 'text-red-400';
      case 'active': return 'text-[var(--vscode-foreground)] font-medium';
      default: return 'text-[var(--vscode-descriptionForeground)]';
    }
  };
  
  return (
    <div className="flex items-center gap-2">
      {getStatusIcon()}
      <span className={`text-xs ${getTextStyle()}`}>
        {todo.text}
      </span>
    </div>
  );
}

/**
 * File change summary with add/delete counts - clickable to open file/diff
 */
function FileChangeComponent({ file }: { file: FileChangeSummary }) {
  const handleClick = () => {
    // Send message to extension to open the file
    if (window.vscode) {
      window.vscode.postMessage({
        type: 'OPEN_FILE',
        path: file.path
      });
    }
  };

  const handleShowDiff = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.vscode) {
      window.vscode.postMessage({
        type: 'showDiff',
        filePath: file.path
      });
    }
  };

  const getStatusIcon = () => {
    switch (file.status) {
      case 'added': return <span className="text-green-500 mr-1">A</span>;
      case 'modified': return <span className="text-yellow-500 mr-1">M</span>;
      case 'deleted': return <span className="text-red-500 mr-1">D</span>;
      default: return null;
    }
  };

  return (
    <div
      className="flex items-center justify-between text-xs hover:bg-[var(--vscode-list-hoverBackground)] rounded px-1 py-0.5 cursor-pointer group"
      onClick={handleClick}
      title={`Click to open ${file.path}`}
    >
      <div className="flex items-center gap-1 min-w-0 flex-1">
        {getStatusIcon()}
        <span className="text-[var(--vscode-foreground)] truncate">
          {file.path}
        </span>
      </div>
      <div className="flex items-center gap-2">
        {file.additions > 0 && (
          <span className="text-green-500">+{file.additions}</span>
        )}
        {file.deletions > 0 && (
          <span className="text-red-500">-{file.deletions}</span>
        )}
        <button
          onClick={handleShowDiff}
          className="opacity-0 group-hover:opacity-100 text-[var(--vscode-textLink-foreground)] hover:underline transition-opacity"
          title="Show diff"
        >
          diff
        </button>
      </div>
    </div>
  );
}