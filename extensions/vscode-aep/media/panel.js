// media/panel.js
// NAVI chat panel with streaming + quick actions + message toolbar

// ---------------------------------------------------------------------------
// Shared state for command menu (wand)
// ---------------------------------------------------------------------------
let commandMenuEl = null;
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
          <div class="navi-model-pill navi-pill" id="modelPill">
            <span>Model: ChatGPT 5.1</span>
            <div class="navi-pill-menu navi-model-menu">
              <div class="navi-pill-menu-item" data-value="ChatGPT 5.1">ChatGPT 5.1</div>
              <div class="navi-pill-menu-item" data-value="gpt-4.2">gpt-4.2</div>
              <div class="navi-pill-menu-item" data-value="o3-mini">o3-mini</div>
            </div>
          </div>

          <div class="navi-mode-pill navi-pill" id="modePill">
            <span>Mode: Agent (full access)</span>
            <div class="navi-pill-menu navi-mode-menu">
              <div class="navi-pill-menu-item" data-value="Agent (full access)">Agent (full access)</div>
              <div class="navi-pill-menu-item" data-value="Chat only">Chat only</div>
              <div class="navi-pill-menu-item" data-value="Read-only explorer">Read-only explorer</div>
            </div>
          </div>
        </div>

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

  // Rendering helpers --------------------------------------------------------
  function renderTextSegments(text, container) {
    const lines = String(text).split('\n');
    container.innerHTML = '';

    let inCodeBlock = false;
    let codeBuffer = [];

    const flushCodeBlock = () => {
      if (!codeBuffer.length) return;
      const pre = document.createElement('pre');
      pre.className = 'navi-code-block';
      pre.textContent = codeBuffer.join('\n');
      container.appendChild(pre);
      codeBuffer = [];
    };

    lines.forEach((line, idx) => {
      if (line.trim().startsWith('```')) {
        if (inCodeBlock) {
          flushCodeBlock();
          inCodeBlock = false;
        } else {
          inCodeBlock = true;
        }
        return;
      }

      if (inCodeBlock) {
        codeBuffer.push(line);
        return;
      }

      if (line.startsWith('> ')) {
        const quote = document.createElement('div');
        quote.className = 'navi-line-quote';
        quote.textContent = line.slice(2);
        container.appendChild(quote);
      } else if (line.trim().length > 0) {
        const p = document.createElement('div');
        p.textContent = line;
        container.appendChild(p);
      }

      if (idx < lines.length - 1 && !inCodeBlock) {
        container.appendChild(document.createElement('br'));
      }
    });

    flushCodeBlock();
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
      { id: 'reuse', label: 'Use as prompt' },
    ];

    actions.forEach(({ id, label }) => {
      const btn = document.createElement('button');
      btn.className = 'navi-msg-toolbar-btn';
      btn.textContent = label;
      btn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (vscode) {
          vscode.postMessage({
            type: 'messageToolbarAction',
            action: id,
            role,
            text: safeText,
          });
        }
      });
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

  // Form events --------------------------------------------------------------
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    if (vscode) {
      vscode.postMessage({ type: 'sendMessage', text });
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
        const value = item.dataset.value;
        modelPill.querySelector('span').textContent = `Model: ${value}`;
        if (vscode) {
          vscode.postMessage({
            type: 'modelSelected',
            value: value,
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
        const value = item.dataset.value;
        modePill.querySelector('span').textContent = `Mode: ${value}`;
        if (vscode) {
          vscode.postMessage({
            type: 'modeSelected',
            value: value,
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

  // Messages from extension ---------------------------------------------------
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    switch (msg.type) {
      case 'botMessage':
        hideThinkingMessage();
        state.streamingBubble = null;
        state.streamingMessageId = null;
        state.streamingText = '';
        appendMessage(msg.text, 'bot');
        break;

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
    const isOnHint   = event.target.closest('.navi-attach-hint');
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

  // ---- WAND / COMMAND MENU STATE (must be declared before use) ----
  let isCommandMenuOpen = false;

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

  // + Attach button - request attachment picker from extension
  if (attachBtn) {
    attachBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      console.log('[NAVI] Attach button clicked');
      if (vscodeApi) {
        vscodeApi.postMessage({ type: 'attachBtnClicked' });
      }
    });
  }

  // Listen for attachmentNotImplemented message from extension
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (msg && msg.type === 'attachmentNotImplemented') {
      showAttachmentHint('Attachment flow is not implemented yet – coming soon.');
    }
  });

  // Attachment toast functionality
  const attachToast = document.querySelector('.navi-attach-toast');
  if (attachBtn && attachToast) {
    attachBtn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      console.log('[NAVI] Attach button clicked - showing coming soon message');

      // Don't call extension - just show the "coming soon" message
      // if (vscodeApi) {
      //   vscodeApi.postMessage({ type: 'attachBtnClicked' });
      // }

      // Show toast
      attachToast.classList.add('navi-attach-toast--visible');

      // Auto-hide after 3s
      clearTimeout(window._naviAttachToastTimer);
      window._naviAttachToastTimer = setTimeout(() => {
        attachToast.classList.remove('navi-attach-toast--visible');
      }, 3000);
    });

    // Clicking anywhere outside hides the toast
    document.addEventListener('click', (event) => {
      const isOnToast = event.target.closest('.navi-attach-toast');
      const isOnAttach = event.target.closest('#navi-attach-btn');
      if (!isOnToast && !isOnAttach) {
        attachToast.classList.remove('navi-attach-toast--visible');
        if (window._naviAttachToastTimer) {
          clearTimeout(window._naviAttachToastTimer);
        }
      }
    });

    // ESC key hides the toast
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && attachToast.classList.contains('navi-attach-toast--visible')) {
        attachToast.classList.remove('navi-attach-toast--visible');
        if (window._naviAttachToastTimer) {
          clearTimeout(window._naviAttachToastTimer);
        }
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
    if (!commandMenu) return;
    if (!isCommandMenuOpen) return;
    if (event.key === 'Escape') {
      closeCommandMenu();
    }
  });
});
