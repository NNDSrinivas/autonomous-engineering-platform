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

  if (type === 'flow') {
    const deviceCard = document.getElementById('device');
    if (deviceCard) {
      deviceCard.style.display = 'block';
    }

    const codeEl = document.getElementById('code');
    if (codeEl) {
      codeEl.textContent = flow.user_code || '';
    }
  }

  if (type === 'done') {
    document.getElementById('signin')?.setAttribute('disabled', 'true');
  }

  if (type === 'error') {
    const deviceCard = document.getElementById('device');
    if (deviceCard) {
      deviceCard.style.display = 'block';
      deviceCard.innerHTML = `
        <div class="h">Something went wrong</div>
        <p class="mono"></p>
        <vscode-button id="retrySignIn">Try again</vscode-button>
      `;

      const messageEl = deviceCard.querySelector('p');
      if (messageEl) {
        messageEl.textContent = message || 'Please try signing in again.';
      }

      document
        .getElementById('retrySignIn')
        ?.addEventListener('click', () => vscode.postMessage({ type: 'signin' }));
    }
  }
});
