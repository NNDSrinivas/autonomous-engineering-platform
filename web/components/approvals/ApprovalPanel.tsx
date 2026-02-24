/**
 * ApprovalPanel Component
 * Displays proposed actions with risk assessment for user approval
 */

import React from 'react';
import { Button } from '@/components/ui/button';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  ShieldAlert,
  Clock,
  Info
} from 'lucide-react';
import { cn } from '@/lib/utils';

export type RiskLevel = 'low' | 'medium' | 'high';
export type ActionType = 'file_edit' | 'file_create' | 'file_delete' | 'command' | 'git_operation';

export interface ProposedAction {
  id: string;
  type: ActionType;
  description: string;
  riskLevel: RiskLevel;
  details: any; // File diffs, command details, etc.
  timestamp: string;
}

export interface ApprovalPanelProps {
  action: ProposedAction;
  onApprove: (actionId: string) => void;
  onReject: (actionId: string) => void;
  isProcessing?: boolean;
}

const riskConfig = {
  low: {
    icon: Shield,
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950/30',
    borderColor: 'border-green-200 dark:border-green-800',
    label: 'Low Risk',
    description: 'Read operations, info gathering, or safe reversible changes'
  },
  medium: {
    icon: AlertTriangle,
    color: 'text-yellow-600 dark:text-yellow-400',
    bgColor: 'bg-yellow-50 dark:bg-yellow-950/30',
    borderColor: 'border-yellow-200 dark:border-yellow-800',
    label: 'Medium Risk',
    description: 'File edits, reversible changes that modify existing code'
  },
  high: {
    icon: ShieldAlert,
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-50 dark:bg-red-950/30',
    borderColor: 'border-red-200 dark:border-red-800',
    label: 'High Risk',
    description: 'Deletions, destructive commands, git operations, or irreversible actions'
  }
};

const actionTypeLabels: Record<ActionType, string> = {
  file_edit: 'File Edit',
  file_create: 'File Create',
  file_delete: 'File Delete',
  command: 'Command Execution',
  git_operation: 'Git Operation'
};

export function ApprovalPanel({
  action,
  onApprove,
  onReject,
  isProcessing = false
}: ApprovalPanelProps) {
  const risk = riskConfig[action.riskLevel];
  const RiskIcon = risk.icon;

  return (
    <div
      className={cn(
        "rounded-lg border-2 p-4 mb-4 transition-all",
        risk.bgColor,
        risk.borderColor
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-start gap-3 flex-1">
          <RiskIcon className={cn("mt-1 flex-shrink-0", risk.color)} size={24} />

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-lg">
                {actionTypeLabels[action.type]}
              </h3>
              <span className={cn(
                "px-2 py-0.5 rounded-full text-xs font-medium",
                risk.bgColor,
                risk.color
              )}>
                {risk.label}
              </span>
            </div>

            <p className="text-sm text-muted-foreground mb-2">
              {action.description}
            </p>

            {/* Risk Description */}
            <div className={cn(
              "flex items-start gap-2 p-2 rounded text-xs",
              risk.bgColor
            )}>
              <Info size={14} className={cn("mt-0.5 flex-shrink-0", risk.color)} />
              <span className={risk.color}>{risk.description}</span>
            </div>
          </div>
        </div>

        {/* Timestamp */}
        <div className="flex items-center gap-1 text-xs text-muted-foreground ml-4">
          <Clock size={12} />
          {new Date(action.timestamp).toLocaleTimeString()}
        </div>
      </div>

      {/* Action Details (rendered by parent components like FileDiffViewer) */}
      <div className="my-4">
        {/* Details will be passed as children or via details prop */}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
        <Button
          variant="outline"
          onClick={() => onReject(action.id)}
          disabled={isProcessing}
          className="gap-2"
        >
          <XCircle size={16} />
          Reject
        </Button>

        <Button
          onClick={() => onApprove(action.id)}
          disabled={isProcessing}
          className={cn(
            "gap-2",
            action.riskLevel === 'high' && "bg-red-600 hover:bg-red-700"
          )}
        >
          <CheckCircle size={16} />
          {isProcessing ? 'Processing...' : 'Approve & Execute'}
        </Button>
      </div>
    </div>
  );
}

export default ApprovalPanel;
