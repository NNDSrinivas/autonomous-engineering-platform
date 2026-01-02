// User types
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// JIRA Task types
export interface JiraTask {
  id: string;
  key: string;
  summary: string;
  description?: string;
  status: string;
  priority: string;
  assignee?: {
    id: string;
    name: string;
    email: string;
  };
  reporter?: {
    id: string;
    name: string;
    email: string;
  };
  created: string;
  updated: string;
  labels?: string[];
  components?: string[];
  project: {
    id: string;
    key: string;
    name: string;
  };
}

// Chat types
export interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
  user_id: string;
}

// Project types
export interface Project {
  id: string;
  name: string;
  description?: string;
  status: 'active' | 'inactive' | 'completed';
  created_at: string;
  updated_at: string;
  owner_id: string;
}

// API Response types
export interface ApiResponse<T = any> {
  data?: T;
  message?: string;
  error?: string;
  status: number;
}

// Search types
export interface SearchResult {
  type: 'file' | 'commit' | 'pr' | 'issue' | 'doc';
  title: string;
  description: string;
  path?: string;
  url?: string;
  score: number;
  metadata?: Record<string, any>;
}

export interface SearchFilters {
  files: boolean;
  commits: boolean;
  prs: boolean;
  issues: boolean;
  docs: boolean;
}