// media/panel.js
// NAVI chat UI with:
// - Inline mascot logo (no path/CSP issues)
// - Persistent history via vscode.getState/setState
// - Welcome message from extension (only on first load)
// - Enter-to-send + input cleared
// - Header buttons wired (new chat, connectors, settings)
// - Typing indicator while NAVI is "thinking"

(function () {
  const vscode = acquireVsCodeApi();

  console.log('[AEP] NAVI panel.js booting…');

  const root = document.getElementById('root');
  const prevState = vscode.getState() || { messages: [] };

  /** @type {{role: 'user' | 'bot', text: string}[]} */
  let messages = Array.isArray(prevState.messages) ? prevState.messages : [];

  // ---------- Basic layout ----------
  root.innerHTML = `
    <div class="navi-shell">
      <header class="navi-header">
        <div class="navi-brand">
          <div class="navi-logo-wrap">
            <div class="navi-logo-inline" aria-label="NAVI fox"></div>
          </div>
          <div class="navi-title-block">
            <div class="navi-title">NAVI — Autonomous Engineering Assistant</div>
            <div class="navi-subtitle">Your AI engineering copilot inside VS Code</div>
          </div>
        </div>
        <div class="navi-header-actions">
          <button class="navi-icon-btn" data-action="newChat" title="New chat">
            <span>⊕</span>
          </button>
          <button class="navi-icon-btn" data-action="connectors" title="Connect repos & tools">
            <span>🔌</span>
          </button>
          <button class="navi-icon-btn" data-action="settings" title="Settings">
            <span>⚙︎</span>
          </button>
        </div>
      </header>

      <main class="navi-main">
        <div id="navi-messages" class="navi-messages"></div>
      </main>

      <footer class="navi-footer">
        <form id="navi-form" class="navi-form">
          <button type="button" id="navi-attach" class="navi-attach-btn" title="Attach files or code">
            +
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
          <div class="navi-pill" id="navi-model-pill">Model: ChatGPT 5.1</div>
          <div class="navi-pill" id="navi-mode-pill">Mode: Agent (full access)</div>
        </div>
      </footer>
    </div>
  `;

  // ---------- Inline logo SVG (no file path issues) ----------
  const logoHost = root.querySelector('.navi-logo-inline');
  if (logoHost) {
    logoHost.innerHTML = `
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" aria-label="NAVI fox">
        <defs>
          <linearGradient id="navifox-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#FF8A3D"/>
            <stop offset="100%" stop-color="#FF5E7E"/>
          </linearGradient>
        </defs>
        <circle cx="22" cy="22" r="22" fill="#020617"/>
        <path d="M10 15 L20 8 L22.5 16 Z" fill="url(#navifox-grad)"/>
        <path d="M34 15 L24 8 L21.5 16 Z" fill="url(#navifox-grad)"/>
        <path d="M13 20 Q22 11 31 20 L30 30 Q22 36 14 30 Z" fill="url(#navifox-grad)"/>
        <circle cx="18" cy="22" r="1.4" fill="#020617"/>
        <circle cx="26" cy="22" r="1.4" fill="#020617"/>
        <path d="M19 26 Q22 28.5 25 26" stroke="#020617" stroke-width="1.4" stroke-linecap="round" fill="none"/>
      </svg>
    `;
  }

  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');

  // Typing indicator state
  let typingEl = null;

  // ---------- Persistence ----------
  function persistState() {
    vscode.setState({ messages });
  }

  // ---------- Rendering helpers ----------
  function renderMessage(msg) {
    if (!messagesEl) return;
    const { role, text } = msg;

    const wrapper = document.createElement('div');
    wrapper.className =
      role === 'user' ? 'navi-msg-row navi-msg-row-user' : 'navi-msg-row navi-msg-row-bot';

    const bubble = document.createElement('div');
    bubble.className =
      role === 'user' ? 'navi-bubble navi-bubble-user' : 'navi-bubble navi-bubble-bot';

    const lines = String(text).split('\n');
    lines.forEach((line, idx) => {
      if (line.startsWith('> ')) {
        const quote = document.createElement('div');
        quote.className = 'navi-line-quote';
        quote.textContent = line.slice(2);
        bubble.appendChild(quote);
      } else {
        const p = document.createElement('div');
        p.textContent = line;
        bubble.appendChild(p);
      }
      if (idx < lines.length - 1) {
        bubble.appendChild(document.createElement('br'));
      }
    });

    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
  }

  function renderAllMessages() {
    if (!messagesEl) return;
    messagesEl.innerHTML = '';
    messages.forEach(renderMessage);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, text) {
    messages.push({ role, text });
    renderMessage({ role, text });
    messagesEl.scrollTop = messagesEl.scrollHeight;
    persistState();
  }

  function clearChat() {
    messages = [];
    if (messagesEl) {
      messagesEl.innerHTML = '';
    }
    persistState();
  }

  // ---------- Typing indicator ----------
  function showTyping() {
    if (!messagesEl) return;
    hideTyping();

    const row = document.createElement('div');
    row.className = 'navi-msg-row navi-msg-row-bot';

    const bubble = document.createElement('div');
    bubble.className = 'navi-bubble navi-bubble-bot navi-bubble-typing';

    const label = document.createElement('span');
    label.className = 'navi-typing-label';
    label.textContent = 'NAVI is thinking';

    const dots = document.createElement('span');
    dots.className = 'navi-typing-dots';
    dots.innerHTML = `
      <span class="navi-typing-dot"></span>
      <span class="navi-typing-dot"></span>
      <span class="navi-typing-dot"></span>
    `;

    bubble.appendChild(label);
    bubble.appendChild(dots);
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    typingEl = row;
  }

  function hideTyping() {
    if (typingEl && typingEl.parentElement) {
      typingEl.parentElement.removeChild(typingEl);
    }
    typingEl = null;
  }

  // ---------- Restore any previous messages ----------
  renderAllMessages();

  // ---------- Form submit / keyboard ----------
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    addMessage('user', text);
    vscode.postMessage({ type: 'sendMessage', text });

    showTyping();

    inputEl.value = '';
    inputEl.focus();
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  // ---------- Header buttons ----------
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

  // ---------- Handle messages from extension ----------
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    switch (msg.type) {
      case 'botMessage':
        hideTyping();
        if (typeof msg.text === 'string' && msg.text.trim()) {
          addMessage('bot', msg.text);
        }
        break;
      case 'clearChat':
        hideTyping();
        clearChat();
        break;
      case 'navi.agent.event':
        // Handle generative repair notifications
        if (msg.event?.type === 'navi.fix.result') {
          hideTyping();
          const data = msg.event.data;

          if (data?.source === 'multi-file-repair') {
            addMessage('bot', `🚀 ${data.message || 'Multi-file repair completed'}`);
          } else if (data?.source === 'generative-repair') {
            addMessage('bot', `✅ ${data.message || 'File repaired automatically'}`);
          } else {
            addMessage('bot', `ℹ️ ${data?.message || 'Fix applied'}`);
          }
        }
        break;
      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // Tell the extension we're ready, and whether we already have history
  vscode.postMessage({ type: 'ready', hasHistory: messages.length > 0 });
})();