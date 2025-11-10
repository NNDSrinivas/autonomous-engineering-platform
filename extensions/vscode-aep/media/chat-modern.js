/**
 * Modern AEP Extension UI Framework
 * Professional chat interface with typing indicators, code highlighting, and state management
 */

class AEPChatUI {
  constructor() {
    this.vscode = acquireVsCodeApi();
    this.messages = [];
    this.isTyping = false;
    this.messageId = 0;
    
    this.initializeUI();
    this.setupEventListeners();
    this.restoreState();
  }

  initializeUI() {
    // Add message handling for data from extension
    window.addEventListener('message', (event) => {
      const message = event.data;
      switch (message.type) {
        case 'chatMessage':
          this.addMessage(message.role, message.content, message.timestamp);
          break;
        case 'typing':
          this.setTyping(message.isTyping);
          break;
        case 'error':
          this.showError(message.message);
          break;
        case 'connectionStatus':
          this.updateConnectionStatus(message.connected);
          break;
      }
    });
  }

  setupEventListeners() {
    // Chat input handling
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSend');
    
    if (chatInput && sendBtn) {
      // Auto-resize textarea
      chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
      });

      // Send on Enter (but not Shift+Enter)
      chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });

      sendBtn.addEventListener('click', () => this.sendMessage());
    }

    // Handle all button clicks with data-command
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-command]');
      if (btn) {
        const command = btn.dataset.command;
        const data = this.extractButtonData(btn);
        this.executeCommand(command, data);
      }
    });

    // Handle external links
    document.addEventListener('click', (e) => {
      const link = e.target.closest('[data-url]');
      if (link && link.dataset.url) {
        this.vscode.postMessage({
          type: 'openExternal',
          url: link.dataset.url
        });
      }
    });
  }

  sendMessage() {
    const input = document.getElementById('chatInput');
    if (!input || !input.value.trim()) return;

    const message = input.value.trim();
    input.value = '';
    input.style.height = 'auto';

    // Add user message immediately
    this.addMessage('user', message);
    
    // Show typing indicator
    this.setTyping(true);

    // Send to extension
    this.vscode.postMessage({
      type: 'chat',
      message: message
    });

    // Update send button state
    this.updateSendButton(false);
  }

  addMessage(role, content, timestamp) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    // Remove typing indicator if present
    this.removeTypingIndicator();

    const messageId = ++this.messageId;
    const message = {
      id: messageId,
      role,
      content,
      timestamp: timestamp || new Date().toLocaleTimeString()
    };

    this.messages.push(message);
    
    const messageEl = this.createMessageElement(message);
    messagesContainer.appendChild(messageEl);
    
    // Scroll to bottom smoothly
    setTimeout(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);

    // Save state
    this.saveState();
  }

  createMessageElement(message) {
    const div = document.createElement('div');
    div.className = `aep-chat__message aep-chat__message--${message.role}`;
    div.dataset.messageId = message.id;

    const bubble = document.createElement('div');
    bubble.className = 'aep-chat__message-bubble';
    
    // Process content for code blocks and formatting
    bubble.innerHTML = this.processMessageContent(message.content);

    const meta = document.createElement('div');
    meta.className = 'aep-chat__message-meta';
    meta.textContent = `${this.getRoleDisplayName(message.role)} • ${message.timestamp}`;

    div.appendChild(bubble);
    div.appendChild(meta);

    return div;
  }

  processMessageContent(content) {
    // Escape HTML first
    let processed = this.escapeHtml(content);

    // Process code blocks (```...```)
    processed = processed.replace(/```(\w+)?\n?([\s\S]*?)```/g, (match, lang, code) => {
      const language = lang || 'text';
      return `<div class="aep-code aep-code--block">
        <div class="aep-code__header">
          <span class="aep-code__lang">${language}</span>
          <button class="aep-btn aep-btn--ghost aep-btn--sm" onclick="this.copyCode(this)" title="Copy code">
            <span class="codicon codicon-copy"></span>
          </button>
        </div>
        <pre><code>${code.trim()}</code></pre>
      </div>`;
    });

    // Process inline code (`...`)
    processed = processed.replace(/`([^`]+)`/g, '<code class="aep-code aep-code--inline">$1</code>');

    // Process bold text (**...** or __...__)
    processed = processed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    processed = processed.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Process italic text (*...* or _..._)
    processed = processed.replace(/\*(.*?)\*/g, '<em>$1</em>');
    processed = processed.replace(/_(.*?)_/g, '<em>$1</em>');

    // Process line breaks
    processed = processed.replace(/\n/g, '<br>');

    return processed;
  }

  setTyping(isTyping) {
    this.isTyping = isTyping;
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    this.removeTypingIndicator();

    if (isTyping) {
      const typingEl = this.createTypingIndicator();
      messagesContainer.appendChild(typingEl);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    this.updateSendButton(!isTyping);
  }

  createTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'aep-chat__message aep-chat__message--assistant aep-typing-indicator';

    const bubble = document.createElement('div');
    bubble.className = 'aep-chat__message-bubble';
    bubble.innerHTML = `
      <div class="aep-typing-dots">
        <span class="aep-typing-dot"></span>
        <span class="aep-typing-dot"></span>
        <span class="aep-typing-dot"></span>
      </div>
      <span class="aep-text--sm aep-text--muted">AEP is thinking...</span>
    `;

    div.appendChild(bubble);
    return div;
  }

  removeTypingIndicator() {
    const indicator = document.querySelector('.aep-typing-indicator');
    if (indicator) {
      indicator.remove();
    }
  }

  updateSendButton(enabled) {
    const sendBtn = document.getElementById('chatSend');
    if (sendBtn) {
      sendBtn.disabled = !enabled;
      sendBtn.innerHTML = enabled ? 'Send' : '<span class="aep-spinner"></span>';
    }
  }

  updateConnectionStatus(connected) {
    const statusEl = document.querySelector('.aep-connection-status');
    if (statusEl) {
      statusEl.className = `aep-status ${connected ? 'aep-status--online' : 'aep-status--offline'}`;
      statusEl.innerHTML = `
        <span class="aep-status__dot"></span>
        ${connected ? 'Connected' : 'Disconnected'}
      `;
    }
  }

  showError(message) {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = 'aep-toast aep-toast--error';
    toast.innerHTML = `
      <div class="aep-toast__content">
        <strong>Error</strong>
        <p>${this.escapeHtml(message)}</p>
      </div>
      <button class="aep-toast__close" onclick="this.parentElement.remove()">×</button>
    `;

    document.body.appendChild(toast);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 5000);
  }

  executeCommand(command, data = {}) {
    this.vscode.postMessage({
      type: command,
      ...data
    });
  }

  extractButtonData(button) {
    const data = {};
    for (const [key, value] of Object.entries(button.dataset)) {
      if (key !== 'command') {
        data[key] = value;
      }
    }
    return data;
  }

  getRoleDisplayName(role) {
    const names = {
      user: 'You',
      assistant: 'AEP Agent',
      system: 'System'
    };
    return names[role] || role;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  saveState() {
    const state = {
      messages: this.messages,
      timestamp: Date.now()
    };
    this.vscode.setState(state);
  }

  restoreState() {
    const state = this.vscode.getState();
    if (state && state.messages) {
      this.messages = state.messages;
      this.messageId = Math.max(...this.messages.map(m => m.id || 0), 0);
      
      // Restore messages to UI
      const messagesContainer = document.getElementById('chatMessages');
      if (messagesContainer) {
        messagesContainer.innerHTML = '';
        this.messages.forEach(message => {
          const messageEl = this.createMessageElement(message);
          messagesContainer.appendChild(messageEl);
        });
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }
  }

  // Utility method for copying code
  copyCode(button) {
    const codeBlock = button.closest('.aep-code').querySelector('code');
    if (codeBlock) {
      navigator.clipboard.writeText(codeBlock.textContent).then(() => {
        button.innerHTML = '<span class="codicon codicon-check"></span>';
        setTimeout(() => {
          button.innerHTML = '<span class="codicon codicon-copy"></span>';
        }, 2000);
      });
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.aepUI = new AEPChatUI();
});

// Add CSS for typing indicator and toasts
const additionalCSS = `
.aep-typing-dots {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.aep-typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--vscode-descriptionForeground);
  animation: typingPulse 1.4s infinite ease-in-out;
}

.aep-typing-dot:nth-child(1) { animation-delay: -0.32s; }
.aep-typing-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes typingPulse {
  0%, 80%, 100% { 
    opacity: 0.3;
    transform: scale(0.8);
  }
  40% { 
    opacity: 1;
    transform: scale(1);
  }
}

.aep-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  background: var(--vscode-notifications-background);
  border: 1px solid var(--vscode-notifications-border);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  max-width: 400px;
  box-shadow: var(--shadow-lg);
  animation: toastSlideIn var(--transition-normal) ease;
  z-index: 1000;
}

.aep-toast--error {
  border-left: 4px solid var(--aep-error);
}

.aep-toast__content strong {
  display: block;
  margin-bottom: var(--space-xs);
  color: var(--vscode-foreground);
}

.aep-toast__content p {
  margin: 0;
  color: var(--vscode-descriptionForeground);
  font-size: 12px;
}

.aep-toast__close {
  position: absolute;
  top: 8px;
  right: 8px;
  background: none;
  border: none;
  color: var(--vscode-descriptionForeground);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

@keyframes toastSlideIn {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.aep-code__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid var(--glass-border);
  font-size: 11px;
}

.aep-code__lang {
  color: var(--vscode-descriptionForeground);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
`;

// Inject additional CSS
const style = document.createElement('style');
style.textContent = additionalCSS;
document.head.appendChild(style);