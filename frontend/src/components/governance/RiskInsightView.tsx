/**
 * Risk Insight View
 * 
 * Dashboard showing risk metrics, patterns, and high-risk areas.
 * Provides engineering leadership visibility into autonomous operations.
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
// import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';
import {
    TrendingUp,
    AlertTriangle,
    Shield,
    Activity,
    Users,
    Clock,
    CheckCircle,
    BarChart3
} from 'lucide-react';
import { toast } from '@/components/ui/use-toast';

interface RiskInsights {
    high_risk_actions: Array<{
        action_type: string;
        count: number;
        avg_risk: number;
    }>;
    approval_stats: Array<{
        decision: string;
        count: number;
    }>;
    user_activity: Array<{
        user_id: string;
        actions: number;
        avg_risk: number;
    }>;
    period_days: number;
}

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

interface RiskInsightViewProps {
    period?: number;
}

export function RiskInsightView({ period = 30 }: RiskInsightViewProps) {
    const [insights, setInsights] = useState<RiskInsights | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedPeriod, setSelectedPeriod] = useState(period);

    useEffect(() => {
        loadInsights();
    }, [selectedPeriod]);

    const loadInsights = async () => {
        try {
            setLoading(true);
            const response = await fetch(`/api/governance/insights?days=${selectedPeriod}`, {
                headers: {
                    'X-Org-Id': 'default',
                    'X-User-Id': 'current-user' // TODO: Get from auth
                }
            });

            if (response.ok) {
                const data = await response.json();
                setInsights(data);
            } else {
                throw new Error('Failed to load insights');
            }
        } catch (error) {
            console.error('Error loading insights:', error);
            toast({
                title: 'Error',
                description: 'Failed to load risk insights.',
                variant: 'destructive'
            });
        } finally {
            setLoading(false);
        }
    };

    const getApprovalRate = () => {
        if (!insights?.approval_stats.length) return 0;

        const approved = insights.approval_stats.find(s => s.decision === 'APPROVED')?.count || 0;
        const total = insights.approval_stats.reduce((sum, s) => sum + s.count, 0);

        return total > 0 ? Math.round((approved / total) * 100) : 0;
    };

    const getTotalActions = () => {
        return insights?.user_activity.reduce((sum, u) => sum + u.actions, 0) || 0;
    };

    const getAverageRisk = () => {
        if (!insights?.high_risk_actions.length) return 0;

        const totalRisk = insights.high_risk_actions.reduce((sum, a) => sum + a.avg_risk, 0);
        return totalRisk / insights.high_risk_actions.length;
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <BarChart3 className="h-5 w-5" />
                            Risk Insights
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="animate-pulse space-y-4">
                            <div className="grid grid-cols-4 gap-4">
                                {[...Array(4)].map((_, i) => (
                                    <div key={i} className="h-20 bg-gray-200 rounded"></div>
                                ))}
                            </div>
                            <div className="h-64 bg-gray-200 rounded"></div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (!insights) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-red-600">
                        <AlertTriangle className="h-5 w-5" />
                        No Data Available
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-gray-600">Unable to load risk insights at this time.</p>
                </CardContent>
            </Card>
        );
    }

    const approvalRate = getApprovalRate();
    const totalActions = getTotalActions();
    const avgRisk = getAverageRisk();

    return (
        <div className="space-y-6">
            {/* Header */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5" />
                        Risk Insights Dashboard
                    </CardTitle>
                    <CardDescription>
                        Engineering leadership visibility into NAVI's autonomous operations over the last {selectedPeriod} days.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {/* Period Selector */}
                    <div className="flex gap-2 mb-6">
                        {[7, 14, 30, 90].map((days) => (
                            <button
                                key={days}
                                onClick={() => setSelectedPeriod(days)}
                                className={`px-3 py-1 rounded-full text-sm font-medium ${selectedPeriod === days
                                    ? 'bg-blue-100 text-blue-700'
                                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                    }`}
                            >
                                {days}d
                            </button>
                        ))}
                    </div>

                    {/* Key Metrics */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-blue-50 p-4 rounded-lg border">
                            <div className="flex items-center gap-2">
                                <Activity className="h-5 w-5 text-blue-600" />
                                <div>
                                    <p className="text-2xl font-bold text-blue-600">{totalActions}</p>
                                    <p className="text-sm text-blue-600">Total Actions</p>
                                </div>
                            </div>
                        </div>

                        <div className="bg-green-50 p-4 rounded-lg border">
                            <div className="flex items-center gap-2">
                                <CheckCircle className="h-5 w-5 text-green-600" />
                                <div>
                                    <p className="text-2xl font-bold text-green-600">{approvalRate}%</p>
                                    <p className="text-sm text-green-600">Approval Rate</p>
                                </div>
                            </div>
                        </div>

                        <div className="bg-yellow-50 p-4 rounded-lg border">
                            <div className="flex items-center gap-2">
                                <Shield className="h-5 w-5 text-yellow-600" />
                                <div>
                                    <p className="text-2xl font-bold text-yellow-600">{(avgRisk * 100).toFixed(0)}%</p>
                                    <p className="text-sm text-yellow-600">Avg Risk Score</p>
                                </div>
                            </div>
                        </div>

                        <div className="bg-purple-50 p-4 rounded-lg border">
                            <div className="flex items-center gap-2">
                                <Users className="h-5 w-5 text-purple-600" />
                                <div>
                                    <p className="text-2xl font-bold text-purple-600">{insights.user_activity.length}</p>
                                    <p className="text-sm text-purple-600">Active Users</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Charts */}
            <Tabs defaultValue="high-risk" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="high-risk">High-Risk Actions</TabsTrigger>
                    <TabsTrigger value="approvals">Approval Patterns</TabsTrigger>
                    <TabsTrigger value="users">User Activity</TabsTrigger>
                </TabsList>

                <TabsContent value="high-risk" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <AlertTriangle className="h-5 w-5 text-red-500" />
                                High-Risk Areas
                            </CardTitle>
                            <CardDescription>
                                Action types with highest risk scores and frequency over the selected period.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {insights.high_risk_actions.length > 0 ? (
                                <>
                                    <ResponsiveContainer width="100%" height={300}>
                                        <BarChart data={insights.high_risk_actions}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis
                                                dataKey="action_type"
                                                tick={{ fontSize: 12 }}
                                                angle={-45}
                                                textAnchor="end"
                                                height={80}
                                            />
                                            <YAxis />
                                            <Tooltip
                                                formatter={(value: any, name: any) => [
                                                    name === 'count' ? `${value} actions` : `${(value * 100).toFixed(1)}% risk`,
                                                    name === 'count' ? 'Frequency' : 'Avg Risk'
                                                ]}
                                            />
                                            <Bar dataKey="count" fill="#3b82f6" name="count" />
                                            <Bar dataKey="avg_risk" fill="#ef4444" name="avg_risk" />
                                        </BarChart>
                                    </ResponsiveContainer>

                                    <div className="mt-4 space-y-2">
                                        <h4 className="font-medium">Top Risk Areas:</h4>
                                        {insights.high_risk_actions.slice(0, 5).map((action, index) => (
                                            <div key={action.action_type} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline">{index + 1}</Badge>
                                                    <span className="font-medium">{action.action_type}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-gray-600">{action.count} actions</span>
                                                    <Badge
                                                        className={action.avg_risk > 0.7 ? 'bg-red-100 text-red-700' :
                                                            action.avg_risk > 0.3 ? 'bg-yellow-100 text-yellow-700' :
                                                                'bg-green-100 text-green-700'}
                                                    >
                                                        {(action.avg_risk * 100).toFixed(0)}% risk
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            ) : (
                                <div className="text-center py-8 text-gray-500">
                                    <Shield className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                                    <p>No high-risk actions in the selected period</p>
                                    <p className="text-sm">This is good news! NAVI is operating safely.</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="approvals" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <CheckCircle className="h-5 w-5 text-green-500" />
                                Approval Patterns
                            </CardTitle>
                            <CardDescription>
                                How approval requests are being resolved by your team.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {insights.approval_stats.length > 0 ? (
                                <div className="grid md:grid-cols-2 gap-6">
                                    <ResponsiveContainer width="100%" height={250}>
                                        <PieChart>
                                            <Pie
                                                data={insights.approval_stats}
                                                cx="50%"
                                                cy="50%"
                                                outerRadius={80}
                                                fill="#8884d8"
                                                dataKey="count"
                                                nameKey="decision"
                                                label={({ decision, percent }: any) => `${decision} ${(percent * 100).toFixed(0)}%`}
                                            >
                                                {insights.approval_stats.map((_entry, index) => (
                                                    <Cell
                                                        key={`cell-${index}`}
                                                        fill={CHART_COLORS[index % CHART_COLORS.length]}
                                                    />
                                                ))}
                                            </Pie>
                                            <Tooltip formatter={(value: any) => [`${value} requests`, 'Count']} />
                                        </PieChart>
                                    </ResponsiveContainer>

                                    <div className="space-y-3">
                                        <h4 className="font-medium">Approval Breakdown:</h4>
                                        {insights.approval_stats.map((stat, index) => (
                                            <div key={stat.decision} className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <div
                                                        className="w-3 h-3 rounded-full"
                                                        style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                                                    />
                                                    <span>{stat.decision}</span>
                                                </div>
                                                <Badge variant="outline">{stat.count} requests</Badge>
                                            </div>
                                        ))}

                                        <div className="mt-4 p-3 bg-blue-50 rounded border">
                                            <div className="flex items-center gap-2">
                                                <TrendingUp className="h-4 w-4 text-blue-600" />
                                                <span className="font-medium text-blue-600">
                                                    {approvalRate}% approval rate
                                                </span>
                                            </div>
                                            <p className="text-sm text-blue-600 mt-1">
                                                {approvalRate > 80 ? 'Excellent approval rate - team is confident in NAVI' :
                                                    approvalRate > 60 ? 'Good approval rate - moderate trust in automation' :
                                                        'Low approval rate - consider reviewing autonomy policies'}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8 text-gray-500">
                                    <Clock className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                                    <p>No approval activity in the selected period</p>
                                    <p className="text-sm">Either no requests required approval, or no activity occurred.</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="users" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Users className="h-5 w-5 text-purple-500" />
                                User Activity
                            </CardTitle>
                            <CardDescription>
                                Individual user activity and risk patterns.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {insights.user_activity.length > 0 ? (
                                <>
                                    <ResponsiveContainer width="100%" height={300}>
                                        <BarChart data={insights.user_activity.slice(0, 10)}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis
                                                dataKey="user_id"
                                                tick={{ fontSize: 12 }}
                                                angle={-45}
                                                textAnchor="end"
                                                height={80}
                                            />
                                            <YAxis />
                                            <Tooltip
                                                formatter={(value: any, name: any) => [
                                                    name === 'actions' ? `${value} actions` : `${(value * 100).toFixed(1)}% avg risk`,
                                                    name === 'actions' ? 'Total Actions' : 'Average Risk'
                                                ]}
                                            />
                                            <Bar dataKey="actions" fill="#8b5cf6" name="actions" />
                                            <Bar dataKey="avg_risk" fill="#f59e0b" name="avg_risk" />
                                        </BarChart>
                                    </ResponsiveContainer>

                                    <div className="mt-4 space-y-2">
                                        <h4 className="font-medium">Most Active Users:</h4>
                                        {insights.user_activity
                                            .sort((a, b) => b.actions - a.actions)
                                            .slice(0, 8)
                                            .map((user, index) => (
                                                <div key={user.user_id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                                                    <div className="flex items-center gap-2">
                                                        <Badge variant="outline">{index + 1}</Badge>
                                                        <span className="font-medium">{user.user_id}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-sm text-gray-600">{user.actions} actions</span>
                                                        <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full transition-all"
                                                                style={{
                                                                    width: `${user.avg_risk * 100}%`,
                                                                    backgroundColor: user.avg_risk > 0.7 ? '#ef4444' :
                                                                        user.avg_risk > 0.3 ? '#f59e0b' : '#22c55e'
                                                                }}
                                                            />
                                                        </div>
                                                        <span className="text-xs text-gray-500">
                                                            {(user.avg_risk * 100).toFixed(0)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            ))}
                                    </div>
                                </>
                            ) : (
                                <div className="text-center py-8 text-gray-500">
                                    <Users className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                                    <p>No user activity in the selected period</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}