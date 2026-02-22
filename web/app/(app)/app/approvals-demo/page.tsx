"use client";

/**
 * Approvals Demo Page
 * Demonstrates the action approval system with examples
 */

import React from 'react';
import { ApprovalPanel } from '@/components/approvals/ApprovalPanel';
import { FileDiffViewer } from '@/components/approvals/FileDiffViewer';
import { CommandExecutionPanel } from '@/components/approvals/CommandExecutionPanel';
import { Button } from '@/components/ui/button';
import {
  useApprovalsStore,
  createFileOperationApproval,
  createCommandApproval
} from '@/lib/stores/approvalsStore';

// Example data
const exampleFileDiffs = [
  {
    oldPath: 'src/components/Button.tsx',
    newPath: 'src/components/Button.tsx',
    oldContent: `export function Button({ children, onClick }) {
  return (
    <button onClick={onClick}>
      {children}
    </button>
  );
}`,
    newContent: `export function Button({ children, onClick, variant = 'primary' }) {
  const className = variant === 'primary' ? 'btn-primary' : 'btn-secondary';

  return (
    <button onClick={onClick} className={className}>
      {children}
    </button>
  );
}`,
    type: 'modify' as const
  }
];

export default function ApprovalsDemoPage() {
  const {
    activeAction,
    pendingActions,
    approveAction,
    rejectAction,
    addAction,
    isProcessing,
    clearActions
  } = useApprovalsStore();

  const handleAddFileChangeApproval = () => {
    const approval = createFileOperationApproval(
      exampleFileDiffs,
      'Add variant prop to Button component'
    );
    addAction(approval);
  };

  const handleAddCommandApproval = () => {
    const approval = createCommandApproval(
      'npm install react-query',
      '/path/to/project',
      'Install React Query for data fetching'
    );
    addAction(approval);
  };

  const handleAddHighRiskCommand = () => {
    const approval = createCommandApproval(
      'git push origin main --force',
      '/path/to/project',
      'Force push to main branch'
    );
    addAction(approval);
  };

  return (
    <div className="container max-w-5xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Approval System Demo</h1>
        <p className="text-muted-foreground">
          Demonstrating the action approval system with risk assessment and sequential workflow
        </p>
      </div>

      {/* Demo Controls */}
      <div className="mb-8 p-4 border rounded-lg bg-muted/30">
        <h2 className="text-lg font-semibold mb-3">Add Test Approvals</h2>
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleAddFileChangeApproval} variant="outline">
            Add File Change (Medium Risk)
          </Button>
          <Button onClick={handleAddCommandApproval} variant="outline">
            Add Command (Low Risk)
          </Button>
          <Button onClick={handleAddHighRiskCommand} variant="outline">
            Add High Risk Command
          </Button>
          <Button onClick={clearActions} variant="destructive">
            Clear All
          </Button>
        </div>

        <div className="mt-3 text-sm text-muted-foreground">
          Pending actions: {pendingActions.length}
        </div>
      </div>

      {/* Active Approval */}
      {activeAction ? (
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Current Approval Request</h2>

          <ApprovalPanel
            action={activeAction}
            onApprove={approveAction}
            onReject={rejectAction}
            isProcessing={isProcessing}
          />

          {/* Render details based on action type */}
          {activeAction.type === 'file_edit' ||
           activeAction.type === 'file_create' ||
           activeAction.type === 'file_delete' ? (
            <FileDiffViewer diffs={activeAction.details.fileDiffs} className="mt-4" />
          ) : activeAction.type === 'command' ? (
            <CommandExecutionPanel
              execution={activeAction.details.execution}
              className="mt-4"
              showOutput={false}
            />
          ) : null}
        </div>
      ) : (
        <div className="text-center py-12 border rounded-lg bg-muted/10">
          <p className="text-lg text-muted-foreground mb-2">No pending approvals</p>
          <p className="text-sm text-muted-foreground">
            Add test approvals using the buttons above
          </p>
        </div>
      )}

      {/* Queue Preview */}
      {pendingActions.length > 1 && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold mb-3">
            Approval Queue ({pendingActions.length - 1} remaining)
          </h3>
          <div className="space-y-2">
            {pendingActions.slice(1).map((action, index) => (
              <div
                key={action.id}
                className="p-3 border rounded-lg bg-muted/10 flex items-center justify-between"
              >
                <div>
                  <span className="text-sm font-medium">#{index + 2}</span>
                  <span className="text-sm ml-3">{action.description}</span>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${
                  action.riskLevel === 'high'
                    ? 'bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-400'
                    : action.riskLevel === 'medium'
                    ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950/30 dark:text-yellow-400'
                    : 'bg-green-100 text-green-700 dark:bg-green-950/30 dark:text-green-400'
                }`}>
                  {action.riskLevel} risk
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Example Components Showcase */}
      <div className="mt-12 space-y-8">
        <div>
          <h2 className="text-2xl font-bold mb-4">Component Examples</h2>
        </div>

        {/* File Diff Viewer Example */}
        <div>
          <h3 className="text-lg font-semibold mb-3">File Diff Viewer</h3>
          <FileDiffViewer diffs={exampleFileDiffs} />
        </div>

        {/* Command Execution Panel Example */}
        <div>
          <h3 className="text-lg font-semibold mb-3">Command Execution Panel</h3>
          <CommandExecutionPanel
            execution={{
              command: 'npm test',
              workingDirectory: '/path/to/project',
              description: 'Run test suite',
              status: 'success',
              stdout: 'PASS  src/components/Button.test.tsx\n  ✓ renders correctly (23ms)\n  ✓ handles click events (5ms)\n\nTest Suites: 1 passed, 1 total\nTests:       2 passed, 2 total\nTime:        2.456s',
              exitCode: 0,
              duration: 2456
            }}
          />
        </div>
      </div>
    </div>
  );
}
