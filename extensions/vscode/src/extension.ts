import * as vscode from 'vscode';
import { greet, fetchContextPack, proposePlan, proposePlanLLM } from 'agent-core/runtime';
import { checkPolicy } from 'agent-core/policy';
import { applyEdits, runCommand } from 'agent-core/tools';

// Configuration constants
const CONFIG = {
  PLAN_PREVIEW_STEP_LIMIT: 3,
  TEXT_SANITIZATION_LIMIT: 200,
  COST_DECIMAL_PLACES: 4,
  STATUS_BAR_TIMEOUT_MS: 8000
} as const;

// Sanitize text for display in user dialogs
function sanitizeDialogText(text: string): string {
  // Limit length and remove potentially confusing characters
  return text.slice(0, CONFIG.TEXT_SANITIZATION_LIMIT).replace(/[\r\n\t]/g, ' ').trim();
}

// Helper function to safely extract and format telemetry values
function getTelemetryValue<T>(
  obj: any, 
  key: string, 
  expectedType: string, 
  formatter?: (value: T) => string
): string {
  const value = obj?.[key];
  if (typeof value === expectedType) {
    return formatter ? formatter(value) : String(value);
  }
  return 'N/A';
}

// Format latency value to rounded milliseconds
function formatLatency(latencyMs: number): string {
  return String(Math.round(latencyMs));
}

// Build a structured confirmation message
function buildConfirmationMessage(step: any): string {
  const kind = String(step.kind).toUpperCase();
  let msg = `Operation: ${kind}\n`;
  if (step.kind === 'edit' && Array.isArray(step.files) && step.files.length) {
    msg += `Files to edit:\n  ${step.files.map((f:string) => sanitizeDialogText(f)).join('\n  ')}\n`;
  }
  if (step.command) {
    msg += `Command to run:\n  ${sanitizeDialogText(step.command)}\n`;
  }
  if (step.desc) {
    msg += `Description:\n  ${sanitizeDialogText(step.desc)}\n`;
  }
  return msg.trim();
}

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
              if (!wf) {
                results.push({ id: step.id, status: 'error', error: 'No workspace folder available' });
                continue;
              }
              const allowed = await checkPolicy(wf, { command: step.command, files: step.files });
              if (!allowed) { results.push({ id: step.id, status: 'denied' }); continue; }
              // ask-before-do per step
              const go = await vscode.window.showInformationMessage(
                buildConfirmationMessage(step), { modal:true }, 'Run'
              );
              if (go !== 'Run') { results.push({ id: step.id, status:'cancelled' }); continue; }

              let details = 'skipped', status = 'ok';
              try {
                if (step.kind === 'edit' && step.files?.length && wf) {
                  details = await applyEdits(wf, step.files, step.desc);
                } else if (step.command && wf) {
                  details = await runCommand(wf, step.command);
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

  const runPlan = vscode.commands.registerCommand('aep.runPlan', async () => {
    try {
      const wf = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!wf) {
        vscode.window.showErrorMessage('No workspace folder available');
        return;
      }
      
      // Prompt user to select a plan file (JSON)
      const files = await vscode.window.showOpenDialog({
        canSelectMany: false,
        openLabel: 'Select Plan File',
        filters: { 'JSON': ['json'] },
        defaultUri: vscode.Uri.file(wf)
      });
      
      if (!files || files.length === 0) {
        vscode.window.showInformationMessage('Plan execution cancelled');
        return;
      }
      
      let plan: any;
      try {
        const fileUri = files[0];
        const fileData = await vscode.workspace.fs.readFile(fileUri);
        const planData = Buffer.from(fileData).toString('utf8');
        plan = JSON.parse(planData);
      } catch (e: any) {
        vscode.window.showErrorMessage('Failed to read or parse plan file: ' + (e?.message || String(e)));
        return;
      }
      
      // Execute plan steps with policy checking
      const results: any[] = [];
      for (const step of plan.items ?? []) {
        const allowed = await checkPolicy(wf, { command: step.command, files: step.files });
        if (!allowed) { 
          results.push({ id: step.id, status: 'denied' }); 
          continue; 
        }
        
        const go = await vscode.window.showInformationMessage(
          buildConfirmationMessage(step), { modal: true }, 'Run'
        );
        if (go !== 'Run') { 
          results.push({ id: step.id, status: 'cancelled' }); 
          continue; 
        }

        let details = 'skipped', status = 'ok';
        try {
          if (step.kind === 'edit' && step.files?.length && wf) {
            details = await applyEdits(wf, step.files, step.desc);
          } else if (step.command && wf) {
            details = await runCommand(wf, step.command);
          } else {
            status = 'skipped';
          }
        } catch (e: any) { 
          status = 'error'; 
          details = e?.message || String(e); 
        }
        results.push({ id: step.id, status, details });
      }
      
      const summary = results.map(r => {
        let line = `Step ${r.id}: ${r.status}`;
        if (r.details && typeof r.details === 'string') {
          const truncatedDetails = r.details.length > 100 ? r.details.substring(0, 100) + '...' : r.details;
          line += ` (${sanitizeDialogText(truncatedDetails)})`;
        }
        return line;
      }).join('\n');
      vscode.window.showInformationMessage(`Plan execution completed.\n${summary}`);
    } catch (e: any) {
      vscode.window.showErrorMessage(`AEP runPlan error: ${e?.message || e}`);
    }
  });

  const generatePlanLLM = vscode.commands.registerCommand('aep.generatePlanLLM', async () => {
    try {
      const wf = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!wf) {
        vscode.window.showErrorMessage('No workspace folder available');
        return;
      }
      
      const key = await vscode.window.showInputBox({
        prompt: 'Enter ticket key (e.g., PROJ-123)',
        placeHolder: 'PROJ-123'
      });
      
      if (!key) {
        vscode.window.showInformationMessage('Plan generation cancelled');
        return;
      }
      
      // Show progress indicator
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: `Generating LLM plan for ${key}`,
        cancellable: false
      }, async (progress) => {
        try {
          progress.report({ message: 'Fetching context pack...' });
          const pack = await fetchContextPack(key);
          
          progress.report({ message: 'Generating plan with LLM...' });
          const llmPlan = await proposePlanLLM(pack);
          
          // Display telemetry in status bar if available
          if (llmPlan?.telemetry) {
            const t = llmPlan.telemetry;
            const model = getTelemetryValue<string>(t, 'model', 'string');
            const tokens = getTelemetryValue<number>(t, 'tokens', 'number');
            const cost = getTelemetryValue<number>(t, 'cost_usd', 'number', v => v.toFixed(CONFIG.COST_DECIMAL_PLACES));
            const latency = getTelemetryValue<number>(t, 'latency_ms', 'number', formatLatency);
            
            vscode.window.setStatusBarMessage(
              `AEP Plan — model: ${model}, tokens: ${tokens}, cost: $${cost}, latency: ${latency}ms`, 
              CONFIG.STATUS_BAR_TIMEOUT_MS
            );
          }
          
          const stepCount = llmPlan.items?.length || 0;
          vscode.window.showInformationMessage(
            `Generated LLM Plan for ${key} with ${stepCount} steps:\n` +
            (llmPlan.items ?? []).slice(0, CONFIG.PLAN_PREVIEW_STEP_LIMIT).map(step => `• ${sanitizeDialogText(step.desc)}`).join('\n') +
            (stepCount > CONFIG.PLAN_PREVIEW_STEP_LIMIT ? `\n• ... and ${stepCount - CONFIG.PLAN_PREVIEW_STEP_LIMIT} more steps` : '')
          );
        } catch (error: any) {
          vscode.window.showErrorMessage(`Failed to generate LLM plan: ${error?.message || error}`);
        }
      });
      
    } catch (e: any) {
      vscode.window.showErrorMessage(`AEP generatePlanLLM error: ${e?.message || e}`);
    }
  });

  context.subscriptions.push(openPanel, runPlan, generatePlanLLM);
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
      
      // Comprehensive HTML escape function to prevent XSS
      const escapeHtml = (text) => {
        if (typeof text !== 'string') return '';
        return text
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#039;')
          .replace(/\`/g, '&#96;')
          // Remove dangerous control characters (preserving tab=\x09, newline=\x0A, carriage return=\x0D)
          .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
          // Remove Unicode line/paragraph separators which can break JS string literals
          .replace(/\u2028/g, '')
          .replace(/\u2029/g, '');
      };

      // Helper function to render a task item as HTML
      function renderTaskItem(t) {
        return (
          '<li>' +
            '<button class="btn" onclick="pick(\'' + escapeHtml(t.key) + '\')">' +
              escapeHtml(t.key) +
            '</button> ' +
            escapeHtml(t.title) +
            ' <code>' + escapeHtml(t.status || '') + '</code>' +
          '</li>'
        );
      }

      window.addEventListener('message', ev => {
        const {type, payload} = ev.data;
        if (type==='message') {
          const items = (payload.tasks||[]).map(renderTaskItem).join('') || '<li><small>No tasks found.</small></li>';
          log(\`<b>\${escapeHtml(payload.text)}</b><ul>\${items}</ul>\`);
        }
        if (type==='context.pack') {
          log('<b>Context Pack</b><pre>'+escapeHtml(JSON.stringify(payload,null,2))+'</pre>');
        }
        if (type==='plan.proposed') {
          window.__plan = payload;
          const list = payload.items.map(i=>\`<li><code>\${escapeHtml(i.kind)}</code> — \${escapeHtml(i.desc)}</li>\`).join('');
          log('<b>Plan Proposed</b><ul>'+list+'</ul><div class="row"><button class="btn primary" onclick="approve()">Approve & Run</button></div>');
        }
        if (type==='plan.results') {
          log('<b>Plan Results</b><pre>'+escapeHtml(JSON.stringify(payload,null,2))+'</pre>');
        }
      });

      function approve(){ vscode.postMessage({type:'plan.approve', plan: window.__plan}); }
      function pick(key){ vscode.postMessage({type:'ticket.select', key}); }
      vscode.postMessage({type:'session.open'});
    </script>
  </body></html>`;
}