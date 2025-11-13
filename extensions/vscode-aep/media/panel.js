(function () {
  const vscode = acquireVsCodeApi();
  const $ = (s, el = document) => el.querySelector(s);

  const messages = $('#messages');
  const input = $('#input');
  const attachBtn = $('#attachBtn');
  const attachMenu = $('#attachMenu');
  const sendBtn = $('#sendBtn');

  const modelChip = $('#modelChip');
  const modeChip = $('#modeChip');
  const modelMenu = $('#modelMenu');
  const modeMenu = $('#modeMenu');
  const modelValBottom = $('#modelValBottom');
  const modeValBottom = $('#modeValBottom');

  const headerActions = document.querySelectorAll('.top-icon');

  const MODELS = [
    'OpenAI GPT-4o — Flagship',
    'OpenAI GPT-4o-mini',
    'Anthropic Claude 3.5 Sonnet',
    'Anthropic Claude 3.5 Haiku',
    'Llama 3.1 405B (API)',
    'Bring your own API key…'
  ];

  const MODES = [
    'Agent (full access)',
    'Lightweight inline hints',
    'Explain only'
  ];

  const state = vscode.getState() || {
    attachOpen: false,
    model: MODELS[0],
    mode: MODES[0]
  };

  // ---------- Persistence helpers ----------

  function persist() {
    vscode.setState({
      attachOpen: attachMenu.classList.contains('open'),
      model: state.model,
      mode: state.mode
    });
  }

  // ---------- Attach menu ----------

  function setAttach(open) {
    attachMenu.classList.toggle('open', open);
    attachMenu.setAttribute('aria-hidden', String(!open));
    persist();
  }

  setAttach(state.attachOpen);

  attachBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    setAttach(!attachMenu.classList.contains('open'));
  });

  document.addEventListener('click', (e) => {
    if (!attachMenu.classList.contains('open')) return;
    const path = e.composedPath();
    if (!path.includes(attachMenu) && !path.includes(attachBtn)) {
      setAttach(false);
    }
  });

  // ---------- Dropdowns (model / mode) ----------

  function setModel(v) {
    if (!v) return;
    state.model = v;
    if (modelValBottom) modelValBottom.textContent = v;
    persist();
  }

  function setMode(v) {
    if (!v) return;
    state.mode = v;
    if (modeValBottom) modeValBottom.textContent = v;
    persist();
  }

  setModel(state.model);
  setMode(state.mode);

  function toggleMenu(menu, open) {
    if (!menu) return;
    const shouldOpen = typeof open === 'boolean'
      ? open
      : !menu.classList.contains('open');
    menu.classList.toggle('open', shouldOpen);
    menu.setAttribute('aria-hidden', String(!shouldOpen));
  }

  modelChip?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleMenu(modelMenu);
    toggleMenu(modeMenu, false);
  });

  modeChip?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleMenu(modeMenu);
    toggleMenu(modelMenu, false);
  });

  modelMenu?.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-model]');
    if (!btn) return;
    setModel(btn.getAttribute('data-model'));
    toggleMenu(modelMenu, false);
  });

  modeMenu?.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-mode]');
    if (!btn) return;
    setMode(btn.getAttribute('data-mode'));
    toggleMenu(modeMenu, false);
  });

  document.addEventListener('click', (e) => {
    const path = e.composedPath();
    if (!path.includes(modelChip)) toggleMenu(modelMenu, false);
    if (!path.includes(modeChip)) toggleMenu(modeMenu, false);
  });

  // ---------- Keyboard shortcuts ----------

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      setAttach(false);
      toggleMenu(modelMenu, false);
      toggleMenu(modeMenu, false);
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  // ---------- Input auto-growth ----------

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });

  // ---------- Header actions ----------

  headerActions.forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.getAttribute('data-action');
      switch (action) {
        case 'refresh': {
          // Just drop a small hint bubble for now
          addBubble('Resetting context (demo only). In the real agent this would restart NAVI for this workspace.', 'bot');
          break;
        }
        case 'new': {
          messages.innerHTML = '';
          vscode.postMessage({ type: 'ready' });
          break;
        }
        case 'focus-code': {
          addBubble('Code focus mode will prioritise reasoning about the active file and test failures (UI stub for now).', 'bot');
          break;
        }
        case 'sources': {
          addBubble(
            'Connections panel (coming soon): link MCP servers and tools like Slack, Teams, Jira, GitHub, Bitbucket, cloud, wikis, and more.',
            'bot'
          );
          break;
        }
        case 'settings': {
          vscode.postMessage({ type: 'openSettings' });
          break;
        }
        default:
          break;
      }
    });
  });

  // ---------- Sending & rendering ----------

  sendBtn.addEventListener('click', send);

  function send() {
    const text = input.value.trim();
    if (!text) return;

    addBubble(text, 'user');
    vscode.postMessage({ type: 'send', text });

    input.value = '';
    input.style.height = 'auto';
  }

  function addBubble(text, who) {
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + who;

    const inner = renderText(text, who);
    wrap.innerHTML = inner;

    // if the whole bubble is a single code block for user, add styling hint
    if (who === 'user' && /^\s*<pre>[\s\S]*<\/pre>\s*$/.test(inner)) {
      wrap.classList.add('only-code');
    }

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = (who === 'user' ? 'You' : 'NAVI') + ' • ' + clock();
    wrap.appendChild(meta);

    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
  }

  function looksLikeCode(text) {
    const newlineCount = (text.match(/\n/g) || []).length;
    if (newlineCount === 0) return false;
    const tokens = ['{', '}', ';', '=>', 'function ', 'class ', 'const ', 'let ', 'var ', 'public ', 'private ', '#include', 'import '];
    return tokens.some(t => text.includes(t));
  }

  function renderText(text) {
    const fenceRe = /```([\w-]+)?\n([\s\S]*?)```/g;

    // If the user used fenced code blocks, honour those first.
    if (text.includes('```')) {
      return text.replace(fenceRe, function (_, lang, code) {
        return '<pre><code>' + escapeHtml(code) + '</code></pre>';
      });
    }

    // If it looks like multi-line code but no backticks, wrap entire thing as code.
    if (looksLikeCode(text)) {
      return '<pre><code>' + escapeHtml(text) + '</code></pre>';
    }

    // Plain text
    return '<span>' + escapeHtml(text) + '</span>';
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function clock() {
    return new Date().toTimeString().slice(0, 5);
  }

  // ---------- Initial handshake ----------

  vscode.postMessage({ type: 'ready' });

  window.addEventListener('message', function (event) {
    const msg = event.data;
    if (msg.type === 'bot') {
      addBubble(msg.text, 'bot');
    }
  });
})();
