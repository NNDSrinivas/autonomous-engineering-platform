// media/panel.js
// NAVI chat panel with streaming + quick actions + message toolbar

// ---------------------------------------------------------------------------
// Shared state for command menu (wand)
// ---------------------------------------------------------------------------
let commandMenuEl = null;
let isCommandMenuOpen = false;
let commandMenuHasUserPosition = false;
let commandMenuDragState = {
  dragging: false,
  offsetX: 0,
  offsetY: 0,
};

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
      </main>

      <footer class="navi-footer">
        <div class="navi-attach-toast">
          <span class="navi-attach-toast-icon">📎</span>
          <span class="navi-attach-toast-text">Attachment flow is not implemented yet – coming soon.</span>
        </div>

        <div id="navi-attachments-banner" class="navi-attachments-banner navi-attachments-banner-hidden">
          <span class="navi-attachments-icon">📎</span>
          <span class="navi-attachments-text">Attachment flow is not implemented yet – coming soon.</span>
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
          <div class="navi-model-pill navi-pill" id="modelPill" data-model-id="gpt-5.1">
            <span>Model: ChatGPT 5.1</span>
            <div class="navi-pill-menu navi-model-menu">
              <div class="navi-pill-menu-item" data-model-id="gpt-5.1" data-model-label="ChatGPT 5.1">ChatGPT 5.1</div>
              <div class="navi-pill-menu-item" data-model-id="gpt-4.2" data-model-label="gpt-4.2">gpt-4.2</div>
              <div class="navi-pill-menu-item" data-model-id="o3-mini" data-model-label="o3-mini">o3-mini</div>
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

        <div class="navi-attachments-preview"></div>

        <div id="navi-command-menu" class="navi-command-menu navi-command-menu-hidden">
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

  // DOM references -----------------------------------------------------------
  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');
  const attachmentsBanner = document.getElementById('navi-attachments-banner');

  // Markdown rendering (enhanced for PR-3) ------------------------------------
  function renderMarkdown(text) {
    if (!text) return '';

    let html = text;

    // Code fences ```lang\ncode\n```
    html = html.replace(/```(\w+)?\n?([\s\S]*?)```/g, (match, lang, code) => {
      const safeLang = lang ? ` language-${lang}` : '';
      const escapedCode = (code || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return `<pre class="navi-code-block"><code class="navi-code-content${safeLang}">${escapedCode}</code></pre>`;
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
    html = html.replace(/^> (.*)$/gm, '<blockquote class="navi-blockquote">$1</blockquote>');

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
  const attachmentsPreviewEl = document.querySelector('.navi-attachments-preview');

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
      appendMessage(text, 'user');
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
        attachments: pendingAttachments  // PR-5: include attachments
      });
    }
    inputEl.value = '';
    inputEl.focus();

    // PR-5: Clear attachments after sending
    pendingAttachments = [];
    if (attachmentsPreviewEl) {
      attachmentsPreviewEl.innerHTML = '';
    }

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
        vscode.postMessage({ type: 'openConnectors' });
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

        const { bubble } = appendMessage(msg.text, 'bot');

        // PR-6: Show agent actions if present
        if (msg.actions && msg.actions.length > 0) {
          const actionsContainer = document.createElement('div');
          actionsContainer.className = 'navi-agent-actions';

          msg.actions.forEach((action, idx) => {
            const row = document.createElement('div');
            row.className = 'navi-agent-action-row';

            const filename = action.filePath.split('/').pop() || action.filePath;

            row.innerHTML = `
              <div class="navi-agent-action-desc">
                <strong>💡 Proposed ${action.type === 'createFile' ? 'new file' : 'edit'}</strong> in <code>${filename}</code>
                <div class="navi-agent-action-detail">${action.description || 'No description'}</div>
              </div>
              <div class="navi-agent-action-buttons">
                <button class="navi-agent-btn navi-agent-btn-approve" data-action="approve" data-index="${idx}">✅ Approve</button>
                <button class="navi-agent-btn navi-agent-btn-reject" data-action="reject" data-index="${idx}">❌ Reject</button>
              </div>
            `;

            actionsContainer.appendChild(row);
          });

          // Add click handler
          actionsContainer.addEventListener('click', (ev) => {
            const btn = ev.target.closest('.navi-agent-btn');
            if (!btn) return;

            const kind = btn.dataset.action;
            const index = Number(btn.dataset.index);

            vscodeApi.postMessage({
              type: kind === 'approve' ? 'agent.applyEdit' : 'agent.rejectEdit',
              messageId: msg.messageId,
              actionIndex: index,
            });

            // Disable buttons after click
            const row = btn.closest('.navi-agent-action-row');
            if (row) {
              const buttons = row.querySelectorAll('.navi-agent-btn');
              buttons.forEach(b => {
                b.disabled = true;
                b.style.opacity = '0.5';
              });

              if (kind === 'approve') {
                row.querySelector('.navi-agent-action-desc').innerHTML += '<br/><em style="color: #10b981;">Applying edit...</em>';
              } else {
                row.querySelector('.navi-agent-action-desc').innerHTML += '<br/><em style="color: #ef4444;">Rejected</em>';
              }
            }
          });

          bubble.appendChild(actionsContainer);
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
        // PR-5: Add attachment to pending list
        if (msg.attachment) {
          pendingAttachments.push(msg.attachment);
          // Render preview
          if (attachmentsPreviewEl) {
            const chip = document.createElement('div');
            chip.className = 'navi-attachment-chip';
            const filename = msg.attachment.path.split('/').pop() || msg.attachment.path;
            chip.textContent = filename;
            attachmentsPreviewEl.appendChild(chip);
          }
        }
        break;
      }

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

  // ---- WAND / COMMAND MENU FUNCTIONS ----

  function openCommandMenu() {
    if (!commandMenuEl) return;
    isCommandMenuOpen = true;
    commandMenuEl.classList.remove('navi-command-menu-hidden');
    commandMenuEl.classList.add('navi-command-menu-visible');
  }

  function closeCommandMenu() {
    if (!commandMenuEl) return;
    isCommandMenuOpen = false;
    commandMenuEl.classList.remove('navi-command-menu-visible');
    commandMenuEl.classList.add('navi-command-menu-hidden');
  }

  function toggleCommandMenu() {
    if (!commandMenuEl) return;
    if (isCommandMenuOpen) {
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

  // --- Command menu helpers -------------------------------------------------
  function openCommandMenu_legacy(anchorButton) {
    if (!commandMenuEl) return;

    if (!commandMenuHasUserPosition && anchorButton) {
      const anchorRect = anchorButton.getBoundingClientRect();
      const webviewRect = document.body.getBoundingClientRect();

      const menuWidth = commandMenuEl.offsetWidth || 360;
      const menuHeight = commandMenuEl.offsetHeight || 260;

      const preferredLeft =
        anchorRect.left - webviewRect.left - menuWidth * 0.25;
      const preferredBottom =
        webviewRect.bottom - anchorRect.top + 16;

      commandMenuEl.style.left = `${Math.max(24, preferredLeft)}px`;
      commandMenuEl.style.bottom = `${preferredBottom}px`;
      commandMenuEl.style.top = 'auto';
      commandMenuEl.style.transform = 'none';
    }

    commandMenuEl.classList.remove('navi-command-menu-hidden');
    commandMenuEl.classList.add('navi-command-menu-visible');
  }

  function closeCommandMenu() {
    if (!commandMenuEl) return;
    commandMenuEl.classList.remove('navi-command-menu-visible');
    commandMenuEl.classList.add('navi-command-menu-hidden');
  }

  function toggleCommandMenu(anchorButton) {
    if (!commandMenuEl) return;
    if (commandMenuEl.classList.contains('navi-command-menu-visible')) {
      closeCommandMenu();
    } else {
      openCommandMenu(anchorButton);
    }
  }

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
    // closeCommandMenu(); // Removed - state is already initialized to false above
  }

  // PR-5: Attachment menu handling
  const attachmentMenu = document.querySelector('.navi-attachment-menu');
  let isAttachmentMenuOpen = false;

  function toggleAttachmentMenu() {
    if (!attachmentMenu) return;
    isAttachmentMenuOpen = !isAttachmentMenuOpen;
    if (isAttachmentMenuOpen) {
      attachmentMenu.classList.add('navi-menu--open');
    } else {
      attachmentMenu.classList.remove('navi-menu--open');
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
      isAttachmentMenuOpen = false;

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
        attachmentMenu.classList.remove('navi-menu--open');
        isAttachmentMenuOpen = false;
      }
    });
  }

  // ---- WAND BUTTON WIRING ----
  const wandBtn = actionsBtn;

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

    // clicking anywhere else closes it
    document.addEventListener('click', () => {
      if (isCommandMenuOpen) {
        closeCommandMenu();
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

  // ESC closes command menu
  document.addEventListener('keydown', (event) => {
    if (!commandMenuEl) return;
    if (!isCommandMenuOpen) return;
    if (event.key === 'Escape') {
      closeCommandMenu();
    }
  });
});
