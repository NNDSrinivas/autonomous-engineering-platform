import React from 'react';
import { postMessage } from '../../utils/vscodeApi';

/**
 * Phase 4.1.2 Tool Approval Component
 * 
 * Shows tool execution requests with Allow/Skip options
 */

interface ToolApprovalProps {
  tool_request: {
    run_id: string;
    request_id: string;
    tool: string;
    args: any;
    approval: {
      required: boolean;
      reason: string;
      risk: 'low' | 'medium' | 'high';
    };
  };
  session_id: string;
  onResolve: () => void;
}

export function ToolApproval({ tool_request, session_id, onResolve }: ToolApprovalProps) {
  const { tool, approval } = tool_request;
  const args = tool_request.args ?? {};

  const handleDecision = (decision: 'approve' | 'reject') => {
    // Send decision to extension
    postMessage({
      type: 'navi.tool.approval',
      decision,
      tool_request,
      session_id
    });
    
    // Clear approval UI
    onResolve();
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'text-red-400 bg-red-900';
      case 'medium': return 'text-yellow-400 bg-yellow-900';
      default: return 'text-green-400 bg-green-900';
    }
  };

  const getToolIcon = (toolName: string) => {
    if (toolName.includes('getDiagnostics')) return '🩺';
    if (toolName.includes('readFile')) return '📄';
    if (toolName.includes('applyPatch')) return '🔧';
    if (toolName.includes('run')) return '▶️';
    return '🛠️';
  };

  return (
    <div className="bg-yellow-950/40 border border-yellow-700/60 rounded-lg p-4 mb-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{getToolIcon(tool)}</span>
          <div>
            <h3 className="text-lg font-semibold text-yellow-100">
              Tool Execution Required
            </h3>
            <p className="text-sm text-yellow-300">
              {approval.reason}
            </p>
          </div>
        </div>
        <span className={`px-2 py-1 text-xs rounded ${getRiskColor(approval.risk)}`}>
          {approval.risk.toUpperCase()} RISK
        </span>
      </div>

      {/* Tool Details */}
      <div className="bg-black/40 rounded p-3 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-yellow-400 font-mono text-sm">Tool:</span>
          <span className="text-white font-mono text-sm">{tool}</span>
        </div>
        
        {Object.keys(args).length > 0 && (
          <div>
            <span className="text-yellow-400 font-mono text-sm">Arguments:</span>
            <pre className="text-white text-xs mt-1 bg-black rounded p-2 overflow-auto">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-3">
        <button
          className="px-3 py-1.5 rounded text-xs font-medium text-[var(--vscode-descriptionForeground)] hover:text-[var(--vscode-foreground)] hover:bg-[var(--vscode-toolbar-hoverBackground)] transition-colors"
          onClick={() => handleDecision('reject')}
        >
          ⏭️ Skip
        </button>
        <button
          className="px-3 py-1.5 rounded text-xs font-medium bg-[var(--vscode-button-background)] text-[var(--vscode-button-foreground)] hover:bg-[var(--vscode-button-hoverBackground)] transition-colors"
          onClick={() => handleDecision('approve')}
        >
          ✅ Allow
        </button>
      </div>

      {/* Risk Warning */}
      {approval.risk === 'high' && (
        <div className="mt-3 pt-3 border-t border-yellow-600">
          <p className="text-xs text-yellow-300">
            ⚠️ This action may modify your workspace. Review carefully before allowing.
          </p>
        </div>
      )}
    </div>
  );
}
