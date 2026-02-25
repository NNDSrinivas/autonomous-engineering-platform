import React, { useState, useEffect, useCallback } from "react";
import {
  Bell,
  ChevronLeft,
  ChevronRight,
  Clock,
  GitBranch,
  HelpCircle,
  LogIn,
  LogOut,
  Moon,
  MoreHorizontal,
  PanelLeft,
  PenSquare,
  Plus,
  Settings,
  Sun,
  User,
  Zap,
  Check,
  X,
  Eye,
  EyeOff,
  ExternalLink,
  Shield,
  Play,
  Copy,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  CheckCircle2,
  Database,
  Bug,
  FileText,
  TestTube,
  BarChart3,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Key,
  Link,
  Unlink,
  Search,
  Star,
  Grid,
  Code,
  MessageSquare,
  Cloud,
  Lock,
  Cpu,
  Mail,
  Smartphone,
  Package,
  DollarSign,
  Headphones,
  Calendar,
  Layers,
  TrendingUp,
  Building,
  Award,
  Briefcase,
  Activity,
  Server,
} from "lucide-react";
import { naviClient, McpExecutionResult, McpServer, buildHeaders, resolveBackendBase } from "../../api/navi/client";
import NaviChatPanel from "../navi/NaviChatPanel";
import { HistoryPanel } from "../navi/HistoryPanel";
import { SidebarPanel } from "../sidebar/SidebarPanel";
import { PremiumAuthEntry } from "../auth/PremiumAuthEntry";
import { ActivityPanel } from "../ActivityPanel";
import { useActivityPanel } from "../../hooks/useActivityPanel";
import { postMessage, onMessage } from "../../utils/vscodeApi";
import "../../styles/futuristic.css";

interface UserInfo {
  email?: string;
  name?: string;
  picture?: string;
  org?: string;
  role?: string;
  sub?: string;
}

interface OrgInfo {
  id: string;
  name: string;
  slug: string;
  role: string;
}

interface AuthSignInStatus {
  state: "starting" | "browser_opened" | "waiting_for_approval" | "success" | "error";
  message: string;
  userCode?: string;
  verificationUri?: string;
  recoverable?: boolean;
}

const NICKNAME_KEY = "aep.navi.nickname.v1";
const SELECTED_ORG_KEY = "aep.navi.selectedOrg.v1";

const readNickname = () => {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(NICKNAME_KEY) || "";
  } catch {
    return "";
  }
};

const readSelectedOrg = () => {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(SELECTED_ORG_KEY) || "";
  } catch {
    return "";
  }
};

const writeSelectedOrg = (value: string) => {
  if (typeof window === "undefined") return;
  try {
    if (!value) {
      window.localStorage.removeItem(SELECTED_ORG_KEY);
    } else {
      window.localStorage.setItem(SELECTED_ORG_KEY, value);
    }
  } catch {
    // ignore storage errors
  }
};

const writeNickname = (value: string) => {
  if (typeof window === "undefined") return;
  try {
    if (!value.trim()) {
      window.localStorage.removeItem(NICKNAME_KEY);
    } else {
      window.localStorage.setItem(NICKNAME_KEY, value.trim());
    }
  } catch {
    // ignore storage errors
  }
};

const decodeJwtUser = (token?: string | null): UserInfo | undefined => {
  if (!token) return undefined;
  const parts = token.split(".");
  if (parts.length !== 3) return undefined;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    const preferredName =
      payload.name ||
      payload.preferred_username ||
      payload.nickname ||
      [payload.given_name, payload.family_name].filter(Boolean).join(" ").trim();
    return {
      email: payload.email,
      name: preferredName || undefined,
      org: payload.org || payload.org_id,
      role: payload.role,
      sub: payload.sub,
    };
  } catch {
    return undefined;
  }
};

const firstName = (name?: string) => {
  if (!name) return "";
  return name.split(" ")[0]?.trim() || "";
};

const formatNameFromEmail = (email?: string) => {
  if (!email) return "";
  const [local] = email.split("@");
  if (!local) return "";
  return local
    .replace(/[._-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part: string) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
};

const resolveUserName = (user?: UserInfo) => {
  const rawName = user?.name?.trim();
  if (rawName && rawName.toLowerCase() !== "user") {
    return rawName;
  }
  const emailName = formatNameFromEmail(user?.email);
  if (emailName) return emailName;
  return "NAVI User";
};

const normalizeUserInfo = (user?: UserInfo): UserInfo | undefined => {
  if (!user) return undefined;
  return {
    ...user,
    name: resolveUserName(user),
  };
};

type SidebarPanelType = 'mcp' | 'connectors' | 'account' | 'rules' | null;
type CommandCenterTab = 'mcp' | 'integrations' | 'rules' | 'account';

// MCP Tool interfaces
interface McpToolProperty {
  type?: string;
  description?: string;
  enum?: string[];
  default?: unknown;
}

interface McpTool {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, McpToolProperty>;
    required: string[];
  };
  metadata: {
    category: string;
    requires_approval: boolean;
    server_id?: string | number;
    server_name?: string;
    source?: 'builtin' | 'external';
    transport?: string;
    scope?: 'org' | 'user' | 'builtin';
  };
}

// Connector interface with category support
interface Connector {
  id: string;
  name: string;
  description: string;
  icon: string;
  logoUrl?: string; // Brand logo URL
  category: ConnectorCategory;
  status: 'connected' | 'disconnected' | 'error';
  authType: 'oauth' | 'api_key' | 'token' | 'basic';
  lastSync?: string;
  configFields?: { key: string; label: string; type: 'text' | 'password'; placeholder?: string }[];
  popular?: boolean;
}

type ConnectorCategory =
  | 'developer_tools'
  | 'project_management'
  | 'communication'
  | 'cloud_infrastructure'
  | 'databases'
  | 'ci_cd'
  | 'monitoring'
  | 'documentation'
  | 'security'
  | 'analytics'
  | 'crm_sales'
  | 'marketing'
  | 'productivity'
  | 'finance'
  | 'hr'
  | 'design'
  | 'ai_ml'
  | 'data_warehouses'
  | 'storage'
  | 'identity';

// Category definitions as an array for iteration (with Lucide icons)
const CONNECTOR_CATEGORIES: { id: ConnectorCategory; label: string; icon: React.ReactNode }[] = [
  { id: 'developer_tools', label: 'Dev Tools', icon: <Code className="h-4 w-4" /> },
  { id: 'project_management', label: 'Projects', icon: <Briefcase className="h-4 w-4" /> },
  { id: 'communication', label: 'Communication', icon: <MessageSquare className="h-4 w-4" /> },
  { id: 'cloud_infrastructure', label: 'Cloud', icon: <Cloud className="h-4 w-4" /> },
  { id: 'databases', label: 'Databases', icon: <Database className="h-4 w-4" /> },
  { id: 'ci_cd', label: 'CI/CD', icon: <RefreshCw className="h-4 w-4" /> },
  { id: 'monitoring', label: 'Monitoring', icon: <Activity className="h-4 w-4" /> },
  { id: 'documentation', label: 'Docs', icon: <FileText className="h-4 w-4" /> },
  { id: 'security', label: 'Security', icon: <Lock className="h-4 w-4" /> },
  { id: 'analytics', label: 'Analytics', icon: <TrendingUp className="h-4 w-4" /> },
  { id: 'crm_sales', label: 'CRM & Sales', icon: <Briefcase className="h-4 w-4" /> },
  { id: 'marketing', label: 'Marketing', icon: <Award className="h-4 w-4" /> },
  { id: 'productivity', label: 'Productivity', icon: <Zap className="h-4 w-4" /> },
  { id: 'finance', label: 'Finance', icon: <DollarSign className="h-4 w-4" /> },
  { id: 'hr', label: 'HR', icon: <User className="h-4 w-4" /> },
  { id: 'design', label: 'Design', icon: <Layers className="h-4 w-4" /> },
  { id: 'ai_ml', label: 'AI & ML', icon: <Cpu className="h-4 w-4" /> },
  { id: 'data_warehouses', label: 'Data Warehouses', icon: <Building className="h-4 w-4" /> },
  { id: 'storage', label: 'Storage', icon: <Package className="h-4 w-4" /> },
  { id: 'identity', label: 'Identity', icon: <Key className="h-4 w-4" /> },
];

// Comprehensive connector marketplace - 280+ connectors
const ALL_CONNECTORS: Connector[] = [
  // Developer Tools (Popular)
  { id: 'github', name: 'GitHub', description: 'Code hosting, PRs, issues, actions', icon: 'github', logoUrl: 'https://cdn.simpleicons.org/github/white', category: 'developer_tools', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'gitlab', name: 'GitLab', description: 'DevOps platform, CI/CD, repos', icon: 'gitlab', logoUrl: 'https://cdn.simpleicons.org/gitlab', category: 'developer_tools', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'bitbucket', name: 'Bitbucket', description: 'Git code management', icon: 'bitbucket', logoUrl: 'https://cdn.simpleicons.org/bitbucket', category: 'developer_tools', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'azure-devops', name: 'Azure DevOps', description: 'Microsoft DevOps services', icon: 'azure', logoUrl: 'https://cdn.simpleicons.org/azuredevops', category: 'developer_tools', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'vscode', name: 'VS Code', description: 'Code editor integration', icon: 'vscode', logoUrl: 'https://cdn.simpleicons.org/visualstudiocode', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'jetbrains', name: 'JetBrains', description: 'IDE family (IntelliJ, PyCharm)', icon: 'jetbrains', logoUrl: 'https://cdn.simpleicons.org/jetbrains', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'npm', name: 'npm', description: 'Node package registry', icon: 'npm', logoUrl: 'https://cdn.simpleicons.org/npm', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'pypi', name: 'PyPI', description: 'Python package index', icon: 'python', logoUrl: 'https://cdn.simpleicons.org/pypi', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'maven', name: 'Maven Central', description: 'Java package repository', icon: 'maven', logoUrl: 'https://cdn.simpleicons.org/apachemaven', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'nuget', name: 'NuGet', description: '.NET package manager', icon: 'nuget', logoUrl: 'https://cdn.simpleicons.org/nuget', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'crates', name: 'crates.io', description: 'Rust package registry', icon: 'rust', logoUrl: 'https://cdn.simpleicons.org/rust', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'docker-hub', name: 'Docker Hub', description: 'Container registry', icon: 'docker', logoUrl: 'https://cdn.simpleicons.org/docker', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'harbor', name: 'Harbor', description: 'Cloud native registry', icon: 'harbor', logoUrl: 'https://cdn.simpleicons.org/harbor', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'artifactory', name: 'JFrog Artifactory', description: 'Universal artifact repository', icon: 'jfrog', logoUrl: 'https://cdn.simpleicons.org/jfrog', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'sonarqube', name: 'SonarQube', description: 'Code quality & security', icon: 'sonarqube', logoUrl: 'https://cdn.simpleicons.org/sonarqube', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'codecov', name: 'Codecov', description: 'Code coverage reporting', icon: 'codecov', logoUrl: 'https://cdn.simpleicons.org/codecov', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'codeclimate', name: 'Code Climate', description: 'Code quality platform', icon: 'codeclimate', logoUrl: 'https://cdn.simpleicons.org/codeclimate', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'snyk', name: 'Snyk', description: 'Developer security platform', icon: 'snyk', logoUrl: 'https://cdn.simpleicons.org/snyk', category: 'developer_tools', status: 'disconnected', authType: 'token' },
  { id: 'replit', name: 'Replit', description: 'Browser-based IDE', icon: 'replit', logoUrl: 'https://cdn.simpleicons.org/replit', category: 'developer_tools', status: 'disconnected', authType: 'oauth' },
  { id: 'codepen', name: 'CodePen', description: 'Frontend code playground', icon: 'codepen', logoUrl: 'https://cdn.simpleicons.org/codepen', category: 'developer_tools', status: 'disconnected', authType: 'oauth' },
  { id: 'codesandbox', name: 'CodeSandbox', description: 'Online IDE for web apps', icon: 'codesandbox', logoUrl: 'https://cdn.simpleicons.org/codesandbox', category: 'developer_tools', status: 'disconnected', authType: 'oauth' },
  { id: 'stackblitz', name: 'StackBlitz', description: 'Instant dev environments', icon: 'stackblitz', logoUrl: 'https://cdn.simpleicons.org/stackblitz', category: 'developer_tools', status: 'disconnected', authType: 'oauth' },
  { id: 'gitpod', name: 'Gitpod', description: 'Cloud development environments', icon: 'gitpod', logoUrl: 'https://cdn.simpleicons.org/gitpod', category: 'developer_tools', status: 'disconnected', authType: 'oauth' },
  { id: 'github-codespaces', name: 'GitHub Codespaces', description: 'Cloud dev environments', icon: 'github', logoUrl: 'https://cdn.simpleicons.org/github', category: 'developer_tools', status: 'disconnected', authType: 'oauth' },

  // Project Management
  { id: 'jira', name: 'Jira', description: 'Issue tracking & project management', icon: 'jira', logoUrl: 'https://cdn.simpleicons.org/jira', category: 'project_management', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'linear', name: 'Linear', description: 'Issue tracking for modern teams', icon: 'linear', logoUrl: 'https://cdn.simpleicons.org/linear', category: 'project_management', status: 'disconnected', authType: 'api_key', popular: true, configFields: [{ key: 'apiKey', label: 'API Key', type: 'password', placeholder: 'lin_api_...' }] },
  { id: 'asana', name: 'Asana', description: 'Work management platform', icon: 'asana', logoUrl: 'https://cdn.simpleicons.org/asana', category: 'project_management', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'trello', name: 'Trello', description: 'Kanban boards & collaboration', icon: 'trello', logoUrl: 'https://cdn.simpleicons.org/trello', category: 'project_management', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'monday', name: 'Monday.com', description: 'Work OS platform', icon: 'monday', logoUrl: 'https://cdn.simpleicons.org/mondaydotcom', category: 'project_management', status: 'disconnected', authType: 'oauth' },
  { id: 'clickup', name: 'ClickUp', description: 'All-in-one productivity', icon: 'clickup', logoUrl: 'https://cdn.simpleicons.org/clickup', category: 'project_management', status: 'disconnected', authType: 'oauth' },
  { id: 'notion', name: 'Notion', description: 'Workspace for notes & docs', icon: 'notion', logoUrl: 'https://cdn.simpleicons.org/notion', category: 'project_management', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'basecamp', name: 'Basecamp', description: 'Project management & team chat', icon: 'basecamp', logoUrl: 'https://cdn.simpleicons.org/basecamp', category: 'project_management', status: 'disconnected', authType: 'oauth' },
  { id: 'wrike', name: 'Wrike', description: 'Work management software', icon: 'wrike', logoUrl: 'https://cdn.simpleicons.org/wrike', category: 'project_management', status: 'disconnected', authType: 'oauth' },
  { id: 'smartsheet', name: 'Smartsheet', description: 'Collaborative work platform', icon: 'smartsheet', logoUrl: 'https://cdn.simpleicons.org/smartsheet', category: 'project_management', status: 'disconnected', authType: 'oauth' },
  { id: 'airtable', name: 'Airtable', description: 'Spreadsheet-database hybrid', icon: 'airtable', logoUrl: 'https://cdn.simpleicons.org/airtable', category: 'project_management', status: 'disconnected', authType: 'api_key' },
  { id: 'teamwork', name: 'Teamwork', description: 'Project management suite', icon: 'teamwork', logoUrl: 'https://cdn.simpleicons.org/teamwork', category: 'project_management', status: 'disconnected', authType: 'oauth' },
  { id: 'pivotal-tracker', name: 'Pivotal Tracker', description: 'Agile project management', icon: 'pivotaltracker', logoUrl: 'https://cdn.simpleicons.org/pivotaltracker', category: 'project_management', status: 'disconnected', authType: 'token' },
  { id: 'height', name: 'Height', description: 'Modern project tool', icon: 'height', logoUrl: 'https://height.app/favicon.ico', category: 'project_management', status: 'disconnected', authType: 'api_key' },
  { id: 'shortcut', name: 'Shortcut', description: 'Project management for software', icon: 'shortcut', logoUrl: 'https://cdn.simpleicons.org/shortcut', category: 'project_management', status: 'disconnected', authType: 'api_key' },
  { id: 'plane', name: 'Plane', description: 'Open-source project tracking', icon: 'plane', logoUrl: 'https://plane.so/favicon.ico', category: 'project_management', status: 'disconnected', authType: 'api_key' },

  // Communication
  { id: 'slack', name: 'Slack', description: 'Team messaging platform', icon: 'slack', logoUrl: 'https://cdn.simpleicons.org/slack', category: 'communication', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'discord', name: 'Discord', description: 'Community & team chat', icon: 'discord', logoUrl: 'https://cdn.simpleicons.org/discord', category: 'communication', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'teams', name: 'Microsoft Teams', description: 'Business communication', icon: 'teams', logoUrl: 'https://cdn.simpleicons.org/microsoftteams', category: 'communication', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'zoom', name: 'Zoom', description: 'Video conferencing', icon: 'zoom', logoUrl: 'https://cdn.simpleicons.org/zoom', category: 'communication', status: 'disconnected', authType: 'oauth' },
  { id: 'google-meet', name: 'Google Meet', description: 'Video meetings', icon: 'googlemeet', logoUrl: 'https://cdn.simpleicons.org/googlemeet', category: 'communication', status: 'disconnected', authType: 'oauth' },
  { id: 'webex', name: 'Webex', description: 'Video conferencing & calling', icon: 'webex', logoUrl: 'https://cdn.simpleicons.org/webex', category: 'communication', status: 'disconnected', authType: 'oauth' },
  { id: 'telegram', name: 'Telegram', description: 'Messaging platform', icon: 'telegram', logoUrl: 'https://cdn.simpleicons.org/telegram', category: 'communication', status: 'disconnected', authType: 'token' },
  { id: 'mattermost', name: 'Mattermost', description: 'Open source messaging', icon: 'mattermost', logoUrl: 'https://cdn.simpleicons.org/mattermost', category: 'communication', status: 'disconnected', authType: 'token' },
  { id: 'rocket-chat', name: 'Rocket.Chat', description: 'Team communication platform', icon: 'rocketchat', logoUrl: 'https://cdn.simpleicons.org/rocketdotchat', category: 'communication', status: 'disconnected', authType: 'token' },
  { id: 'zulip', name: 'Zulip', description: 'Threaded team chat', icon: 'zulip', logoUrl: 'https://cdn.simpleicons.org/zulip', category: 'communication', status: 'disconnected', authType: 'api_key' },
  { id: 'element', name: 'Element (Matrix)', description: 'Secure collaboration', icon: 'element', logoUrl: 'https://cdn.simpleicons.org/element', category: 'communication', status: 'disconnected', authType: 'token' },
  { id: 'intercom', name: 'Intercom', description: 'Customer messaging', icon: 'intercom', logoUrl: 'https://cdn.simpleicons.org/intercom', category: 'communication', status: 'disconnected', authType: 'oauth' },
  { id: 'twilio', name: 'Twilio', description: 'Cloud communications', icon: 'twilio', logoUrl: 'https://cdn.simpleicons.org/twilio', category: 'communication', status: 'disconnected', authType: 'api_key' },
  { id: 'sendgrid', name: 'SendGrid', description: 'Email delivery service', icon: 'sendgrid', logoUrl: 'https://cdn.simpleicons.org/sendgrid', category: 'communication', status: 'disconnected', authType: 'api_key' },
  { id: 'mailchimp', name: 'Mailchimp', description: 'Email marketing', icon: 'mailchimp', logoUrl: 'https://cdn.simpleicons.org/mailchimp', category: 'communication', status: 'disconnected', authType: 'oauth' },

  // Cloud & Infrastructure
  { id: 'aws', name: 'Amazon Web Services', description: 'Cloud computing platform', icon: 'aws', logoUrl: 'https://cdn.simpleicons.org/amazonaws', category: 'cloud_infrastructure', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'azure', name: 'Microsoft Azure', description: 'Cloud services', icon: 'azure', logoUrl: 'https://cdn.simpleicons.org/microsoftazure', category: 'cloud_infrastructure', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'gcp', name: 'Google Cloud', description: 'Google cloud platform', icon: 'googlecloud', logoUrl: 'https://cdn.simpleicons.org/googlecloud', category: 'cloud_infrastructure', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'digitalocean', name: 'DigitalOcean', description: 'Cloud infrastructure', icon: 'digitalocean', logoUrl: 'https://cdn.simpleicons.org/digitalocean', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'linode', name: 'Linode', description: 'Cloud hosting provider', icon: 'linode', logoUrl: 'https://cdn.simpleicons.org/linode', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'vultr', name: 'Vultr', description: 'Cloud compute', icon: 'vultr', logoUrl: 'https://cdn.simpleicons.org/vultr', category: 'cloud_infrastructure', status: 'disconnected', authType: 'api_key' },
  { id: 'heroku', name: 'Heroku', description: 'Platform as a service', icon: 'heroku', logoUrl: 'https://cdn.simpleicons.org/heroku', category: 'cloud_infrastructure', status: 'disconnected', authType: 'oauth' },
  { id: 'vercel', name: 'Vercel', description: 'Frontend cloud platform', icon: 'vercel', logoUrl: 'https://cdn.simpleicons.org/vercel', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token', popular: true },
  { id: 'netlify', name: 'Netlify', description: 'Web development platform', icon: 'netlify', logoUrl: 'https://cdn.simpleicons.org/netlify', category: 'cloud_infrastructure', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'cloudflare', name: 'Cloudflare', description: 'Web security & performance', icon: 'cloudflare', logoUrl: 'https://cdn.simpleicons.org/cloudflare', category: 'cloud_infrastructure', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'railway', name: 'Railway', description: 'Infrastructure platform', icon: 'railway', logoUrl: 'https://cdn.simpleicons.org/railway', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'render', name: 'Render', description: 'Cloud application platform', icon: 'render', logoUrl: 'https://cdn.simpleicons.org/render', category: 'cloud_infrastructure', status: 'disconnected', authType: 'api_key' },
  { id: 'fly', name: 'Fly.io', description: 'Deploy app servers', icon: 'flydotio', logoUrl: 'https://cdn.simpleicons.org/flydotio', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'kubernetes', name: 'Kubernetes', description: 'Container orchestration', icon: 'kubernetes', logoUrl: 'https://cdn.simpleicons.org/kubernetes', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'terraform', name: 'Terraform', description: 'Infrastructure as code', icon: 'terraform', logoUrl: 'https://cdn.simpleicons.org/terraform', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'pulumi', name: 'Pulumi', description: 'Cloud engineering platform', icon: 'pulumi', logoUrl: 'https://cdn.simpleicons.org/pulumi', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'ansible', name: 'Ansible', description: 'Automation platform', icon: 'ansible', logoUrl: 'https://cdn.simpleicons.org/ansible', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'vagrant', name: 'Vagrant', description: 'Development environments', icon: 'vagrant', logoUrl: 'https://cdn.simpleicons.org/vagrant', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'openstack', name: 'OpenStack', description: 'Cloud computing platform', icon: 'openstack', logoUrl: 'https://cdn.simpleicons.org/openstack', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },
  { id: 'vmware', name: 'VMware', description: 'Virtualization platform', icon: 'vmware', logoUrl: 'https://cdn.simpleicons.org/vmware', category: 'cloud_infrastructure', status: 'disconnected', authType: 'token' },

  // Databases
  { id: 'postgresql', name: 'PostgreSQL', description: 'Relational database', icon: 'postgresql', logoUrl: 'https://cdn.simpleicons.org/postgresql', category: 'databases', status: 'disconnected', authType: 'basic', popular: true },
  { id: 'mysql', name: 'MySQL', description: 'Relational database', icon: 'mysql', logoUrl: 'https://cdn.simpleicons.org/mysql', category: 'databases', status: 'disconnected', authType: 'basic', popular: true },
  { id: 'mongodb', name: 'MongoDB', description: 'Document database', icon: 'mongodb', logoUrl: 'https://cdn.simpleicons.org/mongodb', category: 'databases', status: 'disconnected', authType: 'basic', popular: true },
  { id: 'redis', name: 'Redis', description: 'In-memory data store', icon: 'redis', logoUrl: 'https://cdn.simpleicons.org/redis', category: 'databases', status: 'disconnected', authType: 'basic', popular: true },
  { id: 'elasticsearch', name: 'Elasticsearch', description: 'Search & analytics', icon: 'elasticsearch', logoUrl: 'https://cdn.simpleicons.org/elasticsearch', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'cassandra', name: 'Cassandra', description: 'Distributed database', icon: 'apachecassandra', logoUrl: 'https://cdn.simpleicons.org/apachecassandra', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'dynamodb', name: 'DynamoDB', description: 'AWS NoSQL database', icon: 'amazondynamodb', logoUrl: 'https://cdn.simpleicons.org/amazondynamodb', category: 'databases', status: 'disconnected', authType: 'api_key' },
  { id: 'firebase', name: 'Firebase', description: 'Google app platform', icon: 'firebase', logoUrl: 'https://cdn.simpleicons.org/firebase', category: 'databases', status: 'disconnected', authType: 'oauth' },
  { id: 'supabase', name: 'Supabase', description: 'Open source Firebase', icon: 'supabase', logoUrl: 'https://cdn.simpleicons.org/supabase', category: 'databases', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'planetscale', name: 'PlanetScale', description: 'Serverless MySQL', icon: 'planetscale', logoUrl: 'https://cdn.simpleicons.org/planetscale', category: 'databases', status: 'disconnected', authType: 'token' },
  { id: 'neon', name: 'Neon', description: 'Serverless Postgres', icon: 'neon', logoUrl: 'https://neon.tech/favicon.ico', category: 'databases', status: 'disconnected', authType: 'api_key' },
  { id: 'cockroachdb', name: 'CockroachDB', description: 'Distributed SQL', icon: 'cockroachdb', logoUrl: 'https://cdn.simpleicons.org/cockroachlabs', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'fauna', name: 'Fauna', description: 'Distributed database', icon: 'fauna', logoUrl: 'https://cdn.simpleicons.org/fauna', category: 'databases', status: 'disconnected', authType: 'api_key' },
  { id: 'couchbase', name: 'Couchbase', description: 'NoSQL database', icon: 'couchbase', logoUrl: 'https://cdn.simpleicons.org/couchbase', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'neo4j', name: 'Neo4j', description: 'Graph database', icon: 'neo4j', logoUrl: 'https://cdn.simpleicons.org/neo4j', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'influxdb', name: 'InfluxDB', description: 'Time series database', icon: 'influxdb', logoUrl: 'https://cdn.simpleicons.org/influxdb', category: 'databases', status: 'disconnected', authType: 'token' },
  { id: 'timescale', name: 'Timescale', description: 'Time-series PostgreSQL', icon: 'timescale', logoUrl: 'https://cdn.simpleicons.org/timescale', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'mariadb', name: 'MariaDB', description: 'MySQL fork', icon: 'mariadb', logoUrl: 'https://cdn.simpleicons.org/mariadb', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'sqlite', name: 'SQLite', description: 'Embedded database', icon: 'sqlite', logoUrl: 'https://cdn.simpleicons.org/sqlite', category: 'databases', status: 'disconnected', authType: 'basic' },
  { id: 'prisma', name: 'Prisma', description: 'Database toolkit', icon: 'prisma', logoUrl: 'https://cdn.simpleicons.org/prisma', category: 'databases', status: 'disconnected', authType: 'token' },

  // CI/CD
  { id: 'github-actions', name: 'GitHub Actions', description: 'GitHub CI/CD workflows', icon: 'githubactions', logoUrl: 'https://cdn.simpleicons.org/githubactions', category: 'ci_cd', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'gitlab-ci', name: 'GitLab CI', description: 'GitLab pipelines', icon: 'gitlab', logoUrl: 'https://cdn.simpleicons.org/gitlab', category: 'ci_cd', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'jenkins', name: 'Jenkins', description: 'Automation server', icon: 'jenkins', logoUrl: 'https://cdn.simpleicons.org/jenkins', category: 'ci_cd', status: 'disconnected', authType: 'token', popular: true },
  { id: 'circleci', name: 'CircleCI', description: 'Continuous integration', icon: 'circleci', logoUrl: 'https://cdn.simpleicons.org/circleci', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'travis', name: 'Travis CI', description: 'CI for open source', icon: 'travisci', logoUrl: 'https://cdn.simpleicons.org/travisci', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'buildkite', name: 'Buildkite', description: 'CI/CD for teams', icon: 'buildkite', logoUrl: 'https://cdn.simpleicons.org/buildkite', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'teamcity', name: 'TeamCity', description: 'JetBrains CI server', icon: 'teamcity', logoUrl: 'https://cdn.simpleicons.org/teamcity', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'bamboo', name: 'Bamboo', description: 'Atlassian CI/CD', icon: 'bamboo', logoUrl: 'https://cdn.simpleicons.org/bamboo', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'drone', name: 'Drone CI', description: 'Container-native CI', icon: 'drone', logoUrl: 'https://cdn.simpleicons.org/drone', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'semaphore', name: 'Semaphore', description: 'Fast CI/CD', icon: 'semaphore', logoUrl: 'https://cdn.simpleicons.org/semaphoreci', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'codefresh', name: 'Codefresh', description: 'GitOps CI/CD', icon: 'codefresh', logoUrl: 'https://cdn.simpleicons.org/codefresh', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'argocd', name: 'Argo CD', description: 'GitOps for Kubernetes', icon: 'argo', logoUrl: 'https://cdn.simpleicons.org/argo', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'flux', name: 'Flux CD', description: 'GitOps toolkit', icon: 'flux', logoUrl: 'https://fluxcd.io/favicon.ico', category: 'ci_cd', status: 'disconnected', authType: 'token' },
  { id: 'spinnaker', name: 'Spinnaker', description: 'Multi-cloud CD', icon: 'spinnaker', logoUrl: 'https://cdn.simpleicons.org/spinnaker', category: 'ci_cd', status: 'disconnected', authType: 'token' },

  // Monitoring & Observability
  { id: 'datadog', name: 'Datadog', description: 'Cloud monitoring', icon: 'datadog', logoUrl: 'https://cdn.simpleicons.org/datadog', category: 'monitoring', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'grafana', name: 'Grafana', description: 'Analytics & monitoring', icon: 'grafana', logoUrl: 'https://cdn.simpleicons.org/grafana', category: 'monitoring', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'prometheus', name: 'Prometheus', description: 'Monitoring system', icon: 'prometheus', logoUrl: 'https://cdn.simpleicons.org/prometheus', category: 'monitoring', status: 'disconnected', authType: 'token' },
  { id: 'newrelic', name: 'New Relic', description: 'Observability platform', icon: 'newrelic', logoUrl: 'https://cdn.simpleicons.org/newrelic', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'splunk', name: 'Splunk', description: 'Data platform', icon: 'splunk', logoUrl: 'https://cdn.simpleicons.org/splunk', category: 'monitoring', status: 'disconnected', authType: 'token' },
  { id: 'pagerduty', name: 'PagerDuty', description: 'Incident management', icon: 'pagerduty', logoUrl: 'https://cdn.simpleicons.org/pagerduty', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'opsgenie', name: 'Opsgenie', description: 'Alert management', icon: 'opsgenie', logoUrl: 'https://cdn.simpleicons.org/opsgenie', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'sentry', name: 'Sentry', description: 'Error tracking', icon: 'sentry', logoUrl: 'https://cdn.simpleicons.org/sentry', category: 'monitoring', status: 'disconnected', authType: 'token', popular: true },
  { id: 'rollbar', name: 'Rollbar', description: 'Error monitoring', icon: 'rollbar', logoUrl: 'https://cdn.simpleicons.org/rollbar', category: 'monitoring', status: 'disconnected', authType: 'token' },
  { id: 'bugsnag', name: 'Bugsnag', description: 'Error monitoring', icon: 'bugsnag', logoUrl: 'https://cdn.simpleicons.org/bugsnag', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'logrocket', name: 'LogRocket', description: 'Session replay', icon: 'logrocket', logoUrl: 'https://cdn.simpleicons.org/logrocket', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'honeycomb', name: 'Honeycomb', description: 'Observability platform', icon: 'honeycomb', logoUrl: 'https://cdn.simpleicons.org/honeycomb', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'lightstep', name: 'Lightstep', description: 'Distributed tracing', icon: 'lightstep', logoUrl: 'https://cdn.simpleicons.org/lightstep', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'jaeger', name: 'Jaeger', description: 'Distributed tracing', icon: 'jaeger', logoUrl: 'https://cdn.simpleicons.org/jaeger', category: 'monitoring', status: 'disconnected', authType: 'token' },
  { id: 'zipkin', name: 'Zipkin', description: 'Distributed tracing', icon: 'zipkin', logoUrl: 'https://zipkin.io/public/favicon.ico', category: 'monitoring', status: 'disconnected', authType: 'token' },
  { id: 'statuspage', name: 'Statuspage', description: 'Status communication', icon: 'statuspage', logoUrl: 'https://cdn.simpleicons.org/statuspage', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'uptime-robot', name: 'Uptime Robot', description: 'Website monitoring', icon: 'uptimerobot', logoUrl: 'https://cdn.simpleicons.org/uptimerobot', category: 'monitoring', status: 'disconnected', authType: 'api_key' },
  { id: 'pingdom', name: 'Pingdom', description: 'Website monitoring', icon: 'pingdom', logoUrl: 'https://cdn.simpleicons.org/pingdom', category: 'monitoring', status: 'disconnected', authType: 'api_key' },

  // Documentation
  { id: 'confluence', name: 'Confluence', description: 'Team documentation', icon: 'confluence', logoUrl: 'https://cdn.simpleicons.org/confluence', category: 'documentation', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'gitbook', name: 'GitBook', description: 'Modern documentation', icon: 'gitbook', logoUrl: 'https://cdn.simpleicons.org/gitbook', category: 'documentation', status: 'disconnected', authType: 'api_key' },
  { id: 'readme', name: 'ReadMe', description: 'API documentation', icon: 'readme', logoUrl: 'https://cdn.simpleicons.org/readme', category: 'documentation', status: 'disconnected', authType: 'api_key' },
  { id: 'docusaurus', name: 'Docusaurus', description: 'Documentation sites', icon: 'docusaurus', logoUrl: 'https://cdn.simpleicons.org/docusaurus', category: 'documentation', status: 'disconnected', authType: 'token' },
  { id: 'mintlify', name: 'Mintlify', description: 'Beautiful docs', icon: 'mintlify', logoUrl: 'https://mintlify.com/favicon.ico', category: 'documentation', status: 'disconnected', authType: 'api_key' },
  { id: 'swagger', name: 'Swagger', description: 'API design & docs', icon: 'swagger', logoUrl: 'https://cdn.simpleicons.org/swagger', category: 'documentation', status: 'disconnected', authType: 'api_key' },
  { id: 'postman', name: 'Postman', description: 'API platform', icon: 'postman', logoUrl: 'https://cdn.simpleicons.org/postman', category: 'documentation', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'insomnia', name: 'Insomnia', description: 'API client', icon: 'insomnia', logoUrl: 'https://cdn.simpleicons.org/insomnia', category: 'documentation', status: 'disconnected', authType: 'token' },
  { id: 'stoplight', name: 'Stoplight', description: 'API design platform', icon: 'stoplight', logoUrl: 'https://cdn.simpleicons.org/stoplight', category: 'documentation', status: 'disconnected', authType: 'api_key' },

  // Security
  { id: 'vault', name: 'HashiCorp Vault', description: 'Secrets management', icon: 'vault', logoUrl: 'https://cdn.simpleicons.org/vault', category: 'security', status: 'disconnected', authType: 'token', popular: true },
  { id: '1password', name: '1Password', description: 'Password manager', icon: '1password', logoUrl: 'https://cdn.simpleicons.org/1password', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'lastpass', name: 'LastPass', description: 'Password management', icon: 'lastpass', logoUrl: 'https://cdn.simpleicons.org/lastpass', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'doppler', name: 'Doppler', description: 'Secrets management', icon: 'doppler', logoUrl: 'https://cdn.simpleicons.org/doppler', category: 'security', status: 'disconnected', authType: 'token' },
  { id: 'aws-secrets', name: 'AWS Secrets Manager', description: 'AWS secrets', icon: 'aws', logoUrl: 'https://cdn.simpleicons.org/amazonaws', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'azure-keyvault', name: 'Azure Key Vault', description: 'Azure secrets', icon: 'azure', logoUrl: 'https://cdn.simpleicons.org/microsoftazure', category: 'security', status: 'disconnected', authType: 'oauth' },
  { id: 'gcp-secrets', name: 'GCP Secret Manager', description: 'Google secrets', icon: 'googlecloud', logoUrl: 'https://cdn.simpleicons.org/googlecloud', category: 'security', status: 'disconnected', authType: 'oauth' },
  { id: 'crowdstrike', name: 'CrowdStrike', description: 'Endpoint security', icon: 'crowdstrike', logoUrl: 'https://cdn.simpleicons.org/crowdstrike', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'veracode', name: 'Veracode', description: 'Application security', icon: 'veracode', logoUrl: 'https://cdn.simpleicons.org/veracode', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'checkmarx', name: 'Checkmarx', description: 'AppSec platform', icon: 'checkmarx', logoUrl: 'https://cdn.simpleicons.org/checkmarx', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'fortify', name: 'Fortify', description: 'Application security', icon: 'fortify', logoUrl: 'https://www.microfocus.com/favicon.ico', category: 'security', status: 'disconnected', authType: 'api_key' },
  { id: 'dependabot', name: 'Dependabot', description: 'Dependency updates', icon: 'dependabot', logoUrl: 'https://cdn.simpleicons.org/dependabot', category: 'security', status: 'disconnected', authType: 'oauth' },
  { id: 'renovate', name: 'Renovate', description: 'Dependency updates', icon: 'renovate', logoUrl: 'https://cdn.simpleicons.org/renovate', category: 'security', status: 'disconnected', authType: 'token' },

  // Analytics
  { id: 'google-analytics', name: 'Google Analytics', description: 'Web analytics', icon: 'googleanalytics', logoUrl: 'https://cdn.simpleicons.org/googleanalytics', category: 'analytics', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'mixpanel', name: 'Mixpanel', description: 'Product analytics', icon: 'mixpanel', logoUrl: 'https://cdn.simpleicons.org/mixpanel', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'amplitude', name: 'Amplitude', description: 'Product analytics', icon: 'amplitude', logoUrl: 'https://cdn.simpleicons.org/amplitude', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'segment', name: 'Segment', description: 'Customer data platform', icon: 'segment', logoUrl: 'https://cdn.simpleicons.org/segment', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'heap', name: 'Heap', description: 'Digital insights', icon: 'heap', logoUrl: 'https://cdn.simpleicons.org/heap', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'posthog', name: 'PostHog', description: 'Product analytics', icon: 'posthog', logoUrl: 'https://cdn.simpleicons.org/posthog', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'plausible', name: 'Plausible', description: 'Privacy-friendly analytics', icon: 'plausible', logoUrl: 'https://cdn.simpleicons.org/plausible', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'fathom', name: 'Fathom', description: 'Simple analytics', icon: 'fathom', logoUrl: 'https://usefathom.com/favicon.ico', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'hotjar', name: 'Hotjar', description: 'Behavior analytics', icon: 'hotjar', logoUrl: 'https://cdn.simpleicons.org/hotjar', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'fullstory', name: 'FullStory', description: 'Digital experience', icon: 'fullstory', logoUrl: 'https://cdn.simpleicons.org/fullstory', category: 'analytics', status: 'disconnected', authType: 'api_key' },
  { id: 'tableau', name: 'Tableau', description: 'Visual analytics', icon: 'tableau', logoUrl: 'https://cdn.simpleicons.org/tableau', category: 'analytics', status: 'disconnected', authType: 'oauth' },
  { id: 'looker', name: 'Looker', description: 'Business intelligence', icon: 'looker', logoUrl: 'https://cdn.simpleicons.org/looker', category: 'analytics', status: 'disconnected', authType: 'oauth' },
  { id: 'metabase', name: 'Metabase', description: 'Business analytics', icon: 'metabase', logoUrl: 'https://cdn.simpleicons.org/metabase', category: 'analytics', status: 'disconnected', authType: 'basic' },
  { id: 'powerbi', name: 'Power BI', description: 'Microsoft BI', icon: 'powerbi', logoUrl: 'https://cdn.simpleicons.org/powerbi', category: 'analytics', status: 'disconnected', authType: 'oauth' },

  // CRM & Sales
  { id: 'salesforce', name: 'Salesforce', description: 'CRM platform', icon: 'salesforce', logoUrl: 'https://cdn.simpleicons.org/salesforce', category: 'crm_sales', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'hubspot', name: 'HubSpot', description: 'CRM & marketing', icon: 'hubspot', logoUrl: 'https://cdn.simpleicons.org/hubspot', category: 'crm_sales', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'pipedrive', name: 'Pipedrive', description: 'Sales CRM', icon: 'pipedrive', logoUrl: 'https://cdn.simpleicons.org/pipedrive', category: 'crm_sales', status: 'disconnected', authType: 'api_key' },
  { id: 'zoho-crm', name: 'Zoho CRM', description: 'CRM software', icon: 'zoho', logoUrl: 'https://cdn.simpleicons.org/zoho', category: 'crm_sales', status: 'disconnected', authType: 'oauth' },
  { id: 'freshsales', name: 'Freshsales', description: 'Sales CRM', icon: 'freshsales', logoUrl: 'https://cdn.simpleicons.org/freshworks', category: 'crm_sales', status: 'disconnected', authType: 'api_key' },
  { id: 'close', name: 'Close', description: 'Sales CRM', icon: 'close', logoUrl: 'https://close.com/favicon.ico', category: 'crm_sales', status: 'disconnected', authType: 'api_key' },
  { id: 'copper', name: 'Copper', description: 'Google CRM', icon: 'copper', logoUrl: 'https://www.copper.com/favicon.ico', category: 'crm_sales', status: 'disconnected', authType: 'api_key' },
  { id: 'zendesk', name: 'Zendesk', description: 'Customer service', icon: 'zendesk', logoUrl: 'https://cdn.simpleicons.org/zendesk', category: 'crm_sales', status: 'disconnected', authType: 'oauth' },
  { id: 'freshdesk', name: 'Freshdesk', description: 'Help desk software', icon: 'freshdesk', logoUrl: 'https://cdn.simpleicons.org/freshworks', category: 'crm_sales', status: 'disconnected', authType: 'api_key' },
  { id: 'gong', name: 'Gong', description: 'Revenue intelligence', icon: 'gong', logoUrl: 'https://www.gong.io/favicon.ico', category: 'crm_sales', status: 'disconnected', authType: 'oauth' },
  { id: 'outreach', name: 'Outreach', description: 'Sales engagement', icon: 'outreach', logoUrl: 'https://www.outreach.io/favicon.ico', category: 'crm_sales', status: 'disconnected', authType: 'oauth' },
  { id: 'apollo', name: 'Apollo.io', description: 'Sales intelligence', icon: 'apollo', logoUrl: 'https://www.apollo.io/favicon.ico', category: 'crm_sales', status: 'disconnected', authType: 'api_key' },

  // Marketing
  { id: 'google-ads', name: 'Google Ads', description: 'Advertising platform', icon: 'googleads', logoUrl: 'https://cdn.simpleicons.org/googleads', category: 'marketing', status: 'disconnected', authType: 'oauth' },
  { id: 'facebook-ads', name: 'Facebook Ads', description: 'Social advertising', icon: 'facebook', logoUrl: 'https://cdn.simpleicons.org/facebook', category: 'marketing', status: 'disconnected', authType: 'oauth' },
  { id: 'linkedin-ads', name: 'LinkedIn Ads', description: 'B2B advertising', icon: 'linkedin', logoUrl: 'https://cdn.simpleicons.org/linkedin', category: 'marketing', status: 'disconnected', authType: 'oauth' },
  { id: 'twitter-ads', name: 'Twitter Ads', description: 'Social advertising', icon: 'twitter', logoUrl: 'https://cdn.simpleicons.org/x', category: 'marketing', status: 'disconnected', authType: 'oauth' },
  { id: 'marketo', name: 'Marketo', description: 'Marketing automation', icon: 'marketo', logoUrl: 'https://cdn.simpleicons.org/marketo', category: 'marketing', status: 'disconnected', authType: 'oauth' },
  { id: 'pardot', name: 'Pardot', description: 'B2B marketing', icon: 'salesforce', logoUrl: 'https://cdn.simpleicons.org/salesforce', category: 'marketing', status: 'disconnected', authType: 'oauth' },
  { id: 'activecampaign', name: 'ActiveCampaign', description: 'Email marketing', icon: 'activecampaign', logoUrl: 'https://cdn.simpleicons.org/activecampaign', category: 'marketing', status: 'disconnected', authType: 'api_key' },
  { id: 'klaviyo', name: 'Klaviyo', description: 'Ecommerce marketing', icon: 'klaviyo', logoUrl: 'https://cdn.simpleicons.org/klaviyo', category: 'marketing', status: 'disconnected', authType: 'api_key' },
  { id: 'braze', name: 'Braze', description: 'Customer engagement', icon: 'braze', logoUrl: 'https://www.braze.com/favicon.ico', category: 'marketing', status: 'disconnected', authType: 'api_key' },
  { id: 'customer-io', name: 'Customer.io', description: 'Messaging platform', icon: 'customerdotio', logoUrl: 'https://cdn.simpleicons.org/customerdotio', category: 'marketing', status: 'disconnected', authType: 'api_key' },
  { id: 'iterable', name: 'Iterable', description: 'Cross-channel marketing', icon: 'iterable', logoUrl: 'https://cdn.simpleicons.org/iterable', category: 'marketing', status: 'disconnected', authType: 'api_key' },

  // Productivity
  { id: 'google-workspace', name: 'Google Workspace', description: 'Productivity suite', icon: 'google', logoUrl: 'https://cdn.simpleicons.org/google', category: 'productivity', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'microsoft-365', name: 'Microsoft 365', description: 'Office suite', icon: 'microsoft', logoUrl: 'https://cdn.simpleicons.org/microsoft', category: 'productivity', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'dropbox', name: 'Dropbox', description: 'File storage', icon: 'dropbox', logoUrl: 'https://cdn.simpleicons.org/dropbox', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'box', name: 'Box', description: 'Cloud content', icon: 'box', logoUrl: 'https://cdn.simpleicons.org/box', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'google-drive', name: 'Google Drive', description: 'Cloud storage', icon: 'googledrive', logoUrl: 'https://cdn.simpleicons.org/googledrive', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'onedrive', name: 'OneDrive', description: 'Microsoft storage', icon: 'onedrive', logoUrl: 'https://cdn.simpleicons.org/microsoftonedrive', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'evernote', name: 'Evernote', description: 'Note-taking app', icon: 'evernote', logoUrl: 'https://cdn.simpleicons.org/evernote', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'todoist', name: 'Todoist', description: 'Task management', icon: 'todoist', logoUrl: 'https://cdn.simpleicons.org/todoist', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'calendar', name: 'Google Calendar', description: 'Calendar management', icon: 'googlecalendar', logoUrl: 'https://cdn.simpleicons.org/googlecalendar', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'calendly', name: 'Calendly', description: 'Scheduling tool', icon: 'calendly', logoUrl: 'https://cdn.simpleicons.org/calendly', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'zapier', name: 'Zapier', description: 'Workflow automation', icon: 'zapier', logoUrl: 'https://cdn.simpleicons.org/zapier', category: 'productivity', status: 'disconnected', authType: 'oauth' },
  { id: 'make', name: 'Make (Integromat)', description: 'Visual automation', icon: 'make', logoUrl: 'https://cdn.simpleicons.org/make', category: 'productivity', status: 'disconnected', authType: 'api_key' },
  { id: 'n8n', name: 'n8n', description: 'Workflow automation', icon: 'n8n', logoUrl: 'https://cdn.simpleicons.org/n8n', category: 'productivity', status: 'disconnected', authType: 'api_key' },

  // Finance
  { id: 'stripe', name: 'Stripe', description: 'Payment processing', icon: 'stripe', logoUrl: 'https://cdn.simpleicons.org/stripe', category: 'finance', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'plaid', name: 'Plaid', description: 'Financial services API', icon: 'plaid', logoUrl: 'https://cdn.simpleicons.org/plaid', category: 'finance', status: 'disconnected', authType: 'api_key' },
  { id: 'quickbooks', name: 'QuickBooks', description: 'Accounting software', icon: 'quickbooks', logoUrl: 'https://cdn.simpleicons.org/quickbooks', category: 'finance', status: 'disconnected', authType: 'oauth' },
  { id: 'xero', name: 'Xero', description: 'Accounting platform', icon: 'xero', logoUrl: 'https://cdn.simpleicons.org/xero', category: 'finance', status: 'disconnected', authType: 'oauth' },
  { id: 'brex', name: 'Brex', description: 'Corporate cards', icon: 'brex', logoUrl: 'https://cdn.simpleicons.org/brex', category: 'finance', status: 'disconnected', authType: 'api_key' },
  { id: 'ramp', name: 'Ramp', description: 'Corporate cards', icon: 'ramp', logoUrl: 'https://ramp.com/favicon.ico', category: 'finance', status: 'disconnected', authType: 'oauth' },
  { id: 'bill', name: 'Bill.com', description: 'AP/AR automation', icon: 'billdotcom', logoUrl: 'https://cdn.simpleicons.org/billdotcom', category: 'finance', status: 'disconnected', authType: 'oauth' },
  { id: 'chargebee', name: 'Chargebee', description: 'Subscription billing', icon: 'chargebee', logoUrl: 'https://cdn.simpleicons.org/chargebee', category: 'finance', status: 'disconnected', authType: 'api_key' },
  { id: 'recurly', name: 'Recurly', description: 'Subscription management', icon: 'recurly', logoUrl: 'https://cdn.simpleicons.org/recurly', category: 'finance', status: 'disconnected', authType: 'api_key' },

  // HR & Recruiting
  { id: 'workday', name: 'Workday', description: 'HR & finance', icon: 'workday', logoUrl: 'https://cdn.simpleicons.org/workday', category: 'hr', status: 'disconnected', authType: 'oauth' },
  { id: 'bamboohr', name: 'BambooHR', description: 'HR software', icon: 'bamboohr', logoUrl: 'https://cdn.simpleicons.org/bamboohr', category: 'hr', status: 'disconnected', authType: 'api_key' },
  { id: 'gusto', name: 'Gusto', description: 'Payroll & benefits', icon: 'gusto', logoUrl: 'https://cdn.simpleicons.org/gusto', category: 'hr', status: 'disconnected', authType: 'oauth' },
  { id: 'rippling', name: 'Rippling', description: 'HR platform', icon: 'rippling', logoUrl: 'https://www.rippling.com/favicon.ico', category: 'hr', status: 'disconnected', authType: 'oauth' },
  { id: 'lever', name: 'Lever', description: 'Recruiting software', icon: 'lever', logoUrl: 'https://cdn.simpleicons.org/lever', category: 'hr', status: 'disconnected', authType: 'api_key' },
  { id: 'greenhouse', name: 'Greenhouse', description: 'Recruiting platform', icon: 'greenhouse', logoUrl: 'https://cdn.simpleicons.org/greenhouse', category: 'hr', status: 'disconnected', authType: 'api_key' },
  { id: 'ashby', name: 'Ashby', description: 'All-in-one recruiting', icon: 'ashby', logoUrl: 'https://www.ashbyhq.com/favicon.ico', category: 'hr', status: 'disconnected', authType: 'api_key' },
  { id: 'deel', name: 'Deel', description: 'Global payroll', icon: 'deel', logoUrl: 'https://cdn.simpleicons.org/deel', category: 'hr', status: 'disconnected', authType: 'api_key' },
  { id: 'remote', name: 'Remote', description: 'Global HR', icon: 'remote', logoUrl: 'https://remote.com/favicon.ico', category: 'hr', status: 'disconnected', authType: 'api_key' },

  // Design
  { id: 'figma', name: 'Figma', description: 'Design platform', icon: 'figma', logoUrl: 'https://cdn.simpleicons.org/figma', category: 'design', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'sketch', name: 'Sketch', description: 'Design tool', icon: 'sketch', logoUrl: 'https://cdn.simpleicons.org/sketch', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'adobe-xd', name: 'Adobe XD', description: 'UI/UX design', icon: 'adobexd', logoUrl: 'https://cdn.simpleicons.org/adobexd', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'invision', name: 'InVision', description: 'Design collaboration', icon: 'invision', logoUrl: 'https://cdn.simpleicons.org/invision', category: 'design', status: 'disconnected', authType: 'api_key' },
  { id: 'zeplin', name: 'Zeplin', description: 'Design handoff', icon: 'zeplin', logoUrl: 'https://cdn.simpleicons.org/zeplin', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'framer', name: 'Framer', description: 'Interactive design', icon: 'framer', logoUrl: 'https://cdn.simpleicons.org/framer', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'canva', name: 'Canva', description: 'Visual content', icon: 'canva', logoUrl: 'https://cdn.simpleicons.org/canva', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'miro', name: 'Miro', description: 'Visual collaboration', icon: 'miro', logoUrl: 'https://cdn.simpleicons.org/miro', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'figjam', name: 'FigJam', description: 'Whiteboarding', icon: 'figma', logoUrl: 'https://cdn.simpleicons.org/figma', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'whimsical', name: 'Whimsical', description: 'Visual workspace', icon: 'whimsical', logoUrl: 'https://whimsical.com/favicon.ico', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'lucidchart', name: 'Lucidchart', description: 'Diagramming', icon: 'lucidchart', logoUrl: 'https://cdn.simpleicons.org/lucid', category: 'design', status: 'disconnected', authType: 'oauth' },
  { id: 'draw-io', name: 'Draw.io', description: 'Diagram editor', icon: 'diagramsdotnet', logoUrl: 'https://cdn.simpleicons.org/diagramsdotnet', category: 'design', status: 'disconnected', authType: 'oauth' },

  // AI & Machine Learning
  { id: 'openai', name: 'OpenAI', description: 'AI research lab', icon: 'openai', logoUrl: 'https://cdn.simpleicons.org/openai', category: 'ai_ml', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'anthropic', name: 'Anthropic', description: 'AI safety company', icon: 'anthropic', logoUrl: 'https://cdn.simpleicons.org/anthropic', category: 'ai_ml', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'cohere', name: 'Cohere', description: 'NLP platform', icon: 'cohere', logoUrl: 'https://cdn.simpleicons.org/cohere', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'huggingface', name: 'Hugging Face', description: 'ML community', icon: 'huggingface', logoUrl: 'https://cdn.simpleicons.org/huggingface', category: 'ai_ml', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'replicate', name: 'Replicate', description: 'Run ML models', icon: 'replicate', logoUrl: 'https://cdn.simpleicons.org/replicate', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'weights-biases', name: 'Weights & Biases', description: 'ML experiment tracking', icon: 'weightsandbiases', logoUrl: 'https://cdn.simpleicons.org/weightsandbiases', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'mlflow', name: 'MLflow', description: 'ML lifecycle', icon: 'mlflow', logoUrl: 'https://cdn.simpleicons.org/mlflow', category: 'ai_ml', status: 'disconnected', authType: 'token' },
  { id: 'sagemaker', name: 'AWS SageMaker', description: 'ML on AWS', icon: 'amazonsagemaker', logoUrl: 'https://cdn.simpleicons.org/amazonsagemaker', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'vertex-ai', name: 'Vertex AI', description: 'Google Cloud ML', icon: 'googlecloud', logoUrl: 'https://cdn.simpleicons.org/googlecloud', category: 'ai_ml', status: 'disconnected', authType: 'oauth' },
  { id: 'azure-ml', name: 'Azure ML', description: 'Microsoft ML', icon: 'azure', logoUrl: 'https://cdn.simpleicons.org/microsoftazure', category: 'ai_ml', status: 'disconnected', authType: 'oauth' },
  { id: 'langchain', name: 'LangChain', description: 'LLM framework', icon: 'langchain', logoUrl: 'https://cdn.simpleicons.org/langchain', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'pinecone', name: 'Pinecone', description: 'Vector database', icon: 'pinecone', logoUrl: 'https://cdn.simpleicons.org/pinecone', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'weaviate', name: 'Weaviate', description: 'Vector search', icon: 'weaviate', logoUrl: 'https://cdn.simpleicons.org/weaviate', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },
  { id: 'qdrant', name: 'Qdrant', description: 'Vector similarity', icon: 'qdrant', logoUrl: 'https://cdn.simpleicons.org/qdrant', category: 'ai_ml', status: 'disconnected', authType: 'api_key' },

  // Data Warehouses
  { id: 'snowflake', name: 'Snowflake', description: 'Cloud data platform', icon: 'snowflake', logoUrl: 'https://cdn.simpleicons.org/snowflake', category: 'data_warehouses', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'bigquery', name: 'BigQuery', description: 'Google data warehouse', icon: 'googlebigquery', logoUrl: 'https://cdn.simpleicons.org/googlebigquery', category: 'data_warehouses', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'redshift', name: 'Amazon Redshift', description: 'AWS data warehouse', icon: 'amazonredshift', logoUrl: 'https://cdn.simpleicons.org/amazonredshift', category: 'data_warehouses', status: 'disconnected', authType: 'api_key' },
  { id: 'databricks', name: 'Databricks', description: 'Unified analytics', icon: 'databricks', logoUrl: 'https://cdn.simpleicons.org/databricks', category: 'data_warehouses', status: 'disconnected', authType: 'token', popular: true },
  { id: 'dbt', name: 'dbt', description: 'Data transformation', icon: 'dbt', logoUrl: 'https://cdn.simpleicons.org/dbt', category: 'data_warehouses', status: 'disconnected', authType: 'api_key' },
  { id: 'fivetran', name: 'Fivetran', description: 'Data integration', icon: 'fivetran', logoUrl: 'https://cdn.simpleicons.org/fivetran', category: 'data_warehouses', status: 'disconnected', authType: 'api_key' },
  { id: 'stitch', name: 'Stitch', description: 'ETL service', icon: 'stitch', logoUrl: 'https://cdn.simpleicons.org/stitch', category: 'data_warehouses', status: 'disconnected', authType: 'api_key' },
  { id: 'airbyte', name: 'Airbyte', description: 'Data integration', icon: 'airbyte', logoUrl: 'https://cdn.simpleicons.org/airbyte', category: 'data_warehouses', status: 'disconnected', authType: 'api_key' },
  { id: 'clickhouse', name: 'ClickHouse', description: 'OLAP database', icon: 'clickhouse', logoUrl: 'https://cdn.simpleicons.org/clickhouse', category: 'data_warehouses', status: 'disconnected', authType: 'basic' },
  { id: 'druid', name: 'Apache Druid', description: 'Real-time analytics', icon: 'apachedruid', logoUrl: 'https://cdn.simpleicons.org/apachedruid', category: 'data_warehouses', status: 'disconnected', authType: 'basic' },

  // Storage
  { id: 's3', name: 'Amazon S3', description: 'Object storage', icon: 'amazons3', logoUrl: 'https://cdn.simpleicons.org/amazons3', category: 'storage', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'gcs', name: 'Google Cloud Storage', description: 'Object storage', icon: 'googlecloud', logoUrl: 'https://cdn.simpleicons.org/googlecloud', category: 'storage', status: 'disconnected', authType: 'oauth' },
  { id: 'azure-blob', name: 'Azure Blob', description: 'Object storage', icon: 'microsoftazure', logoUrl: 'https://cdn.simpleicons.org/microsoftazure', category: 'storage', status: 'disconnected', authType: 'oauth' },
  { id: 'backblaze', name: 'Backblaze B2', description: 'Cloud storage', icon: 'backblaze', logoUrl: 'https://cdn.simpleicons.org/backblaze', category: 'storage', status: 'disconnected', authType: 'api_key' },
  { id: 'wasabi', name: 'Wasabi', description: 'Cloud storage', icon: 'wasabi', logoUrl: 'https://wasabi.com/favicon.ico', category: 'storage', status: 'disconnected', authType: 'api_key' },
  { id: 'minio', name: 'MinIO', description: 'S3-compatible storage', icon: 'minio', logoUrl: 'https://cdn.simpleicons.org/minio', category: 'storage', status: 'disconnected', authType: 'api_key' },
  { id: 'cloudinary', name: 'Cloudinary', description: 'Media management', icon: 'cloudinary', logoUrl: 'https://cdn.simpleicons.org/cloudinary', category: 'storage', status: 'disconnected', authType: 'api_key' },
  { id: 'imgix', name: 'imgix', description: 'Image processing', icon: 'imgix', logoUrl: 'https://cdn.simpleicons.org/imgix', category: 'storage', status: 'disconnected', authType: 'api_key' },
  { id: 'uploadcare', name: 'Uploadcare', description: 'File uploads', icon: 'uploadcare', logoUrl: 'https://cdn.simpleicons.org/uploadcare', category: 'storage', status: 'disconnected', authType: 'api_key' },

  // Identity & Access
  { id: 'okta', name: 'Okta', description: 'Identity platform', icon: 'okta', logoUrl: 'https://cdn.simpleicons.org/okta', category: 'identity', status: 'disconnected', authType: 'oauth', popular: true },
  { id: 'auth0', name: 'Auth0', description: 'Authentication', icon: 'auth0', logoUrl: 'https://cdn.simpleicons.org/auth0', category: 'identity', status: 'disconnected', authType: 'api_key', popular: true },
  { id: 'onelogin', name: 'OneLogin', description: 'IAM solution', icon: 'onelogin', logoUrl: 'https://cdn.simpleicons.org/onelogin', category: 'identity', status: 'disconnected', authType: 'oauth' },
  { id: 'jumpcloud', name: 'JumpCloud', description: 'Directory platform', icon: 'jumpcloud', logoUrl: 'https://cdn.simpleicons.org/jumpcloud', category: 'identity', status: 'disconnected', authType: 'api_key' },
  { id: 'azure-ad', name: 'Azure AD', description: 'Microsoft identity', icon: 'microsoftazure', logoUrl: 'https://cdn.simpleicons.org/microsoftazure', category: 'identity', status: 'disconnected', authType: 'oauth' },
  { id: 'google-iam', name: 'Google Cloud IAM', description: 'Google identity', icon: 'googlecloud', logoUrl: 'https://cdn.simpleicons.org/googlecloud', category: 'identity', status: 'disconnected', authType: 'oauth' },
  { id: 'aws-iam', name: 'AWS IAM', description: 'AWS identity', icon: 'amazonaws', logoUrl: 'https://cdn.simpleicons.org/amazonaws', category: 'identity', status: 'disconnected', authType: 'api_key' },
  { id: 'clerk', name: 'Clerk', description: 'User management', icon: 'clerk', logoUrl: 'https://cdn.simpleicons.org/clerk', category: 'identity', status: 'disconnected', authType: 'api_key' },
  { id: 'stytch', name: 'Stytch', description: 'Passwordless auth', icon: 'stytch', logoUrl: 'https://stytch.com/favicon.ico', category: 'identity', status: 'disconnected', authType: 'api_key' },
  { id: 'workos', name: 'WorkOS', description: 'Enterprise auth', icon: 'workos', logoUrl: 'https://workos.com/favicon.ico', category: 'identity', status: 'disconnected', authType: 'api_key' },
];

// NAVI Rule interface
interface NaviRule {
  id: string;
  name: string;
  description: string;
  type: 'coding_standard' | 'auto_approval' | 'response_style' | 'security';
  enabled: boolean;
  config?: Record<string, unknown>;
}

// User preferences interface
interface UserPreferences {
  theme: 'dark' | 'light' | 'system';
  responseVerbosity: 'brief' | 'balanced' | 'detailed';
  explanationLevel: 'beginner' | 'intermediate' | 'expert';
  keyboardShortcuts: boolean;
  autoApprove: 'none' | 'safe' | 'all';
}

export function CodeCompanionShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true); // Sidebar closed by default
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<UserInfo | undefined>(undefined);
  const [nickname, setNickname] = useState(readNickname());
  const [orgOnboardingOpen, setOrgOnboardingOpen] = useState(false);
  const [orgs, setOrgs] = useState<OrgInfo[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState(readSelectedOrg());
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [inviteEmails, setInviteEmails] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [orgLoading, setOrgLoading] = useState(false);
  const [orgError, setOrgError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [chatSettingsTrigger, setChatSettingsTrigger] = useState(0);
  const [activityPanelOpen, setActivityPanelOpen] = useState(false);
  const [activityJumpCommandId, setActivityJumpCommandId] = useState<string | null>(null);
  const [chatJumpCommandId, setChatJumpCommandId] = useState<string | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [headerMoreOpen, setHeaderMoreOpen] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [externalPanelRequest, setExternalPanelRequest] = useState<SidebarPanelType>(null);
  const [fullPanelOpen, setFullPanelOpen] = useState(false);
  const [fullPanelTab, setFullPanelTab] = useState<CommandCenterTab>('mcp');
  const [authSignInStatus, setAuthSignInStatus] = useState<AuthSignInStatus | null>(null);

  // MCP Tools state
  const [mcpTools, setMcpTools] = useState<McpTool[]>([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [mcpError, setMcpError] = useState<string | null>(null);
  const [selectedMcpTool, setSelectedMcpTool] = useState<McpTool | null>(null);
  const [mcpToolArgs, setMcpToolArgs] = useState<Record<string, unknown>>({});
  const [mcpExecuting, setMcpExecuting] = useState(false);
  const [mcpResult, setMcpResult] = useState<McpExecutionResult | null>(null);
  const [expandedMcpCategories, setExpandedMcpCategories] = useState<Record<string, boolean>>({});
  const [mcpSearchQuery, setMcpSearchQuery] = useState('');
  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [mcpServerFilter, setMcpServerFilter] = useState<string>('all');
  const canManageMcpServers = user?.role === 'admin';

  // Connectors state - initialized from comprehensive marketplace (280+ connectors)
  const [connectors, setConnectors] = useState<Connector[]>(ALL_CONNECTORS);
  const [connectorSearchQuery, setConnectorSearchQuery] = useState('');
  const [selectedConnectorCategory, setSelectedConnectorCategory] = useState<ConnectorCategory | 'all' | 'popular'>('popular');
  const [configuringConnector, setConfiguringConnector] = useState<string | null>(null);
  const [connectorConfig, setConnectorConfig] = useState<Record<string, string>>({});

  // NAVI Rules state
  const [naviRules, setNaviRules] = useState<NaviRule[]>([
    { id: 'coding-style', name: 'Coding Standards', description: 'Follow team coding conventions and style guides', type: 'coding_standard', enabled: true },
    { id: 'auto-approve-read', name: 'Auto-approve Read Operations', description: 'Automatically approve file reads and searches', type: 'auto_approval', enabled: false },
    { id: 'detailed-responses', name: 'Detailed Explanations', description: 'Always provide detailed code explanations', type: 'response_style', enabled: true },
    { id: 'security-scan', name: 'Security Scanning', description: 'Scan code changes for security vulnerabilities', type: 'security', enabled: true },
    { id: 'test-first', name: 'Test-First Development', description: 'Suggest writing tests before implementation', type: 'coding_standard', enabled: false },
  ]);

  // Account preferences state
  const [preferences, setPreferences] = useState<UserPreferences>({
    theme: 'dark',
    responseVerbosity: 'balanced',
    explanationLevel: 'intermediate',
    keyboardShortcuts: true,
    autoApprove: 'none',
  });
  const [accountTab, setAccountTab] = useState<'profile' | 'preferences' | 'shortcuts'>('profile');

  const activityPanelState = useActivityPanel();

  // Always emit readiness, even when chat panel is not mounted (unauth state).
  useEffect(() => {
    postMessage({ type: "webview.ready", source: "CodeCompanionShell" });
  }, []);

  useEffect(() => {
    if (!activityPanelState.isVisible) {
      setActivityPanelOpen(false);
    }
  }, [activityPanelState.isVisible]);

  // Listen for messages from extension
  useEffect(() => {
    const unsubscribe = onMessage((message: any) => {
      if (message.type === "auth.stateChange") {
        setIsAuthenticated(message.isAuthenticated);
        if (message.isAuthenticated) {
          setAuthSignInStatus(null);
        }
        const currentConfig = (window as any).__AEP_CONFIG__ || {};
        if (message.isAuthenticated && message.authToken) {
          (window as any).__AEP_CONFIG__ = {
            ...currentConfig,
            authToken: message.authToken,
            orgId: message.orgId ?? currentConfig.orgId,
            userId: message.userId ?? currentConfig.userId,
          };
        } else if (!message.isAuthenticated) {
          (window as any).__AEP_CONFIG__ = {
            ...currentConfig,
            authToken: undefined,
          };
          setHistoryOpen(false);
          setActivityPanelOpen(false);
        }
        if (message.user) {
          setUser(normalizeUserInfo(message.user));
        } else {
          setUser(undefined);
        }
      }
      if (message.type === "auth.signIn.status") {
        if (message && typeof message.message === "string" && typeof message.state === "string") {
          setAuthSignInStatus({
            state: message.state as AuthSignInStatus["state"],
            message: message.message,
            userCode: typeof message.userCode === "string" ? message.userCode : undefined,
            verificationUri: typeof message.verificationUri === "string" ? message.verificationUri : undefined,
            recoverable: Boolean(message.recoverable),
          });
        }
      }
      if (message.type === "navi.sso.success" && message.token) {
        setIsAuthenticated(true);
        setAuthSignInStatus(null);
        const currentConfig = (window as any).__AEP_CONFIG__ || {};
        (window as any).__AEP_CONFIG__ = {
          ...currentConfig,
          authToken: message.token,
        };
        const tokenUser = message.user || decodeJwtUser(message.token);
        if (tokenUser) {
          setUser(normalizeUserInfo(tokenUser));
        }
      }
      // Handle panel.openOverlay from extension
      if (message.type === "panel.openOverlay" && message.panel) {
        // Ensure sidebar is open
        setSidebarCollapsed(false);
        // Set the external panel request
        setExternalPanelRequest(message.panel as SidebarPanelType);
      }
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const handleSsoMessage = (event: MessageEvent) => {
      const msg = event.data;
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "navi.sso.success" && msg.token) {
        setIsAuthenticated(true);
        const currentConfig = (window as any).__AEP_CONFIG__ || {};
        (window as any).__AEP_CONFIG__ = {
          ...currentConfig,
          authToken: msg.token,
        };
        const tokenUser = msg.user || decodeJwtUser(msg.token);
        if (tokenUser) {
          setUser(normalizeUserInfo(tokenUser));
        }
      }
    };
    window.addEventListener("message", handleSsoMessage);
    return () => window.removeEventListener("message", handleSsoMessage);
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      void fetchOrgs();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated && fullPanelOpen && fullPanelTab !== 'account') {
      setFullPanelTab('account');
    }
  }, [isAuthenticated, fullPanelOpen, fullPanelTab]);

  // Keyboard handler: close "More" menu on Escape key
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && headerMoreOpen) {
        setHeaderMoreOpen(false);
      }
    };

    if (headerMoreOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [headerMoreOpen]);

  // Handle sign in/out
  const handleSignIn = () => {
    setAuthSignInStatus({
      state: "starting",
      message: "Starting secure sign-in...",
    });
    postMessage({ type: "auth.signIn" });
  };

  const handleSignUp = () => {
    setAuthSignInStatus(null);
    postMessage({ type: "auth.signUp" });
  };

  const handleSignOut = () => {
    postMessage({ type: "auth.signOut" });
    setUserMenuOpen(false);
  };

  const handleOpenActivityForCommand = useCallback((commandId: string) => {
    if (!commandId) return;
    setActivityPanelOpen(true);
    setActivityJumpCommandId(commandId);
  }, []);

  const handleViewCommandInChat = useCallback((commandId: string) => {
    if (!commandId) return;
    setChatJumpCommandId(commandId);
  }, []);

  const displayName =
    nickname ||
    firstName(resolveUserName(user)) ||
    user?.email?.split("@")[0] ||
    "NAVI User";

  const applySelectedOrg = (org: OrgInfo | undefined) => {
    if (!org) return;
    setSelectedOrgId(org.id);
    writeSelectedOrg(org.id);
    const currentConfig = (window as any).__AEP_CONFIG__ || {};
    (window as any).__AEP_CONFIG__ = {
      ...currentConfig,
      orgId: org.id,
    };
    setUser((prev) => ({
      ...(prev || {}),
      org: org.name,
    }));
  };

  const fetchOrgs = async () => {
    try {
      setOrgLoading(true);
      const base = resolveBackendBase();
      const res = await fetch(`${base}/api/orgs`, { headers: buildHeaders() });
      if (!res.ok) {
        throw new Error("Failed to load organizations");
      }
      const data = (await res.json()) as OrgInfo[];
      setOrgs(data);
      if (!data.length) {
        setOrgOnboardingOpen(true);
        return;
      }
      const matched = data.find((org) => org.id === selectedOrgId) || data[0];
      applySelectedOrg(matched);
      setOrgOnboardingOpen(false);
    } catch (err: any) {
      setOrgError(err?.message || "Unable to load orgs");
      setOrgOnboardingOpen(true);
    } finally {
      setOrgLoading(false);
    }
  };

  const createOrg = async () => {
    if (!orgName.trim()) {
      setOrgError("Organization name required");
      return;
    }
    try {
      setOrgLoading(true);
      const base = resolveBackendBase();
      const res = await fetch(`${base}/api/orgs`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify({ name: orgName.trim(), slug: orgSlug.trim() || undefined }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to create org");
      }
      const org = (await res.json()) as OrgInfo;
      setOrgs((prev) => [org, ...prev]);
      setOrgName("");
      setOrgSlug("");
      applySelectedOrg(org);
      setOrgOnboardingOpen(false);
      setOrgError(null);
    } catch (err: any) {
      setOrgError(err?.message || "Unable to create org");
    } finally {
      setOrgLoading(false);
    }
  };

  const selectOrg = async (orgId: string) => {
    try {
      setOrgLoading(true);
      const base = resolveBackendBase();
      const res = await fetch(`${base}/api/orgs/select`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify({ org_id: orgId }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to select org");
      }
      const org = orgs.find((o) => o.id === orgId);
      applySelectedOrg(org);
      setOrgOnboardingOpen(false);
      setOrgError(null);
    } catch (err: any) {
      setOrgError(err?.message || "Unable to select org");
    } finally {
      setOrgLoading(false);
    }
  };

  const sendInvites = async () => {
    if (!selectedOrgId) {
      setOrgError("Select an organization first");
      return;
    }
    const emails = inviteEmails
      .split(/[,\n\s]+/)
      .map((e) => e.trim())
      .filter(Boolean);
    if (!emails.length) {
      setOrgError("Enter at least one email");
      return;
    }
    try {
      setOrgLoading(true);
      const base = resolveBackendBase();
      const res = await fetch(`${base}/api/orgs/invite`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify({ org_id: selectedOrgId, emails, role: inviteRole }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to send invites");
      }
      setInviteEmails("");
      setOrgError(null);
    } catch (err: any) {
      setOrgError(err?.message || "Unable to send invites");
    } finally {
      setOrgLoading(false);
    }
  };

  useEffect(() => {
    if (!activityJumpCommandId) return;
    const timer = window.setTimeout(() => {
      setActivityJumpCommandId(null);
    }, 20000);
    return () => window.clearTimeout(timer);
  }, [activityJumpCommandId]);

  useEffect(() => {
    if (!chatJumpCommandId) return;
    const timer = window.setTimeout(() => {
      setChatJumpCommandId(null);
    }, 20000);
    return () => window.clearTimeout(timer);
  }, [chatJumpCommandId]);

  // Handle MCP tool execution
  const handleExecuteMcpTool = useCallback(async (
    toolName: string,
    args: Record<string, unknown>,
    serverId?: string | number
  ): Promise<McpExecutionResult> => {
    try {
      const result = await naviClient.executeMcpTool(
        toolName,
        args,
        true,
        serverId !== undefined && serverId !== null ? String(serverId) : undefined
      );
      console.log('MCP Tool Result:', result);
      return result;
    } catch (error) {
      console.error('MCP Tool Error:', error);
      throw error;
    }
  }, []);

  // Handle conversation selection from history
  const handleSelectConversation = useCallback((id: string) => {
    postMessage({ type: "conversation.load", conversationId: id });
    setHistoryOpen(false);
  }, []);

  const openAuthGate = useCallback(() => {
    setFullPanelTab('account');
    setFullPanelOpen(true);
    setHeaderMoreOpen(false);
    setUserMenuOpen(false);
    setHistoryOpen(false);
  }, []);

  const openCommandCenterTab = useCallback((tab: CommandCenterTab) => {
    if (!isAuthenticated && tab !== 'account') {
      setFullPanelTab('account');
    } else {
      setFullPanelTab(tab);
    }
    setFullPanelOpen(true);
    setHeaderMoreOpen(false);
    setUserMenuOpen(false);
  }, [isAuthenticated]);

  // Handle new chat
  const handleNewChat = useCallback(() => {
    if (!isAuthenticated) {
      openAuthGate();
      return;
    }
    postMessage({ type: "conversation.new" });
    setHistoryOpen(false);
  }, [isAuthenticated, openAuthGate]);

  const handleOpenChatSettings = useCallback(() => {
    if (!isAuthenticated) {
      openAuthGate();
      return;
    }
    setChatSettingsTrigger((prev) => prev + 1);
    setHeaderMoreOpen(false);
    setUserMenuOpen(false);
    setHistoryOpen(false);
  }, [isAuthenticated, openAuthGate]);

  // Toggle theme
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    document.documentElement.classList.toggle('light', newTheme === 'light');
  };

  // Fetch MCP tools when panel opens
  const fetchMcpTools = useCallback(async () => {
    setMcpLoading(true);
    setMcpError(null);
    try {
      const response = await naviClient.listMcpTools();
      const fetchedTools = response.tools as unknown as McpTool[];
      const fetchedServers = response.servers as McpServer[] | undefined;
      setMcpTools(fetchedTools);
      if (fetchedServers) {
        setMcpServers(fetchedServers);
        setMcpServerFilter((prev) =>
          prev === 'all' || fetchedServers.some((s) => String(s.id) === String(prev))
            ? prev
            : 'all'
        );
      }
      if (fetchedTools.length > 0) {
        const firstCategory = fetchedTools[0].metadata.category;
        setExpandedMcpCategories({ [firstCategory]: true });
      }
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : 'Failed to load MCP tools');
    } finally {
      setMcpLoading(false);
    }
  }, []);

  useEffect(() => {
    if (fullPanelOpen && fullPanelTab === 'mcp') {
      fetchMcpTools();
    }
  }, [fullPanelOpen, fullPanelTab, fetchMcpTools]);

  // MCP Tool handlers
  const handleSelectMcpTool = (tool: McpTool) => {
    setSelectedMcpTool(tool);
    setMcpResult(null);
    const initialArgs: Record<string, unknown> = {};
    Object.entries(tool.inputSchema.properties).forEach(([key, prop]) => {
      if (prop.default !== undefined) {
        initialArgs[key] = prop.default;
      }
    });
    setMcpToolArgs(initialArgs);
  };

  const handleMcpArgChange = (key: string, value: unknown) => {
    setMcpToolArgs(prev => ({ ...prev, [key]: value }));
  };

  const handleExecuteMcpToolInPanel = async () => {
    if (!selectedMcpTool) return;
    setMcpExecuting(true);
    setMcpResult(null);
    try {
      const result = await naviClient.executeMcpTool(
        selectedMcpTool.name,
        mcpToolArgs,
        true,
        selectedMcpTool.metadata.server_id !== undefined && selectedMcpTool.metadata.server_id !== null
          ? String(selectedMcpTool.metadata.server_id)
          : undefined
      );
      setMcpResult(result);
    } catch (err) {
      setMcpResult({
        success: false,
        data: null,
        error: err instanceof Error ? err.message : 'Execution failed',
        metadata: {},
      });
    } finally {
      setMcpExecuting(false);
    }
  };

  const copyMcpResult = () => {
    if (mcpResult) {
      navigator.clipboard.writeText(JSON.stringify(mcpResult.data, null, 2));
    }
  };

  const toggleMcpCategory = (category: string) => {
    setExpandedMcpCategories(prev => ({ ...prev, [category]: !prev[category] }));
  };

  // Connector handlers
  const handleConnectorOAuth = (connectorId: string) => {
    // In real implementation, this would start OAuth flow
    postMessage({ type: 'connector.oauth', connectorId });
    // For demo, simulate connection
    setTimeout(() => {
      setConnectors(prev => prev.map(c =>
        c.id === connectorId ? { ...c, status: 'connected', lastSync: new Date().toISOString() } : c
      ));
    }, 1500);
  };

  const handleConnectorDisconnect = (connectorId: string) => {
    setConnectors(prev => prev.map(c =>
      c.id === connectorId ? { ...c, status: 'disconnected', lastSync: undefined } : c
    ));
  };

  const handleConnectorApiKey = (connectorId: string) => {
    const config = connectorConfig;
    // Save API key
    postMessage({ type: 'connector.apiKey', connectorId, config });
    setConnectors(prev => prev.map(c =>
      c.id === connectorId ? { ...c, status: 'connected', lastSync: new Date().toISOString() } : c
    ));
    setConfiguringConnector(null);
    setConnectorConfig({});
  };

  // Rule handlers
  const toggleRule = (ruleId: string) => {
    setNaviRules(prev => prev.map(r =>
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
    ));
  };

  // Preference handler
  const handlePreferenceChange = (key: keyof UserPreferences, value: unknown) => {
    setPreferences(prev => ({ ...prev, [key]: value }));
  };

  // Get category config for MCP tools
  const mcpCategoryConfig: Record<string, { label: string; icon: React.ReactNode; description: string }> = {
    git_operations: { label: 'Git Operations', icon: <GitBranch className="h-5 w-5" />, description: 'Branch, merge, rebase, stash' },
    database_operations: { label: 'Database', icon: <Database className="h-5 w-5" />, description: 'Schema, migrations, queries' },
    code_debugging: { label: 'Debugging', icon: <Bug className="h-5 w-5" />, description: 'Error analysis, performance' },
    file_operations: { label: 'File Operations', icon: <FileText className="h-5 w-5" />, description: 'Read, write, search files' },
    test_execution: { label: 'Testing', icon: <TestTube className="h-5 w-5" />, description: 'Run tests, coverage' },
    code_analysis: { label: 'Analysis', icon: <BarChart3 className="h-5 w-5" />, description: 'Complexity, dependencies' },
    external: { label: 'External Tools', icon: <Server className="h-5 w-5" />, description: 'Tools from connected MCP servers' },
    builtin: { label: 'Builtin Tools', icon: <Settings className="h-5 w-5" />, description: 'NAVI built-in MCP tools' },
  };

  // Filter MCP tools by search + server
  const filteredMcpTools = mcpTools.filter((tool) => {
    const matchesSearch =
      tool.name.toLowerCase().includes(mcpSearchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(mcpSearchQuery.toLowerCase());
    const toolServerId = String(tool.metadata.server_id ?? 'builtin');
    const matchesServer = mcpServerFilter === 'all' || toolServerId === mcpServerFilter;
    return matchesSearch && matchesServer;
  });

  const mcpToolsByCategory = filteredMcpTools.reduce((acc, tool) => {
    const category = tool.metadata.category;
    if (!acc[category]) acc[category] = [];
    acc[category].push(tool);
    return acc;
  }, {} as Record<string, McpTool[]>);

  // Get user initials
  const getInitials = (name?: string, email?: string): string => {
    const resolvedName = resolveUserName({ name, email });
    if (resolvedName) {
      const parts = resolvedName
        .trim()
        .split(/\s+/)
        .filter(Boolean);
      if (parts.length === 1) {
        return (parts[0][0] || "N").toUpperCase();
      }
      const first = parts[0][0] || '';
      const last = parts[parts.length - 1][0] || '';
      const initials = `${first}${last}`.toUpperCase();
      return initials || "NU";
    }
    return "NU";
  };

  return (
    <div className="aep-webview-container bg-background text-foreground">
      <div className="flex h-full flex-col">
        {/* Advanced Unified Header */}
        <header className="navi-unified-header">
          <div className="navi-header-container">
            {/* Left Section: Sidebar Toggle + Logo */}
            <div className="navi-header-left">
              {/* Sidebar Toggle - Enhanced visibility */}
              <button
                className="navi-sidebar-toggle-btn"
                title={sidebarCollapsed ? "Open sidebar (Tools, Connectors, Account)" : "Close sidebar"}
                onClick={() => setSidebarCollapsed((prev) => !prev)}
              >
                <span className="navi-sidebar-toggle-bg" />
                <span className="navi-sidebar-toggle-icon">
                  {sidebarCollapsed ? (
                    <ChevronRight className="h-4 w-4" />
                  ) : (
                    <ChevronLeft className="h-4 w-4" />
                  )}
                </span>
                {sidebarCollapsed && <span className="navi-sidebar-toggle-hint">Menu</span>}
              </button>

              {/* Logo with Animated Glow */}
              <div className="navi-header-brand">
                <div className="navi-logo-container">
                  <div className="navi-logo-glow" />
                  <div className="navi-logo-icon">
                    <Zap className="h-5 w-5" />
                  </div>
                </div>
                <div className="navi-brand-text">
                  <span className="navi-brand-name">NAVI</span>
                  <span className="navi-brand-tagline">Autonomous Intelligence</span>
                </div>
              </div>

            </div>

            {/* Center Section: Reserved for future use */}
            <div className="navi-header-center">
              {/* Status indicator removed - cleaner UI */}
            </div>

            {/* Right Section: Actions + User */}
            <div className="navi-header-right">
              {/* New Chat Button - Animated Icon Only */}
              <button
                className="navi-icon-btn navi-icon-btn--lg navi-header-icon-btn navi-animated-icon navi-new-chat-btn"
                title={isAuthenticated ? "Start New Chat" : "Sign in required"}
                onClick={handleNewChat}
                disabled={!isAuthenticated}
              >
                <span className="navi-icon-glow" />
                <PenSquare className="h-4 w-4 navi-new-chat-icon" />
              </button>

              {/* History Button - Animated rewind effect */}
              <button
                className="navi-icon-btn navi-icon-btn--lg navi-header-icon-btn navi-animated-icon navi-history-btn"
                title={isAuthenticated ? "Chat History" : "Sign in required"}
                onClick={() => {
                  if (!isAuthenticated) {
                    openAuthGate();
                    return;
                  }
                  setHistoryOpen(true);
                }}
                disabled={!isAuthenticated}
              >
                <span className="navi-icon-glow" />
                <Clock className="h-4 w-4 navi-history-icon" />
              </button>

              <button
                className="navi-icon-btn navi-icon-btn--lg navi-header-icon-btn navi-animated-icon navi-settings-btn"
                title={isAuthenticated ? "Chat Settings" : "Sign in required"}
                onClick={handleOpenChatSettings}
                disabled={!isAuthenticated}
              >
                <span className="navi-icon-glow" />
                <Settings className="h-4 w-4 navi-settings-icon" />
              </button>

              <button
                className={`navi-icon-btn navi-icon-btn--lg navi-header-icon-btn navi-animated-icon navi-activity-btn ${activityPanelOpen ? 'is-active' : ''}`}
                title={isAuthenticated ? "Activity" : "Sign in required"}
                onClick={() => {
                  if (!isAuthenticated) {
                    openAuthGate();
                    return;
                  }
                  setActivityPanelOpen((prev) => !prev);
                }}
                disabled={!isAuthenticated}
              >
                <span className="navi-icon-glow" />
                <Activity className="h-4 w-4 navi-activity-icon" />
              </button>

              {/* More Menu - Notifications, Theme, Activity, Help */}
              <div className="navi-header-more-anchor">
                <button
                  className="navi-icon-btn navi-icon-btn--lg navi-header-icon-btn navi-animated-icon navi-more-btn"
                  title="More"
                  aria-expanded={headerMoreOpen}
                  aria-controls="navi-more-menu"
                  onClick={() => {
                    setHeaderMoreOpen((prev) => !prev);
                    if (userMenuOpen) {
                      setUserMenuOpen(false);
                    }
                  }}
                >
                  <span className="navi-icon-glow" />
                  <MoreHorizontal className="h-4 w-4 navi-more-icon" />
                </button>

                {headerMoreOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setHeaderMoreOpen(false)}
                    />
                    <div id="navi-more-menu" role="menu" className="navi-header-more-dropdown">
                      <button
                        className="navi-header-more-menu-item"
                        onClick={() => {
                          openCommandCenterTab('mcp');
                        }}
                      >
                        <Layers className="h-4 w-4" />
                        <span>Open Command Center</span>
                      </button>
                      <div className="navi-header-more-divider" />
                      <button
                        className="navi-header-more-menu-item"
                        onClick={() => {
                          toggleTheme();
                          setHeaderMoreOpen(false);
                        }}
                      >
                        {theme === 'dark' ? (
                          <Sun className="h-4 w-4" />
                        ) : (
                          <Moon className="h-4 w-4" />
                        )}
                        <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
                      </button>
                      {isAuthenticated ? (
                        <>
                          <div className="navi-header-more-divider" />
                          <button
                            className="navi-header-more-menu-item"
                            onClick={() => {
                              setAccountTab('preferences');
                              openCommandCenterTab('account');
                            }}
                          >
                            <User className="h-4 w-4" />
                            <span>Account</span>
                          </button>
                          <button
                            className="navi-header-more-menu-item"
                            onClick={() => {
                              handleOpenChatSettings();
                            }}
                          >
                            <Settings className="h-4 w-4" />
                            <span>Chat Settings</span>
                          </button>
                          <button
                            className="navi-header-more-menu-item"
                            onClick={() => {
                              setAccountTab('profile');
                              openCommandCenterTab('account');
                            }}
                          >
                            <User className="h-4 w-4" />
                            <span>Profile</span>
                          </button>
                          <button
                            className="navi-header-more-menu-item navi-header-more-menu-item--danger"
                            onClick={() => {
                              handleSignOut();
                              setHeaderMoreOpen(false);
                            }}
                          >
                            <LogOut className="h-4 w-4" />
                            <span>Sign out</span>
                          </button>
                          <div className="navi-header-more-divider" />
                        </>
                      ) : (
                        <>
                          <button
                            className="navi-header-more-menu-item"
                            onClick={() => {
                              handleSignIn();
                              setHeaderMoreOpen(false);
                            }}
                          >
                            <LogIn className="h-4 w-4" />
                            <span>Sign in</span>
                          </button>
                          <div className="navi-header-more-divider" />
                        </>
                      )}
                      <button
                        className="navi-header-more-menu-item"
                        onClick={() => {
                          setHeaderMoreOpen(false);
                          postMessage({ type: "help.open" });
                          postMessage({ type: "openExternal", url: "https://docs.navra.ai" });
                        }}
                      >
                        <HelpCircle className="h-4 w-4" />
                        <span>Help & Documentation</span>
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* User Status / Sign In */}
              {isAuthenticated ? null : null}
            </div>
          </div>
        </header>

        {orgOnboardingOpen && (
          <div className="navi-org-gate">
            <div className="navi-org-card">
              <div className="navi-org-card__header">
                <div>
                  <div className="navi-org-card__title">Set up your organization</div>
                  <div className="navi-org-card__subtitle">
                    Create or join a workspace for team collaboration.
                  </div>
                </div>
                <button
                  className="navi-org-card__dismiss"
                  onClick={() => setOrgOnboardingOpen(false)}
                >
                  Later
                </button>
              </div>

              {orgs.length > 0 && (
                <div className="navi-org-card__section">
                  <div className="navi-org-card__label">Select an existing org</div>
                  <div className="navi-org-card__orgs">
                    {orgs.map((org) => (
                      <button
                        key={org.id}
                        className={`navi-org-card__org ${selectedOrgId === org.id ? "is-active" : ""}`}
                        onClick={() => void selectOrg(org.id)}
                      >
                        <div className="navi-org-card__org-name">{org.name}</div>
                        <div className="navi-org-card__org-meta">{org.slug}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="navi-org-card__section">
                <div className="navi-org-card__label">Create a new org</div>
                <div className="navi-org-card__inputs">
                  <input
                    className="navi-org-card__input"
                    placeholder="Organization name"
                    value={orgName}
                    onChange={(event) => setOrgName(event.target.value)}
                  />
                  <input
                    className="navi-org-card__input"
                    placeholder="Slug (optional)"
                    value={orgSlug}
                    onChange={(event) => setOrgSlug(event.target.value)}
                  />
                  <button className="navi-org-card__primary" onClick={() => void createOrg()}>
                    Create org
                  </button>
                </div>
              </div>

              <div className="navi-org-card__section">
                <div className="navi-org-card__label">Invite teammates</div>
                <textarea
                  className="navi-org-card__textarea"
                  rows={3}
                  placeholder="emails, separated by commas"
                  value={inviteEmails}
                  onChange={(event) => setInviteEmails(event.target.value)}
                />
                <div className="navi-org-card__invite-row">
                  <select
                    className="navi-org-card__select"
                    value={inviteRole}
                    onChange={(event) => setInviteRole(event.target.value)}
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button className="navi-org-card__secondary" onClick={() => void sendInvites()}>
                    Send invites
                  </button>
                </div>
              </div>

              {orgError && <div className="navi-org-card__error">{orgError}</div>}
              {orgLoading && <div className="navi-org-card__loading">Working…</div>}
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
          {isAuthenticated ? (
            <>
              {/* Left Sidebar */}
              <aside
                className={`navi-sidebar transition-all duration-300 ease-in-out ${sidebarCollapsed ? "w-0 overflow-hidden" : "w-72"
                  }`}
              >
                {!sidebarCollapsed && (
                  <SidebarPanel
                    isAuthenticated={isAuthenticated}
                    user={user}
                    onSignIn={handleSignIn}
                    onSignUp={handleSignUp}
                    onSignOut={handleSignOut}
                    onExecuteMcpTool={handleExecuteMcpTool}
                    onOpenFullPanel={() => setFullPanelOpen(true)}
                    externalPanelRequest={externalPanelRequest}
                    onClearExternalPanelRequest={() => setExternalPanelRequest(null)}
                  />
                )}
              </aside>

              {/* Main Chat Area */}
              <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
                  <NaviChatPanel
                    activityPanelState={activityPanelState}
                    onOpenActivityForCommand={handleOpenActivityForCommand}
                    highlightCommandId={chatJumpCommandId}
                    openSettingsTrigger={chatSettingsTrigger}
                  />

                  {/* Activity Panel - Right Sidebar */}
                  {activityPanelOpen && isAuthenticated && (
                    <aside className="navi-activity-sidebar">
                      <ActivityPanel
                        steps={activityPanelState.steps}
                        currentStep={activityPanelState.currentStep}
                        highlightCommandId={activityJumpCommandId}
                        onViewInChat={handleViewCommandInChat}
                        onFileClick={(filePath) => {
                          postMessage({ type: 'openFile', filePath });
                        }}
                        onViewHistory={() => setHistoryOpen(true)}
                        onAcceptAll={() => {
                          // TODO: wire up bulk accept flow
                        }}
                        onRejectAll={() => {
                          // TODO: wire up bulk reject flow
                        }}
                      />
                      <button
                        className="navi-icon-btn navi-icon-btn--sm navi-activity-close"
                        onClick={() => setActivityPanelOpen(false)}
                        title="Close Activity Panel"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </aside>
                  )}
                </div>
              </main>
            </>
          ) : (
            <main className="navi-auth-wall" aria-label="Authentication required">
              <div className="navi-auth-wall__layout">
                <div className="navi-auth-wall__entry">
                  <PremiumAuthEntry
                    onSignIn={handleSignIn}
                    onSignUp={handleSignUp}
                    title="Sign in to unlock the NAVI workspace"
                    subtitle="Chat, MCP tools, integrations, and rules are available only after authentication."
                    signInStatus={authSignInStatus}
                  />
                </div>
              </div>
            </main>
          )}
        </div>
      </div>

      {/* History Panel Overlay */}
      <HistoryPanel
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
      />

      {/* Full Command Center Panel Overlay */}
      {fullPanelOpen && (
        <div className="navi-full-panel-overlay" onClick={() => setFullPanelOpen(false)}>
          <div className="navi-full-panel navi-full-panel--large" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="navi-full-panel__header">
              <div className="navi-full-panel__header-left">
                <div className="navi-full-panel__logo">
                  <Zap className="h-5 w-5" />
                </div>
                <div className="navi-full-panel__title">
                  <h2>Command Center</h2>
                  <span>AI Workspace Configuration</span>
                </div>
              </div>
              <button
                className="navi-icon-btn navi-icon-btn--sm navi-full-panel__close"
                onClick={() => setFullPanelOpen(false)}
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Tabs */}
            <div className="navi-full-panel__tabs">
              <button
                className={`navi-full-panel__tab ${fullPanelTab === 'mcp' ? 'is-active' : ''}`}
                onClick={() => setFullPanelTab('mcp')}
                disabled={!isAuthenticated}
                title={!isAuthenticated ? "Sign in required" : "MCP Tools"}
              >
                <Settings className="h-4 w-4" />
                MCP Tools
              </button>
              <button
                className={`navi-full-panel__tab ${fullPanelTab === 'integrations' ? 'is-active' : ''}`}
                onClick={() => setFullPanelTab('integrations')}
                disabled={!isAuthenticated}
                title={!isAuthenticated ? "Sign in required" : "Integrations"}
              >
                <Link className="h-4 w-4" />
                Integrations
              </button>
              <button
                className={`navi-full-panel__tab ${fullPanelTab === 'rules' ? 'is-active' : ''}`}
                onClick={() => setFullPanelTab('rules')}
                disabled={!isAuthenticated}
                title={!isAuthenticated ? "Sign in required" : "NAVI Rules"}
              >
                <Shield className="h-4 w-4" />
                NAVI Rules
              </button>
              <button
                className={`navi-full-panel__tab ${fullPanelTab === 'account' ? 'is-active' : ''}`}
                onClick={() => setFullPanelTab('account')}
              >
                <User className="h-4 w-4" />
                Account
              </button>
            </div>

            {/* Content */}
            <div className="navi-full-panel__content">
              {/* MCP Tools Tab */}
              {fullPanelTab === 'mcp' && (
                <div className="navi-cc-mcp">
                  <div className="navi-cc-mcp__header">
                    <div>
                      <h3>Model Context Protocol Tools</h3>
                      <p>Available tools for AI-powered operations • {mcpTools.length} tools</p>
                    </div>
                    <div className="navi-cc-mcp__controls">
                      <div className="navi-cc-mcp__server">
                        <Server className="h-4 w-4" />
                        <select
                          value={mcpServerFilter}
                          onChange={(e) => setMcpServerFilter(e.target.value)}
                        >
                          <option value="all">All servers</option>
                          {mcpServers.map((server) => (
                            <option key={String(server.id)} value={String(server.id)}>
                              {server.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="navi-cc-mcp__search">
                        <input
                          type="text"
                          placeholder="Search tools..."
                          value={mcpSearchQuery}
                          onChange={(e) => setMcpSearchQuery(e.target.value)}
                        />
                      </div>
                      {canManageMcpServers && (
                        <button
                          className="navi-cc-mcp__manage"
                          onClick={() => {
                            setFullPanelOpen(false);
                            setSidebarCollapsed(false);
                            setExternalPanelRequest('mcp');
                          }}
                        >
                          Manage Servers
                        </button>
                      )}
                    </div>
                  </div>

                  {mcpLoading && (
                    <div className="navi-cc-loading">
                      <RefreshCw className="h-6 w-6 animate-spin" />
                      <span>Loading tools...</span>
                    </div>
                  )}

                  {mcpError && (
                    <div className="navi-cc-error">
                      <AlertCircle className="h-5 w-5" />
                      <p>{mcpError}</p>
                      <button onClick={fetchMcpTools}>Retry</button>
                    </div>
                  )}

                  {!mcpLoading && !mcpError && (
                    <div className="navi-cc-mcp__body">
                      {/* Categories */}
                      <div className="navi-cc-mcp__categories">
                        {Object.entries(mcpToolsByCategory).map(([category, categoryTools]) => {
                          const config = mcpCategoryConfig[category] || { label: category, icon: <Settings className="h-5 w-5" />, description: '' };
                          const isExpanded = expandedMcpCategories[category];

                          return (
                            <div key={category} className={`navi-cc-category ${isExpanded ? 'is-expanded' : ''}`}>
                              <button className="navi-cc-category__header" onClick={() => toggleMcpCategory(category)}>
                                <div className="navi-cc-category__icon">{config.icon}</div>
                                <div className="navi-cc-category__info">
                                  <span className="navi-cc-category__name">{config.label}</span>
                                  <span className="navi-cc-category__desc">{config.description}</span>
                                </div>
                                <span className="navi-cc-category__count">{categoryTools.length}</span>
                                <ChevronRight className={`h-4 w-4 navi-cc-category__chevron ${isExpanded ? 'rotate-90' : ''}`} />
                              </button>

                              {isExpanded && (
                                <div className="navi-cc-category__tools">
                                  {categoryTools.map((tool) => (
                                    <button
                                      key={tool.name}
                                      className={`navi-cc-tool ${selectedMcpTool?.name === tool.name ? 'is-selected' : ''}`}
                                      onClick={() => handleSelectMcpTool(tool)}
                                    >
                                      <div className="navi-cc-tool__info">
                                        <span className="navi-cc-tool__name">
                                          {tool.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                                        </span>
                                        <span className="navi-cc-tool__server">
                                          {tool.metadata.server_name ||
                                            (tool.metadata.source === 'external' ? 'External' : 'Builtin')}
                                        </span>
                                      </div>
                                      {tool.metadata.requires_approval && (
                                        <span className="navi-cc-tool__badge">Approval</span>
                                      )}
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}

                        {Object.keys(mcpToolsByCategory).length === 0 && mcpTools.length === 0 && (
                          <div className="navi-cc-empty">
                            <Settings className="h-8 w-8" />
                            <p>No MCP tools available</p>
                            <span>Configure MCP servers to add tools</span>
                          </div>
                        )}
                      </div>

                      {/* Selected Tool Detail */}
                      {selectedMcpTool && (
                        <div className="navi-cc-mcp__detail">
                          <div className="navi-cc-detail__header">
                            <div className="navi-cc-detail__title">
                              <h4>{selectedMcpTool.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}</h4>
                              <span className="navi-cc-detail__server">
                                {selectedMcpTool.metadata.server_name ||
                                  (selectedMcpTool.metadata.source === 'external' ? 'External' : 'Builtin')}
                              </span>
                            </div>
                            {selectedMcpTool.metadata.requires_approval && (
                              <span className="navi-cc-detail__badge">
                                <Shield className="h-3 w-3" /> Requires Approval
                              </span>
                            )}
                          </div>
                          <p className="navi-cc-detail__desc">{selectedMcpTool.description}</p>

                          {/* Parameters */}
                          <div className="navi-cc-params">
                            <h5>Parameters</h5>
                            {Object.entries(selectedMcpTool.inputSchema.properties).map(([key, prop]) => (
                              <div key={key} className="navi-cc-param">
                                <label>
                                  {key}
                                  {selectedMcpTool.inputSchema.required.includes(key) && <span className="required">*</span>}
                                </label>
                                {prop.enum ? (
                                  <select
                                    value={String(mcpToolArgs[key] || '')}
                                    onChange={(e) => handleMcpArgChange(key, e.target.value)}
                                  >
                                    <option value="">Select...</option>
                                    {prop.enum.map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                ) : prop.type === 'boolean' ? (
                                  <label className="navi-cc-checkbox">
                                    <input
                                      type="checkbox"
                                      checked={Boolean(mcpToolArgs[key])}
                                      onChange={(e) => handleMcpArgChange(key, e.target.checked)}
                                    />
                                    <span>{prop.description || 'Enable'}</span>
                                  </label>
                                ) : (
                                  <input
                                    type="text"
                                    placeholder={prop.description || key}
                                    value={String(mcpToolArgs[key] || '')}
                                    onChange={(e) => handleMcpArgChange(key, e.target.value)}
                                  />
                                )}
                              </div>
                            ))}
                          </div>

                          {/* Execute Button */}
                          <button
                            className="navi-cc-execute"
                            onClick={handleExecuteMcpToolInPanel}
                            disabled={mcpExecuting}
                          >
                            {mcpExecuting ? (
                              <>
                                <RefreshCw className="h-4 w-4 animate-spin" />
                                Executing...
                              </>
                            ) : (
                              <>
                                <Play className="h-4 w-4" />
                                Execute Tool
                              </>
                            )}
                          </button>

                          {/* Result */}
                          {mcpResult && (
                            <div className={`navi-cc-result ${mcpResult.success ? 'is-success' : 'is-error'}`}>
                              <div className="navi-cc-result__header">
                                {mcpResult.success ? (
                                  <><CheckCircle className="h-4 w-4" /> Success</>
                                ) : (
                                  <><AlertCircle className="h-4 w-4" /> Error</>
                                )}
                                <button onClick={copyMcpResult} title="Copy result">
                                  <Copy className="h-4 w-4" />
                                </button>
                              </div>
                              <pre>{JSON.stringify(mcpResult.success ? mcpResult.data : mcpResult.error, null, 2)}</pre>
                            </div>
                          )}
                        </div>
                      )}

                      {!selectedMcpTool && mcpTools.length > 0 && (
                        <div className="navi-cc-mcp__placeholder">
                          <Settings className="h-10 w-10" />
                          <h4>Select a Tool</h4>
                          <p>Choose a tool from the categories on the left to view details and execute</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Integrations Tab */}
              {fullPanelTab === 'integrations' && (
                <div className="navi-cc-integrations">
                  <div className="navi-cc-integrations__header">
                    <h3>Integration Marketplace</h3>
                    <p>Connect 280+ tools and services to enhance NAVI's capabilities</p>
                  </div>

                  {/* Search and Filter Bar */}
                  <div className="navi-cc-integrations__toolbar">
                    <div className="navi-cc-integrations__search">
                      <Search className="h-4 w-4" />
                      <input
                        type="text"
                        placeholder="Search integrations..."
                        value={connectorSearchQuery}
                        onChange={(e) => setConnectorSearchQuery(e.target.value)}
                      />
                      {connectorSearchQuery && (
                        <button
                          className="navi-cc-integrations__search-clear"
                          onClick={() => setConnectorSearchQuery('')}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Category Tabs */}
                  <div className="navi-cc-integrations__categories">
                    <button
                      className={`navi-cc-integrations__category ${selectedConnectorCategory === 'popular' ? 'is-active' : ''}`}
                      onClick={() => setSelectedConnectorCategory('popular')}
                    >
                      <Star className="h-4 w-4" />
                      Popular
                    </button>
                    <button
                      className={`navi-cc-integrations__category ${selectedConnectorCategory === 'all' ? 'is-active' : ''}`}
                      onClick={() => setSelectedConnectorCategory('all')}
                    >
                      <Grid className="h-4 w-4" />
                      All
                    </button>
                    {CONNECTOR_CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        className={`navi-cc-integrations__category ${selectedConnectorCategory === cat.id ? 'is-active' : ''}`}
                        onClick={() => setSelectedConnectorCategory(cat.id)}
                        title={cat.label}
                      >
                        {cat.icon}
                        <span>{cat.label}</span>
                      </button>
                    ))}
                  </div>

                  {/* Results Count */}
                  <div className="navi-cc-integrations__results-count">
                    {(() => {
                      const filtered = connectors.filter(c => {
                        const matchesSearch = !connectorSearchQuery ||
                          c.name.toLowerCase().includes(connectorSearchQuery.toLowerCase()) ||
                          c.description.toLowerCase().includes(connectorSearchQuery.toLowerCase());
                        const matchesCategory = selectedConnectorCategory === 'all' ||
                          (selectedConnectorCategory === 'popular' && c.popular) ||
                          c.category === selectedConnectorCategory;
                        return matchesSearch && matchesCategory;
                      });
                      return `${filtered.length} integration${filtered.length !== 1 ? 's' : ''} ${connectorSearchQuery ? `matching "${connectorSearchQuery}"` : ''}`;
                    })()}
                  </div>

                  <div className="navi-cc-integrations__grid">
                    {connectors
                      .filter(connector => {
                        const matchesSearch = !connectorSearchQuery ||
                          connector.name.toLowerCase().includes(connectorSearchQuery.toLowerCase()) ||
                          connector.description.toLowerCase().includes(connectorSearchQuery.toLowerCase());
                        const matchesCategory = selectedConnectorCategory === 'all' ||
                          (selectedConnectorCategory === 'popular' && connector.popular) ||
                          connector.category === selectedConnectorCategory;
                        return matchesSearch && matchesCategory;
                      })
                      .map((connector) => (
                        <div key={connector.id} className={`navi-cc-connector ${connector.status === 'connected' ? 'is-connected' : ''}`}>
                          <div className="navi-cc-connector__header">
                            <div className="navi-cc-connector__icon">
                              {connector.logoUrl ? (
                                <img
                                  src={connector.logoUrl}
                                  alt={`${connector.name} logo`}
                                  onError={(e) => {
                                    // Fallback to icon if logo fails to load
                                    e.currentTarget.style.display = 'none';
                                    e.currentTarget.nextElementSibling?.classList.remove('hidden');
                                  }}
                                />
                              ) : null}
                              <span className={`navi-cc-connector__icon-fallback ${connector.logoUrl ? 'hidden' : ''}`}>
                                {connector.icon}
                              </span>
                            </div>
                            <div className="navi-cc-connector__info">
                              <h4>{connector.name}</h4>
                              <p>{connector.description}</p>
                              <span className="navi-cc-connector__category-tag">
                                {CONNECTOR_CATEGORIES.find(c => c.id === connector.category)?.label || connector.category}
                              </span>
                            </div>
                            <div className={`navi-cc-connector__status ${connector.status}`}>
                              {connector.status === 'connected' ? (
                                <><CheckCircle className="h-4 w-4" /> Connected</>
                              ) : connector.status === 'error' ? (
                                <><AlertCircle className="h-4 w-4" /> Error</>
                              ) : (
                                <><Unlink className="h-4 w-4" /> Disconnected</>
                              )}
                            </div>
                          </div>

                          <div className="navi-cc-connector__body">
                            {connector.status === 'connected' ? (
                              <>
                                {connector.lastSync && (
                                  <span className="navi-cc-connector__sync">
                                    Last synced: {new Date(connector.lastSync).toLocaleString()}
                                  </span>
                                )}
                                <button
                                  className="navi-cc-connector__btn navi-cc-connector__btn--disconnect"
                                  onClick={() => handleConnectorDisconnect(connector.id)}
                                >
                                  <Unlink className="h-4 w-4" />
                                  Disconnect
                                </button>
                              </>
                            ) : configuringConnector === connector.id ? (
                              <div className="navi-cc-connector__config">
                                {connector.configFields?.map((field) => (
                                  <div key={field.key} className="navi-cc-connector__field">
                                    <label>{field.label}</label>
                                    <input
                                      type={field.type}
                                      placeholder={field.placeholder}
                                      value={connectorConfig[field.key] || ''}
                                      onChange={(e) => setConnectorConfig(prev => ({ ...prev, [field.key]: e.target.value }))}
                                    />
                                  </div>
                                ))}
                                <div className="navi-cc-connector__actions">
                                  <button
                                    className="navi-cc-connector__btn"
                                    onClick={() => handleConnectorApiKey(connector.id)}
                                  >
                                    <Check className="h-4 w-4" /> Save
                                  </button>
                                  <button
                                    className="navi-cc-connector__btn navi-cc-connector__btn--cancel"
                                    onClick={() => {
                                      setConfiguringConnector(null);
                                      setConnectorConfig({});
                                    }}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <button
                                className="navi-cc-connector__btn navi-cc-connector__btn--connect"
                                onClick={() => {
                                  if (connector.authType === 'api_key') {
                                    setConfiguringConnector(connector.id);
                                  } else {
                                    handleConnectorOAuth(connector.id);
                                  }
                                }}
                              >
                                {connector.authType === 'oauth' ? (
                                  <><ExternalLink className="h-4 w-4" /> Connect with OAuth</>
                                ) : (
                                  <><Key className="h-4 w-4" /> Configure API Key</>
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>

                  {/* Empty state */}
                  {connectors.filter(c => {
                    const matchesSearch = !connectorSearchQuery ||
                      c.name.toLowerCase().includes(connectorSearchQuery.toLowerCase()) ||
                      c.description.toLowerCase().includes(connectorSearchQuery.toLowerCase());
                    const matchesCategory = selectedConnectorCategory === 'all' ||
                      (selectedConnectorCategory === 'popular' && c.popular) ||
                      c.category === selectedConnectorCategory;
                    return matchesSearch && matchesCategory;
                  }).length === 0 && (
                      <div className="navi-cc-integrations__empty">
                        <Search className="h-12 w-12" />
                        <h4>No integrations found</h4>
                        <p>Try adjusting your search or category filter</p>
                        <button onClick={() => { setConnectorSearchQuery(''); setSelectedConnectorCategory('all'); }}>
                          Clear filters
                        </button>
                      </div>
                    )}
                </div>
              )}

              {/* NAVI Rules Tab */}
              {fullPanelTab === 'rules' && (
                <div className="navi-cc-rules">
                  <div className="navi-cc-rules__header">
                    <h3>NAVI Rules & Standards</h3>
                    <p>Configure AI behavior, auto-approval settings, and coding standards</p>
                  </div>

                  <div className="navi-cc-rules__list">
                    {naviRules.map((rule) => (
                      <div key={rule.id} className={`navi-cc-rule ${rule.enabled ? 'is-enabled' : ''}`}>
                        <div className="navi-cc-rule__info">
                          <div className="navi-cc-rule__icon">
                            {rule.type === 'coding_standard' && <FileText className="h-5 w-5" />}
                            {rule.type === 'auto_approval' && <Check className="h-5 w-5" />}
                            {rule.type === 'response_style' && <Settings className="h-5 w-5" />}
                            {rule.type === 'security' && <Shield className="h-5 w-5" />}
                          </div>
                          <div className="navi-cc-rule__text">
                            <h4>{rule.name}</h4>
                            <p>{rule.description}</p>
                            <span className="navi-cc-rule__type">{rule.type.replace('_', ' ')}</span>
                          </div>
                        </div>
                        <button
                          className={`navi-cc-rule__toggle ${rule.enabled ? 'is-on' : ''}`}
                          onClick={() => toggleRule(rule.id)}
                        >
                          {rule.enabled ? <ToggleRight className="h-6 w-6" /> : <ToggleLeft className="h-6 w-6" />}
                        </button>
                      </div>
                    ))}
                  </div>

                  <div className="navi-cc-rules__add">
                    <button className="navi-cc-rules__add-btn">
                      <Plus className="h-4 w-4" />
                      Add Custom Rule
                    </button>
                  </div>
                </div>
              )}

              {/* Account Tab */}
              {fullPanelTab === 'account' && (
                <div className={`navi-cc-account ${!isAuthenticated ? 'navi-cc-account--unauth' : ''}`}>
                  {!isAuthenticated ? (
                    <div className="navi-cc-account__auth-entry">
                      <PremiumAuthEntry
                        variant="compact"
                        onSignIn={handleSignIn}
                        onSignUp={handleSignUp}
                        title="Enterprise-grade account access"
                        subtitle="Secure browser authorization with scoped access. Tokens stay in VS Code secrets storage."
                        signInStatus={authSignInStatus}
                      />
                    </div>
                  ) : (
                    <>
                      {/* Profile Card */}
                      <div className="navi-cc-account__profile">
                        {user?.picture ? (
                          <img src={user.picture} alt={displayName} className="navi-cc-account__avatar" />
                        ) : (
                          <div className="navi-cc-account__avatar-placeholder">
                            {getInitials(user?.name, user?.email)}
                          </div>
                        )}
                        <div className="navi-cc-account__info">
                          <span className="navi-cc-account__name">{displayName}</span>
                          <span className="navi-cc-account__email">{user?.email || 'Signed in with NAVI Identity'}</span>
                          {user?.org && (
                            <span className="navi-cc-account__org">{user.org} {user.role && `• ${user.role}`}</span>
                          )}
                        </div>
                      </div>

                      {/* Account Tabs */}
                      <div className="navi-cc-account__tabs">
                        <button
                          className={`navi-cc-account__tab ${accountTab === 'profile' ? 'is-active' : ''}`}
                          onClick={() => setAccountTab('profile')}
                        >
                          Profile
                        </button>
                        <button
                          className={`navi-cc-account__tab ${accountTab === 'preferences' ? 'is-active' : ''}`}
                          onClick={() => setAccountTab('preferences')}
                        >
                          Preferences
                        </button>
                        <button
                          className={`navi-cc-account__tab ${accountTab === 'shortcuts' ? 'is-active' : ''}`}
                          onClick={() => setAccountTab('shortcuts')}
                        >
                          Shortcuts
                        </button>
                      </div>

                      {/* Tab Content */}
                      <div className="navi-cc-account__content">
                        {accountTab === 'profile' && (
                          <div className="navi-cc-profile">
                            <div className="navi-cc-profile__details">
                              <div className="navi-cc-profile__detail">
                                <span className="navi-cc-profile__detail-label">Display name</span>
                                <span className="navi-cc-profile__detail-value">{displayName}</span>
                              </div>
                              <div className="navi-cc-profile__detail">
                                <span className="navi-cc-profile__detail-label">Email</span>
                                <span className="navi-cc-profile__detail-value">{user?.email || "Not provided"}</span>
                              </div>
                              <div className="navi-cc-profile__detail">
                                <span className="navi-cc-profile__detail-label">Organization</span>
                                <span className="navi-cc-profile__detail-value">{user?.org || "Not selected"}</span>
                              </div>
                              <div className="navi-cc-profile__detail">
                                <span className="navi-cc-profile__detail-label">Role</span>
                                <span className="navi-cc-profile__detail-value">{user?.role || "Member"}</span>
                              </div>
                            </div>
                            <div className="navi-cc-profile__actions">
                              <button onClick={() => setActivityPanelOpen(true)}><BarChart3 className="h-4 w-4" /> View Activity</button>
                              <button><ExternalLink className="h-4 w-4" /> Export Data</button>
                            </div>
                          </div>
                        )}

                        {accountTab === 'preferences' && (
                          <div className="navi-cc-prefs">
                            <div className="navi-cc-pref">
                              <label>Response Style</label>
                              <div className="navi-cc-pref__options">
                                {(['brief', 'balanced', 'detailed'] as const).map(opt => (
                                  <button
                                    key={opt}
                                    className={preferences.responseVerbosity === opt ? 'is-active' : ''}
                                    onClick={() => handlePreferenceChange('responseVerbosity', opt)}
                                  >
                                    {opt.charAt(0).toUpperCase() + opt.slice(1)}
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div className="navi-cc-pref">
                              <label>Explanation Level</label>
                              <div className="navi-cc-pref__options">
                                {(['beginner', 'intermediate', 'expert'] as const).map(opt => (
                                  <button
                                    key={opt}
                                    className={preferences.explanationLevel === opt ? 'is-active' : ''}
                                    onClick={() => handlePreferenceChange('explanationLevel', opt)}
                                  >
                                    {opt.charAt(0).toUpperCase() + opt.slice(1)}
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div className="navi-cc-pref">
                              <label>Auto-Approve Actions</label>
                              <div className="navi-cc-pref__options">
                                {(['none', 'safe', 'all'] as const).map(opt => (
                                  <button
                                    key={opt}
                                    className={preferences.autoApprove === opt ? 'is-active' : ''}
                                    onClick={() => handlePreferenceChange('autoApprove', opt)}
                                  >
                                    {opt === 'none' ? 'Never' : opt === 'safe' ? 'Safe Only' : 'All'}
                                  </button>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}

                        {accountTab === 'shortcuts' && (
                          <div className="navi-cc-shortcuts">
                            <div className="navi-cc-shortcut">
                              <span className="navi-cc-shortcut__keys"><kbd>⌘</kbd><kbd>K</kbd></span>
                              <span>Quick Command</span>
                            </div>
                            <div className="navi-cc-shortcut">
                              <span className="navi-cc-shortcut__keys"><kbd>⌘</kbd><kbd>Enter</kbd></span>
                              <span>Send Message</span>
                            </div>
                            <div className="navi-cc-shortcut">
                              <span className="navi-cc-shortcut__keys"><kbd>⌘</kbd><kbd>L</kbd></span>
                              <span>Clear Chat</span>
                            </div>
                            <div className="navi-cc-shortcut">
                              <span className="navi-cc-shortcut__keys"><kbd>⌘</kbd><kbd>Shift</kbd><kbd>N</kbd></span>
                              <span>New Chat</span>
                            </div>
                            <div className="navi-cc-shortcut">
                              <span className="navi-cc-shortcut__keys"><kbd>Esc</kbd></span>
                              <span>Cancel Action</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Sign Out */}
                      <button className="navi-cc-account__signout" onClick={handleSignOut}>
                        <LogOut className="h-4 w-4" />
                        Sign Out
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Advanced Header Styles */}
      <style>{`
        /* ===== UNIFIED HEADER ===== */
        .navi-unified-header {
          position: sticky;
          top: 0;
          z-index: 50;
          height: 44px;
          background: linear-gradient(180deg,
            hsl(var(--background)) 0%,
            hsl(var(--background) / 0.98) 100%
          );
          border-bottom: 1px solid hsl(var(--border) / 0.5);
          backdrop-filter: blur(12px);
        }

        .navi-header-container {
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: 100%;
          padding: 0 12px;
          gap: 12px;
        }

        /* ===== LEFT SECTION ===== */
        .navi-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        /* ===== ANIMATED ICON BUTTON ===== */
        .navi-header-icon-btn {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          --icon-btn-size: 30px;
          width: var(--icon-btn-size);
          height: var(--icon-btn-size);
          border-radius: 8px;
          overflow: hidden;
        }

        .navi-animated-icon .navi-icon-glow {
          position: absolute;
          inset: -50%;
          background: radial-gradient(circle at center, hsl(var(--primary) / 0.3), transparent 70%);
          opacity: 0;
          transition: opacity 0.3s ease;
          pointer-events: none;
        }

        .navi-animated-icon:hover .navi-icon-glow {
          opacity: 1;
          animation: iconPulse 1.5s ease-in-out infinite;
        }

        .navi-header-icon-btn:hover svg {
          animation: iconBounce 0.4s ease;
        }

        @keyframes iconBounce {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.15); }
        }

        @keyframes iconPulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 0.6; transform: scale(1.2); }
        }

        /* ===== LOGO ===== */
        .navi-header-brand {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .navi-logo-container {
          position: relative;
          width: 28px;
          height: 28px;
        }

        .navi-logo-glow {
          position: absolute;
          inset: -3px;
          background: radial-gradient(circle, hsl(var(--primary) / 0.4), transparent 70%);
          border-radius: 10px;
          animation: logoGlow 3s ease-in-out infinite;
        }

        @keyframes logoGlow {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50% { opacity: 0.8; transform: scale(1.1); }
        }

        .navi-logo-icon {
          position: relative;
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border-radius: 8px;
          color: hsl(var(--primary-foreground));
          box-shadow: 0 2px 12px hsl(var(--primary) / 0.3);
        }

        .navi-brand-text {
          display: flex;
          flex-direction: column;
        }

        .navi-brand-name {
          font-size: 12px;
          font-weight: 700;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .navi-brand-tagline {
          display: none;
          font-size: 9px;
          color: hsl(var(--muted-foreground));
          letter-spacing: 0.02em;
          line-height: 1.1;
        }

        /* ===== COLLABORATORS BADGE ===== */
        .navi-collab-badge {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px 10px 4px 6px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border) / 0.5);
          border-radius: 20px;
          margin-left: 8px;
        }

        .navi-collab-avatars {
          display: flex;
          align-items: center;
        }

        .navi-collab-avatar {
          width: 22px;
          height: 22px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          font-weight: 600;
          border: 2px solid hsl(var(--background));
        }

        .navi-collab-avatar:not(:first-child) {
          margin-left: -8px;
        }

        .navi-collab-primary {
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          color: white;
          z-index: 2;
        }

        .navi-collab-you {
          background: hsl(var(--secondary));
          color: hsl(var(--foreground));
          z-index: 1;
        }

        .navi-collab-count {
          font-size: 11px;
          color: hsl(var(--muted-foreground));
        }

        /* ===== CENTER SECTION ===== */
        .navi-header-center {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        /* ===== CONNECTION STATUS PILL ===== */
        .navi-connection-pill {
          position: relative;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px 6px 10px;
          border-radius: 20px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border) / 0.5);
          font-size: 12px;
          font-weight: 500;
          cursor: default;
          overflow: hidden;
          transition: all 0.3s ease;
        }

        .navi-connection-pill-glow {
          position: absolute;
          inset: -2px;
          border-radius: 22px;
          opacity: 0;
          transition: opacity 0.3s ease;
          pointer-events: none;
        }

        .navi-connection-pill--connected {
          border-color: hsl(var(--status-success) / 0.4);
          background: linear-gradient(135deg, hsl(var(--status-success) / 0.1), hsl(var(--status-success) / 0.05));
        }

        .navi-connection-pill--connected .navi-connection-pill-glow {
          background: radial-gradient(ellipse at center, hsl(var(--status-success) / 0.15), transparent 70%);
          animation: connectionGlow 3s ease-in-out infinite;
        }

        @keyframes connectionGlow {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.8; }
        }

        .navi-connection-pill--connected:hover .navi-connection-pill-glow {
          opacity: 1;
        }

        .navi-connection-pill-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: hsl(var(--status-success));
          box-shadow: 0 0 8px hsl(var(--status-success) / 0.6);
          animation: dotPulse 2s ease-in-out infinite;
        }

        @keyframes dotPulse {
          0%, 100% { transform: scale(1); box-shadow: 0 0 8px hsl(var(--status-success) / 0.6); }
          50% { transform: scale(1.15); box-shadow: 0 0 12px hsl(var(--status-success) / 0.8); }
        }

        .navi-connection-pill-text {
          color: hsl(var(--status-success));
          font-weight: 600;
          letter-spacing: 0.01em;
        }

        .navi-connection-pill-icon {
          width: 14px;
          height: 14px;
          color: hsl(var(--status-success));
          animation: iconZap 2s ease-in-out infinite;
        }

        @keyframes iconZap {
          0%, 90%, 100% { opacity: 1; transform: scale(1); }
          95% { opacity: 0.7; transform: scale(1.1); }
        }

        /* Disconnected state */
        .navi-connection-pill--disconnected {
          border-color: hsl(var(--destructive) / 0.4);
          background: linear-gradient(135deg, hsl(var(--destructive) / 0.1), hsl(var(--destructive) / 0.05));
        }

        .navi-connection-pill--disconnected .navi-connection-pill-dot {
          background: hsl(var(--destructive));
          box-shadow: 0 0 8px hsl(var(--destructive) / 0.6);
          animation: none;
        }

        .navi-connection-pill--disconnected .navi-connection-pill-text {
          color: hsl(var(--destructive));
        }

        .navi-connection-pill--disconnected .navi-connection-pill-icon {
          color: hsl(var(--destructive));
          animation: none;
        }

        /* ===== RIGHT SECTION ===== */
        .navi-header-right {
          display: flex;
          align-items: center;
          gap: 4px;
          position: relative;
        }

        .navi-header-more-anchor {
          position: static;
        }

        .navi-header-more-dropdown {
          position: absolute;
          right: 0;
          top: calc(100% + 4px);
          width: 220px;
          min-width: 220px;
          max-width: 220px;
          background: hsl(var(--popover));
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          box-shadow: 0 10px 40px hsl(0 0% 0% / 0.3);
          padding: 4px;
          max-height: 260px;
          overflow: hidden;
          z-index: 60;
          box-sizing: border-box;
          writing-mode: horizontal-tb;
          text-orientation: mixed;
          animation: dropdownSlide 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .navi-header-more-menu-item {
          display: flex;
          align-items: center;
          gap: 10px;
          width: 100%;
          min-height: 30px;
          padding: 6px 8px;
          border: none;
          border-radius: 8px;
          background: transparent;
          color: hsl(var(--foreground));
          font-size: 11.5px;
          cursor: pointer;
          text-align: left;
          transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
          white-space: nowrap;
          writing-mode: horizontal-tb;
          text-orientation: mixed;
        }

        .navi-header-more-menu-item:hover {
          background: hsl(var(--secondary) / 0.55);
          transform: translateY(-1px);
          box-shadow: 0 6px 12px hsl(var(--primary) / 0.12);
        }

        .navi-header-more-menu-item svg {
          color: hsl(var(--muted-foreground));
        }

        .navi-header-more-menu-item--danger {
          color: hsl(var(--destructive));
        }

        .navi-header-more-menu-item--danger svg {
          color: hsl(var(--destructive));
        }

        .navi-header-more-menu-item--danger:hover {
          background: hsl(var(--destructive) / 0.12);
          box-shadow: none;
        }

        .navi-header-more-menu-item__meta {
          margin-left: auto;
          min-width: 18px;
          height: 18px;
          padding: 0 6px;
          border-radius: 999px;
          background: hsl(var(--destructive));
          color: white;
          font-size: 10px;
          font-weight: 700;
          display: inline-flex;
          align-items: center;
          justify-content: center;
        }

        .navi-header-more-divider {
          height: 1px;
          background: hsl(var(--border));
          margin: 3px 2px;
        }

        /* ===== NEW CHAT BUTTON ===== */
        .navi-new-chat-btn {
          border-radius: 8px;
        }

        .navi-new-chat-icon {
          transition: transform 0.25s ease;
        }

        /* ===== NOTIFICATION BADGE ===== */
        .navi-has-badge {
          position: relative;
          overflow: visible !important;
        }

        .navi-notification-badge {
          position: absolute;
          top: -6px;
          right: -6px;
          min-width: 18px;
          height: 18px;
          padding: 0 5px;
          background: hsl(var(--destructive));
          border: 2px solid hsl(var(--background));
          border-radius: 10px;
          font-size: 10px;
          font-weight: 700;
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: badgePop 0.3s ease;
          z-index: 10;
          box-shadow: 0 2px 6px hsl(var(--destructive) / 0.4);
        }

        @keyframes badgePop {
          0% { transform: scale(0); }
          50% { transform: scale(1.2); }
          100% { transform: scale(1); }
        }

        /* ===== HEADER DIVIDER ===== */
        .navi-header-divider {
          width: 1px;
          height: 24px;
          background: hsl(var(--border) / 0.5);
          margin: 0 4px;
        }

        /* ===== THEME TOGGLE ===== */
        .navi-theme-toggle .navi-theme-icon-wrapper {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .navi-theme-toggle:hover .navi-icon-sun {
          animation: sunSpin 0.6s ease;
          color: hsl(40 100% 60%);
        }

        .navi-theme-toggle:hover .navi-icon-moon {
          animation: moonWobble 0.6s ease;
          color: hsl(220 80% 70%);
        }

        @keyframes sunSpin {
          0% { transform: rotate(0deg) scale(1); }
          50% { transform: rotate(180deg) scale(1.2); }
          100% { transform: rotate(360deg) scale(1); }
        }

        @keyframes moonWobble {
          0%, 100% { transform: rotate(0deg); }
          25% { transform: rotate(-15deg); }
          75% { transform: rotate(15deg); }
        }

        /* ===== BELL ICON ANIMATION ===== */
        .navi-bell-btn:hover .navi-bell-icon {
          animation: bellRing 0.6s ease;
          transform-origin: top center;
        }

        @keyframes bellRing {
          0% { transform: rotate(0deg); }
          15% { transform: rotate(15deg); }
          30% { transform: rotate(-12deg); }
          45% { transform: rotate(10deg); }
          60% { transform: rotate(-8deg); }
          75% { transform: rotate(5deg); }
          85% { transform: rotate(-3deg); }
          100% { transform: rotate(0deg); }
        }

        /* ===== HISTORY ICON ANIMATION ===== */
        .navi-history-btn:hover .navi-history-icon {
          animation: historyRewind 0.8s ease;
        }

        @keyframes historyRewind {
          0% { transform: rotate(0deg); }
          50% { transform: rotate(-360deg) scale(1.1); }
          100% { transform: rotate(-360deg) scale(1); }
        }

        /* ===== HELP ICON ANIMATION ===== */
        .navi-help-btn:hover .navi-help-icon {
          animation: helpBounce 0.5s ease;
        }

        @keyframes helpBounce {
          0%, 100% { transform: scale(1) rotate(0deg); }
          25% { transform: scale(1.15) rotate(-5deg); }
          50% { transform: scale(1.1) rotate(5deg); }
          75% { transform: scale(1.05) rotate(-3deg); }
        }

        /* ===== SIDEBAR TOGGLE BUTTON ===== */
        .navi-sidebar-toggle-btn {
          position: relative;
          display: none;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 8px;
          border: 1px solid hsl(var(--primary) / 0.3);
          background: linear-gradient(135deg, hsl(var(--primary) / 0.1), hsl(var(--accent) / 0.05));
          color: hsl(var(--primary));
          cursor: pointer;
          transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
        }

        .navi-sidebar-toggle-bg {
          position: absolute;
          inset: 0;
          background: linear-gradient(135deg, hsl(var(--primary) / 0.15), hsl(var(--accent) / 0.1));
          opacity: 0;
          transition: opacity 0.3s ease;
        }

        .navi-sidebar-toggle-btn:hover .navi-sidebar-toggle-bg {
          opacity: 1;
        }

        .navi-sidebar-toggle-icon {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: transform 0.3s ease;
        }

        .navi-sidebar-toggle-btn:hover .navi-sidebar-toggle-icon {
          transform: translateX(2px);
        }

        .navi-sidebar-toggle-hint {
          position: relative;
          display: none;
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.02em;
          text-transform: uppercase;
        }

        .navi-sidebar-toggle-btn:hover {
          border-color: hsl(var(--primary) / 0.5);
          box-shadow: 0 0 20px hsl(var(--primary) / 0.2);
          transform: translateX(2px);
        }

        /* ===== USER AVATAR BUTTON ===== */
        .navi-user-avatar-btn {
          position: relative;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px 10px 4px 4px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border) / 0.5);
          border-radius: 24px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-user-status {
          cursor: default;
        }

        .navi-user-status:hover {
          background: hsl(var(--secondary) / 0.3);
          border-color: hsl(var(--border) / 0.5);
        }

        .navi-user-status:hover .navi-avatar-glow {
          opacity: 0;
        }

        .navi-user-avatar-btn:hover {
          background: hsl(var(--secondary) / 0.5);
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-avatar-glow {
          position: absolute;
          left: 0;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: radial-gradient(circle, hsl(var(--primary) / 0.3), transparent);
          opacity: 0;
          transition: opacity 0.3s ease;
        }

        .navi-user-avatar-btn:hover .navi-avatar-glow {
          opacity: 1;
        }

        .navi-user-avatar {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: 2px solid hsl(var(--border));
          object-fit: cover;
        }

        .navi-user-initials {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          font-weight: 600;
          color: white;
        }

        .navi-user-name {
          font-size: 12px;
          color: hsl(var(--foreground));
          max-width: 100px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .navi-auth-status {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 2px 6px;
          border-radius: 999px;
          background: hsl(var(--primary) / 0.15);
          color: hsl(var(--primary));
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .navi-auth-required-badge {
          padding: 4px 8px;
          border-radius: 999px;
          background: hsl(var(--destructive) / 0.15);
          color: hsl(var(--destructive));
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .navi-user-chevron {
          color: hsl(var(--muted-foreground));
          transition: transform 0.2s ease;
        }

        /* ===== USER DROPDOWN ===== */
        .navi-user-dropdown {
          position: absolute;
          right: 0;
          top: calc(100% + 8px);
          width: 260px;
          background: hsl(var(--popover));
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          box-shadow: 0 10px 40px hsl(0 0% 0% / 0.3);
          overflow: hidden;
          z-index: 50;
          animation: dropdownSlide 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .navi-user-dropdown.navi-header-more-dropdown {
          width: 220px;
          padding: 6px 0;
          max-height: 320px;
        }

        @keyframes dropdownSlide {
          from { opacity: 0; transform: translateY(-8px) scale(0.96); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .navi-dropdown-user-info {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          background: hsl(var(--secondary) / 0.3);
        }

        .navi-dropdown-user-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .navi-dropdown-user-avatar img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .navi-dropdown-user-avatar span {
          font-size: 14px;
          font-weight: 600;
          color: white;
        }

        .navi-dropdown-user-details {
          flex: 1;
          min-width: 0;
        }

        .navi-dropdown-user-name {
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-dropdown-user-email {
          font-size: 12px;
          color: hsl(var(--muted-foreground));
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .navi-dropdown-user-org {
          font-size: 11px;
          color: hsl(var(--muted-foreground) / 0.7);
          margin-top: 2px;
        }

        .navi-dropdown-divider {
          height: 1px;
          background: hsl(var(--border));
        }

        .navi-nickname-row {
          padding: 12px 16px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: hsl(var(--secondary) / 0.2);
        }

        .navi-nickname-label {
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: hsl(var(--muted-foreground));
        }

        .navi-nickname-controls {
          display: flex;
          gap: 6px;
          align-items: center;
        }

        .navi-nickname-input {
          flex: 1;
          background: hsl(var(--background));
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
          padding: 6px 8px;
          font-size: 12px;
          color: hsl(var(--foreground));
        }

        .navi-nickname-save {
          border: 1px solid hsl(var(--primary) / 0.4);
          background: hsl(var(--primary) / 0.15);
          color: hsl(var(--primary-foreground));
          padding: 6px 10px;
          border-radius: 8px;
          font-size: 11px;
          cursor: pointer;
        }

        .navi-org-gate {
          position: fixed;
          inset: 0;
          background: rgba(8, 12, 24, 0.7);
          backdrop-filter: blur(6px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 60;
        }

        .navi-org-card {
          width: min(640px, 92vw);
          background: hsl(var(--background));
          border: 1px solid hsl(var(--border));
          border-radius: 16px;
          padding: 20px 22px;
          box-shadow: 0 18px 44px hsl(0 0% 0% / 0.35);
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .navi-org-card__header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: center;
        }

        .navi-org-card__title {
          font-size: 1rem;
          font-weight: 700;
        }

        .navi-org-card__subtitle {
          font-size: 0.8rem;
          color: hsl(var(--muted-foreground));
          margin-top: 4px;
        }

        .navi-org-card__dismiss {
          border: none;
          background: transparent;
          color: hsl(var(--muted-foreground));
          cursor: pointer;
          font-size: 0.8rem;
        }

        .navi-org-card__section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .navi-org-card__label {
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: hsl(var(--muted-foreground));
        }

        .navi-org-card__orgs {
          display: grid;
          gap: 8px;
        }

        .navi-org-card__org {
          border: 1px solid hsl(var(--border));
          background: hsl(var(--secondary) / 0.2);
          border-radius: 12px;
          padding: 10px 12px;
          text-align: left;
          cursor: pointer;
        }

        .navi-org-card__org.is-active {
          border-color: hsl(var(--primary));
          background: hsl(var(--primary) / 0.12);
        }

        .navi-org-card__org-name {
          font-weight: 600;
          font-size: 0.85rem;
        }

        .navi-org-card__org-meta {
          font-size: 0.72rem;
          color: hsl(var(--muted-foreground));
        }

        .navi-org-card__inputs {
          display: grid;
          gap: 8px;
        }

        .navi-org-card__input,
        .navi-org-card__select,
        .navi-org-card__textarea {
          border: 1px solid hsl(var(--border));
          background: hsl(var(--background));
          border-radius: 10px;
          padding: 8px 10px;
          color: hsl(var(--foreground));
          font-size: 0.85rem;
        }

        .navi-org-card__primary {
          background: hsl(var(--primary));
          color: hsl(var(--primary-foreground));
          border: none;
          border-radius: 10px;
          padding: 8px 12px;
          cursor: pointer;
          font-weight: 600;
        }

        .navi-org-card__invite-row {
          display: flex;
          gap: 8px;
          align-items: center;
        }

        .navi-org-card__secondary {
          border: 1px solid hsl(var(--border));
          background: hsl(var(--secondary) / 0.4);
          border-radius: 10px;
          padding: 8px 12px;
          cursor: pointer;
        }

        .navi-org-card__error {
          color: hsl(var(--destructive));
          font-size: 0.8rem;
        }

        .navi-org-card__loading {
          font-size: 0.75rem;
          color: hsl(var(--muted-foreground));
        }

        .navi-dropdown-menu-item {
          display: flex;
          align-items: center;
          gap: 12px;
          width: 100%;
          padding: 12px 16px;
          background: none;
          border: none;
          font-size: 13px;
          color: hsl(var(--foreground));
          cursor: pointer;
          transition: all 0.15s ease;
          text-align: left;
        }

        .navi-dropdown-menu-item:hover {
          background: hsl(var(--secondary) / 0.5);
        }

        .navi-dropdown-menu-item svg {
          color: hsl(var(--muted-foreground));
        }

        .navi-dropdown-menu-item__meta {
          margin-left: auto;
          min-width: 18px;
          height: 18px;
          padding: 0 6px;
          border-radius: 999px;
          background: hsl(var(--destructive));
          color: white;
          font-size: 10px;
          font-weight: 700;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 6px hsl(var(--destructive) / 0.35);
        }

        .navi-menu-item-danger {
          color: hsl(var(--destructive));
        }

        .navi-menu-item-danger:hover {
          background: hsl(var(--destructive) / 0.1);
        }

        .navi-menu-item-danger svg {
          color: hsl(var(--destructive));
        }

        /* ===== SIGN IN BUTTON V2 ===== */
        .navi-signin-btn-v2 {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 8px 18px;
          border: none;
          border-radius: 24px;
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
          background: transparent;
        }

        .navi-signin-gradient {
          position: absolute;
          inset: 0;
          background: linear-gradient(135deg,
            hsl(var(--primary)) 0%,
            hsl(var(--accent)) 50%,
            hsl(var(--primary)) 100%
          );
          background-size: 200% 100%;
          animation: gradientFlow 3s linear infinite;
          border-radius: 24px;
        }

        @keyframes gradientFlow {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }

        .navi-signin-content {
          position: relative;
          z-index: 2;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 600;
          color: white;
        }

        .navi-signin-shimmer {
          position: absolute;
          inset: 0;
          background: linear-gradient(
            90deg,
            transparent 0%,
            hsl(0 0% 100% / 0.25) 50%,
            transparent 100%
          );
          transform: translateX(-100%);
          transition: transform 0.6s ease;
        }

        .navi-signin-btn-v2:hover .navi-signin-shimmer {
          transform: translateX(100%);
        }

        .navi-signin-btn-v2:hover {
          transform: translateY(-2px) scale(1.02);
          box-shadow:
            0 8px 25px hsl(var(--primary) / 0.4),
            0 0 40px hsl(var(--accent) / 0.2);
        }

        .navi-signin-btn-v2:active {
          transform: translateY(0) scale(0.98);
        }

        .navi-signin-btn-v2::before {
          content: '';
          position: absolute;
          inset: -2px;
          border-radius: 26px;
          background: linear-gradient(135deg, hsl(var(--primary) / 0.5), hsl(var(--accent) / 0.5));
          opacity: 0;
          transition: opacity 0.3s ease;
          z-index: -1;
        }

        .navi-signin-btn-v2:hover::before {
          opacity: 1;
          animation: signInGlow 2s ease-in-out infinite;
        }

        @keyframes signInGlow {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50% { opacity: 0.8; transform: scale(1.05); }
        }

        /* ===== AUTH GROUP - Settings + Sign In ===== */
        .navi-auth-group {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .navi-settings-btn {
          position: relative;
        }

        .navi-settings-icon {
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .navi-settings-btn:hover .navi-settings-icon {
          transform: rotate(90deg);
          color: hsl(var(--primary));
        }

        .navi-settings-btn:active .navi-settings-icon {
          transform: rotate(180deg);
        }

        .navi-activity-btn.is-active {
          border-color: hsl(var(--primary) / 0.55);
          background: hsl(var(--primary) / 0.16);
          box-shadow: 0 0 0 1px hsl(var(--primary) / 0.22) inset;
        }

        .navi-activity-btn.is-active .navi-activity-icon {
          color: hsl(var(--primary));
        }

        /* ===== SIGN IN BUTTON V3 - Modern Glassy ===== */
        .navi-signin-btn-v3 {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 6px 12px;
          border-radius: 8px;
          border: 1px solid hsl(var(--primary) / 0.4);
          background: hsl(var(--primary) / 0.08);
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
        }

        .navi-signin-border-glow {
          position: absolute;
          inset: -1px;
          border-radius: 9px;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)), hsl(var(--primary)));
          background-size: 200% 200%;
          animation: borderRotate 4s linear infinite;
          opacity: 0;
          transition: opacity 0.3s ease;
          z-index: -1;
        }

        @keyframes borderRotate {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }

        .navi-signin-btn-v3:hover .navi-signin-border-glow {
          opacity: 1;
        }

        .navi-signin-bg {
          position: absolute;
          inset: 1px;
          border-radius: 7px;
          background: hsl(var(--background));
          z-index: 0;
        }

        .navi-signin-inner {
          position: relative;
          z-index: 2;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .navi-signin-icon {
          color: hsl(var(--primary));
          transition: all 0.3s ease;
        }

        .navi-signin-text {
          font-size: 11px;
          font-weight: 600;
          color: hsl(var(--primary));
          transition: all 0.3s ease;
        }

        .navi-signin-pulse {
          position: absolute;
          inset: 0;
          border-radius: 10px;
          background: radial-gradient(circle at center, hsl(var(--primary) / 0.15), transparent 70%);
          opacity: 0;
          transition: opacity 0.3s ease;
          animation: signinPulse 2s ease-in-out infinite;
          pointer-events: none;
        }

        @keyframes signinPulse {
          0%, 100% { transform: scale(0.95); opacity: 0; }
          50% { transform: scale(1.05); opacity: 0.5; }
        }

        .navi-signin-btn-v3:hover {
          border-color: transparent;
          background: hsl(var(--primary) / 0.12);
          transform: translateY(-2px);
          box-shadow: 0 8px 24px hsl(var(--primary) / 0.25);
        }

        .navi-signin-btn-v3:hover .navi-signin-pulse {
          opacity: 1;
        }

        .navi-signin-btn-v3:hover .navi-signin-icon {
          transform: scale(1.1);
        }

        .navi-signin-btn-v3:active {
          transform: translateY(0);
          box-shadow: 0 4px 12px hsl(var(--primary) / 0.2);
        }

        /* ===== STATUS CHIP - Minimal Online Indicator ===== */
        .navi-status-chip {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px 4px 8px;
          border-radius: 16px;
          background: hsl(var(--secondary) / 0.2);
          border: 1px solid hsl(var(--border) / 0.5);
          font-size: 11px;
          font-weight: 500;
          transition: all 0.3s ease;
        }

        .navi-status-chip__indicator {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: hsl(var(--muted-foreground));
          transition: all 0.3s ease;
        }

        .navi-status-chip__label {
          color: hsl(var(--muted-foreground));
          text-transform: uppercase;
          letter-spacing: 0.04em;
          transition: color 0.3s ease;
        }

        /* Online state */
        .navi-status-chip--online {
          background: hsl(var(--status-success) / 0.08);
          border-color: hsl(var(--status-success) / 0.25);
        }

        .navi-status-chip--online .navi-status-chip__indicator {
          background: hsl(var(--status-success));
          box-shadow: 0 0 6px hsl(var(--status-success) / 0.5);
          animation: statusPulse 2s ease-in-out infinite;
        }

        .navi-status-chip--online .navi-status-chip__label {
          color: hsl(var(--status-success));
        }

        @keyframes statusPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.1); }
        }

        /* Offline state */
        .navi-status-chip--offline {
          background: hsl(var(--destructive) / 0.08);
          border-color: hsl(var(--destructive) / 0.25);
        }

        .navi-status-chip--offline .navi-status-chip__indicator {
          background: hsl(var(--destructive));
        }

        .navi-status-chip--offline .navi-status-chip__label {
          color: hsl(var(--destructive));
        }

        /* Connecting state */
        .navi-status-chip--connecting {
          background: hsl(var(--status-warning) / 0.08);
          border-color: hsl(var(--status-warning) / 0.25);
        }

        .navi-status-chip--connecting .navi-status-chip__indicator {
          background: hsl(var(--status-warning));
          animation: statusBlink 1s ease-in-out infinite;
        }

        .navi-status-chip--connecting .navi-status-chip__label {
          color: hsl(var(--status-warning));
        }

        @keyframes statusBlink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }

        /* ===== SIDEBAR ===== */
        .navi-sidebar {
          background: hsl(var(--sidebar-bg));
          border-right: 1px solid hsl(var(--border));
          overflow-y: auto;
          overflow-x: hidden;
        }

        /* ===== RESPONSIVE ===== */
        @media (max-width: 768px) {
          .navi-brand-tagline,
          .navi-collab-count,
          .navi-action-label,
          .navi-user-name {
            display: none;
          }

          .navi-header-center {
            display: none;
          }
        }

        /* ===== FULL COMMAND CENTER PANEL ===== */
        .navi-full-panel-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: stretch;
          justify-content: stretch;
          padding: 16px;
          z-index: 1000;
          animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .navi-full-panel {
          width: 100%;
          height: 100%;
          max-width: none;
          max-height: none;
          background: linear-gradient(160deg, hsl(var(--card)) 0%, hsl(var(--background)) 65%);
          border: 1px solid hsl(var(--border) / 0.85);
          border-radius: 18px;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: slideUp 0.3s ease;
          box-shadow: 0 25px 80px hsl(var(--background) / 0.7), 0 0 40px hsl(var(--primary) / 0.12);
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(30px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        .navi-full-panel__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px 24px;
          border-bottom: 1px solid hsl(var(--border));
          background: linear-gradient(180deg, hsl(var(--secondary) / 0.3) 0%, transparent 100%);
        }

        .navi-full-panel__header-left {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .navi-full-panel__logo {
          width: 40px;
          height: 40px;
          border-radius: 12px;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          display: flex;
          align-items: center;
          justify-content: center;
          color: hsl(var(--primary-foreground));
          box-shadow: 0 4px 15px hsl(var(--primary) / 0.3);
        }

        .navi-full-panel__logo svg {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-full-panel__header-left:hover .navi-full-panel__logo svg {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.25));
        }

        .navi-full-panel__title h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-full-panel__title span {
          font-size: 12px;
          color: hsl(var(--muted-foreground));
        }

        .navi-full-panel__close {
          --icon-btn-size: 32px;
        }

        .navi-full-panel__close:hover {
          background: hsl(var(--destructive) / 0.12);
          border-color: hsl(var(--destructive) / 0.35);
          color: hsl(var(--destructive));
          box-shadow: 0 6px 18px hsl(var(--destructive) / 0.2);
        }

        .navi-full-panel__tabs {
          display: flex;
          gap: 4px;
          padding: 12px 24px;
          border-bottom: 1px solid hsl(var(--border) / 0.5);
          background: hsl(var(--secondary) / 0.2);
        }

        .navi-full-panel__tab {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 18px;
          border-radius: 8px;
          background: transparent;
          border: 1px solid transparent;
          color: hsl(var(--muted-foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
        }

        .navi-full-panel__tab:hover {
          background: hsl(var(--secondary) / 0.5);
          color: hsl(var(--foreground));
        }

        .navi-full-panel__tab:disabled {
          opacity: 0.48;
          cursor: not-allowed;
          color: hsl(var(--muted-foreground));
          background: transparent;
          border-color: transparent;
          box-shadow: none;
        }

        .navi-full-panel__tab:disabled:hover {
          background: transparent;
          color: hsl(var(--muted-foreground));
        }

        .navi-full-panel__tab.is-active {
          background: hsl(var(--secondary) / 0.6);
          color: hsl(var(--foreground));
          border-color: hsl(var(--border) / 0.7);
          box-shadow: inset 0 0 0 1px hsl(var(--primary) / 0.08);
        }

        .navi-full-panel__tab svg {
          transition: transform 0.2s ease, color 0.2s ease, filter 0.2s ease;
        }

        .navi-full-panel__tab:hover svg {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .navi-full-panel__tab:disabled svg,
        .navi-full-panel__tab:disabled:hover svg {
          transform: none;
          filter: none;
        }

        .navi-full-panel__content {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
        }

        .navi-icon-btn:disabled {
          opacity: 0.45;
          cursor: not-allowed;
          transform: none !important;
          box-shadow: none !important;
        }

        .navi-icon-btn:disabled .navi-icon-glow {
          opacity: 0;
        }

        .navi-full-panel__section-header {
          margin-bottom: 20px;
        }

        .navi-full-panel__section-header h3 {
          margin: 0 0 4px 0;
          font-size: 16px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-full-panel__section-header p {
          margin: 0;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-full-panel__tools-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }

        .navi-tool-card {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 16px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          transition: all 0.2s ease;
        }

        .navi-tool-card:hover {
          border-color: hsl(var(--primary) / 0.5);
          box-shadow: 0 4px 20px hsl(var(--primary) / 0.1);
        }

        .navi-tool-card__icon {
          width: 44px;
          height: 44px;
          border-radius: 10px;
          background: hsl(var(--secondary));
          display: flex;
          align-items: center;
          justify-content: center;
          color: hsl(var(--primary));
        }

        .navi-tool-card__info {
          flex: 1;
        }

        .navi-tool-card__info h4 {
          margin: 0 0 2px 0;
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-tool-card__info p {
          margin: 0;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
        }

        .navi-tool-card__badge {
          padding: 4px 10px;
          border-radius: 6px;
          background: hsl(var(--accent) / 0.15);
          color: hsl(var(--accent));
          font-size: 11px;
          font-weight: 600;
        }

        /* ===== COMMAND CENTER - FULL SIZE ===== */
        .navi-full-panel--large {
          width: 100%;
          height: 100%;
          max-width: none;
          max-height: none;
        }

        /* ===== MCP TOOLS TAB ===== */
        .navi-cc-mcp {
          display: flex;
          flex-direction: column;
          height: 100%;
        }

        .navi-cc-mcp__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 20px;
        }

        .navi-cc-mcp__header h3 {
          margin: 0 0 4px 0;
          font-size: 16px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-mcp__header p {
          margin: 0;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-mcp__controls {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .navi-cc-mcp__server {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          color: hsl(var(--muted-foreground));
          transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
        }

        .navi-cc-mcp__server svg {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-cc-mcp__server:hover {
          background: hsl(var(--secondary) / 0.7);
          border-color: hsl(var(--primary) / 0.35);
          color: hsl(var(--foreground));
        }

        .navi-cc-mcp__server:hover svg {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .navi-cc-mcp__server select {
          background: transparent;
          border: none;
          color: inherit;
          font-size: 13px;
          outline: none;
          min-width: 150px;
        }

        .navi-cc-mcp__search input {
          width: 240px;
          padding: 10px 14px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          color: hsl(var(--foreground));
          font-size: 13px;
        }

        .navi-cc-mcp__search input::placeholder {
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-mcp__search input:focus {
          outline: none;
          border-color: hsl(var(--primary) / 0.5);
          box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
        }

        .navi-cc-mcp__manage {
          padding: 10px 14px;
          background: hsl(var(--secondary) / 0.6);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          color: hsl(var(--foreground));
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-mcp__manage:hover {
          background: hsl(var(--secondary) / 0.8);
          border-color: hsl(var(--primary) / 0.35);
          box-shadow: 0 8px 18px hsl(var(--primary) / 0.12);
        }

        .navi-cc-loading, .navi-cc-error, .navi-cc-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 60px 20px;
          color: hsl(var(--muted-foreground));
          text-align: center;
        }

        .navi-cc-loading span, .navi-cc-error p {
          margin-top: 12px;
          font-size: 14px;
        }

        .navi-cc-error button {
          margin-top: 16px;
          padding: 8px 16px;
          background: hsl(var(--primary));
          border: none;
          border-radius: 8px;
          color: white;
          font-size: 13px;
          cursor: pointer;
        }

        .navi-cc-empty svg {
          opacity: 0.5;
        }

        .navi-cc-empty p {
          margin: 12px 0 4px;
          font-size: 14px;
          color: hsl(var(--foreground));
        }

        .navi-cc-empty span {
          font-size: 12px;
        }

        .navi-cc-mcp__body {
          display: grid;
          grid-template-columns: 320px 1fr;
          gap: 24px;
          flex: 1;
          min-height: 0;
        }

        .navi-cc-mcp__categories {
          display: flex;
          flex-direction: column;
          gap: 8px;
          overflow-y: auto;
          max-height: 500px;
        }

        .navi-cc-category {
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          overflow: hidden;
        }

        .navi-cc-category.is-expanded {
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-cc-category__header {
          display: flex;
          align-items: center;
          gap: 12px;
          width: 100%;
          padding: 14px 16px;
          background: none;
          border: none;
          cursor: pointer;
          text-align: left;
        }

        .navi-cc-category__icon {
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: hsl(var(--card));
          border-radius: 10px;
          color: hsl(var(--primary));
        }

        .navi-cc-category__info {
          flex: 1;
        }

        .navi-cc-category__name {
          display: block;
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-category__desc {
          display: block;
          font-size: 11px;
          color: hsl(var(--muted-foreground));
          margin-top: 2px;
        }

        .navi-cc-category__count {
          padding: 4px 8px;
          background: hsl(var(--primary) / 0.15);
          color: hsl(var(--primary));
          font-size: 11px;
          font-weight: 600;
          border-radius: 6px;
        }

        .navi-cc-category__chevron {
          color: hsl(var(--muted-foreground));
          transition: transform 0.2s ease;
        }

        .navi-cc-category__chevron.rotate-90 {
          transform: rotate(90deg);
        }

        .navi-cc-category__tools {
          padding: 0 8px 8px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .navi-cc-tool {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 12px;
          background: hsl(var(--card));
          border: 1px solid transparent;
          border-radius: 8px;
          cursor: pointer;
          text-align: left;
        }

        .navi-cc-tool:hover {
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-cc-tool.is-selected {
          background: hsl(var(--primary) / 0.1);
          border-color: hsl(var(--primary));
        }

        .navi-cc-tool__name {
          font-size: 13px;
          color: hsl(var(--foreground));
        }

        .navi-cc-tool__info {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .navi-cc-tool__server {
          font-size: 10px;
          color: hsl(var(--muted-foreground));
          letter-spacing: 0.02em;
          text-transform: uppercase;
        }

        .navi-cc-tool__badge {
          padding: 2px 6px;
          background: hsl(var(--status-warning) / 0.15);
          color: hsl(var(--status-warning));
          font-size: 10px;
          font-weight: 600;
          border-radius: 4px;
        }

        .navi-cc-mcp__detail {
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 16px;
          padding: 24px;
          overflow-y: auto;
          max-height: 500px;
        }

        .navi-cc-detail__header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 12px;
        }

        .navi-cc-detail__title {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .navi-cc-detail__header h4 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-detail__server {
          font-size: 10px;
          color: hsl(var(--muted-foreground));
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .navi-cc-detail__badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 10px;
          background: hsl(var(--status-warning) / 0.15);
          color: hsl(var(--status-warning));
          font-size: 11px;
          font-weight: 600;
          margin-left: auto;
          border-radius: 6px;
        }

        .navi-cc-detail__desc {
          margin: 0 0 24px;
          font-size: 14px;
          color: hsl(var(--muted-foreground));
          line-height: 1.5;
        }

        .navi-cc-params h5 {
          margin: 0 0 12px;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-param {
          margin-bottom: 16px;
        }

        .navi-cc-param label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: hsl(var(--foreground));
          margin-bottom: 6px;
        }

        .navi-cc-param label .required {
          color: hsl(var(--destructive));
          margin-left: 2px;
        }

        .navi-cc-param input, .navi-cc-param select {
          width: 100%;
          padding: 10px 14px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
          color: hsl(var(--foreground));
          font-size: 13px;
        }

        .navi-cc-param input:focus, .navi-cc-param select:focus {
          outline: none;
          border-color: hsl(var(--primary) / 0.5);
        }

        .navi-cc-checkbox {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
        }

        .navi-cc-checkbox input {
          width: 18px;
          height: 18px;
          accent-color: hsl(var(--primary));
        }

        .navi-cc-checkbox span {
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-execute {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border: none;
          border-radius: 10px;
          color: white;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          margin-top: 20px;
          transition: all 0.2s ease;
        }

        .navi-cc-execute:hover:not(:disabled) {
          box-shadow: 0 8px 24px hsl(var(--primary) / 0.4);
          transform: translateY(-2px);
        }

        .navi-cc-execute:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        .navi-cc-result {
          margin-top: 20px;
          border-radius: 10px;
          overflow: hidden;
        }

        .navi-cc-result.is-success {
          background: hsl(var(--status-success) / 0.1);
          border: 1px solid hsl(var(--status-success) / 0.3);
        }

        .navi-cc-result.is-error {
          background: hsl(var(--destructive) / 0.1);
          border: 1px solid hsl(var(--destructive) / 0.3);
        }

        .navi-cc-result__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          font-size: 13px;
          font-weight: 600;
        }

        .navi-cc-result.is-success .navi-cc-result__header {
          color: hsl(var(--status-success));
        }

        .navi-cc-result.is-error .navi-cc-result__header {
          color: hsl(var(--destructive));
        }

        .navi-cc-result__header button {
          background: none;
          border: none;
          padding: 4px;
          cursor: pointer;
          opacity: 0.7;
        }

        .navi-cc-result__header button:hover {
          opacity: 1;
        }

        .navi-cc-result pre {
          margin: 0;
          padding: 12px 14px;
          background: hsl(var(--background) / 0.5);
          font-size: 12px;
          font-family: monospace;
          white-space: pre-wrap;
          word-break: break-all;
          max-height: 200px;
          overflow-y: auto;
        }

        .navi-cc-mcp__placeholder {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: 60px 40px;
          background: hsl(var(--secondary) / 0.2);
          border: 2px dashed hsl(var(--border));
          border-radius: 16px;
        }

        .navi-cc-mcp__placeholder svg {
          color: hsl(var(--muted-foreground));
          opacity: 0.5;
          margin-bottom: 16px;
        }

        .navi-cc-mcp__placeholder h4 {
          margin: 0 0 8px;
          font-size: 16px;
          color: hsl(var(--foreground));
        }

        .navi-cc-mcp__placeholder p {
          margin: 0;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        /* ===== INTEGRATIONS TAB ===== */
        .navi-cc-integrations__header {
          margin-bottom: 24px;
        }

        .navi-cc-integrations__header h3 {
          margin: 0 0 4px;
          font-size: 16px;
          font-weight: 600;
        }

        .navi-cc-integrations__header p {
          margin: 0;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-integrations__grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
          gap: 16px;
        }

        .navi-cc-connector {
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 14px;
          overflow: hidden;
          transition: all 0.2s ease;
        }

        .navi-cc-connector.is-connected {
          border-color: hsl(var(--status-success) / 0.3);
        }

        .navi-cc-connector:hover {
          border-color: hsl(var(--primary) / 0.4);
          box-shadow: 0 4px 20px hsl(var(--primary) / 0.1);
        }

        .navi-cc-connector__header {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          padding: 16px;
          border-bottom: 1px solid hsl(var(--border) / 0.5);
        }

        .navi-cc-connector__icon {
          width: 48px;
          height: 48px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: hsl(var(--secondary));
          border-radius: 12px;
          flex-shrink: 0;
        }

        .navi-cc-connector__icon svg {
          width: 24px;
          height: 24px;
        }

        .navi-cc-connector__info {
          flex: 1;
          min-width: 0;
        }

        .navi-cc-connector__info h4 {
          margin: 0 0 4px;
          font-size: 15px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-connector__info p {
          margin: 0;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-connector__status {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 600;
          flex-shrink: 0;
        }

        .navi-cc-connector__status.connected {
          background: hsl(var(--status-success) / 0.15);
          color: hsl(var(--status-success));
        }

        .navi-cc-connector__status.disconnected {
          background: hsl(var(--secondary));
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-connector__status.error {
          background: hsl(var(--destructive) / 0.15);
          color: hsl(var(--destructive));
        }

        .navi-cc-connector__body {
          padding: 16px;
        }

        .navi-cc-connector__sync {
          display: block;
          font-size: 11px;
          color: hsl(var(--muted-foreground));
          margin-bottom: 12px;
        }

        .navi-cc-connector__btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          width: 100%;
          padding: 10px 16px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
          color: hsl(var(--foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-connector__btn:hover {
          background: hsl(var(--secondary));
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-cc-connector__btn--connect {
          background: hsl(var(--primary));
          border-color: hsl(var(--primary));
          color: white;
        }

        .navi-cc-connector__btn--connect:hover {
          background: hsl(var(--primary) / 0.9);
          box-shadow: 0 4px 12px hsl(var(--primary) / 0.3);
        }

        .navi-cc-connector__btn--disconnect {
          color: hsl(var(--destructive));
        }

        .navi-cc-connector__btn--disconnect:hover {
          background: hsl(var(--destructive) / 0.1);
          border-color: hsl(var(--destructive) / 0.3);
        }

        .navi-cc-connector__btn--cancel {
          background: transparent;
        }

        .navi-cc-connector__config {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .navi-cc-connector__field label {
          display: block;
          font-size: 12px;
          font-weight: 500;
          margin-bottom: 6px;
          color: hsl(var(--foreground));
        }

        .navi-cc-connector__field input {
          width: 100%;
          padding: 10px 12px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
          color: hsl(var(--foreground));
          font-size: 13px;
        }

        .navi-cc-connector__field input:focus {
          outline: none;
          border-color: hsl(var(--primary) / 0.5);
        }

        .navi-cc-connector__actions {
          display: flex;
          gap: 8px;
          margin-top: 8px;
        }

        .navi-cc-connector__actions button {
          flex: 1;
        }

        /* Connector logo images */
        .navi-cc-connector__icon img {
          width: 28px;
          height: 28px;
          object-fit: contain;
          filter: brightness(0) invert(1); /* Make SVG icons white for dark theme */
        }

        .navi-cc-connector__icon-fallback {
          font-size: 20px;
        }

        .navi-cc-connector__icon-fallback.hidden {
          display: none;
        }

        .navi-cc-connector__category-tag {
          display: inline-block;
          margin-top: 6px;
          padding: 2px 8px;
          background: hsl(var(--secondary));
          border-radius: 4px;
          font-size: 10px;
          font-weight: 500;
          color: hsl(var(--muted-foreground));
          text-transform: capitalize;
        }

        /* ===== INTEGRATIONS TOOLBAR ===== */
        .navi-cc-integrations__toolbar {
          display: flex;
          gap: 12px;
          margin-bottom: 16px;
        }

        .navi-cc-integrations__search {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 14px;
          background: hsl(var(--secondary) / 0.5);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          transition: all 0.2s ease;
        }

        .navi-cc-integrations__search:focus-within {
          border-color: hsl(var(--primary) / 0.5);
          box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
        }

        .navi-cc-integrations__search svg {
          color: hsl(var(--muted-foreground));
          flex-shrink: 0;
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-cc-integrations__search:focus-within svg {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .navi-cc-integrations__search input {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: hsl(var(--foreground));
          font-size: 14px;
        }

        .navi-cc-integrations__search input::placeholder {
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-integrations__search-clear {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          background: hsl(var(--muted-foreground) / 0.2);
          border: none;
          border-radius: 50%;
          color: hsl(var(--muted-foreground));
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .navi-cc-integrations__search-clear svg {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-cc-integrations__search-clear:hover {
          background: hsl(var(--muted-foreground) / 0.3);
          color: hsl(var(--foreground));
        }

        .navi-cc-integrations__search-clear:hover svg {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        /* ===== INTEGRATIONS CATEGORIES ===== */
        .navi-cc-integrations__categories {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 16px;
          padding-bottom: 16px;
          border-bottom: 1px solid hsl(var(--border) / 0.5);
        }

        .navi-cc-integrations__category {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 20px;
          color: hsl(var(--muted-foreground));
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          white-space: nowrap;
        }

        .navi-cc-integrations__category:hover {
          background: hsl(var(--secondary));
          color: hsl(var(--foreground));
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-cc-integrations__category.is-active {
          background: hsl(var(--secondary) / 0.7);
          border-color: hsl(var(--border) / 0.7);
          color: hsl(var(--foreground));
          box-shadow: inset 0 0 0 1px hsl(var(--primary) / 0.08);
        }

        .navi-cc-integrations__category svg {
          width: 14px;
          height: 14px;
          transition: transform 0.2s ease, filter 0.2s ease, color 0.2s ease;
        }

        .navi-cc-integrations__category:hover svg {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .navi-cc-integrations__category span {
          max-width: 100px;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        /* ===== INTEGRATIONS RESULTS COUNT ===== */
        .navi-cc-integrations__results-count {
          margin-bottom: 16px;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        /* ===== INTEGRATIONS EMPTY STATE ===== */
        .navi-cc-integrations__empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 60px 20px;
          text-align: center;
        }

        .navi-cc-integrations__empty svg {
          color: hsl(var(--muted-foreground) / 0.3);
          margin-bottom: 16px;
        }

        .navi-cc-integrations__empty h4 {
          margin: 0 0 8px;
          font-size: 16px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-integrations__empty p {
          margin: 0 0 20px;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-integrations__empty button {
          padding: 8px 16px;
          background: hsl(var(--primary));
          border: none;
          border-radius: 8px;
          color: white;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-integrations__empty button:hover {
          background: hsl(var(--primary) / 0.9);
          box-shadow: 0 4px 12px hsl(var(--primary) / 0.3);
        }

        /* ===== NAVI RULES TAB ===== */
        .navi-cc-rules__header {
          margin-bottom: 24px;
        }

        .navi-cc-rules__header h3 {
          margin: 0 0 4px;
          font-size: 16px;
          font-weight: 600;
        }

        .navi-cc-rules__header p {
          margin: 0;
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-rules__list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .navi-cc-rule {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 20px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          transition: all 0.2s ease;
        }

        .navi-cc-rule.is-enabled {
          border-color: hsl(var(--primary) / 0.3);
          background: linear-gradient(135deg, hsl(var(--primary) / 0.05), hsl(var(--accent) / 0.02));
        }

        .navi-cc-rule__info {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .navi-cc-rule__icon {
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: hsl(var(--secondary));
          border-radius: 10px;
          color: hsl(var(--primary));
        }

        .navi-cc-rule__text h4 {
          margin: 0 0 4px;
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-rule__text p {
          margin: 0 0 6px;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-rule__type {
          display: inline-block;
          padding: 2px 8px;
          background: hsl(var(--secondary));
          border-radius: 4px;
          font-size: 10px;
          font-weight: 600;
          text-transform: capitalize;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-rule__toggle {
          background: none;
          border: none;
          padding: 0;
          cursor: pointer;
          color: hsl(var(--muted-foreground));
          transition: color 0.2s ease;
        }

        .navi-cc-rule__toggle.is-on {
          color: hsl(var(--primary));
        }

        .navi-cc-rules__add {
          margin-top: 20px;
        }

        .navi-cc-rules__add-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          width: 100%;
          padding: 14px;
          background: hsl(var(--secondary) / 0.3);
          border: 2px dashed hsl(var(--border));
          border-radius: 12px;
          color: hsl(var(--muted-foreground));
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-rules__add-btn:hover {
          border-color: hsl(var(--primary) / 0.5);
          color: hsl(var(--primary));
          background: hsl(var(--primary) / 0.05);
        }

        /* ===== ACCOUNT TAB ===== */
        .navi-auth-wall {
          width: 100%;
          height: 100%;
          padding: clamp(18px, 2vw, 28px);
          display: flex;
          align-items: stretch;
          justify-content: center;
          overflow-y: auto;
          background:
            radial-gradient(110% 95% at 18% 6%, hsl(191 98% 63% / 0.12), transparent 54%),
            radial-gradient(95% 100% at 86% 4%, hsl(229 100% 66% / 0.11), transparent 56%),
            linear-gradient(180deg, hsl(var(--background)), hsl(var(--background)));
        }

        .navi-auth-wall__layout {
          width: min(1240px, 100%);
          min-height: 100%;
          display: grid;
          grid-template-columns: minmax(320px, 1.08fr) minmax(360px, 0.92fr);
          gap: clamp(14px, 1.8vw, 22px);
        }

        .navi-auth-wall__trust-rail {
          border: 1px solid hsl(var(--border) / 0.62);
          border-radius: 16px;
          padding: clamp(22px, 2.5vw, 34px);
          background:
            radial-gradient(132% 120% at 15% 7%, hsl(191 98% 63% / 0.16), transparent 58%),
            radial-gradient(126% 112% at 86% 9%, hsl(229 100% 66% / 0.16), transparent 60%),
            linear-gradient(165deg, hsl(222 28% 12% / 0.96), hsl(220 24% 9% / 0.94));
          display: flex;
          flex-direction: column;
          justify-content: center;
          box-shadow: inset 0 1px 0 hsl(0 0% 100% / 0.05);
        }

        .navi-auth-wall__trust-rail h3 {
          margin: 0;
          font-size: clamp(1.22rem, 2.5vw, 1.8rem);
          line-height: 1.2;
          color: hsl(var(--foreground));
        }

        .navi-auth-wall__trust-rail p {
          margin: 0.75rem 0 0;
          font-size: 0.95rem;
          color: hsl(var(--muted-foreground));
          line-height: 1.58;
          max-width: 64ch;
        }

        .navi-auth-wall__trust-list {
          list-style: none;
          margin: 1.3rem 0 0;
          padding: 0;
          display: grid;
          gap: 0.88rem;
        }

        .navi-auth-wall__trust-list li {
          display: flex;
          align-items: flex-start;
          gap: 0.62rem;
          color: hsl(var(--foreground));
          font-size: 0.9rem;
          line-height: 1.45;
        }

        .navi-auth-wall__trust-list svg {
          margin-top: 0.08rem;
          color: hsl(192 100% 68%);
          flex-shrink: 0;
        }

        .navi-auth-wall__entry {
          min-height: 100%;
          display: flex;
          align-items: stretch;
        }

        .navi-auth-wall__entry > .premium-auth-entry {
          width: 100%;
          min-height: 100%;
        }

        .navi-cc-account {
          width: min(100%, 1140px);
          max-width: none;
          margin: 0 auto;
          min-height: 100%;
          height: 100%;
          display: flex;
          flex-direction: column;
        }

        .navi-cc-account--unauth {
          display: flex;
          align-items: stretch;
          flex: 1;
        }

        .navi-cc-account__unauth-layout {
          width: 100%;
          min-height: max(520px, 100%);
          height: 100%;
          flex: 1;
          display: grid;
          grid-template-columns: minmax(280px, 1.08fr) minmax(360px, 0.92fr);
          gap: 14px;
        }

        .navi-cc-account__trust-rail {
          border: 1px solid hsl(var(--border) / 0.6);
          border-radius: 16px;
          padding: clamp(18px, 2.1vw, 28px);
          background:
            radial-gradient(120% 120% at 14% 6%, hsl(192 95% 60% / 0.14), transparent 52%),
            radial-gradient(150% 140% at 84% 8%, hsl(228 90% 62% / 0.16), transparent 58%),
            linear-gradient(165deg, hsl(220 24% 13% / 0.96), hsl(220 24% 9% / 0.92));
          display: flex;
          flex-direction: column;
          justify-content: center;
          box-shadow: inset 0 1px 0 hsl(0 0% 100% / 0.05);
        }

        .navi-cc-account__trust-rail h3 {
          margin: 0;
          font-size: clamp(1.06rem, 2.2vw, 1.28rem);
          line-height: 1.22;
          color: hsl(var(--foreground));
        }

        .navi-cc-account__trust-rail p {
          margin: 0.6rem 0 0;
          font-size: 0.93rem;
          color: hsl(var(--muted-foreground));
          line-height: 1.55;
        }

        .navi-cc-account__trust-list {
          list-style: none;
          margin: 1rem 0 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 0.62rem;
        }

        .navi-cc-account__trust-list li {
          display: flex;
          align-items: flex-start;
          gap: 0.56rem;
          color: hsl(var(--foreground));
          font-size: 0.83rem;
          line-height: 1.45;
        }

        .navi-cc-account__trust-list svg {
          margin-top: 0.12rem;
          color: hsl(190 96% 64%);
          flex-shrink: 0;
        }

        .navi-cc-account__auth-entry {
          width: 100%;
          display: flex;
          align-items: stretch;
          min-width: 0;
        }

        .navi-cc-account__auth-entry > .premium-auth-entry {
          width: 100%;
          min-height: 100%;
          max-width: 460px;
          margin-left: auto;
        }

        .navi-cc-account__profile {
          display: flex;
          align-items: center;
          gap: 20px;
          padding: 24px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 16px;
          margin-bottom: 24px;
        }

        .navi-cc-account__avatar {
          width: 72px;
          height: 72px;
          border-radius: 50%;
          object-fit: cover;
          border: 3px solid hsl(var(--primary));
        }

        .navi-cc-account__avatar-placeholder {
          width: 72px;
          height: 72px;
          border-radius: 50%;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          font-weight: 700;
          color: white;
        }

        .navi-cc-account__info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .navi-cc-account__name {
          font-size: 18px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-account__email {
          font-size: 14px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-account__org {
          font-size: 12px;
          color: hsl(var(--muted-foreground) / 0.8);
        }

        .navi-cc-account__tabs {
          display: flex;
          gap: 4px;
          padding: 4px;
          background: hsl(var(--secondary) / 0.3);
          border-radius: 12px;
          margin-bottom: 20px;
        }

        .navi-cc-account__tab {
          flex: 1;
          padding: 12px 16px;
          background: transparent;
          border: none;
          border-radius: 10px;
          color: hsl(var(--muted-foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-account__tab svg {
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .navi-cc-account__tab:hover svg {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .navi-cc-account__tab:hover {
          color: hsl(var(--foreground));
          background: hsl(var(--secondary) / 0.5);
        }

        .navi-cc-account__tab.is-active {
          color: hsl(var(--foreground));
          background: hsl(var(--secondary) / 0.6);
          box-shadow: inset 0 0 0 1px hsl(var(--primary) / 0.08);
        }

        .navi-cc-account__content {
          min-height: 200px;
        }

        .navi-cc-profile__details {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 20px;
        }

        .navi-cc-profile__detail {
          padding: 12px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 12px;
          display: flex;
          flex-direction: column;
          gap: 5px;
          min-height: 72px;
        }

        .navi-cc-profile__detail-label {
          display: block;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-profile__detail-value {
          display: block;
          font-size: 14px;
          font-weight: 600;
          color: hsl(var(--foreground));
        }

        .navi-cc-profile__actions {
          display: flex;
          gap: 12px;
        }

        .navi-cc-profile__actions button {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 12px 16px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          color: hsl(var(--foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-profile__actions button:hover {
          background: hsl(var(--secondary) / 0.5);
          border-color: hsl(var(--primary) / 0.3);
        }

        .navi-cc-profile__actions button svg {
          color: hsl(var(--primary));
        }

        @media (max-width: 920px) {
          .navi-cc-profile__details {
            grid-template-columns: 1fr;
          }
        }

        .navi-cc-prefs {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .navi-cc-pref label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: hsl(var(--foreground));
          margin-bottom: 10px;
        }

        .navi-cc-pref__options {
          display: flex;
          gap: 8px;
        }

        .navi-cc-pref__options button {
          flex: 1;
          padding: 12px 16px;
          background: hsl(var(--secondary) / 0.3);
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
          color: hsl(var(--muted-foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .navi-cc-pref__options button:hover {
          border-color: hsl(var(--primary) / 0.5);
          color: hsl(var(--foreground));
        }

        .navi-cc-pref__options button.is-active {
          background: hsl(var(--secondary) / 0.65);
          border-color: hsl(var(--border) / 0.7);
          color: hsl(var(--foreground));
          box-shadow: inset 0 0 0 1px hsl(var(--primary) / 0.08);
        }

        .navi-cc-shortcuts {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .navi-cc-shortcut {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 18px;
          background: hsl(var(--card));
          border: 1px solid hsl(var(--border));
          border-radius: 10px;
        }

        .navi-cc-shortcut__keys {
          display: flex;
          gap: 4px;
        }

        .navi-cc-shortcut__keys kbd {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 32px;
          height: 32px;
          padding: 0 10px;
          background: hsl(var(--secondary));
          border: 1px solid hsl(var(--border));
          border-radius: 6px;
          font-size: 12px;
          font-family: inherit;
          color: hsl(var(--foreground));
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .navi-cc-shortcut > span:last-child {
          font-size: 13px;
          color: hsl(var(--muted-foreground));
        }

        .navi-cc-account__signout {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          width: 100%;
          padding: 14px;
          background: hsl(var(--destructive) / 0.1);
          border: 1px solid hsl(var(--destructive) / 0.2);
          border-radius: 12px;
          color: hsl(var(--destructive));
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          margin-top: 24px;
          transition: all 0.2s ease;
        }

        .navi-cc-account__signout:hover {
          background: hsl(var(--destructive) / 0.15);
          border-color: hsl(var(--destructive) / 0.4);
        }

        @media (max-width: 1100px) {
          .navi-auth-wall__layout {
            grid-template-columns: 1fr;
          }

          .navi-auth-wall__trust-rail {
            min-height: 0;
          }

          .navi-cc-account__unauth-layout {
            grid-template-columns: 1fr;
            min-height: auto;
            gap: 12px;
          }

          .navi-cc-account__trust-rail {
            min-height: 0;
          }

          .navi-cc-account__auth-entry > .premium-auth-entry {
            max-width: none;
            margin-left: 0;
          }
        }

        /* Spin animation */
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .animate-spin {
          animation: spin 1s linear infinite;
        }
      `}</style>
    </div>
  );
}
