const vscode = acquireVsCodeApi();
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('signIn')?.addEventListener('click', ()=> vscode.commands?.executeCommand?.('aep.signIn') || vscode.postMessage({ type:'command', cmd:'aep.signIn' }));
  document.getElementById('start')?.addEventListener('click', ()=> vscode.postMessage({ type:'pickIssue' }));
  document.querySelectorAll('[data-url]')?.forEach(a=> a.addEventListener('click', (e)=>{ e.preventDefault(); vscode.postMessage({ type:'openExternal', url: a.getAttribute('data-url') }); }));
  document.querySelectorAll('vscode-button[data-key]')?.forEach(b=> b.addEventListener('click', ()=> vscode.postMessage({ type:'pickIssue', key: b.getAttribute('data-key') })));
});