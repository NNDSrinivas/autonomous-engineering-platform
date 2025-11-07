const vscode = acquireVsCodeApi();

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('signin')?.addEventListener('click', ()=> vscode.postMessage({ type:'signin' }));
  document.getElementById('openPortal')?.addEventListener('click', ()=> vscode.postMessage({ type:'open', url:'portal:' }));
  document.getElementById('signup')?.addEventListener('click', ()=> vscode.postMessage({ type:'open', url:'portal:' }));
  document.getElementById('copy')?.addEventListener('click', ()=> {
    const code = document.getElementById('code')?.textContent;
    if (code) {
      navigator.clipboard.writeText(code);
    }
  });
});

window.addEventListener('message', (ev) => {
  const { type, flow } = ev.data || {};
  if(type==='flow'){
    document.getElementById('device').style.display='block';
    document.getElementById('code').textContent = flow.user_code || '';
  }
  if(type==='done'){
    document.getElementById('signin').setAttribute('disabled','true');
  }
});