// media/panel.js
// NAVI chat panel with:
// - Logo from data-mascot-src
// - Welcome + new chat support
// - Model / mode selectors (handled in CSS + JS)
// - Streaming support via botStreamStart / botStreamDelta / botStreamEnd
// - "NAVI is thinking…" typing indicator

(function () {
  const vscode = acquireVsCodeApi();
  const root = document.getElementById('root');

  // Only allow mascotSrc as a safe URL (HTTPS, relative path, or data:image/*)
  function isSafeMascotSrc(url) {
    if (!url || typeof url !== 'string') return false;
    // Defensive: normalize and trim input to address tricky input vectors
    const normalizedUrl = url.trim().replace(/^[\s\u200B-\u200D\uFEFF]+|[\s\u200B-\u200D\uFEFF]+$/g, '');
    // Lowercase protocol portion only for scheme checks
    const protoMatch = normalizedUrl.match(/^([a-zA-Z]+):/);
    const proto = protoMatch ? protoMatch[1].toLowerCase() : '';
    // Reject any javascript: or vbscript:, etc.
    if (proto === 'javascript' || proto === 'vbscript' || proto === 'data' && !/^data:image\/(png|jpeg|jpg|gif|webp);base64,/.test(normalizedUrl)) return false;
    // Allow HTTPS, relative, and certain image data URLs only
    if (/^(https:\/\/|\.\/|\/)/.test(normalizedUrl)) return true;
    if (/^data:image\/(png|jpeg|jpg|gif|webp);base64,/.test(normalizedUrl)) return true;
    return false;
  }

  const state = {
    streamingMessageId: null,
    streamingBubble: null,
    streamingText: '',
    thinking: false,
  };

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

  // ---------- Logo ----------
  const mascotSrc = root.getAttribute('data-mascot-src');
  const logoImg = root.querySelector('.navi-logo');
  if (mascotSrc && logoImg) {
    if (isSafeMascotSrc(mascotSrc)) {
      logoImg.src = mascotSrc;
    }
  }

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
    logoSvg = logoHost.querySelector('svg');
  }

  function setThinking(on) {
    if (!logoSvg) return;
    if (on) logoSvg.classList.add('thinking');
    else logoSvg.classList.remove('thinking');
  }

  function celebrateOnce() {
    if (!logoSvg) return;
    logoSvg.classList.add('navi-logo-celebrate');
    setTimeout(() => logoSvg && logoSvg.classList.remove('navi-logo-celebrate'), 600);
  }

  const messagesEl = document.getElementById('navi-messages');
  const formEl = document.getElementById('navi-form');
  const inputEl = document.getElementById('navi-input');
  const attachBtn = document.getElementById('navi-attach');

  let typingEl = null;

  function persist() {
    vscode.setState({ messages });
  }

  // ---------- Render helpers ----------
  function renderTextSegments(text, container) {
    const lines = String(text).split('\n');
    lines.forEach((line, idx) => {
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
      if (idx < lines.length - 1) {
        container.appendChild(document.createElement('br'));
      }
    });
  }

  // Support markdown-style ``` fenced blocks + heuristics for raw code / JSON
  function renderMessageContent(text, container) {
    const raw = String(text);

    // Early check: if markdown fences exist, skip expensive heuristics
    if (raw.includes('```')) {
      // Handle standard markdown-style ``` fenced blocks
      const segments = raw.split('```');
      for (let i = 0; i < segments.length; i++) {
        if (i % 2 === 0) {
          // Text segment
          renderTextSegments(segments[i], container);
        } else {
          // Code segment
          const pre = document.createElement('pre');
          pre.className = 'navi-code-block';
          const codeEl = document.createElement('code');
          codeEl.textContent = segments[i].trim();
          pre.appendChild(codeEl);
          container.appendChild(pre);
        }
      }
      return;
    }

    // Skip heuristics for very short strings (performance optimization)
    if (raw.length < 20) {
      renderTextSegments(raw, container);
      return;
    }

    // 1) Improved heuristic: looks like CSS/JS (braces + semicolons + code keywords)
    const looksLikeCssOrJs =
      raw.includes('{') &&
      raw.includes('}') &&
      (raw.match(/;/g) || []).length >= 3 && // Require at least 3 semicolons
      (
        raw.includes('function') ||
        raw.includes('const') ||
        raw.includes('let') ||
        raw.includes('var') ||
        /[.#][a-zA-Z]/.test(raw) ||
        /:\s*[^;]+;/.test(raw) // Property: value; pattern
      );

    // 2) Heuristic: looks like JSON (braces + key: value with quotes)
    const looksLikeJson =
      raw.includes('{') &&
      raw.includes('}') &&
      /"[^"]*"\s*:/.test(raw);

    if (looksLikeCssOrJs || looksLikeJson) {
      const pre = document.createElement('pre');
      pre.className = 'navi-code-block';
      const codeEl = document.createElement('code');
      codeEl.textContent = raw.trim();
      pre.appendChild(codeEl);
      container.appendChild(pre);
      return;
    }

    // Default: render as regular text
    renderTextSegments(raw, container);
  }

  function renderMessage(msg) {
    if (!messagesEl) return;
    const { role, text } = msg;

    const row = document.createElement('div');
    row.className =
      role === 'user' ? 'navi-msg-row navi-msg-row-user' : 'navi-msg-row navi-msg-row-bot';

    const bubble = document.createElement('div');
    bubble.className =
      role === 'user' ? 'navi-bubble navi-bubble-user' : 'navi-bubble navi-bubble-bot';

    renderMessageContent(text, bubble);

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
    if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
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
    setThinking(true);
  }

  function hideTyping() {
    if (typingEl && typingEl.parentElement) {
      typingEl.parentElement.removeChild(typingEl);
    }
    typingEl = null;
    setThinking(false);
  }

  // ---------- Initial render ----------
  renderAll();

  // ---------- Form / keyboard ----------
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    const currentModel = modelPill ? modelPill.textContent.trim() : 'ChatGPT 5.1';
    const currentMode = modePill ? modePill.textContent.trim() : 'Agent (full access)';

    addMessage('user', text);
    vscode.postMessage({
      type: 'sendMessage',
      text,
      model: currentModel,
      mode: currentMode
    });

    inputEl.value = '';
    inputEl.focus();
  });

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });



  // ---------- Dropdown infra (shared for model/mode/attach) ----------
  const MODEL_OPTIONS = ['ChatGPT 5.1', 'gpt-4.2', 'o3-mini'];
  const MODE_OPTIONS = ['Agent (full access)', 'Safe (read-only)', 'Audit (explain only)'];
  const ATTACH_OPTIONS = [
    { id: 'file', label: 'File from workspace' },
    { id: 'snippet', label: 'Code snippet' },
    { id: 'screenshot', label: 'Screenshot / image' },
    { id: 'link', label: 'Repo / URL' },
  ];

  const modelPill = document.getElementById('navi-model-pill');
  const modePill = document.getElementById('navi-mode-pill');

  let openDropdown = null;
  /** @type {'model'|'mode'|'attach'|null} */
  let openDropdownKind = null;

  function closeDropdown() {
    if (openDropdown && openDropdown.parentElement) {
      openDropdown.parentElement.removeChild(openDropdown);
    }
    openDropdown = null;
    openDropdownKind = null;
  }

  function createDropdown(kind, anchorEl) {
    closeDropdown();

    const menu = document.createElement('div');
    menu.className = 'navi-dropdown';
    menu.style.position = 'fixed';

    let options;
    if (kind === 'model') options = MODEL_OPTIONS.map((v) => ({ id: v, label: v }));
    else if (kind === 'mode') options = MODE_OPTIONS.map((v) => ({ id: v, label: v }));
    else options = ATTACH_OPTIONS;

    options.forEach((opt) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'navi-dropdown-item';
      item.textContent = opt.label;
      item.addEventListener('click', () => {
        closeDropdown();
        if (kind === 'model') {
          if (modelPill) modelPill.textContent = `Model: ${opt.label}`;
          vscode.postMessage({ type: 'modelChanged', value: opt.label });
        } else if (kind === 'mode') {
          if (modePill) modePill.textContent = `Mode: ${opt.label}`;
          vscode.postMessage({ type: 'modeChanged', value: opt.label });
        } else {
          vscode.postMessage({ type: 'attachTypeSelected', value: opt.id });
        }
      });
      menu.appendChild(item);
    });

    document.body.appendChild(menu);

    const pillRect = anchorEl.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();

    let left = pillRect.left;
    if (left + menuRect.width > window.innerWidth - 8) {
      left = window.innerWidth - menuRect.width - 8;
    }

    // Prefer opening upwards so it doesn't get cut off
    let top = pillRect.top - menuRect.height - 8;
    if (top < 8) {
      top = pillRect.bottom + 8;
      if (top + menuRect.height > window.innerHeight - 8) {
        top = window.innerHeight - menuRect.height - 8;
      }
    }

    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;

    openDropdown = menu;
    openDropdownKind = kind;
  }

  // ---------- Attach button dropdown ----------
  if (attachBtn) {
    attachBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (openDropdown && openDropdownKind === 'attach') {
        closeDropdown();
      } else {
        createDropdown('attach', attachBtn);
      }
    });
  }

  // ---------- Header buttons ----------
  root.querySelectorAll('.navi-icon-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.getAttribute('data-action');
      if (!action) return;

      if (action === 'newChat') {
        vscode.postMessage({ type: 'buttonAction', action: 'newChat' });
      } else if (action === 'mcp') {
        vscode.postMessage({ type: 'buttonAction', action: 'connectors' });
      } else if (action === 'settings') {
        vscode.postMessage({ type: 'buttonAction', action: 'settings' });
      }
    });
  });

  // Model / Mode dropdowns (one-click switch between them)
  if (modelPill) {
    modelPill.addEventListener('click', (e) => {
      e.stopPropagation();
      createDropdown('model', modelPill);
    });
  }

  if (modePill) {
    modePill.addEventListener('click', (e) => {
      e.stopPropagation();
      createDropdown('mode', modePill);
    });
  }

  document.addEventListener('click', () => {
    closeDropdown();
  });

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
        celebrateOnce();
        break;
      case 'showTyping':
        showTyping();
        break;
      case 'hideTyping':
        hideTyping();
        break;
      default:
        console.log('[AEP] Unknown message in webview:', msg);
    }
  });

  // ---------- Tell extension we're ready ----------
  vscode.postMessage({ type: 'ready', hasHistory: messages.length > 0 });
})();