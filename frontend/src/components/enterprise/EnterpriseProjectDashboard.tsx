/**
 * EnterpriseProjectDashboard Component
 *
 * Full dashboard view for managing enterprise-level projects.
 * Shows all active projects, their progress, tasks, and pending decisions.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  PlayCircle,
  PauseCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Users,
  GitBranch,
  Layers,
  Target,
  ChevronRight,
  RefreshCw,
  Filter,
  Plus,
} from 'lucide-react';

export type ProjectStatus = 'planning' | 'active' | 'paused' | 'blocked' | 'completed' | 'failed';

export interface ProjectTask {
  id: string;
  title: string;
  status: 'pending' | 'ready' | 'in_progress' | 'completed' | 'failed';
  priority: number;
  dependencies: string[];
  assignedAgent?: string;
}

export interface ProjectMilestone {
  id: string;
  title: string;
  completedTasks: number;
  totalTasks: number;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
}

export interface PendingGate {
  id: string;
  type: string;
  title: string;
  blocksProgress: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
  createdAt: string;
}

export interface EnterpriseProject {
  id: string;
  name: string;
  description: string;
  projectType: string;
  status: ProjectStatus;
  progress: number;
  createdAt: string;
  updatedAt: string;
  stats: {
    totalTasks: number;
    completedTasks: number;
    failedTasks: number;
    pendingGates: number;
    activeAgents: number;
    iterationCount: number;
    runtimeHours: number;
  };
  currentTask?: {
    id: string;
    title: string;
    status: string;
  };
  milestones: ProjectMilestone[];
  pendingGates: PendingGate[];
  recentTasks: ProjectTask[];
}

export interface EnterpriseProjectDashboardProps {
  projects: EnterpriseProject[];
  onSelectProject: (projectId: string) => void;
  onPauseProject: (projectId: string) => void;
  onResumeProject: (projectId: string) => void;
  onCreateProject: () => void;
  onRefresh: () => void;
  onReviewGate: (projectId: string, gateId: string) => void;
  isLoading?: boolean;
}

const STATUS_CONFIG: Record<ProjectStatus, { icon: React.ReactNode; label: string; color: string }> = {
  planning: { icon: <Target className="w-4 h-4" />, label: 'Planning', color: 'bg-purple-500' },
  active: { icon: <PlayCircle className="w-4 h-4" />, label: 'Active', color: 'bg-green-500' },
  paused: { icon: <PauseCircle className="w-4 h-4" />, label: 'Paused', color: 'bg-yellow-500' },
  blocked: { icon: <AlertTriangle className="w-4 h-4" />, label: 'Blocked', color: 'bg-orange-500' },
  completed: { icon: <CheckCircle2 className="w-4 h-4" />, label: 'Completed', color: 'bg-blue-500' },
  failed: { icon: <AlertTriangle className="w-4 h-4" />, label: 'Failed', color: 'bg-red-500' },
};

const ProjectCard: React.FC<{
  project: EnterpriseProject;
  onSelect: () => void;
  onPause: () => void;
  onResume: () => void;
  onReviewGate: (gateId: string) => void;
}> = ({ project, onSelect, onPause, onResume, onReviewGate }) => {
  const statusConfig = STATUS_CONFIG[project.status];
  const blockingGates = project.pendingGates.filter(g => g.blocksProgress);

  return (
    <Card className="hover:border-primary/50 transition-colors cursor-pointer" onClick={onSelect}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className={`${statusConfig.color} text-white border-0`}>
                {statusConfig.icon}
                <span className="ml-1">{statusConfig.label}</span>
              </Badge>
              <Badge variant="secondary">{project.projectType}</Badge>
            </div>
            <CardTitle className="text-lg">{project.name}</CardTitle>
            <CardDescription className="line-clamp-2 mt-1">
              {project.description}
            </CardDescription>
          </div>
          <div className="flex gap-1">
            {project.status === 'active' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => { e.stopPropagation(); onPause(); }}
              >
                <PauseCircle className="w-4 h-4" />
              </Button>
            )}
            {(project.status === 'paused' || project.status === 'blocked') && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => { e.stopPropagation(); onResume(); }}
              >
                <PlayCircle className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Progress */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-semibold">{project.progress}%</span>
          </div>
          <Progress value={project.progress} className="h-2" />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4 mb-4 text-center">
          <div>
            <div className="text-2xl font-bold">{project.stats.completedTasks}</div>
            <div className="text-xs text-muted-foreground">Completed</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{project.stats.totalTasks - project.stats.completedTasks}</div>
            <div className="text-xs text-muted-foreground">Remaining</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{project.stats.activeAgents}</div>
            <div className="text-xs text-muted-foreground">Agents</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{project.stats.iterationCount}</div>
            <div className="text-xs text-muted-foreground">Iterations</div>
          </div>
        </div>

        {/* Current Task */}
        {project.currentTask && (
          <div className="mb-4 p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-primary" />
              <span className="text-sm font-medium">Current Task</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1 truncate">
              {project.currentTask.title}
            </p>
          </div>
        )}

        {/* Blocking Gates Alert */}
        {blockingGates.length > 0 && (
          <div className="p-3 bg-orange-500/10 border border-orange-500/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-orange-500" />
              <span className="text-sm font-medium text-orange-500">
                {blockingGates.length} Blocking Decision{blockingGates.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="space-y-1">
              {blockingGates.slice(0, 2).map(gate => (
                <Button
                  key={gate.id}
                  variant="ghost"
                  size="sm"
                  className="w-full justify-between text-left h-auto py-2"
                  onClick={(e) => { e.stopPropagation(); onReviewGate(gate.id); }}
                >
                  <span className="truncate">{gate.title}</span>
                  <ChevronRight className="w-4 h-4 flex-shrink-0" />
                </Button>
              ))}
              {blockingGates.length > 2 && (
                <p className="text-xs text-muted-foreground text-center">
                  +{blockingGates.length - 2} more
                </p>
              )}
            </div>
          </div>
        )}

        {/* View Details */}
        <div className="flex justify-end mt-4">
          <Button variant="link" size="sm" className="gap-1">
            View Details <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

const SummaryStats: React.FC<{ projects: EnterpriseProject[] }> = ({ projects }) => {
  const totalTasks = projects.reduce((sum, p) => sum + p.stats.totalTasks, 0);
  const completedTasks = projects.reduce((sum, p) => sum + p.stats.completedTasks, 0);
  const totalGates = projects.reduce((sum, p) => sum + p.stats.pendingGates, 0);
  const activeProjects = projects.filter(p => p.status === 'active').length;
  const blockedProjects = projects.filter(p => p.status === 'blocked').length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Layers className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{projects.length}</p>
              <p className="text-xs text-muted-foreground">Total Projects</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <PlayCircle className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeProjects}</p>
              <p className="text-xs text-muted-foreground">Active</p>
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
              <p className="text-2xl font-bold">{blockedProjects}</p>
              <p className="text-xs text-muted-foreground">Blocked</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <CheckCircle2 className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{completedTasks}/{totalTasks}</p>
              <p className="text-xs text-muted-foreground">Tasks Done</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg">
              <Clock className="w-5 h-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalGates}</p>
              <p className="text-xs text-muted-foreground">Pending Decisions</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export const EnterpriseProjectDashboard: React.FC<EnterpriseProjectDashboardProps> = ({
  projects,
  onSelectProject,
  onPauseProject,
  onResumeProject,
  onCreateProject,
  onRefresh,
  onReviewGate,
  isLoading = false,
}) => {
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredProjects = projects.filter(project => {
    if (statusFilter !== 'all' && project.status !== statusFilter) {
      return false;
    }
    if (searchQuery && !project.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  const activeProjects = filteredProjects.filter(p => p.status === 'active');
  const blockedProjects = filteredProjects.filter(p => p.status === 'blocked');
  const otherProjects = filteredProjects.filter(p => p.status !== 'active' && p.status !== 'blocked');

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Enterprise Projects</h1>
          <p className="text-muted-foreground">
            Manage long-running, multi-week development projects
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={onCreateProject}>
            <Plus className="w-4 h-4 mr-2" />
            New Project
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <SummaryStats projects={projects} />

      {/* Tabs */}
      <Tabs defaultValue="all" className="w-full">
        <div className="flex items-center justify-between mb-4">
          <TabsList>
            <TabsTrigger value="all">All ({filteredProjects.length})</TabsTrigger>
            <TabsTrigger value="active">
              Active ({activeProjects.length})
            </TabsTrigger>
            <TabsTrigger value="blocked">
              <AlertTriangle className="w-4 h-4 mr-1 text-orange-500" />
              Blocked ({blockedProjects.length})
            </TabsTrigger>
          </TabsList>

          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="px-3 py-1.5 text-sm border rounded-md bg-background"
            />
            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <TabsContent value="all">
          {filteredProjects.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Layers className="w-12 h-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Projects Found</h3>
                <p className="text-muted-foreground text-center mb-4">
                  Create your first enterprise project to get started.
                </p>
                <Button onClick={onCreateProject}>
                  <Plus className="w-4 h-4 mr-2" />
                  Create Project
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProjects.map(project => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onSelect={() => onSelectProject(project.id)}
                  onPause={() => onPauseProject(project.id)}
                  onResume={() => onResumeProject(project.id)}
                  onReviewGate={(gateId) => onReviewGate(project.id, gateId)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="active">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeProjects.map(project => (
              <ProjectCard
                key={project.id}
                project={project}
                onSelect={() => onSelectProject(project.id)}
                onPause={() => onPauseProject(project.id)}
                onResume={() => onResumeProject(project.id)}
                onReviewGate={(gateId) => onReviewGate(project.id, gateId)}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="blocked">
          {blockedProjects.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <CheckCircle2 className="w-12 h-12 text-green-500 mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Blocked Projects</h3>
                <p className="text-muted-foreground text-center">
                  All projects are running smoothly.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {blockedProjects.map(project => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onSelect={() => onSelectProject(project.id)}
                  onPause={() => onPauseProject(project.id)}
                  onResume={() => onResumeProject(project.id)}
                  onReviewGate={(gateId) => onReviewGate(project.id, gateId)}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default EnterpriseProjectDashboard;
