import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { vscode } from '../types';
import { useReviewStream, type StreamError } from '../hooks/useReviewStream';
import { useAutoFix } from '../hooks/useAutoFix';
import { DiffViewer } from './DiffViewer';
import DiffApplyPanel from './DiffApplyPanel';

// Types for comprehensive message handling
interface Message {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'error' | 'streaming';
  content: string;
  timestamp: Date;
  metadata?: {
    tokens?: number;
    model?: string;
    cost?: number;
    isStreaming?: boolean;
    suggestions?: string[];
    files?: string[];
    isRefactor?: boolean;
  };
}

// Streaming refactor interfaces
interface RefactorProgress {
  stage: 'planning' | 'transforming' | 'generating' | 'applying' | 'complete';
  progress: number;
  message: string;
  details?: Record<string, any>;
}

interface RefactorPlan {
  instruction: string;
  language: string;
  analyzed_files: string[];
  execution_plan: any;
  estimated_changes: number;
  complexity: string;
}

interface DiffChunk {
  file: string;
  description: string;
  diff: string;
  diff_content?: string;
  change_summary: any;
  change_type: 'create' | 'modify' | 'delete';
}

interface PatchBundle {
  files: any[];
  statistics: any;
  dry_run: boolean;
  ready_to_apply: boolean;
}

interface NaviChatPanelProps {
  onStartReview: () => void;
  onAutoFix?: (filePath: string, fix: string) => void;
  onOpenFile?: (filePath: string) => void;
  initialMessages?: Message[];
  maxMessages?: number;
  allowFileUploads?: boolean;
  enableKeyboardShortcuts?: boolean;
  enableStreaming?: boolean;
}

// Message component with rich rendering
// Streaming refactor components
const ProgressTimeline: React.FC<{ steps: string[]; currentFile?: string; className?: string }> = ({
  steps,
  currentFile,
  className = ''
}) => {
  return (
    <div className={`space-y-2 bg-blue-50 p-3 rounded-lg border ${className}`}>
      <h4 className="font-semibold text-blue-900 text-sm">Refactor Progress</h4>
      {steps.map((step, i) => (
        <div key={i} className="text-sm text-gray-700 flex items-center space-x-2">
          <span className="text-blue-500">•</span>
          <span>{step}</span>
        </div>
      ))}
      {currentFile && (
        <div className="text-blue-600 font-mono text-sm bg-blue-100 p-2 rounded mt-2">
          <span className="text-blue-800 font-semibold">Working on:</span> {currentFile}
        </div>
      )}
    </div>
  );
};

const DiffPreview: React.FC<{ file: string; diff: string; onToggle?: () => void; isOpen?: boolean }> = ({
  file, diff, onToggle, isOpen = true
}) => {
  return (
    <div className="border rounded bg-white shadow-sm mb-2">
      <button
        className="w-full text-left p-3 bg-gray-100 font-mono text-sm hover:bg-gray-200 transition-colors"
        onClick={onToggle}
      >
        <span className="mr-2">{isOpen ? '▼' : '▶'}</span>
        {file}
      </button>
      {isOpen && (
        <div className="p-2 overflow-auto max-h-96 bg-gray-50">
          <pre className="text-xs font-mono whitespace-pre-wrap text-gray-800">
            {diff}
          </pre>
        </div>
      )}
    </div>
  );
};

const PatchSummary: React.FC<{ patchBundle: PatchBundle; onApply?: () => void }> = ({ patchBundle, onApply }) => {
  return (
    <div className="border border-green-600 rounded p-4 bg-green-50 mb-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-green-800">🎉 Refactor Complete</h4>
          <p className="text-green-700 text-sm">
            {patchBundle.files.length} files changed • {patchBundle.statistics?.lines?.added || 0} lines added • {patchBundle.statistics?.lines?.removed || 0} lines removed
          </p>
        </div>
        {patchBundle.ready_to_apply && onApply && (
          <button
            onClick={onApply}
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition-colors font-medium"
          >
            Apply Changes
          </button>
        )}
      </div>
    </div>
  );
};

const MessageBubble: React.FC<{
  message: Message;
  onSuggestionClick: (suggestion: string) => void;
  onFileClick: (filePath: string) => void;
}> = ({ message, onSuggestionClick, onFileClick }) => {
  const isUser = message.type === 'user';
  const isError = message.type === 'error';
  const isSystem = message.type === 'system';
  const isStreaming = message.metadata?.isStreaming;
  const isRefactorStreaming = message.type === 'streaming' && message.metadata?.isRefactor;

  const formatTimestamp = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).format(date);
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 group`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
        <div className={`
          px-4 py-3 rounded-lg shadow-sm
          ${isUser ? 'bg-blue-600 text-white' :
            isError ? 'bg-red-900 text-red-100 border border-red-700' :
              isSystem ? 'bg-yellow-900 text-yellow-100 border border-yellow-700' :
                'bg-gray-800 text-gray-100'}
          ${isStreaming ? 'animate-pulse' : ''}
        `}>
          <div className="whitespace-pre-wrap break-words">
            {message.content}
            {isStreaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-current animate-ping" />
            )}
          </div>

          {/* File attachments */}
          {message.metadata?.files && message.metadata.files.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-600">
              <div className="flex flex-wrap gap-1">
                {message.metadata.files.map((file, idx) => (
                  <button
                    key={idx}
                    onClick={() => onFileClick(file)}
                    className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                    title={`Open ${file}`}
                  >
                    📁 {file.split('/').pop()}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Quick suggestions */}
          {message.metadata?.suggestions && message.metadata.suggestions.length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-600">
              <div className="text-xs text-gray-400 mb-1">Suggestions:</div>
              <div className="flex flex-wrap gap-1">
                {message.metadata.suggestions.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => onSuggestionClick(suggestion)}
                    className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                  >
                    💡 {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Message metadata */}
        <div className={`mt-1 text-xs text-gray-500 ${isUser ? 'text-right' : 'text-left'}`}>
          <span>{formatTimestamp(message.timestamp)}</span>
          {message.metadata?.tokens && (
            <span className="ml-2">• {message.metadata.tokens} tokens</span>
          )}
          {message.metadata?.model && (
            <span className="ml-2">• {message.metadata.model}</span>
          )}
          {message.metadata?.cost && (
            <span className="ml-2">• ${message.metadata.cost.toFixed(4)}</span>
          )}
        </div>
      </div>
    </div>
  );
};

// Typing indicator component
const TypingIndicator: React.FC = () => (
  <div className="flex justify-start mb-4">
    <div className="bg-gray-800 px-4 py-3 rounded-lg">
      <div className="flex space-x-1">
        <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  </div>
);

// Connection status indicator
const ConnectionStatus: React.FC<{ status: 'connected' | 'connecting' | 'disconnected' | 'error' }> = ({ status }) => {
  const statusConfig = {
    connected: { color: 'bg-green-500', text: 'Connected', icon: '🟢' },
    connecting: { color: 'bg-yellow-500', text: 'Connecting', icon: '🟡' },
    disconnected: { color: 'bg-gray-500', text: 'Disconnected', icon: '⚫' },
    error: { color: 'bg-red-500', text: 'Connection Error', icon: '🔴' }
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center space-x-2 text-xs text-gray-400">
      <div className={`w-2 h-2 rounded-full ${config.color}`} />
      <span>{config.icon} {config.text}</span>
    </div>
  );
};

const NaviChatPanel: React.FC<NaviChatPanelProps> = ({
  onStartReview,
  onAutoFix,
  onOpenFile,
  initialMessages = [],
  maxMessages = 1000,
  allowFileUploads = true,
  enableKeyboardShortcuts = true,
  enableStreaming = true
}) => {
  // State management
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [showFileDialog, setShowFileDialog] = useState(false);

  // Streaming refactor state
  const [isRefactoring, setIsRefactoring] = useState(false);
  const [refactorProgress, setRefactorProgress] = useState<RefactorProgress | null>(null);
  const [refactorPlan, setRefactorPlan] = useState<RefactorPlan | null>(null);
  const [progressSteps, setProgressSteps] = useState<string[]>([]);
  const [currentFile, setCurrentFile] = useState<string>('');
  const [diffs, setDiffs] = useState<DiffChunk[]>([]);
  const [patchBundle, setPatchBundle] = useState<PatchBundle | null>(null);
  const [collapsedDiffs, setCollapsedDiffs] = useState<Set<string>>(new Set());

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Custom hooks
  const reviewStream = useReviewStream();
  const streamError: StreamError | undefined = reviewStream.status.error;
  const connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error' =
    reviewStream.status.error
      ? 'error'
      : reviewStream.status.connected
        ? 'connected'
        : reviewStream.status.streaming
          ? 'connecting'
          : 'disconnected';
  const isStreaming = reviewStream.status.streaming;

  const {
    applyFix,
    isFixing,
    progress: fixProgress,
    fixError
  } = useAutoFix({
    onProgress: handleFixProgress,
    onComplete: handleFixComplete,
    onError: handleFixError
  });
  const fixErrorMessage = (fixError as { message?: string } | null | undefined)?.message;

  // SSE Event handling for streaming refactors
  useEffect(() => {
    if (!enableStreaming) return;

    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      switch (message.type) {
        case 'sse_liveProgress':
          setRefactorProgress(message.data);
          setProgressSteps(prev => [...prev, message.data.message]);
          break;

        case 'sse_refactorPlan':
          setRefactorPlan(message.data);
          setIsRefactoring(true);
          addMessage({
            id: `plan_${Date.now()}`,
            type: 'system',
            content: `📋 Refactor Plan Created\n\n**Language:** ${message.data.language}\n**Files Analyzed:** ${message.data.analyzed_files?.length || 0}\n**Estimated Changes:** ${message.data.estimated_changes}\n**Complexity:** ${message.data.complexity}`,
            timestamp: new Date()
          });
          break;

        case 'sse_fileStart':
          setCurrentFile(message.data.file);
          break;

        case 'sse_fileASTEdit':
          addMessage({
            id: `edit_${Date.now()}`,
            type: 'system',
            content: `🔧 **${message.data.file}**\n${message.data.description}\n\n\`\`\`diff\n${message.data.before}\n---\n${message.data.after}\n\`\`\``,
            timestamp: new Date()
          });
          break;

        case 'sse_diffChunk':
          setDiffs(prev => {
            const existing = prev.find(d => d.file === message.data.file);
            if (existing) {
              return prev.map(d => d.file === message.data.file ? message.data : d);
            }
            return [...prev, message.data];
          });
          break;

        case 'sse_issue':
          addMessage({
            id: `issue_${Date.now()}`,
            type: 'error',
            content: `⚠️ **${message.data.type}:** ${message.data.message}${message.data.file ? `\n\n**File:** ${message.data.file}` : ''}`,
            timestamp: new Date()
          });
          break;

        case 'sse_patchBundle':
          setPatchBundle(message.data);
          addMessage({
            id: `patch_${Date.now()}`,
            type: 'system',
            content: `📦 **Patch Bundle Ready**\n\n${message.data.files.length} files modified\n- ${message.data.statistics?.lines?.added || 0} lines added\n- ${message.data.statistics?.lines?.removed || 0} lines removed\n\n${message.data.ready_to_apply ? '✅ Ready to apply' : '⏸️ Review required'}`,
            timestamp: new Date()
          });
          break;

        case 'sse_done':
          setIsRefactoring(false);
          setCurrentFile('');
          addMessage({
            id: `done_${Date.now()}`,
            type: 'system',
            content: `🎉 **Refactor Completed Successfully!**\n\nExecution time: ${message.data.execution_time?.toFixed(2) || 0}s\nFiles transformed: ${message.data.files_transformed || 0}\nPatches generated: ${message.data.patches_generated || 0}`,
            timestamp: new Date()
          });
          break;

        case 'sse_error':
        case 'refactorError':
          setIsRefactoring(false);
          addMessage({
            id: `error_${Date.now()}`,
            type: 'error',
            content: `❌ **Refactor Failed**\n\n${message.data.message || message.data.error}\n\n${message.data.stage ? `Stage: ${message.data.stage}` : ''}`,
            timestamp: new Date()
          });
          break;

        case 'refactorCancelled':
          setIsRefactoring(false);
          addMessage({
            id: `cancelled_${Date.now()}`,
            type: 'system',
            content: `⏹️ **Refactor Cancelled**\n\nReason: ${message.data.reason}`,
            timestamp: new Date()
          });
          break;

        case 'smartMode.result':
          addMessage({
            id: `smart_${Date.now()}`,
            type: 'system',
            content: `🚀 **Smart Mode Completed**\n\n**Mode:** ${message.result.mode.toUpperCase()}\n**Files Modified:** ${message.result.filesModified.length}\n**Summary:** ${message.result.summary}\n\n${message.result.success ? '✅ Successfully completed' : '❌ Completed with issues'}`,
            timestamp: new Date()
          });
          break;

        case 'smartMode.error':
          addMessage({
            id: `smart_error_${Date.now()}`,
            type: 'error',
            content: `❌ **Smart Mode Failed**\n\n${message.error}`,
            timestamp: new Date()
          });
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [enableStreaming]);

  // Message handling
  function handleStreamMessage(content: string, isComplete: boolean) {
    setMessages(prev => {
      const lastMessage = prev[prev.length - 1];

      if (lastMessage?.type === 'streaming' && !isComplete) {
        // Update streaming message
        return prev.map((msg, idx) =>
          idx === prev.length - 1
            ? { ...msg, content: content, metadata: { ...msg.metadata, isStreaming: true } }
            : msg
        );
      } else {
        // Complete the message or add new one
        const newMessage: Message = {
          id: `msg-${Date.now()}-${Math.random()}`,
          type: isComplete ? 'assistant' : 'streaming',
          content,
          timestamp: new Date(),
          metadata: {
            isStreaming: !isComplete,
            tokens: content.length,
            model: 'navi-gpt-4'
          }
        };

        return [...prev.slice(-maxMessages + 1), newMessage];
      }
    });

    setIsTyping(!isComplete);
  }

  function handleStreamError(error: Error) {
    addSystemMessage(`Stream error: ${error.message}`, 'error');
  }

  function handleFixProgress(progress: any) {
    // Update UI with fix progress
    if (progress?.overallProgress !== undefined) {
      console.log(`Fix progress: ${progress.overallProgress}% - stage: ${progress.stage}`);
    }
  }

  function handleFixComplete(results: any[]) {
    addSystemMessage(`Successfully applied ${results.length} fix operation(s)`, 'system');
  }

  function handleFixError(error: Error) {
    addSystemMessage(`Fix error: ${error.message}`, 'error');
  }

  // Utility functions
  const addMessage = useCallback((messageOrContent: Message | string, type: Message['type'] = 'user', metadata?: Message['metadata']) => {
    const newMessage: Message =
      typeof messageOrContent === 'string'
        ? {
            id: `msg-${Date.now()}-${Math.random()}`,
            type,
            content: messageOrContent,
            timestamp: new Date(),
            metadata
          }
        : {
            id: messageOrContent.id || `msg-${Date.now()}-${Math.random()}`,
            type: messageOrContent.type,
            content: messageOrContent.content,
            timestamp: messageOrContent.timestamp || new Date(),
            metadata: messageOrContent.metadata
          };

    setMessages(prev => [...prev.slice(-maxMessages + 1), newMessage]);
  }, [maxMessages]);

  const addSystemMessage = useCallback((content: string, type: 'system' | 'error' = 'system') => {
    addMessage(content, type, { model: 'system' });
  }, [addMessage]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Effects
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    // Focus input on mount
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (enableKeyboardShortcuts) {
      const handleKeyDown = (e: KeyboardEvent) => {
        // Global keyboard shortcuts
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
          e.preventDefault();
          inputRef.current?.focus();
        }
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
          e.preventDefault();
          onStartReview();
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [enableKeyboardShortcuts, onStartReview]);

  // Event handlers
  const handleSendMessage = useCallback(async () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput) return;

    // Add user message
    addMessage(trimmedInput, 'user', {
      files: selectedFiles.length > 0 ? [...selectedFiles] : undefined
    });

    // Clear input and files
    setInputValue('');
    setSelectedFiles([]);
    setIsTyping(true);

    try {
      // Send message to VS Code extension
      vscode.postMessage({
        type: 'chat-message',
        text: trimmedInput,
        files: selectedFiles
      });

    } catch (error) {
      console.error('Failed to send message:', error);
      addSystemMessage(`Failed to send message: ${error}`, 'error');
    } finally {
      setIsTyping(false);
    }
  }, [inputValue, selectedFiles, addMessage, addSystemMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter') {
      if (e.shiftKey || e.ctrlKey || e.metaKey) {
        // Allow multi-line input
        return;
      } else {
        // Send message
        e.preventDefault();
        handleSendMessage();
      }
    }

    if (e.key === 'Escape') {
      // Clear input
      setInputValue('');
      setSelectedFiles([]);
    }
  }, [handleSendMessage]);

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setInputValue(suggestion);
    inputRef.current?.focus();
  }, []);

  const handleFileClick = useCallback((filePath: string) => {
    onOpenFile?.(filePath);
    vscode.postMessage({
      type: 'open-file',
      filePath
    });
  }, [onOpenFile]);

  const handleFileSelect = useCallback(() => {
    // Trigger VS Code file picker
    vscode.postMessage({
      type: 'select-files'
    });
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    addSystemMessage('Chat cleared');
  }, [addSystemMessage]);

  // Patch and refactor handlers
  const handleApplyPatch = useCallback((patchBundle: PatchBundle) => {
    vscode.postMessage({
      type: 'applyPatch',
      patchBundle
    });

    addSystemMessage(`Applying patch bundle with ${patchBundle.files.length} files...`);
    setPatchBundle(null);
  }, [addSystemMessage]);

  const handleApplyFile = useCallback((file: string, patch: string) => {
    vscode.postMessage({
      type: 'applyFilePatch',
      file,
      patch
    });

    addSystemMessage(`Applying changes to ${file}...`);
  }, [addSystemMessage]);

  const handleCancelRefactor = useCallback(() => {
    vscode.postMessage({ type: 'cancelRefactor' });
    setIsRefactoring(false);
    setProgressSteps([]);
    setDiffs([]);
    setPatchBundle(null);
    addSystemMessage('Refactor cancelled by user');
  }, [addSystemMessage]);

  const exportChat = useCallback(() => {
    const chatData = {
      messages,
      timestamp: new Date().toISOString(),
      version: '1.0'
    };

    vscode.postMessage({
      type: 'export-chat',
      data: chatData
    });
  }, [messages]);

  // Memoized values
  const messageCount = messages.length;
  const hasMessages = messageCount > 0;
  const canSend = inputValue.trim().length > 0 && !isStreaming;

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      {/* Header with controls */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center space-x-3">
          <h2 className="text-lg font-semibold">Navi Chat</h2>
          <ConnectionStatus status={connectionStatus} />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400">{messageCount} messages</span>
          {hasMessages && (
            <>
              <button
                onClick={exportChat}
                className="p-1 text-gray-400 hover:text-white transition-colors"
                title="Export chat (⌘E)"
              >
                📤
              </button>
              <button
                onClick={clearChat}
                className="p-1 text-gray-400 hover:text-red-400 transition-colors"
                title="Clear chat"
              >
                🗑️
              </button>
            </>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 scroll-smooth">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center">
            <div className="max-w-md">
              <div className="text-6xl mb-4">🤖</div>
              <h3 className="text-xl font-semibold mb-2">Welcome to Navi</h3>
              <p className="text-gray-400 mb-4">
                I'm your autonomous engineering assistant. Ask me about your code,
                start a review, or request automated fixes.
              </p>
              <div className="text-sm text-gray-500">
                <p>Try: "Review my recent changes" or "Fix console logs"</p>
                <p className="mt-1">⌘K to focus, ⌘Enter to start review</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onSuggestionClick={handleSuggestionClick}
                onFileClick={handleFileClick}
              />
            ))}
            {isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Streaming Refactor UI */}
      {enableStreaming && (isRefactoring || patchBundle || diffs.length > 0) && (
        <div className="border-t border-gray-700 bg-gray-850 p-4 space-y-4">
          {/* Progress Timeline */}
          {progressSteps.length > 0 && (
            <ProgressTimeline
              steps={progressSteps}
              currentFile={currentFile}
              className="max-h-48 overflow-y-auto"
            />
          )}

          {/* Live Diffs */}
          {diffs.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-semibold text-white flex items-center">
                📝 File Changes ({diffs.length})
              </h4>
              {diffs.map((diff, index) => (
                <DiffViewer
                  key={diff.file}
                  hunk={diff.diff_content ?? diff.diff}
                  fileName={diff.file}
                  className="bg-gray-800 border-gray-600"
                />
              ))}
            </div>
          )}

          {/* Patch Bundle */}
          {patchBundle && (
            <DiffApplyPanel
              patchBundle={patchBundle}
              onApplyAll={(bundle: any) => {
                vscode.postMessage({
                  type: 'applyAll',
                  payload: bundle
                });
              }}
              onApplyFile={(filePath: string, content: string) => {
                vscode.postMessage({
                  type: 'applyFile',
                  payload: { filePath, content }
                });
              }}
              onUndo={() => {
                vscode.postMessage({ type: 'undo' });
              }}
            />
          )}

          {/* Refactor Controls */}
          {isRefactoring && (
            <div className="flex items-center justify-between bg-blue-900 border border-blue-600 rounded p-3">
              <div className="flex items-center space-x-2">
                <div className="animate-spin w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" />
                <span className="text-blue-200">Autonomous refactor in progress...</span>
                {currentFile && (
                  <span className="text-xs font-mono text-blue-300 bg-blue-800 px-2 py-1 rounded">
                    {currentFile}
                  </span>
                )}
              </div>

              <button
                onClick={() => {
                  vscode.postMessage({ type: 'cancelRefactor' });
                  setIsRefactoring(false);
                }}
                className="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 transition-colors text-sm"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {/* Input area */}
      <div className="p-4 border-t border-gray-700 bg-gray-800">
        {/* Selected files */}
        {selectedFiles.length > 0 && (
          <div className="mb-2 p-2 bg-gray-700 rounded">
            <div className="text-xs text-gray-400 mb-1">Attached files:</div>
            <div className="flex flex-wrap gap-1">
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="flex items-center space-x-1 px-2 py-1 bg-gray-600 rounded text-xs">
                  <span>📎 {file.split('/').pop()}</span>
                  <button
                    onClick={() => setSelectedFiles(prev => prev.filter((_, i) => i !== idx))}
                    className="text-gray-400 hover:text-white"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Input row */}
        <div className="flex items-end space-x-2">
          {allowFileUploads && (
            <button
              onClick={handleFileSelect}
              className="p-2 text-gray-400 hover:text-white transition-colors"
              title="Attach files"
            >
              📎
            </button>
          )}

          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Navi anything... (Enter to send, Shift+Enter for new line)"
              className="w-full px-3 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 
                       focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500
                       resize-none min-h-[40px] max-h-32"
              rows={1}
              style={{
                height: 'auto',
                minHeight: '40px',
                maxHeight: '128px'
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = Math.min(target.scrollHeight, 128) + 'px';
              }}
              disabled={isStreaming}
            />
          </div>

          <button
            onClick={handleSendMessage}
            disabled={!canSend}
            className={`px-4 py-2 rounded-lg font-medium transition-all duration-200
              ${canSend
                ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl'
                : 'bg-gray-600 text-gray-400 cursor-not-allowed'}
            `}
            title="Send message (Enter)"
          >
            {isStreaming ? '⏹️' : '📤'}
          </button>
        </div>

        {/* Action buttons */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700">
          <div className="flex space-x-2">
            <button
              onClick={onStartReview}
              disabled={isStreaming}
              className={`px-4 py-2 rounded-lg font-medium transition-all duration-200
                ${!isStreaming
                  ? 'bg-green-600 hover:bg-green-700 text-white shadow-md hover:shadow-lg'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'}
              `}
              title="Start code review (⌘Enter)"
            >
              🔍 Start Review
            </button>

            {onAutoFix && (
              <button
                onClick={() => onAutoFix('', '')}
                disabled={isStreaming || isFixing}
                className={`px-4 py-2 rounded-lg font-medium transition-all duration-200
                  ${!isStreaming && !isFixing
                    ? 'bg-orange-600 hover:bg-orange-700 text-white shadow-md hover:shadow-lg'
                    : 'bg-gray-600 text-gray-400 cursor-not-allowed'}
                `}
                title="Auto-fix issues"
              >
                {isFixing ? '⏳' : '🔧'} Auto Fix
              </button>
            )}

            {/* Smart Mode Buttons */}
            <button
              onClick={() => vscode.postMessage({
                type: 'runOrchestrator',
                instruction: 'Review my code and suggest improvements'
              })}
              disabled={isStreaming || isFixing}
              className={`px-3 py-2 rounded-lg font-medium transition-all duration-200
                ${!isStreaming && !isFixing
                  ? 'bg-purple-600 hover:bg-purple-700 text-white shadow-md hover:shadow-lg'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'}
              `}
              title="AI Orchestrator: Intelligent code review with real backend analysis"
            >
              🚀 Smart Workspace
            </button>

            <button
              onClick={() => vscode.postMessage({ type: 'smartMode.reviewSelection' })}
              disabled={isStreaming || isFixing}
              className={`px-3 py-2 rounded-lg font-medium transition-all duration-200
                ${!isStreaming && !isFixing
                  ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'}
              `}
              title="Smart Mode: Analyze current selection with intelligent routing"
            >
              🎯 Smart Selection
            </button>
          </div>

          <div className="text-xs text-gray-500">
            {isStreaming && 'Streaming response...'}
            {isFixing && `Fixing... ${fixProgress?.overallProgress ?? 0}%`}
            {streamError?.message && `Error: ${streamError.message}`}
            {fixErrorMessage && `Fix error: ${fixErrorMessage}`}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NaviChatPanel;
