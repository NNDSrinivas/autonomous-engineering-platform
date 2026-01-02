/**
 * Autonomy Settings Panel
 * 
 * Allows users to configure their autonomy level and action permissions.
 * Provides sliders and toggles for granular control over NAVI's behavior.
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
    Shield,
    ShieldCheck,
    ShieldAlert,
    ShieldX,
    Settings,
    Save,
    RotateCcw,
    AlertTriangle,
    CheckCircle
} from 'lucide-react';
import { toast } from '@/components/ui/use-toast';

export interface AutonomyPolicy {
    user_id: string;
    org_id: string;
    repo?: string;
    autonomy_level: 'minimal' | 'standard' | 'elevated' | 'full';
    max_auto_risk: number;
    blocked_actions: string[];
    auto_allowed_actions: string[];
    require_approval_for: string[];
    created_at?: string;
    updated_at?: string;
}

const AUTONOMY_LEVELS = {
    minimal: {
        label: 'Minimal',
        icon: ShieldX,
        color: 'text-red-500',
        description: 'Most actions require approval. Maximum safety.',
        maxRisk: 0.1
    },
    standard: {
        label: 'Standard',
        icon: Shield,
        color: 'text-blue-500',
        description: 'Balanced autonomy with moderate risk tolerance.',
        maxRisk: 0.3
    },
    elevated: {
        label: 'Elevated',
        icon: ShieldCheck,
        color: 'text-green-500',
        description: 'High autonomy for experienced developers.',
        maxRisk: 0.6
    },
    full: {
        label: 'Full',
        icon: ShieldAlert,
        color: 'text-orange-500',
        description: 'Maximum autonomy. For platform teams only.',
        maxRisk: 0.8
    }
};

const ACTION_CATEGORIES = {
    'Safe Operations': [
        'lint_fix',
        'test_fix',
        'doc_update',
        'format_code'
    ],
    'Code Changes': [
        'code_edit',
        'refactor',
        'feature_flag',
        'dependency_update'
    ],
    'Configuration': [
        'config_change',
        'env_update',
        'ci_config'
    ],
    'Infrastructure': [
        'schema_change',
        'deploy_staging',
        'deploy_prod',
        'infrastructure_change'
    ],
    'Security': [
        'auth_config',
        'security_policy',
        'user_permissions'
    ]
};

interface AutonomySettingsPanelProps {
    userId?: string;
    repo?: string;
    onPolicyUpdated?: (policy: AutonomyPolicy) => void;
}

export function AutonomySettingsPanel({
    userId,
    repo,
    onPolicyUpdated
}: AutonomySettingsPanelProps) {
    const [policy, setPolicy] = useState<AutonomyPolicy | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);

    // Load current policy
    useEffect(() => {
        loadPolicy();
    }, [userId, repo]);

    const loadPolicy = async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams();
            if (userId) params.append('user_id', userId);
            if (repo) params.append('repo', repo);

            const response = await fetch(`/api/governance/policy?${params}`, {
                headers: {
                    'X-Org-Id': 'default', // TODO: Get from context
                    'X-User-Id': userId || 'current-user' // TODO: Get from auth
                }
            });

            if (response.ok) {
                const data = await response.json();
                setPolicy(data);
            } else if (response.status === 404) {
                // No policy found, use defaults
                setPolicy({
                    user_id: userId || 'current-user',
                    org_id: 'default',
                    repo,
                    autonomy_level: 'standard',
                    max_auto_risk: 0.3,
                    blocked_actions: ['deploy_prod', 'schema_change'],
                    auto_allowed_actions: ['lint_fix', 'test_fix', 'doc_update'],
                    require_approval_for: ['config_change', 'infrastructure_change']
                });
            }
        } catch (error) {
            console.error('Error loading policy:', error);
            toast({
                title: 'Error',
                description: 'Failed to load autonomy policy.',
                variant: 'destructive'
            });
        } finally {
            setLoading(false);
        }
    };

    const savePolicy = async () => {
        if (!policy) return;

        try {
            setSaving(true);

            const response = await fetch('/api/governance/policy', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Org-Id': 'default',
                    'X-User-Id': 'admin' // TODO: Get admin user from auth
                },
                body: JSON.stringify(policy)
            });

            if (response.ok) {
                toast({
                    title: 'Success',
                    description: 'Autonomy policy updated successfully.',
                });
                setHasChanges(false);
                onPolicyUpdated?.(policy);
            } else {
                throw new Error('Failed to save policy');
            }
        } catch (error) {
            console.error('Error saving policy:', error);
            toast({
                title: 'Error',
                description: 'Failed to save autonomy policy.',
                variant: 'destructive'
            });
        } finally {
            setSaving(false);
        }
    };

    const updatePolicy = (updates: Partial<AutonomyPolicy>) => {
        if (!policy) return;

        const newPolicy = { ...policy, ...updates };
        setPolicy(newPolicy);
        setHasChanges(true);
    };

    const updateAutonomyLevel = (level: keyof typeof AUTONOMY_LEVELS) => {
        const levelConfig = AUTONOMY_LEVELS[level];
        updatePolicy({
            autonomy_level: level,
            max_auto_risk: levelConfig.maxRisk
        });
    };

    const toggleAction = (action: string, category: 'blocked' | 'allowed' | 'approval') => {
        if (!policy) return;

        const currentBlocked = new Set(policy.blocked_actions);
        const currentAllowed = new Set(policy.auto_allowed_actions);
        const currentApproval = new Set(policy.require_approval_for);

        // Remove from all lists first
        currentBlocked.delete(action);
        currentAllowed.delete(action);
        currentApproval.delete(action);

        // Add to appropriate list
        if (category === 'blocked') {
            currentBlocked.add(action);
        } else if (category === 'allowed') {
            currentAllowed.add(action);
        } else if (category === 'approval') {
            currentApproval.add(action);
        }

        updatePolicy({
            blocked_actions: Array.from(currentBlocked),
            auto_allowed_actions: Array.from(currentAllowed),
            require_approval_for: Array.from(currentApproval)
        });
    };

    const getActionStatus = (action: string): 'blocked' | 'allowed' | 'approval' | 'default' => {
        if (!policy) return 'default';

        if (policy.blocked_actions.includes(action)) return 'blocked';
        if (policy.auto_allowed_actions.includes(action)) return 'allowed';
        if (policy.require_approval_for.includes(action)) return 'approval';
        return 'default';
    };

    const resetToDefaults = () => {
        if (!policy) return;

        const defaultPolicy: AutonomyPolicy = {
            ...policy,
            autonomy_level: 'standard',
            max_auto_risk: 0.3,
            blocked_actions: ['deploy_prod', 'schema_change'],
            auto_allowed_actions: ['lint_fix', 'test_fix', 'doc_update'],
            require_approval_for: ['config_change', 'infrastructure_change']
        };

        setPolicy(defaultPolicy);
        setHasChanges(true);
    };

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5" />
                        Autonomy Settings
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-4">
                        <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div className="h-8 bg-gray-200 rounded"></div>
                        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!policy) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-red-600">
                        <AlertTriangle className="h-5 w-5" />
                        Policy Not Found
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-gray-600">
                        Unable to load autonomy policy. Please contact your administrator.
                    </p>
                </CardContent>
            </Card>
        );
    }

    const currentLevel = AUTONOMY_LEVELS[policy.autonomy_level];
    const LevelIcon = currentLevel.icon;

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5" />
                        Autonomy Settings
                        {repo && <Badge variant="outline">{repo}</Badge>}
                    </CardTitle>
                    <div className="text-sm text-muted-foreground">
                        Configure how much NAVI can do autonomously vs requiring approval.
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Autonomy Level Selector */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-3">
                            <LevelIcon className={`h-6 w-6 ${currentLevel.color}`} />
                            <div>
                                <Label className="text-base font-medium">
                                    Autonomy Level: {currentLevel.label}
                                </Label>
                                <p className="text-sm text-gray-600">{currentLevel.description}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {Object.entries(AUTONOMY_LEVELS).map(([level, config]) => {
                                const Icon = config.icon;
                                const isSelected = policy.autonomy_level === level;

                                return (
                                    <button
                                        key={level}
                                        onClick={() => updateAutonomyLevel(level as keyof typeof AUTONOMY_LEVELS)}
                                        className={`p-3 rounded-lg border-2 transition-all ${isSelected
                                            ? 'border-blue-500 bg-blue-50'
                                            : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                    >
                                        <Icon className={`h-5 w-5 mx-auto mb-2 ${isSelected ? 'text-blue-600' : config.color
                                            }`} />
                                        <div className="text-sm font-medium">{config.label}</div>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Risk Threshold Slider */}
                    <div className="space-y-3">
                        <div className="flex justify-between items-center">
                            <Label>Maximum Auto Risk: {(policy.max_auto_risk * 100).toFixed(0)}%</Label>
                            <Badge variant={policy.max_auto_risk > 0.6 ? 'destructive' :
                                policy.max_auto_risk > 0.3 ? 'primary' : 'secondary'}>
                                {policy.max_auto_risk > 0.6 ? 'High Risk' :
                                    policy.max_auto_risk > 0.3 ? 'Medium Risk' : 'Low Risk'}
                            </Badge>
                        </div>
                        <Slider
                            value={[policy.max_auto_risk]}
                            onValueChange={([value]: number[]) => updatePolicy({ max_auto_risk: value })}
                            max={1}
                            min={0}
                            step={0.1}
                            className="w-full"
                        />
                        <p className="text-sm text-gray-600">
                            Actions above this risk threshold will require approval.
                        </p>
                    </div>

                    <Separator />

                    {/* Action Configuration */}
                    <div className="space-y-4">
                        <Label className="text-base font-medium">Action Permissions</Label>

                        {Object.entries(ACTION_CATEGORIES).map(([category, actions]) => (
                            <div key={category} className="space-y-2">
                                <Label className="text-sm font-medium text-gray-700">{category}</Label>
                                <div className="grid grid-cols-1 gap-2">
                                    {actions.map((action) => {
                                        const status = getActionStatus(action);

                                        return (
                                            <div key={action} className="flex items-center justify-between p-2 border rounded">
                                                <span className="text-sm font-mono">{action}</span>
                                                <div className="flex gap-1">
                                                    <Button
                                                        size="sm"
                                                        variant={status === 'allowed' ? 'secondary' : 'outline'}
                                                        onClick={() => toggleAction(action, 'allowed')}
                                                        className="h-8 px-2"
                                                    >
                                                        <CheckCircle className="h-3 w-3" />
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant={status === 'approval' ? 'secondary' : 'outline'}
                                                        onClick={() => toggleAction(action, 'approval')}
                                                        className="h-8 px-2"
                                                    >
                                                        <AlertTriangle className="h-3 w-3" />
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant={status === 'blocked' ? 'secondary' : 'outline'}
                                                        onClick={() => toggleAction(action, 'blocked')}
                                                        className="h-8 px-2"
                                                    >
                                                        <ShieldX className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Actions */}
                    <div className="flex justify-between pt-4">
                        <Button
                            variant="outline"
                            onClick={resetToDefaults}
                            disabled={saving}
                        >
                            <RotateCcw className="h-4 w-4 mr-2" />
                            Reset to Defaults
                        </Button>

                        <Button
                            onClick={savePolicy}
                            disabled={!hasChanges || saving}
                        >
                            <Save className="h-4 w-4 mr-2" />
                            {saving ? 'Saving...' : 'Save Changes'}
                        </Button>
                    </div>

                    {hasChanges && (
                        <Alert>
                            <AlertTriangle className="h-4 w-4" />
                            <AlertDescription>
                                You have unsaved changes. Click "Save Changes" to apply your configuration.
                            </AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}