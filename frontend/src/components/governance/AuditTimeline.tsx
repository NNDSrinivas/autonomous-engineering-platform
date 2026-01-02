/**
 * Audit Timeline
 * 
 * Displays chronological audit trail with detailed action history.
 * Shows decisions, risk scores, rollback options, and complete audit context.
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import {
    History,
    Search,
    Filter,
    User,
    Clock,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Shield,
    RotateCcw,
    Eye,
    Activity,
    ArrowLeft,
    ArrowRight,
    RefreshCw
} from 'lucide-react';
import { toast } from '@/components/ui/use-toast';

interface AuditEntry {
    id: string;
    timestamp: string;
    user_id: string;
    action_type: string;
    decision: string;
    risk_score: number;
    execution_result?: string;
    rollback_available: boolean;
    artifacts: {
        [key: string]: any;
    };
}

const DECISION_COLORS = {
    AUTO: 'bg-green-100 text-green-800 border-green-200',
    APPROVAL_REQUIRED: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    APPROVED: 'bg-blue-100 text-blue-800 border-blue-200',
    REJECTED: 'bg-red-100 text-red-800 border-red-200',
    BLOCKED: 'bg-red-100 text-red-800 border-red-200',
    EXECUTED: 'bg-green-100 text-green-800 border-green-200'
};

const DECISION_ICONS = {
    AUTO: CheckCircle,
    APPROVAL_REQUIRED: AlertTriangle,
    APPROVED: CheckCircle,
    REJECTED: XCircle,
    BLOCKED: Shield,
    EXECUTED: Activity
};

interface AuditTimelineProps {
    userId?: string;
    actionType?: string;
    onRollbackRequested?: (actionId: string) => void;
}

export function AuditTimeline({
    userId,
    actionType,
    onRollbackRequested
}: AuditTimelineProps) {
    const [entries, setEntries] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);

    // Filters
    const [searchUser, setSearchUser] = useState(userId || '');
    const [filterActionType, setFilterActionType] = useState(actionType || '');
    const [filterDecision, setFilterDecision] = useState('');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [limit] = useState(100);

    // Pagination
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 20;

    useEffect(() => {
        loadAuditEntries();
    }, [searchUser, filterActionType, filterDecision, startDate, endDate, limit]);

    const loadAuditEntries = async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams();

            if (searchUser) params.append('user_id', searchUser);
            if (filterActionType) params.append('action_type', filterActionType);
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            params.append('limit', limit.toString());

            const response = await fetch(`/api/governance/audit?${params}`, {
                headers: {
                    'X-Org-Id': 'default',
                    'X-User-Id': 'current-user' // TODO: Get from auth
                }
            });

            if (response.ok) {
                const data = await response.json();
                setEntries(data.audit_entries || []);
                setCurrentPage(1);
            } else {
                throw new Error('Failed to load audit entries');
            }
        } catch (error) {
            console.error('Error loading audit entries:', error);
            toast({
                title: 'Error',
                description: 'Failed to load audit trail.',
                variant: 'destructive'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleRollback = async (actionId: string) => {
        if (onRollbackRequested) {
            onRollbackRequested(actionId);
        } else {
            // Default rollback handling
            try {
                const response = await fetch(`/api/governance/rollback/${actionId}/check`);

                if (response.ok) {
                    const data = await response.json();

                    if (data.can_rollback) {
                        if (window.confirm('Are you sure you want to rollback this action?')) {
                            const rollbackResponse = await fetch(`/api/governance/rollback/${actionId}`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-User-Id': 'current-user'
                                },
                                body: JSON.stringify({ reason: 'Manual rollback from audit timeline' })
                            });

                            if (rollbackResponse.ok) {
                                toast({
                                    title: 'Success',
                                    description: 'Action rolled back successfully.',
                                });
                                loadAuditEntries(); // Refresh to show rollback entry
                            } else {
                                throw new Error('Rollback failed');
                            }
                        }
                    } else {
                        toast({
                            title: 'Cannot Rollback',
                            description: data.reason,
                            variant: 'destructive'
                        });
                    }
                }
            } catch (error) {
                console.error('Rollback error:', error);
                toast({
                    title: 'Error',
                    description: 'Failed to rollback action.',
                    variant: 'destructive'
                });
            }
        }
    };

    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now.getTime() - date.getTime();

        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    };

    const clearFilters = () => {
        setSearchUser('');
        setFilterActionType('');
        setFilterDecision('');
        setStartDate('');
        setEndDate('');
    };

    // Pagination
    const totalPages = Math.ceil(entries.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const paginatedEntries = entries.slice(startIndex, startIndex + itemsPerPage);

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <History className="h-5 w-5" />
                        Audit Timeline
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-4">
                        {[...Array(5)].map((_, i) => (
                            <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
                                <div className="w-10 h-10 bg-gray-200 rounded-full"></div>
                                <div className="flex-1 space-y-2">
                                    <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                                    <div className="h-3 bg-gray-200 rounded w-2/3"></div>
                                </div>
                                <div className="w-20 h-6 bg-gray-200 rounded"></div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <History className="h-5 w-5" />
                            Audit Timeline
                            {entries.length > 0 && (
                                <Badge variant="secondary">{entries.length} entries</Badge>
                            )}
                        </div>
                        <Button variant="outline" size="sm" onClick={loadAuditEntries}>
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Refresh
                        </Button>
                    </CardTitle>
                    <CardDescription>
                        Complete audit trail of all governance decisions and actions.
                    </CardDescription>
                </CardHeader>

                <CardContent>
                    {/* Filters */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        <div className="space-y-2">
                            <Label htmlFor="user-search">User</Label>
                            <div className="relative">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-500" />
                                <Input
                                    id="user-search"
                                    placeholder="Search by user..."
                                    value={searchUser}
                                    onChange={(e) => setSearchUser(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>Action Type</Label>
                            <Select value={filterActionType} onValueChange={setFilterActionType}>
                                <SelectTrigger>
                                    <SelectValue placeholder="All actions" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="">All actions</SelectItem>
                                    <SelectItem value="code_edit">Code Edit</SelectItem>
                                    <SelectItem value="config_change">Config Change</SelectItem>
                                    <SelectItem value="deploy_prod">Deploy Prod</SelectItem>
                                    <SelectItem value="schema_change">Schema Change</SelectItem>
                                    <SelectItem value="approval_decision">Approval Decision</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label>Decision</Label>
                            <Select value={filterDecision} onValueChange={setFilterDecision}>
                                <SelectTrigger>
                                    <SelectValue placeholder="All decisions" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="">All decisions</SelectItem>
                                    <SelectItem value="AUTO">Auto</SelectItem>
                                    <SelectItem value="APPROVAL_REQUIRED">Approval Required</SelectItem>
                                    <SelectItem value="APPROVED">Approved</SelectItem>
                                    <SelectItem value="REJECTED">Rejected</SelectItem>
                                    <SelectItem value="BLOCKED">Blocked</SelectItem>
                                    <SelectItem value="EXECUTED">Executed</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex items-end gap-2">
                            <Button variant="outline" size="sm" onClick={clearFilters}>
                                <Filter className="h-4 w-4 mr-2" />
                                Clear Filters
                            </Button>
                        </div>
                    </div>

                    {/* Date Range Filter */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <div className="space-y-2">
                            <Label htmlFor="start-date">Start Date</Label>
                            <Input
                                id="start-date"
                                type="datetime-local"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="end-date">End Date</Label>
                            <Input
                                id="end-date"
                                type="datetime-local"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                            />
                        </div>
                    </div>

                    {/* Timeline */}
                    {entries.length === 0 ? (
                        <div className="text-center py-8 text-gray-500">
                            <History className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                            <p className="text-lg font-medium">No audit entries found</p>
                            <p className="text-sm">Try adjusting your filters or check back later.</p>
                        </div>
                    ) : (
                        <>
                            <div className="space-y-4">
                                {paginatedEntries.map((entry) => {
                                    const DecisionIcon = DECISION_ICONS[entry.decision as keyof typeof DECISION_ICONS] || Activity;
                                    const decisionColor = DECISION_COLORS[entry.decision as keyof typeof DECISION_COLORS] || 'bg-gray-100 text-gray-800';

                                    return (
                                        <div key={entry.id} className="flex items-start gap-4 p-4 border rounded-lg hover:bg-gray-50">
                                            {/* Icon */}
                                            <div className="flex-shrink-0">
                                                <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                                                    <DecisionIcon className="h-5 w-5" />
                                                </div>
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-start justify-between mb-2">
                                                    <div>
                                                        <h3 className="font-medium">{entry.action_type.replace('_', ' ')}</h3>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <div className="flex items-center gap-1 text-sm text-gray-600">
                                                                <User className="h-3 w-3" />
                                                                {entry.user_id}
                                                            </div>
                                                            <div className="flex items-center gap-1 text-sm text-gray-600">
                                                                <Clock className="h-3 w-3" />
                                                                {formatTimestamp(entry.timestamp)}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div className="flex items-center gap-2">
                                                        <Badge className={`${decisionColor} border`}>
                                                            {entry.decision}
                                                        </Badge>
                                                        {entry.risk_score > 0 && (
                                                            <Badge
                                                                variant={entry.risk_score > 0.7 ? 'destructive' :
                                                                    entry.risk_score > 0.3 ? 'default' : 'secondary'}
                                                            >
                                                                {(entry.risk_score * 100).toFixed(0)}% risk
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Execution Result */}
                                                {entry.execution_result && (
                                                    <p className="text-sm text-gray-600 mb-2">
                                                        Result: {entry.execution_result}
                                                    </p>
                                                )}

                                                {/* Actions */}
                                                <div className="flex items-center gap-2">
                                                    <Dialog>
                                                        <DialogTrigger asChild>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => setSelectedEntry(entry)}
                                                            >
                                                                <Eye className="h-3 w-3 mr-1" />
                                                                Details
                                                            </Button>
                                                        </DialogTrigger>
                                                    </Dialog>

                                                    {entry.rollback_available && entry.decision === 'EXECUTED' && (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => handleRollback(entry.id)}
                                                            className="text-orange-600 hover:text-orange-700"
                                                        >
                                                            <RotateCcw className="h-3 w-3 mr-1" />
                                                            Rollback
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Pagination */}
                            {totalPages > 1 && (
                                <div className="flex items-center justify-between mt-6">
                                    <p className="text-sm text-gray-600">
                                        Showing {startIndex + 1}-{Math.min(startIndex + itemsPerPage, entries.length)} of {entries.length} entries
                                    </p>

                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                            disabled={currentPage === 1}
                                        >
                                            <ArrowLeft className="h-4 w-4" />
                                        </Button>

                                        <span className="text-sm">
                                            {currentPage} of {totalPages}
                                        </span>

                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                                            disabled={currentPage === totalPages}
                                        >
                                            <ArrowRight className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </CardContent>
            </Card>

            {/* Entry Details Dialog */}
            {selectedEntry && (
                <Dialog open={!!selectedEntry} onOpenChange={() => setSelectedEntry(null)}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Audit Entry Details</DialogTitle>
                            <DialogDescription>
                                Complete information about this audit entry.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-4">
                            {/* Basic Info */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <Label className="font-medium">Entry ID</Label>
                                    <p className="text-sm font-mono">{selectedEntry.id}</p>
                                </div>
                                <div>
                                    <Label className="font-medium">Timestamp</Label>
                                    <p className="text-sm">{new Date(selectedEntry.timestamp).toLocaleString()}</p>
                                </div>
                                <div>
                                    <Label className="font-medium">User</Label>
                                    <p className="text-sm">{selectedEntry.user_id}</p>
                                </div>
                                <div>
                                    <Label className="font-medium">Action Type</Label>
                                    <p className="text-sm">{selectedEntry.action_type}</p>
                                </div>
                                <div>
                                    <Label className="font-medium">Decision</Label>
                                    <Badge className={`${DECISION_COLORS[selectedEntry.decision as keyof typeof DECISION_COLORS]} border`}>
                                        {selectedEntry.decision}
                                    </Badge>
                                </div>
                                <div>
                                    <Label className="font-medium">Risk Score</Label>
                                    <p className="text-sm">{(selectedEntry.risk_score * 100).toFixed(1)}%</p>
                                </div>
                            </div>

                            {/* Execution Result */}
                            {selectedEntry.execution_result && (
                                <div>
                                    <Label className="font-medium">Execution Result</Label>
                                    <p className="text-sm mt-1 p-3 bg-gray-50 rounded border">
                                        {selectedEntry.execution_result}
                                    </p>
                                </div>
                            )}

                            {/* Artifacts */}
                            {Object.keys(selectedEntry.artifacts).length > 0 && (
                                <div>
                                    <Label className="font-medium">Additional Context</Label>
                                    <pre className="text-xs mt-1 p-3 bg-gray-50 rounded border overflow-auto max-h-40">
                                        {JSON.stringify(selectedEntry.artifacts, null, 2)}
                                    </pre>
                                </div>
                            )}

                            {/* Rollback Option */}
                            {selectedEntry.rollback_available && selectedEntry.decision === 'EXECUTED' && (
                                <div className="pt-4 border-t">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <Label className="font-medium text-orange-600">Rollback Available</Label>
                                            <p className="text-sm text-gray-600">This action can be rolled back if needed.</p>
                                        </div>
                                        <Button
                                            variant="outline"
                                            onClick={() => {
                                                handleRollback(selectedEntry.id);
                                                setSelectedEntry(null);
                                            }}
                                            className="text-orange-600 hover:text-orange-700"
                                        >
                                            <RotateCcw className="h-4 w-4 mr-2" />
                                            Rollback Action
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </DialogContent>
                </Dialog>
            )}
        </div>
    );
}