import { useState, useCallback } from 'react';

export interface ReviewIssue {
    id: string;
    title: string;
    description: string;
    suggestion?: string;
    fixId?: string;
    severity?: 'low' | 'medium' | 'high';
    line?: number;
}

export interface ReviewFile {
    path: string;
    diff?: string;
    issues: ReviewIssue[];
    severity?: string;
}

export interface ReviewSession {
    reviewResults: ReviewFile[];
    isLoading: boolean;
    error: string | null;
    fetchReviewDiffs: () => Promise<void>;
    applyAutoFix: (path: string, fixId: string) => Promise<boolean>;
}

export function useReviewSession(): ReviewSession {
    const [reviewResults, setReviewResults] = useState<ReviewFile[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchReviewDiffs = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            // Connect to the NAVI SSE endpoint for real-time analysis
            // Note: EventSource doesn't support custom headers, relies on cookie-based auth
            // For token auth, append as query param (less secure but necessary for SSE)
            const authToken = typeof window !== 'undefined' ? window.localStorage.getItem('authToken') : null;
            const sseUrl = authToken
                ? `/api/navi/analyze-changes?token=${encodeURIComponent(authToken)}`
                : '/api/navi/analyze-changes';
            const eventSource = new EventSource(sseUrl);

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'review' && data.payload) {
                        // Handle both string and object payloads from backend
                        const reviewData = typeof data.payload === 'string'
                            ? JSON.parse(data.payload)
                            : data.payload;

                        // Transform backend data to match frontend interface
                        const transformedFiles: ReviewFile[] = reviewData.files.map((file: any) => ({
                            path: file.path,
                            diff: file.diff,
                            severity: file.severity,
                            issues: (file.issues || []).map((issue: any, index: number) => ({
                                id: issue.id || `issue-${index}`,
                                title: issue.title || 'Code Issue',
                                description: issue.body || issue.description || 'No description available',
                                suggestion: issue.suggestedFix,
                                fixId: generateFixId(issue.title),
                                severity: issue.severity || 'medium',
                                line: issue.line
                            }))
                        }));

                        setReviewResults(transformedFiles);
                        eventSource.close();
                        setIsLoading(false);
                    } else if (data.type === 'error') {
                        setError(data.message || 'Analysis failed');
                        eventSource.close();
                        setIsLoading(false);
                    }
                } catch (parseError) {
                    console.warn('Failed to parse SSE data:', event.data);
                }
            };

            eventSource.onerror = (err) => {
                console.error('SSE connection error:', err);
                setError('Failed to connect to analysis service');
                eventSource.close();
                setIsLoading(false);
            };

            // Close connection after 3 minutes max (code analysis can take time)
            setTimeout(() => {
                if (eventSource.readyState !== EventSource.CLOSED) {
                    eventSource.close();
                    setError('Analysis timed out - please try again');
                    setIsLoading(false);
                }
            }, 180000);

        } catch (err) {
            console.error('Error starting analysis:', err);
            setError(err instanceof Error ? err.message : 'Unknown error');
            setIsLoading(false);
        }
    }, []);

    const applyAutoFix = useCallback(async (path: string, fixId: string): Promise<boolean> => {
        try {
            const response = await fetch('/api/navi/auto-fix', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    path,
                    fixes: [fixId],
                    workspace_root: getCurrentWorkspaceRoot()
                }),
            });

            const result = await response.json();

            if (result.success && result.changes_made) {
                // Refresh the review results after successful fix
                await fetchReviewDiffs();
                return true;
            } else {
                setError(result.error || 'Auto-fix failed');
                return false;
            }
        } catch (err) {
            console.error('Auto-fix error:', err);
            setError(err instanceof Error ? err.message : 'Auto-fix failed');
            return false;
        }
    }, [fetchReviewDiffs]);

    return {
        reviewResults,
        isLoading,
        error,
        fetchReviewDiffs,
        applyAutoFix,
    };
}

/**
 * Generate a fixId based on the issue title and file path
 */
function generateFixId(issueTitle: string): string {
    const title = issueTitle.toLowerCase();

    if (title.includes('error handling') || title.includes('try-catch')) {
        return 'add-error-handling';
    } else if (title.includes('type annotation') || title.includes('typing')) {
        return 'add-type-annotations';
    } else if (title.includes('import') || title.includes('organize')) {
        return 'fix-imports';
    } else if (title.includes('performance') || title.includes('optimization')) {
        return 'optimize-performance';
    } else if (title.includes('security') || title.includes('vulnerability')) {
        return 'fix-security';
    }

    // Default fallback
    return 'generic-fix';
}

/**
 * Get the current workspace root.
 *
 * In a VS Code webview context, the extension is expected to inject a
 * `workspaceRoot` property on the `window` object. In a regular browser
 * context or when that property is not set, this returns an empty string
 * to indicate that no workspace root is available.
 */
function getCurrentWorkspaceRoot(): string {
    // Guard against non-browser / non-webview environments (e.g. SSR)
    if (typeof window === 'undefined') {
        return '';
    }
    const root = (window as any).workspaceRoot;
    if (typeof root === 'string' && root.trim() !== '') {
        return root;
    }
    // No workspace root is available in this context
    return '';
}