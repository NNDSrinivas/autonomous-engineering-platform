import { NaviClient } from './NaviClient';

export interface JiraTask {
    key: string;
    summary: string;
    description?: string;
    status: string;
    assignee?: string;
    priority?: string;
    issueType: string;
    projectKey: string;
    url: string;
    created: string;
    updated: string;
    reporter?: string;
    labels?: string[];
    components?: string[];
    fixVersions?: string[];
    dueDate?: string;
    estimatedHours?: number;
    timeSpent?: number;
    subtasks?: string[];
    parentTask?: string;
}

export interface JiraProject {
    key: string;
    name: string;
    description?: string;
    lead?: string;
    url: string;
    issueTypes?: string[];
}

export interface TaskSearchFilters {
    projectKey?: string;
    assignee?: string;
    status?: string;
    priority?: string;
    issueType?: string;
    labels?: string[];
    search?: string;
    updatedSince?: string;
    createdSince?: string;
}

export interface TaskContext {
    task: JiraTask;
    relatedTasks: JiraTask[];
    recentComments: Comment[];
    linkedPRs: LinkedPR[];
    relatedMeetings: Meeting[];
    codeReferences: CodeReference[];
}

export interface Comment {
    id: string;
    author: string;
    body: string;
    created: string;
    updated: string;
}

export interface LinkedPR {
    number: number;
    title: string;
    url: string;
    status: string;
    author: string;
    created: string;
}

export interface Meeting {
    id: string;
    title: string;
    date: string;
    participants: string[];
    summary?: string;
}

export interface CodeReference {
    filePath: string;
    lineNumber?: number;
    snippet?: string;
    repository?: string;
}

export interface TaskDashboard {
    assignedToMe: JiraTask[];
    recentlyUpdated: JiraTask[];
    blockedTasks: JiraTask[];
    inProgress: JiraTask[];
    readyForReview: JiraTask[];
    statistics: {
        total: number;
        completed: number;
        inProgress: number;
        blocked: number;
        avgCompletionTime: number;
    };
}

export interface CreateTaskRequest {
    projectKey: string;
    summary: string;
    description?: string;
    issueType: string;
    priority?: string;
    assignee?: string;
    labels?: string[];
    components?: string[];
    dueDate?: string;
    parentTask?: string;
}

export interface UpdateTaskRequest {
    summary?: string;
    description?: string;
    status?: string;
    assignee?: string;
    priority?: string;
    labels?: string[];
    dueDate?: string;
    estimatedHours?: number;
}

export class TaskService {
    private client: NaviClient;
    private tasksCache: Map<string, JiraTask> = new Map();
    private projectsCache: Map<string, JiraProject> = new Map();
    private lastCacheUpdate: number = 0;
    private cacheExpiry: number;

    constructor(client: NaviClient, cacheExpiryMs?: number) {
        this.client = client;
        this.cacheExpiry = cacheExpiryMs ?? 5 * 60 * 1000; // default 5 minutes
    }

    /**
     * Get all tasks (with optional filters)
     */
    async getTasks(filters?: TaskSearchFilters): Promise<JiraTask[]> {
        try {
            const params = new URLSearchParams();

            if (filters?.projectKey) {
                params.append('project', filters.projectKey);
            }
            if (filters?.assignee) {
                params.append('assignee', filters.assignee);
            }
            if (filters?.status) {
                params.append('status', filters.status);
            }
            if (filters?.priority) {
                params.append('priority', filters.priority);
            }
            if (filters?.issueType) {
                params.append('type', filters.issueType);
            }
            if (filters?.search) {
                params.append('q', filters.search);
            }
            if (filters?.updatedSince) {
                params.append('updated_since', filters.updatedSince);
            }
            if (filters?.labels && filters.labels.length > 0) {
                params.append('labels', filters.labels.join(','));
            }

            const queryString = params.toString();
            const endpoint = `/api/navi/tasks${queryString ? `?${queryString}` : ''}`;

            const response = await this.client.request<{ items: JiraTask[] }>(endpoint);

            // Update cache
            response.items.forEach(task => {
                this.tasksCache.set(task.key, task);
            });
            this.lastCacheUpdate = Date.now();

            return response.items;
        } catch (error) {
            console.error('Failed to get tasks:', error);
            throw error;
        }
    }

    /**
     * Get single task by key
     */
    async getTask(taskKey: string, forceRefresh: boolean = false): Promise<JiraTask> {
        try {
            // Check cache first
            if (!forceRefresh && this.isTaskCacheValid(taskKey)) {
                return this.tasksCache.get(taskKey)!;
            }

            const response = await this.client.request<JiraTask>(`/api/navi/tasks/${taskKey}`);

            // Update cache
            this.tasksCache.set(taskKey, response);

            return response;
        } catch (error) {
            console.error(`Failed to get task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Get comprehensive task context (task + related data)
     */
    async getTaskContext(taskKey: string): Promise<TaskContext> {
        try {
            const response = await this.client.request<TaskContext>(`/api/context/pack`, {
                method: 'POST',
                body: JSON.stringify({
                    query: taskKey,
                    task_key: taskKey,
                    k: 10
                })
            });

            return response;
        } catch (error) {
            console.error(`Failed to get task context for ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Get dashboard data (assigned tasks, statistics, etc.)
     */
    async getDashboard(): Promise<TaskDashboard> {
        try {
            const response = await this.client.request<TaskDashboard>('/api/navi/dashboard');
            return response;
        } catch (error) {
            console.error('Failed to get dashboard:', error);
            throw error;
        }
    }

    /**
     * Get projects list
     */
    async getProjects(): Promise<JiraProject[]> {
        try {
            // Check cache first
            if (this.projectsCache.size > 0 && this.isCacheValid()) {
                return Array.from(this.projectsCache.values());
            }

            const response = await this.client.request<{ projects: JiraProject[] }>('/api/navi/projects');

            // Update cache
            response.projects.forEach(project => {
                this.projectsCache.set(project.key, project);
            });
            this.lastCacheUpdate = Date.now();

            return response.projects;
        } catch (error) {
            console.error('Failed to get projects:', error);
            throw error;
        }
    }

    /**
     * Get project by key
     */
    async getProject(projectKey: string): Promise<JiraProject> {
        try {
            // Check cache first
            if (this.projectsCache.has(projectKey) && this.isCacheValid()) {
                return this.projectsCache.get(projectKey)!;
            }

            const response = await this.client.request<JiraProject>(`/api/navi/projects/${projectKey}`);

            // Update cache
            this.projectsCache.set(projectKey, response);

            return response;
        } catch (error) {
            console.error(`Failed to get project ${projectKey}:`, error);
            throw error;
        }
    }

    /**
     * Create new task
     */
    async createTask(request: CreateTaskRequest): Promise<JiraTask> {
        try {
            const response = await this.client.request<JiraTask>('/api/navi/tasks', {
                method: 'POST',
                body: JSON.stringify(request)
            });

            // Add to cache
            this.tasksCache.set(response.key, response);

            return response;
        } catch (error) {
            console.error('Failed to create task:', error);
            throw error;
        }
    }

    /**
     * Update existing task
     */
    async updateTask(taskKey: string, updates: UpdateTaskRequest): Promise<JiraTask> {
        try {
            const response = await this.client.request<JiraTask>(`/api/navi/tasks/${taskKey}`, {
                method: 'PATCH',
                body: JSON.stringify(updates)
            });

            // Update cache
            this.tasksCache.set(taskKey, response);

            return response;
        } catch (error) {
            console.error(`Failed to update task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Transition task to new status
     */
    async transitionTask(taskKey: string, newStatus: string, comment?: string): Promise<JiraTask> {
        try {
            const response = await this.client.request<JiraTask>(`/api/navi/tasks/${taskKey}/transition`, {
                method: 'POST',
                body: JSON.stringify({
                    status: newStatus,
                    comment
                })
            });

            // Update cache
            this.tasksCache.set(taskKey, response);

            return response;
        } catch (error) {
            console.error(`Failed to transition task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Add comment to task
     */
    async addComment(taskKey: string, comment: string): Promise<Comment> {
        try {
            const response = await this.client.request<Comment>(`/api/navi/tasks/${taskKey}/comments`, {
                method: 'POST',
                body: JSON.stringify({ body: comment })
            });

            return response;
        } catch (error) {
            console.error(`Failed to add comment to task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Get comments for task
     */
    async getComments(taskKey: string): Promise<Comment[]> {
        try {
            const response = await this.client.request<{ comments: Comment[] }>(`/api/navi/tasks/${taskKey}/comments`);
            return response.comments;
        } catch (error) {
            console.error(`Failed to get comments for task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Assign task to user
     */
    async assignTask(taskKey: string, assignee: string): Promise<JiraTask> {
        try {
            return await this.updateTask(taskKey, { assignee });
        } catch (error) {
            console.error(`Failed to assign task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Search tasks
     */
    async searchTasks(query: string, projectKey?: string): Promise<JiraTask[]> {
        try {
            return await this.getTasks({
                search: query,
                projectKey
            });
        } catch (error) {
            console.error('Failed to search tasks:', error);
            throw error;
        }
    }

    /**
     * Get my assigned tasks
     */
    async getMyTasks(): Promise<JiraTask[]> {
        try {
            return await this.getTasks({
                assignee: 'currentUser'
            });
        } catch (error) {
            console.error('Failed to get my tasks:', error);
            throw error;
        }
    }

    /**
     * Get tasks in progress
     */
    async getInProgressTasks(projectKey?: string): Promise<JiraTask[]> {
        try {
            return await this.getTasks({
                status: 'In Progress',
                projectKey
            });
        } catch (error) {
            console.error('Failed to get in-progress tasks:', error);
            throw error;
        }
    }

    /**
     * Get recently updated tasks
     */
    async getRecentTasks(days: number = 7, projectKey?: string): Promise<JiraTask[]> {
        try {
            const since = new Date();
            since.setDate(since.getDate() - days);

            return await this.getTasks({
                updatedSince: since.toISOString(),
                projectKey
            });
        } catch (error) {
            console.error('Failed to get recent tasks:', error);
            throw error;
        }
    }

    /**
     * Get task analytics
     */
    async getAnalytics(projectKey?: string, timeframe?: 'week' | 'month' | 'quarter'): Promise<any> {
        try {
            const params = new URLSearchParams();

            if (projectKey) {
                params.append('project', projectKey);
            }
            if (timeframe) {
                params.append('timeframe', timeframe);
            }

            const queryString = params.toString();
            const endpoint = `/api/navi/analytics${queryString ? `?${queryString}` : ''}`;

            const response = await this.client.request<any>(endpoint);
            return response;
        } catch (error) {
            console.error('Failed to get analytics:', error);
            throw error;
        }
    }

    /**
     * Link task to PR
     */
    async linkTaskToPR(taskKey: string, prUrl: string): Promise<void> {
        try {
            await this.client.request(`/api/navi/tasks/${taskKey}/links`, {
                method: 'POST',
                body: JSON.stringify({
                    type: 'pull_request',
                    url: prUrl
                })
            });
        } catch (error) {
            console.error(`Failed to link task ${taskKey} to PR:`, error);
            throw error;
        }
    }

    /**
     * Get linked PRs for task
     */
    async getLinkedPRs(taskKey: string): Promise<LinkedPR[]> {
        try {
            const response = await this.client.request<{ pull_requests: LinkedPR[] }>(
                `/api/navi/tasks/${taskKey}/links?type=pull_request`
            );
            return response.pull_requests;
        } catch (error) {
            console.error(`Failed to get linked PRs for task ${taskKey}:`, error);
            throw error;
        }
    }

    /**
     * Check if task cache is valid
     */
    private isTaskCacheValid(taskKey: string): boolean {
        return this.tasksCache.has(taskKey) && this.isCacheValid();
    }

    /**
     * Check if general cache is valid
     */
    private isCacheValid(): boolean {
        return Date.now() - this.lastCacheUpdate < this.cacheExpiry;
    }

    /**
     * Clear cache
     */
    clearCache(): void {
        this.tasksCache.clear();
        this.projectsCache.clear();
        this.lastCacheUpdate = 0;
    }

    /**
     * Invalidate specific task in cache
     */
    invalidateTask(taskKey: string): void {
        this.tasksCache.delete(taskKey);
    }

    dispose(): void {
        this.clearCache();
    }
}
