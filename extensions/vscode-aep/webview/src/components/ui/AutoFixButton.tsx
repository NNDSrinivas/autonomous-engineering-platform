import { useState } from 'react';
import { resolveBackendBase, buildHeaders } from '../../api/navi/client';

// Simple icon components to replace lucide-react
const Loader2 = ({ className }: { className?: string }) => (
  <div className={`${className} animate-spin`}>⟳</div>
);

const CheckCircle = ({ className }: { className?: string }) => (
  <div className={className}>✓</div>
);

const XCircle = ({ className }: { className?: string }) => (
  <div className={className}>✗</div>
);

const Wrench = ({ className }: { className?: string }) => (
  <div className={className}>🔧</div>
);

export interface AutoFixButtonProps {
  filePath: string;
  fixId: string;
  fixTitle?: string;
  onFixApplied?: (result: AutoFixResult) => void;
  onFixFailed?: (error: string) => void;
  disabled?: boolean;
  className?: string;
  size?: 'sm' | 'default' | 'lg';
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive';
}

export interface AutoFixResult {
  success: boolean;
  applied_fixes: Array<{
    fix_id: string;
    description: string;
    success: boolean;
  }>;
  failed_fixes?: Array<{
    fix_id: string;
    description: string;
    success: boolean;
  }>;
  file_path: string;
  changes_made: boolean;
  total_fixes?: number;
  message?: string;
}

export function AutoFixButton({
  filePath,
  fixId,
  fixTitle,
  onFixApplied,
  onFixFailed,
  disabled = false,
  className = "",
  // size = "sm",
  variant = "outline"
}: AutoFixButtonProps) {
  const [isFixing, setIsFixing] = useState(false);
  const [fixStatus, setFixStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const handleAutoFix = async () => {
    if (isFixing || disabled) return;

    setIsFixing(true);
    setFixStatus('idle');

    try {
      const response = await fetch(`${resolveBackendBase()}/api/navi/auto-fix`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          path: filePath,
          fixes: [fixId],
          workspace_root: getCurrentWorkspaceRoot()
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result: AutoFixResult = await response.json();

      if (result.success && result.changes_made) {
        setFixStatus('success');
        onFixApplied?.(result);

        // Reset status after 3 seconds
        setTimeout(() => setFixStatus('idle'), 3000);
      } else {
        const errorMsg = result.message || 'Fix could not be applied';
        setFixStatus('error');
        onFixFailed?.(errorMsg);

        // Reset status after 3 seconds  
        setTimeout(() => setFixStatus('idle'), 3000);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Auto-fix failed';
      setFixStatus('error');
      onFixFailed?.(errorMsg);

      console.error('Auto-fix error:', error);

      // Reset status after 3 seconds
      setTimeout(() => setFixStatus('idle'), 3000);
    } finally {
      setIsFixing(false);
    }
  };

  const getButtonContent = () => {
    if (isFixing) {
      return (
        <>
          <Loader2 className="h-3 w-3 animate-spin mr-1" />
          Applying...
        </>
      );
    }

    if (fixStatus === 'success') {
      return (
        <>
          <CheckCircle className="h-3 w-3 mr-1 text-green-500" />
          Applied!
        </>
      );
    }

    if (fixStatus === 'error') {
      return (
        <>
          <XCircle className="h-3 w-3 mr-1 text-red-500" />
          Failed
        </>
      );
    }

    return (
      <>
        <Wrench className="h-3 w-3 mr-1" />
        {fixTitle || 'Auto-fix'}
      </>
    );
  };

  const getButtonStyle = () => {
    const baseStyle = "px-3 py-1.5 rounded text-sm font-medium transition-all duration-200 flex items-center gap-2";
    if (disabled || isFixing) {
      return `${baseStyle} bg-gray-300 text-gray-500 cursor-not-allowed opacity-50`;
    }

    const currentVariant = fixStatus === 'success' ? 'default' : fixStatus === 'error' ? 'destructive' : variant;

    switch (currentVariant) {
      case 'destructive':
        return `${baseStyle} bg-red-600 hover:bg-red-700 text-white`;
      case 'secondary':
        return `${baseStyle} bg-gray-200 hover:bg-gray-300 text-gray-800`;
      case 'outline':
        return `${baseStyle} border border-gray-300 hover:bg-gray-50 text-gray-700`;
      default:
        return `${baseStyle} bg-blue-600 hover:bg-blue-700 text-white`;
    }
  };

  return (
    <button
      onClick={handleAutoFix}
      disabled={disabled || isFixing}
      className={`${getButtonStyle()} ${className}`}
    >
      {getButtonContent()}
    </button>
  );
}

/**
 * Bulk auto-fix button for applying multiple fixes at once
 */
export function BulkAutoFixButton({
  fixes,
  onAllFixesApplied,
  onFixesFailed,
  disabled = false,
  className = ""
}: {
  fixes: Array<{ filePath: string; fixId: string }>;
  onAllFixesApplied?: (results: AutoFixResult[]) => void;
  onFixesFailed?: (error: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [isFixing, setIsFixing] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleBulkFix = async () => {
    if (isFixing || disabled || fixes.length === 0) return;

    setIsFixing(true);
    setProgress(0);

    const results: AutoFixResult[] = [];

    try {
      for (let i = 0; i < fixes.length; i++) {
        const { filePath, fixId } = fixes[i];
        setProgress(Math.round((i / fixes.length) * 100));

        const response = await fetch(`${resolveBackendBase()}/api/navi/auto-fix`, {
          method: 'POST',
          headers: buildHeaders(),
          body: JSON.stringify({
            path: filePath,
            fixes: [fixId],
            workspace_root: getCurrentWorkspaceRoot()
          }),
        });

        const result: AutoFixResult = await response.json();
        results.push(result);
      }

      setProgress(100);
      onAllFixesApplied?.(results);

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Bulk auto-fix failed';
      onFixesFailed?.(errorMsg);
    } finally {
      setIsFixing(false);
      setTimeout(() => setProgress(0), 1000);
    }
  };

  return (
    <button
      onClick={handleBulkFix}
      disabled={disabled || isFixing || fixes.length === 0}
      className={`relative px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed text-white rounded font-medium transition-colors ${className}`}
    >
      {isFixing && (
        <div className="absolute inset-0 bg-blue-400/30 rounded"
          style={{ width: `${progress}%` }} />
      )}
      <div className="relative flex items-center">
        {isFixing ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Fixing {progress}%
          </>
        ) : (
          <>
            <Wrench className="h-4 w-4 mr-2" />
            Fix All ({fixes.length})
          </>
        )}
      </div>
    </button>
  );
}

/**
 * Get the current workspace root - this would be provided by VS Code extension
 */
function getCurrentWorkspaceRoot(): string {
  // In a real VS Code extension, this would come from the webview API
  // For now, return a placeholder
  return (window as any).workspaceRoot || process.cwd?.() || '.';
}

export default AutoFixButton;