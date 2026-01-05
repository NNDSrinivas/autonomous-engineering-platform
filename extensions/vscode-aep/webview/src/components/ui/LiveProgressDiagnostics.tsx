import { useState } from 'react';
import { Card, CardContent, CardHeader } from './card';
import { Button } from './button';
import { Badge, CheckCircle, XCircle, AlertCircle, Loader2, Progress } from './icons';

// Simple AutoFixButton component
function AutoFixButton({
    canAutoFix,
    onFixApplied,
    onFixFailed
}: {
    fixId?: string;
    canAutoFix: boolean;
    onFixApplied: (result: any) => void;
    onFixFailed: (error: string) => void;
}) {
    const [isFixing, setIsFixing] = useState(false);

    if (!canAutoFix) return null;

    const handleClick = async () => {
        setIsFixing(true);
        try {
            // Simulate fix application
            await new Promise(resolve => setTimeout(resolve, 1000));
            onFixApplied({ success: true, changes_made: true });
        } catch (error) {
            onFixFailed(error instanceof Error ? error.message : 'Fix failed');
        } finally {
            setIsFixing(false);
        }
    };

    return (
        <Button
            onClick={handleClick}
            disabled={isFixing}
            className="text-xs px-2 py-1"
        >
            {isFixing ? 'Fixing...' : 'Auto Fix'}
        </Button>
    );
}

interface DiagnosticsProgress {
    step: string;
    progress: number;
    type: 'progress' | 'complete' | 'error';
}

interface ReviewIssue {
    id: string;
    title: string;
    description: string;
    severity: 'low' | 'medium' | 'high';
    fixId?: string;
    canAutoFix: boolean;
    line?: number;
}

interface ReviewFile {
    path: string;
    diff?: string;
    issues: ReviewIssue[];
    severity: string;
}

export function LiveProgressDiagnostics() {
    const [isRunning, setIsRunning] = useState(false);
    const [progress, setProgress] = useState<DiagnosticsProgress[]>([]);
    const [currentProgress, setCurrentProgress] = useState(0);
    const [reviewResults, setReviewResults] = useState<ReviewFile[]>([]);
    const [error, setError] = useState<string | null>(null);

    const startDiagnostics = async () => {
        setIsRunning(true);
        setProgress([]);
        setCurrentProgress(0);
        setReviewResults([]);
        setError(null);

        try {
            const eventSource = new EventSource('/api/navi/analyze-changes');

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'progress') {
                        setProgress(prev => [...prev, {
                            step: data.step,
                            progress: data.progress,
                            type: 'progress'
                        }]);
                        setCurrentProgress(data.progress);
                    } else if (data.type === 'review' && data.payload) {
                        const reviewData = JSON.parse(data.payload);
                        setReviewResults(reviewData.files || []);
                    } else if (data.type === 'complete') {
                        setProgress(prev => [...prev, {
                            step: '✅ Analysis complete!',
                            progress: 100,
                            type: 'complete'
                        }]);
                        setCurrentProgress(100);
                        setIsRunning(false);
                        eventSource.close();
                    } else if (data.type === 'error') {
                        setError(data.message || 'Analysis failed');
                        setIsRunning(false);
                        eventSource.close();
                    }
                } catch (parseError) {
                    console.warn('Failed to parse SSE data:', event.data);
                }
            };

            eventSource.onerror = (err) => {
                console.error('SSE connection error:', err);
                setError('Failed to connect to diagnostics service');
                setIsRunning(false);
                eventSource.close();
            };

        } catch (error) {
            console.error('Error starting diagnostics:', error);
            setError(error instanceof Error ? error.message : 'Unknown error');
            setIsRunning(false);
        }
    };

    const handleFixApplied = (result: { success: boolean; message?: string; changes_made?: boolean }) => {
        console.log('Fix applied successfully:', result);
        // Refresh diagnostics after fix
        if (result.changes_made) {
            setTimeout(() => startDiagnostics(), 1000);
        }
    };

    const handleFixFailed = (error: string) => {
        console.error('Fix failed:', error);
        setError(`Fix failed: ${error}`);
    };



    const getSeverityIcon = (severity: string) => {
        switch (severity?.toLowerCase()) {
            case 'high': return <XCircle className="h-4 w-4 text-red-500" />;
            case 'medium': return <AlertCircle className="h-4 w-4 text-yellow-500" />;
            case 'low': return <CheckCircle className="h-4 w-4 text-blue-500" />;
            default: return <CheckCircle className="h-4 w-4 text-gray-500" />;
        }
    };

    return (
        <div className="space-y-6 p-4">
            {/* Header Controls */}
            <Card>
                <CardHeader className="pb-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-semibold">🔍 Live Code Diagnostics</h2>
                        <div className="flex items-center space-x-2">
                            <Button
                                onClick={startDiagnostics}
                                disabled={isRunning}
                                variant="primary"
                            >
                                {isRunning ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                        Analyzing...
                                    </>
                                ) : (
                                    '🚀 Start Analysis'
                                )}
                            </Button>

                            {reviewResults.length > 0 && (
                                <div className="mt-4 text-sm text-gray-600">
                                    Found {reviewResults.length} files to review
                                </div>
                            )}
                        </div>
                    </div>

                    {isRunning && (
                        <div className="space-y-2">
                            <Progress value={currentProgress} className="w-full" />
                            <p className="text-sm text-muted-foreground">
                                {currentProgress}% complete
                            </p>
                        </div>
                    )}
                </CardHeader>
            </Card>

            {/* Error Display */}
            {error && (
                <Card className="border-red-200">
                    <CardContent className="pt-4">
                        <div className="flex items-center space-x-2 text-red-600">
                            <XCircle className="h-5 w-5" />
                            <span>{error}</span>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Progress Steps */}
            {progress.length > 0 && (
                <Card>
                    <CardHeader>
                        <h3 className="text-lg font-medium">📊 Progress Steps</h3>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {progress.map((step, index) => (
                                <div key={index} className="flex items-center space-x-2 text-sm">
                                    <CheckCircle className="h-3 w-3 text-green-500 flex-shrink-0" />
                                    <span className="text-gray-700">{step.step}</span>
                                    <span className="text-xs text-gray-500 ml-auto">
                                        {step.progress}%
                                    </span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Review Results */}
            {reviewResults.length > 0 && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-lg font-medium">
                            📋 Review Results ({reviewResults.length} files)
                        </h3>
                        <Badge variant="outline">
                            {reviewResults.reduce((total, file) => total + file.issues.length, 0)} issues found
                        </Badge>
                    </div>

                    {reviewResults.map((file, fileIndex) => (
                        <Card key={fileIndex}>
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center space-x-2">
                                        <span className="font-mono text-sm">📄 {file.path}</span>
                                        {getSeverityIcon(file.severity)}
                                    </div>
                                    <Badge variant="secondary">
                                        {file.issues.length} issues
                                    </Badge>
                                </div>
                            </CardHeader>

                            <CardContent className="space-y-3">
                                {/* Diff Preview */}
                                {file.diff && (
                                    <div className="bg-gray-50 rounded-md p-3 font-mono text-xs overflow-x-auto max-h-32">
                                        <pre className="text-gray-700 whitespace-pre-wrap">
                                            {file.diff.substring(0, 500)}
                                            {file.diff.length > 500 && '...'}
                                        </pre>
                                    </div>
                                )}

                                {/* Issues */}
                                <div className="space-y-2">
                                    {file.issues.map((issue, issueIndex) => (
                                        <div key={issueIndex} className="border rounded-lg p-3 bg-white">
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1 space-y-1">
                                                    <div className="flex items-center space-x-2">
                                                        {getSeverityIcon(issue.severity)}
                                                        <span className="font-medium text-sm">{issue.title}</span>
                                                        {issue.line && (
                                                            <Badge variant="outline" className="text-xs">
                                                                Line {issue.line}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    <p className="text-xs text-gray-600 leading-relaxed">
                                                        {issue.description}
                                                    </p>
                                                </div>

                                                <div className="ml-3 flex-shrink-0">
                                                    {issue.canAutoFix && issue.fixId ? (
                                                        <AutoFixButton
                                                            canAutoFix={issue.canAutoFix}
                                                            onFixApplied={handleFixApplied}
                                                            onFixFailed={handleFixFailed}
                                                        />
                                                    ) : (
                                                        <Badge variant="outline" className="text-xs">
                                                            Manual Fix Required
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}

export default LiveProgressDiagnostics;