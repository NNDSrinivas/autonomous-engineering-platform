import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './card';
import { Button } from './button';
// import { Progress } from './progress'; // Component not available
// import { Badge } from './badge'; // Component not available
// import { Separator } from './separator'; // Component not available
// import { useLiveProgressState, useLiveProgressActions } from '../hooks/useLiveProgress'; // Hook not available
// import { startLiveDiagnostics, applyAutoFixById, applyBulkAutoFix } from '../services/autoFixService'; // Service not available
// import { useToast } from './use-toast'; // Hook not available

// Simple component stubs to replace missing UI components
const Progress = ({ value, className }: { value?: number; className?: string }) => (
    <div className={`w-full bg-gray-200 rounded-full h-2.5 ${className || ''}`}>
        <div className="bg-blue-600 h-2.5 rounded-full" style={{ width: `${value || 0}%` }}></div>
    </div>
);

const Badge = ({ children, variant, className }: { children: React.ReactNode; variant?: string; className?: string }) => (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variant === 'destructive' ? 'bg-red-100 text-red-800' :
        variant === 'outline' ? 'bg-white border border-gray-300 text-gray-700' :
            'bg-blue-100 text-blue-800'
        } ${className || ''}`}>
        {children}
    </span>
);



// Stub service functions
const startLiveDiagnostics = async (options: any) => {
    console.log('startLiveDiagnostics called with:', options);
    return () => { }; // cleanup function
};

const applyAutoFixById = async (fixId: string, options: any) => {
    console.log('applyAutoFixById called with:', fixId, options);
    return Promise.resolve(true);
};

const applyBulkAutoFix = async (issues: any[], options: any) => {
    console.log('applyBulkAutoFix called with:', issues, options);
    return Promise.resolve();
};

// Simple icon components to replace lucide-react
const PlayCircle = ({ className }: { className?: string }) => (
    <div className={className}>▶️</div>
);

const PauseCircle = ({ className }: { className?: string }) => (
    <div className={className}>⏸️</div>
);

const CheckCircle = ({ className }: { className?: string }) => (
    <div className={className}>✓</div>
);

const AlertCircle = ({ className }: { className?: string }) => (
    <div className={className}>⚠️</div>
);

const XCircle = ({ className }: { className?: string }) => (
    <div className={className}>✗</div>
);

const Loader2 = ({ className }: { className?: string }) => (
    <div className={`${className} animate-spin`}>⟳</div>
);

const Wrench = ({ className }: { className?: string }) => (
    <div className={className}>🔧</div>
);

const FileText = ({ className }: { className?: string }) => (
    <div className={className}>📄</div>
);

const Clock = ({ className }: { className?: string }) => (
    <div className={className}>🕐</div>
);

interface ReviewIssue {
    id: string;
    title: string;
    body: string;
    fixId?: string;
    canAutoFix: boolean;
    severity: 'low' | 'medium' | 'high';
    line?: number;
}

interface ReviewFile {
    path: string;
    diff?: string;
    issues: ReviewIssue[];
    severity: string;
}

interface DiagnosticsResults {
    files: ReviewFile[];
}

export function SSEDiagnosticsIntegration() {
    const [isRunning, setIsRunning] = useState(false);
    const [results, setResults] = useState<DiagnosticsResults | null>(null);
    const [cleanup, setCleanup] = useState<(() => void) | null>(null);
    const [autoFixInProgress, setAutoFixInProgress] = useState<Set<string>>(new Set());

    // Stub for missing hooks
    const steps: any[] = [];
    const isActive = false;
    const totalProgress = 0;
    // const _activeStep: { title: string; progress: number } | null = null;
    const clearSteps = () => { };
    const toast = ({ title, description }: { title: string; description?: string }) => {
        console.log('Toast:', title, description);
    };

    // Listen for diagnostics completion
    useEffect(() => {
        const handleDiagnosticsComplete = (event: CustomEvent) => {
            setResults(event.detail);
            setIsRunning(false);
        };

        window.addEventListener('diagnostics-complete', handleDiagnosticsComplete as EventListener);

        return () => {
            window.removeEventListener('diagnostics-complete', handleDiagnosticsComplete as EventListener);
        };
    }, []);

    const startDiagnostics = useCallback(async () => {
        setIsRunning(true);
        setResults(null);

        try {
            const cleanupFn = await startLiveDiagnostics({
                showProgress: true,
                showToasts: false // We'll handle toasts manually for better control
            });

            setCleanup(() => cleanupFn);

            toast({
                title: '🔍 Diagnostics Started',
                description: 'Analyzing your codebase for issues...'
            });
        } catch (error) {
            console.error('Failed to start diagnostics:', error);
            setIsRunning(false);

            toast({
                title: '❌ Diagnostics Failed',
                description: 'Failed to start code analysis'
            });
        }
    }, []);

    const stopDiagnostics = useCallback(() => {
        if (cleanup) {
            cleanup();
            setCleanup(null);
        }
        setIsRunning(false);
        clearSteps();

        toast({
            title: '⏹️ Diagnostics Stopped',
            description: 'Code analysis has been stopped'
        });
    }, [cleanup, clearSteps]);

    const handleAutoFix = useCallback(async (filePath: string, fixId: string) => {
        const key = `${filePath}:${fixId}`;
        setAutoFixInProgress(prev => new Set([...prev, key]));

        try {
            const success = await applyAutoFixById(fixId, {
                filePath,
                showProgress: true,
                showToasts: true
            });

            if (success) {
                // Refresh diagnostics after successful fix
                setTimeout(() => {
                    startDiagnostics();
                }, 1000);
            }
        } finally {
            setAutoFixInProgress(prev => {
                const newSet = new Set(prev);
                newSet.delete(key);
                return newSet;
            });
        }
    }, [startDiagnostics]);

    const handleBulkAutoFix = useCallback(async () => {
        if (!results) return;

        const fixableIssues = results.files.flatMap(file =>
            file.issues
                .filter(issue => issue.canAutoFix && issue.fixId)
                .map(issue => ({ filePath: file.path, fixId: issue.fixId! }))
        );

        if (fixableIssues.length === 0) {
            toast({
                title: '⚠️ No Fixes Available',
                description: 'No auto-fixable issues found'
            });
            return;
        }

        setAutoFixInProgress(prev => new Set([...prev, 'bulk']));

        try {
            await applyBulkAutoFix(fixableIssues, {
                showProgress: true,
                showToasts: true
            });

            // Refresh diagnostics after bulk fix
            setTimeout(() => {
                startDiagnostics();
            }, 2000);
        } finally {
            setAutoFixInProgress(prev => {
                const newSet = new Set(prev);
                newSet.delete('bulk');
                return newSet;
            });
        }
    }, [results, startDiagnostics]);

    const getSeverityIcon = (severity: string) => {
        switch (severity?.toLowerCase()) {
            case 'high': return <XCircle className="h-4 w-4 text-red-500" />;
            case 'medium': return <AlertCircle className="h-4 w-4 text-yellow-500" />;
            case 'low': return <CheckCircle className="h-4 w-4 text-blue-500" />;
            default: return <FileText className="h-4 w-4 text-gray-500" />;
        }
    };

    const getSeverityColor = (severity: string) => {
        switch (severity?.toLowerCase()) {
            case 'high': return 'text-red-600 bg-red-50 border-red-200';
            case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
            case 'low': return 'text-blue-600 bg-blue-50 border-blue-200';
            default: return 'text-gray-600 bg-gray-50 border-gray-200';
        }
    };

    const totalIssues = results?.files.reduce((sum, file) => sum + file.issues.length, 0) || 0;
    const fixableIssues = results?.files.reduce((sum, file) =>
        sum + file.issues.filter(issue => issue.canAutoFix).length, 0
    ) || 0;

    return (
        <div className="space-y-6 p-4">
            {/* Header Controls */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center space-x-2">
                            <Wrench className="h-5 w-5" />
                            <span>Live Code Diagnostics & Auto-Fix</span>
                        </CardTitle>

                        <div className="flex items-center space-x-2">
                            {!isRunning ? (
                                <Button onClick={startDiagnostics} disabled={isActive}>
                                    <PlayCircle className="h-4 w-4 mr-2" />
                                    Start Analysis
                                </Button>
                            ) : (
                                <Button onClick={stopDiagnostics} variant="outline">
                                    <PauseCircle className="h-4 w-4 mr-2" />
                                    Stop
                                </Button>
                            )}

                            {results && fixableIssues > 0 && (
                                <Button
                                    onClick={handleBulkAutoFix}
                                    disabled={autoFixInProgress.has('bulk')}
                                    variant="primary"
                                >
                                    {autoFixInProgress.has('bulk') ? (
                                        <>
                                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                            Fixing...
                                        </>
                                    ) : (
                                        <>
                                            <Wrench className="h-4 w-4 mr-2" />
                                            Fix All ({fixableIssues})
                                        </>
                                    )}
                                </Button>
                            )}
                        </div>
                    </div>

                    {/* Progress Display */}
                    {(isActive || isRunning) && (
                        <div className="space-y-2 mt-4">
                            <Progress value={totalProgress} className="w-full" />
                            {/* Active step display removed - not implemented yet */}
                        </div>
                    )}
                </CardHeader>
            </Card>

            {/* Progress Steps */}
            {steps.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Progress Steps</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {steps.slice(-10).map((step) => (
                                <div key={step.id} className="flex items-center space-x-2 text-sm">
                                    {step.status === 'completed' && <CheckCircle className="h-3 w-3 text-green-500" />}
                                    {step.status === 'active' && <Loader2 className="h-3 w-3 animate-spin text-blue-500" />}
                                    {step.status === 'error' && <XCircle className="h-3 w-3 text-red-500" />}
                                    {step.status === 'pending' && <Clock className="h-3 w-3 text-gray-400" />}

                                    <span className={`${step.status === 'error' ? 'text-red-600' :
                                        step.status === 'completed' ? 'text-green-600' : 'text-gray-700'
                                        }`}>
                                        {step.title}
                                    </span>

                                    {step.progress > 0 && (
                                        <Badge variant="outline" className="text-xs">
                                            {step.progress}%
                                        </Badge>
                                    )}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Results Summary */}
            {results && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center justify-between">
                            <span>Analysis Results</span>
                            <div className="flex items-center space-x-2">
                                <Badge variant="outline">{results.files.length} files</Badge>
                                <Badge variant="outline">{totalIssues} issues</Badge>
                                <Badge variant="outline" className="text-green-600">
                                    {fixableIssues} fixable
                                </Badge>
                            </div>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {results.files.map((file, index) => (
                                <div key={index} className="border rounded-lg p-4 space-y-3">
                                    {/* File Header */}
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center space-x-2">
                                            <FileText className="h-4 w-4" />
                                            <span className="font-mono text-sm">{file.path}</span>
                                            {getSeverityIcon(file.severity)}
                                        </div>
                                        <Badge variant="secondary">{file.issues.length} issues</Badge>
                                    </div>

                                    {/* Issues */}
                                    <div className="space-y-2">
                                        {file.issues.map((issue, issueIndex) => (
                                            <div key={issueIndex} className={`border rounded-md p-3 ${getSeverityColor(issue.severity)}`}>
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
                                                        <p className="text-xs opacity-80">{issue.body}</p>
                                                    </div>

                                                    <div className="ml-3 flex-shrink-0">
                                                        {issue.canAutoFix && issue.fixId ? (
                                                            <Button
                                                                size="sm"
                                                                onClick={() => handleAutoFix(file.path, issue.fixId!)}
                                                                disabled={autoFixInProgress.has(`${file.path}:${issue.fixId}`)}
                                                                className="text-xs"
                                                            >
                                                                {autoFixInProgress.has(`${file.path}:${issue.fixId}`) ? (
                                                                    <>
                                                                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                                                        Fixing...
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <Wrench className="h-3 w-3 mr-1" />
                                                                        Fix
                                                                    </>
                                                                )}
                                                            </Button>
                                                        ) : (
                                                            <Badge variant="outline" className="text-xs">
                                                                Manual Fix
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

export default SSEDiagnosticsIntegration;
