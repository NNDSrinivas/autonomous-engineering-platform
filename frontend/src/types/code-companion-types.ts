export interface FileItem {
  id: string;
  name: string;
  type: 'file' | 'folder';
  language?: string;
  children?: FileItem[];
  content?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  codeBlocks?: CodeBlock[];
  actions?: ActionItem[];
  sources?: SourceLink[];
  requiresApproval?: boolean;
  approvalStatus?: 'pending' | 'approved' | 'rejected';
  modelId?: string;
  modelName?: string;
}

export interface CodeBlock {
  language: string;
  code: string;
}

export interface ActionItem {
  id: string;
  type: 'implement' | 'fix' | 'create_pr' | 'commit' | 'run_tests' | 'deploy';
  label: string;
  status: 'pending' | 'approved' | 'rejected' | 'completed';
}

export interface SourceLink {
  type: 'jira' | 'slack' | 'teams' | 'confluence' | 'github' | 'zoom' | 'meeting';
  title: string;
  url: string;
  snippet?: string;
}

export interface CodeSuggestion {
  id: string;
  code: string;
  description: string;
  confidence: number;
}

export interface EditorTab {
  id: string;
  name: string;
  language: string;
  content: string;
  isModified: boolean;
}

// NAVI Types
export interface JiraTask {
  id: string;
  key: string;
  title: string;
  description: string;
  status: 'todo' | 'in_progress' | 'in_review' | 'done' | 'blocked';
  priority: 'low' | 'medium' | 'high' | 'critical';
  assignee: string | null;
  sprint?: string | null;
  epic?: string;
  project?: string | null;
  labels?: string[];
  storyPoints?: number | null;
  acceptanceCriteria?: string[];
  linkedPRs?: string[];
  relatedDocs?: SourceLink[];
  relatedMessages?: SourceLink[];
  relatedMeetings?: MeetingNote[];
  createdAt?: Date;
  updatedAt?: Date;
}

export interface MeetingNote {
  id: string;
  title: string;
  date: Date;
  type: 'standup' | 'grooming' | 'sprint_planning' | 'retrospective' | 'ad_hoc';
  platform: 'zoom' | 'teams' | 'google_meet';
  summary: string;
  actionItems: string[];
  decisions: string[];
  mentions: string[];
  transcriptUrl?: string;
}

export interface SlackMessage {
  id: string;
  channel: string;
  author: string;
  content: string;
  timestamp: Date;
  threadUrl?: string;
  reactions?: string[];
}

export interface ConfluenceDoc {
  id: string;
  title: string;
  space: string;
  url: string;
  lastUpdated: Date;
  author: string;
  type: 'design_doc' | 'adr' | 'runbook' | 'wiki' | 'requirements';
}

export interface GitHubPR {
  id: string;
  number: number;
  title: string;
  status: 'open' | 'merged' | 'closed';
  author: string;
  branch: string;
  targetBranch: string;
  reviewStatus: 'pending' | 'approved' | 'changes_requested';
  comments: number;
  commits: number;
  additions: number;
  deletions: number;
  url: string;
  linkedIssue?: string;
  checksStatus: 'pending' | 'passing' | 'failing';
}

export interface CICDBuild {
  id: string;
  pipeline: string;
  status: 'running' | 'success' | 'failed' | 'cancelled';
  branch: string;
  commit: string;
  triggeredBy: string;
  startedAt: Date;
  duration?: number;
  logs?: string;
  failureReason?: string;
}

export interface Integration {
  id: string;
  name: string;
  type: 'jira' | 'slack' | 'teams' | 'confluence' | 'github' | 'zoom' | 'cicd';
  status: 'connected' | 'disconnected' | 'error';
  lastSync?: Date;
  config?: Record<string, unknown>;
}

export interface UserContext {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  avatar?: string;
  role: string;
  team: string;
  timezone: string;
  preferences: {
    llmProvider: 'openai' | 'anthropic' | 'llama' | 'gemini';
    autoApprove: boolean;
    notificationLevel: 'all' | 'important' | 'minimal';
  };
}

export interface NaviState {
  currentTask?: JiraTask;
  activeIntegrations: Integration[];
  recentActivity: ActivityItem[];
  contextSources: SourceLink[];
}

export interface ActivityItem {
  id: string;
  type: 'task_update' | 'pr_update' | 'build_status' | 'message' | 'meeting';
  title: string;
  description: string;
  timestamp: Date;
  source: string;
  url?: string;
}
