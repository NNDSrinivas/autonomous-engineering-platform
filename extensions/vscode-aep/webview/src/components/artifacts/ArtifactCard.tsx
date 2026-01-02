import React from 'react';
import type { ArtifactPayload } from '../../state/uiStore';

const KIND_LABELS: Record<string, string> = {
  changePlan: 'Plan',
  diffs: 'Diffs',
  validation: 'Validation',
  apply: 'Apply',
  pr: 'Pull Request',
  ci: 'CI',
  command: 'Command',
  context: 'Context'
};

function renderChangePlan(data: any) {
  const files = Array.isArray(data?.files) ? data.files : [];
  return (
    <div className="space-y-2 text-xs text-gray-300">
      {data?.strategy && (
        <div>
          <span className="text-gray-400">Strategy:</span> {data.strategy}
        </div>
      )}
      {data?.riskLevel && (
        <div>
          <span className="text-gray-400">Risk:</span> {String(data.riskLevel).toUpperCase()}
        </div>
      )}
      {typeof data?.testsRequired === 'boolean' && (
        <div>
          <span className="text-gray-400">Tests:</span> {data.testsRequired ? 'Required' : 'Not required'}
        </div>
      )}
      {files.length > 0 && (
        <div className="space-y-1">
          <div className="text-gray-400">Files:</div>
          <ul className="space-y-1">
            {files.map((file: any, index: number) => (
              <li key={`${file.path || file.file_path || index}`} className="flex items-center gap-2">
                <span className="text-gray-500">{file.intent || file.change_type || 'modify'}</span>
                <span className="truncate">{file.path || file.file_path || 'unknown'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function renderDiffs(data: any) {
  const changes = Array.isArray(data) ? data : data?.codeChanges || [];
  if (!changes.length) {
    return <div className="text-xs text-gray-400">No diffs provided.</div>;
  }

  return (
    <div className="space-y-3 text-xs text-gray-300">
      {changes.map((change: any, index: number) => (
        <div key={`${change.file_path || change.path || index}`} className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">{change.change_type || 'modify'}</span>
            <span className="truncate">{change.file_path || change.path || 'unknown'}</span>
          </div>
          {change.reasoning && (
            <div className="text-gray-400">{change.reasoning}</div>
          )}
          {change.diff && (
            <details className="rounded border border-white/5 bg-black/30">
              <summary className="cursor-pointer px-2 py-1 text-gray-400">View diff</summary>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap px-2 py-2 text-[11px] text-gray-200">
                {change.diff}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

function renderValidation(data: any) {
  const issues = Array.isArray(data?.issues) ? data.issues : [];
  const status = String(data?.status || data?.state || 'UNKNOWN');
  const canProceed = data?.canProceed === true;
  return (
    <div className="space-y-2 text-xs text-gray-300">
      <div>
        <span className="text-gray-400">Status:</span> {status}
      </div>
      <div>
        <span className="text-gray-400">Proceed:</span> {canProceed ? 'Yes' : 'No'}
      </div>
      {issues.length > 0 && (
        <div className="space-y-1">
          <div className="text-gray-400">Issues:</div>
          <ul className="space-y-1">
            {issues.map((issue: any, index: number) => (
              <li key={`${issue.file_path || issue.message || index}`} className="text-gray-300">
                <div>{issue.message || 'Validation issue'}</div>
                {issue.file_path && (
                  <div className="text-gray-500">{issue.file_path}{issue.line_number ? `:${issue.line_number}` : ''}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function renderApply(data: any) {
  const appliedFiles = Array.isArray(data?.appliedFiles) ? data.appliedFiles : [];
  return (
    <div className="space-y-2 text-xs text-gray-300">
      {data?.summary && (
        <div className="text-gray-400">
          {data.summary.successfulFiles ?? 0}/{data.summary.totalFiles ?? appliedFiles.length} files applied
        </div>
      )}
      {appliedFiles.length > 0 && (
        <ul className="space-y-1">
          {appliedFiles.map((file: any, index: number) => (
            <li key={`${file.file_path || index}`} className="flex items-center gap-2">
              <span className="text-gray-500">{file.operation || 'modified'}</span>
              <span className="truncate">{file.file_path || 'unknown'}</span>
              <span className="text-gray-400">{file.success === false ? 'failed' : 'ok'}</span>
            </li>
          ))}
        </ul>
      )}
      {typeof data?.rollbackAvailable === 'boolean' && (
        <div className="text-gray-400">
          Rollback: {data.rollbackAvailable ? 'Available' : 'Unavailable'}
        </div>
      )}
    </div>
  );
}

function renderPr(data: any) {
  return (
    <div className="space-y-2 text-xs text-gray-300">
      {data?.stage && (
        <div className="text-gray-400">Stage: {data.stage}</div>
      )}
      {data?.branchName && (
        <div><span className="text-gray-400">Branch:</span> {data.branchName}</div>
      )}
      {data?.sha && (
        <div><span className="text-gray-400">Commit:</span> {String(data.sha).slice(0, 7)}</div>
      )}
      {data?.prNumber && (
        <div><span className="text-gray-400">PR:</span> #{data.prNumber}</div>
      )}
      {data?.title && (
        <div className="text-gray-400">{data.title}</div>
      )}
      {data?.prUrl && (
        <div className="text-gray-400 break-all">{data.prUrl}</div>
      )}
    </div>
  );
}

function renderCi(data: any) {
  return (
    <div className="space-y-2 text-xs text-gray-300">
      {data?.state && (
        <div><span className="text-gray-400">State:</span> {data.state}</div>
      )}
      {data?.conclusion && (
        <div><span className="text-gray-400">Conclusion:</span> {data.conclusion}</div>
      )}
      {typeof data?.checkCount === 'number' && (
        <div><span className="text-gray-400">Checks:</span> {data.checkCount}</div>
      )}
      {typeof data?.failedChecks === 'number' && (
        <div><span className="text-gray-400">Failed:</span> {data.failedChecks}</div>
      )}
      {data?.url && (
        <div className="text-gray-400 break-all">{data.url}</div>
      )}
    </div>
  );
}

function renderCommand(data: any) {
  return (
    <div className="space-y-2 text-xs text-gray-300">
      {data?.command && (
        <div className="text-gray-400">{data.command}</div>
      )}
      {data?.cwd && (
        <div className="text-gray-500">cwd: {data.cwd}</div>
      )}
      {data?.status && (
        <div className="text-gray-400">Status: {data.status}</div>
      )}
      {typeof data?.exitCode === 'number' && (
        <div className="text-gray-400">Exit: {data.exitCode}</div>
      )}
      {(data?.stdout || data?.stderr) && (
        <details className="rounded border border-white/5 bg-black/30">
          <summary className="cursor-pointer px-2 py-1 text-gray-400">Output</summary>
          <pre className="max-h-56 overflow-auto whitespace-pre-wrap px-2 py-2 text-[11px] text-gray-200">
            {data?.stdout}
            {data?.stderr ? `\n${data.stderr}` : ''}
          </pre>
        </details>
      )}
      {data?.error && (
        <div className="text-red-400">Error: {data.error}</div>
      )}
    </div>
  );
}

function renderContext(data: any) {
  const files = Array.isArray(data?.files) ? data.files : [];
  if (!files.length) {
    return <div className="text-xs text-gray-400">No files captured for this response.</div>;
  }

  return (
    <div className="space-y-2 text-xs text-gray-300">
      {data?.summary && (
        <div className="text-gray-400">{data.summary}</div>
      )}
      <div className="space-y-1">
        <div className="text-gray-400">Files read:</div>
        <ul className="space-y-1">
          {files.map((file: any, index: number) => (
            <li key={`${file.path || index}`} className="flex items-center gap-2">
              {file.kind && <span className="text-gray-500">{file.kind}</span>}
              <span className="truncate">{file.path || 'unknown'}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function ArtifactCard({ artifact }: { artifact: ArtifactPayload }) {
  const label = KIND_LABELS[artifact.kind] || artifact.kind;

  const renderBody = () => {
    switch (artifact.kind) {
      case 'changePlan':
        return renderChangePlan(artifact.data);
      case 'diffs':
        return renderDiffs(artifact.data);
      case 'validation':
        return renderValidation(artifact.data);
      case 'apply':
        return renderApply(artifact.data);
      case 'pr':
        return renderPr(artifact.data);
      case 'ci':
        return renderCi(artifact.data);
      case 'command':
        return renderCommand(artifact.data);
      case 'context':
        return renderContext(artifact.data);
      default:
        return <div className="text-xs text-gray-400">No renderer for this artifact.</div>;
    }
  };

  return (
    <div className="animate-artifact-in rounded-lg border border-white/5 bg-[#16181f]/80 p-4">
      <div className="mb-3 flex items-start justify-between">
        <div className="text-sm font-medium text-gray-100">
          {artifact.title || label}
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-gray-400">
          {label}
        </span>
      </div>
      {renderBody()}
    </div>
  );
}
