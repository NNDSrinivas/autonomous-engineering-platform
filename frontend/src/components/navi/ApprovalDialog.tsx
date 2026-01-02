import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  GitBranch,
  GitPullRequest,
  FileCode,
  Play,
  RefreshCw,
  Loader2,
  MessageSquare,
  FileText,
  Rocket,
  StopCircle,
  Link2,
  Edit3,
  Copy
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WriteActionType, RiskLevel, PendingAction } from '@/hooks/useApprovalGate';

export type ActionType = WriteActionType;

export interface ApprovalAction extends PendingAction {}

interface ApprovalDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  action: ApprovalAction | null;
  onApprove: (action: ApprovalAction) => Promise<void>;
  onReject: (action: ApprovalAction) => void;
}

const actionIcons: Record<WriteActionType, React.ReactNode> = {
  // GitHub
  github_create_branch: <GitBranch className="h-5 w-5" />,
  github_create_pr: <GitPullRequest className="h-5 w-5" />,
  github_merge_pr: <GitPullRequest className="h-5 w-5" />,
  github_commit_files: <FileCode className="h-5 w-5" />,
  github_update_file: <FileCode className="h-5 w-5" />,
  // CI/CD
  cicd_rerun_workflow: <RefreshCw className="h-5 w-5" />,
  cicd_cancel_workflow: <StopCircle className="h-5 w-5" />,
  cicd_trigger_deploy: <Rocket className="h-5 w-5" />,
  // Slack
  slack_post_message: <MessageSquare className="h-5 w-5" />,
  slack_post_thread_reply: <MessageSquare className="h-5 w-5" />,
  // Confluence
  confluence_create_page: <FileText className="h-5 w-5" />,
  confluence_update_page: <Edit3 className="h-5 w-5" />,
  // Jira
  jira_update_status: <Play className="h-5 w-5" />,
  jira_add_comment: <MessageSquare className="h-5 w-5" />,
  jira_link_pr: <Link2 className="h-5 w-5" />,
};

const actionLabels: Record<WriteActionType, string> = {
  github_create_branch: 'Create Git Branch',
  github_create_pr: 'Create Pull Request',
  github_merge_pr: 'Merge Pull Request',
  github_commit_files: 'Commit Files',
  github_update_file: 'Update File',
  cicd_rerun_workflow: 'Re-run CI/CD Workflow',
  cicd_cancel_workflow: 'Cancel CI/CD Workflow',
  cicd_trigger_deploy: 'Trigger Deployment',
  slack_post_message: 'Post Slack Message',
  slack_post_thread_reply: 'Reply in Slack Thread',
  confluence_create_page: 'Create Confluence Page',
  confluence_update_page: 'Update Confluence Page',
  jira_update_status: 'Update Jira Status',
  jira_add_comment: 'Add Jira Comment',
  jira_link_pr: 'Link PR to Jira Issue',
};

const riskColors: Record<RiskLevel, string> = {
  low: 'bg-status-success/20 text-status-success border-status-success/30',
  medium: 'bg-status-warning/20 text-status-warning border-status-warning/30',
  high: 'bg-status-error/20 text-status-error border-status-error/30',
  critical: 'bg-destructive/20 text-destructive border-destructive/30',
};

const integrationColors: Record<string, string> = {
  github: 'text-github-gray',
  cicd: 'text-cicd-orange',
  slack: 'text-slack-purple',
  confluence: 'text-confluence-blue',
  jira: 'text-jira-blue',
};

export function ApprovalDialog({
  open,
  onOpenChange,
  action,
  onApprove,
  onReject,
}: ApprovalDialogProps) {
  const [isProcessing, setIsProcessing] = useState(false);

  if (!action) return null;

  const handleApprove = async () => {
    setIsProcessing(true);
    try {
      await onApprove(action);
      onOpenChange(false);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = () => {
    onReject(action);
    onOpenChange(false);
  };

  const handleCopyDraft = () => {
    if (action.metadata?.draftContent) {
      navigator.clipboard.writeText(action.metadata.draftContent);
    }
  };

  const integration = action.metadata?.integration || action.type.split('_')[0];
  const isDraft = action.metadata?.draftContent;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className={cn(
              "h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center",
              integrationColors[integration] || 'text-primary'
            )}>
              {actionIcons[action.type]}
            </div>
            <div>
              <DialogTitle className="flex items-center gap-2">
                {actionLabels[action.type]}
                <Badge 
                  variant="outline" 
                  className={cn("text-[10px] uppercase", riskColors[action.risk])}
                >
                  {action.risk} risk
                </Badge>
              </DialogTitle>
              <DialogDescription className="mt-1">
                NAVI wants to perform the following action
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="rounded-lg bg-secondary/50 p-4 space-y-2">
            <h4 className="font-medium text-sm">{action.title}</h4>
            <p className="text-sm text-muted-foreground">{action.description}</p>
          </div>

          {/* Draft content preview */}
          {isDraft && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Draft Content
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyDraft}
                  className="h-6 text-xs gap-1"
                >
                  <Copy className="h-3 w-3" />
                  Copy
                </Button>
              </div>
              <Textarea
                value={action.metadata?.draftContent || ''}
                readOnly
                className="min-h-[100px] text-sm font-mono bg-muted/50"
              />
            </div>
          )}

          {action.details && Object.keys(action.details).length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Details
              </h4>
              <ScrollArea className="max-h-48">
                <div className="space-y-2 text-sm">
                  {Object.entries(action.details).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-4">
                      <span className="text-muted-foreground capitalize">
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span className="font-mono text-xs truncate max-w-[200px]">
                        {String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}

          {(action.risk === 'high' || action.risk === 'critical') && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-status-warning/10 border border-status-warning/30">
              <AlertTriangle className="h-4 w-4 text-status-warning flex-shrink-0 mt-0.5" />
              <p className="text-xs text-status-warning">
                {action.risk === 'critical' 
                  ? 'This is a critical action that could have significant impact. Please review very carefully.'
                  : 'This action has high risk. Please review carefully before approving.'}
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={handleReject}
            disabled={isProcessing}
            className="gap-2"
          >
            <XCircle className="h-4 w-4" />
            {isDraft ? 'Discard' : 'Reject'}
          </Button>
          <Button
            onClick={handleApprove}
            disabled={isProcessing}
            className="gap-2"
          >
            {isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            {isProcessing ? 'Processing...' : (isDraft ? 'Approve & Send' : 'Approve')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
