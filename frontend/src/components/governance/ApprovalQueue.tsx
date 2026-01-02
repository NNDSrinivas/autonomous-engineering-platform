/**
 * Approval Queue
 * 
 * Displays pending approval requests with 1-click approve/reject functionality.
 * Shows risk scores, context, and explanations for each request.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import {
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Shield,
    User,
    GitBranch,
    Database,
    Code,
    Settings,
    Eye,
    Timer
} from 'lucide-react';
import { toast } from '@/components/ui/use-toast';

export interface ApprovalRequest {
    id: string;
    action_type: string;
    requester_id: string;
    risk_score: number;
    risk_reasons: string[];
    plan_summary: string;
    created_at: string;
    expires_at: string;
    context: {
        repo?: string;
        branch?: string;
        estimated_impact: string;
        touches_auth: boolean;
        touches_prod: boolean;
        is_multi_repo: boolean;
    };
}

const ACTION_ICONS: { [key: string]: React.ComponentType<any> } = {
    code_edit: Code,
    config_change: Settings,
    deploy_prod: Database,
    schema_change: Database,
    infrastructure_change: Shield,
    default: Settings
};

const RISK_COLORS = {
    low: 'text-green-600 bg-green-50 border-green-200',
    medium: 'text-yellow-600 bg-yellow-50 border-yellow-200',
    high: 'text-red-600 bg-red-50 border-red-200'
};

function getRiskLevel(score: number): keyof typeof RISK_COLORS {
    if (score >= 0.7) return 'high';
    if (score >= 0.3) return 'medium';
    return 'low';
}

function getTimeRemaining(expiresAt: string): { text: string; urgent: boolean } {
    const now = new Date();
    const expires = new Date(expiresAt);
    const diffMs = expires.getTime() - now.getTime();

    if (diffMs <= 0) {
        return { text: 'Expired', urgent: true };
    }

    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

    if (diffHours >= 24) {
        const diffDays = Math.floor(diffHours / 24);
        return { text: `${diffDays}d remaining`, urgent: false };
    } else if (diffHours > 0) {
        return { text: `${diffHours}h ${diffMinutes}m remaining`, urgent: diffHours < 2 };
    } else {
        return { text: `${diffMinutes}m remaining`, urgent: true };
    }
}

interface ApprovalQueueProps {
    userId?: string;
    onApprovalProcessed?: () => void;
}

export function ApprovalQueue({ userId, onApprovalProcessed }: ApprovalQueueProps) {
    const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState<string | null>(null);
    const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
    const [comment, setComment] = useState('');

    useEffect(() => {
        loadApprovals();

        // Auto-refresh every 30 seconds
        const interval = setInterval(loadApprovals, 30000);
        return () => clearInterval(interval);
    }, [userId]);

    const loadApprovals = async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams();
            if (userId) params.append('user_id', userId);

            const response = await fetch(`/api/governance/approvals?${params}`, {
                headers: {
                    'X-Org-Id': 'default',
                    'X-User-Id': 'current-user' // TODO: Get from auth
                }
            });

            if (response.ok) {
                const data = await response.json();
                setApprovals(data.approvals || []);
            }
        } catch (error) {
            console.error('Error loading approvals:', error);
            toast({
                title: 'Error',
                description: 'Failed to load approval requests.',
                variant: 'destructive'
            });
        } finally {
            setLoading(false);
        }
    };

    const processApproval = async (approvalId: string, decision: 'approve' | 'reject') => {
        try {
            setProcessing(approvalId);

            const endpoint = `/api/governance/approvals/${approvalId}/${decision}`;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': 'default',
                    'X-User-Id': 'current-user' // TODO: Get from auth
                },
                body: JSON.stringify({ comment })
            });

            if (response.ok) {
                toast({
                    title: 'Success',
                    description: `Request ${decision}d successfully.`,
                });

                // Remove from local state
                setApprovals(prev => prev.filter(a => a.id !== approvalId));
                setComment('');
                onApprovalProcessed?.();
            } else {
                throw new Error(`Failed to ${decision} request`);
            }
        } catch (error) {
            console.error(`Error ${decision}ing request:`, error);
            toast({
                title: 'Error',
                description: `Failed to ${decision} request.`,
                variant: 'destructive'
            });
        } finally {
            setProcessing(null);
        }
    };

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Clock className="h-5 w-5" />
                        Approval Queue
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-4">
                        {[...Array(3)].map((_, i) => (
                            <div key={i} className="border rounded-lg p-4 space-y-3">
                                <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                                <div className="h-3 bg-gray-200 rounded w-2/3"></div>
                                <div className="h-8 bg-gray-200 rounded w-full"></div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Clock className="h-5 w-5" />
                        Approval Queue
                        {approvals.length > 0 && (
                            <Badge variant="secondary">{approvals.length}</Badge>
                        )}
                    </div>
                    <Button variant="outline" size="sm" onClick={loadApprovals}>
                        Refresh
                    </Button>
                </CardTitle>
                <CardDescription>
                    Review and approve pending NAVI actions that require human oversight.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {approvals.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                        <CheckCircle className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                        <p className="text-lg font-medium">No pending approvals</p>
                        <p className="text-sm">All clear! NAVI is operating within approved parameters.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {approvals.map((approval) => {
                            const ActionIcon = ACTION_ICONS[approval.action_type] || ACTION_ICONS.default;
                            const riskLevel = getRiskLevel(approval.risk_score);
                            const timeRemaining = getTimeRemaining(approval.expires_at);

                            return (
                                <div key={approval.id} className="border rounded-lg p-4 space-y-3">
                                    {/* Header */}
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-center gap-3">
                                            <ActionIcon className="h-5 w-5 text-gray-600" />
                                            <div>
                                                <h3 className="font-medium">{approval.action_type.replace('_', ' ')}</h3>
                                                <p className="text-sm text-gray-600">{approval.plan_summary}</p>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            <Badge
                                                className={`${RISK_COLORS[riskLevel]} border`}
                                            >
                                                Risk: {(approval.risk_score * 100).toFixed(0)}%
                                            </Badge>
                                            <Badge
                                                variant={timeRemaining.urgent ? 'destructive' : 'outline'}
                                                className="flex items-center gap-1"
                                            >
                                                <Timer className="h-3 w-3" />
                                                {timeRemaining.text}
                                            </Badge>
                                        </div>
                                    </div>

                                    {/* Context */}
                                    <div className="flex flex-wrap gap-2 text-sm">
                                        <div className="flex items-center gap-1">
                                            <User className="h-3 w-3" />
                                            <span>{approval.requester_id}</span>
                                        </div>

                                        {approval.context.repo && (
                                            <div className="flex items-center gap-1">
                                                <GitBranch className="h-3 w-3" />
                                                <span>{approval.context.repo}</span>
                                                {approval.context.branch && (
                                                    <span className="text-gray-500">/{approval.context.branch}</span>
                                                )}
                                            </div>
                                        )}

                                        {approval.context.touches_auth && (
                                            <Badge variant="outline" className="text-xs">Auth</Badge>
                                        )}
                                        {approval.context.touches_prod && (
                                            <Badge variant="destructive" className="text-xs">Production</Badge>
                                        )}
                                        {approval.context.is_multi_repo && (
                                            <Badge variant="outline" className="text-xs">Multi-repo</Badge>
                                        )}
                                    </div>

                                    {/* Risk Reasons */}
                                    <div className="space-y-2">
                                        <Label className="text-sm font-medium">Why approval is required:</Label>
                                        <ul className="text-sm text-gray-600 space-y-1">
                                            {approval.risk_reasons.map((reason, index) => (
                                                <li key={index} className="flex items-start gap-2">
                                                    <AlertTriangle className="h-3 w-3 mt-0.5 text-yellow-500" />
                                                    {reason}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex items-center justify-between pt-2">
                                        <Dialog>
                                            <DialogTrigger asChild>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => setSelectedApproval(approval)}
                                                >
                                                    <Eye className="h-4 w-4 mr-1" />
                                                    View Details
                                                </Button>
                                            </DialogTrigger>
                                        </Dialog>

                                        <div className="flex gap-2">
                                            <Button
                                                variant="destructive"
                                                size="sm"
                                                onClick={() => processApproval(approval.id, 'reject')}
                                                disabled={processing === approval.id}
                                            >
                                                <XCircle className="h-4 w-4 mr-1" />
                                                Reject
                                            </Button>

                                            <Button
                                                size="sm"
                                                onClick={() => processApproval(approval.id, 'approve')}
                                                disabled={processing === approval.id}
                                            >
                                                <CheckCircle className="h-4 w-4 mr-1" />
                                                {processing === approval.id ? 'Processing...' : 'Approve'}
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </CardContent>

            {/* Approval Details Dialog */}
            {selectedApproval && (
                <Dialog open={!!selectedApproval} onOpenChange={() => setSelectedApproval(null)}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Approval Request Details</DialogTitle>
                            <DialogDescription>
                                Review the full context and make an informed decision.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-4">
                            {/* Basic Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <Label className="font-medium">Action Type</Label>
                                    <p className="text-sm">{selectedApproval.action_type}</p>
                                </div>
                                <div>
                                    <Label className="font-medium">Requester</Label>
                                    <p className="text-sm">{selectedApproval.requester_id}</p>
                                </div>
                                <div>
                                    <Label className="font-medium">Risk Score</Label>
                                    <p className="text-sm">{(selectedApproval.risk_score * 100).toFixed(0)}%</p>
                                </div>
                                <div>
                                    <Label className="font-medium">Impact</Label>
                                    <p className="text-sm capitalize">{selectedApproval.context.estimated_impact}</p>
                                </div>
                            </div>

                            <Separator />

                            {/* Plan Summary */}
                            <div>
                                <Label className="font-medium">Plan Summary</Label>
                                <p className="text-sm mt-1 p-3 bg-gray-50 rounded border">
                                    {selectedApproval.plan_summary}
                                </p>
                            </div>

                            {/* Risk Analysis */}
                            <div>
                                <Label className="font-medium">Risk Analysis</Label>
                                <ul className="text-sm mt-1 space-y-1">
                                    {selectedApproval.risk_reasons.map((reason, index) => (
                                        <li key={index} className="flex items-start gap-2">
                                            <AlertTriangle className="h-3 w-3 mt-0.5 text-yellow-500" />
                                            {reason}
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Comment */}
                            <div className="space-y-2">
                                <Label htmlFor="comment">Approval Comment (Optional)</Label>
                                <Textarea
                                    id="comment"
                                    placeholder="Add a comment explaining your decision..."
                                    value={comment}
                                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setComment(e.target.value)}
                                    rows={3}
                                />
                            </div>

                            {/* Action Buttons */}
                            <div className="flex justify-end gap-2 pt-4">
                                <Button
                                    variant="destructive"
                                    onClick={() => {
                                        processApproval(selectedApproval.id, 'reject');
                                        setSelectedApproval(null);
                                    }}
                                    disabled={processing === selectedApproval.id}
                                >
                                    <XCircle className="h-4 w-4 mr-2" />
                                    Reject Request
                                </Button>

                                <Button
                                    onClick={() => {
                                        processApproval(selectedApproval.id, 'approve');
                                        setSelectedApproval(null);
                                    }}
                                    disabled={processing === selectedApproval.id}
                                >
                                    <CheckCircle className="h-4 w-4 mr-2" />
                                    Approve Request
                                </Button>
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </Card>
    );
}