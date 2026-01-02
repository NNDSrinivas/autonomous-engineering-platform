import { useEffect, useState } from 'react';
import { Card, CardContent } from './card';
import { Collapsible } from './collapsible';
import { Button } from './button';
import { useReviewSession } from '../../lib/hooks/useReviewSession';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';

export default function VisualDiffViewer() {
    const { reviewResults, isLoading, error, fetchReviewDiffs, applyAutoFix } = useReviewSession();
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const [fixingFiles, setFixingFiles] = useState<Set<string>>(new Set());

    useEffect(() => {
        // Auto-fetch on mount
        fetchReviewDiffs();
    }, [fetchReviewDiffs]);

    const toggleFile = (filename: string) => {
        setExpanded(prev => ({ ...prev, [filename]: !prev[filename] }));
    };

    const handleAutoFix = async (path: string, fixId: string) => {
        const fileKey = `${path}-${fixId}`;
        setFixingFiles(prev => new Set([...prev, fileKey]));

        try {
            const success = await applyAutoFix(path, fixId);
            if (success) {
                console.log(`✅ Auto-fix applied successfully for ${path}`);
            }
        } catch (error) {
            console.error(`❌ Auto-fix failed for ${path}:`, error);
        } finally {
            setFixingFiles(prev => {
                const newSet = new Set(prev);
                newSet.delete(fileKey);
                return newSet;
            });
        }
    };

    const getSeverityColor = (severity?: string) => {
        switch (severity?.toLowerCase()) {
            case 'high': return 'text-red-500';
            case 'medium': return 'text-yellow-500';
            case 'low': return 'text-blue-500';
            default: return 'text-gray-500';
        }
    };

    const getSeverityIcon = (severity?: string) => {
        switch (severity?.toLowerCase()) {
            case 'high': return '🔴';
            case 'medium': return '🟡';
            case 'low': return '🟢';
            default: return '📝';
        }
    };

    if (isLoading) {
        return (
            <div className="px-4 py-2 space-y-4">
                <h2 className="text-lg font-semibold">🔍 Visual Diff Viewer</h2>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                    <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full"></div>
                    <span>Analyzing changes...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="px-4 py-2 space-y-4">
                <h2 className="text-lg font-semibold">🔍 Visual Diff Viewer</h2>
                <div className="text-sm text-red-500">
                    ❌ {error}
                </div>
                <Button
                    onClick={fetchReviewDiffs}
                    size="sm"
                    variant="outline"
                >
                    🔄 Retry Analysis
                </Button>
            </div>
        );
    }

    if (!reviewResults || reviewResults.length === 0) {
        return (
            <div className="px-4 py-2 space-y-4">
                <h2 className="text-lg font-semibold">🔍 Visual Diff Viewer</h2>
                <div className="text-sm text-muted-foreground">
                    📄 No changes detected in working tree
                </div>
                <Button
                    onClick={fetchReviewDiffs}
                    size="sm"
                    variant="outline"
                >
                    🔄 Refresh Analysis
                </Button>
            </div>
        );
    }

    return (
        <div className="px-4 py-2 space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">🔍 Visual Diff Viewer</h2>
                <Button
                    onClick={fetchReviewDiffs}
                    size="sm"
                    variant="outline"
                    disabled={isLoading}
                >
                    🔄 Refresh
                </Button>
            </div>

            {reviewResults.map((file: any) => (
                <Card key={file.path} className="bg-muted">
                    <CardContent className="py-3">
                        <Collapsible
                            open={!!expanded[file.path]}
                            onOpenChange={() => toggleFile(file.path)}
                        >
                            <div
                                className="flex items-center justify-between cursor-pointer"
                                onClick={() => toggleFile(file.path)}
                            >
                                <span className="text-sm font-medium">📄 {file.path}</span>
                                <div className="flex items-center space-x-2">
                                    <span className="text-xs text-muted-foreground">
                                        {file.issues.length} issues
                                    </span>
                                    {file.severity && (
                                        <span className={`text-xs ${getSeverityColor(file.severity)}`}>
                                            {getSeverityIcon(file.severity)}
                                        </span>
                                    )}
                                </div>
                            </div>

                            {expanded[file.path] && (
                                <div className="mt-3 space-y-4">
                                    {/* Diff Display */}
                                    {file.diff ? (
                                        <div className="border rounded-md overflow-hidden">
                                            <div className="bg-muted-foreground/10 px-3 py-1 text-xs text-muted-foreground border-b">
                                                Changes in {file.path}
                                            </div>
                                            <SyntaxHighlighter
                                                language="diff"
                                                style={atomOneDark}
                                                customStyle={{
                                                    fontSize: '12px',
                                                    borderRadius: '0',
                                                    margin: 0,
                                                    background: 'transparent'
                                                }}
                                            >
                                                {file.diff}
                                            </SyntaxHighlighter>
                                        </div>
                                    ) : (
                                        <p className="text-sm text-muted-foreground">⚠️ No diff available</p>
                                    )}

                                    {/* Issues Display */}
                                    {file.issues.map((issue: any, i: number) => {
                                        const fileKey = `${file.path}-${issue.fixId}`;
                                        const isFixing = fixingFiles.has(fileKey);

                                        return (
                                            <div key={i} className="bg-background p-3 rounded border space-y-2">
                                                <div className="flex items-start justify-between">
                                                    <div className="space-y-1 flex-1">
                                                        <p className="text-sm font-semibold flex items-center space-x-2">
                                                            <span className={getSeverityColor(issue.severity)}>
                                                                {getSeverityIcon(issue.severity)}
                                                            </span>
                                                            <span>Issue: {issue.title}</span>
                                                            {issue.line && (
                                                                <span className="text-xs text-muted-foreground">
                                                                    (Line {issue.line})
                                                                </span>
                                                            )}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {issue.description}
                                                        </p>
                                                        {issue.suggestion && (
                                                            <p className="text-xs text-green-500">
                                                                💡 Suggestion: {issue.suggestion}
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>

                                                {issue.fixId && (
                                                    <div className="flex justify-end">
                                                        <Button
                                                            size="sm"
                                                            className="text-xs"
                                                            variant="outline"
                                                            disabled={isFixing}
                                                            onClick={() => handleAutoFix(file.path, issue.fixId!)}
                                                        >
                                                            {isFixing ? (
                                                                <>
                                                                    <div className="animate-spin h-3 w-3 border border-current border-t-transparent rounded-full mr-1" />
                                                                    Applying...
                                                                </>
                                                            ) : (
                                                                '✨ Auto-fix with Navi'
                                                            )}
                                                        </Button>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </Collapsible>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}