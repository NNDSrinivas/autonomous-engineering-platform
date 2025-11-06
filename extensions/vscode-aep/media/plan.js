const vscode = acquireVsCodeApi();

window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('li[data-i]').forEach((li, index) => {
    li.addEventListener('click', () => {
      vscode.postMessage({ type: 'select', index: parseInt(li.getAttribute('data-i')) });
    });
  });
  
  document.getElementById('approve')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'approve' });
  });
  
  document.getElementById('reject')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'reject' });
  });
  
  document.getElementById('apply')?.addEventListener('click', () => {
    vscode.postMessage({ type: 'applyPatch' });
  });
});