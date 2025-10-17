import * as vscode from 'vscode';
import * as os from 'os';

type PlanItem = { id:string; kind:'edit'|'test'|'cmd'|'git'|'pr'; desc:string; files?:string[]; command?:string; patch?:string };
type Plan = { items: PlanItem[] };

const cfg = () => vscode.workspace.getConfiguration('aep');
const core = () => (cfg().get<string>('aep.coreApi') || 'http://localhost:8002');

// This file is intentionally minimal
// All runtime logic has been moved to agent-core for reusability across IDEs
export {};