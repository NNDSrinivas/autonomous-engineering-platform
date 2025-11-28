// media/panel.js
// NAVI chat panel with streaming + quick actions + message toolbar

// ---------------------------------------------------------------------------
// Shared state for menus (unified to prevent overlapping)
// ---------------------------------------------------------------------------
let commandMenuEl = null;
let openMenu = null; // 'actions' | 'attach' | null
let commandMenuHasUserPosition = false;
let commandMenuDragState = {
  dragging: false,
  offsetX: 0,
  offsetY: 0,
};

// --- Attachments state -------------------------------------------------------
let currentAttachments = [];

// --- Ephemeral toast (short-lived banner above input) ------------------------

let naviToastTimeoutId = null;

function showEphemeralToast(message, level = 'info') {
  // Try to anchor near the chat input, fall back to body
  const root =
    document.querySelector('.aep-chat-input-row') ||
    document.getElementById('root') ||
    document.body;

  let el = document.getElementById('navi-ephemeral-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'navi-ephemeral-toast';
    el.className = 'navi-ephemeral-toast';
    root.appendChild(el);
  }

  el.textContent = message;
  el.setAttribute('data-level', level);

  el.classList.add('visible');

  if (naviToastTimeoutId) {
    clearTimeout(naviToastTimeoutId);
  }

  naviToastTimeoutId = setTimeout(() => {
    el.classList.remove('visible');
  }, 3500); // 3.5s then fade
}



// ---------------------------------------------------------------------------
// Main webview bootstrap (UI + streaming + basic wiring)
// ---------------------------------------------------------------------------
(function () {
  const vscode = (() => {
    try {
      const api = acquireVsCodeApi();
      if (typeof window !== 'undefined') {
        window.vscode = api;
      }
      return api;
    } catch (err) {
      console.error('[NAVI] Failed to acquire VS Code API:', err);
      return null;
    }
  })();

  // NAVI Intent Classification functionality
  function getSelectedModel() {
    const modelSelect = document.getElementById('navi-model-select');
    if (!modelSelect) {
      return 'smart-auto';
    }
    return modelSelect.value || 'smart-auto';
  }

  function sendIntentClassification(text) {
    if (!text.trim() || !vscode) return;

    vscode.postMessage({
      type: 'aep.intent.classify',
      text: text,
      model: getSelectedModel()
    });
  }

  function displayIntentResult(message) {
    const intentResultEl = document.getElementById('navi-intent-result');
    if (!intentResultEl) return;

    if (!message.ok) {
      intentResultEl.innerHTML = `❌ Intent error: ${message.error || 'Unknown error'}`;
      intentResultEl.className = 'navi-intent-pill show';
      return;
    }

    const data = message.data || {};
    const intent = data.intent || {};

    const family = intent.family || 'UNKNOWN';
    const kind = intent.kind || 'UNKNOWN';
    const confidence = intent.confidence || 0;
    const modelUsed = intent.model_used || intent.provider_used || 'smart-auto';

    intentResultEl.innerHTML =
      `🧠 <strong>${family}</strong> / ${kind} ` +
      `(${Math.round(confidence * 100)}% confidence) · model: <code>${modelUsed}</code>`;
    intentResultEl.className = 'navi-intent-pill show';
  }

  const root = document.getElementById('root');

  const state = {
    streamingMessageId: null,
    streamingBubble: null,
    streamingText: '',
    thinking: false,
  };

  // Track which message bubble is being edited (null = not editing)
  let editingMessageBubble = null;

  let thinkingMessageEl = null;

  // HTML escaping function to prevent XSS
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function showThinkingMessage() {
    const messagesEl = document.getElementById('navi-messages');
    if (!messagesEl) return;

    hideThinkingMessage();

    const bubble = document.createElement('div');
    bubble.className = 'navi-message-thinking';
    bubble.dataset.kind = 'thinking';
    bubble.textContent = 'NAVI is thinking...';

    messagesEl.appendChild(bubble);
    thinkingMessageEl = bubble;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideThinkingMessage() {
    if (thinkingMessageEl && thinkingMessageEl.parentElement) {
      thinkingMessageEl.parentElement.removeChild(thinkingMessageEl);
    }
    thinkingMessageEl = null;
  }

  // Build UI -----------------------------------------------------------------
  root.innerHTML = `
    <div class="navi-shell">
      <header class="navi-header">
        <div class="navi-brand">
          <div class="navi-logo-container">
            <svg class="navi-logo-svg" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" aria-label="NAVI fox">
              <defs>
                <linearGradient id="naviFoxGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#FF8A3D"/>
                  <stop offset="100%" stop-color="#FF5E7E"/>
                </linearGradient>
              </defs>

              <circle cx="22" cy="22" r="20" fill="#020617"/>

              <g transform="translate(33,29)">
                <path d="M0 0 C7 0 9 7 3 10 C-1 12 -2 7 0 0 Z" fill="url(#naviFoxGrad)" opacity="0.85"/>
              </g>

              <g>
                <path d="M22 5 L36 16 33 34 22 39 11 34 8 16Z" fill="url(#naviFoxGrad)"/>

                <g transform="translate(12,14)">
                  <path d="M0 3 L6 -1 4 6 Z" fill="#fff" opacity="0.95"/>
                </g>
                <g transform="translate(26,14)">
                  <path d="M6 3 L0 -1 2 6 Z" fill="#fff" opacity="0.95"/>
                </g>

                <ellipse cx="18" cy="24" rx="1.6" ry="1.6" fill="#0F172A"/>
                <ellipse cx="26" cy="24" rx="1.6" ry="1.6" fill="#0F172A"/>
                <rect x="20.3" y="26.5" width="3.4" height="1.2" rx="0.6" fill="#0F172A" opacity="0.75"/>
              </g>
            </svg>
          </div>
          <div class="navi-title-block">
            <div class="navi-title">NAVI — Autonomous Engineering Assistant</div>
            <div class="navi-subtitle">Your AI engineering copilot inside VS Code</div>
          </div>
        </div>
        <div class="navi-header-actions">
          <button class="navi-icon-btn" data-action="newChat" title="Start a fresh chat">
            <span class="navi-icon-main">+</span>
          </button>
          <button class="navi-icon-btn" data-action="connectors" title="Connect tools & MCP servers">
            <span class="navi-icon-main">🔌</span>
          </button>
          <button class="navi-icon-btn" data-action="settings" title="Settings">
            <span class="navi-icon-main">⚙︎</span>
          </button>
        </div>
      </header>

      <main class="navi-main">
        <div id="navi-messages" class="navi-messages"></div>
        <div id="navi-jira-tasks" class="navi-jira-tasks navi-jira-tasks-hidden"></div>
      </main>
      
      <!-- Connectors Marketplace Modal -->
      <div id="aep-connectors-root" class="aep-connectors-root" hidden></div>

      <footer class="navi-footer">
        <div class="navi-attach-toast">
          <span class="navi-attach-toast-icon">📎</span>
          <span class="navi-attach-toast-text">Attachment flow is not implemented yet – coming soon.</span>
        </div>

        <div id="navi-attachments-container" class="navi-attachments-container">
          <!-- Attachment pills will be dynamically added here -->
        </div>

        <form id="navi-form" class="navi-form">
          <button type="button" id="navi-attach-btn" class="navi-icon-btn navi-attach-btn" title="Attach files or code">
            +
          </button>
          <button type="button" id="navi-actions-btn" class="navi-icon-btn navi-actions-btn" title="Quick actions">
            ✨
          </button>
          <input
            id="navi-input"
            class="navi-input"
            type="text"
            autocomplete="off"
            placeholder="Ask NAVI anything…"
          />
          <button type="submit" class="navi-send-btn" title="Send">
            <span>➤</span>
          </button>
        </form>

        <div class="navi-bottom-row">
          <div class="navi-model-pill navi-pill" id="modelPill" data-model-id="smart-auto">
            <span>Model: Smart Auto (recommended)</span>
            <div class="navi-pill-menu navi-model-menu">
              <div class="navi-pill-menu-item" data-model-id="smart-auto" data-model-label="Smart Auto (recommended)">Smart Auto (recommended)</div>
              <div class="navi-pill-menu-item" data-model-id="openai:gpt-4o" data-model-label="GPT-4o (OpenAI)">GPT-4o (OpenAI)</div>
              <div class="navi-pill-menu-item" data-model-id="openai:gpt-4o-mini" data-model-label="GPT-4o Mini (OpenAI)">GPT-4o Mini (OpenAI)</div>
              <div class="navi-pill-menu-item" data-model-id="anthropic:claude-3-5-sonnet-20241022" data-model-label="Claude 3.5 Sonnet">Claude 3.5 Sonnet</div>
              <div class="navi-pill-menu-item" data-model-id="anthropic:claude-3-5-haiku-20241022" data-model-label="Claude 3.5 Haiku">Claude 3.5 Haiku</div>
              <div class="navi-pill-menu-item" data-model-id="google:gemini-2.0-flash-exp" data-model-label="Gemini 2.0 Flash">Gemini 2.0 Flash</div>
            </div>
          </div>

          <div class="navi-mode-pill navi-pill" id="modePill" data-mode-id="agent-full">
            <span>Mode: Agent (full access)</span>
            <div class="navi-pill-menu navi-mode-menu">
              <div class="navi-pill-menu-item" data-mode-id="agent-full" data-mode-label="Agent (full access)">Agent (full access)</div>
              <div class="navi-pill-menu-item" data-mode-id="chat-only" data-mode-label="Chat only">Chat only</div>
              <div class="navi-pill-menu-item" data-mode-id="read-only" data-mode-label="Read-only explorer">Read-only explorer</div>
            </div>
          </div>
        </div>



        <div id="navi-intent-result" class="navi-intent-pill">
          <!-- Intent classification results will appear here -->
        </div>

        <div id="navi-command-menu" class="navi-command-menu navi-command-menu-hidden">
          <button class="navi-command-item" data-command-id="jira-task-brief">
            <div class="navi-command-title">Work on a Jira task</div>
            <div class="navi-command-subtitle">Pick a Jira ticket and get a full brief</div>
          </button>
          <button class="navi-command-item" data-command-id="explain-code">
            <div class="navi-command-title">Explain code</div>
            <div class="navi-command-subtitle">High-level and line-by-line explanation</div>
          </button>
          <button class="navi-command-item" data-command-id="refactor-code">
            <div class="navi-command-title">Refactor for readability</div>
            <div class="navi-command-subtitle">Cleaner, more idiomatic version</div>
          </button>
          <button class="navi-command-item" data-command-id="add-tests">
            <div class="navi-command-title">Generate tests</div>
            <div class="navi-command-subtitle">Unit tests for the selected code or function</div>
          </button>
          <button class="navi-command-item" data-command-id="review-diff">
            <div class="navi-command-title">Code review</div>
            <div class="navi-command-subtitle">Bugs, smells, and style issues</div>
          </button>
          <button class="navi-command-item" data-command-id="document-code">
            <div class="navi-command-title">Document this code</div>
            <div class="navi-command-subtitle">Comments and docstrings</div>
          </button>
        </div>

        <div class="navi-attachment-menu">
          <div class="navi-menu-item" data-attach="selection">Attach Selection</div>
          <div class="navi-menu-item" data-attach="current-file">Attach Current File</div>
          <div class="navi-menu-item" data-attach="pick-file">Pick File…</div>
        </div>
      </footer>
    </div>
  `;

  // Fox logo styling ---------------------------------------------------------
  const logoContainer = root.querySelector('.navi-logo-container');
  const logoSvg = root.querySelector('.navi-logo-svg');

  if (logoContainer && logoSvg) {
    logoContainer.style.cssText = `
      width: 34px;
      height: 34px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 18px rgba(129, 140, 248, 0.6);
    `;

    logoSvg.style.cssText = `
      width: 32px;
      height: 32px;
      display: block;
      border-radius: 10px;
    `;

    console.log('[NAVI] Fox logo embedded successfully');
  } else {
    console.warn('[NAVI] Logo container or SVG not found');
  }

  // Add attachment styles
  const attachmentStyles = document.createElement('style');
  attachmentStyles.textContent = `
    .navi-attachments-container {
      margin-bottom: 12px;
      max-height: 280px;
      overflow-y: auto;
    }
    
    .navi-attachment-pill {
      background: rgba(5, 7, 22, 0.95);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 8px 12px;
      margin-bottom: 8px;
    }
    
    .navi-attachment-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
      font-size: 11px;
    }
    
    .navi-attachment-label {
      font-weight: 600;
      color: #F9F5FF;
      white-space: nowrap;
    }
    
    .navi-attachment-path {
      color: #9CA3AF;
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-family: ui-monospace, Menlo, Monaco, 'Courier New', monospace;
    }
    
    .navi-attachment-remove {
      background: transparent;
      border: none;
      color: #9CA3AF;
      cursor: pointer;
      padding: 2px 4px;
      border-radius: 4px;
      font-size: 12px;
      line-height: 1;
    }
    
    .navi-attachment-remove:hover {
      background: rgba(239, 68, 68, 0.1);
      color: #EF4444;
    }
    
    .navi-attachment-content {
      margin: 0;
    }
    
    .navi-attachment-code {
      margin: 0;
      padding: 8px 10px;
      background: rgba(2, 3, 12, 0.8);
      border-radius: 8px;
      font-family: ui-monospace, Menlo, Monaco, 'Courier New', monospace;
      font-size: 11px;
      line-height: 1.4;
      max-height: 120px;
      overflow: auto;
      white-space: pre;
      color: #E5E7EB;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .navi-attachment-code code {
      display: block;
    }
  `;
  document.head.appendChild(attachmentStyles);

  // DOM references -----------------------------------------------------------
  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');
  const attachmentsBanner = document.getElementById('navi-attachments-banner');

  // Markdown rendering (enhanced for PR-3) ------------------------------------
  function renderMarkdown(text) {
    if (!text) return '';

    // First, escape ALL HTML to prevent XSS
    let html = escapeHtml(text);

    // Now apply markdown transformations on the escaped text
    // Code fences ```lang\ncode\n```
    html = html.replace(/```(\w+)?\n?([\s\S]*?)```/g, (match, lang, code) => {
      const safeLang = lang ? ` language-${lang}` : '';
      return `<pre class="navi-code-block"><code class="navi-code-content${safeLang}">${code}</code></pre>`;
    });

    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code class="navi-inline-code">$1</code>');

    // Bold / italic
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Headings
    html = html.replace(/^### (.*)$/gm, '<h3 class="navi-heading-3">$1</h3>');
    html = html.replace(/^## (.*)$/gm, '<h2 class="navi-heading-2">$1</h2>');
    html = html.replace(/^# (.*)$/gm, '<h1 class="navi-heading-1">$1</h1>');

    // Lists (basic support)
    html = html.replace(/^[*-] (.*)$/gm, '<li class="navi-list-item">$1</li>');
    html = html.replace(/(<li.*<\/li>\n?)+/g, (match) => {
      return `<ul class="navi-list">${match}</ul>`;
    });

    // Numbered lists
    html = html.replace(/^\d+\. (.*)$/gm, '<li class="navi-list-item">$1</li>');

    // Blockquotes
    html = html.replace(/^&gt; (.*)$/gm, '<blockquote class="navi-blockquote">$1</blockquote>');

    // Paragraphs (preserve line breaks but create paragraph blocks)
    const blocks = html.split(/\n\n+/);
    html = blocks
      .map((block) => {
        const trimmed = block.trim();
        if (!trimmed) return '';
        // Don't wrap if already a block element
        if (/^<(h[1-3]|pre|ul|ol|blockquote|li)/.test(trimmed)) {
          return trimmed;
        }
        // Convert single line breaks to <br>
        return `<p class="navi-paragraph">${trimmed.replace(/\n/g, '<br>')}</p>`;
      })
      .join('\n');

    return html;
  }

  // Rendering helpers --------------------------------------------------------
  function renderTextSegments(text, container) {
    if (!container) return;

    const safeText = String(text || '');
    if (!safeText.trim()) {
      container.innerHTML = '';
      return;
    }

    // Use markdown rendering for all content
    container.innerHTML = renderMarkdown(safeText);
  }

  // appendMessage with stable toolbar ---------------------------------------
  function appendMessage(text, role, options = {}) {
    const safeText = String(text || '');
    if (!safeText.trim()) {
      console.warn('[NAVI] Ignoring empty message for role:', role);
      return;
    }

    const wrapper = document.createElement('div');
    wrapper.className =
      role === 'user' ? 'navi-msg-row navi-msg-row-user' : 'navi-msg-row navi-msg-row-bot';

    const bubble = document.createElement('div');
    bubble.className =
      role === 'user' ? 'navi-bubble navi-bubble-user' : 'navi-bubble navi-bubble-bot';

    if (options.muted) bubble.classList.add('navi-bubble-muted');

    renderTextSegments(safeText, bubble);

    // --- sources section (for assistant messages) ---
    if (role === 'bot' && options.sources && Array.isArray(options.sources) && options.sources.length > 0) {
      const sourcesEl = document.createElement('div');
      sourcesEl.className = 'message-sources';

      const label = document.createElement('div');
      label.className = 'message-sources-label';
      label.textContent = 'Sources';
      sourcesEl.appendChild(label);

      const list = document.createElement('div');
      list.className = 'message-sources-list';

      options.sources.forEach((src) => {
        if (!src.url) return;

        const link = document.createElement('a');
        link.className = 'message-source-pill';
        link.href = src.url;
        link.target = '_blank';
        link.rel = 'noreferrer';

        const type = (src.type || src.connector || '').toUpperCase();
        const name = src.name || src.url;

        link.textContent = type ? `${type} · ${name}` : name;
        list.appendChild(link);
      });

      sourcesEl.appendChild(list);
      bubble.appendChild(sourcesEl);
    }

    // --- message toolbar (Copy / Edit / Use as prompt) ---
    const toolbar = document.createElement('div');
    toolbar.className = 'navi-msg-toolbar';

    const actions = [
      { id: 'copy', label: 'Copy' },
      { id: 'edit', label: 'Edit' },
      { id: 'use-as-prompt', label: 'Use as prompt' },
    ];

    actions.forEach(({ id, label }) => {
      const btn = document.createElement('button');
      btn.className = 'navi-msg-toolbar-btn';
      btn.textContent = label;
      btn.dataset.action = id;
      // Store the message text in the button's data for easy access
      btn.dataset.messageText = safeText;
      toolbar.appendChild(btn);
    });

    // Add toolbar INSIDE bubble, not wrapper
    bubble.appendChild(toolbar);
    wrapper.appendChild(bubble);

    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    return { wrapper, bubble };
  }

  function clearChat() {
    messagesEl.innerHTML = '';
    state.streamingBubble = null;
    state.streamingMessageId = null;
    state.streamingText = '';
    hideThinkingMessage();
  }

  function setThinking(isThinking) {
    state.thinking = isThinking;
    if (isThinking) {
      showThinkingMessage();
    } else {
      hideThinkingMessage();
    }
  }

  // Attachment state (PR-5)
  let pendingAttachments = [];
  const attachmentsContainer = document.getElementById('navi-attachments-container');

  // Helper function to generate unique attachment ID
  function generateAttachmentId() {
    return `att-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  // Helper function to get file extension for syntax highlighting
  function getFileExtension(filePath) {
    return filePath.split('.').pop()?.toLowerCase() || 'txt';
  }

  // Helper function to get language name from extension
  function getLanguageFromExtension(ext) {
    const languageMap = {
      'js': 'javascript', 'ts': 'typescript', 'py': 'python', 'java': 'java',
      'cpp': 'cpp', 'c': 'c', 'cs': 'csharp', 'php': 'php', 'rb': 'ruby',
      'go': 'go', 'rs': 'rust', 'sh': 'bash', 'yml': 'yaml', 'yaml': 'yaml',
      'json': 'json', 'xml': 'xml', 'html': 'html', 'css': 'css', 'scss': 'scss',
      'md': 'markdown', 'sql': 'sql', 'jsx': 'javascript', 'tsx': 'typescript'
    };
    return languageMap[ext] || 'text';
  }

  // Function to remove attachment by ID (globally accessible)
  window.removeAttachment = function (attachmentId) {
    pendingAttachments = pendingAttachments.filter(att => att.id !== attachmentId);
    renderAttachments();
  };

  // Function to render all attachments
  function renderAttachments() {
    if (!attachmentsContainer) return;

    if (pendingAttachments.length === 0) {
      attachmentsContainer.innerHTML = '';
      attachmentsContainer.style.display = 'none';
      return;
    }

    attachmentsContainer.style.display = 'block';
    attachmentsContainer.innerHTML = pendingAttachments.map(attachment => {
      const filename = attachment.path.split(/[\\\/]/).pop() || attachment.path;
      const ext = getFileExtension(attachment.path);
      const language = getLanguageFromExtension(ext);
      const lineCount = attachment.content.split('\n').length;

      const kindLabel = {
        'selection': '📝 Selected code',
        'currentFile': '📄 Current file',
        'file': '📁 File'
      }[attachment.kind] || '📎 Attachment';

      // Truncate content for preview (first 5 lines)
      const lines = attachment.content.split('\n');
      const previewLines = lines.slice(0, 5);
      const hasMore = lines.length > 5;
      const preview = previewLines.join('\n') + (hasMore ? '\n...' : '');

      return `
        <div class="navi-attachment-pill" data-attachment-id="${attachment.id}">
          <div class="navi-attachment-header">
            <span class="navi-attachment-label">${kindLabel}</span>
            <span class="navi-attachment-path" title="${attachment.path}">
              ${filename} · ${lineCount} line${lineCount !== 1 ? 's' : ''}
            </span>
            <button class="navi-attachment-remove" onclick="removeAttachment('${attachment.id}')" title="Remove attachment">
              ✕
            </button>
          </div>
          <div class="navi-attachment-content">
            <pre class="navi-attachment-code language-${language}"><code>${escapeHtml(preview)}</code></pre>
          </div>
        </div>
      `;
    }).join('');
  }

  // Form events --------------------------------------------------------------
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    if (editingMessageBubble) {
      // Update existing message bubble (Edit mode)
      console.log('[NAVI] Updating existing message');
      // Clear existing content and re-render
      editingMessageBubble.innerHTML = '';
      renderTextSegments(text, editingMessageBubble);

      // Re-add toolbar if it was in a user message
      if (editingMessageBubble.classList.contains('navi-bubble-user')) {
        const toolbar = document.createElement('div');
        toolbar.className = 'navi-msg-toolbar';
        const actions = [
          { id: 'copy', label: 'Copy' },
          { id: 'edit', label: 'Edit' },
          { id: 'use-as-prompt', label: 'Use as prompt' },
        ];
        actions.forEach(({ id, label }) => {
          const btn = document.createElement('button');
          btn.className = 'navi-msg-toolbar-btn';
          btn.textContent = label;
          btn.dataset.action = id;
          btn.dataset.messageText = text;
          toolbar.appendChild(btn);
        });
        editingMessageBubble.appendChild(toolbar);
      }

      // Exit edit mode
      editingMessageBubble = null;
    } else {
      // Create new user message (normal send or Use as prompt)
      console.log('[NAVI] Creating new message');
      const { bubble } = appendMessage(text, 'user');

      // Add attachments to the user message if any exist
      if (currentAttachments.length > 0) {
        const attachmentsList = document.createElement('div');
        attachmentsList.className = 'navi-message-attachments';

        currentAttachments.forEach(attachment => {
          const attachmentEl = document.createElement('div');
          attachmentEl.className = 'navi-message-attachment';

          const filename = attachment.path ? attachment.path.split('/').pop() : 'Unknown file';
          const lines = attachment.content ? attachment.content.split('\n').length : 0;

          attachmentEl.innerHTML = `
            <div class="navi-attachment-icon">📎</div>
            <div class="navi-attachment-info">
              <div class="navi-attachment-name">${filename}</div>
              <div class="navi-attachment-meta">${lines} lines • ${attachment.language || 'text'}</div>
            </div>
          `;

          attachmentsList.appendChild(attachmentEl);
        });

        // Insert attachments before the toolbar
        const toolbar = bubble.querySelector('.navi-msg-toolbar');
        if (toolbar) {
          bubble.insertBefore(attachmentsList, toolbar);
        } else {
          bubble.appendChild(attachmentsList);
        }
      }
    }

    if (vscode) {
      // Get current model and mode IDs from pills
      const modelPillEl = document.getElementById('modelPill');
      const modePillEl = document.getElementById('modePill');
      const modelId = modelPillEl?.dataset.modelId;
      const modeId = modePillEl?.dataset.modeId;

      vscode.postMessage({
        type: 'sendMessage',
        text,
        modelId,
        modeId,
        attachments: currentAttachments  // PR-5: include attachments
      });

      // Trigger intent classification for the user input
      vscode.postMessage({
        type: 'aep.intent.classify',
        text,
        modelId
      });
    }
    inputEl.value = '';
    inputEl.focus();

    // If stub chip is visible, clear it once the user sends something
    const footer = document.querySelector('.navi-footer');
    if (footer) {
      const chip = footer.querySelector('.navi-attachment-chip');
      if (chip) chip.remove();
    }

    showThinkingMessage();
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  // Header buttons
  root.querySelectorAll('.navi-header .navi-icon-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.getAttribute('data-action');
      if (!action || !vscode) return;

      if (action === 'newChat') {
        vscode.postMessage({ type: 'newChat' });
      } else if (action === 'connectors') {
        if (typeof window !== 'undefined' && window.connectorsMarketplace) {
          window.connectorsMarketplace.toggle();
        } else if (vscode) {
          // Fallback: let host know
          vscode.postMessage({ type: 'openConnectors' });
        }
      } else if (action === 'settings') {
        vscode.postMessage({ type: 'openSettings' });
      }
    });
  });

  // Model / Mode pills with custom dropdown menus ---------------------------
  const modelPill = document.getElementById('modelPill');
  const modePill = document.getElementById('modePill');
  const modelMenu = document.querySelector('.navi-model-menu');
  const modeMenu = document.querySelector('.navi-mode-menu');

  function closeAllPillMenus() {
    modelMenu?.classList.remove('navi-pill-menu--open');
    modeMenu?.classList.remove('navi-pill-menu--open');
  }

  if (modelPill && modelMenu) {
    modelPill.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = !modelMenu.classList.contains('navi-pill-menu--open');
      closeAllPillMenus();
      if (willOpen) modelMenu.classList.add('navi-pill-menu--open');
    });

    // Handle menu item clicks
    modelMenu.addEventListener('click', (e) => {
      const item = e.target.closest('.navi-pill-menu-item');
      if (item) {
        e.stopPropagation();
        const modelId = item.dataset.modelId;
        const modelLabel = item.dataset.modelLabel || item.textContent.trim();

        // Update pill display and data
        modelPill.dataset.modelId = modelId;
        modelPill.querySelector('span').textContent = `Model: ${modelLabel}`;

        if (vscode) {
          vscode.postMessage({
            type: 'setModel',
            modelId,
            modelLabel,
          });
        }
        closeAllPillMenus();
      }
    });
  }

  if (modePill && modeMenu) {
    modePill.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = !modeMenu.classList.contains('navi-pill-menu--open');
      closeAllPillMenus();
      if (willOpen) modeMenu.classList.add('navi-pill-menu--open');
    });

    // Handle menu item clicks
    modeMenu.addEventListener('click', (e) => {
      const item = e.target.closest('.navi-pill-menu-item');
      if (item) {
        e.stopPropagation();
        const modeId = item.dataset.modeId;
        const modeLabel = item.dataset.modeLabel || item.textContent.trim();

        // Update pill display and data
        modePill.dataset.modeId = modeId;
        modePill.querySelector('span').textContent = `Mode: ${modeLabel}`;

        if (vscode) {
          vscode.postMessage({
            type: 'setMode',
            modeId,
            modeLabel,
          });
        }
        closeAllPillMenus();
      }
    });
  }

  // Click anywhere else to close
  document.addEventListener('click', () => {
    closeAllPillMenus();
  });

  // ---------------------------------------------------------------------------
  // Message toolbar actions: Copy / Edit / Use as prompt
  // ---------------------------------------------------------------------------
  if (messagesEl && inputEl) {
    messagesEl.addEventListener('click', async (event) => {
      const button = event.target.closest('.navi-msg-toolbar-btn');
      if (!button) return;

      event.stopPropagation();

      const action = button.dataset.action;
      const text = button.dataset.messageText;

      if (!action || !text) return;

      switch (action) {
        case 'copy': {
          try {
            await navigator.clipboard.writeText(text);
            console.log('[NAVI] Copied message to clipboard');
          } catch (err) {
            console.error('[NAVI] Failed to copy message', err);
          }
          break;
        }

        case 'edit': {
          inputEl.value = text;
          inputEl.focus();
          inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);

          // Next send should UPDATE this bubble
          const messageRow = button.closest('.navi-msg-row');
          editingMessageBubble = messageRow ? messageRow.querySelector('.navi-bubble') : null;
          console.log('[NAVI] Edit mode: will update existing message');
          break;
        }

        case 'use-as-prompt': {
          inputEl.value = text;
          inputEl.focus();
          inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);

          // Next send should create a NEW message (not edit)
          editingMessageBubble = null;
          console.log('[NAVI] Use as prompt: will create new message');
          break;
        }

        default:
          break;
      }
    });
  }

  // Minimal Workspace Plan UI (A + C): header strip + collapsible steps
  function renderAgentRun(agentRun) {
    if (!agentRun || !agentRun.steps || !agentRun.steps.length) return null;

    const steps = agentRun.steps || [];
    const container = document.createElement('div');
    container.className = 'navi-agent-run';

    const header = document.createElement('div');
    header.className = 'navi-agent-run-header';

    const title = document.createElement('div');
    title.className = 'navi-agent-run-title';
    title.textContent = 'Workspace plan';

    const meta = document.createElement('div');
    meta.className = 'navi-agent-run-meta';
    const dur = agentRun.duration_ms ?? agentRun.durationMs;
    const parts = [];
    if (steps.length) {
      parts.push(`${steps.length} step${steps.length === 1 ? '' : 's'}`);
    }
    if (dur) {
      parts.push(`${dur} ms`);
    }
    meta.textContent = parts.join(' • ');

    const toggle = document.createElement('button');
    toggle.className = 'navi-agent-run-toggle';
    toggle.type = 'button';
    toggle.textContent = 'Details';

    header.appendChild(title);
    header.appendChild(meta);
    header.appendChild(toggle);

    const body = document.createElement('div');
    body.className = 'navi-agent-run-body navi-agent-run-body--collapsed';

    steps.forEach((step, index) => {
      const row = document.createElement('div');
      row.className = 'navi-agent-run-step';

      const statusDot = document.createElement('span');
      statusDot.className = `navi-agent-run-step-status status-${step.status || 'planned'}`;

      const label = document.createElement('span');
      label.className = 'navi-agent-run-step-label';
      const idx = index + 1;
      label.textContent = `${idx}. ${step.label || step.id || 'Step'}`;

      const head = document.createElement('div');
      head.appendChild(statusDot);
      head.appendChild(label);
      body.appendChild(head);

      if (step.detail) {
        const detail = document.createElement('div');
        detail.className = 'navi-agent-run-step-detail';
        detail.textContent = step.detail;
        body.appendChild(detail);
      }
    });

    toggle.addEventListener('click', () => {
      const isCollapsed = body.classList.contains('navi-agent-run-body--collapsed');
      if (isCollapsed) {
        body.classList.remove('navi-agent-run-body--collapsed');
        toggle.textContent = 'Hide details';
      } else {
        body.classList.add('navi-agent-run-body--collapsed');
        toggle.textContent = 'Details';
      }
    });

    container.appendChild(header);
    container.appendChild(body);
    return container;
  }

  // Helper: determine if an action is a code-changing patch
  function isPatchAction(action) {
    if (!action || typeof action !== 'object') return false;
    if (action.type === 'code.apply_patch') return true;
    if (typeof action.patch === 'string' && action.patch.trim().length > 0) return true;
    if (action.mutatesWorkspace === true) return true;
    if (action.safe === false) return true;
    return false;
  }

  // Messages from extension ---------------------------------------------------
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    switch (msg.type) {
      case 'botMessage': {
        hideThinkingMessage();
        state.streamingBubble = null;
        state.streamingMessageId = null;
        state.streamingText = '';

        const { bubble } = appendMessage(msg.text, 'bot', { sources: msg.sources });

        // Workspace plan / actions UI ----------------------------------------
        if (msg.actions && Array.isArray(msg.actions) && msg.actions.length > 0) {
          const actionsContainer = document.createElement('div');
          actionsContainer.className = 'navi-agent-actions';

          msg.actions.forEach((action, idx) => {
            const row = document.createElement('div');
            row.className = 'navi-agent-action-row';

            const isPatch = isPatchAction(action);
            const stepIndex = idx + 1;
            const titleText =
              action.title ||
              action.label ||
              action.description ||
              (isPatch ? 'Apply code change' : 'Workspace step');

            const filePath = action.filePath || action.path || '';
            const escapedTitle = escapeHtml(titleText);
            const escapedDesc = escapeHtml(action.description || action.detail || '');
            const escapedFile = filePath ? escapeHtml(filePath) : '';

            const safetyLabel = isPatch ? 'CHANGES CODE' : 'SAFE · reads workspace';
            const safetyClass = isPatch ? 'navi-agent-badge-danger' : 'navi-agent-badge-safe';

            row.innerHTML = `
              <div class="navi-agent-action-desc">
                <div class="navi-agent-action-title">
                  <span class="navi-agent-step-index">Step ${stepIndex}</span>
                  <span class="navi-agent-step-title-text">${escapedTitle}</span>
                </div>
                <div class="navi-agent-action-meta">
                  <span class="navi-agent-badge ${safetyClass}">${safetyLabel}</span>
                  ${escapedFile
                ? `<span class="navi-agent-file-path">${escapedFile}</span>`
                : ''
              }
                </div>
                ${escapedDesc
                ? `<div class="navi-agent-action-detail">${escapedDesc}</div>`
                : ''
              }
              </div>
              <div class="navi-agent-action-buttons">
                ${isPatch
                ? `
                      <button class="navi-agent-btn navi-agent-btn-approve" data-command="apply" data-index="${idx}">Apply</button>
                      <button class="navi-agent-btn" data-command="diff" data-index="${idx}">Diff</button>
                      <button class="navi-agent-btn" data-command="explain" data-index="${idx}">Explain</button>
                    `
                : `
                      <button class="navi-agent-btn navi-agent-btn-approve" data-command="run" data-index="${idx}">Run step</button>
                      <button class="navi-agent-btn" data-command="explain" data-index="${idx}">Explain</button>
                    `
              }
              </div>
            `;

            actionsContainer.appendChild(row);
          });

          // Click handler for Apply / Diff / Explain / Run
          actionsContainer.addEventListener('click', (ev) => {
            const btn = ev.target.closest('.navi-agent-btn');
            if (!btn) return;

            const command = btn.dataset.command;
            const index = Number(btn.dataset.index);
            const action = msg.actions[index];

            if (!command || !action) {
              console.warn('[NAVI] Missing command or action for workspace step');
              return;
            }

            if (!vscode) {
              console.warn('[NAVI] VS Code API not available for agent action');
              const row = btn.closest('.navi-agent-action-row');
              if (row) {
                const buttons = row.querySelectorAll('.navi-agent-btn');
                buttons.forEach((b) => {
                  b.disabled = true;
                  b.style.opacity = '0.5';
                });
                const desc = row.querySelector('.navi-agent-action-desc');
                if (desc) {
                  const errorMsg = document.createElement('em');
                  errorMsg.style.color = '#ef4444';
                  errorMsg.textContent = 'Error: VS Code API unavailable';
                  desc.appendChild(document.createElement('br'));
                  desc.appendChild(errorMsg);
                }
              }
              return;
            }

            vscode.postMessage({
              type: 'agent.applyAction',
              command,      // 'apply' | 'diff' | 'explain' | 'run'
              actionIndex: index,
              action       // full action object so extension can apply/diff
            });

            // Visual feedback for Apply / Run
            if (command === 'apply' || command === 'run') {
              const row = btn.closest('.navi-agent-action-row');
              if (row) {
                const buttons = row.querySelectorAll('.navi-agent-btn');
                buttons.forEach((b) => {
                  b.disabled = true;
                  b.style.opacity = '0.6';
                });

                const desc = row.querySelector('.navi-agent-action-desc');
                if (desc) {
                  const msgEl = document.createElement('em');
                  msgEl.style.display = 'block';
                  msgEl.style.marginTop = '4px';
                  msgEl.style.color = command === 'apply' ? '#10b981' : '#60a5fa';
                  msgEl.textContent =
                    command === 'apply'
                      ? 'Applying changes…'
                      : 'Running step…';
                  desc.appendChild(msgEl);
                }
              }
            }
          });

          bubble.appendChild(actionsContainer);
        }

        // If backend sent a real agentRun, render minimal Workspace plan header
        if (msg.agentRun) {
          const agentRunEl = renderAgentRun(msg.agentRun);
          if (agentRunEl && bubble) {
            // Attach inside the bot bubble to save space
            bubble.appendChild(agentRunEl);
          }
        }

        break;
      }

      case 'clearChat':
        clearChat();
        hideThinkingMessage();
        break;

      case 'botThinking':
        setThinking(!!msg.value);
        break;

      case 'botStreamStart': {
        hideThinkingMessage();
        state.streamingMessageId = msg.messageId;
        state.streamingText = '';
        const { bubble } = appendMessage('', 'bot');
        state.streamingBubble = bubble;
        break;
      }

      case 'botStreamDelta': {
        if (!msg.messageId || msg.messageId !== state.streamingMessageId) return;
        if (!state.streamingBubble) {
          const { bubble: newBubble } = appendMessage('', 'bot');
          state.streamingBubble = newBubble;
        }
        state.streamingText += msg.text || '';
        renderTextSegments(state.streamingText, state.streamingBubble);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        break;
      }

      case 'botStreamEnd':
        if (msg.messageId === state.streamingMessageId) {
          state.streamingMessageId = null;
          state.streamingBubble = null;
        }
        break;

      case 'insertCommandPrompt': {
        const input = document.querySelector('#navi-input') || document.querySelector('.navi-input');
        if (input) {
          input.value = msg.prompt || '';
          input.focus();
        }
        break;
      }

      case 'resetChat':
        clearChat();
        appendMessage('New chat started! How can I help you today?', 'bot');
        break;

      case 'attachmentsSelected': {
        const files = msg.files || [];
        if (!files.length) break;
        // Just show banner for now
        attachmentsBanner.classList.remove('navi-attachments-banner-hidden');
        attachmentsBanner.classList.add('navi-attachments-banner-visible');
        break;
      }

      case 'attachmentsCanceled':
        // No-op for now
        break;

      case 'aep.intent.result': {
        // Display intent classification result
        const intentResultEl = document.getElementById('navi-intent-result');
        if (intentResultEl && msg.intent) {
          const confidence = (msg.confidence * 100).toFixed(1);
          const model = msg.model || 'Unknown';

          intentResultEl.innerHTML = `
            <div class="navi-intent-display">
              <strong>Intent:</strong> ${escapeHtml(msg.intent)} 
              <span class="navi-intent-confidence">(${confidence}% confidence)</span>
              <div class="navi-intent-model">Model: ${escapeHtml(model)}</div>
            </div>
          `;
          intentResultEl.style.display = 'block';
        }
        break;
      }

      case 'hydrateState': {
        // Restore model and mode from saved state (PR-4)
        const modelPillEl = document.getElementById('modelPill');
        const modePillEl = document.getElementById('modePill');

        if (msg.modelId && msg.modelLabel && modelPillEl) {
          modelPillEl.dataset.modelId = msg.modelId;
          modelPillEl.querySelector('span').textContent = `Model: ${msg.modelLabel}`;
        }

        if (msg.modeId && msg.modeLabel && modePillEl) {
          modePillEl.dataset.modeId = msg.modeId;
          modePillEl.querySelector('span').textContent = `Mode: ${msg.modeLabel}`;
        }
        break;
      }

      case 'addAttachment': {
        // PR-5: Add attachment to pending list with enhanced data
        if (msg.attachment) {
          const attachmentWithId = {
            ...msg.attachment,
            id: generateAttachmentId()
          };
          pendingAttachments.push(attachmentWithId);
          currentAttachments.push(msg.attachment);
          renderAttachments();
        }
        break;
      }

      case 'toast': {
        const { message, level } = msg;
        if (message) {
          showEphemeralToast(message, level || 'info');
        }
        break;
      }

      case 'error': {
        // Stop the thinking bubble
        hideThinkingMessage();

        const text = msg.text || '⚠️ Something went wrong talking to NAVI backend.';
        // Show as a muted bot message so it's visible in history
        appendMessage(text, 'bot', { muted: true });

        // Optionally also use the ephemeral toast
        showEphemeralToast(text, 'error');
        break;
      }

      case 'showJiraTasks': {
        const container = document.getElementById('navi-jira-tasks');
        if (!container) break;

        const tasks = msg.tasks || [];
        if (!tasks.length) {
          container.innerHTML = `
            <div class="navi-jira-tasks-empty">
              No Jira tasks found in NAVI's memory yet.
              Try running the Jira sync or check your user_id.
            </div>
          `;
        } else {
          const itemsHtml = tasks
            .map(
              (t) => `
                <button class="navi-jira-task-item" data-jira-key="${escapeHtml(t.jira_key)}">
                  <div class="navi-jira-task-title">${escapeHtml(t.jira_key)} — ${escapeHtml(t.title)}</div>
                  <div class="navi-jira-task-meta">
                    <span class="navi-jira-task-status">${escapeHtml(t.status)}</span>
                    <span class="navi-jira-task-updated">Updated: ${escapeHtml(t.updated_at || '')}</span>
                  </div>
                </button>
              `
            )
            .join('');

          container.innerHTML = `
            <div class="navi-jira-tasks-header">
              <div class="navi-jira-tasks-title">Select a Jira task to get a full brief</div>
              <button class="navi-jira-tasks-close">✕</button>
            </div>
            <div class="navi-jira-tasks-list">
              ${itemsHtml}
            </div>
          `;
        }

        container.classList.remove('navi-jira-tasks-hidden');

        // Click handlers: select task or close
        container.addEventListener('click', (ev) => {
          const closeBtn = ev.target.closest('.navi-jira-tasks-close');
          if (closeBtn) {
            container.classList.add('navi-jira-tasks-hidden');
            return;
          }

          const item = ev.target.closest('.navi-jira-task-item');
          if (!item) return;

          const jiraKey = item.dataset.jiraKey;
          if (!jiraKey || !vscode) return;

          vscode.postMessage({
            type: 'jiraTaskSelected',
            jiraKey,
          });

          // Hide list once a task is selected
          container.classList.add('navi-jira-tasks-hidden');
        }, { once: true });
        break;
      }

      case 'ephemeralToast': {
        const { text, level } = msg;
        showEphemeralToast(text || '', level || 'info');
        break;
      }

      // Connector messages (handled by ConnectorsPanel, not main panel)
      case 'connectors.status':
      case 'connectors.statusError':
      case 'connectors.jiraConnected':
      case 'connectors.jiraConnectError':
        // These are for the ConnectorsPanel webview, ignore in main panel
        break;

      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // Tell extension we're ready
  if (vscode) {
    vscode.postMessage({ type: 'ready' });
  }
})();

// ---------------------------------------------------------------------------
// Footer wiring (wand, attach, command menu) – runs after DOM ready
// ---------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', () => {
  const vscodeApi = (typeof window !== 'undefined' && window.vscode) || null;
  console.log('[NAVI] Footer wiring: vscodeApi present?', !!vscodeApi);

  // Attachment hint (banner) helpers -----------------------------------------
  let attachmentHintEl = null;
  let attachmentHintTimeout = null;

  function showAttachmentHint(message) {
    const footer = document.querySelector('.navi-footer');
    if (!footer) return;

    if (!attachmentHintEl) {
      attachmentHintEl = document.createElement('div');
      attachmentHintEl.className = 'navi-attach-hint';

      const icon = document.createElement('span');
      icon.className = 'navi-attach-hint-icon';
      icon.textContent = '📎';

      const text = document.createElement('span');
      text.className = 'navi-attach-hint-text';

      attachmentHintEl.appendChild(icon);
      attachmentHintEl.appendChild(text);

      footer.insertBefore(attachmentHintEl, footer.firstChild);
    }

    attachmentHintEl.querySelector('.navi-attach-hint-text').textContent = message;
    attachmentHintEl.classList.add('navi-attach-hint--visible');

    if (attachmentHintTimeout) clearTimeout(attachmentHintTimeout);
    attachmentHintTimeout = setTimeout(() => {
      attachmentHintEl.classList.remove('navi-attach-hint--visible');
    }, 4000);
  }

  // Close hint when clicking elsewhere
  window.addEventListener('click', (event) => {
    if (!attachmentHintEl) return;
    const isOnHint = event.target.closest('.navi-attach-hint');
    const isOnAttach = event.target.closest('#navi-attach-btn');
    if (!isOnHint && !isOnAttach) {
      attachmentHintEl.classList.remove('navi-attach-hint--visible');
    }
  }, true);

  if (!vscodeApi) {
    console.warn('[NAVI] vscode API instance not found – footer wiring disabled.');
    return;
  }

  const attachBtn = document.getElementById('navi-attach-btn');
  const actionsBtn = document.getElementById('navi-actions-btn');
  const menu = document.getElementById('navi-command-menu');
  const attachmentsBanner = document.getElementById('navi-attachments-banner');

  commandMenuEl = menu;

  // ---- UNIFIED MENU MANAGEMENT ----

  function closeAllMenus() {
    // Close command menu
    if (commandMenuEl) {
      commandMenuEl.classList.remove('navi-command-menu-visible');
      commandMenuEl.classList.add('navi-command-menu-hidden');
    }

    // Close attachment menu
    const attachmentMenu = document.querySelector('.navi-attachment-menu');
    if (attachmentMenu) {
      attachmentMenu.classList.remove('navi-menu--open');
    }

    openMenu = null;
  }

  function openCommandMenu() {
    if (!commandMenuEl) return;
    closeAllMenus();
    openMenu = 'actions';
    commandMenuEl.classList.remove('navi-command-menu-hidden');
    commandMenuEl.classList.add('navi-command-menu-visible');
  }

  function closeCommandMenu() {
    if (!commandMenuEl) return;
    openMenu = null;
    commandMenuEl.classList.remove('navi-command-menu-visible');
    commandMenuEl.classList.add('navi-command-menu-hidden');
  }

  function toggleCommandMenu() {
    if (!commandMenuEl) return;
    if (openMenu === 'actions') {
      closeCommandMenu();
    } else {
      openCommandMenu();
    }
  }

  console.log(
    '[NAVI] Footer wiring:',
    'attachBtn', !!attachBtn,
    'actionsBtn', !!actionsBtn,
    'menu', !!menu
  );

  // Drag handlers (optional but nice) ----------------------------------------
  function onCommandMenuDragStart(e) {
    if (!commandMenuEl) return;

    commandMenuDragState.dragging = true;
    const rect = commandMenuEl.getBoundingClientRect();
    commandMenuDragState.offsetX = e.clientX - rect.left;
    commandMenuDragState.offsetY = e.clientY - rect.top;

    commandMenuHasUserPosition = true;
    commandMenuEl.style.transform = 'none';
  }

  function onCommandMenuDragMove(e) {
    if (!commandMenuEl || !commandMenuDragState.dragging) return;

    const webviewRect = document.body.getBoundingClientRect();
    let left = e.clientX - commandMenuDragState.offsetX - webviewRect.left;
    let top = e.clientY - commandMenuDragState.offsetY - webviewRect.top;

    const maxLeft = webviewRect.width - commandMenuEl.offsetWidth - 16;
    const maxTop = webviewRect.height - commandMenuEl.offsetHeight - 16;

    left = Math.min(Math.max(16, left), Math.max(16, maxLeft));
    top = Math.min(Math.max(16, top), Math.max(16, maxTop));

    commandMenuEl.style.bottom = 'auto';
    commandMenuEl.style.left = `${left}px`;
    commandMenuEl.style.top = `${top}px`;
  }

  function onCommandMenuDragEnd() {
    if (!commandMenuEl) return;
    commandMenuDragState.dragging = false;
  }

  if (commandMenuEl) {
    commandMenuEl.addEventListener('mousedown', onCommandMenuDragStart);
    window.addEventListener('mousemove', onCommandMenuDragMove);
    window.addEventListener('mouseup', onCommandMenuDragEnd);
  }

  // PR-5: Attachment menu handling
  const attachmentMenu = document.querySelector('.navi-attachment-menu');
  // Note: using unified openMenu state instead of separate isAttachmentMenuOpen

  function toggleAttachmentMenu() {
    if (!attachmentMenu) return;

    if (openMenu === 'attach') {
      // Close attachment menu
      openMenu = null;
      attachmentMenu.classList.remove('navi-menu--open');
    } else {
      // Close any other open menu and open attachment menu
      closeAllMenus();
      openMenu = 'attach';
      attachmentMenu.classList.add('navi-menu--open');
    }
  }

  if (attachBtn && attachmentMenu) {
    attachBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      console.log('[NAVI] Attach button clicked - showing menu');
      toggleAttachmentMenu();
    });

    attachmentMenu.addEventListener('click', (event) => {
      const item = event.target.closest('[data-attach]');
      if (!item) return;

      const kind = item.dataset.attach;
      console.log('[NAVI] Attachment type selected:', kind);
      attachmentMenu.classList.remove('navi-menu--open');
      openMenu = null;

      if (vscodeApi) {
        vscodeApi.postMessage({
          type: 'requestAttachment',
          kind, // "selection" | "current-file" | "pick-file"
        });
      }
    });

    // Close menu when clicking outside
    document.addEventListener('click', (event) => {
      if (!attachmentMenu.contains(event.target) && !attachBtn.contains(event.target)) {
        closeAllMenus();
      }
    });
  }

  // ---- WAND BUTTON WIRING ----
  const wandBtn = actionsBtn;

  // ---- JIRA TASK PICKER HANDLER ----
  async function handleWorkOnJiraTask() {
    try {
      // Get backend URL from window.AEP_CONFIG
      const backendBaseUrl = (window.AEP_CONFIG && window.AEP_CONFIG.backendBaseUrl) || 'http://127.0.0.1:8787';
      const userId = (window.AEP_CONFIG && window.AEP_CONFIG.userId) || 'srinivas@example.com';

      const url = `${backendBaseUrl}/api/navi/jira-tasks?user_id=${encodeURIComponent(userId)}&limit=20`;

      console.log('[NAVI] Fetching Jira tasks from:', url);

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        showToast(
          `Couldn't load Jira tasks from NAVI (HTTP ${response.status}). Make sure Jira is connected and synced.`,
          'error'
        );
        return;
      }

      const data = await response.json();
      const tasks = data.tasks || [];

      if (!tasks.length) {
        showToast(
          'NAVI didn\'t find any Jira tasks in memory yet. Try running Jira sync or checking your connector in the Connectors Hub.',
          'info'
        );
        return;
      }

      // Show tasks using the existing showJiraTasks UI
      const container = document.getElementById('navi-jira-tasks');
      if (!container) return;

      if (!tasks || tasks.length === 0) {
        container.innerHTML = `
          <div class="navi-jira-tasks-empty">
            No Jira tasks found in NAVI's memory yet.
          </div>
        `;
      } else {
        const itemsHtml = tasks
          .map(
            (t) => `
              <button class="navi-jira-task-item" data-jira-key="${escapeHtml(t.jira_key || t.key)}">
                <div class="navi-jira-task-title">${escapeHtml(t.jira_key || t.key)} — ${escapeHtml(t.title || t.summary)}</div>
                <div class="navi-jira-task-meta">
                  <span class="navi-jira-task-status">${escapeHtml(t.status)}</span>
                  <span class="navi-jira-task-updated">Updated: ${escapeHtml(t.updated_at || '')}</span>
                </div>
              </button>
            `
          )
          .join('');

        container.innerHTML = `
          <div class="navi-jira-tasks-header">
            <div class="navi-jira-tasks-title">Select a Jira task to get a full brief</div>
            <button class="navi-jira-tasks-close">✕</button>
          </div>
          <div class="navi-jira-tasks-list">
            ${itemsHtml}
          </div>
        `;
      }

      container.classList.remove('navi-jira-tasks-hidden');

      // Click handlers: select task or close
      container.addEventListener('click', (ev) => {
        const closeBtn = ev.target.closest('.navi-jira-tasks-close');
        if (closeBtn) {
          container.classList.add('navi-jira-tasks-hidden');
          return;
        }

        const item = ev.target.closest('.navi-jira-task-item');
        if (!item) return;

        const jiraKey = item.dataset.jiraKey;
        if (!jiraKey || !vscodeApi) return;

        vscodeApi.postMessage({
          type: 'jiraTaskSelected',
          jiraKey,
        });

        // Hide list once a task is selected
        container.classList.add('navi-jira-tasks-hidden');
      }, { once: true });

    } catch (error) {
      console.error('[NAVI] Failed to load Jira tasks', error);
      showToast('Error loading Jira tasks. Check the backend logs.', 'error');
    }
  }

  // Simple toast helper
  function showToast(message, type = 'info') {
    // Reuse VS Code's showInformationMessage via extension host
    if (vscodeApi) {
      vscodeApi.postMessage({
        type: 'showToast',
        message,
        level: type
      });
    }
  }

  // Toast system now uses global showEphemeralToast function

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ---- WAND BUTTON WIRING ----

  // Wand button click handler
  if (wandBtn && commandMenuEl) {
    wandBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      console.log('[NAVI] Wand button clicked');
      toggleCommandMenu();
    });

    // clicking inside the menu should not close it
    commandMenuEl.addEventListener('click', (event) => {
      event.stopPropagation();
    });

    // clicking anywhere else closes all menus
    document.addEventListener('click', (event) => {
      if (openMenu && !commandMenuEl.contains(event.target) && !wandBtn.contains(event.target)) {
        closeAllMenus();
      }
    });
  }

  // Command menu item clicks
  if (menu) {
    const ITEM_SELECTOR = '.navi-command-item';

    menu.addEventListener('click', (event) => {
      const target = event.target;
      if (!target) return;

      const item = target.closest ? target.closest(ITEM_SELECTOR) : null;
      if (!item) return;

      event.stopPropagation();

      const id =
        item.dataset.commandId ||
        item.getAttribute('data-command-id') ||
        '';

      console.log('[NAVI] Command selected:', id);

      // Handle "Work on a Jira task" command directly in webview
      if (id === 'jira-task-brief') {
        handleWorkOnJiraTask();
        closeCommandMenu();
        return;
      }

      // For other commands, delegate to extension host
      if (id) {
        vscodeApi.postMessage({
          type: 'commandSelected',
          command: id,
        });
      }

      closeCommandMenu();
    });

    menu.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      const target = event.target;
      if (!target) return;
      const item = target.closest ? target.closest(ITEM_SELECTOR) : null;
      if (!item) return;

      event.preventDefault();
      item.click();
    });
  }

  // ESC closes any open menu
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && openMenu) {
      closeAllMenus();
    }
  });

  // --- Ephemeral toast just above the input row ------------------------------

  // --- Initialize Connectors Marketplace -----------------------------------
  // Load the connectors marketplace after the main UI is ready
  if (typeof window !== 'undefined' && window.ConnectorsMarketplace) {
    window.connectorsMarketplace = new window.ConnectorsMarketplace();
    console.log('[NAVI] Connectors marketplace initialized');
  } else {
    console.warn('[NAVI] ConnectorsMarketplace class not available');
  }

});