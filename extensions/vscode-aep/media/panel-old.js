// media/panel.js
// NAVI chat UI with:
// - Inline NAVI fox SVG (animated)
// - Persistent history via vscode.getState/setState
// - Welcome message only when there is no history
// - Enter-to-send + input cleared
// - Header buttons wired (new chat, connectors, settings)
// - Typing indicator while NAVI is "thinking"
// - Model / Mode pill click events

(function () {
  const vscode = acquireVsCodeApi();
  console.log('[AEP] NAVI panel.js booting…');

  const root = document.getElementById('root');

  // ---------- Restore any previous state ----------
  const prevState = vscode.getState() || {};
  /** @type {{role:'user'|'bot',text:string}[]} */
  let messagesRaw = Array.isArray(prevState.messages) ? prevState.messages : [];

  // Filter out corrupted / legacy entries (prevents "undefined" bubbles)
  let messages = messagesRaw
    .filter((m) => m && (m.role === 'user' || m.role === 'bot') && typeof m.text === 'string')
    .map((m) => ({ role: m.role, text: m.text.trim() }))
    .filter((m) => m.text.length > 0);

  // ---------- Layout skeleton ----------
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
          <button class="navi-pill" id="navi-model-pill" type="button">Model: ChatGPT 5.1</button>
          <button class="navi-pill" id="navi-mode-pill" type="button">Mode: Agent (full access)</button>
        </div>
      </footer>
    </div>
  `;

  // ---------- Inline NAVI fox SVG (your final version) ----------
  const logoHost = root.querySelector('.navi-logo-inline');
  if (logoHost) {
    logoHost.innerHTML = `
<svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" aria-label="NAVI fox">
  <defs>
    <linearGradient id="p" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF8A3D"/>
      <stop offset="100%" stop-color="#FF5E7E"/>
    </linearGradient>

    <style>
      @keyframes nod {0%{transform:rotate(0)}50%{transform:rotate(-2.5deg)}100%{transform:rotate(0)}}
      @keyframes blink {0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
      @keyframes pulse {
        0%{r:22; opacity:.55}
        70%{r:28; opacity:0}
        100%{r:28; opacity:0}
      }
      @keyframes earFlick {0%{transform:rotate(0)}40%{transform:rotate(-12deg)}80%{transform:rotate(10deg)}100%{transform:rotate(0)}}
      @keyframes tailWave {0%{transform:rotate(0)}50%{transform:rotate(12deg)}100%{transform:rotate(0)}}

      #head{transform-origin:22px 22px; animation:nod 5s ease-in-out infinite}
      .eye{animation:blink 6s ease-in-out infinite; transform-origin:50% 50%}
      .pulse-ring{fill:none; stroke:url(#p); stroke-width:2.4; opacity:0}

      svg.thinking .pulse-ring{animation:pulse 2s ease-out infinite}
      svg.celebrate #earL, svg.celebrate #earR{animation:earFlick .65s ease-out 1}
      svg.celebrate #tail{animation:tailWave .7s ease-out 1}
    </style>
  </defs>

  <circle class="pulse-ring" cx="22" cy="22" r="22"/>

  <g id="tail" transform="translate(33,29)">
    <path d="M0 0 C7 0 9 7 3 10 C-1 12 -2 7 0 0 Z" fill="url(#p)" opacity=".85"/>
  </g>

  <g id="head">
    <path d="M22 5 L36 16 33 34 22 39 11 34 8 16Z" fill="url(#p)"/>

    <g id="earL" transform="translate(12,14)">
      <path d="M0 3 L6 -1 4 6 Z" fill="#fff" opacity=".95"/>
    </g>
    <g id="earR" transform="translate(26,14)">
      <path d="M6 3 L0 -1 2 6 Z" fill="#fff" opacity=".95"/>
    </g>

    <ellipse cx="18" cy="24" rx="1.6" ry="1.6" class="eye" fill="#0F172A"/>
    <ellipse cx="26" cy="24" rx="1.6" ry="1.6" class="eye" fill="#0F172A"/>
    <rect x="20.3" y="26.5" width="3.4" height="1.2" rx=".6" fill="#0F172A" opacity=".75"/>
  </g>
</svg>`;
  }

  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');

  let typingEl = null;

  function persist() {
    vscode.setState({ messages });
  }

  // ---------- Rendering helpers ----------
  function renderMessage(msg) {
    if (!messagesEl) return;
    const { role, text } = msg;

    const row = document.createElement('div');
    row.className =
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

    row.appendChild(bubble);
    messagesEl.appendChild(row);
  }

  function renderAll() {
    if (!messagesEl) return;
    messagesEl.innerHTML = '';
    messages.forEach(renderMessage);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, text) {
    const cleanText = String(text || '').trim();
    if (!cleanText) return;
    const msg = { role, text: cleanText };
    messages.push(msg);
    renderMessage(msg);
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
    persist();
  }

  function clearChat() {
    messages = [];
    if (messagesEl) messagesEl.innerHTML = '';
    persist();
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

  // ---------- Initial render from restored state ----------
  renderAll();

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

  // ---------- Model / Mode pills ----------
  const modelPill = document.getElementById('navi-model-pill');
  const modePill = document.getElementById('navi-mode-pill');

  if (modelPill) {
    modelPill.addEventListener('click', () => {
      vscode.postMessage({ type: 'chooseModel' });
    });
  }
  if (modePill) {
    modePill.addEventListener('click', () => {
      vscode.postMessage({ type: 'chooseMode' });
    });
  }

  // ---------- Handle messages from extension ----------
  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    switch (msg.type) {
      case 'botMessage':
        hideTyping();
        if (typeof msg.text === 'string') {
          addMessage('bot', msg.text);
        }
        break;
      case 'clearChat':
        hideTyping();
        clearChat();
        break;
      case 'updateModelLabel':
        if (modelPill && typeof msg.label === 'string') modelPill.textContent = msg.label;
        break;
      case 'updateModeLabel':
        if (modePill && typeof msg.label === 'string') modePill.textContent = msg.label;
        break;
      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // ---------- Tell extension we're ready ----------
  vscode.postMessage({ type: 'ready', hasHistory: messages.length > 0 });
})();