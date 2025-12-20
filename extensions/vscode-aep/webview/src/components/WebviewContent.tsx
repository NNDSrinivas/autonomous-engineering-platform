import React, { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SeverityBadge from "./SeverityBadge";
import AutoFixButton from "./AutoFixButton";
import VisualDiff from "./VisualDiff";

type Props = {
  reviewData: any;
  loading: boolean;
};

export default function WebviewContent({ reviewData, loading }: Props) {
  const [expanded, setExpanded] = useState(false);
  const MAX_FILES = 5;

  const { filesToRender, issueCount } = useMemo(() => {
    const files = reviewData?.files ?? [];
    const trimmed = expanded ? files : files.slice(0, MAX_FILES);
    const count = files.reduce(
      (sum: number, f: any) => sum + (f.issues?.length || 0),
      0
    );
    return { filesToRender: trimmed, issueCount: count };
  }, [reviewData, expanded]);

  if (loading) {
    return (
      <div className="p-6 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 rounded-xl text-gray-200 shadow-lg border border-slate-700">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-full bg-slate-700 animate-pulse flex items-center justify-center">
            <div className="h-6 w-6 border-2 border-white/40 border-t-transparent rounded-full animate-spin" />
          </div>
          <div>
            <div className="text-sm font-semibold">Navi is analyzing…</div>
            <div className="text-xs text-gray-400">
              Scanning files, diffs, and issues. This view will update live.
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!reviewData || !reviewData.files?.length) {
    return (
      <div className="p-4 text-sm text-gray-500">
        No issues found. Your working tree looks clean.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-4 py-3 rounded-lg shadow">
        <div>
          <div className="text-sm font-semibold">Review Summary</div>
          <div className="text-xs opacity-80">
            {reviewData.files.length} file{reviewData.files.length === 1 ? "" : "s"} · {issueCount} issue{issueCount === 1 ? "" : "s"}
          </div>
        </div>
        {reviewData.files.length > MAX_FILES && (
          <button
            className="text-xs px-3 py-1 bg-white/15 hover:bg-white/25 rounded-full transition"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Collapse" : `Show all (${reviewData.files.length})`}
          </button>
        )}
      </div>

      {filesToRender.map((file: any, i: number) => (
        <div
          key={i}
          className="border rounded-lg shadow-sm bg-white overflow-hidden"
        >
          {/* File header */}
          <div className="flex justify-between items-center px-4 py-2 bg-gray-100 border-b">
            <span className="font-mono text-xs text-gray-800">
              {file.path}
            </span>
            <SeverityBadge severity={file.severity} />
          </div>

          {/* Diff viewer */}
          <div className="p-4 border-b bg-gray-50">
            <VisualDiff diff={file.diff} />
          </div>

          {/* Issue list */}
          <div className="p-4 space-y-4">
            {file.issues?.map((issue: any) => (
              <div key={issue.id} className="border rounded p-3 bg-gray-50">
                <div className="font-semibold text-sm text-gray-800">
                  {issue.title}
                </div>

                <ReactMarkdown
                  className="prose prose-sm max-w-none mt-2"
                  remarkPlugins={[remarkGfm]}
                >
                  {issue.body}
                </ReactMarkdown>

                {issue.canAutoFix && (
                  <AutoFixButton
                    filePath={file.path}
                    fixId={issue.id}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
