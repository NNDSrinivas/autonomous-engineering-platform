"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const react_1 = require("react");
require("./NaviPanel.css");
const NaviPanel = () => {
    // State management
    const [messages, setMessages] = (0, react_1.useState)([]);
    const [inputValue, setInputValue] = (0, react_1.useState)('');
    const [attachments, setAttachments] = (0, react_1.useState)([]);
    const [isAttachMenuOpen, setIsAttachMenuOpen] = (0, react_1.useState)(false);
    const [isActionsMenuOpen, setIsActionsMenuOpen] = (0, react_1.useState)(false);
    const [selectedModel, setSelectedModel] = (0, react_1.useState)('smart-auto');
    const [selectedMode, setSelectedMode] = (0, react_1.useState)('chat');
    const [isModelMenuOpen, setIsModelMenuOpen] = (0, react_1.useState)(false);
    const [isModeMenuOpen, setIsModeMenuOpen] = (0, react_1.useState)(false);
    // Refs
    const vscodeRef = (0, react_1.useRef)(null);
    const messagesEndRef = (0, react_1.useRef)(null);
    const attachMenuRef = (0, react_1.useRef)(null);
    const actionsMenuRef = (0, react_1.useRef)(null);
    // Initialize VS Code API
    (0, react_1.useEffect)(() => {
        try {
            vscodeRef.current = window.acquireVsCodeApi();
            window.vscode = vscodeRef.current;
        }
        catch (error) {
            console.error('[NAVI] Failed to acquire VS Code API:', error);
        }
        // Message listener for extension communication
        const handleMessage = (event) => {
            const message = event.data;
            switch (message.type) {
                case 'attachmentsUpdated':
                    setAttachments(message.attachments || []);
                    break;
                case 'naviResponse':
                    if (message.response) {
                        setMessages(prev => [...prev, {
                                type: 'assistant',
                                content: message.response,
                                timestamp: Date.now()
                            }]);
                    }
                    break;
                default:
                    break;
            }
        };
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, []);
    // Auto-scroll to bottom on new messages
    (0, react_1.useEffect)(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);
    // Close menus when clicking outside
    (0, react_1.useEffect)(() => {
        const handleClickOutside = (event) => {
            if (attachMenuRef.current && !attachMenuRef.current.contains(event.target)) {
                setIsAttachMenuOpen(false);
            }
            if (actionsMenuRef.current && !actionsMenuRef.current.contains(event.target)) {
                setIsActionsMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);
    // Helper functions
    const postMessage = (0, react_1.useCallback)((message) => {
        if (vscodeRef.current) {
            vscodeRef.current.postMessage(message);
        }
    }, []);
    const getFileExtension = (filePath) => {
        return filePath.split('.').pop()?.toLowerCase() || '';
    };
    const getLanguageFromExtension = (ext) => {
        const languageMap = {
            'ts': 'typescript', 'tsx': 'typescript',
            'js': 'javascript', 'jsx': 'javascript',
            'py': 'python', 'java': 'java',
            'cpp': 'cpp', 'c': 'c',
            'cs': 'csharp', 'go': 'go',
            'rs': 'rust', 'rb': 'ruby',
            'php': 'php', 'kt': 'kotlin',
            'swift': 'swift', 'html': 'html',
            'css': 'css', 'scss': 'scss',
            'json': 'json', 'xml': 'xml',
            'md': 'markdown', 'yml': 'yaml', 'yaml': 'yaml'
        };
        return languageMap[ext] || 'text';
    };
    const truncateContent = (content, maxLines = 5) => {
        const lines = content.split('\n');
        const hasMore = lines.length > maxLines;
        const preview = lines.slice(0, maxLines).join('\n') + (hasMore ? '\n...' : '');
        return { preview, hasMore };
    };
    // Event handlers
    const handleSubmit = (e) => {
        e.preventDefault();
        if (!inputValue.trim())
            return;
        const userMessage = {
            type: 'user',
            content: inputValue,
            attachments: [...attachments],
            timestamp: Date.now()
        };
        setMessages(prev => [...prev, userMessage]);
        // Send to backend via extension
        postMessage({
            type: 'aep.navi.send',
            text: inputValue,
            attachments: attachments,
            model: selectedModel,
            mode: selectedMode
        });
        setInputValue('');
    };
    const handleAttachmentAction = (action) => {
        setIsAttachMenuOpen(false);
        switch (action) {
            case 'selection':
                postMessage({ type: 'requestAttachSelection' });
                break;
            case 'current-file':
                postMessage({ type: 'requestAttachFile' });
                break;
            case 'pick-file':
                postMessage({ type: 'requestPickFile' });
                break;
        }
    };
    const removeAttachment = (attachmentId) => {
        postMessage({ type: 'removeAttachment', attachmentId });
    };
    const handleQuickAction = (actionId) => {
        setIsActionsMenuOpen(false);
        const actionPrompts = {
            'explain': 'Explain this code',
            'fix': 'Fix any bugs or issues in this code',
            'optimize': 'Optimize this code for better performance',
            'add-tests': 'Generate unit tests for this code',
            'review-diff': 'Review this code for bugs, code smells, and style issues',
            'document-code': 'Add comments and documentation to this code'
        };
        const prompt = actionPrompts[actionId];
        if (prompt) {
            setInputValue(prompt);
        }
    };
    // Model configuration
    const models = [
        { id: 'smart-auto', label: 'Smart Auto (recommended)' },
        { id: 'openai:gpt-4o', label: 'GPT-4o (OpenAI)' },
        { id: 'openai:gpt-4o-mini', label: 'GPT-4o Mini (OpenAI)' },
        { id: 'anthropic:claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
        { id: 'anthropic:claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
        { id: 'google:gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash' }
    ];
    const modes = [
        { id: 'chat', label: 'Chat' },
        { id: 'auto', label: 'Auto' },
        { id: 'semi-auto', label: 'Semi-auto' }
    ];
    const currentModel = models.find(m => m.id === selectedModel) || models[0];
    const currentMode = modes.find(m => m.id === selectedMode) || modes[0];
    return (<div className="navi-panel">
      {/* Header */}
      <header className="navi-header">
        <div className="navi-logo-container">
          <svg className="navi-logo-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="foxGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#818cf8"/>
                <stop offset="100%" stopColor="#6366f1"/>
              </linearGradient>
            </defs>
            <circle cx="50" cy="50" r="45" fill="url(#foxGradient)"/>
            <path d="M30 35 Q50 25 70 35 Q65 45 50 50 Q35 45 30 35 Z" fill="white"/>
            <circle cx="42" cy="40" r="3" fill="#1f2937"/>
            <circle cx="58" cy="40" r="3" fill="#1f2937"/>
            <path d="M45 50 Q50 55 55 50" stroke="white" strokeWidth="2" fill="none"/>
          </svg>
        </div>
        <div className="navi-title">
          <h1>NAVI</h1>
          <span>Autonomous Engineering Platform</span>
        </div>
      </header>

      {/* Messages */}
      <main className="navi-main">
        <div className="navi-messages">
          {messages.map((message, index) => (<div key={index} className={`navi-message ${message.type === 'user' ? 'navi-message-user' : 'navi-message-assistant'}`}>
              <div className="navi-message-content">
                {message.content}
              </div>
              {message.attachments && message.attachments.length > 0 && (<div className="navi-message-attachments">
                  {message.attachments.map((attachment) => {
                    const filename = attachment.filePath.split(/[\\\/]/).pop() || attachment.filePath;
                    const ext = getFileExtension(attachment.filePath);
                    const language = getLanguageFromExtension(ext);
                    const { preview, hasMore } = truncateContent(attachment.content);
                    return (<div key={attachment.id} className="navi-message-attachment">
                        <div className="navi-message-attachment-header">
                          <span className="navi-message-attachment-kind">
                            {attachment.kind === 'selection' ? '📝' : '📁'} {filename}
                          </span>
                          {attachment.startLine && attachment.endLine && (<span className="navi-message-attachment-lines">
                              Lines {attachment.startLine}-{attachment.endLine}
                            </span>)}
                        </div>
                        <pre className={`navi-message-attachment-code language-${language}`}>
                          <code>{preview}</code>
                        </pre>
                      </div>);
                })}
                </div>)}
            </div>))}
          <div ref={messagesEndRef}/>
        </div>
      </main>

      {/* Footer */}
      <footer className="navi-footer">
        {/* Attachments Container */}
        {attachments.length > 0 && (<div className="navi-attachments-container">
            {attachments.map((attachment) => {
                const filename = attachment.filePath.split(/[\\\/]/).pop() || attachment.filePath;
                const ext = getFileExtension(attachment.filePath);
                const language = getLanguageFromExtension(ext);
                const { preview, hasMore } = truncateContent(attachment.content);
                const lineCount = attachment.content.split('\n').length;
                return (<div key={attachment.id} className="navi-attachment-pill">
                  <div className="navi-attachment-header">
                    <span className="navi-attachment-kind">
                      {attachment.kind === 'selection' ? '📝 Selected code' : '📁 File'}
                    </span>
                    <span className="navi-attachment-info">
                      {filename} · {lineCount} line{lineCount !== 1 ? 's' : ''}
                    </span>
                    <button className="navi-attachment-remove" onClick={() => removeAttachment(attachment.id)} title="Remove attachment">
                      ✕
                    </button>
                  </div>
                  <div className="navi-attachment-content">
                    <pre className={`navi-attachment-code language-${language}`}>
                      <code>{preview}</code>
                    </pre>
                  </div>
                </div>);
            })}
          </div>)}

        {/* Input Form */}
        <form className="navi-form" onSubmit={handleSubmit}>
          {/* Attachment Button */}
          <div className="navi-input-group">
            <div className="navi-button-group">
              <button type="button" className="navi-icon-btn navi-attach-btn" onClick={() => setIsAttachMenuOpen(!isAttachMenuOpen)} title="Attach files or code">
                +
              </button>
              
              {/* Attachment Menu */}
              {isAttachMenuOpen && (<div ref={attachMenuRef} className="navi-menu navi-attach-menu">
                  <button className="navi-menu-item" onClick={() => handleAttachmentAction('selection')}>
                    📝 Attach Selection
                  </button>
                  <button className="navi-menu-item" onClick={() => handleAttachmentAction('current-file')}>
                    📁 Attach Current File
                  </button>
                  <button className="navi-menu-item" onClick={() => handleAttachmentAction('pick-file')}>
                    🔍 Pick File…
                  </button>
                </div>)}

              {/* Actions Button */}
              <button type="button" className="navi-icon-btn navi-actions-btn" onClick={() => setIsActionsMenuOpen(!isActionsMenuOpen)} title="Quick actions">
                ✨
              </button>

              {/* Actions Menu */}
              {isActionsMenuOpen && (<div ref={actionsMenuRef} className="navi-menu navi-actions-menu">
                  <button className="navi-menu-item" onClick={() => handleQuickAction('explain')}>
                    <div className="navi-menu-item-content">
                      <div className="navi-menu-item-title">Explain</div>
                      <div className="navi-menu-item-subtitle">Break down how the code works</div>
                    </div>
                  </button>
                  <button className="navi-menu-item" onClick={() => handleQuickAction('fix')}>
                    <div className="navi-menu-item-content">
                      <div className="navi-menu-item-title">Fix</div>
                      <div className="navi-menu-item-subtitle">Suggest improvements and bug fixes</div>
                    </div>
                  </button>
                  <button className="navi-menu-item" onClick={() => handleQuickAction('optimize')}>
                    <div className="navi-menu-item-content">
                      <div className="navi-menu-item-title">Optimize</div>
                      <div className="navi-menu-item-subtitle">Improve performance and efficiency</div>
                    </div>
                  </button>
                  <button className="navi-menu-item" onClick={() => handleQuickAction('add-tests')}>
                    <div className="navi-menu-item-content">
                      <div className="navi-menu-item-title">Generate tests</div>
                      <div className="navi-menu-item-subtitle">Unit tests for the selected code</div>
                    </div>
                  </button>
                  <button className="navi-menu-item" onClick={() => handleQuickAction('review-diff')}>
                    <div className="navi-menu-item-content">
                      <div className="navi-menu-item-title">Code review</div>
                      <div className="navi-menu-item-subtitle">Bugs, smells, and style issues</div>
                    </div>
                  </button>
                  <button className="navi-menu-item" onClick={() => handleQuickAction('document-code')}>
                    <div className="navi-menu-item-content">
                      <div className="navi-menu-item-title">Document this code</div>
                      <div className="navi-menu-item-subtitle">Comments and docstrings</div>
                    </div>
                  </button>
                </div>)}
            </div>

            <input className="navi-input" type="text" value={inputValue} onChange={(e) => setInputValue(e.target.value)} placeholder="Ask NAVI anything…" autoComplete="off"/>

            <button type="submit" className="navi-send-btn" title="Send">
              ➤
            </button>
          </div>
        </form>

        {/* Model and Mode Pills */}
        <div className="navi-bottom-row">
          {/* Model Pill */}
          <div className="navi-pill-container">
            <button className="navi-pill navi-model-pill" onClick={() => setIsModelMenuOpen(!isModelMenuOpen)}>
              Model: {currentModel.label}
            </button>
            {isModelMenuOpen && (<div className="navi-pill-menu navi-model-menu">
                {models.map((model) => (<button key={model.id} className={`navi-pill-menu-item ${selectedModel === model.id ? 'active' : ''}`} onClick={() => {
                    setSelectedModel(model.id);
                    setIsModelMenuOpen(false);
                }}>
                    {model.label}
                  </button>))}
              </div>)}
          </div>

          {/* Mode Pill */}
          <div className="navi-pill-container">
            <button className="navi-pill navi-mode-pill" onClick={() => setIsModeMenuOpen(!isModeMenuOpen)}>
              Mode: {currentMode.label}
            </button>
            {isModeMenuOpen && (<div className="navi-pill-menu navi-mode-menu">
                {modes.map((mode) => (<button key={mode.id} className={`navi-pill-menu-item ${selectedMode === mode.id ? 'active' : ''}`} onClick={() => {
                    setSelectedMode(mode.id);
                    setIsModeMenuOpen(false);
                }}>
                    {mode.label}
                  </button>))}
              </div>)}
          </div>
        </div>
      </footer>
    </div>);
};
exports.default = NaviPanel;
//# sourceMappingURL=NaviPanel.js.map