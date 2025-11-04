/**
 * Context-Aware Code Generation Page
 * Allows users to generate diffs from natural language intent and apply them.
 */
import { useState } from "react";
import { generateDiff, applyPatch, GenerateDiffResponse } from "../api/ai";
import { DiffViewer } from "../components/DiffViewer";

export default function CodegenPage() {
  const [intent, setIntent] = useState("");
  const [files, setFiles] = useState("");
  const [diff, setDiff] = useState("");
  const [stats, setStats] = useState<GenerateDiffResponse["stats"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setBusy(true);
    setOutput(null);
    setError(null);
    setDiff("");
    setStats(null);

    try {
      const fileList = files
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean);

      if (fileList.length === 0) {
        setError("Please specify at least one target file");
        return;
      }

      if (fileList.length > 5) {
        setError("Maximum 5 files allowed per generation");
        return;
      }

      const result = await generateDiff(intent, fileList);
      setDiff(result.diff);
      setStats(result.stats);
      setOutput(
        `Generated diff: ${result.stats.files} file(s), ` +
          `+${result.stats.additions} -${result.stats.deletions} lines, ` +
          `${result.stats.size_kb.toFixed(1)}KB`
      );
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    setBusy(true);
    setOutput(null);
    setError(null);

    try {
      const result = await applyPatch(diff, false);
      if (result.applied) {
        setOutput("✅ Patch applied successfully!\n\n" + result.output);
      } else {
        setError("❌ Failed to apply patch:\n\n" + result.output);
      }
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
          Context-Aware Code Generation
        </h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Generate repo-aware code diffs from natural language intent
        </p>
      </div>

      {/* Input Form */}
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-4">
        {/* Intent */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Plan Intent
          </label>
          <textarea
            className="w-full border border-slate-300 dark:border-slate-600 rounded-lg p-3 font-mono text-sm bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder="e.g., Add rate limiting middleware to reject requests with payloads > 1MB on /api/upload"
            rows={4}
            disabled={busy}
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Describe what you want to implement (10-5000 characters)
          </p>
        </div>

        {/* Target Files */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Target Files
          </label>
          <input
            className="w-full border border-slate-300 dark:border-slate-600 rounded-lg p-3 font-mono text-sm bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            value={files}
            onChange={(e) => setFiles(e.target.value)}
            placeholder="backend/api/routers/upload.py frontend/src/api/upload.ts"
            disabled={busy}
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Space or comma-separated file paths (max 5 files)
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-2">
          <button
            disabled={busy || !intent.trim() || !files.trim()}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            onClick={handleGenerate}
          >
            {busy && !diff ? "Generating..." : "Generate Diff"}
          </button>

          <button
            disabled={busy || !diff}
            className="px-6 py-2.5 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            onClick={handleApply}
          >
            {busy && diff ? "Applying..." : "Apply Patch"}
          </button>

          {diff && (
            <button
              disabled={busy}
              className="px-6 py-2.5 rounded-lg bg-slate-600 text-white font-medium hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              onClick={() => {
                setDiff("");
                setStats(null);
                setOutput(null);
                setError(null);
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-800 p-4">
          <div className="flex items-center gap-6 text-sm">
            <div>
              <span className="font-medium text-blue-900 dark:text-blue-100">
                Files:
              </span>{" "}
              <span className="text-blue-700 dark:text-blue-300">{stats.files}</span>
            </div>
            <div>
              <span className="font-medium text-blue-900 dark:text-blue-100">
                Additions:
              </span>{" "}
              <span className="text-emerald-600 dark:text-emerald-400">
                +{stats.additions}
              </span>
            </div>
            <div>
              <span className="font-medium text-blue-900 dark:text-blue-100">
                Deletions:
              </span>{" "}
              <span className="text-rose-600 dark:text-rose-400">
                -{stats.deletions}
              </span>
            </div>
            <div>
              <span className="font-medium text-blue-900 dark:text-blue-100">
                Size:
              </span>{" "}
              <span className="text-blue-700 dark:text-blue-300">
                {stats.size_kb.toFixed(1)}KB
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Diff Viewer */}
      {diff && (
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
            Generated Diff
          </h2>
          <DiffViewer diff={diff} />
        </div>
      )}

      {/* Output / Success Message */}
      {output && !error && (
        <div className="bg-emerald-50 dark:bg-emerald-950/20 rounded-lg border border-emerald-200 dark:border-emerald-800 p-4">
          <pre className="text-sm text-emerald-800 dark:text-emerald-200 whitespace-pre-wrap font-mono">
            {output}
          </pre>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-rose-50 dark:bg-rose-950/20 rounded-lg border border-rose-200 dark:border-rose-800 p-4">
          <pre className="text-sm text-rose-800 dark:text-rose-200 whitespace-pre-wrap font-mono">
            {error}
          </pre>
        </div>
      )}
    </div>
  );
}
