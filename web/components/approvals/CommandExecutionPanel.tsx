/**
 * CommandExecutionPanel Component
 * Displays command execution details with real-time output
 */

import React from 'react';
import { Terminal, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface CommandExecution {
  command: string;
  workingDirectory?: string;
  description?: string;
  status: 'pending' | 'running' | 'success' | 'error';
  stdout?: string;
  stderr?: string;
  exitCode?: number;
  startTime?: string;
  endTime?: string;
  duration?: number; // in milliseconds
}

export interface CommandExecutionPanelProps {
  execution: CommandExecution;
  showOutput?: boolean;
  className?: string;
}

export function CommandExecutionPanel({
  execution,
  showOutput = true,
  className
}: CommandExecutionPanelProps) {
  const { command, workingDirectory, description, status, stdout, stderr, exitCode, duration } = execution;

  const getStatusIcon = () => {
    switch (status) {
      case 'pending':
        return <Clock className="text-muted-foreground" size={18} />;
      case 'running':
        return <Loader2 className="text-blue-600 animate-spin" size={18} />;
      case 'success':
        return <CheckCircle className="text-green-600" size={18} />;
      case 'error':
        return <XCircle className="text-red-600" size={18} />;
    }
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'pending':
        return 'Awaiting approval';
      case 'running':
        return 'Executing...';
      case 'success':
        return 'Completed successfully';
      case 'error':
        return 'Failed';
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'pending':
        return 'text-muted-foreground';
      case 'running':
        return 'text-blue-600';
      case 'success':
        return 'text-green-600';
      case 'error':
        return 'text-red-600';
    }
  };

  return (
    <div className={cn("border rounded-lg overflow-hidden", className)}>
      {/* Header */}
      <div className="bg-muted/50 px-4 py-3 border-b">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            <Terminal size={18} className="text-muted-foreground flex-shrink-0 mt-0.5" />
            <h4 className="font-medium">Command Execution</h4>
          </div>

          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className={cn("text-sm font-medium", getStatusColor())}>
              {getStatusLabel()}
            </span>
          </div>
        </div>

        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>

      {/* Command Details */}
      <div className="p-4 space-y-3">
        {/* Working Directory */}
        {workingDirectory && (
          <div>
            <label className="text-xs font-medium text-muted-foreground">
              Working Directory
            </label>
            <p className="text-sm font-mono bg-muted/50 px-2 py-1 rounded mt-1">
              {workingDirectory}
            </p>
          </div>
        )}

        {/* Command */}
        <div>
          <label className="text-xs font-medium text-muted-foreground">
            Command
          </label>
          <pre className="text-sm font-mono bg-black/90 text-green-400 px-3 py-2 rounded mt-1 overflow-x-auto">
            <code>$ {command}</code>
          </pre>
        </div>

        {/* Output (if available) */}
        {showOutput && (stdout || stderr) && (
          <div>
            <label className="text-xs font-medium text-muted-foreground">
              Output
            </label>

            <div className="mt-1 bg-black/90 rounded overflow-hidden">
              {stdout && (
                <pre className="text-xs font-mono text-gray-300 px-3 py-2 overflow-x-auto max-h-[300px] overflow-y-auto">
                  <code>{stdout}</code>
                </pre>
              )}

              {stderr && (
                <pre className="text-xs font-mono text-red-400 px-3 py-2 overflow-x-auto max-h-[300px] overflow-y-auto border-t border-gray-700">
                  <code>{stderr}</code>
                </pre>
              )}
            </div>
          </div>
        )}

        {/* Execution Details */}
        {(exitCode !== undefined || duration !== undefined) && (
          <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
            {exitCode !== undefined && (
              <span className="flex items-center gap-1">
                Exit Code:
                <span className={cn(
                  "font-mono font-medium",
                  exitCode === 0 ? "text-green-600" : "text-red-600"
                )}>
                  {exitCode}
                </span>
              </span>
            )}

            {duration !== undefined && (
              <span className="flex items-center gap-1">
                <Clock size={12} />
                Duration: {duration}ms
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default CommandExecutionPanel;
