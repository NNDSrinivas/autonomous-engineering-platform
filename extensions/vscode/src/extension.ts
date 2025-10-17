import * as vscode from 'vscode';
import { greet, fetchContextPack, proposePlan } from '../../../agent-core/dist/runtime';
import { checkPolicy } from '../../../agent-core/dist/policy';
import { applyEdits, runCommand } from '../../../agent-core/dist/tools';

export function activate(context: vscode.ExtensionContext) {
  const openPanel = vscode.commands.registerCommand('aep.openPanel', () => {
    const panel = vscode.window.createWebviewPanel('aep', 'AEP Agent', vscode.ViewColumn.Active,
      { enableScripts: true, retainContextWhenHidden: true });
    panel.webview.html = html();
    const send = (type:string, payload?:any) => panel.webview.postMessage({ type, payload });

    panel.webview.onDidReceiveMessage(async (msg) => {
      try {
        const wf = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        switch (msg.type) {
          case 'session.open': {
            const g = await greet();
            send('message', g);
            break;
          }
          case 'ticket.select': {
            const pack = await fetchContextPack(msg.key);
            send('context.pack', pack);
            const plan = await proposePlan(pack);
            send('plan.proposed', plan);
            break;
          }
          case 'plan.approve': {
            const results: any[] = [];
            for (const step of msg.plan.items ?? []) {
              const allowed = await checkPolicy(wf!, { command: step.command, files: step.files });
              if (!allowed) { results.push({ id: step.id, status: 'denied' }); continue; }
              // ask-before-do per step
              const go = await vscode.window.showInformationMessage(
                `${step.kind.toUpperCase()}: ${step.desc}${step.command ? `\n${step.command}`:''}`, { modal:true }, 'Run'
              );
              if (go !== 'Run') { results.push({ id: step.id, status:'cancelled' }); continue; }

              let details = 'skipped', status = 'ok';
              try {
                if (step.kind === 'edit' && step.files?.length && wf) {
                  details = await applyEdits(wf, step.files, step.desc);
                } else if (step.command && wf) {
                  details = runCommand(wf, step.command);
                } else {
                  status = 'skipped';
                }
              } catch (e:any) { status = 'error'; details = e?.message || String(e); }
              results.push({ id: step.id, status, details });
            }
            send('plan.results', { results });
            break;
          }
        }
      } catch (e:any) {
        vscode.window.showErrorMessage(`AEP error: ${e?.message || e}`);
      }
    });

    setTimeout(() => send('session.open'), 200);
  });

  context.subscriptions.push(openPanel);
}
export function deactivate() {}

function html(): string {
  return `<!doctype html><html><head><meta charset="utf-8">
  <style>
  body{font:12px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:12px;background:#f6f7fb}
  .card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin:10px 0}
  .row{display:flex;gap:8px;align-items:center;margin:6px 0}
  .btn{border:1px solid #cbd5e1;border-radius:8px;padding:6px 10px;background:#fff;cursor:pointer}
  .btn.primary{background:#0ea5e9;color:#fff;border-color:#0ea5e9}
  code{background:#f3f4f6;padding:2px 4px;border-radius:4px}
  ul{margin:6px 0 0 18px}
  small{color:#64748b}
  </style></head><body>
    <div id="log"></div>
    <script>
      const vscode = acquireVsCodeApi();
      const log = (html) => { const d=document.createElement('div'); d.className='card'; d.innerHTML=html; document.getElementById('log').prepend(d); };

      window.addEventListener('message', ev => {
        const {type, payload} = ev.data;
        if (type==='message') {
          const items = (payload.tasks||[]).map(t => \`<li><button class="btn" onclick="pick('\${t.key}')">\${t.key}</button> \${t.title} <code>\${t.status||''}</code></li>\`).join('') || '<li><small>No tasks found.</small></li>';
          log(\`<b>\${payload.text}</b><ul>\${items}</ul>\`);
        }
        if (type==='context.pack') {
          log('<b>Context Pack</b><pre>'+JSON.stringify(payload,null,2)+'</pre>');
        }
        if (type==='plan.proposed') {
          window.__plan = payload;
          const list = payload.items.map(i=>\`<li><code>\${i.kind}</code> — \${i.desc}</li>\`).join('');
          log('<b>Plan Proposed</b><ul>'+list+'</ul><div class="row"><button class="btn primary" onclick="approve()">Approve & Run</button></div>');
        }
        if (type==='plan.results') {
          log('<b>Plan Results</b><pre>'+JSON.stringify(payload,null,2)+'</pre>');
        }
      });

      function approve(){ vscode.postMessage({type:'plan.approve', plan: window.__plan}); }
      function pick(key){ vscode.postMessage({type:'ticket.select', key}); }
      vscode.postMessage({type:'session.open'});
    </script>
  </body></html>`;
}