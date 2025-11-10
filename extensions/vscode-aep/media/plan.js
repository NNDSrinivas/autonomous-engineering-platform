const vscode = acquireVsCodeApi();

window.addEventListener('DOMContentLoaded', () => {
  bind('demo-plan', 'load-demo-plan');
  bind('plan-approve', 'approve');
  bind('plan-reject', 'reject');
  bind('plan-apply', 'applyPatch');
  bind('plan-start', 'start-session');

  document.body.addEventListener('click', event => {
    const step = event.target?.closest('.plan-step[data-i]');
    if (step instanceof HTMLElement) {
      const index = parseInt(step.getAttribute('data-i') ?? '', 10);
      if (!Number.isNaN(index)) {
        vscode.postMessage({ type: 'select', index });
      }
    }
  });
});

function bind(id, type) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener('click', () => vscode.postMessage({ type }));
  }
}
