export interface JiraTask {
  id: string;
  key: string;
  title: string;
  description?: string;
  status?: string;
  priority?: string;
  assignee?: string;
  created?: string;
  updated?: string;
}

export interface GitHubPR {
  id: number;
  number: number;
  title: string;
  url: string;
  state: 'open' | 'closed' | 'merged';
  author: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  phases: string[];
  config: Record<string, any>;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'user';
  avatar?: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  repository?: string;
  owner: string;
  created_at: string;
  updated_at: string;
}