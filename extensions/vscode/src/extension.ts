import * as vscode from 'vscode';
import { greet, fetchContextPack, proposePlan, proposePlanLLM } from 'agent-core/runtime';
import { checkPolicy } from 'agent-core/policy';
import { applyEdits, runCommand } from 'agent-core/tools';

// Configuration constants
const CONFIG = {
  PLAN_PREVIEW_STEP_LIMIT: 3,
  TEXT_SANITIZATION_LIMIT: 200,
  COST_DECIMAL_PLACES: 4,
  // Duration in ms to display status bar messages
  STATUS_BAR_TIMEOUT_MS: 8000,
  // API base URL for delivery operations
  API_BASE_URL: process.env.AEP_CORE_API || 'http://localhost:8002'
} as const;

// Sanitize text for display in user dialogs
function sanitizeDialogText(text: string): string {
  // Limit length and remove potentially confusing characters
  return text.slice(0, CONFIG.TEXT_SANITIZATION_LIMIT).replace(/[\r\n\t]/g, ' ').trim();
}

// Type alias for typeof operator return values using const assertion
const TYPEOF_RESULTS = ['string', 'number', 'boolean', 'object', 'undefined', 'function', 'symbol', 'bigint'] as const;
type TypeOfResult = typeof TYPEOF_RESULTS[number];

// Helper function to safely extract and format telemetry values
function getTelemetryValue<T>(
  obj: Record<string, unknown>, 
  key: string, 
  expectedType: TypeOfResult, 
  formatter?: (value: T) => string
): string {
  const value = obj?.[key];
  if (typeof value === expectedType) {
    return formatter ? formatter(value as T) : String(value);
  }
  return 'N/A';
}

// Format latency value to rounded milliseconds
function formatLatency(latencyMs: number): string {
  return String(Math.round(latencyMs));
}

// Format cost value to fixed decimal places
function formatCost(costUsd: number): string {
  return costUsd.toFixed(CONFIG.COST_DECIMAL_PLACES);
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
          case 'deliver.draftPR': {
            // Show consent modal for draft PR creation
            const confirmMessage = `Create Draft PR?\n\nRepo: ${msg.repo}\nBase: ${msg.base} → Head: ${msg.head}\nTitle: ${sanitizeDialogText(msg.title)}`;
            const consent = await vscode.window.showInformationMessage(
              confirmMessage, 
              { modal: true }, 
              'Create PR'
            );
            
            if (consent !== 'Create PR') {
              send('deliver.result', { kind: 'draftPR', status: 'cancelled' });
              break;
            }

            try {
              const payload = {
                repo_full_name: msg.repo,
                base: msg.base,
                head: msg.head,
                title: msg.title,
                body: msg.body,
                ticket_key: msg.ticket || null,
                dry_run: false
              };

              const response = await fetch(`${CONFIG.API_BASE_URL}/api/deliver/github/draft-pr`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'X-Org-Id': 'default'
                },
                body: JSON.stringify(payload)
              });

              if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
              }

              const result = await response.json();
              send('deliver.result', { kind: 'draftPR', status: 'success', data: result });
              
              // Show success message with link
              if (result.url) {
                const action = await vscode.window.showInformationMessage(
                  `Draft PR ${result.existed ? 'found' : 'created'} successfully!`,
                  'Open PR'
                );
                if (action === 'Open PR') {
                  vscode.env.openExternal(vscode.Uri.parse(result.url));
                }
              }
              
            } catch (error: any) {
              send('deliver.result', { kind: 'draftPR', status: 'error', error: error.message });
              vscode.window.showErrorMessage(`Failed to create PR: ${error.message}`);
            }
            break;
          }
          case 'deliver.jiraComment': {
            // Show consent modal for JIRA comment
            const confirmMessage = `Post JIRA Comment?\n\nIssue: ${msg.issueKey}\nComment: ${sanitizeDialogText(msg.comment)}${msg.transition ? `\nTransition: ${msg.transition}` : ''}`;
            const consent = await vscode.window.showInformationMessage(
              confirmMessage,
              { modal: true },
              'Post Comment'
            );
            
            if (consent !== 'Post Comment') {
              send('deliver.result', { kind: 'jiraComment', status: 'cancelled' });
              break;
            }

            try {
              const payload = {
                issue_key: msg.issueKey,
                comment: msg.comment,
                transition: msg.transition || null,
                dry_run: false
              };

              const response = await fetch(`${CONFIG.API_BASE_URL}/api/deliver/jira/comment`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'X-Org-Id': 'default'
                },
                body: JSON.stringify(payload)
              });

              if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
              }

              const result = await response.json();
              send('deliver.result', { kind: 'jiraComment', status: 'success', data: result });
              
              // Show success message with link
              if (result.url) {
                const action = await vscode.window.showInformationMessage(
                  'JIRA comment posted successfully!',
                  'Open Issue'
                );
                if (action === 'Open Issue') {
                  vscode.env.openExternal(vscode.Uri.parse(result.url));
                }
              }
              
            } catch (error: any) {
              send('deliver.result', { kind: 'jiraComment', status: 'error', error: error.message });
              vscode.window.showErrorMessage(`Failed to post comment: ${error.message}`);
            }
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
            const cost = getTelemetryValue<number>(t, 'cost_usd', 'number', formatCost);
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
          const list = payload.items.map(i => 
            \`<li><code>\${escapeHtml(i.kind)}</code> — \${escapeHtml(i.desc)}</li>\`
          ).join('');
          log('<b>Plan Proposed</b><ul>'+list+'</ul><div class="row"><button class="btn primary" onclick="approve()">Approve & Run</button></div>');
          
          // Add delivery actions section
          log('<b>Delivery Actions</b>' +
            '<div class="row">' +
              '<button class="btn" onclick="draftPR()">📝 Draft PR</button>' +
              '<button class="btn" onclick="jiraComment()">💬 JIRA Comment</button>' +
            '</div>');
        }
        if (type==='plan.results') {
          log('<b>Plan Results</b><pre>'+escapeHtml(JSON.stringify(payload,null,2))+'</pre>');
        }
        if (type==='deliver.result') {
          const { kind, status, data, error } = payload;
          if (status === 'success') {
            if (kind === 'draftPR') {
              const existed = data.existed ? ' (already existed)' : '';
              const url = data.url ? \` <a href="\${escapeHtml(data.url)}" target="_blank">Open PR #\${escapeHtml(data.number)}</a>\` : '';
              log(\`<b>✅ Draft PR Created\${existed}</b>\${url}\`);
            } else if (kind === 'jiraComment') {
              const url = data.url ? \` <a href="\${escapeHtml(data.url)}" target="_blank">View Issue</a>\` : '';
              log(\`<b>✅ JIRA Comment Posted</b>\${url}\`);
            }
          } else if (status === 'cancelled') {
            log(\`<b>❌ \${escapeHtml(kind)} Cancelled</b><p>Action was cancelled by user.</p>\`);
          } else if (status === 'error') {
            log(\`<b>❌ \${escapeHtml(kind)} Failed</b><p>Error: \${escapeHtml(error || 'Unknown error')}</p>\`);
          }
        }
      });

      function approve(){ vscode.postMessage({type:'plan.approve', plan: window.__plan}); }
      function pick(key){ vscode.postMessage({type:'ticket.select', key}); }
      
      function draftPR() {
        const repo = prompt("Repository (owner/repo):");
        if (!repo) return;
        
        const base = prompt("Base branch:", "main");
        if (!base) return;
        
        const head = prompt("Head branch:", "feat/new-feature");
        if (!head) return;
        
        const title = prompt("PR title:");
        if (!title) return;
        
        const body = prompt("PR description (markdown):", "## Summary\\n\\nImplements new functionality based on plan.\\n\\n## Changes\\n\\n- Added new features\\n- Updated documentation");
        if (body === null) return; // Allow empty body
        
        const ticket = prompt("Ticket key (optional, e.g., AEP-27):", "");
        
        vscode.postMessage({
          type: 'deliver.draftPR',
          repo: repo.trim(),
          base: base.trim(),
          head: head.trim(),
          title: title.trim(),
          body: body.trim(),
          ticket: ticket ? ticket.trim() : null
        });
      }
      
      function jiraComment() {
        const issueKey = prompt("JIRA Issue key (e.g., AEP-27):");
        if (!issueKey) return;
        
        const comment = prompt("Comment text:");
        if (!comment) return;
        
        const transition = prompt("Status transition (optional, e.g., 'In Progress', 'Done'):", "");
        
        vscode.postMessage({
          type: 'deliver.jiraComment',
          issueKey: issueKey.trim(),
          comment: comment.trim(),
          transition: transition ? transition.trim() : null
        });
      }
      
      vscode.postMessage({type:'session.open'});
    </script>
  </body></html>`;
}