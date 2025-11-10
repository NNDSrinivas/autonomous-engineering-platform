const vscode = acquireVsCodeApi();

window.addEventListener('DOMContentLoaded', () => {
  bindCommandButton('cta-signin', 'signIn');
  bindCommandButton('cta-portal', 'openPortal');
  bindCommandButton('action-start', 'startSession');
  bindCommandButton('action-refresh', 'refresh');
  bindCommandButton('action-refresh-secondary', 'refresh');
  bindCommandButton('action-portal', 'openPortal');
  bindCommandButton('retry', 'refresh');
  bindCommandButton('openPortal', 'openPortal');

  document.getElementById('cta-demo')?.addEventListener('click', () => toggleDemo(true));
  document.getElementById('demo-close')?.addEventListener('click', () => toggleDemo(false));

  document.getElementById('chatSend')?.addEventListener('click', sendChat);
  document.getElementById('chatInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });

  document.getElementById('demoSend')?.addEventListener('click', sendDemoMessage);
  document.getElementById('demoInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendDemoMessage();
    }
  });

  document.body.addEventListener('click', event => {
    const commandTarget = event.target?.closest('[data-command]');
    if (commandTarget instanceof HTMLElement) {
      const command = commandTarget.getAttribute('data-command');
      if (command) {
        if (command === 'pickIssue') {
          const key = commandTarget.getAttribute('data-key');
          if (key) {
            vscode.postMessage({ type: 'pickIssue', key });
          }
        } else {
          vscode.postMessage({ type: command });
        }
      }
      event.preventDefault();
    }

    const urlTarget = event.target?.closest('[data-url]');
    if (urlTarget instanceof HTMLElement) {
      const url = urlTarget.getAttribute('data-url');
      if (url) {
        vscode.postMessage({ type: 'openExternal', url });
        event.preventDefault();
      }
    }
  });
});

window.addEventListener('message', event => {
  const message = event.data;
  if (message?.type === 'chatMessage') {
    addChatMessage(message.role, message.content, message.timestamp);
  }
});

function bindCommandButton(id, command) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener('click', () => vscode.postMessage({ type: command }));
  }
}

function toggleDemo(visible) {
  const demoModule = document.querySelector('.module.demo');
  if (demoModule instanceof HTMLElement) {
    demoModule.dataset.visible = visible ? 'true' : 'false';
    demoModule.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }
}

function sendChat() {
  const input = document.getElementById('chatInput');
  if (!(input instanceof HTMLTextAreaElement)) {
    return;
  }

  const message = input.value.trim();
  if (!message) {
    return;
  }

  vscode.postMessage({ type: 'chat', message });
  input.value = '';
}

function sendDemoMessage() {
  const input = document.getElementById('demoInput');
  if (!(input instanceof HTMLTextAreaElement)) {
    return;
  }

  const message = input.value.trim();
  if (!message) {
    return;
  }

  addDemoMessage(message, 'user');
  input.value = '';

  setTimeout(() => {
    const responses = [
      "Here's how I would break that down into milestones...",
      'Let me surface the risks and required approvals for that change.',
      'I can scaffold tests and a rollout checklist once you connect your workspace.',
      'Sounds good—link an issue and I will prepare an execution plan with patches.'
    ];
    const response = responses[Math.floor(Math.random() * responses.length)];
    addDemoMessage(response, 'assistant');
  }, 900);
}

function addDemoMessage(message, sender) {
  const log = document.getElementById('demoLog');
  if (!log) {
    return;
  }

  const bubble = document.createElement('div');
  bubble.className = `demo-message ${sender}`;

  const author = document.createElement('strong');
  author.textContent = sender === 'user' ? 'You' : 'AEP Agent';
  const text = document.createElement('p');
  text.textContent = message;

  bubble.appendChild(author);
  bubble.appendChild(text);
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

function addChatMessage(role, content, timestamp) {
  const container = document.getElementById('chatMessages');
  if (!container) {
    return;
  }

  const placeholder = container.querySelector('.chat-placeholder');
  if (placeholder) {
    placeholder.remove();
  }

  const message = document.createElement('div');
  message.className = `chat-message ${role}`;

  const meta = document.createElement('div');
  meta.className = 'chat-meta';
  meta.textContent = `${role === 'user' ? 'You' : role === 'assistant' ? 'AEP Agent' : 'System'} • ${timestamp}`;

  const body = document.createElement('div');
  body.className = 'chat-body';
  body.textContent = content;

  message.appendChild(meta);
  message.appendChild(body);
  container.appendChild(message);
  container.scrollTop = container.scrollHeight;
}
