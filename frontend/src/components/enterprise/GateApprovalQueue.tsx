/**
 * GateApprovalQueue Component
 *
 * Queue view for managing pending human checkpoint gates across all enterprise projects.
 * Provides a centralized location for team leads/managers to review and approve decisions.
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Shield,
  DollarSign,
  Rocket,
  Target,
  Building,
  ChevronDown,
  ChevronUp,
  Filter,
  RefreshCw,
  Bell,
} from 'lucide-react';

export type GateType =
  | 'architecture_review'
  | 'security_review'
  | 'cost_approval'
  | 'deployment_approval'
  | 'milestone_review';

export type GatePriority = 'low' | 'medium' | 'high' | 'critical';

export interface GateOption {
  id: string;
  label: string;
  description: string;
  tradeOffs?: string[];
  recommended?: boolean;
  estimatedCost?: string;
  riskLevel?: 'low' | 'medium' | 'high';
}

export interface HumanGate {
  id: string;
  projectId: string;
  projectName: string;
  gateType: GateType;
  title: string;
  description: string;
  context?: string;
  options: GateOption[];
  blocksProgress: boolean;
  priority: GatePriority;
  createdAt: string;
  metadata?: {
    affectedFiles?: string[];
    estimatedImpact?: string;
    relatedTasks?: string[];
    requestedBy?: string;
  };
}

export interface GateDecision {
  gateId: string;
  approved: boolean;
  selectedOptionId?: string;
  reason?: string;
  decidedBy?: string;
  decidedAt: string;
}

export interface GateApprovalQueueProps {
  gates: HumanGate[];
  onDecision: (decision: GateDecision) => void;
  onRefresh: () => void;
  isLoading?: boolean;
}

const GATE_TYPE_CONFIG: Record<GateType, { icon: React.ReactNode; label: string; color: string }> = {
  architecture_review: { icon: <Building className="w-4 h-4" />, label: 'Architecture', color: 'bg-purple-500' },
  security_review: { icon: <Shield className="w-4 h-4" />, label: 'Security', color: 'bg-red-500' },
  cost_approval: { icon: <DollarSign className="w-4 h-4" />, label: 'Cost', color: 'bg-yellow-500' },
  deployment_approval: { icon: <Rocket className="w-4 h-4" />, label: 'Deployment', color: 'bg-blue-500' },
  milestone_review: { icon: <Target className="w-4 h-4" />, label: 'Milestone', color: 'bg-green-500' },
};

const PRIORITY_CONFIG: Record<GatePriority, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-gray-500' },
  medium: { label: 'Medium', color: 'bg-blue-500' },
  high: { label: 'High', color: 'bg-orange-500' },
  critical: { label: 'Critical', color: 'bg-red-500' },
};

const GateCard: React.FC<{
  gate: HumanGate;
  onDecision: (decision: GateDecision) => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}> = ({ gate, onDecision, isExpanded, onToggleExpand }) => {
  const [selectedOption, setSelectedOption] = useState<string | null>(
    gate.options.find(o => o.recommended)?.id || null
  );
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const gateConfig = GATE_TYPE_CONFIG[gate.gateType];
  const priorityConfig = PRIORITY_CONFIG[gate.priority];

  const handleApprove = async () => {
    if (gate.options.length > 0 && !selectedOption) return;

    setIsSubmitting(true);
    try {
      await onDecision({
        gateId: gate.id,
        approved: true,
        selectedOptionId: selectedOption || undefined,
        reason: reason || undefined,
        decidedAt: new Date().toISOString(),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    try {
      await onDecision({
        gateId: gate.id,
        approved: false,
        reason: reason || 'Rejected by reviewer',
        decidedAt: new Date().toISOString(),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const timeSinceCreated = () => {
    const now = new Date();
    const created = new Date(gate.createdAt);
    const diffMs = now.getTime() - created.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMins = Math.floor(diffMs / (1000 * 60));

    if (diffHours >= 24) {
      return `${Math.floor(diffHours / 24)}d ago`;
    } else if (diffHours >= 1) {
      return `${diffHours}h ago`;
    } else {
      return `${diffMins}m ago`;
    }
  };

  return (
    <Card className={`border-l-4 ${gate.blocksProgress ? 'border-l-orange-500' : 'border-l-gray-300'}`}>
      <CardHeader className="pb-3 cursor-pointer" onClick={onToggleExpand}>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className={`${gateConfig.color} text-white border-0`}>
                {gateConfig.icon}
                <span className="ml-1">{gateConfig.label}</span>
              </Badge>
              <Badge variant="outline" className={`${priorityConfig.color} text-white border-0`}>
                {priorityConfig.label}
              </Badge>
              {gate.blocksProgress && (
                <Badge variant="outline" className="bg-orange-500/20 text-orange-500 border-orange-500/30">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Blocking
                </Badge>
              )}
            </div>
            <CardTitle className="text-base">{gate.title}</CardTitle>
            <CardDescription className="mt-1 flex items-center gap-2">
              <span>{gate.projectName}</span>
              <span className="text-muted-foreground">•</span>
              <Clock className="w-3 h-3" />
              <span>{timeSinceCreated()}</span>
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </Button>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent>
          {/* Description */}
          <div className="mb-4">
            <p className="text-sm text-muted-foreground">{gate.description}</p>
          </div>

          {/* Context */}
          {gate.context && (
            <div className="mb-4 p-3 bg-muted rounded-lg">
              <p className="text-xs font-semibold mb-1">Additional Context</p>
              <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                {gate.context}
              </pre>
            </div>
          )}

          {/* Metadata */}
          {gate.metadata && (
            <div className="mb-4 grid grid-cols-2 gap-4">
              {gate.metadata.affectedFiles && gate.metadata.affectedFiles.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1">Affected Files</p>
                  <div className="flex flex-wrap gap-1">
                    {gate.metadata.affectedFiles.slice(0, 3).map((file, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        {file.split('/').pop()}
                      </Badge>
                    ))}
                    {gate.metadata.affectedFiles.length > 3 && (
                      <Badge variant="outline" className="text-xs">
                        +{gate.metadata.affectedFiles.length - 3} more
                      </Badge>
                    )}
                  </div>
                </div>
              )}
              {gate.metadata.estimatedImpact && (
                <div>
                  <p className="text-xs font-semibold mb-1">Estimated Impact</p>
                  <p className="text-xs text-muted-foreground">{gate.metadata.estimatedImpact}</p>
                </div>
              )}
            </div>
          )}

          {/* Options */}
          {gate.options.length > 0 && (
            <div className="mb-4">
              <Label className="text-sm font-semibold mb-2 block">Select an option:</Label>
              <div className="space-y-2">
                {gate.options.map((option) => (
                  <div
                    key={option.id}
                    className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedOption === option.id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => !isSubmitting && setSelectedOption(option.id)}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`w-4 h-4 rounded-full border-2 flex-shrink-0 mt-0.5 ${
                          selectedOption === option.id
                            ? 'border-primary bg-primary'
                            : 'border-muted-foreground'
                        }`}
                      >
                        {selectedOption === option.id && (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="w-1.5 h-1.5 bg-white rounded-full" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{option.label}</span>
                          {option.recommended && (
                            <Badge className="bg-green-500/20 text-green-500 border-0 text-xs">
                              Recommended
                            </Badge>
                          )}
                          {option.riskLevel && (
                            <Badge
                              variant="outline"
                              className={`text-xs ${
                                option.riskLevel === 'high'
                                  ? 'text-red-500 border-red-500/30'
                                  : option.riskLevel === 'medium'
                                  ? 'text-yellow-500 border-yellow-500/30'
                                  : 'text-green-500 border-green-500/30'
                              }`}
                            >
                              {option.riskLevel} risk
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">{option.description}</p>
                        {option.tradeOffs && option.tradeOffs.length > 0 && (
                          <div className="mt-2">
                            <span className="text-xs font-medium text-orange-500">Trade-offs:</span>
                            <ul className="text-xs text-muted-foreground list-disc list-inside">
                              {option.tradeOffs.map((tradeoff, idx) => (
                                <li key={idx}>{tradeoff}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {option.estimatedCost && (
                          <p className="text-xs text-yellow-500 mt-1">
                            Est. Cost: {option.estimatedCost}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reason */}
          <div className="mb-4">
            <Label htmlFor={`reason-${gate.id}`} className="text-sm font-semibold mb-2 block">
              Decision Reason (optional)
            </Label>
            <Textarea
              id={`reason-${gate.id}`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Add a note about your decision..."
              disabled={isSubmitting}
              rows={2}
              className="text-sm"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2 justify-end">
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={isSubmitting}
            >
              <XCircle className="w-4 h-4 mr-2" />
              Reject
            </Button>
            <Button
              onClick={handleApprove}
              disabled={isSubmitting || (gate.options.length > 0 && !selectedOption)}
            >
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Approve
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
};

const QueueStats: React.FC<{ gates: HumanGate[] }> = ({ gates }) => {
  const blocking = gates.filter(g => g.blocksProgress).length;
  const critical = gates.filter(g => g.priority === 'critical').length;
  const byType = gates.reduce((acc, g) => {
    acc[g.gateType] = (acc[g.gateType] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg">
              <Bell className="w-5 h-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{gates.length}</p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-500/10 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{blocking}</p>
              <p className="text-xs text-muted-foreground">Blocking</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <Shield className="w-5 h-5 text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{critical}</p>
              <p className="text-xs text-muted-foreground">Critical</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <Building className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{byType.architecture_review || 0}</p>
              <p className="text-xs text-muted-foreground">Architecture</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export const GateApprovalQueue: React.FC<GateApprovalQueueProps> = ({
  gates,
  onDecision,
  onRefresh,
  isLoading = false,
}) => {
  const [expandedGates, setExpandedGates] = useState<Set<string>>(new Set());
  const [typeFilter, setTypeFilter] = useState<GateType | 'all'>('all');

  const toggleExpand = (gateId: string) => {
    const newExpanded = new Set(expandedGates);
    if (newExpanded.has(gateId)) {
      newExpanded.delete(gateId);
    } else {
      newExpanded.add(gateId);
    }
    setExpandedGates(newExpanded);
  };

  const filteredGates = gates.filter(gate => {
    if (typeFilter !== 'all' && gate.gateType !== typeFilter) {
      return false;
    }
    return true;
  });

  // Sort by priority (critical first) then by blocking status
  const sortedGates = [...filteredGates].sort((a, b) => {
    const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    if (a.blocksProgress !== b.blocksProgress) {
      return a.blocksProgress ? -1 : 1;
    }
    return priorityOrder[a.priority] - priorityOrder[b.priority];
  });

  const blockingGates = sortedGates.filter(g => g.blocksProgress);
  const nonBlockingGates = sortedGates.filter(g => !g.blocksProgress);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Approval Queue</h1>
          <p className="text-muted-foreground">
            Review and approve pending checkpoint gates
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={isLoading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Stats */}
      <QueueStats gates={gates} />

      {/* Tabs by Type */}
      <Tabs defaultValue="all" className="w-full">
        <div className="flex items-center justify-between mb-4">
          <TabsList>
            <TabsTrigger value="all" onClick={() => setTypeFilter('all')}>
              All ({gates.length})
            </TabsTrigger>
            <TabsTrigger value="architecture" onClick={() => setTypeFilter('architecture_review')}>
              <Building className="w-4 h-4 mr-1" />
              Architecture
            </TabsTrigger>
            <TabsTrigger value="security" onClick={() => setTypeFilter('security_review')}>
              <Shield className="w-4 h-4 mr-1" />
              Security
            </TabsTrigger>
            <TabsTrigger value="cost" onClick={() => setTypeFilter('cost_approval')}>
              <DollarSign className="w-4 h-4 mr-1" />
              Cost
            </TabsTrigger>
            <TabsTrigger value="deployment" onClick={() => setTypeFilter('deployment_approval')}>
              <Rocket className="w-4 h-4 mr-1" />
              Deploy
            </TabsTrigger>
          </TabsList>

          <Button variant="outline" size="sm">
            <Filter className="w-4 h-4" />
          </Button>
        </div>

        <TabsContent value="all">
          {sortedGates.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <CheckCircle2 className="w-12 h-12 text-green-500 mb-4" />
                <h3 className="text-lg font-semibold mb-2">Queue Empty</h3>
                <p className="text-muted-foreground text-center">
                  No pending decisions at this time.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Blocking section */}
              {blockingGates.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-4 h-4 text-orange-500" />
                    <h3 className="text-sm font-semibold text-orange-500">
                      Blocking ({blockingGates.length})
                    </h3>
                  </div>
                  <div className="space-y-3">
                    {blockingGates.map(gate => (
                      <GateCard
                        key={gate.id}
                        gate={gate}
                        onDecision={onDecision}
                        isExpanded={expandedGates.has(gate.id)}
                        onToggleExpand={() => toggleExpand(gate.id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Non-blocking section */}
              {nonBlockingGates.length > 0 && (
                <div>
                  {blockingGates.length > 0 && (
                    <div className="flex items-center gap-2 mb-3 mt-6">
                      <Clock className="w-4 h-4 text-muted-foreground" />
                      <h3 className="text-sm font-semibold text-muted-foreground">
                        Non-Blocking ({nonBlockingGates.length})
                      </h3>
                    </div>
                  )}
                  <div className="space-y-3">
                    {nonBlockingGates.map(gate => (
                      <GateCard
                        key={gate.id}
                        gate={gate}
                        onDecision={onDecision}
                        isExpanded={expandedGates.has(gate.id)}
                        onToggleExpand={() => toggleExpand(gate.id)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* Type-specific tabs reuse the same content with filtered data */}
        {['architecture', 'security', 'cost', 'deployment'].map(type => (
          <TabsContent key={type} value={type}>
            <div className="space-y-3">
              {sortedGates.map(gate => (
                <GateCard
                  key={gate.id}
                  gate={gate}
                  onDecision={onDecision}
                  isExpanded={expandedGates.has(gate.id)}
                  onToggleExpand={() => toggleExpand(gate.id)}
                />
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default GateApprovalQueue;
