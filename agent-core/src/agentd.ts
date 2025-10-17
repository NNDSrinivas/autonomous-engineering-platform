import { WebSocketServer } from 'ws';
import { greet, fetchContextPack, proposePlan } from './runtime';
import { applyEdits, runCommand } from './tools';
import { checkPolicy } from './policy';
import type { RpcReq, RpcRes, PlanItem } from './protocol';
import { existsSync } from 'fs';
import { cwd } from 'process';

const PORT = Number(process.env.AEP_AGENTD_PORT || 8765);
const wss = new WebSocketServer({ port: PORT });
console.log(`[aep-agentd] listening on ws://127.0.0.1:${PORT}`);

wss.on('connection', (ws) => {
  ws.on('message', async (data) => {
    let req: RpcReq; try { req = JSON.parse(data.toString()); } catch { return; }
    const res: RpcRes = { id: (req as any).id, ok: true, result: null };
    try {
      const root = process.env.AEP_WORKSPACE || (existsSync(cwd()) ? cwd() : process.cwd());
      switch (req.method) {
        case 'session.open': res.result = await greet(); break;
        case 'ticket.select': res.result = await fetchContextPack(req.params.key); break;
        case 'plan.propose': res.result = await proposePlan(await fetchContextPack(req.params.key)); break;
        case 'plan.runStep': {
          const step: PlanItem = req.params.step;
          const allowed = await checkPolicy(root, { command: step.command, files: step.files });
          if (!allowed) throw new Error('Denied by policy');
          if (step.kind === 'edit' && step.files?.length) {
            res.result = await applyEdits(root, step.files, step.desc);
          } else if (step.command) {
            res.result = await runCommand(root, step.command);
          } else {
            res.result = 'skipped';
          }
          break;
        }
        case 'tools.readFile': res.result = 'not implemented in MVP'; break;
        default: throw new Error(`Unknown method: ${(req as any).method}`);
      }
    } catch (e: any) {
      ws.send(JSON.stringify({ id: (req as any).id, ok: false, error: e?.message || String(e) }));
      return;
    }
    ws.send(JSON.stringify(res));
  });
});