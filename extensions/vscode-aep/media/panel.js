// media/panel.js
// NAVI chat panel with streaming support

(function () {
  // ---------------------------------------------------------------------------
  // NAVI webview VS Code API bootstrap
  // ---------------------------------------------------------------------------
  const vscode = (() => {
    try {
      const api = acquireVsCodeApi();
      if (typeof window !== 'undefined') {
        // expose globally so later modules (footer, etc.) can reuse it
        window.vscode = api;
      }
      return api;
    } catch (err) {
      console.error('[NAVI] Failed to acquire VS Code API:', err);
      return null;
    }
  })();

  const root = document.getElementById('root');
  if (!root) {
    console.error('[NAVI] Root element #root not found');
    return;
  }

  // ---------------------------------------------------------------------------
  // Command menu shared state (wand)
  // ---------------------------------------------------------------------------
  let commandMenuEl = null;
  let commandMenuHasUserPosition = false;
  const commandMenuDragState = {
    dragging: false,
    offsetX: 0,
    offsetY: 0,
  };

  // ---------------------------------------------------------------------------
  // Streaming + thinking state
  // ---------------------------------------------------------------------------
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
    bubble.className = 'navi-message navi-message-thinking';
    bubble.dataset.kind = 'thinking';
    bubble.textContent = 'NAVI is thinking…';

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

  // ---------------------------------------------------------------------------
  // Shell markup
  // ---------------------------------------------------------------------------
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
          <button class="navi-pill" id="navi-model-pill" type="button">Model: ChatGPT 5.1</button>
          <button class="navi-pill" id="navi-mode-pill" type="button">Mode: Agent (full access)</button>
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

  // NAVI logo styling
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

  // ---------------------------------------------------------------------------
  // Chat message rendering
  // ---------------------------------------------------------------------------
  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');
  const modelPill = document.getElementById('navi-model-pill');
  const modePill = document.getElementById('navi-mode-pill');

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

  function createMessageActions(role, text) {
    const safe = String(text || '');
    if (!safe.trim()) return null;

    const actions = document.createElement('div');
    actions.className = 'navi-msg-actions';

    function makeBtn(label, title) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'navi-msg-action-btn';
      btn.textContent = label;
      if (title) btn.title = title;
      return btn;
    }

    // Copy (both user + bot)
    const copyBtn = makeBtn('Copy', 'Copy to clipboard');
    copyBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(safe).catch((err) =>
          console.warn('[NAVI] clipboard write failed:', err)
        );
      } else if (vscode) {
        vscode.postMessage({ type: 'copyToClipboard', text: safe });
      }
    });
    actions.appendChild(copyBtn);

    if (role === 'user') {
      // Edit user message (put back into input)
      const editBtn = makeBtn('Edit', 'Edit this prompt');
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (inputEl) {
          inputEl.value = safe;
          inputEl.focus();
        }
      });
      actions.appendChild(editBtn);

      // Reuse message (re-send after editing)
      const reuseBtn = makeBtn('Use again', 'Reuse this prompt');
      reuseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (inputEl) {
          inputEl.value = safe;
          inputEl.focus();
        }
      });
      actions.appendChild(reuseBtn);
    } else {
      // Bot bubble actions
      const insertBtn = makeBtn('Insert', 'Insert into a file');
      insertBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (vscode) {
          vscode.postMessage({
            type: 'insertIntoFile',
            text: safe,
          });
        }
      });
      actions.appendChild(insertBtn);

      const useBtn = makeBtn('Use as prompt', 'Send as a follow-up prompt');
      useBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (inputEl) {
          inputEl.value = safe;
          inputEl.focus();
        }
      });
      actions.appendChild(useBtn);
    }

    return actions;
  }

  function appendMessage(text, role, options = {}) {
    const safeText = String(text || '');
    if (!safeText.trim()) {
      console.warn('[NAVI] Ignoring empty message for role:', role);
      return;
    }

    const wrapper = document.createElement('div');
    wrapper.className =
      role === 'user'
        ? 'navi-msg-row navi-msg-row-user'
        : 'navi-msg-row navi-msg-row-bot';

    const bubble = document.createElement('div');
    bubble.className =
      role === 'user' ? 'navi-bubble navi-bubble-user' : 'navi-bubble navi-bubble-bot';

    if (options.muted) bubble.classList.add('navi-bubble-muted');

    renderTextSegments(safeText, bubble);
    wrapper.appendChild(bubble);

    // Hover actions (only when there is visible text)
    if (safeText.trim()) {
      const actions = createMessageActions(role, safeText);
      if (actions) {
        wrapper.appendChild(actions);
      }
    }

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

  // ---------------------------------------------------------------------------
  // Form + input events
  // ---------------------------------------------------------------------------
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    vscode?.postMessage({ type: 'sendMessage', text });
    inputEl.value = '';
    inputEl.focus();
    showThinkingMessage();
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  // Header buttons
  root.querySelectorAll('.navi-icon-btn[data-action]').forEach((btn) => {
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

  // Model / Mode pickers
  modelPill.addEventListener('click', () => {
    vscode?.postMessage({
      type: 'modelPickerRequested',
      options: ['ChatGPT 5.1', 'gpt-4.2', 'o3-mini'],
    });
  });

  modePill.addEventListener('click', () => {
    vscode?.postMessage({
      type: 'modePickerRequested',
      options: ['Agent (full access)', 'Chat only', 'Read-only explorer'],
    });
  });

  // ---------------------------------------------------------------------------
  // Messages from extension host
  // ---------------------------------------------------------------------------
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
        const { bubble } = appendMessage('', 'bot', { allowEmpty: true });
        state.streamingBubble = bubble;
        break;
      }

      case 'botStreamDelta':
        if (!msg.messageId || msg.messageId !== state.streamingMessageId) return;
        if (!state.streamingBubble) {
          const { bubble: newBubble } = appendMessage('', 'bot', { allowEmpty: true });
          state.streamingBubble = newBubble;
        }
        state.streamingText += msg.text || '';
        renderTextSegments(state.streamingText, state.streamingBubble);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        break;

      case 'botStreamEnd':
        if (msg.messageId === state.streamingMessageId) {
          state.streamingMessageId = null;
          state.streamingBubble = null;
        }
        break;

      case 'insertCommandPrompt': {
        const input =
          document.querySelector('#navi-input') ||
          document.querySelector('.navi-input');
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

        const chip = document.createElement('div');
        chip.className = 'navi-attachment-chip';
        chip.textContent =
          files.length === 1
            ? `Attached: ${files[0].name}`
            : `Attached ${files.length} files`;

        const footer = document.querySelector('.navi-footer');
        if (footer) {
          const oldChip = footer.querySelector('.navi-attachment-chip');
          if (oldChip) oldChip.remove();
          footer.insertBefore(chip, footer.firstChild);
        }
        break;
      }

      case 'attachmentsCanceled':
        // no-op for now
        break;

      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // ---------------------------------------------------------------------------
  // Footer wiring (attach button + wand menu) – inside same IIFE
  // ---------------------------------------------------------------------------
  function initFooter() {
    const vscodeApi = vscode || (typeof window !== 'undefined' && window.vscode);
    console.log('[NAVI] Footer wiring: vscodeApi present?', !!vscodeApi);

    if (!vscodeApi) return;

    const attachBtn = document.getElementById('navi-attach-btn');
    const actionsBtn = document.getElementById('navi-actions-btn');
    const menu = document.getElementById('navi-command-menu');
    commandMenuEl = menu;

    console.log(
      '[NAVI] Footer wiring:',
      'attachBtn', !!attachBtn,
      'actionsBtn', !!actionsBtn,
      'menu', !!menu
    );

    function openCommandMenu(anchorButton) {
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

    // start hidden
    closeCommandMenu();

    // Attach button – currently just shows "coming soon" chip via host
    if (attachBtn) {
      attachBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        console.log('[NAVI] Attach button clicked');
        vscodeApi.postMessage({ type: 'pickAttachment' });
      });
    }

    // Wand button
    if (actionsBtn && commandMenuEl) {
      actionsBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        console.log('[NAVI] Actions button clicked');
        toggleCommandMenu(actionsBtn);
      });
    }

    // Command menu items
    if (menu) {
      const items = Array.from(menu.querySelectorAll('.navi-command-item'));
      console.log('[NAVI] Command menu items found:', items.length);

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
        const target = event.target;
        if (!target) return;
        if (event.key !== 'Enter' && event.key !== ' ') return;

        const item = target.closest
          ? target.closest(ITEM_SELECTOR)
          : null;
        if (!item) return;

        event.preventDefault();
        item.click();
      });
    }

    // Click outside to close
    document.addEventListener('click', (event) => {
      if (
        !commandMenuEl ||
        !commandMenuEl.classList.contains('navi-command-menu-visible')
      ) {
        return;
      }

      const target = event.target;
      if (!target) return;

      if (
        commandMenuEl.contains(target) ||
        actionsBtn?.contains(target)
      ) {
        return;
      }

      closeCommandMenu();
    });

    // ESC closes menu
    document.addEventListener('keydown', (event) => {
      if (
        event.key === 'Escape' &&
        commandMenuEl &&
        commandMenuEl.classList.contains('navi-command-menu-visible')
      ) {
        closeCommandMenu();
      }
    });
  }

  // Initialise footer once DOM is ready
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', initFooter, { once: true });
  } else {
    initFooter();
  }

  // Tell extension we're ready
  vscode?.postMessage({ type: 'ready' });
})();
