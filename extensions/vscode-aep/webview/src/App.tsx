import React, { useEffect, useMemo, useState } from "react";
import { useVSCodeAPI } from "./hooks/useVSCodeAPI";
import { useReviewStream } from "./hooks/useReviewStream";
import WebviewContent from "./components/WebviewContent";
import ReviewEntryCard from "./components/ReviewEntryCard";
import { PatchPreviewModal, usePatchPreview } from "./components/PatchPreviewModal";
import type { ReviewEntry as StreamingReviewEntry } from "./hooks/useReviewStream";
import type { ReviewEntry as CardReviewEntry } from "./components/ReviewEntryCard";
import "./globals.css";

export interface ReviewData {
  files: any[];
  startedAt: number;
  finished?: boolean;
}

export interface OrchestratorResult {
  session_id: string;
  success: boolean;
  plan: {
    id: string;
    steps: Array<{
      id: string;
      action_type: string;
      description: string;
      file_targets: string[];
      priority: number;
      estimated_duration: number;
    }>;
  };
  execution_results: Array<{
    step_id: string;
    success: boolean;
    output: string;
    error?: string;
    files_modified: string[];
    execution_time: number;
  }>;
  review: {
    overall_success: boolean;
    success_rate: number;
    files_modified: string[];
    summary: string;
    recommendations: string[];
  };
  response: string;
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}

function ConnectionStatusIndicator({ status }: { status: any }) {
  const getStatusColor = () => {
    if (status.error) return "bg-red-500";
    if (status.streaming) return "bg-green-500 animate-pulse";
    if (status.connected) return "bg-blue-500";
    return "bg-gray-400";
  };

  const getStatusText = () => {
    if (status.error) return `Error: ${status.error.message}`;
    if (status.streaming) return "Streaming...";
    if (status.connected) return "Connected";
    return "Disconnected";
  };

  return (
    <div className="flex items-center space-x-2 text-xs">
      <div className={`w-2 h-2 rounded-full ${getStatusColor()}`}></div>
      <span className={status.error ? "text-red-600" : "text-gray-600"}>
        {getStatusText()}
      </span>
      {status.retryCount > 0 && (
        <span className="text-orange-600">(Retry {status.retryCount})</span>
      )}
    </div>
  );
}

function OrchestratorInterface() {
  const [instruction, setInstruction] = useState("");
  const [orchestratorResult, setOrchestratorResult] = useState<OrchestratorResult | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const vscode = useVSCodeAPI();

  const handleRunOrchestrator = () => {
    if (!instruction.trim()) return;

    setIsExecuting(true);
    setOrchestratorResult(null);

    vscode.postMessage({
      type: "runOrchestrator",
      instruction: instruction.trim()
    });
  };

  const handleQuickInstruction = (quickInstruction: string) => {
    setInstruction(quickInstruction);
    setTimeout(() => handleRunOrchestrator(), 100);
  };

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;

      if (message.type === "orchestratorResult") {
        setOrchestratorResult(message.result);
        setIsExecuting(false);
      } else if (message.type === "orchestratorError") {
        console.error("Orchestrator error:", message.error);
        setIsExecuting(false);
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  return (
    <div className="space-y-4">
      {/* Orchestrator Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-4 rounded-lg">
        <div className="flex items-center space-x-3">
          <div className="text-2xl">🧠</div>
          <div>
            <h2 className="text-lg font-bold">Navi Orchestrator</h2>
            <p className="text-sm opacity-90">Multi-Agent AI Engineering Platform</p>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => handleQuickInstruction("Review my code and suggest improvements")}
          className="p-3 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg text-left transition-colors"
          disabled={isExecuting}
        >
          <div className="font-medium text-blue-900">🔍 Smart Review</div>
          <div className="text-xs text-blue-600 mt-1">Analyze code quality</div>
        </button>

        <button
          onClick={() => handleQuickInstruction("Refactor this code to improve maintainability")}
          className="p-3 bg-green-50 hover:bg-green-100 border border-green-200 rounded-lg text-left transition-colors"
          disabled={isExecuting}
        >
          <div className="font-medium text-green-900">🔄 Smart Refactor</div>
          <div className="text-xs text-green-600 mt-1">Improve structure</div>
        </button>

        <button
          onClick={() => handleQuickInstruction("Add comprehensive tests for this codebase")}
          className="p-3 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-lg text-left transition-colors"
          disabled={isExecuting}
        >
          <div className="font-medium text-orange-900">🧪 Add Tests</div>
          <div className="text-xs text-orange-600 mt-1">Generate test coverage</div>
        </button>

        <button
          onClick={() => handleQuickInstruction("Optimize performance and fix security issues")}
          className="p-3 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg text-left transition-colors"
          disabled={isExecuting}
        >
          <div className="font-medium text-purple-900">⚡ Optimize</div>
          <div className="text-xs text-purple-600 mt-1">Performance & security</div>
        </button>
      </div>

      {/* Custom Instruction Input */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-gray-700">
          Custom Instruction
        </label>
        <div className="flex space-x-2">
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Tell Navi what you want to accomplish..."
            className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            rows={3}
            disabled={isExecuting}
          />
        </div>
        <button
          onClick={handleRunOrchestrator}
          disabled={!instruction.trim() || isExecuting}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center space-x-2"
        >
          {isExecuting ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
              <span>Executing...</span>
            </>
          ) : (
            <>
              <span>🚀</span>
              <span>Run Orchestrator</span>
            </>
          )}
        </button>
      </div>

      {/* Orchestrator Results */}
      {orchestratorResult && (
        <OrchestratorResultDisplay result={orchestratorResult} />
      )}
    </div>
  );
}

function OrchestratorResultDisplay({ result }: { result: OrchestratorResult }) {
  const [activeTab, setActiveTab] = useState('summary');

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Success/Failure Header */}
      <div className={`p-4 ${result.success ? 'bg-green-50 border-b border-green-200' : 'bg-red-50 border-b border-red-200'}`}>
        <div className="flex items-center space-x-2">
          <span className="text-lg">{result.success ? '✅' : '❌'}</span>
          <span className={`font-medium ${result.success ? 'text-green-900' : 'text-red-900'}`}>
            {result.success ? 'Execution Successful' : 'Execution Completed with Issues'}
          </span>
        </div>
        <p className={`mt-1 text-sm ${result.success ? 'text-green-700' : 'text-red-700'}`}>
          {result.review.summary}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {[
          { id: 'summary', label: '📋 Summary' },
          { id: 'plan', label: '🗂️ Plan' },
          { id: 'results', label: '📊 Results' },
          { id: 'files', label: '📁 Files' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === tab.id
              ? 'border-b-2 border-blue-500 text-blue-600'
              : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {activeTab === 'summary' && (
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-gray-900 mb-2">Execution Summary</h3>
              <p className="text-gray-700">{result.response}</p>
            </div>

            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-blue-50 p-3 rounded">
                <div className="text-lg font-bold text-blue-600">{result.plan.steps.length}</div>
                <div className="text-xs text-blue-600">Total Steps</div>
              </div>
              <div className="bg-green-50 p-3 rounded">
                <div className="text-lg font-bold text-green-600">
                  {Math.round(result.review.success_rate * 100)}%
                </div>
                <div className="text-xs text-green-600">Success Rate</div>
              </div>
              <div className="bg-purple-50 p-3 rounded">
                <div className="text-lg font-bold text-purple-600">{result.review.files_modified.length}</div>
                <div className="text-xs text-purple-600">Files Modified</div>
              </div>
            </div>

            {result.review.recommendations.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-900 mb-2">💡 Recommendations</h4>
                <ul className="space-y-1">
                  {result.review.recommendations.map((rec, idx) => (
                    <li key={idx} className="text-sm text-gray-600 flex items-start space-x-2">
                      <span className="text-blue-500 mt-0.5">•</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === 'plan' && (
          <div className="space-y-3">
            <h3 className="font-medium text-gray-900">Execution Plan</h3>
            {result.plan.steps.map((step, idx) => (
              <div key={step.id} className="border border-gray-200 rounded p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-500">Step {idx + 1}</span>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${step.action_type === 'modify_file' ? 'bg-blue-100 text-blue-800' :
                        step.action_type === 'refactor' ? 'bg-green-100 text-green-800' :
                          step.action_type === 'run_command' ? 'bg-orange-100 text-orange-800' :
                            'bg-gray-100 text-gray-800'
                        }`}>
                        {step.action_type}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-900">{step.description}</p>
                    {step.file_targets.length > 0 && (
                      <p className="mt-1 text-xs text-gray-500">
                        Files: {step.file_targets.join(', ')}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    ~{Math.round(step.estimated_duration / 60)}m
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'results' && (
          <div className="space-y-3">
            <h3 className="font-medium text-gray-900">Execution Results</h3>
            {result.execution_results.map((execResult, idx) => (
              <div key={execResult.step_id} className="border border-gray-200 rounded p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className={execResult.success ? '✅' : '❌'}></span>
                      <span className="text-sm font-medium">Step {idx + 1}</span>
                      <span className="text-xs text-gray-500">({execResult.step_id})</span>
                    </div>
                    {execResult.output && (
                      <pre className="mt-2 p-2 bg-gray-50 rounded text-xs font-mono overflow-x-auto">
                        {execResult.output}
                      </pre>
                    )}
                    {execResult.error && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded">
                        <p className="text-xs text-red-700 font-medium">Error:</p>
                        <p className="text-xs text-red-600">{execResult.error}</p>
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    {execResult.execution_time.toFixed(1)}s
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'files' && (
          <div className="space-y-3">
            <h3 className="font-medium text-gray-900">Modified Files</h3>
            {result.review.files_modified.length === 0 ? (
              <p className="text-gray-500 text-sm">No files were modified.</p>
            ) : (
              <ul className="space-y-2">
                {result.review.files_modified.map((file, idx) => (
                  <li key={idx} className="flex items-center space-x-2 text-sm">
                    <span className="text-blue-500">📄</span>
                    <span className="font-mono text-gray-900">{file}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ProgressBar({ percentage, text }: { percentage: number; text?: string }) {
  return (
    <div className="w-full">
      {text && <div className="text-xs text-gray-600 mb-1">{text}</div>}
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div
          className="bg-blue-600 h-1.5 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
        ></div>
      </div>
      <div className="text-xs text-gray-500 mt-1">{percentage.toFixed(1)}%</div>
    </div>
  );
}

function MetricsPanel({ metrics, status }: { metrics: any; status: any }) {
  const duration = metrics.startTime && metrics.endTime
    ? metrics.endTime - metrics.startTime
    : metrics.startTime
      ? Date.now() - metrics.startTime
      : 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg text-xs">
      <div className="text-center">
        <div className="text-gray-500">Files</div>
        <div className="font-semibold">{metrics.processedFiles}/{metrics.totalFiles}</div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Issues</div>
        <div className="font-semibold">{metrics.issuesFound}</div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Duration</div>
        <div className="font-semibold">{duration > 0 ? formatDuration(duration) : '-'}</div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Status</div>
        <div className="font-semibold">
          {status.streaming ? "Processing" : status.connected ? "Ready" : "Offline"}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const vscode = useVSCodeAPI();
  const { progress, progressPercentage, entries, summary, done, status, metrics, actions } = useReviewStream();
  const [memory, setMemory] = useState<{ chat?: any[]; reviews?: any[]; builds?: any[] }>({});
  const reviewEntries: CardReviewEntry[] = useMemo(() => {
    return entries.map((entry: StreamingReviewEntry) => {
      const firstIssue = entry.issues?.[0];
      const severity =
        entry.severity === "high" || entry.severity === "error"
          ? "high"
          : entry.severity === "medium" || entry.severity === "warning"
            ? "medium"
            : "low";

      return {
        file: entry.file ?? "Unknown file",
        hunk: entry.diff ?? "",
        severity,
        title:
          entry.title ||
          firstIssue?.title ||
          firstIssue?.description ||
          "Issue detected",
        body:
          entry.description ||
          entry.suggestion ||
          firstIssue?.description ||
          firstIssue?.title ||
          "",
        fixId:
          entry.canAutoFix || firstIssue?.canAutoFix
            ? entry.id || firstIssue?.id || "auto-fix"
            : "none",
      };
    });
  }, [entries]);
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusMessage, setStatusMessage] = useState<string>("Analyzing…");
  const [activeTab, setActiveTab] = useState<'orchestrator' | 'streaming' | 'legacy'>('orchestrator');
  const { patchData, showPatchPreview, hidePatchPreview, isVisible } = usePatchPreview();
  const lastBuild = useMemo(() => (memory.builds || []).slice(-1)[0], [memory.builds]);
  const lastReviewSummary = useMemo(
    () => (memory.reviews || []).filter((r: any) => r.kind === 'review:summary').slice(-1)[0],
    [memory.reviews]
  );

  // Listen for backend messages
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const msg = event.data;

      switch (msg.type) {
        case "aep.review.start":
          setStatusMessage("Starting review…");
          setLoading(true);
          break;

        case "aep.review.progress":
          setStatusMessage(msg.message ?? "Working…");
          setLoading(true);
          break;

        case "aep.review.update":
          setReviewData(msg.payload);
          break;

        case "aep.review.complete":
          setStatusMessage("Completed");
          setLoading(false);
          break;

        case "review.patchGenerated":
          // Show patch preview modal when AI generates a patch
          showPatchPreview({
            patch: msg.patch,
            filePath: msg.filePath,
            metadata: msg.metadata,
            entry: msg.entry
          });
          break;

        case "review.patchApplied":
          // Handle patch application result
          if (msg.success) {
            setStatusMessage("Patch applied successfully!");
          } else {
            setStatusMessage(`Patch failed: ${msg.message}`);
          }
          break;

        case "hydrateMemory":
        case "memory.update":
          setMemory(msg.memory || {});
          break;

        default:
          break;
      }
    };

    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  const requestReview = () => {
    vscode.postMessage({ type: "aep.review.request" });
    setStatusMessage("Starting review…");
    setLoading(true);
  };

  return (
    <div className="h-full w-full flex flex-col bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="px-4 py-3 border-b bg-white shadow-sm">
        <div className="flex justify-between items-center mb-2">
          <div className="font-semibold text-sm">
            NAVRA Labs – Code Review Assistant
          </div>

          <div className="flex items-center space-x-3">
            <ConnectionStatusIndicator status={status} />

            <div className="flex space-x-2">
              {status.streaming ? (
                <button
                  onClick={actions.stopReview}
                  className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700"
                >
                  Stop Review
                </button>
              ) : (
                <button
                  onClick={actions.startReview}
                  className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  disabled={!status.connected && !status.error}
                >
                  {status.error ? 'Retry Review' : 'Start Review'}
                </button>
              )}

              <button
                onClick={requestReview}
                className="text-xs px-3 py-1.5 bg-gray-600 text-white rounded hover:bg-gray-700"
              >
                Legacy Review
              </button>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex space-x-4 text-xs">
          <button
            onClick={() => setActiveTab('orchestrator')}
            className={`pb-1 border-b-2 ${activeTab === 'orchestrator'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
          >
            🚀 Orchestrator (Multi-Agent AI)
          </button>
          <button
            onClick={() => setActiveTab('streaming')}
            className={`pb-1 border-b-2 ${activeTab === 'streaming'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
          >
            Real-time Review ({metrics.issuesFound || reviewEntries.length} issues)
          </button>
          <button
            onClick={() => setActiveTab('legacy')}
            className={`pb-1 border-b-2 ${activeTab === 'legacy'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
          >
            Legacy View
          </button>
        </div>
      </header>

      {/* Status bar */}
      {(loading || status.streaming) && (
        <div className="px-4 py-3 bg-blue-50 border-b">
          {status.streaming && progress && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-blue-700 text-xs animate-pulse">
                  🔍 {progress}
                </span>
                {status.error && (
                  <button
                    onClick={actions.retry}
                    className="text-xs text-blue-600 hover:text-blue-800 underline"
                  >
                    Retry Connection
                  </button>
                )}
              </div>
              {progressPercentage > 0 && (
                <ProgressBar percentage={progressPercentage} />
              )}
            </div>
          )}
          {loading && !status.streaming && (
            <div className="text-blue-700 text-xs">
              {statusMessage}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'orchestrator' ? (
          <div className="p-4">
            <OrchestratorInterface />
          </div>
        ) : activeTab === 'streaming' ? (
          <div className="p-4 space-y-4">
            {/* Metrics & Summary */}
            {(status.streaming || reviewEntries.length > 0 || done || summary) && (
              <div className="space-y-3">
                <MetricsPanel metrics={metrics} status={status} />
                {summary && (
                  <div className="p-3 bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 rounded-lg text-white shadow">
                    <div className="flex items-center justify-between text-xs font-medium">
                      <span>📊 Summary</span>
                      <span className="opacity-80">
                        {summary.totalFiles ?? 0} files · {summary.skippedFiles ?? 0} skipped
                      </span>
                    </div>
                    {summary.listedFiles && summary.listedFiles.length > 0 && (
                      <div className="mt-2 text-[11px] opacity-90">
                        Showing: {summary.listedFiles.map((f: string) => `\`${f}\``).join(", ")}
                      </div>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        onClick={() => vscode.postMessage({ type: 'aep.review.openAllDiffs' })}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        🧾 View all diffs
                      </button>
                      <button
                        onClick={() => {
                          const cmd = window.prompt('Enter build/test command to run', 'npm test');
                          if (cmd) {
                            vscode.postMessage({ type: 'build.start', command: cmd });
                          }
                        }}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        🛠️ Run build
                      </button>
                      <button
                        onClick={() => vscode.postMessage({ type: 'git.status' })}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        🌀 Git status
                      </button>
                      <button
                        onClick={() => vscode.postMessage({ type: 'git.push' })}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        🚀 Git push
                      </button>
                      <button
                        onClick={() => vscode.postMessage({ type: 'git.pr.open' })}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        📮 Open PRs
                      </button>
                      <button
                        onClick={() => {
                          const repo = window.prompt('Repo (owner/repo):');
                          const base = window.prompt('Base branch:', 'main');
                          const head = window.prompt('Head branch (your branch):');
                          const title = window.prompt('PR title:');
                          const body = window.prompt('PR body:', '');
                          if (repo && base && head && title) {
                            vscode.postMessage({
                              type: 'git.pr.create',
                              payload: { repo_full_name: repo, base, head, title, body },
                            });
                          }
                        }}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        📝 Create PR
                      </button>
                      <button
                        onClick={() => {
                          const repo = window.prompt('Repo (owner/repo):');
                          const workflow = window.prompt('Workflow file (e.g., ci.yml):', 'ci.yml');
                          const ref = window.prompt('Ref (branch):', 'main');
                          if (repo && workflow && ref) {
                            vscode.postMessage({ type: 'ci.trigger', repo, workflow, ref });
                          }
                        }}
                        className="text-xs px-3 py-2 bg-white/15 text-white rounded border border-white/20 hover:bg-white/25 transition-colors"
                      >
                        🏗️ Trigger CI
                      </button>
                    </div>
                  </div>
                )}
                <div className="p-3 bg-white rounded-lg border border-gray-200 shadow-sm">
                  <div className="flex items-center justify-between text-xs font-semibold text-gray-800">
                    🧠 Memory (workspace)
                    <span className="text-gray-500">
                      Chat {memory.chat?.length || 0} · Reviews {memory.reviews?.length || 0} · Builds {memory.builds?.length || 0}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-gray-600 space-y-1">
                    {lastBuild && (
                      <div>
                        <span className="font-semibold">Last build:</span> {lastBuild.status} ({lastBuild.command})
                      </div>
                    )}
                    {lastReviewSummary?.summary && (
                      <div>
                        <span className="font-semibold">Last review:</span> {lastReviewSummary.summary?.quickSummary || 'Summary cached'}
                      </div>
                    )}
                    {[...(memory.chat || []), ...(memory.reviews || []), ...(memory.builds || [])].slice(-5).reverse().map((item: any, idx: number) => (
                      <div key={idx} className="flex items-start space-x-2">
                        <span className="text-gray-500">
                          {item.category || item.kind || 'item'}
                        </span>
                        <span className="text-gray-700 truncate">
                          {item.title || item.content || item.summary || item.command || ''}
                        </span>
                      </div>
                    ))}
                    {!lastBuild && !lastReviewSummary && [...(memory.chat || []), ...(memory.reviews || []), ...(memory.builds || [])].length === 0 && (
                      <div className="text-gray-500">No memory captured yet.</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Error Display */}
            {status.error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-red-800 font-semibold text-sm">Stream Error</div>
                    <div className="text-red-600 text-xs mt-1">{status.error.message}</div>
                    {status.error.code && (
                      <div className="text-red-500 text-xs mt-1">Code: {status.error.code}</div>
                    )}
                  </div>
                  <button
                    onClick={actions.retry}
                    className="text-xs px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    Retry
                  </button>
                </div>
              </div>
            )}

            {/* Getting Started Message */}
            {!status.streaming && reviewEntries.length === 0 && !status.error && (
              <div className="text-center py-12">
                <div className="text-gray-400 text-4xl mb-4">🚀</div>
                <div className="text-gray-600 text-lg font-semibold mb-2">Real-time Code Review</div>
                <div className="text-gray-500 text-sm mb-4">Stream live code analysis with instant feedback</div>
                <button
                  onClick={actions.startReview}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  disabled={!status.connected}
                >
                  Start Streaming Review
                </button>
              </div>
            )}

            {/* Review Entries */}
            {reviewEntries.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-sm text-gray-900">
                    Issues Found ({reviewEntries.length})
                  </h3>
                  <div className="text-xs text-gray-500">
                    {done ? 'Complete' : 'Streaming...'}
                  </div>
                </div>

                {reviewEntries.map((entry, i) => (
                  <ReviewEntryCard key={`${entry.file}-${i}`} entry={entry} />
                ))}
              </div>
            )}

            {/* Completion Status */}
            {done && reviewEntries.length === 0 && (
              <div className="text-center py-8">
                <div className="text-green-400 text-4xl mb-4">✅</div>
                <div className="text-green-600 font-semibold text-lg mb-2">Review Complete</div>
                <div className="text-gray-500 text-sm">No issues found in the codebase</div>
              </div>
            )}

            {done && reviewEntries.length > 0 && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="text-green-800 font-semibold text-sm flex items-center">
                  ✅ Review Complete
                  <span className="ml-auto text-xs text-green-600">
                    Found {reviewEntries.length} issue{reviewEntries.length !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="p-4">
            <WebviewContent reviewData={reviewData} loading={loading} />
          </div>
        )}
      </div>
    </div>
  );
}
