const vscode = acquireVsCodeApi();

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('signin')?.addEventListener('click', () =>
    vscode.postMessage({ type: 'signin' })
  );

  document.getElementById('openPortal')?.addEventListener('click', () =>
    vscode.postMessage({ type: 'open', url: 'portal:' })
  );

  document.getElementById('signup')?.addEventListener('click', () =>
    vscode.postMessage({ type: 'open', url: 'portal:' })
  );

  document.getElementById('copy')?.addEventListener('click', () => {
    const code = document.getElementById('code')?.textContent;
    if (code) {
      navigator.clipboard.writeText(code);
    }
  });
});

window.addEventListener('message', event => {
  const { type, flow, message } = event.data || {};
  const deviceSection = document.getElementById('device');

  if (type === 'flow' && deviceSection) {
    deviceSection.dataset.visible = 'true';
    deviceSection.setAttribute('aria-hidden', 'false');
    const codeEl = document.getElementById('code');
    if (codeEl) {
      codeEl.textContent = flow?.user_code || '';
    }
  }

  if (type === 'done') {
    document.getElementById('signin')?.setAttribute('disabled', 'true');
    const hint = deviceSection?.querySelector('.hint');
    if (hint) {
      hint.textContent = 'Authentication complete. You can return to the Agent or Plan views to continue.';
    }
  }

  if (type === 'error' && deviceSection) {
    deviceSection.dataset.visible = 'true';
    deviceSection.setAttribute('aria-hidden', 'false');
    deviceSection.classList.add('error');
    const header = deviceSection.querySelector('h2');
    if (header) {
      header.textContent = 'Something went wrong';
    }
    const hint = deviceSection.querySelector('.hint');
    if (hint) {
      hint.textContent = message || 'Please try signing in again.';
    }
  }
});
