// media/panel.js
// Minimal, working NAVI chat UI with:
// - Logo loaded from data-mascot-src
// - Welcome message
// - Enter-to-send
// - Input cleared after send
// - Header buttons wired (new chat, connectors, settings)

(function () {
  const vscode = acquireVsCodeApi();

  console.log('[AEP] NAVI panel.js booting…');

  const root = document.getElementById('root');

  // ---------- Basic layout ----------
  root.innerHTML = `
    <div class="navi-shell">
      <header class="navi-header">
        <div class="navi-brand">
          <img class="navi-logo" alt="NAVI" />
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

  // ---------- Wire logo ----------
  const mascotSrc = root.getAttribute('data-mascot-src');
  const logoImg = root.querySelector('.navi-logo');
  if (mascotSrc && logoImg) {
    logoImg.src = mascotSrc;
  }

  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');

  // ---------- Helpers ----------
  function appendMessage(text, role) {
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
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function clearChat() {
    messagesEl.innerHTML = '';
  }

  // ---------- Form submit / keyboard ----------
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    vscode.postMessage({ type: 'sendMessage', text });

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
        appendMessage(msg.text, 'bot');
        break;
      case 'clearChat':
        clearChat();
        break;
      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // Tell the extension we're ready so it can send the welcome
  vscode.postMessage({ type: 'ready' });
})();