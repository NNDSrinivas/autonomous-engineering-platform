// webview/src/components/PatchPreviewModal.tsx
/**
 * Patch Preview Modal Component
 * 
 * Shows AI-generated unified diff patches with syntax highlighting
 * and provides apply/cancel options for auto-fixes.
 * Part of Batch 6 — Real Auto-Fix Engine.
 */

import React, { useState, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
const getVsCodeApi = (): any => {
  if (typeof window === 'undefined') return { postMessage: () => undefined };
  const anyWindow = window as any;
  if (typeof anyWindow.acquireVsCodeApi === 'function') {
    return anyWindow.acquireVsCodeApi();
  }
  return {
    postMessage: (msg: any) => console.log('[webview] postMessage (no VS Code host):', msg),
  };
};

interface PatchPreviewModalProps {
  patch: string;
  filePath: string;
  metadata?: {
    confidence?: number;
    safety_level?: string;
    change_stats?: {
      additions: number;
      deletions: number;
      change_ratio: number;
    };
    estimated_risk?: string;
  };
  entry?: any;
  onClose: () => void;
}

interface PatchStats {
  additions: number;
  deletions: number;
  files: number;
  hunks: number;
}

export function PatchPreviewModal({ patch, filePath, metadata, entry, onClose }: PatchPreviewModalProps) {
  const [stats, setStats] = useState<PatchStats>({ additions: 0, deletions: 0, files: 0, hunks: 0 });
  const [isApplying, setIsApplying] = useState(false);
  const vscode = getVsCodeApi();

  // Calculate patch statistics
  useEffect(() => {
    const lines = patch.split('\n');
    let additions = 0;
    let deletions = 0;
    let files = 0;
    let hunks = 0;

    for (const line of lines) {
      if (line.startsWith('+++')) files++;
      else if (line.startsWith('@@')) hunks++;
      else if (line.startsWith('+') && !line.startsWith('+++')) additions++;
      else if (line.startsWith('-') && !line.startsWith('---')) deletions++;
    }

    setStats({ additions, deletions, files, hunks });
  }, [patch]);

  const handleApplyPatch = async () => {
    if (isApplying) return;
    
    setIsApplying(true);
    
    // Send patch to extension for application
    vscode.postMessage({
      type: "review.applyPatch",
      patch
    });
    
    // Close modal after sending (result will be handled separately)
    setTimeout(() => {
      setIsApplying(false);
      onClose();
    }, 500);
  };

  const getSafetyColor = (level?: string) => {
    switch (level) {
      case 'high': return 'text-green-400';
      case 'medium': return 'text-yellow-400'; 
      case 'low': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getRiskColor = (risk?: string) => {
    switch (risk) {
      case 'low': return 'text-green-400';
      case 'medium': return 'text-yellow-400';
      case 'high': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
      <div className="bg-slate-900 w-full max-w-4xl max-h-[90vh] rounded-lg shadow-2xl border border-slate-700 flex flex-col">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
              <span className="text-blue-400 text-sm font-semibold">✨</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">AI Patch Preview</h2>
              <p className="text-sm text-slate-400 truncate max-w-96">{filePath}</p>
            </div>
          </div>
          
          <button
            onClick={onClose}
            disabled={isApplying}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Stats & Metadata */}
        <div className="p-4 border-b border-slate-700 bg-slate-800/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-green-400">+{stats.additions}</span>
                <span className="text-red-400">-{stats.deletions}</span>
                <span className="text-slate-400">
                  • {stats.files} file{stats.files !== 1 ? 's' : ''} 
                  • {stats.hunks} hunk{stats.hunks !== 1 ? 's' : ''}
                </span>
              </div>
              
              {metadata && (
                <div className="flex items-center gap-4 text-sm">
                  {metadata.confidence && (
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400">Confidence:</span>
                      <span className={metadata.confidence >= 0.8 ? 'text-green-400' : metadata.confidence >= 0.6 ? 'text-yellow-400' : 'text-red-400'}>
                        {Math.round(metadata.confidence * 100)}%
                      </span>
                    </div>
                  )}
                  
                  {metadata.safety_level && (
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400">Safety:</span>
                      <span className={getSafetyColor(metadata.safety_level)}>
                        {metadata.safety_level}
                      </span>
                    </div>
                  )}
                  
                  {metadata.estimated_risk && (
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400">Risk:</span>
                      <span className={getRiskColor(metadata.estimated_risk)}>
                        {metadata.estimated_risk}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Patch Content */}
        <div className="flex-1 overflow-auto">
          <SyntaxHighlighter
            language="diff"
            style={atomDark}
            customStyle={{
              margin: 0,
              padding: '16px',
              background: 'transparent',
              fontSize: '13px',
              lineHeight: '1.4',
            }}
            lineNumberStyle={{
              color: '#64748b',
              fontSize: '12px',
              minWidth: '40px',
              paddingRight: '12px',
            }}
            showLineNumbers={true}
            wrapLines={true}
          >
            {patch}
          </SyntaxHighlighter>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-slate-700 bg-slate-800/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {metadata?.estimated_risk === 'high' && (
                <div className="flex items-center gap-2 text-amber-400 text-sm">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                  <span>High-risk change - review carefully</span>
                </div>
              )}
            </div>
            
            <div className="flex items-center gap-3">
              <button
                onClick={onClose}
                disabled={isApplying}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg border border-slate-600 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              
              <button
                onClick={handleApplyPatch}
                disabled={isApplying}
                className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isApplying ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Applying...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Apply Patch
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Hook to handle patch preview state
 */
export function usePatchPreview() {
  const [patchData, setPatchData] = useState<{
    patch: string;
    filePath: string;
    metadata?: any;
    entry?: any;
  } | null>(null);

  const showPatchPreview = (data: { patch: string; filePath: string; metadata?: any; entry?: any }) => {
    setPatchData(data);
  };

  const hidePatchPreview = () => {
    setPatchData(null);
  };

  return {
    patchData,
    showPatchPreview,
    hidePatchPreview,
    isVisible: !!patchData
  };
}
