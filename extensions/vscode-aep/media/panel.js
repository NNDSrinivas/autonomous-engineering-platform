(function () {
  const vscode = acquireVsCodeApi();
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));

  const messages = $('#messages');
  const input = $('#input');
  const attachBtn = $('#attachBtn');
  const attachMenu = $('#attachMenu');
  const sendBtn = $('#sendBtn');

  const modelPill = $('#modelPill');
  const modePill = $('#modePill');
  const modelValBottom = $('#modelValBottom');
  const modeValBottom = $('#modeValBottom');
  const modelMenu = $('#modelMenu');
  const modeMenu = $('#modeMenu');

  // Model & mode options – UI only for now
  const MODEL_OPTIONS = [
    {
      group: 'OpenAI',
      items: [
        'OpenAI GPT-4o — Flagship',
        'OpenAI GPT-4o-mini',
        'OpenAI o3-mini (reasoning)'
      ]
    },
    {
      group: 'Anthropic',
      items: ['Claude 3.5 Sonnet', 'Claude 3.5 Haiku']
    },
    {
      group: 'Google',
      items: ['Gemini 1.5 Pro', 'Gemini 1.5 Flash']
    },
    {
      group: 'Meta',
      items: ['Llama 3.1 70B', 'Llama 3.1 8B']
    },
    {
      group: 'Others',
      items: ['Mistral Large', 'Mistral Small']
    },
    {
      group: 'Custom',
      items: ['Bring your own key…']
    }
  ];

  const MODE_OPTIONS = [
    'Agent (full access)',
    'Chat only (read-only)',
    'Explain selection',
    'Refactor file',
    'Tests & QA'
  ];

  const persisted = vscode.getState() || {};
  const state = {
    attachOpen: !!persisted.attachOpen,
    model: persisted.model || 'OpenAI GPT-4o — Flagship',
    mode: persisted.mode || 'Agent (full access)'
  };

  setAttach(state.attachOpen);
  setModel(state.model);
  setMode(state.mode);
  buildModelMenu();
  buildModeMenu();

  function persist() {
    vscode.setState({
      attachOpen: attachMenu.classList.contains('open'),
      model: state.model,
      mode: state.mode
    });
  }

  // ----- Attach menu -----
  function setAttach(open) {
    attachMenu.classList.toggle('open', open);
    attachMenu.setAttribute('aria-hidden', String(!open));
    persist();
  }

  attachBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    setAttach(!attachMenu.classList.contains('open'));
  });

  attachMenu.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    vscode.postMessage({ type: 'attach', action: btn.getAttribute('data-action') });
    setAttach(false);
  });

  // ----- Dropdown menus (model/mode) -----
  function buildModelMenu() {
    let html = '';
    MODEL_OPTIONS.forEach((grp) => {
      html += `<div class="menu-group-label">${grp.group}</div>`;
      grp.items.forEach((item) => {
        html += `<button data-value="${item}">${item}</button>`;
      });
    });
    modelMenu.innerHTML = html;
  }

  function buildModeMenu() {
    let html = '';
    html += `<div class="menu-group-label">Mode</div>`;
    MODE_OPTIONS.forEach((item) => {
      html += `<button data-value="${item}">${item}</button>`;
    });
    modeMenu.innerHTML = html;
  }

  function closeDropdowns() {
    modelMenu.classList.remove('open');
    modeMenu.classList.remove('open');
    modelMenu.setAttribute('aria-hidden', 'true');
    modeMenu.setAttribute('aria-hidden', 'true');
  }

  modelPill.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = !modelMenu.classList.contains('open');
    closeDropdowns();
    if (open) {
      modelMenu.classList.add('open');
      modelMenu.setAttribute('aria-hidden', 'false');
    }
  });

  modePill.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = !modeMenu.classList.contains('open');
    closeDropdowns();
    if (open) {
      modeMenu.classList.add('open');
      modeMenu.setAttribute('aria-hidden', 'false');
    }
  });

  modelMenu.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-value]');
    if (!btn) return;
    const value = btn.getAttribute('data-value');
    setModel(value);
    vscode.postMessage({ type: 'setModel', value });
    closeDropdowns();
  });

  modeMenu.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-value]');
    if (!btn) return;
    const value = btn.getAttribute('data-value');
    setMode(value);
    vscode.postMessage({ type: 'setMode', value });
    closeDropdowns();
  });

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

  // ----- Global clicks / keys -----
  document.addEventListener('click', (e) => {
    // Close attach if open and click outside
    if (attachMenu.classList.contains('open')) {
      const path = e.composedPath();
      if (!path.includes(attachMenu) && !path.includes(attachBtn)) {
        setAttach(false);
      }
    }
    // Close dropdowns
    const path = e.composedPath();
    if (!path.includes(modelMenu) && !path.includes(modelPill) &&
      !path.includes(modeMenu) && !path.includes(modePill)) {
      closeDropdowns();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      setAttach(false);
      closeDropdowns();
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  // ----- Textarea behaviour -----
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });

  // ----- Toolbar buttons -----
  $$('.ctrl').forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.getAttribute('data-action');
      if (!action) return;
      vscode.postMessage({ type: 'toolbar', action });
    });
  });

  // ----- Sending messages -----
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
    wrap.innerHTML = renderText(text);

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = (who === 'user' ? 'You' : 'NAVI') + ' • ' + clock();
    wrap.appendChild(meta);

    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
  }

  function renderText(text) {
    const fence = /```([\w-]+)?\n([\s\S]*?)```/g;
    if (fence.test(text)) {
      return text.replace(fence, function (_match, _lang, code) {
        return '<pre><code>' + escapeHtml(code) + '</code></pre>';
      });
    }
    return '<span>' + escapeHtml(text) + '</span>';
  }

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function clock() {
    return new Date().toTimeString().slice(0, 5);
  }

  // ----- Messages from extension -----
  window.addEventListener('message', function (event) {
    const msg = event.data;
    if (msg.type === 'bot') {
      addBubble(msg.text, 'bot');
    } else if (msg.type === 'reset') {
      messages.innerHTML = '';
    }
  });

  // Initial handshake
  vscode.postMessage({ type: 'ready' });
})();
