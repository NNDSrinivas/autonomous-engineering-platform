"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlanViewProvider = void 0;
const vscode = __importStar(require("vscode"));
class PlanViewProvider {
    constructor(ctx, state) {
        this.ctx = ctx;
        this.state = state;
    }
    resolveWebviewView(view) {
        view.webview.options = { enableScripts: true };
        view.webview.html = this.render();
        view.webview.onDidReceiveMessage(msg => {
            if (msg.t === 'signin')
                vscode.commands.executeCommand('aep.connect');
            if (msg.t === 'start')
                vscode.commands.executeCommand('aep.ai.newSession');
        });
    }
    refresh() {
        // Refresh method for external calls
    }
    async approveCurrentStep() {
        await this.refreshPlan();
        vscode.window.showInformationMessage('Use the approve buttons in the Plan view to approve individual steps');
    }
    async rejectCurrentStep() {
        await this.refreshPlan();
        vscode.window.showInformationMessage('Use the reject buttons in the Plan view to reject individual steps');
    }
    async refreshPlan() {
        // Refresh plan implementation
    }
    render() {
        const signedIn = !!this.state.token;
        return `<!DOCTYPE html><html><head>
      <meta charset="UTF-8" />
      <style>
        :root { --bg:#0f1115; --panel:#141720; --border:#202534; --fg:#e7eaf0; --muted:#8a93a5; --primary:#6e8cff; --accent:#22c55e; }
        body { margin:0; padding:0; color:var(--fg); background:var(--bg); font-family: var(--vscode-font-family); }
        .wrap { padding:14px; }
        .card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px; }
        h3 { margin:0 0 4px; font-size:14px; }
        p { margin:0 0 10px; color:var(--muted); font-size:12px; }
        .btns{ display:flex; gap:8px; }
        button { border:1px solid var(--border); background:#2a2f40; color:var(--fg); padding:6px 10px; border-radius:8px; font-size:12px; cursor:pointer; }
        .primary { background:var(--accent); border-color:transparent; color:#0a0c12; }
        .list { display:grid; gap:8px; margin-top:8px; }
        .item { background:#0f1422; border:1px dashed var(--border); border-radius:8px; padding:8px; }
        .item h4 { margin:0 0 4px; font-size:12px; }
        .item p { margin:0; font-size:12px; color:var(--muted); }
      </style>
    </head><body>
      <div class="wrap">
        <div class="card">
          <h3>🗂️ Plan & Act</h3>
          <p>${signedIn ? 'Select a JIRA issue in the Agent panel to generate a plan.' : 'Sign in to enable planning.'}</p>
          <div class="btns">
            ${signedIn
            ? `<button class="primary" onclick="post('start')">Load Demo Plan</button>`
            : `<button onclick="post('signin')">Sign in</button>`}
          </div>
          <div class="list">
            <div class="item">
              <h4>Example Plan</h4>
              <p>1) Add endpoint · 2) Write tests · 3) Update docs · 4) Create PR</p>
            </div>
          </div>
        </div>
      </div>
      <script>
        const vscode = acquireVsCodeApi();
        function post(t){ vscode.postMessage({t}); }
      </script>
    </body></html>`;
    }
}
exports.PlanViewProvider = PlanViewProvider;
//# sourceMappingURL=PlanViewProvider.js.map