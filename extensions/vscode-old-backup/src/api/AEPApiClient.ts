import axios, { AxiosInstance } from 'axios';
import * as vscode from 'vscode';
import { AuthManager } from '../auth/AuthManager';

/**
 * AEP API Client for VS Code Extension
 * 
 * Provides typed interfaces for all AEP backend endpoints with
 * automatic authentication and error handling.
 */

export interface JiraTask {
    key: string;
    summary: string;
    description: string;
    status: string;
    priority: string;
    assignee: string;
    reporter: string;
    created: string;
    updated: string;
    dueDate?: string;
    storyPoints?: number;
    labels: string[];
    components: string[];
    url: string;
}

export interface MorningBriefData {
    greeting: string;
    jiraTasks: JiraTask[];
    recentActivity: ActivityItem[];
    upcomingMeetings: Meeting[];
    relevantDocs: Document[];
    teamStatus: TeamMember[];
    suggestions: Suggestion[];
}

export interface ActivityItem {
    id: string;
    type: 'commit' | 'pr' | 'comment' | 'meeting' | 'slack';
    title: string;
    description: string;
    author: string;
    timestamp: string;
    url?: string;
}

export interface Meeting {
    id: string;
    title: string;
    startTime: string;
    endTime: string;
    attendees: string[];
    agenda?: string;
    url?: string;
}

export interface Document {
    id: string;
    title: string;
    type: 'confluence' | 'notion' | 'wiki';
    summary: string;
    lastUpdated: string;
    url: string;
    relevanceScore: number;
}

export interface TeamMember {
    id: string;
    name: string;
    email: string;
    status: 'available' | 'busy' | 'away' | 'offline';
    currentTask?: string;
    location?: string;
}

export interface Suggestion {
    id: string;
    type: 'task' | 'optimization' | 'learning' | 'collaboration';
    title: string;
    description: string;
    action: string;
    priority: 'low' | 'medium' | 'high';
}

export interface PlanStep {
    id: string;
    type: 'create_file' | 'modify_file' | 'delete_file' | 'run_command' | 'git_commit';
    description: string;
    details: any;
    status: 'pending' | 'approved' | 'rejected' | 'completed' | 'error';
    dependencies: string[];
}

export interface ExecutionPlan {
    id: string;
    title: string;
    description: string;
    jiraTaskKey?: string;
    steps: PlanStep[];
    status: 'draft' | 'pending_approval' | 'approved' | 'executing' | 'completed' | 'failed';
    createdAt: string;
    estimatedDuration: number;
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    context?: {
        jiraTask?: string;
        files?: string[];
        citations?: string[];
    };
}

export interface MemorySearchResult {
    id: string;
    source: 'jira' | 'confluence' | 'slack' | 'teams' | 'zoom' | 'code';
    title: string;
    content: string;
    url: string;
    relevanceScore: number;
    lastUpdated: string;
}

export class AEPApiClient {
    private axios: AxiosInstance;
    private authManager: AuthManager;

    constructor(authManager: AuthManager) {
        this.authManager = authManager;
        
        const config = vscode.workspace.getConfiguration('aep');
        const baseURL = config.get<string>('coreApi') || 'http://localhost:8002';

        this.axios = axios.create({
            baseURL,
            timeout: 30000, // 30 second timeout
        });

        // Add auth interceptor
        this.axios.interceptors.request.use(async (config) => {
            const token = this.authManager.getAccessToken();
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
            return config;
        });

        // Add error interceptor
        this.axios.interceptors.response.use(
            (response) => response,
            async (error) => {
                if (error.response?.status === 401) {
                    // Token expired, try to refresh
                    const refreshed = await this.authManager.isAuthenticated();
                    if (!refreshed) {
                        vscode.window.showErrorMessage('Authentication expired. Please sign in again.');
                        vscode.commands.executeCommand('aep.authenticate');
                    }
                }
                return Promise.reject(error);
            }
        );
    }

    /**
     * Get morning brief with task context and suggestions
     */
    async getMorningBrief(): Promise<MorningBriefData> {
        const response = await this.axios.get('/api/morning-brief');
        return response.data;
    }

    /**
     * Get user's assigned Jira tasks
     */
    async getJiraTasks(): Promise<JiraTask[]> {
        const response = await this.axios.get('/api/jira/tasks/assigned');
        return response.data.tasks || [];
    }

    /**
     * Get detailed context for a specific Jira task
     */
    async getJiraTaskContext(taskKey: string): Promise<{
        task: JiraTask;
        relatedPRs: any[];
        relatedDocs: Document[];
        recentActivity: ActivityItem[];
        teamDiscussion: any[];
    }> {
        const response = await this.axios.get(`/api/jira/tasks/${taskKey}/context`);
        return response.data;
    }

    /**
     * Search across all enterprise memory sources
     */
    async searchMemory(query: string, sources?: string[]): Promise<MemorySearchResult[]> {
        const response = await this.axios.post('/api/memory/search', {
            query,
            sources,
            limit: 20
        });
        return response.data.results || [];
    }

    /**
     * Create an execution plan for a task
     */
    async createPlan(request: {
        description: string;
        jiraTaskKey?: string;
        context?: any;
        files?: string[];
    }): Promise<ExecutionPlan> {
        const response = await this.axios.post('/api/plan/create', request);
        return response.data;
    }

    /**
     * Execute a specific step in a plan
     */
    async executeStep(planId: string, stepId: string): Promise<{
        success: boolean;
        result?: any;
        error?: string;
    }> {
        const response = await this.axios.post(`/api/plan/${planId}/step/${stepId}/execute`);
        return response.data;
    }

    /**
     * Get current plan status
     */
    async getPlan(planId: string): Promise<ExecutionPlan> {
        const response = await this.axios.get(`/api/plan/${planId}`);
        return response.data;
    }

    /**
     * Send chat message and get AI response
     */
    async sendChatMessage(message: string, context?: {
        jiraTask?: string;
        files?: string[];
        planId?: string;
    }): Promise<ChatMessage> {
        const response = await this.axios.post('/api/chat/message', {
            message,
            context
        });
        return response.data;
    }

    /**
     * Get chat conversation history
     */
    async getChatHistory(limit: number = 50): Promise<ChatMessage[]> {
        const response = await this.axios.get(`/api/chat/history?limit=${limit}`);
        return response.data.messages || [];
    }

    /**
     * Get team activity feed
     */
    async getTeamActivity(limit: number = 20): Promise<ActivityItem[]> {
        const response = await this.axios.get(`/api/activity/recent?limit=${limit}`);
        return response.data.activities || [];
    }

    /**
     * Get team member status
     */
    async getTeamStatus(): Promise<TeamMember[]> {
        const response = await this.axios.get('/api/team/status');
        return response.data.members || [];
    }

    /**
     * Get workspace context for current VS Code workspace
     */
    async getWorkspaceContext(): Promise<{
        files: Array<{
            path: string;
            type: string;
            lastModified: string;
            size: number;
        }>;
        gitStatus: {
            branch: string;
            uncommittedChanges: number;
            ahead: number;
            behind: number;
        };
        dependencies: {
            [key: string]: string;
        };
    }> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        const workspacePath = workspaceFolders?.[0]?.uri.fsPath;

        const response = await this.axios.post('/api/workspace/context', {
            workspacePath
        });
        return response.data;
    }

    /**
     * Health check
     */
    async healthCheck(): Promise<boolean> {
        try {
            await this.axios.get('/health');
            return true;
        } catch {
            return false;
        }
    }
}