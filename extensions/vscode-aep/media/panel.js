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

  // Streaming state
  const state = {
    streamingMessageId: null,
    streamingBubble: null,
    streamingText: '',
    thinking: false,
  };

  // Thinking message helpers
  let thinkingMessageEl = null;

  function showThinkingMessage() {
    const messagesEl = document.getElementById('navi-messages');
    if (!messagesEl) return;

    // Make sure we never have duplicates
    hideThinkingMessage();

    const bubble = document.createElement('div');
    bubble.className = 'navi-message navi-message-thinking';
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

  // Simple toast helper (used by Attach button)
  function showToast(message) {
    let toast = document.getElementById('navi-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'navi-toast';
      toast.className = 'navi-toast';
      document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.classList.add('navi-toast-visible');

    clearTimeout(showToast._timeout);
    showToast._timeout = setTimeout(() => {
      toast.classList.remove('navi-toast-visible');
    }, 4000);
  }

  // Create the UI
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
              
              <!-- Background circle -->
              <circle cx="22" cy="22" r="20" fill="#020617"/>
              
              <!-- Tail (behind head) -->
              <g transform="translate(33,29)">
                <path d="M0 0 C7 0 9 7 3 10 C-1 12 -2 7 0 0 Z" fill="url(#naviFoxGrad)" opacity="0.85"/>
              </g>
              
              <!-- Fox head -->
              <g>
                <path d="M22 5 L36 16 33 34 22 39 11 34 8 16Z" fill="url(#naviFoxGrad)"/>
                
                <!-- ears -->
                <g transform="translate(12,14)">
                  <path d="M0 3 L6 -1 4 6 Z" fill="#fff" opacity="0.95"/>
                </g>
                <g transform="translate(26,14)">
                  <path d="M6 3 L0 -1 2 6 Z" fill="#fff" opacity="0.95"/>
                </g>
                
                <!-- eyes + nose -->
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

        <!-- Command menu overlay (now anchored to footer) -->
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

  // Setup NAVI fox logo
  const logoContainer = root.querySelector('.navi-logo-container');
  const logoSvg = root.querySelector('.navi-logo-svg');

  if (logoContainer && logoSvg) {
    // Style the container
    logoContainer.style.cssText = `
      width: 34px;
      height: 34px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 18px rgba(129, 140, 248, 0.6);
    `;

    // Style the SVG
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

  // Get DOM elements
  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');
  const attachBtn = document.getElementById('navi-attach');
  const modelPill = document.getElementById('navi-model-pill');
  const modePill = document.getElementById('navi-mode-pill');

  // Message rendering
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

  function appendMessage(text, role, options = {}) {
    // Guard against empty messages to prevent phantom bubbles
    const safeText = String(text || '');
    if (!safeText.trim()) {
      console.warn('[NAVI] Ignoring empty message for role:', role);
      return;
    }

    const wrapper = document.createElement('div');
    wrapper.className = role === 'user' ? 'navi-msg-row navi-msg-row-user' : 'navi-msg-row navi-msg-row-bot';

    const bubble = document.createElement('div');
    bubble.className = role === 'user' ? 'navi-bubble navi-bubble-user' : 'navi-bubble navi-bubble-bot';

    if (options.muted) bubble.classList.add('navi-bubble-muted');

    renderTextSegments(safeText, bubble);
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

  // Old thinking indicator system - now redirects to new unified thinking system
  let thinkingRow = null;

  function setThinking(isThinking) {
    state.thinking = isThinking;
    // Redirect to new unified thinking message system
    if (isThinking) {
      showThinkingMessage();
    } else {
      hideThinkingMessage();
    }
  }

  // Event handlers
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    vscode.postMessage({ type: 'sendMessage', text });
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

  // Attach button handler moved to avoid conflicts - see PR-2 section

  // Header buttons
  root.querySelectorAll('.navi-icon-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.getAttribute('data-action');
      if (!action) return;

      if (action === 'newChat') {
        vscode.postMessage({ type: 'newChat' });
      } else if (action === 'connectors') {
        vscode.postMessage({ type: 'openConnectors' });
      } else if (action === 'settings') {
        vscode.postMessage({ type: 'openSettings' });
      }
    });
  });

  // Model/mode pills
  modelPill.addEventListener('click', () => {
    vscode.postMessage({ type: 'modelPickerRequested', options: ['ChatGPT 5.1', 'gpt-4.2', 'o3-mini'] });
  });

  modePill.addEventListener('click', () => {
    vscode.postMessage({ type: 'modePickerRequested', options: ['Agent (full access)', 'Chat only', 'Read-only explorer'] });
  });

  // Messages from extension
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

      case 'botStreamStart':
        hideThinkingMessage();
        state.streamingMessageId = msg.messageId;
        state.streamingText = '';
        const { bubble } = appendMessage('', 'bot');
        state.streamingBubble = bubble;
        break;

      case 'botStreamDelta':
        if (!msg.messageId || msg.messageId !== state.streamingMessageId) return;
        if (!state.streamingBubble) {
          const { bubble: newBubble } = appendMessage('', 'bot');
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
        const input = document.querySelector('#navi-input') || document.querySelector('.navi-input');
        if (input) {
          input.value = msg.prompt || '';
          input.focus();
        }
        break;
      }

      case 'resetChat': {
        // Clear messages & show welcome bubble again
        clearChat();
        appendMessage(
          "New chat started! How can I help you today?",
          'bot'
        );
        break;
      }

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
        // optional: quietly ignore for now
        break;

      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // Tell extension we're ready
  vscode.postMessage({ type: 'ready' });
})();

// ---------------------------------------------------------------------------
// NAVI footer controls + command menu wiring (attach + wand)
// ---------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', () => {
  const vscodeApi =
    (typeof window !== 'undefined' && window.vscode) || null;

  console.log('[NAVI] Footer wiring: vscodeApi present?', !!vscodeApi);

  if (!vscodeApi) {
    console.warn(
      '[NAVI] vscode API instance not found – footer wiring disabled.'
    );
    return;
  }

  const attachBtn = document.getElementById('navi-attach-btn');
  const actionsBtn = document.getElementById('navi-actions-btn');
  const commandMenu = document.getElementById('navi-command-menu');

  console.log(
    '[NAVI] Footer wiring:',
    'attachBtn', !!attachBtn,
    'actionsBtn', !!actionsBtn,
    'commandMenu', !!commandMenu
  );

  // ---------- Command menu (wand) ----------

  let commandMenuOpen = false;

  function openCommandMenu() {
    if (!commandMenu) return;
    commandMenu.classList.remove('navi-command-menu-hidden');
    commandMenu.classList.add('navi-command-menu-visible');
    commandMenuOpen = true;
  }

  function closeCommandMenu() {
    if (!commandMenu) return;
    commandMenu.classList.remove('navi-command-menu-visible');
    commandMenu.classList.add('navi-command-menu-hidden');
    commandMenuOpen = false;
  }

  function toggleCommandMenu() {
    if (commandMenuOpen) {
      closeCommandMenu();
    } else {
      openCommandMenu();
    }
  }

  // ---------- Attachment button ----------

  // Attach button – show inline "coming soon" chip and close wand menu if open
  if (attachBtn) {
    attachBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      console.log('[NAVI] Attach button clicked');

      // Close the quick-actions (wand) menu so they don't overlap
      closeCommandMenu();

      const footer = document.querySelector('.navi-footer');
      if (!footer) return;

      // Reuse/update a single chip so it doesn't spam the UI
      let chip = footer.querySelector('.navi-attachment-chip');
      if (!chip) {
        chip = document.createElement('div');
        chip.className = 'navi-attachment-chip';
        footer.insertBefore(chip, footer.firstChild);
      }

      chip.textContent =
        'Attachment flow is not implemented yet – coming soon.';
    });
  }

  // Start menu closed
  closeCommandMenu();

  // ---------- Wand button ----------

  // Wire up wand button
  if (actionsBtn && commandMenu) {
    actionsBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      console.log('[NAVI] Actions button clicked');
      toggleCommandMenu();
    });

    // Close when clicking anywhere outside the menu / wand
    document.addEventListener('click', (event) => {
      if (!commandMenuOpen) return;
      const target = event.target;
      if (
        target instanceof Node &&
        !commandMenu.contains(target) &&
        target !== actionsBtn
      ) {
        closeCommandMenu();
      }
    });
  }

  // Command menu items – use event delegation so clicks anywhere
  // inside the button (icon, text, etc.) are handled reliably.
  if (commandMenu) {
    const items = Array.from(
      commandMenu.querySelectorAll('.navi-command-item')
    );
    console.log('[NAVI] Command menu items found:', items.length);

    const ITEM_SELECTOR = '.navi-command-item';

    commandMenu.addEventListener('click', (event) => {
      const target = event.target;
      if (!target) return;

      const item = target.closest
        ? target.closest(ITEM_SELECTOR)
        : null;

      if (!item) {
        return; // clicked on the purple frame, not on a button
      }

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

    // Keyboard support: Enter on a focused item acts like click.
    commandMenu.addEventListener('keydown', (event) => {
      const target = event.target;
      if (!target) return;

      if (event.key === 'Enter' || event.key === ' ') {
        const item = target.closest
          ? target.closest(ITEM_SELECTOR)
          : null;
        if (!item) return;

        event.preventDefault();
        item.click();
      }
    });
  }

  // Click outside → close menu
  document.addEventListener('click', (event) => {
    if (!commandMenuOpen) return;

    const target = event.target;
    if (!target) return;

    if (
      commandMenu && commandMenu.contains(target) ||
      actionsBtn?.contains(target)
    ) {
      return;
    }

    closeCommandMenu();
  });

  // ESC closes menu
  document.addEventListener('keydown', (event) => {
    if (!commandMenuOpen) return;
    if (event.key === 'Escape') {
      closeCommandMenu();
    }
  });
});