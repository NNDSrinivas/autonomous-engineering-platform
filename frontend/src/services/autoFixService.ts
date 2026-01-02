import { toast } from '../components/ui/use-toast';
import { useLiveProgress, useSSEProgress } from '../hooks/useLiveProgress';

export interface AutoFixOptions {
    filePath?: string;
    workspaceRoot?: string;
    showProgress?: boolean;
    showToasts?: boolean;
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

/**
 * Apply a single auto-fix by ID with live progress tracking
 */
export async function applyAutoFixById(
    fixId: string,
    options: AutoFixOptions = {}
): Promise<boolean> {
    const {
        filePath,
        workspaceRoot = getCurrentWorkspaceRoot(),
        showProgress = true,
        showToasts = true
    } = options;

    const { startStep, updateStep, completeStep, errorStep } = useLiveProgress.getState();

    let stepId: string | null = null;

    try {
        if (showProgress) {
            stepId = startStep(`🔧 Applying fix ${fixId}...`);
        }

        if (!filePath) {
            throw new Error('File path is required for auto-fix');
        }

        // Update progress
        if (stepId && showProgress) {
            updateStep(stepId, 30, 'Sending fix request to backend...');
        }

        const response = await fetch(`/api/navi/repo/fix/${fixId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                path: filePath,
                workspace_root: workspaceRoot
            }),
        });

        if (stepId && showProgress) {
            updateStep(stepId, 60, 'Processing fix response...');
        }

        const result: AutoFixResult = await response.json();

        if (!response.ok) {
            throw new Error(result.message || `HTTP ${response.status}: Auto-fix failed`);
        }

        if (stepId && showProgress) {
            updateStep(stepId, 90, 'Verifying changes...');
        }

        if (result.success && result.changes_made) {
            if (stepId && showProgress) {
                completeStep(stepId, `✅ Fix ${fixId} applied successfully`);
            }

            if (showToasts) {
                toast({
                    title: '🎉 Fix Applied',
                    description: `Auto-fix for ${fixId} completed successfully.`,
                    variant: 'success',
                });
            }

            return true;
        } else {
            const errorMsg = result.message || 'No changes were made';

            if (stepId && showProgress) {
                errorStep(stepId, errorMsg);
            }

            if (showToasts) {
                toast({
                    title: '⚠️ Fix Not Applied',
                    description: errorMsg,
                    variant: 'warning',
                });
            }

            return false;
        }
    } catch (err: any) {
        const errorMessage = err.message || 'Unknown error occurred';

        if (stepId && showProgress) {
            errorStep(stepId, errorMessage);
        }

        if (showToasts) {
            toast({
                title: '❌ Auto-fix Failed',
                description: errorMessage,
                variant: 'destructive',
            });
        }

        console.error(`Auto-fix failed for ${fixId}:`, err);
        return false;
    }
}

/**
 * Apply multiple auto-fixes in sequence with progress tracking
 */
export async function applyBulkAutoFix(
    fixes: Array<{ filePath: string; fixId: string }>,
    options: AutoFixOptions = {}
): Promise<{ success: number; failed: number; results: AutoFixResult[] }> {
    const { showProgress = true, showToasts = true } = options;
    const { startStep, updateStep, completeStep } = useLiveProgress.getState();

    let stepId: string | null = null;
    let successCount = 0;
    let failedCount = 0;
    const results: AutoFixResult[] = [];

    try {
        if (showProgress) {
            stepId = startStep(`🔧 Applying ${fixes.length} fixes...`);
        }

        for (let i = 0; i < fixes.length; i++) {
            const { filePath, fixId } = fixes[i];
            const progress = Math.round((i / fixes.length) * 100);

            if (stepId && showProgress) {
                updateStep(stepId, progress, `Applying fix ${i + 1}/${fixes.length}: ${fixId}`);
            }

            try {
                const success = await applyAutoFixById(fixId, {
                    filePath,
                    ...options,
                    showProgress: false, // Don't show individual progress for bulk operations
                    showToasts: false   // Don't show individual toasts for bulk operations
                });

                if (success) {
                    successCount++;
                } else {
                    failedCount++;
                }
            } catch (error) {
                failedCount++;
                console.error(`Bulk fix failed for ${fixId}:`, error);
            }
        }

        if (stepId && showProgress) {
            completeStep(stepId, `✅ Bulk fix complete: ${successCount} success, ${failedCount} failed`);
        }

        if (showToasts) {
            if (successCount > 0 && failedCount === 0) {
                toast({
                    title: '🎉 All Fixes Applied',
                    description: `Successfully applied ${successCount} fixes.`,
                    variant: 'success',
                });
            } else if (successCount > 0 && failedCount > 0) {
                toast({
                    title: '⚠️ Partial Success',
                    description: `Applied ${successCount} fixes, ${failedCount} failed.`,
                    variant: 'warning',
                });
            } else {
                toast({
                    title: '❌ Bulk Fix Failed',
                    description: `All ${failedCount} fixes failed to apply.`,
                    variant: 'destructive',
                });
            }
        }

        return { success: successCount, failed: failedCount, results };

    } catch (error) {
        if (stepId && showProgress) {
            const { errorStep } = useLiveProgress.getState();
            errorStep(stepId, `Bulk fix failed: ${error}`);
        }

        if (showToasts) {
            toast({
                title: '❌ Bulk Fix Error',
                description: `Failed to apply fixes: ${error}`,
                variant: 'destructive',
            });
        }

        return { success: successCount, failed: fixes.length - successCount, results };
    }
}

/**
 * Start a live diagnostics session with SSE streaming
 */
export async function startLiveDiagnostics(
    options: AutoFixOptions = {}
): Promise<() => void> {
    const { workspaceRoot = getCurrentWorkspaceRoot(), showProgress = true } = options;
    const { connectToSSE } = useSSEProgress();
    const { clearSteps } = useLiveProgress.getState();

    // Clear any existing progress
    if (showProgress) {
        clearSteps();
    }

    // Connect to SSE diagnostics stream
    const cleanup = connectToSSE(
        `/api/navi/analyze-changes?workspace_root=${encodeURIComponent(workspaceRoot)}`,
        (data: any) => {
            // Handle completion data
            console.log('Diagnostics complete:', data);

            if (data.payload) {
                try {
                    const reviewData = JSON.parse(data.payload);
                    // Trigger custom event for components to handle review results
                    window.dispatchEvent(new CustomEvent('diagnostics-complete', {
                        detail: reviewData
                    }));
                } catch (error) {
                    console.error('Failed to parse diagnostics results:', error);
                }
            }
        }
    );

    return cleanup;
}

/**
 * Get suggested fixes for a file based on its extension and content
 */
export async function getSuggestedFixes(filePath: string): Promise<string[]> {
    try {
        const response = await fetch('/api/navi/suggest-fixes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_path: filePath,
                workspace_root: getCurrentWorkspaceRoot()
            }),
        });

        const result = await response.json();
        return result.suggested_fixes || [];
    } catch (error) {
        console.error('Failed to get suggested fixes:', error);
        return [];
    }
}

/**
 * Get the current workspace root - this would be provided by VS Code extension
 */
function getCurrentWorkspaceRoot(): string {
    // In a real VS Code extension, this would come from the webview API
    return (window as any).workspaceRoot || process.cwd?.() || '.';
}

// Export the main function for backward compatibility
export { applyAutoFixById as default };