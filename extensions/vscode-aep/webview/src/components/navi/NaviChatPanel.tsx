// frontend/src/components/navi/NaviChatPanel.tsx
"use client";

import {
  ClipboardEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowDown,
  ArrowUp,
  BarChart3,
  Bell,
  Brain,
  Check,
  CheckCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Circle,
  CircleX,
  ClipboardList,
  Copy,
  Cpu,
  Eye,
  FileText,
  Filter,
  Folder,
  FolderTree,
  GitBranch,
  HelpCircle,
  History,
  Info,
  Lightbulb,
  Loader2,
  MessageSquare,
  Moon,
  Palette,
  Paperclip,
  Pencil,
  Pin,
  Plus,
  RotateCcw,
  RotateCw,
  Search,
  SendHorizontal,
  Settings,
  Shield,
  Sparkles,
  Star,
  Sun,
  Tag,
  Terminal,
  ThumbsDown,
  ThumbsUp,
  ToggleLeft,
  ToggleRight,
  Trash2,
  User,
  Wrench,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { NaviInlineCommand } from "../command";
import { resolveBackendBase, buildHeaders } from "../../api/navi/client";
import { ORG, USER_ID } from "../../api/client";
import { getRecommendedModel, getProgressMessages, detectTaskType, type TaskType } from "../../lib/llmRouter";
import {
  clearSessionDraft,
  clearSessionMessages,
  createSession,
  deleteSession,
  ensureActiveSession,
  getActiveSessionId,
  getSession,
  listSessions,
  listActiveSessions,
  listArchivedSessions,
  listStarredSessions,
  listPinnedSessions,
  loadSessionDraft,
  loadSessionMessages,
  saveSessionDraft,
  saveSessionMessages,
  setActiveSessionId as persistActiveSessionId,
  toggleSessionStar,
  toggleSessionArchive,
  toggleSessionPin,
  addSessionTag,
  removeSessionTag,
  formatRelativeTime,
  updateSession,
  type ChatSessionTag,
} from "../../utils/chatSessions";
import { QuickActionsBar, type QuickAction } from "./QuickActionsBar";
import { AttachmentToolbar } from "./AttachmentToolbar";
import {
  AttachmentChips,
  AttachmentChipData,
} from "./AttachmentChips";
import * as vscodeApi from "../../utils/vscodeApi";
import { AutonomousStepApproval } from "../AutonomousStepApproval";
import { NaviActionRunner } from "./NaviActionRunner";
import { NaviApprovalPanel, ActionWithRisk } from "./NaviApprovalPanel";
import { InlineCommandApproval } from "./InlineCommandApproval";
import { ExecutionPlanStepper, ExecutionPlanStep } from "./ExecutionPlanStepper";
import { FileChangeSummary } from "./FileChangeSummary";
import { FileDiffView, type DiffLine, type FileDiff } from "./FileDiffView";
import { useActivityPanelPreferences } from "../../hooks/useActivityPanelPreferences";
import "./NaviChatPanel.css";
import Prism from 'prismjs';
import type { ActivityEvent as ActivityEventPayload } from "../../types/activity";
// import * as Diff from 'diff';
// Temporarily commenting out components with missing dependencies
// import { LiveProgressDiagnostics } from '../ui/LiveProgressDiagnostics';
// import { Toaster } from '../ui/toaster';
// import EnhancedLiveReview from '../ui/EnhancedLiveReview';

/* ---------- Types ---------- */

type ChatRole = "user" | "assistant" | "system";

type ChatMessageMeta = {
  kind?: "command";
  commandId?: string;
};

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;           // NEW: timestamp for each message
  responseData?: NaviChatResponse;
  actions?: AgentAction[];
  meta?: ChatMessageMeta;
  attachments?: AttachmentChipData[];  // Image/file attachments for the message
  // Streaming support
  isStreaming?: boolean;  // True while message is being streamed
  // Autonomous coding fields
  agentRun?: {
    mode?: string;
    task_id?: string;
    status?: string;
  };
  state?: {
    autonomous_coding?: boolean;
    task_id?: string;
    workspace?: string;
    current_step?: number;
    total_steps?: number;
  };
  // Intelligence fields (like Codex/Claude Code)
  thinking_steps?: string[];  // Show what NAVI did
  files_read?: string[];  // Show what files were analyzed
  project_type?: string;  // Detected project type
  framework?: string;  // Detected framework
  warnings?: string[];  // Safety warnings

  // NAVI V2: Approval flow fields
  requiresApproval?: boolean;  // If true, show approval UI
  planId?: string;  // Unique plan ID for tracking
  actionsWithRisk?: ActionWithRisk[];  // Actions with risk assessment

  // Persisted activities and narratives (stored when streaming completes)
  // This allows activities to be displayed even after streaming ends
  storedActivities?: ActivityEvent[];
  storedNarratives?: Array<{ id: string; text: string; timestamp: string }>;
  storedThinking?: string; // Persisted thinking content
}

// Command consent request type
interface CommandConsentRequest {
  consent_id: string;
  command: string;
  shell: string;
  cwd?: string;
  danger_level: string;
  warning: string;
  consequences: string[];
  alternatives: string[];
  rollback_possible: boolean;
  timestamp: string;
}

type ExecutionMode = "plan_propose" | "plan_and_run";
type ScopeMode = "this_repo" | "current_file" | "service";
type ProviderId = "openai_navra" | "openai_byok" | "anthropic_byok";
type ChatMode = "agent" | "plan" | "ask" | "edit";

type LLMModel = {
  id: string;
  name: string;
  description: string;
};

type LLMProvider = {
  id: string;
  name: string;
  models: LLMModel[];
};

type AgentAction = {
  type: "editFile" | "createFile" | "runCommand";
  filePath?: string;
  description?: string;
  content?: string;
  diff?: string;
  command?: string;
  cwd?: string;
  meta?: {
    kind?: string;
    threshold?: number;
    [key: string]: any;
  };
};

const EXECUTION_LABELS: Record<ExecutionMode, string> = {
  plan_propose: "Agent",
  plan_and_run: "Auto (Recommended)",
};

const SCOPE_LABELS: Record<ScopeMode, string> = {
  this_repo: "This repo",
  current_file: "This file",
  service: "This service",
};

const PROVIDER_LABELS: Record<ProviderId, string> = {
  openai_navra: "OpenAI (Navra key)",
  openai_byok: "OpenAI (BYOK)",
  anthropic_byok: "Anthropic (BYOK)",
};

const CHAT_MODE_LABELS: Record<ChatMode, string> = {
  agent: "Agent",
  plan: "Plan",
  ask: "Ask",
  edit: "Edit",
};

const AUTO_MODEL_ID = "auto/recommended";

// Slash commands configuration
interface SlashCommand {
  command: string;
  label: string;
  description: string;
  icon: string;
  prompt?: string;  // Optional pre-filled prompt
}

const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: "/plan",
    label: "Plan",
    description: "Create a step-by-step implementation plan",
    icon: "📋",
    prompt: "Create a detailed plan for: ",
  },
  {
    command: "/explain",
    label: "Explain",
    description: "Explain code, architecture, or concepts",
    icon: "💡",
    prompt: "Explain: ",
  },
  {
    command: "/fix",
    label: "Fix",
    description: "Find and fix bugs or errors",
    icon: "🔧",
    prompt: "Fix the issue with: ",
  },
  {
    command: "/test",
    label: "Test",
    description: "Generate or run tests",
    icon: "🧪",
    prompt: "Write tests for: ",
  },
  {
    command: "/review",
    label: "Review",
    description: "Review code for issues and improvements",
    icon: "👀",
    prompt: "Review: ",
  },
  {
    command: "/refactor",
    label: "Refactor",
    description: "Improve code quality and structure",
    icon: "✨",
    prompt: "Refactor: ",
  },
  {
    command: "/commit",
    label: "Commit",
    description: "Generate commit message for changes",
    icon: "📝",
    prompt: "Generate a commit message for the current changes",
  },
  {
    command: "/debug",
    label: "Debug",
    description: "Help debug an issue",
    icon: "🐛",
    prompt: "Debug: ",
  },
  {
    command: "/doc",
    label: "Document",
    description: "Generate documentation",
    icon: "📄",
    prompt: "Generate documentation for: ",
  },
  {
    command: "/optimize",
    label: "Optimize",
    description: "Optimize code for performance",
    icon: "⚡",
    prompt: "Optimize: ",
  },
  {
    command: "/project",
    label: "Project",
    description: "Explain the entire project structure",
    icon: "🏗️",
    prompt: "Explain this project in detail",
  },
  {
    command: "/help",
    label: "Help",
    description: "Show available commands and tips",
    icon: "❓",
    prompt: "",
  },
];

const LLM_PROVIDERS: LLMProvider[] = [
  {
    id: "auto",
    name: "Auto",
    models: [
      {
        id: AUTO_MODEL_ID,
        name: "Auto (Recommended)",
        description: "Automatically selects the best model",
      },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    models: [
      // GPT-5 Series (Latest)
      { id: "openai/gpt-5.2", name: "GPT-5.2", description: "Latest flagship model" },
      { id: "openai/gpt-5.2-pro", name: "GPT-5.2 Pro", description: "Enhanced reasoning" },
      { id: "openai/gpt-5.1", name: "GPT-5.1", description: "Previous 5.x version" },
      { id: "openai/gpt-5", name: "GPT-5", description: "Fifth generation flagship" },
      { id: "openai/gpt-5-mini", name: "GPT-5 Mini", description: "Fast & efficient" },
      { id: "openai/gpt-5-nano", name: "GPT-5 Nano", description: "Ultra-fast for simple tasks" },
      // GPT-4.1 Series
      { id: "openai/gpt-4.1", name: "GPT-4.1", description: "Enhanced GPT-4" },
      { id: "openai/gpt-4.1-mini", name: "GPT-4.1 Mini", description: "Fast GPT-4.1" },
      { id: "openai/gpt-4.1-nano", name: "GPT-4.1 Nano", description: "Lightweight GPT-4.1" },
      // GPT-4o Series
      { id: "openai/gpt-4o", name: "GPT-4o", description: "Optimized multimodal" },
      { id: "openai/chatgpt-4o-latest", name: "ChatGPT-4o Latest", description: "ChatGPT optimized" },
      { id: "openai/gpt-4o-mini", name: "GPT-4o Mini", description: "Fast 4o variant" },
      { id: "openai/gpt-4o-search-preview", name: "GPT-4o Search", description: "Web search enabled" },
      // Reasoning Models (o-series)
      { id: "openai/o1", name: "o1", description: "Advanced reasoning" },
      { id: "openai/o1-pro", name: "o1 Pro", description: "Enhanced reasoning" },
      { id: "openai/o3", name: "o3", description: "Latest reasoning model" },
      { id: "openai/o3-mini", name: "o3 Mini", description: "Fast reasoning" },
      { id: "openai/o4-mini", name: "o4 Mini", description: "Compact reasoning" },
      { id: "openai/o4-mini-deep-research", name: "o4 Mini Deep Research", description: "Research optimized" },
      // Code Models
      { id: "openai/gpt-5.2-codex", name: "GPT-5.2 Codex", description: "Latest code model" },
      { id: "openai/gpt-5.1-codex", name: "GPT-5.1 Codex", description: "Code generation" },
      { id: "openai/gpt-5-codex", name: "GPT-5 Codex", description: "Code specialist" },
      { id: "openai/codex-mini-latest", name: "Codex Mini", description: "Fast code model" },
      // Legacy
      { id: "openai/gpt-4-turbo", name: "GPT-4 Turbo", description: "Legacy turbo model" },
      { id: "openai/gpt-3.5-turbo", name: "GPT-3.5 Turbo", description: "Fast legacy model" },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    models: [
      { id: "anthropic/claude-sonnet-4", name: "Claude Sonnet 4", description: "Balanced performance" },
      { id: "anthropic/claude-opus-4", name: "Claude Opus 4", description: "Most capable Claude" },
      { id: "anthropic/claude-3.5-haiku", name: "Claude 3.5 Haiku", description: "Fast & efficient" },
      { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet", description: "Previous generation" },
    ],
  },
  {
    id: "google",
    name: "Google",
    models: [
      { id: "google/gemini-2.5-pro", name: "Gemini 2.5 Pro", description: "Top-tier multimodal" },
      { id: "google/gemini-2.5-flash", name: "Gemini 2.5 Flash", description: "Fast & balanced" },
      { id: "google/gemini-2.5-flash-lite", name: "Gemini 2.5 Flash Lite", description: "Fastest option" },
      { id: "google/gemini-3-pro-preview", name: "Gemini 3 Pro", description: "Next-gen preview" },
    ],
  },
  {
    id: "groq",
    name: "Groq (Ultra-Fast)",
    models: [
      { id: "groq/llama-3.3-70b-versatile", name: "Llama 3.3 70B", description: "Most capable" },
      { id: "groq/llama3-70b-8192", name: "Llama 3 70B", description: "Previous generation" },
      { id: "groq/mixtral-8x7b-32768", name: "Mixtral 8x7B", description: "Fast mixture model" },
    ],
  },
];

interface NaviAction {
  id?: string;
  title?: string;
  description?: string;
  intent_kind?: string;
  type?: string;
  filePath?: string;
  command?: string;
  content?: string;
  diff?: string;
  cwd?: string;
  context?: Record<string, unknown>;
  meta?: {
    kind?: string;
    threshold?: number;
    [key: string]: unknown;
  };
}

interface ReviewComment {
  path: string;
  line?: number | null;
  summary: string;
  comment: string;
  level?: "nit" | "suggestion" | "issue" | "critical";
  suggestion?: string;
}

interface StructuredReviewFile {
  path: string;
  severity?: string;
  diff?: string;
  issues: Array<{
    id: string;
    title: string;
    body: string;
    canAutoFix: boolean;
  }>;
}

interface StructuredReview {
  files: StructuredReviewFile[];
}

interface NaviChatResponse {
  content?: string;
  reply?: string;
  actions?: NaviAction[];
  reviews?: ReviewComment[];
  context?: Record<string, any>;
  prDraft?: {
    title?: string;
    body?: string;
  };
  status?: string;
  progress_steps?: string[];
  state?: {
    repo_fast_path?: boolean;
    kind?: string;
    [key: string]: any;
  };
  // V3 Intelligence fields
  framework?: string;
  project_type?: string;
}

type DetectedTask = {
  taskType?: string;
  modelId?: string;
  modelName?: string;
  reason?: string;
  provider?: string;
  source?: "auto" | "manual";
  requestedModel?: string;
  requestedMode?: string;
  resolvedModel?: string;
  mode?: string; // chat | agent | agent-full-access
  autoExecute?: boolean;
};

type TerminalEntry = {
  id: string;
  command: string;
  cwd?: string;
  output: string;
  status: "running" | "done" | "error";
  startedAt: string;
  exitCode?: number;
  durationMs?: number;
};

type ActivityEvent = {
  id: string;
  kind: "read" | "edit" | "create" | "delete" | "command" | "info" | "error" | "thinking" | "llm_call" | "detection" | "context" | "analysis" | "prompt" | "parsing" | "validation" | "intent" | "rag" | "response";
  label: string;
  detail?: string;
  filePath?: string;
  status?: "running" | "done" | "error";
  timestamp: string;
  output?: string; // Command output for IN/OUT display
  exitCode?: number; // Command exit code
  additions?: number; // Lines added for edit/create operations
  deletions?: number; // Lines removed for edit operations
  diff?: string; // Unified diff content for edit operations
  _sequence?: number; // PHASE 5: Internal sequence number for guaranteed ordering
  // Command context fields (Bug 5 fix)
  purpose?: string; // Why this command/action is being run
  explanation?: string; // What the result means
  nextAction?: string; // What will happen next
};

type ActivityFile = {
  path: string;
  additions?: number;
  deletions?: number;
  scope?: "staged" | "unstaged" | "working";
  status?: "pending" | "editing" | "done" | "error";
  diff?: string;
  lastTouched?: string;
};

type ActionSummaryEntry = {
  type: AgentAction["type"];
  filePath?: string;
  command?: string;
  additions?: number;
  deletions?: number;
  exitCode?: number;
  durationMs?: number;
  success: boolean;
  message?: string;
  originalContent?: string; // For undo functionality
  wasCreated?: boolean; // True if file was newly created (for undo = delete)
};

// Inline change summary bar state (Cursor-style)
type InlineChangeSummary = {
  id: string;
  fileCount: number;
  totalAdditions: number;
  totalDeletions: number;
  files: Array<{
    path: string;
    additions: number;
    deletions: number;
    originalContent?: string;
    wasCreated?: boolean; // True if file was newly created (for undo = delete)
  }>;
  timestamp: string;
};

// PHASE 3: Consolidated activity types for reducing clutter
type ConsolidatedActivity =
  | { type: 'single'; activity: ActivityEvent }
  | { type: 'group'; kind: string; label: string; activities: ActivityEvent[]; collapsed: boolean };

// PHASE 3: Utility to consolidate activities (group consecutive file reads, limit display)
function consolidateActivities(activities: ActivityEvent[]): ConsolidatedActivity[] {
  // First, deduplicate activities for the same file - keep only the latest status
  // This prevents showing both "Reading/Read" and "Editing/Edit" duplicates
  // Also merge Read+Edit on same file into just Edit
  const deduped: ActivityEvent[] = [];
  const seenFiles = new Map<string, number>(); // file path -> index in deduped array

  for (const activity of activities) {
    const filePath = activity.detail || activity.filePath;

    if ((activity.kind === 'read' || activity.kind === 'edit' || activity.kind === 'create') && filePath) {
      const existingIdx = seenFiles.get(filePath);
      
      if (existingIdx !== undefined) {
        const existing = deduped[existingIdx];
        
        // If we have Read followed by Edit/Create on same file, keep only the Edit/Create
        if (existing.kind === 'read' && (activity.kind === 'edit' || activity.kind === 'create')) {
          deduped[existingIdx] = activity;
        }
        // If both are same kind, keep the one with better status/stats
        else if (existing.kind === activity.kind) {
          // Prefer the activity with additions/deletions info
          if (activity.additions !== undefined || activity.deletions !== undefined) {
            deduped[existingIdx] = activity;
          } else if (activity.status === 'done' && existing.status !== 'done') {
            deduped[existingIdx] = activity;
          }
        }
        // Otherwise keep existing (Edit/Create takes precedence over Read)
      } else {
        seenFiles.set(filePath, deduped.length);
        deduped.push(activity);
      }
    } else {
      deduped.push(activity);
    }
  }

  const result: ConsolidatedActivity[] = [];
  let fileReadGroup: ActivityEvent[] = [];
  let analysisGroup: ActivityEvent[] = [];

  const flushFileReads = () => {
    if (fileReadGroup.length === 0) return;
    if (fileReadGroup.length === 1) {
      result.push({ type: 'single', activity: fileReadGroup[0] });
    } else {
      result.push({
        type: 'group',
        kind: 'read',
        label: `Read ${fileReadGroup.length} files`,
        activities: [...fileReadGroup],
        collapsed: true,
      });
    }
    fileReadGroup = [];
  };

  const flushAnalysis = () => {
    if (analysisGroup.length === 0) return;
    if (analysisGroup.length === 1) {
      result.push({ type: 'single', activity: analysisGroup[0] });
    } else {
      result.push({
        type: 'group',
        kind: 'analysis',
        label: `${analysisGroup.length} analysis steps`,
        activities: [...analysisGroup],
        collapsed: true,
      });
    }
    analysisGroup = [];
  };

  for (const activity of deduped) {
    if (activity.kind === 'read') {
      flushAnalysis();
      fileReadGroup.push(activity);
    } else if (activity.kind === 'analysis' || activity.kind === 'context' || activity.kind === 'detection') {
      flushFileReads();
      analysisGroup.push(activity);
    } else {
      // Flush both groups and add as single
      flushFileReads();
      flushAnalysis();
      result.push({ type: 'single', activity });
    }
  }

  // Flush remaining
  flushFileReads();
  flushAnalysis();

  return result;
}

/* ---------- Utils ---------- */

const makeMessageId = (role: ChatRole): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${role}-${(crypto as any).randomUUID()}`;
  }
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

const makeActivityId = (): string =>
  `activity-${Date.now()}-${Math.random().toString(36).slice(2)}`;

const nowIso = () => new Date().toISOString();

const formatTime = (iso?: string): string => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const countLines = (text?: string): number => {
  if (!text) return 0;
  return text.split("\n").length;
};

const countUnifiedDiffStats = (diff?: string): { additions: number; deletions: number } | null => {
  if (!diff) return null;
  let additions = 0;
  let deletions = 0;
  diff.split("\n").forEach((line) => {
    if (line.startsWith("+") && !line.startsWith("+++")) {
      additions += 1;
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      deletions += 1;
    }
  });
  return { additions, deletions };
};

// Parse unified diff format into DiffLine array for rendering
const parseUnifiedDiff = (diffText: string): DiffLine[] => {
  if (!diffText) return [];

  const lines = diffText.split('\n');
  const result: DiffLine[] = [];
  let oldLineNum = 1;
  let newLineNum = 1;

  for (const line of lines) {
    // Skip diff headers (--- and +++ lines)
    if (line.startsWith('---') || line.startsWith('+++')) continue;

    // Parse hunk header (@@ -1,5 +1,7 @@)
    const hunkMatch = line.match(/^@@\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@/);
    if (hunkMatch) {
      oldLineNum = parseInt(hunkMatch[1], 10);
      newLineNum = parseInt(hunkMatch[2], 10);
      continue;
    }

    // Skip other metadata lines
    if (line.startsWith('diff ') || line.startsWith('index ')) continue;

    // Parse actual diff content
    if (line.startsWith('+')) {
      result.push({
        type: 'addition',
        content: line.slice(1),
        newLineNumber: newLineNum,
      });
      newLineNum++;
    } else if (line.startsWith('-')) {
      result.push({
        type: 'deletion',
        content: line.slice(1),
        oldLineNumber: oldLineNum,
      });
      oldLineNum++;
    } else if (line.startsWith(' ') || line === '') {
      // Context line
      result.push({
        type: 'context',
        content: line.startsWith(' ') ? line.slice(1) : line,
        oldLineNumber: oldLineNum,
        newLineNumber: newLineNum,
      });
      oldLineNum++;
      newLineNum++;
    }
  }

  return result;
};

const normalizeRoutingInfo = (routing: any): DetectedTask | null => {
  if (!routing || typeof routing !== "object") return null;
  const taskType =
    routing.task_type ||
    routing.taskType ||
    routing.task ||
    routing.intent ||
    undefined;
  const modelId =
    routing.resolved_model_id ||
    routing.model_id ||
    routing.modelId ||
    routing.model ||
    routing.resolved_model ||
    undefined;
  const modelName =
    routing.resolved_model_name ||
    routing.model_name ||
    routing.modelName ||
    routing.model_label ||
    undefined;
  const provider =
    routing.provider ||
    routing.provider_id ||
    routing.providerId ||
    undefined;
  const reason = routing.reason || routing.rationale || routing.explanation || undefined;
  const source = routing.source || undefined;
  const requestedModel = routing.requested_model || routing.requestedModel || undefined;
  const requestedMode = routing.mode || routing.requested_mode || routing.requestedMode || undefined;
  const resolvedModel = routing.resolved_model || routing.resolvedModel || undefined;
  return {
    taskType,
    modelId,
    modelName,
    provider,
    reason,
    source,
    requestedModel,
    requestedMode,
    resolvedModel,
  };
};

const formatTaskLabel = (taskType?: string) => {
  if (!taskType) return "Auto";
  return taskType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatProviderLabel = (provider?: string) => {
  if (!provider) return "";
  const normalized = provider.toLowerCase();
  if (normalized === "openai") return "OpenAI";
  if (normalized === "anthropic") return "Anthropic";
  if (normalized === "google") return "Google";
  return provider
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const flattenModels = () =>
  LLM_PROVIDERS.flatMap((provider) =>
    provider.models.map((model) => ({
      ...model,
      providerId: provider.id,
      providerName: provider.name,
    }))
  );

const getModelOption = (modelId: string) => {
  const all = flattenModels();
  return all.find((model) => model.id === modelId) || null;
};

const getModelLabel = (modelId: string, fallbackLabel?: string) => {
  const model = getModelOption(modelId);
  if (model) return model.name;
  return fallbackLabel || modelId;
};

const getDefaultManualModelId = () => {
  const preferred = LLM_PROVIDERS.find((provider) => provider.id !== "auto");
  return preferred?.models[0]?.id ?? "openai/gpt-5";
};

const DEFAULT_QUICK_ACTIONS: QuickAction[] = [
  { id: "tell_more", label: "Tell me more", prompt: "tell me more" },
  { id: "explain_further", label: "Can you explain further?", prompt: "can you explain further?" },
  { id: "next_steps", label: "What are the next steps?", prompt: "what are the next steps?" },
  { id: "alternatives", label: "Any alternatives?", prompt: "any alternatives?" },
];

const buildQuickActions = (contextText: string): QuickAction[] => {
  const text = contextText.toLowerCase();
  const actions: QuickAction[] = [];

  const pushUnique = (action: QuickAction) => {
    if (actions.some((existing) => existing.id === action.id)) return;
    actions.push(action);
  };

  if (/(error|bug|fail|exception|crash|stack trace)/.test(text)) {
    pushUnique({ id: "triage", label: "Summarize the error", prompt: "summarize the error and likely root cause" });
    pushUnique({ id: "fix_plan", label: "Propose a fix plan", prompt: "propose a fix plan with steps" });
    pushUnique({ id: "regression", label: "Add tests", prompt: "add tests to prevent regressions" });
  }

  if (/(review|audit|diff|changes|pr|pull request)/.test(text)) {
    pushUnique({ id: "prioritize", label: "Prioritize issues", prompt: "prioritize the issues by impact" });
    pushUnique({ id: "suggest_fixes", label: "Suggest fixes", prompt: "suggest fixes for the top issues" });
    pushUnique({ id: "open_diff", label: "Show diffs", prompt: "show the diffs and explain changes" });
  }

  if (/(test|coverage|ci|failing)/.test(text)) {
    pushUnique({ id: "run_tests", label: "Run tests", prompt: "run the relevant tests" });
    pushUnique({ id: "fix_failures", label: "Fix test failures", prompt: "fix the failing tests" });
  }

  if (/(plan|steps|approach|architecture|design)/.test(text)) {
    pushUnique({ id: "review_plan", label: "Review plan", prompt: "review the plan and adjust if needed" });
    pushUnique({ id: "risks", label: "List risks", prompt: "list key risks and assumptions" });
    pushUnique({ id: "milestones", label: "Break into milestones", prompt: "break this into milestones" });
  }

  if (/(ui|layout|component|css|style|frontend)/.test(text)) {
    pushUnique({ id: "ui_structure", label: "Propose structure", prompt: "propose a UI structure and layout" });
    pushUnique({ id: "ui_interactions", label: "Define interactions", prompt: "define key interactions and states" });
  }

  if (/(doc|readme|documentation|guide)/.test(text)) {
    pushUnique({ id: "doc_outline", label: "Outline docs", prompt: "outline the documentation sections" });
    pushUnique({ id: "doc_examples", label: "Add examples", prompt: "add usage examples" });
  }

  for (const fallback of DEFAULT_QUICK_ACTIONS) {
    pushUnique(fallback);
    if (actions.length >= 4) break;
  }

  return actions.slice(0, 4);
};

const MAX_SESSION_MESSAGES = 200;
const MAX_CONVERSATION_HISTORY = 25;
const MAX_TERMINAL_ENTRIES = 6;
const MAX_ACTIVITY_EVENTS = 60;

type GreetingKind = "simple" | "how_are_you" | "whats_up" | "time_of_day";

const getGreetingKind = (text: string): GreetingKind | null => {
  const raw = (text || "").trim().toLowerCase();
  if (!raw || raw.length > 60) return null;

  if (
    /\b(repo|project|code|error|review|scan|diff|change|fix|tests?|build|deploy|bug|issue)\b/.test(
      raw
    )
  ) {
    return null;
  }

  const normalized = raw
    .replace(/[^a-z0-9\s']/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return null;

  if (
    /\b(how\s*(are|ar|r)\s*(you|u|ya)|howre\s*(you|u)|hru|hw\s*(are|ar|r)?\s*(you|u)|how\s*u|how'?s it going|hows it going)\b/.test(
      normalized
    )
  ) {
    return "how_are_you";
  }

  if (/\b(what'?s up|whats up|wassup|watsup|sup)\b/.test(normalized)) {
    return "whats_up";
  }

  if (/\b(good morning|good afternoon|good evening|gm|ga|ge)\b/.test(normalized)) {
    return "time_of_day";
  }

  const filler = new Set([
    "navi",
    "assistant",
    "there",
    "team",
    "everyone",
    "all",
    "folks",
    "friend",
    "buddy",
    "sir",
    "maam",
  ]);

  const isGreetingToken = (token: string) => {
    if (!token) return false;
    if (/^h+i+$/.test(token)) return true;
    if (/^he+y+$/.test(token)) return true;
    if (/^hell+o+$/.test(token)) return true;
    if (/^hel+o+$/.test(token)) return true;
    if (/^hell+$/.test(token)) return true;
    if (/^yo+$/.test(token)) return true;
    if (/^hiya+$/.test(token)) return true;
    if (/^sup+$/.test(token)) return true;
    if (token === "wassup" || token === "watsup" || token === "whatsup") return true;
    if (token === "gm" || token === "ga" || token === "ge") return true;
    if (token === "hru" || token === "howre") return true;
    return false;
  };

  const tokens = normalized.split(" ").filter(Boolean);
  const remaining = tokens.filter(
    (token) => !filler.has(token) && !isGreetingToken(token)
  );
  if (tokens.length > 0 && remaining.length === 0) {
    return "simple";
  }

  return null;
};

const pickGreetingReply = (kind: GreetingKind): string => {
  const hour = new Date().getHours();
  const timeHint = hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
  const responses: Record<GreetingKind, string[]> = {
    simple: [
      "Hey! What do you want to tackle today: code, reviews, tests, or scans?",
      "Hi there! Tell me what you want me to do next.",
      "Hello! I can review code, fix errors, or sync connectors. What is up?",
      "Hey! Need a repo scan, a fix, or a review?",
    ],
    how_are_you: [
      "Doing well and ready to help. What should we work on?",
      "All good on my side. Want a review, a fix, or a repo scan?",
      "I am great. What do you want to tackle next?",
      "Doing fine. I can jump into code, tests, or connector syncs.",
    ],
    whats_up: [
      "All good here. What do you want me to do?",
      "Not much, ready to dive in. Code review or repo scan?",
      "Quiet on my side. Want me to check errors or sync connectors?",
      "I am ready. What should we tackle: bugs, tests, or scans?",
    ],
    time_of_day: [
      `Good ${timeHint}! What should we work on?`,
      `Good ${timeHint}! Want me to scan the repo or review changes?`,
      `Good ${timeHint}! I can help with code, tests, or connector syncs.`,
      `Good ${timeHint}! What is the next task?`,
    ],
  };

  const pool = responses[kind] || responses.simple;
  return pool[Math.floor(Math.random() * pool.length)];
};

const isGreeting = (text: string) => getGreetingKind(text) !== null;

const looksLikeGenericGreeting = (text: string) =>
  /autonomous engineering assistant/i.test(text);

const stripContextSection = (text: string): string => {
  const lines = text.split("\n");
  const result: string[] = [];
  let skipping = false;
  for (const line of lines) {
    const lower = line.toLowerCase();
    if (lower.startsWith("context i referenced")) {
      skipping = true;
      continue;
    }
    if (skipping) {
      // stop skipping once we hit a blank line after context block
      if (line.trim() === "") {
        skipping = false;
      }
      continue;
    }
    result.push(line);
  }
  return result.join("\n").trim();
};

const truncateText = (value: string, max = 64) => {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}...`;
};

const deriveSessionTitle = (messages: ChatMessage[], fallback?: string) => {
  const firstUser = messages.find(
    (msg) => msg.role === "user" && msg.content.trim().length > 0
  );
  if (firstUser) {
    return truncateText(firstUser.content, 64);
  }
  return fallback && fallback.trim() ? fallback : "New chat";
};

const derivePreview = (messages: ChatMessage[]) => {
  const last = messages[messages.length - 1];
  if (!last || !last.content) return "";
  const firstLine = last.content.split("\n")[0];
  return truncateText(firstLine, 120);
};

const MAX_COMMAND_OUTPUT = 20000;

const appendWithLimit = (current: string, next: string, limit: number) => {
  const combined = current + next;
  if (combined.length <= limit) {
    return { text: combined, truncated: false };
  }
  return { text: combined.slice(-limit), truncated: true };
};

const buildCommandMessage = (params: {
  command: string;
  cwd?: string;
  output: string;
  status: "running" | "done" | "error";
  exitCode?: number;
  durationMs?: number;
  truncated?: boolean;
  meta?: {
    kind?: string;
    threshold?: number;
  };
}) => {
  const lines: string[] = [];
  lines.push("Command:");
  lines.push(params.command);
  if (params.cwd) {
    lines.push(`CWD: ${params.cwd}`);
  }
  if (params.status === "running") {
    lines.push("Status: running...");
  } else if (params.status === "error") {
    lines.push("Status: error");
  } else {
    const code = params.exitCode ?? 0;
    const duration =
      typeof params.durationMs === "number"
        ? ` in ${Math.round(params.durationMs / 1000)}s`
        : "";
    lines.push(`Status: exited with code ${code}${duration}`);
  }
  if (params.meta?.kind === "coverage" && typeof params.meta.threshold === "number") {
    lines.push(`Coverage gate: >= ${params.meta.threshold}%`);
  }
  lines.push("");
  lines.push("Output:");
  if (params.output) {
    lines.push(params.output.trimEnd());
  } else {
    lines.push("(no output yet)");
  }
  if (params.truncated) {
    lines.push("");
    lines.push("...output truncated...");
  }
  return lines.join("\n");
};

const extractCoveragePercent = (output: string): number | null => {
  if (!output) return null;

  const goMatch = output.match(/coverage:\s*([\d.]+)%/i);
  if (goMatch?.[1]) return Number.parseFloat(goMatch[1]);

  const totalMatch = output.match(/^TOTAL.*?(\d+(?:\.\d+)?)%/im);
  if (totalMatch?.[1]) return Number.parseFloat(totalMatch[1]);

  const allFilesLine = output
    .split("\n")
    .find((line) => /all files/i.test(line));
  if (allFilesLine) {
    const percents = allFilesLine.match(/(\d+(?:\.\d+)?)%/g);
    if (percents && percents.length > 0) {
      return Number.parseFloat(percents[percents.length - 1]);
    }
  }

  const linesMatch = output.match(/lines?.*?(\d+(?:\.\d+)?)%/i);
  if (linesMatch?.[1]) return Number.parseFloat(linesMatch[1]);

  const stmtsMatch = output.match(/statements?.*?(\d+(?:\.\d+)?)%/i);
  if (stmtsMatch?.[1]) return Number.parseFloat(stmtsMatch[1]);

  return null;
};

/* ---------- Toast ---------- */

interface ToastState {
  id: number;
  message: string;
  kind: "info" | "warning" | "error";
}

type CoverageGateState = {
  status: "fail";
  coverage?: number | null;
  threshold?: number;
  updatedAt: string;
};

/* ---------- Phase 1.3.1: Diff File Card (HYBRID - IDE-native diff) ---------- */

interface FileDiffDetail {
  path: string;
  additions: number;
  deletions: number;
  diff: string;
  scope: 'staged' | 'unstaged';
}

function DiffFileCard({ fileDiff }: { fileDiff: FileDiffDetail }) {
  const handleOpenDiff = () => {
    vscodeApi.postMessage({
      type: 'openDiff',
      path: fileDiff.path,
      scope: fileDiff.scope
    });
  };

  return (
    <div className="border border-gray-700 rounded-lg bg-gray-900/50 overflow-hidden">
      {/* File summary with action button */}
      <div className="p-2 flex items-center justify-between">
        <div className="flex items-center gap-2 flex-1">
          <FileText className="h-3.5 w-3.5 text-gray-400" />
          <span className="text-xs font-mono text-gray-300">{fileDiff.path}</span>
          <span className={`text-xs px-1 rounded ${fileDiff.scope === 'staged' ? 'bg-green-900/30 text-green-400' : 'bg-yellow-900/30 text-yellow-400'}`}>
            {fileDiff.scope}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-green-400">+{fileDiff.additions}</span>
          <span className="text-xs text-red-400">-{fileDiff.deletions}</span>
          <button
            onClick={handleOpenDiff}
            className="text-xs px-2 py-1 ml-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
            title="Open native diff in VS Code editor"
          >
            Open
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Component ---------- */

interface NaviChatPanelProps {
  activityPanelState?: ReturnType<typeof import("../../hooks/useActivityPanel").useActivityPanel>;
  onOpenActivityForCommand?: (commandId: string) => void;
  highlightCommandId?: string | null;
}

export default function NaviChatPanel({ activityPanelState, onOpenActivityForCommand, highlightCommandId }: NaviChatPanelProps = {}) {
  const { workspaceRoot, repoName, isLoading } = useWorkspace();
  const activityPanelRef = useRef(activityPanelState);

  useEffect(() => {
    activityPanelRef.current = activityPanelState;
  }, [activityPanelState]);

  useEffect(() => {
    if (!highlightCommandId) return;
    setInlineCommandHighlightId(highlightCommandId);
    const el = document.querySelector(
      `[data-command-id="${highlightCommandId}"]`
    ) as HTMLElement | null;
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    const timer = window.setTimeout(() => {
      setInlineCommandHighlightId((current) =>
        current === highlightCommandId ? null : current
      );
    }, 20000);
    return () => window.clearTimeout(timer);
  }, [highlightCommandId]);

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AttachmentChipData[]>([]);
  const [sending, setSending] = useState(false);
  const [sendTimedOut, setSendTimedOut] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "error">("checking");
  const [backendError, setBackendError] = useState<string>("");
  const [coverageGate, setCoverageGate] = useState<CoverageGateState | null>(null);
  const [pendingConsents, setPendingConsents] = useState<Map<string, CommandConsentRequest>>(new Map());
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [historyFilter, setHistoryFilter] = useState<"all" | "pinned" | "starred" | "archived">("all");
  const [historySort, setHistorySort] = useState<"recent" | "oldest" | "name">("recent");
  const [historySortOpen, setHistorySortOpen] = useState(false);
  const [, setHistoryRefreshTrigger] = useState(0);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [inlineCommandHighlightId, setInlineCommandHighlightId] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [authRequiredDetail, setAuthRequiredDetail] = useState<string>("");
  const pendingAuthRetryRef = useRef(false);

  // Settings panel state
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<"behavior" | "appearance" | "notifications">("behavior");

  // Execution Plan Stepper state - for visual step-by-step progress UI
  const [executionPlan, setExecutionPlan] = useState<{
    planId: string;
    steps: ExecutionPlanStep[];
    isExecuting: boolean;
  } | null>(null);
  const executionPlanRef = useRef<typeof executionPlan>(null);

  useEffect(() => {
    executionPlanRef.current = executionPlan;
  }, [executionPlan]);

  // AI Behavior Settings
  const [aiSettings, setAiSettings] = useState({
    requireApprovalDestructive: true,
    autoExecuteSafe: false,
    explainBeforeExecute: true,
    preferLocalPatterns: true,
    verboseExplanations: false,
    streamResponses: true,
  });

  // Appearance Settings
  const [appearanceSettings, setAppearanceSettings] = useState({
    compactMode: false,
    showTimestamps: true,
    syntaxHighlighting: true,
    animationsEnabled: true,
  });
  const [activityPanelPreferences, setActivityPanelPreferences] = useActivityPanelPreferences();

  // Notification Settings
  const [notificationSettings, setNotificationSettings] = useState({
    soundEnabled: false,
    desktopNotifications: true,
    showErrorAlerts: true,
  });

  const [executionMode, setExecutionMode] =
    useState<ExecutionMode>("plan_propose");
  const [scope, setScope] = useState<ScopeMode>("this_repo");
  const [provider, setProvider] = useState<ProviderId>("openai_navra");
  const [chatMode, setChatMode] = useState<ChatMode>("agent");
  const [selectedModelId, setSelectedModelId] = useState(AUTO_MODEL_ID);
  const [modelLabelOverride, setModelLabelOverride] = useState<string | null>(null);
  const [useAutoModel, setUseAutoModel] = useState(true);
  const [lastManualModelId, setLastManualModelId] = useState(getDefaultManualModelId());
  const [lastRouterInfo, setLastRouterInfo] = useState<DetectedTask | null>(null);

  // Task Complete panel state
  type TaskSummary = {
    filesRead: number;
    filesModified: number;
    filesCreated: number;
    iterations: number;
    verificationPassed: boolean | null;
    nextSteps: string[];
    summaryText?: string;
    filesList?: Array<{
      path: string;
      action: 'created' | 'modified' | 'read';
      additions?: number;
      deletions?: number;
    }>;
    verificationDetails?: {
      typecheck?: { passed: boolean; errors?: string[] };
      lint?: { passed: boolean; errors?: string[] };
      build?: { passed: boolean; errors?: string[] };
      tests?: { passed: boolean; errors?: string[] };
    };
  };
  const [taskSummary, setTaskSummary] = useState<TaskSummary | null>(null);
  const [taskFilesExpanded, setTaskFilesExpanded] = useState(true);
  const [lastNextSteps, setLastNextSteps] = useState<string[]>([]);
  const [terminalEntries, setTerminalEntries] = useState<TerminalEntry[]>([]);
  const [terminalOpen, setTerminalOpen] = useState(true);
  const [activityOpen, setActivityOpen] = useState(true);

  // Branch dropdown state
  const [branchDropdownOpen, setBranchDropdownOpen] = useState(false);
  const [branches, setBranches] = useState<string[]>([]);
  const [currentBranch, setCurrentBranch] = useState<string>("");
  const [branchesLoading, setBranchesLoading] = useState(false);
  const [activityEvents, setActivityEvents] = useState<ActivityEvent[]>([]);
  const activityEventsRef = useRef<ActivityEvent[]>([]); // Ref to get latest activities in closures
  const [activityFiles, setActivityFiles] = useState<ActivityFile[]>([]);
  const [activityFilesOpen, setActivityFilesOpen] = useState(false);
  const [expandedActivityGroups, setExpandedActivityGroups] = useState<Set<string>>(new Set());
  const [expandedActivityFiles, setExpandedActivityFiles] = useState<Set<string>>(new Set());
  const [completedActionMessages, setCompletedActionMessages] = useState<Set<string>>(new Set());
  // Track activities per action index for inline display
  const [perActionActivities, setPerActionActivities] = useState<Map<number, ActivityEvent[]>>(new Map());
  // Live narrative stream (like Claude Code's conversational output)
  const [narrativeLines, setNarrativeLines] = useState<Array<{ id: string; text: string; timestamp: string }>>([]);
  const narrativeLinesRef = useRef<Array<{ id: string; text: string; timestamp: string }>>([]); // Ref for closures

  // Expandable thinking block (Claude Code-like reasoning display)
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const [accumulatedThinking, setAccumulatedThinking] = useState("");
  const accumulatedThinkingRef = useRef(""); // Ref for closure access
  const [isThinkingComplete, setIsThinkingComplete] = useState(false);

  // Execution plan panel state
  interface ExecutionStep {
    id: string;
    title: string;
    status: 'pending' | 'running' | 'done' | 'error';
    description?: string;
  }
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [planCollapsed, setPlanCollapsed] = useState(true);

  // Build verification state - tracks build/typecheck results after task completion
  type BuildVerificationResult = {
    success: boolean;
    skipped?: boolean;
    message?: string;
    project_type?: string;
    command?: string;
    command_name?: string;
    output?: string;
    errors?: string[];
    return_code?: number;
  };
  const [buildVerification, setBuildVerification] = useState<BuildVerificationResult | null>(null);

  // Dynamic placeholder suggestions
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const NAVI_SUGGESTIONS = [
    "Try: \"Explain this codebase architecture\"",
    "Try: \"Find and fix bugs in this file\"",
    "Try: \"Refactor this function for better performance\"",
    "Try: \"Add unit tests for this component\"",
    "Try: \"Generate API documentation\"",
    "Try: \"Review this PR for security issues\"",
    "Try: \"Create a new React component\"",
    "Try: \"Optimize database queries\"",
    "Try: \"Debug this error in the logs\"",
    "Try: \"Implement authentication flow\"",
  ];

  // Command history state
  const [commandHistory, setCommandHistory] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('navi-command-history');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [tempInput, setTempInput] = useState('');

  // Slash commands state
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [selectedSlashIndex, setSelectedSlashIndex] = useState(0);
  const slashMenuRef = useRef<HTMLDivElement | null>(null);

  // Filter slash commands based on input
  const filteredSlashCommands = useMemo(() => {
    if (!slashFilter) return SLASH_COMMANDS;
    const filter = slashFilter.toLowerCase();
    return SLASH_COMMANDS.filter(
      cmd => cmd.command.toLowerCase().includes(filter) ||
        cmd.label.toLowerCase().includes(filter) ||
        cmd.description.toLowerCase().includes(filter)
    );
  }, [slashFilter]);

  // Keep refs in sync with state for closure access in botMessageEnd
  // IMPORTANT: We sync refs both via useEffect AND directly in state setters
  // to ensure refs have latest values even before React renders
  useEffect(() => {
    activityEventsRef.current = activityEvents;
  }, [activityEvents]);

  useEffect(() => {
    narrativeLinesRef.current = narrativeLines;
  }, [narrativeLines]);

  useEffect(() => {
    accumulatedThinkingRef.current = accumulatedThinking;
  }, [accumulatedThinking]);

  // Wrapper to set activity events AND sync ref immediately (before React renders)
  const setActivityEventsWithRef = useCallback((updater: React.SetStateAction<ActivityEvent[]>) => {
    setActivityEvents(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      activityEventsRef.current = next; // Sync ref immediately
      return next;
    });
  }, []);

  // Wrapper to set narrative lines AND sync ref immediately
  const setNarrativeLinesWithRef = useCallback((updater: React.SetStateAction<Array<{ id: string; text: string; timestamp: string }>>) => {
    setNarrativeLines(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      narrativeLinesRef.current = next; // Sync ref immediately
      return next;
    });
  }, []);

  // Rotating placeholder effect
  useEffect(() => {
    if (input) return; // Don't rotate when user is typing
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % NAVI_SUGGESTIONS.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [input]);
  // Track streaming narratives per action index
  const [perActionNarratives, setPerActionNarratives] = useState<Map<number, Array<{ id: string; text: string; timestamp: string }>>>(new Map());
  // Track command outputs per action index for inline display
  const [perActionOutputs, setPerActionOutputs] = useState<Map<number, string>>(new Map());

  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const diffSectionRef = useRef<HTMLDivElement | null>(null);

  // Scroll navigation state
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const sendTimeoutRef = useRef<number | null>(null);
  const lastSentRef = useRef<string>("");
  const lastAttachmentsRef = useRef<AttachmentChipData[]>([]);
  const lastModelIdRef = useRef<string>(AUTO_MODEL_ID);
  const lastModeIdRef = useRef<ChatMode>("agent");
  const sentViaExtensionRef = useRef(false);
  const pendingResetRef = useRef(false);
  const resetTimeoutRef = useRef<number | null>(null);
  const analysisAbortRef = useRef<AbortController | null>(null);
  const chatAbortRef = useRef<AbortController | null>(null);
  const commandActivityRef = useRef<Map<string, string>>(new Map());
  const actionActivityRef = useRef<Map<string, string>>(new Map());
  const thinkingActivityRef = useRef<string | null>(null);
  const progressIntervalRef = useRef<(() => void) | null>(null);
  // Track current action index for associating activities
  const currentActionIndexRef = useRef<number | null>(null);
  const lastLiveProgressRef = useRef<string>("");
  const commandStateRef = useRef(
    new Map<
      string,
      {
        messageId: string;
        command: string;
        cwd?: string;
        output: string;
        truncated: boolean;
        status: "running" | "done" | "error";
        exitCode?: number;
        durationMs?: number;
        actionIndex?: number | null;
        activityStepIndex?: number;
        meta?: {
          kind?: string;
          threshold?: number;
          [key: string]: any;
        };
        coverageReported?: boolean;
      }
    >()
  );
  const pendingActionCountRef = useRef(0);
  const actionSummaryRef = useRef<ActionSummaryEntry[]>([]);
  const actionSummaryTimerRef = useRef<number | null>(null);

  // SELF-HEALING: Track retry attempts to prevent infinite loops
  const selfHealingRetryCountRef = useRef(0);
  const MAX_SELF_HEALING_RETRIES = 5; // Maximum attempts before giving up
  const lastFailedActionRef = useRef<string | null>(null); // Track last failed action to detect repeated failures
  // PHASE 4: Track current retry activity ID to update in place instead of creating new ones
  const currentRetryActivityRef = useRef<string | null>(null);
  // Track auto-execute mode for Agent Full Access
  const autoExecuteModeRef = useRef<boolean>(false);

  const [toast, setToast] = useState<ToastState | null>(null);
  const [structuredReview, setStructuredReview] = useState<StructuredReview | null>(null);
  const [reviewViewMode, setReviewViewMode] = useState<"issues" | "diffs">("issues");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState<string[]>([]);
  const [currentProgress, setCurrentProgress] = useState(0);
  // Autonomous coding state
  const [autonomousSteps, setAutonomousSteps] = useState<Record<string, any[]>>({});
  // const [analysisSummary, setAnalysisSummary] = useState<{
  // total_files: number;
  // detailed_files: number;
  // skipped_files: number;
  // highlights: string[];
  // } | null>(null);

  // NEW: Repo diff summary from agent (Phase 1.2)
  const [repoSummary, setRepoSummary] = useState<{
    base: string;
    unstagedCount: number;
    stagedCount: number;
    unstagedFiles: Array<{ path: string; status: string }>;
    stagedFiles: Array<{ path: string; status: string }>;
    totalChanges: number;
  } | null>(null);

  // NEW: Diff details for each file (Phase 1.3)
  const [diffDetails, setDiffDetails] = useState<Array<{
    path: string;
    additions: number;
    deletions: number;
    diff: string;
    scope: 'staged' | 'unstaged';
  }>>([]);
  const [changeDetailsOpen, setChangeDetailsOpen] = useState(false);

  // Sync latest terminal output into Activity Panel as a fallback
  useEffect(() => {
    if (!activityPanelState || terminalEntries.length === 0) return;
    if (!activityPanelState.steps.length) return;

    const latest = terminalEntries[terminalEntries.length - 1];
    const stepIndex = activityPanelState.currentStep ?? 0;
    activityPanelState.upsertCommand(stepIndex, latest.id, {
      command: latest.command,
      status: latest.status,
      exitCode: latest.exitCode,
      stdout: latest.output,
      truncated: latest.truncated,
    });
  }, [terminalEntries, activityPanelState]);

  // Phase 1.4: Diagnostics scoped to changed files
  const [diagnosticsByFile, setDiagnosticsByFile] = useState<Array<{
    path: string;
    diagnostics: Array<{ message: string; severity: number; line: number; character: number }>
  }>>([]);

  // Phase 1.3: Assessment summary (read-only intelligence)
  const [assessment, setAssessment] = useState<null | {
    totalDiagnostics: number;
    introduced: number;
    preExisting: number;
    errors: number;
    warnings: number;
    filesAffected: number;
    // Phase 1.4: Scope breakdown
    scope?: 'changed-files' | 'workspace';
    changedFileDiagsCount?: number;
    globalDiagsCount?: number;
    changedFileErrors?: number;
    changedFileWarnings?: number;
    hasGlobalIssuesOutsideChanged?: boolean;
  }>(null);

  // Phase 1.4: User's scope decision (changed-files | workspace)
  const [scopeDecision, setScopeDecision] = useState<'changed-files' | 'workspace'>('changed-files');

  // Inline change summary bar (Cursor-style) - shows after action completion
  const [inlineChangeSummary, setInlineChangeSummary] = useState<InlineChangeSummary | null>(null);

  // Phase 1.5: Detailed diagnostics grouped by file (for visualization)
  const [detailedDiagnostics, setDetailedDiagnostics] = useState<Array<{
    filePath: string;
    diagnostics: Array<{
      severity: string;
      message: string;
      line: number;
      character: number;
      source: string;
      impact: 'introduced' | 'preExisting';
    }>;
  }>>([]);
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());

  // Phase 2.0 Step 2: Fix proposals with approval state
  const [fixProposals, setFixProposals] = useState<Array<{
    filePath: string;
    proposals: Array<{
      id: string;
      line: number;
      severity: string;
      issue: string;
      rootCause: string;
      suggestedChange: string;
      confidence: string;
      impact: 'introduced' | 'preExisting';
      canAutoFixLater: boolean;
      source: string;
      riskLevel?: string;
      requiresChoice?: boolean;
      alternatives?: Array<{
        id: string;
        issue: string;
        suggestedChange: string;
        confidence: string;
        riskLevel: string;
        replacementText: string;
      }>;
    }>;
  }>>([]);
  const [approvalState, setApprovalState] = useState<Map<string, 'approved' | 'ignored'>>(new Map());
  const [expandedProposals, setExpandedProposals] = useState<Set<string>>(new Set());

  // Phase 2.1.2: Alternative selection modal state
  const [alternativeModal, setAlternativeModal] = useState<{
    proposalId: string;
    alternatives: Array<{
      id: string;
      issue: string;
      suggestedChange: string;
      confidence: string;
      riskLevel: string;
      replacementText: string;
    }>;
  } | null>(null);

  const showToast = (
    message: string,
    kind: ToastState["kind"] = "info"
  ) => {
    const id = Date.now();
    setToast({ id, message, kind });

    window.setTimeout(() => {
      setToast((current) =>
        current && current.id === id ? null : current
      );
    }, 2400);
  };

  const activityStreamRef = useRef<HTMLDivElement>(null);
  // PHASE 5: Sequence counter for guaranteed chronological ordering
  const activitySequenceRef = useRef(0);

  const pushActivityEvent = (event: ActivityEvent) => {
    // PHASE 5: Add sequence number for reliable ordering
    setActivityEvents((prev) => {
      // FIX: When a new "running" activity starts, mark all previous "running" activities as "done"
      // This ensures spinners stop when NAVI moves to the next step
      let workingPrev = prev;
      if (event.status === "running") {
        workingPrev = prev.map((item) =>
          item.status === "running" ? { ...item, status: "done" as const } : item
        );
      }

      // ENHANCED DEDUPLICATION: Check by label AND detail to avoid deduplicating different file reads
      // File reads all have label "Reading" or "Read" but different detail (file path)
      // So we need to match BOTH to properly deduplicate
      const existingByLabelAndDetail = workingPrev.findIndex(
        (item) => item.label === event.label && item.detail === event.detail
      );

      if (existingByLabelAndDetail >= 0) {
        // Update existing activity instead of adding duplicate
        const next = [...workingPrev];
        next[existingByLabelAndDetail] = {
          ...next[existingByLabelAndDetail],
          kind: event.kind, // Update kind in case it changed
          status: event.status,
          detail: event.detail || next[existingByLabelAndDetail].detail,
          timestamp: event.timestamp,
        };
        return next;
      }

      // Also check by ID
      const existingById = workingPrev.findIndex((item) => item.id === event.id);
      if (existingById >= 0) {
        const next = [...workingPrev];
        next[existingById] = { ...event, _sequence: workingPrev[existingById]._sequence };
        return next;
      }

      // New event - assign sequence number
      activitySequenceRef.current += 1;
      const sequencedEvent: ActivityEvent = {
        ...event,
        _sequence: activitySequenceRef.current,
      };

      // Add new event and sort by sequence number for guaranteed order
      const updated = [...workingPrev, sequencedEvent];
      updated.sort((a, b) => {
        const seqA = a._sequence || 0;
        const seqB = b._sequence || 0;
        if (seqA !== seqB) return seqA - seqB;
        const timeA = new Date(a.timestamp).getTime();
        const timeB = new Date(b.timestamp).getTime();
        return timeA - timeB;
      });
      return updated.slice(-MAX_ACTIVITY_EVENTS);
    });
    if (event.status === "running" || event.kind !== "info") {
      setActivityOpen(true);
    }
    if (event.filePath) {
      setActivityFilesOpen(true);
    }
    // Auto-scroll to latest event
    requestAnimationFrame(() => {
      if (activityStreamRef.current) {
        activityStreamRef.current.scrollTop = activityStreamRef.current.scrollHeight;
      }
    });
  };

  const normalizeActivityPath = (filePath: string) => {
    if (!filePath) return filePath;
    const relative = toWorkspaceRelativePath(filePath);
    return relative || filePath;
  };

  const upsertActivityFile = (update: ActivityFile) => {
    if (!update.path) return;
    const normalizedPath = normalizeActivityPath(update.path);
    const updateWithStats: ActivityFile = { ...update, path: normalizedPath };

    if (
      (updateWithStats.additions === undefined || updateWithStats.deletions === undefined) &&
      updateWithStats.diff
    ) {
      const stats = countUnifiedDiffStats(updateWithStats.diff);
      if (stats) {
        if (updateWithStats.additions === undefined) {
          updateWithStats.additions = stats.additions;
        }
        if (updateWithStats.deletions === undefined) {
          updateWithStats.deletions = stats.deletions;
        }
      }
    }

    setActivityFiles((prev) => {
      const idx = prev.findIndex((file) => file.path === normalizedPath);
      if (idx < 0) {
        return [...prev, updateWithStats];
      }
      const next = [...prev];
      const existing = next[idx];
      const merged: ActivityFile = { ...existing };
      if (updateWithStats.path) merged.path = updateWithStats.path;
      if (updateWithStats.additions !== undefined) merged.additions = updateWithStats.additions;
      if (updateWithStats.deletions !== undefined) merged.deletions = updateWithStats.deletions;
      if (updateWithStats.scope !== undefined) merged.scope = updateWithStats.scope;
      if (updateWithStats.status !== undefined) merged.status = updateWithStats.status;
      if (updateWithStats.diff !== undefined) merged.diff = updateWithStats.diff;
      if (updateWithStats.lastTouched !== undefined) merged.lastTouched = updateWithStats.lastTouched;
      next[idx] = merged;
      return next;
    });
    setActivityOpen(true);
    setActivityFilesOpen(true);
  };

  const toggleActivityFile = (path: string) => {
    setExpandedActivityFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const recordActionStart = () => {
    pendingActionCountRef.current += 1;
  };

  const recordActionSummary = (entry: ActionSummaryEntry) => {
    actionSummaryRef.current.push(entry);
  };

  const flushActionSummary = () => {
    // This is now only called when ALL actions are complete (via NaviActionRunner.onAllComplete)
    // so we don't need to check pendingActionCountRef
    if (actionSummaryRef.current.length === 0) return;

    const entries = [...actionSummaryRef.current];
    actionSummaryRef.current = [];

    const fileEntries = entries.filter((entry) => entry.type !== "runCommand" && entry.filePath);
    const commandEntries = entries.filter((entry) => entry.type === "runCommand");

    // Create inline change summary bar (Cursor-style) for file changes
    if (fileEntries.length > 0) {
      const totalAdditions = fileEntries.reduce((sum, e) => sum + (e.additions ?? 0), 0);
      const totalDeletions = fileEntries.reduce((sum, e) => sum + (e.deletions ?? 0), 0);

      const summary: InlineChangeSummary = {
        id: makeMessageId("assistant"),
        fileCount: fileEntries.length,
        totalAdditions,
        totalDeletions,
        files: fileEntries.map((entry) => ({
          path: entry.filePath!,
          additions: entry.additions ?? 0,
          deletions: entry.deletions ?? 0,
          originalContent: entry.originalContent,
          wasCreated: entry.wasCreated,
        })),
        timestamp: nowIso(),
      };

      setInlineChangeSummary(summary);
    }

    // Check if all commands succeeded using the success flag
    const allSuccess = entries.every((e) => e.success);
    const anyFailed = entries.some((e) => !e.success);

    // Don't create a summary message if actions failed - the failure handler
    // already created an error message. Only show success summaries.
    if (anyFailed) {
      // Failure messages are already handled in the action.complete handler
      return;
    }

    // DYNAMIC LLM-GENERATED SUMMARY: Instead of hardcoded messages,
    // request the LLM to generate a natural, contextual summary of all completed actions
    if (commandEntries.length > 0 || fileEntries.length > 0) {
      const hasCommands = commandEntries.length > 0;
      const hasFiles = fileEntries.length > 0;
      const commandCount = commandEntries.length;
      const fileCount = fileEntries.length;

      // Analyze what commands were run
      const commandNames = commandEntries.map(e => e.command || "").filter(Boolean);
      const hasInstall = commandNames.some(c => c.includes("install"));
      const hasTest = commandNames.some(c => c.includes("test"));
      const hasBuild = commandNames.some(c => c.includes("build"));
      const hasDev = commandNames.some(c => c.includes("dev") || c.includes("start"));

      // Send request to backend for LLM-generated summary
      // The LLM will generate natural, contextual conversation for billions of unique scenarios
      vscodeApi.postMessage({
        type: "generateActionFollowUp",
        actionType: "allComplete",
        success: true,
        summary: {
          commandCount,
          fileCount,
          commands: commandNames.slice(0, 5), // Limit to avoid too much context
          files: fileEntries.slice(0, 5).map(e => e.filePath),
          hasInstall,
          hasTest,
          hasBuild,
          hasDev,
        },
        hasMoreActions: false,
        projectInfo: {
          framework: messages.find(m => m.responseData?.framework)?.responseData?.framework,
          projectType: messages.find(m => m.responseData?.project_type)?.responseData?.project_type,
        },
      });
    }
  };

  const scheduleActionSummaryFlush = () => {
    if (actionSummaryTimerRef.current) {
      clearTimeout(actionSummaryTimerRef.current);
    }
    actionSummaryTimerRef.current = window.setTimeout(() => {
      flushActionSummary();
    }, 300);
  };

  /**
   * Derive workspaceRoot / repoName robustly.
   */
  const getEffectiveWorkspace = () => {
    let effectiveRoot: string | null =
      (workspaceRoot && workspaceRoot.trim()) || null;

    if (!effectiveRoot && typeof window !== "undefined") {
      try {
        const url = new URL(window.location.href);
        const fromQuery = url.searchParams.get("workspaceRoot");
        if (fromQuery && fromQuery.trim()) {
          effectiveRoot = fromQuery.trim();
        }
      } catch {
        // ignore
      }
    }

    let effectiveRepoName: string | null =
      (repoName && repoName.trim()) || null;

    if (
      (!effectiveRepoName || effectiveRepoName === "current") &&
      effectiveRoot
    ) {
      const segments = effectiveRoot.split(/[\\/]/).filter(Boolean);
      if (segments.length > 0) {
        effectiveRepoName = segments[segments.length - 1];
      }
    }

    return {
      effectiveRoot,
      effectiveRepoName,
    };
  };

  // Fetch branches when dropdown opens
  const fetchBranches = async () => {
    if (branches.length > 0) return; // Already fetched
    setBranchesLoading(true);
    try {
      // Request branches from extension
      vscodeApi.postMessage({ type: "git.getBranches" });
    } catch (error) {
      console.error("[NaviChatPanel] Failed to fetch branches:", error);
      setBranchesLoading(false);
    }
  };

  // Handle branch dropdown toggle
  const handleBranchDropdownToggle = () => {
    const newState = !branchDropdownOpen;
    setBranchDropdownOpen(newState);
    if (newState) {
      fetchBranches();
    }
  };

  // Handle branch selection
  const handleBranchSelect = (branch: string) => {
    setCurrentBranch(branch);
    setBranchDropdownOpen(false);
    // Notify extension about branch switch
    vscodeApi.postMessage({ type: "git.checkoutBranch", branch });
  };

  // Debug workspace context
  useEffect(() => {
    const { effectiveRoot, effectiveRepoName } = getEffectiveWorkspace();
    console.log("[NaviChatPanel] 🔍 Workspace context:", {
      contextWorkspaceRoot: workspaceRoot,
      contextRepoName: repoName,
      isLoading,
      url:
        typeof window !== "undefined"
          ? window.location.href
          : "(no-window)",
      effectiveRoot,
      effectiveRepoName,
    });

    if (!workspaceRoot) {
      vscodeApi.postMessage({ type: "getWorkspaceRoot" });
    }
  }, [workspaceRoot, repoName, isLoading]);

  // Listen for branch data from extension
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const message = event.data;
      if (message.type === "git.branches") {
        setBranches(message.branches || []);
        setCurrentBranch(message.currentBranch || "");
        setBranchesLoading(false);
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Handle clicks on file links (uses native DOM since dangerouslySetInnerHTML bypasses React events)
  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;

      // Check if clicked element or any parent is a file link
      const fileLink = target.classList.contains('navi-link--file')
        ? target
        : target.closest('.navi-link--file') as HTMLElement | null;

      // Also check if clicked on the wrapper span (for SVG icon clicks)
      const fileLinkWrapper = target.closest('.navi-file-link') as HTMLElement | null;
      const anchorFromWrapper = fileLinkWrapper?.querySelector('.navi-link--file') as HTMLElement | null;

      const finalLink = fileLink || anchorFromWrapper;

      if (finalLink) {
        e.preventDefault();
        e.stopPropagation();
        const filePath = finalLink.getAttribute('data-file-path');
        const lineStr = finalLink.getAttribute('data-line');
        const line = lineStr ? parseInt(lineStr, 10) : undefined;
        if (filePath) {
          console.log('[NAVI] Opening file:', filePath, 'at line:', line);
          vscodeApi.postMessage({ type: 'openFile', filePath, line });
        }
      }
    };
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);

  // Establish active session on mount
  useEffect(() => {
    const { effectiveRoot, effectiveRepoName } = getEffectiveWorkspace();
    const session = ensureActiveSession({
      repoName: effectiveRepoName || undefined,
      workspaceRoot: effectiveRoot || undefined,
    });
    setActiveSessionId(session.id);
  }, []);

  // Hydrate chat from the active session
  useEffect(() => {
    if (!activeSessionId) return;
    try {
      const storedMessages = loadSessionMessages<ChatMessage>(activeSessionId);
      const normalized = storedMessages
        .filter((m) => typeof m?.content === "string" && typeof m?.role === "string")
        .map((m) => ({
          id: m.id || makeMessageId((m.role as ChatRole) || "assistant"),
          role: (m.role as ChatRole) || "assistant",
          content: m.content || "",
          createdAt: m.createdAt || nowIso(),
          responseData: m.responseData,
          actions: Array.isArray((m as any).actions) ? (m as any).actions : undefined,
          meta:
            (m as any).meta && typeof (m as any).meta === "object"
              ? (m as any).meta
              : undefined,
          // Preserve all context fields for session recovery
          isStreaming: false, // Loaded messages are never streaming
          attachments: Array.isArray((m as any).attachments) ? (m as any).attachments : undefined,
          agentRun: (m as any).agentRun || undefined,
          state: (m as any).state || undefined,
          planSteps: Array.isArray((m as any).planSteps) ? (m as any).planSteps : undefined,
          planId: (m as any).planId || undefined,
          actionsWithRisk: Array.isArray((m as any).actionsWithRisk) ? (m as any).actionsWithRisk : undefined,
          // Critical: Preserve stored activities, narratives, and thinking for context continuity
          storedActivities: Array.isArray((m as any).storedActivities) ? (m as any).storedActivities : undefined,
          storedNarratives: Array.isArray((m as any).storedNarratives) ? (m as any).storedNarratives : undefined,
          storedThinking: typeof (m as any).storedThinking === "string" ? (m as any).storedThinking : undefined,
        }));
      setMessages(normalized);
      setInput(loadSessionDraft(activeSessionId));
      console.log("[NaviChatPanel] Session hydrated with", normalized.length, "messages, including stored activities and context");
    } catch (err) {
      console.warn("[NaviChatPanel] Failed to hydrate chat history:", err);
    }
  }, [activeSessionId]);

  // Backend status check
  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      setBackendStatus("checking");
      setBackendError("");
      try {
        const backendBase = resolveBackendBase();
        console.log('[NAVI] Backend health check - URL:', `${backendBase}/api/navi/chat`);
        const res = await fetch(`${backendBase}/api/navi/chat`, {
          method: "POST",
          headers: buildHeaders(),
          body: JSON.stringify({
            message: "health_check",
            attachments: [],
            workspace_root: null,
          }),
        });
        if (!res.ok) {
          const text = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
        }
        const text = await res.text();
        if (!text || !text.trim()) {
          throw new Error("Empty response from backend");
        }
        // We don't need parsed content, just a successful round-trip
        if (!cancelled) {
          setBackendStatus("ok");
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error('[NAVI] Backend health check failed:', err);
          setBackendStatus("error");
          setBackendError(err?.message || String(err));
        }
      }
    };
    void ping();
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist chat history per-session
  useEffect(() => {
    if (!activeSessionId) return;
    if (messages.length > MAX_SESSION_MESSAGES) {
      setMessages(messages.slice(-MAX_SESSION_MESSAGES));
      return;
    }
    try {
      saveSessionMessages(activeSessionId, messages);
      const preview = derivePreview(messages);
      const existing = getSession(activeSessionId);
      const title = deriveSessionTitle(messages, existing?.title);
      const { effectiveRoot, effectiveRepoName } = getEffectiveWorkspace();
      updateSession(activeSessionId, {
        title,
        messageCount: messages.length,
        lastMessagePreview: preview || undefined,
        repoName: effectiveRepoName || existing?.repoName,
        workspaceRoot: effectiveRoot || existing?.workspaceRoot,
      });
    } catch (err) {
      console.warn("[NaviChatPanel] Failed to persist chat history:", err);
    }
  }, [messages, activeSessionId, workspaceRoot, repoName]);

  // Persist draft input per-session
  useEffect(() => {
    if (!activeSessionId) return;
    saveSessionDraft(activeSessionId, input);
  }, [input, activeSessionId]);

  // Scroll on new message
  useEffect(() => {
    if (!scrollerRef.current) return;
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [messages.length]);

  // Auto-scroll during streaming when new content arrives
  // Only auto-scroll if user is already at/near the bottom (within 150px)
  // This allows users to scroll up and read previous content during streaming
  useEffect(() => {
    if (!sending || !scrollerRef.current) return;
    const scroller = scrollerRef.current;
    const isNearBottom = scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 150;

    // Only auto-scroll if user hasn't scrolled up
    if (isNearBottom) {
      const timeoutId = setTimeout(() => {
        if (scrollerRef.current) {
          scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
        }
      }, 50);
      return () => clearTimeout(timeoutId);
    }
  }, [sending, activityEvents.length, narrativeLines.length]);

  // Handle scroll position for navigation buttons
  useEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scroller;
      const scrollBuffer = 100; // pixels from edge to show buttons

      // Show "scroll to top" if not at top
      setShowScrollTop(scrollTop > scrollBuffer);

      // Show "scroll to bottom" if not at bottom
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - scrollBuffer;
      setShowScrollBottom(!isAtBottom && scrollHeight > clientHeight);
    };

    // Initial check
    handleScroll();

    scroller.addEventListener('scroll', handleScroll, { passive: true });
    return () => scroller.removeEventListener('scroll', handleScroll);
  }, [messages.length]);

  // Scroll navigation functions
  const scrollToTop = () => {
    scrollerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollToBottom = () => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTo({
        top: scrollerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  // Auto fallback once on timeout
  const fallbackTriggeredRef = useRef(false);
  useEffect(() => {
    if (sendTimedOut && !fallbackTriggeredRef.current) {
      fallbackTriggeredRef.current = true;
      if (!sentViaExtensionRef.current) {
        void handleDirectFallbackSend();
      }
    }
    if (!sendTimedOut) {
      fallbackTriggeredRef.current = false;
    }
  }, [sendTimedOut]);

  // Enhanced copy/paste handling for VSCode webview
  useEffect(() => {
    if (typeof window === "undefined") return;

    const getActiveInputSelection = () => {
      const active = document.activeElement as
        | HTMLInputElement
        | HTMLTextAreaElement
        | null;
      if (!active) return "";
      const tag = active.tagName;
      if (tag !== "INPUT" && tag !== "TEXTAREA") return "";
      const start = active.selectionStart ?? 0;
      const end = active.selectionEnd ?? 0;
      if (end <= start) return "";
      return active.value.slice(start, end);
    };

    // Copy handler - works with Cmd/Ctrl+C
    const copyHandler = () => {
      let selection = window.getSelection()?.toString() ?? "";
      if (!selection.trim()) {
        selection = getActiveInputSelection();
      }
      if (!selection.trim()) return;

      // Write to both native clipboard and VSCode clipboard
      navigator.clipboard.writeText(selection).catch(() => { });
      if (vscodeApi.hasVsCodeHost()) {
        vscodeApi.writeClipboard(selection).catch(() => { });
      }
    };

    // Keyboard shortcut handler for copy/paste/cut
    const keyHandler = (e: globalThis.KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const cmdKey = isMac ? e.metaKey : e.ctrlKey;

      // Copy: Cmd/Ctrl+C
      if (cmdKey && e.key.toLowerCase() === 'c') {
        const selection = window.getSelection()?.toString() ?? "";
        if (selection.trim()) {
          navigator.clipboard.writeText(selection).catch(() => { });
          if (vscodeApi.hasVsCodeHost()) {
            vscodeApi.writeClipboard(selection).catch(() => { });
          }
        }
      }

      // Paste: Cmd/Ctrl+V
      if (cmdKey && e.key.toLowerCase() === 'v') {
        const active = document.activeElement;
        if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) {
          // Let native paste work for input fields
          return;
        }
        // For non-input areas, try to paste into the input field if focused
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }

      // Select All: Cmd/Ctrl+A
      if (cmdKey && e.key.toLowerCase() === 'a') {
        const active = document.activeElement;
        // Only prevent default for non-input areas to allow selecting all chat content
        if (active && active.tagName !== 'INPUT' && active.tagName !== 'TEXTAREA') {
          // Allow native select all behavior
        }
      }
    };

    // Context menu handler for right-click copy
    const contextMenuHandler = (e: MouseEvent) => {
      const selection = window.getSelection()?.toString() ?? "";
      // Allow native context menu when text is selected
      if (selection.trim()) {
        // Native context menu should work - no need to prevent
        return;
      }
    };

    window.addEventListener("copy", copyHandler);
    window.addEventListener("keydown", keyHandler);
    window.addEventListener("contextmenu", contextMenuHandler);

    return () => {
      window.removeEventListener("copy", copyHandler);
      window.removeEventListener("keydown", keyHandler);
      window.removeEventListener("contextmenu", contextMenuHandler);
    };
  }, []);

  // Listen for VS Code messages
  useEffect(() => {
    const clearSendTimeout = () => {
      if (sendTimeoutRef.current) {
        clearTimeout(sendTimeoutRef.current);
        sendTimeoutRef.current = null;
      }
      setSendTimedOut(false);
    };

    const reportCoverageIfNeeded = (entry: {
      output: string;
      meta?: { kind?: string; threshold?: number };
      coverageReported?: boolean;
    }) => {
      if (entry.coverageReported) return;
      if (entry.meta?.kind !== "coverage") return;
      entry.coverageReported = true;

      const coverage = extractCoveragePercent(entry.output);
      const threshold =
        typeof entry.meta?.threshold === "number" ? entry.meta.threshold : undefined;

      let summary = "Coverage check complete.";
      if (coverage == null) {
        summary += " I couldn't parse a coverage percentage from the output.";
        if (typeof threshold === "number") {
          setCoverageGate({
            status: "fail",
            coverage: null,
            threshold,
            updatedAt: nowIso(),
          });
        }
      } else if (typeof threshold === "number") {
        const status = coverage >= threshold ? "PASS" : "FAIL";
        summary = `Coverage: ${coverage.toFixed(1)}% (target ${threshold}%) - ${status}`;
        if (coverage >= threshold) {
          setCoverageGate(null);
        } else {
          setCoverageGate({
            status: "fail",
            coverage,
            threshold,
            updatedAt: nowIso(),
          });
        }
      } else {
        summary = `Coverage: ${coverage.toFixed(1)}%`;
        setCoverageGate(null);
      }

      const coverageMessage: ChatMessage = {
        id: makeMessageId("system"),
        role: "system",
        content: summary,
        createdAt: nowIso(),
      };

      setMessages((prev) => [...prev, coverageMessage]);
    };

    // Phase 2.1 Step 1: Bridge for iframe -> webview -> extension messages
    // The iframe (EnhancedLiveReview) sends messages via window.parent.postMessage
    const handleIframeMessage = (event: MessageEvent) => {
      if (!event.data || typeof event.data !== 'object') return;
      const msg = event.data;
      // Only handle messages we care about (ignore others)
      if (msg.type === 'navi.fix.apply') {
        console.log('[NaviChatPanel] Bridging iframe message to extension:', msg);
        vscodeApi.postMessage(msg);
      }
    };
    window.addEventListener('message', handleIframeMessage);

    const unsub = vscodeApi.onMessage((msg) => {
      if (!msg || typeof msg !== "object") return;
      const activityPanel = activityPanelRef.current;

      if (msg.type === "hydrateState") {
        const nextModelId = typeof msg.modelId === "string" ? msg.modelId : AUTO_MODEL_ID;
        const nextModelLabel = typeof msg.modelLabel === "string" ? msg.modelLabel : null;
        const nextModeId = typeof msg.modeId === "string" ? msg.modeId : "agent";

        const knownModel = getModelOption(nextModelId);
        setSelectedModelId(nextModelId);
        setModelLabelOverride(knownModel ? null : nextModelLabel);

        const isAuto = nextModelId === AUTO_MODEL_ID || nextModelId === "auto";
        setUseAutoModel(isAuto);
        if (!isAuto) {
          setLastManualModelId(nextModelId);
        }

        const normalizedMode: ChatMode = (["agent", "plan", "ask", "edit"] as ChatMode[]).includes(
          nextModeId as ChatMode
        )
          ? (nextModeId as ChatMode)
          : "agent";
        setChatMode(normalizedMode);
        return;
      }

      if (msg.type === "auth.stateChange") {
        if (msg.isAuthenticated) {
          const currentConfig = (window as any).__AEP_CONFIG__ || {};
          if (msg.authToken) {
            (window as any).__AEP_CONFIG__ = {
              ...currentConfig,
              authToken: msg.authToken,
              orgId: msg.orgId ?? currentConfig.orgId,
              userId: msg.userId ?? currentConfig.userId,
            };
          }
          setAuthRequired(false);
          setAuthRequiredDetail("");
          if (pendingAuthRetryRef.current && lastSentRef.current && !sending) {
            pendingAuthRetryRef.current = false;
            showToast("Signed in. Retrying your last request…", "info");
            void handleSend(lastSentRef.current);
          } else if (pendingAuthRetryRef.current && lastSentRef.current && sending) {
            setTimeout(() => {
              if (!sending && pendingAuthRetryRef.current && lastSentRef.current) {
                pendingAuthRetryRef.current = false;
                showToast("Signed in. Retrying your last request…", "info");
                void handleSend(lastSentRef.current);
              }
            }, 300);
          }
        } else {
          const currentConfig = (window as any).__AEP_CONFIG__ || {};
          (window as any).__AEP_CONFIG__ = {
            ...currentConfig,
            authToken: undefined,
          };
        }
        return;
      }

      // NEW: inline toast from extension
      if (msg.type === 'toast' && msg.message) {
        showToast(msg.message, msg.kind || 'info');
        return;
      }

      // Handle LLM-generated action follow-up response
      // This is the dynamic, contextual response generated by the LLM after an action completes
      if (msg.type === 'actionFollowUp' && msg.followUpText) {
        // Append the LLM-generated follow-up to the existing assistant message
        setMessages((prev) => {
          const lastAssistantIndex = [...prev].reverse().findIndex(m => m.role === "assistant");
          if (lastAssistantIndex === -1) return prev;

          const actualIndex = prev.length - 1 - lastAssistantIndex;
          const updated = [...prev];
          const currentContent = updated[actualIndex].content;

          // Append the follow-up with a separator if needed
          const separator = currentContent.endsWith('\n') ? '\n' : '\n\n';
          updated[actualIndex] = {
            ...updated[actualIndex],
            content: currentContent + separator + "---\n\n" + msg.followUpText,
          };
          return updated;
        });
        return;
      }

      if (msg.type === "addAttachment" && msg.attachment) {
        const att = msg.attachment as AttachmentChipData;

        setAttachments((prev) => {
          const key = `${att.kind}:${att.path}:${(att as any).content?.length ?? 0}`;
          const exists = prev.some(
            (p) =>
              `${p.kind}:${p.path}:${(p as any).content?.length ?? 0}` === key
          );
          if (exists) return prev;
          return [...prev, att];
        });
      }

      if (msg.type === "clearAttachments") {
        setAttachments([]);
      }

      if (msg.type === "resetChat") {
        if (resetTimeoutRef.current) {
          clearTimeout(resetTimeoutRef.current);
          resetTimeoutRef.current = null;
        }
        if (pendingResetRef.current) {
          pendingResetRef.current = false;
          return;
        }
        const storedSeed = getStoredSessionSeed();
        startNewSession(storedSeed);
        return;
      }

      // Handle new conversation created by extension
      if (msg.type === "conversation.created") {
        console.log('[NaviChatPanel] 🆕 New conversation created:', msg.conversationId);
        const storedSeed = getStoredSessionSeed();
        startNewSession(storedSeed);
        showToast("New chat started", "info");
        return;
      }

      if (msg.type === "RUN_STARTED" && msg.runId) {
        console.log('[NaviChatPanel] 🏃 RUN_STARTED received:', msg.runId);
        setActivityEvents([]);
        setActivityFiles([]);
        setExpandedActivityFiles(new Set());
        setNarrativeLines([]); // Clear narrative stream for new run
        setActivityOpen(true);
        setActivityFilesOpen(false);
        // Clear per-action activities for new run
        setPerActionActivities(new Map());
        setPerActionNarratives(new Map());
        setPerActionOutputs(new Map());
        currentActionIndexRef.current = null;
        return;
      }

      if (msg.type === "RUN_FINISHED" && msg.runId) {
        console.log('[NaviChatPanel] 🏁 RUN_FINISHED received:', msg.runId);
        return;
      }

      if (msg.type === "ACTIVITY_EVENT_APPEND" && msg.event) {
        console.log('[NaviChatPanel] 📊 ACTIVITY_EVENT_APPEND received:', msg.event);
        const payload = msg.event as ActivityEventPayload;

        // Special handling for phase_end: find and update the corresponding phase_start
        if (payload.type === "phase_end") {
          setActivityEvents((prev) => {
            // Find the most recent running phase activity
            const runningPhaseIdx = prev.findIndex(
              (evt) => evt.status === "running" && evt.detail === "Phase started"
            );
            if (runningPhaseIdx >= 0) {
              const updated = [...prev];
              updated[runningPhaseIdx] = {
                ...updated[runningPhaseIdx],
                status: "done",
                detail: "Phase completed",
              };
              return updated;
            }
            return prev;
          });
          return;
        }

        const mapped = mapActivityPayload(payload);
        console.log('[NaviChatPanel] 📊 Mapped activity event:', mapped);
        if (mapped) {
          pushActivityEvent(mapped);
        }
        if (payload.type === "edit" && payload.path) {
          const diffStats = countUnifiedDiffStats(payload.diffUnified);
          const additions =
            typeof payload.stats?.added === "number"
              ? payload.stats.added
              : diffStats?.additions;
          const deletions =
            typeof payload.stats?.removed === "number"
              ? payload.stats.removed
              : diffStats?.deletions;
          upsertActivityFile({
            path: String(payload.path),
            additions,
            deletions,
            diff: payload.diffUnified,
            scope: "working",
            status: "done",
            lastTouched: nowIso(),
          });
        }
        return;
      }

      if (msg.type === "botMessage" && msg.text) {
        // Deduplicate: Check if we recently added a message with the same content
        // This prevents duplicate bubbles when the same message arrives from multiple sources
        const contentTrimmed = msg.text.trim();
        const now = Date.now();

        // Use the message ID from the extension if available, otherwise generate one
        const messageId = msg.messageId || makeMessageId("assistant");

        const assistantMessage: ChatMessage = {
          id: messageId,
          role: "assistant",
          content: msg.text,
          createdAt: nowIso(),
          actions: Array.isArray(msg.actions) ? msg.actions : undefined,
          agentRun: msg.agentRun,
          state: msg.state,
          // Intelligence fields (like Codex/Claude Code)
          thinking_steps: msg.thinking_steps,
          files_read: msg.files_read,
          project_type: msg.project_type,
          framework: msg.framework,
          warnings: msg.warnings,
          // NAVI V2: Approval flow fields
          requiresApproval: msg.requires_approval,
          planId: msg.plan_id,
          actionsWithRisk: msg.actions_with_risk,
        };

        setMessages((prev) => {
          // PHASE 1 FIX: Check for ANY streaming message to update instead of creating duplicate
          // This handles both empty placeholders AND messages filled via botMessageChunk
          const streamingIdx = prev.findIndex(
            (m) => m.role === "assistant" && m.isStreaming
          );

          if (streamingIdx !== -1) {
            // Update the streaming message instead of creating a new one
            console.log('[NaviChatPanel] Updating streaming message with final botMessage content');
            const updated = [...prev];
            updated[streamingIdx] = {
              ...updated[streamingIdx],
              id: messageId,
              content: msg.text,
              isStreaming: false,
              actions: Array.isArray(msg.actions) ? msg.actions : undefined,
              agentRun: msg.agentRun,
              state: msg.state,
              thinking_steps: msg.thinking_steps,
              files_read: msg.files_read,
              project_type: msg.project_type,
              framework: msg.framework,
              warnings: msg.warnings,
              requiresApproval: msg.requires_approval,
              planId: msg.plan_id,
              actionsWithRisk: msg.actions_with_risk,
            };
            return updated;
          }

          // Check for duplicate: same messageId or same content within 2 seconds
          const isDuplicate = prev.some((m) => {
            if (m.id === messageId) return true;
            if (m.role === "assistant" && m.content.trim() === contentTrimmed) {
              const msgTime = new Date(m.createdAt).getTime();
              return now - msgTime < 2000; // Within 2 seconds
            }
            return false;
          });

          if (isDuplicate) {
            console.log('[NaviChatPanel] Skipping duplicate botMessage:', contentTrimmed.substring(0, 50));
            return prev;
          }

          return [...prev, assistantMessage];
        });
        setSending(false);
        setIsAnalyzing(false);
        // Clean up progress message rotation
        if (progressIntervalRef.current) {
          progressIntervalRef.current();
          progressIntervalRef.current = null;
        }
        // Mark all running activity events as done when response completes
        setActivityEvents((prev) =>
          prev.map((evt) =>
            evt.status === "running" ? { ...evt, status: "done" } : evt
          )
        );
        // Clear the live progress ref so new requests can show progress
        lastLiveProgressRef.current = "";
        // PHASE 4: Clear retry activity ref on successful response
        currentRetryActivityRef.current = null;
        clearSendTimeout();

        const routingInfo = normalizeRoutingInfo(msg.routing || msg.context?.llm);
        if (routingInfo) {
          const resolvedName =
            routingInfo.modelName ||
            (routingInfo.modelId
              ? getModelLabel(routingInfo.modelId, modelLabelOverride || undefined)
              : undefined) ||
            (routingInfo.provider ? formatProviderLabel(routingInfo.provider) : undefined);
          setLastRouterInfo({
            ...routingInfo,
            modelName: resolvedName || routingInfo.modelName,
          });
        }

        if (Array.isArray(msg.files_read) && msg.files_read.length > 0) {
          msg.files_read.forEach((filePath: string) => {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "read",
              label: "Read file",
              detail: String(filePath),
              filePath: String(filePath),
              status: "done",
              timestamp: nowIso(),
            });
          });
        }

        // If this is an autonomous coding message, fetch the steps
        if (msg.agentRun?.mode === 'autonomous_coding' && msg.state?.task_id) {
          fetchAutonomousSteps(msg.state.task_id);
        }

        // If this is a project creation success or opening existing, open the project in VSCode
        if (
          (msg.agentRun?.mode === 'project_created' || msg.agentRun?.mode === 'open_existing_project') &&
          msg.agentRun?.project_path
        ) {
          const projectPath = msg.agentRun.project_path;
          console.log('[NAVI] Opening project in VSCode:', projectPath);

          // Send message to VSCode extension to open the folder
          (window as any).vscode?.postMessage({
            type: 'openFolder',
            folderPath: projectPath,
            newWindow: true,
          });
        }
      }

      if (msg.type === "botThinking") {
        const isThinking = msg.value === true;
        setSending(isThinking);
        if (isThinking) {
          // Track thinking state but don't push duplicate activity events
          // Real activities come from backend streaming (file_read, analysis, etc.)
          if (!thinkingActivityRef.current) {
            thinkingActivityRef.current = makeActivityId();
          }
        } else {
          if (thinkingActivityRef.current) {
            thinkingActivityRef.current = null;
          }
          clearSendTimeout();
        }
      }

      // Handle streaming message start - update existing placeholder or create new
      if (msg.type === "botMessageStart" && msg.messageId) {
        setMessages((prev) => {
          // Check if there's already a streaming assistant message (placeholder from handleSend)
          const existingStreamingIdx = prev.findIndex(
            (m) => m.role === "assistant" && m.isStreaming && m.content === ""
          );
          if (existingStreamingIdx >= 0) {
            // Update the existing placeholder with the actual message ID
            return prev.map((m, idx) =>
              idx === existingStreamingIdx
                ? { ...m, id: msg.messageId }
                : m
            );
          }
          // Fallback: create new streaming message if no placeholder exists
          return [...prev, {
            id: msg.messageId,
            role: "assistant" as ChatRole,
            content: "",
            createdAt: nowIso(),
            isStreaming: true,
          }];
        });
        // Don't clear activities here - they're already being populated from backend streaming
        // Activities will be cleared after response completes (in botMessageEnd handler)
        return;
      }

      // Handle streaming message chunk - update the streaming message content
      if (msg.type === "botMessageChunk" && msg.messageId && msg.fullContent !== undefined) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msg.messageId
              ? { ...m, content: msg.fullContent, isStreaming: true }
              : m
          )
        );
        return;
      }

      // Handle streaming message end - finalize the streaming message with actions
      if (msg.type === "botMessageEnd" && msg.messageId) {
        const messageId = msg.messageId;
        const incomingActions = Array.isArray(msg.actions) ? msg.actions : [];
        const msgText = msg.text;

        // Use setTimeout to ensure React has processed all pending state updates
        // This ensures refs have the latest values from useEffect syncing
        setTimeout(() => {
          // Store current activities, narratives, and thinking with the message so they persist after streaming
          // Use refs to get latest values (avoids stale closure issue with state)
          const currentActivities = [...activityEventsRef.current];
          const currentNarratives = [...narrativeLinesRef.current];
          const currentThinking = accumulatedThinkingRef.current;
          console.log('[NaviChatPanel] 📦 Storing for message:', currentActivities.length, 'activities,', currentNarratives.length, 'narratives,', currentThinking.length, 'chars thinking');

          setMessages((prev) =>
            prev.map((m) =>
              m.id === messageId
                ? {
                  ...m,
                  content: msgText || m.content,
                  isStreaming: false,
                  // Include actions from the streamed response
                  actions: incomingActions.length > 0 ? incomingActions : m.actions,
                  // Persist activities, narratives, and thinking for display after streaming ends
                  storedActivities: currentActivities,
                  storedNarratives: currentNarratives,
                  storedThinking: currentThinking || undefined,
                }
                : m
            )
          );

          // Mark all running activity events as done - keep them visible for the user
          setActivityEvents((prev) =>
            prev.map((evt) =>
              evt.status === "running" ? { ...evt, status: "done" } : evt
            )
          );
        }, 0);

        setSending(false);
        setIsAnalyzing(false);
        // Don't clear activities - keep them visible so user can see what was done
        // Activities will be cleared when a new message is sent
        lastLiveProgressRef.current = "";
        clearSendTimeout();

        // TASK COMPLETION: Now handled by backend via task_complete event
        // The backend (streaming_agent.py) uses TaskContext to track:
        // - Tool calls started/completed
        // - File modifications/creations
        // - Command executions and their success
        // - Verification results
        //
        // The frontend receives a task_complete event with:
        // - success: boolean - Whether task succeeded
        // - state: TaskState - Current state (complete, failed, idle)
        // - is_actionable_task: boolean - Whether task had file changes or commands
        //
        // This replaces heuristic regex-based detection which was error-prone.
        // The Task Complete UI is now shown ONLY when:
        // 1. Backend emits task_complete with success=true
        // 2. is_actionable_task=true (file changes or commands run)
        //
        // See the "task_complete" event handler above for the implementation.

        // AUTO-EXECUTE: If auto-execute mode is enabled, automatically approve and execute all actions
        if (autoExecuteModeRef.current && incomingActions.length > 0) {
          console.log('[NaviChatPanel] 🚀 Auto-executing', incomingActions.length, 'actions in Agent Full Access mode');

          // Show activity notification
          pushActivityEvent({
            id: makeActivityId(),
            kind: 'info',
            label: 'Auto-executing actions',
            detail: `Running ${incomingActions.length} action(s) automatically`,
            status: 'running',
            timestamp: nowIso(),
          });

          // Open activity panel to show live progress
          if (activityPanelState && !activityPanelState.isVisible) {
            console.log('[NaviChatPanel] Opening activity panel for auto-execution');
            activityPanelState.setIsVisible(true);
          }

          // Execute each action sequentially with a small delay between them
          setTimeout(() => {
            incomingActions.forEach((action: any, idx: number) => {
              setTimeout(() => {
                console.log(`[NaviChatPanel] Auto-executing action ${idx + 1}/${incomingActions.length}:`, action.type);
                handleApproveAction(incomingActions, idx);
              }, idx * 200); // Stagger execution by 200ms
            });
          }, 500); // Initial delay of 500ms
        }

        return;
      }

      // Handle router info from streaming endpoint (mode, model, task type)
      if (msg.type === "navi.router.info") {
        const { provider, model, mode, task_type, auto_execute } = msg;
        const autoExecuteEnabled = auto_execute || false;

        setLastRouterInfo({
          source: "auto",
          provider: provider || "openai",
          modelId: model ? `${provider}/${model}` : undefined,
          modelName: model || "auto",
          taskType: task_type || "code_generation",
          mode: mode || "agent",
          autoExecute: autoExecuteEnabled,
        });

        // Store auto-execute state for action processing
        autoExecuteModeRef.current = autoExecuteEnabled;

        console.log('[NaviChatPanel] 🤖 Auto-execute mode:', autoExecuteEnabled);
        return;
      }

      // Handle next_steps from streaming endpoint
      if (msg.type === "navi.next_steps") {
        const nextSteps = msg.next_steps;
        if (Array.isArray(nextSteps) && nextSteps.length > 0) {
          console.log('[NaviChatPanel] 📋 Next steps received:', nextSteps);
          setLastNextSteps(nextSteps);
        }
        return;
      }

      // Handle execution plan events from backend
      if (msg.type === "plan_start" && msg.data) {
        console.log('[NaviChatPanel] ⚡ Execution plan started:', msg.data.plan_id);
        console.log('[NaviChatPanel] 📋 Plan steps:', msg.data.steps);
        const rawSteps = Array.isArray(msg.data.steps) ? msg.data.steps : [];
        const normalizedSteps: ExecutionPlanStep[] = rawSteps.map((s: any, idx: number) => {
          if (typeof s === 'string') {
            return {
              index: idx + 1,
              title: s,
              status: 'pending' as const,
            };
          }
          const title =
            s?.title ||
            s?.label ||
            s?.description ||
            `Step ${idx + 1}`;
          const detail = s?.detail || s?.description;
          const index =
            typeof s?.index === 'number'
              ? s.index
              : typeof s?.id === 'number'
                ? s.id
                : idx + 1;
          return {
            index,
            title,
            detail,
            status: 'pending' as const,
          };
        });
        const nextPlan = {
          planId: msg.data.plan_id,
          steps: normalizedSteps,
          isExecuting: true,
        };
        executionPlanRef.current = nextPlan;
        setExecutionPlan(nextPlan);
        if (activityPanel) {
          const steps = normalizedSteps.map((s, idx) => {
            const cleanTitle = (s.title || '').trim();
            const cleanDetail = (s.detail || '').trim();
            return {
              description: cleanDetail && cleanDetail !== cleanTitle
                ? cleanDetail
                : cleanTitle || `Step ${idx + 1}`,
            };
          });
          activityPanel.initializeSteps(
            {
              mode: 'autonomous_coding',
              total_steps: steps.length,
              current_step: 0,
            },
            steps
          );
        }
        return;
      }

      // Log ALL step_update messages for debugging
      if (msg.type === "step_update") {
        console.log('[NaviChatPanel] 📨 Step update message received:', {
          step_index: msg.data?.step_index,
          status: msg.data?.status,
          plan_id: msg.data?.plan_id,
          current_plan: executionPlan?.planId,
          matches: executionPlan?.planId === msg.data?.plan_id
        });
      }

      if (msg.type === "step_update" && msg.data && executionPlanRef.current?.planId === msg.data.plan_id) {
        console.log('[NaviChatPanel] ⚡ Step update PROCESSING:', {
          step_index: msg.data.step_index,
          status: msg.data.status,
          output: msg.data.output,
          error: msg.data.error
        });
        setExecutionPlan((prev) => {
          if (!prev) {
            console.warn('[NaviChatPanel] ⚠️ Step update received but no execution plan exists');
            return null;
          }
          // Map backend status to frontend status
          const mapStatus = (backendStatus: string) => {
            switch (backendStatus) {
              case 'running': return 'running'; // Keep as 'running' for ExecutionPlanStepper
              case 'completed': return 'completed';
              case 'failed': return 'error'; // Map 'failed' to 'error' for ExecutionPlanStepper
              default: return backendStatus as any;
            }
          };
          const updatedSteps = prev.steps.map((s, i) =>
            i === msg.data.step_index
              ? { ...s, status: mapStatus(msg.data.status), output: msg.data.output, error: msg.data.error }
              : s
          );
          console.log('[NaviChatPanel] 📊 Updated steps:', updatedSteps);
          // Also update activity panel if available
          if (activityPanel) {
            if (msg.data.status === 'running') {
              activityPanel.updateStep(msg.data.step_index);
            } else if (msg.data.status === 'completed') {
              activityPanel.completeStep(msg.data.step_index);
            } else if (msg.data.status === 'failed') {
              activityPanel.updateStepStatus(msg.data.step_index, 'failed');
            }
          }
          return {
            ...prev,
            steps: updatedSteps,
          };
        });
        return;
      }

      if (msg.type === "plan_complete" && msg.data) {
        console.log('[NaviChatPanel] ⚡ Execution plan completed:', msg.data.plan_id);
        setExecutionPlan((prev) => (prev ? { ...prev, isExecuting: false } : null));
        return;
      }

      // Handle task completion with summary
      if (msg.type === "navi.task.complete") {
        const summary = msg.summary || msg;
        console.log('[NaviChatPanel] ✅ Task complete received:', summary);

        // Build file list from activity files
        const filesList = activityFiles.map(f => ({
          path: f.path,
          action: (f.status === 'done' ? 'modified' : 'modified') as 'created' | 'modified' | 'read',
          additions: f.additions,
          deletions: f.deletions,
        }));

        // Calculate actual file changes
        const filesModifiedCount = summary.files_modified || filesList.filter(f => f.action === 'modified').length;
        const filesCreatedCount = summary.files_created || filesList.filter(f => f.action === 'created').length;
        const hasFileChanges = filesModifiedCount > 0 || filesCreatedCount > 0 || filesList.length > 0;

        // ONLY show Task Complete UI if there were actual file changes
        // This prevents showing "Task Complete" when NAVI only provided analysis
        if (!hasFileChanges) {
          console.log('[NaviChatPanel] ⏳ No file changes detected - NOT showing Task Complete UI (analysis-only response)');
          // Still update next steps if provided
          if (Array.isArray(summary.next_steps) && summary.next_steps.length > 0) {
            setLastNextSteps(summary.next_steps);
          }
          return;
        }

        setTaskSummary({
          filesRead: summary.files_read || 0,
          filesModified: filesModifiedCount,
          filesCreated: filesCreatedCount,
          iterations: summary.iterations || 1,
          verificationPassed: summary.verification_passed ?? null,
          nextSteps: Array.isArray(summary.next_steps) ? summary.next_steps : [],
          summaryText: summary.summary_text || summary.message,
          filesList: filesList.length > 0 ? filesList : undefined,
          verificationDetails: summary.verification_details,
        });

        // Also update next steps if provided
        if (Array.isArray(summary.next_steps) && summary.next_steps.length > 0) {
          setLastNextSteps(summary.next_steps);
        }
        return;
      }

      // Handle build verification events from backend
      // This is emitted after file changes to verify the build/typecheck passes
      if (msg.type === "build_verification" && msg.build_verification) {
        const buildResult = msg.build_verification;
        console.log('[NaviChatPanel] 🔨 Build verification result:', buildResult);

        setBuildVerification(buildResult);

        // Add activity event for build verification
        if (!buildResult.skipped) {
          pushActivityEvent({
            id: makeActivityId(),
            kind: buildResult.success ? 'success' : 'error',
            label: buildResult.command_name || 'Build verification',
            detail: buildResult.success
              ? 'Build passed successfully'
              : `Build failed: ${buildResult.errors?.slice(0, 2).join(', ') || 'Unknown error'}`,
            status: 'done',
            timestamp: nowIso(),
          });
        }
        return;
      }

      // Handle BACKEND-DRIVEN task completion (proper solution)
      // This event is emitted by streaming_agent.py with semantic completion status
      // It replaces heuristic regex-based detection in the "done" handler
      if (msg.type === "task_complete" && msg.task_complete) {
        const taskData = msg.task_complete;
        console.log('[NaviChatPanel] 🎯 Backend task_complete event:', taskData);

        // ONLY show Task Complete UI if:
        // 1. Task was successful
        // 2. It was an actionable task (file changes or commands run)
        if (taskData.success && taskData.is_actionable_task) {
          const summary = taskData.summary || {};
          const taskState = summary.task_state || {};

          // Build file list from activity files
          const filesList = activityFiles.map(f => ({
            path: f.path,
            action: (f.status === 'done' ? 'modified' : 'modified') as 'created' | 'modified' | 'read',
            additions: f.additions,
            deletions: f.deletions,
          }));

          // Get build verification from event payload or existing state
          const buildResult = taskData.build_verification || buildVerification;
          const buildPassed = buildResult ? (buildResult.skipped || buildResult.success) : null;

          // Create verification details if we have build info
          const verificationDetails = buildResult && !buildResult.skipped ? {
            build: {
              passed: buildResult.success,
              errors: buildResult.errors || [],
            },
          } : undefined;

          // Generate appropriate summary text
          let summaryText = 'Task completed successfully.';
          if (buildResult && !buildResult.skipped) {
            if (buildResult.success) {
              summaryText = `Task completed. ${buildResult.command_name || 'Build'} passed.`;
            } else {
              summaryText = `Task completed with ${buildResult.errors?.length || 0} build error(s).`;
            }
          }

          setTaskSummary({
            filesRead: taskState.files_modified?.length || 0,
            filesModified: summary.files_modified || taskState.files_modified?.length || filesList.length,
            filesCreated: summary.files_created || taskState.files_created?.length || 0,
            iterations: 1,
            verificationPassed: buildPassed,
            nextSteps: [],
            summaryText,
            filesList: filesList.length > 0 ? filesList : undefined,
            verificationDetails,
          });

          // Clear build verification state after using it
          setBuildVerification(null);

          console.log('[NaviChatPanel] ✅ Showing Task Complete UI (backend-verified)', {
            buildResult,
            verificationDetails,
          });
        } else {
          console.log('[NaviChatPanel] ⏳ Task not complete or not actionable:', {
            success: taskData.success,
            state: taskData.state,
            is_actionable_task: taskData.is_actionable_task
          });
          // Don't show Task Complete UI - task either failed or was just informational
        }
        return;
      }

      // Handle real-time LLM thinking/reasoning stream
      if (msg.type === "navi.thinking") {
        const thinkingText = msg.thinking || "";
        console.log('[NaviChatPanel] 🧠 Thinking received:', thinkingText.substring(0, 100) + '...');

        // Accumulate full thinking text for expandable display
        setAccumulatedThinking(prev => prev + thinkingText);
        setIsThinkingComplete(false);

        // Update or create thinking activity with the streamed content
        setActivityEvents((prev) => {
          const thinkingIdx = prev.findIndex(
            (evt) => evt.kind === "thinking" && evt.status === "running"
          );

          if (thinkingIdx >= 0) {
            // Append to existing thinking activity
            const updated = [...prev];
            const existing = updated[thinkingIdx];
            updated[thinkingIdx] = {
              ...existing,
              // Append new thinking text, limit to last ~500 chars for display
              detail: ((existing.detail || "") + thinkingText).slice(-500),
            };
            return updated;
          }

          // Create new thinking activity if none exists
          return [
            ...prev,
            {
              id: makeActivityId(),
              kind: "thinking" as const,
              label: "Thinking",
              detail: thinkingText.slice(-500),
              status: "running" as const,
              timestamp: nowIso(),
            },
          ];
        });
        return;
      }

      // Handle thinking complete event
      if (msg.type === "navi.thinking.complete" || msg.type === "thinking_complete") {
        setIsThinkingComplete(true);
        // Mark thinking activity as done
        setActivityEvents((prev) =>
          prev.map((evt) =>
            evt.kind === "thinking" && evt.status === "running"
              ? { ...evt, status: "done" as const }
              : evt
          )
        );
        return;
      }

      // Handle streaming narrative text for actions (Cline/Claude-like conversational output)
      if (msg.type === "navi.narrative" || msg.type === "action.narrative") {
        const narrativeText = msg.text || msg.narrative || "";
        const actionIndex = typeof msg.actionIndex === 'number' ? msg.actionIndex : currentActionIndexRef.current;
        console.log('[NaviChatPanel] 💬 Narrative received:', narrativeText.substring(0, 100), 'for action:', actionIndex);

        // Add to the live narrative stream (Claude Code-like display)
        if (narrativeText) {
          setNarrativeLines((prev) => [
            ...prev,
            {
              id: makeActivityId(),
              text: narrativeText,
              // Use backend timestamp if available for accurate chronological ordering
              timestamp: msg.timestamp || nowIso(),
            },
          ]);
        }

        // Also add to per-action narratives if we have an action context
        if (narrativeText && actionIndex !== null) {
          setPerActionNarratives((prev) => {
            const next = new Map(prev);
            const existing = next.get(actionIndex) || [];
            next.set(actionIndex, [
              ...existing,
              {
                id: makeActivityId(),
                text: narrativeText,
                // Use backend timestamp if available for accurate chronological ordering
                timestamp: msg.timestamp || nowIso(),
              },
            ]);
            return next;
          });
        }
        return;
      }

      if (msg.type === "command.start" && msg.commandId && msg.command) {
        const messageId = makeMessageId("system");
        const command = String(msg.command);
        const terminalId = String(msg.commandId);
        const cwd = typeof msg.cwd === "string" ? msg.cwd : undefined;
        const meta =
          msg.meta && typeof msg.meta === "object" ? msg.meta : undefined;
        const actionIndex = currentActionIndexRef.current;
        let activityStepIndex =
          activityPanel &&
          typeof actionIndex === 'number' &&
          actionIndex >= 0 &&
          actionIndex < activityPanel.steps.length
            ? actionIndex
            : activityPanel &&
              typeof activityPanel.currentStep === 'number' &&
              activityPanel.currentStep >= 0 &&
              activityPanel.currentStep < activityPanel.steps.length
              ? activityPanel.currentStep
              : undefined;
        if (
          activityStepIndex === undefined &&
          activityPanel &&
          activityPanel.steps.length > 0
        ) {
          activityStepIndex = 0;
        }
        const entry = {
          messageId,
          command,
          cwd,
          output: "",
          truncated: false,
          status: "running" as const,
          meta,
          actionIndex, // Track which action this command belongs to
          activityStepIndex,
        };
        commandStateRef.current.set(msg.commandId, entry);
        const activityId = makeActivityId();
        commandActivityRef.current.set(msg.commandId, activityId);

        const newActivity: ActivityEvent = {
          id: activityId,
          kind: "command",
          label: "Running command",
          detail: command,
          status: "running",
          timestamp: nowIso(),
        };
        pushActivityEvent(newActivity);

        // Also track in per-action activities for inline display
        if (actionIndex !== null) {
          setPerActionActivities((prev) => {
            const next = new Map(prev);
            const existing = next.get(actionIndex) || [];
            next.set(actionIndex, [...existing, newActivity]);
            return next;
          });
        }
        // Don't add command output to chat messages - keep it in terminal panel only
        // The command output will be shown in the terminal entries and activity stream
        // This prevents cluttering the chat with verbose terminal output
        setTerminalEntries((prev) => [
          ...prev,
          {
            id: terminalId,
            command,
            cwd,
            output: "",
            status: "running" as const,
            startedAt: nowIso(),
          },
        ].slice(-MAX_TERMINAL_ENTRIES));

        if (activityPanel && activityStepIndex !== undefined) {
          activityPanel.upsertCommand(activityStepIndex, terminalId, {
            command,
            status: "running",
          });
        }
        return;
      }

      if (msg.type === "command.output" && msg.commandId && msg.text) {
        const entry = commandStateRef.current.get(msg.commandId);
        if (!entry) return;
        const terminalId = String(msg.commandId);
        const actionIndex = entry.actionIndex ?? null;
        const stream = msg.stream === "stderr" ? "stderr" : "stdout";
        const next = appendWithLimit(entry.output, String(msg.text), MAX_COMMAND_OUTPUT);
        // CRITICAL: Update entry.output so it's available for self-healing!
        entry.output = next.text;
        entry.truncated = entry.truncated || next.truncated;
        // Also update terminal entries for UI display
        setTerminalEntries((prev) =>
          prev.map((terminalEntry) => {
            if (terminalEntry.id !== terminalId) return terminalEntry;
            return {
              ...terminalEntry,
              output: next.text,
            };
          })
        );
        // Track output by action index for inline display in NaviActionRunner
        if (actionIndex !== null) {
          setPerActionOutputs((prev) => {
            const updated = new Map(prev);
            updated.set(actionIndex, next.text);
            return updated;
          });
        }

        if (activityPanel && entry.activityStepIndex !== undefined) {
          activityPanel.appendCommandOutput(
            entry.activityStepIndex,
            terminalId,
            String(msg.text),
            stream
          );
        } else if (activityPanel && activityPanel.steps.length > 0) {
          const fallbackStep = activityPanel.currentStep ?? 0;
          activityPanel.upsertCommand(fallbackStep, terminalId, {
            command: entry.command,
            status: entry.status,
          });
          activityPanel.appendCommandOutput(
            fallbackStep,
            terminalId,
            String(msg.text),
            stream
          );
        }
        // IMPORTANT: Don't return early - we're updating entry which is a ref!
        // But we can return since no other processing needed
        return;
      }

      if (msg.type === "command.done" && msg.commandId) {
        const entry = commandStateRef.current.get(msg.commandId);
        if (!entry) return;
        const terminalId = String(msg.commandId);
        const actionIndex = entry.actionIndex ?? null;
        entry.status = "done";
        entry.exitCode =
          typeof msg.exitCode === "number" ? msg.exitCode : entry.exitCode;
        entry.durationMs =
          typeof msg.durationMs === "number" ? msg.durationMs : entry.durationMs;
        // Include any final output from the done message (stdout/stderr)
        if (msg.stdout) {
          const next = appendWithLimit(entry.output, String(msg.stdout), MAX_COMMAND_OUTPUT);
          entry.output = next.text;
          entry.truncated = entry.truncated || next.truncated;
        }
        if (msg.stderr) {
          const next = appendWithLimit(entry.output, String(msg.stderr), MAX_COMMAND_OUTPUT);
          entry.output = next.text;
          entry.truncated = entry.truncated || next.truncated;
        }

        // CRITICAL FIX: Trigger self-healing when command fails (non-zero exit code)
        // MUST happen AFTER we've added final stdout/stderr to entry.output!
        const exitCode = entry.exitCode;
        if (exitCode !== undefined && exitCode !== 0) {
          // Extract last few lines of output as error preview
          const outputLines = entry.output.trim().split('\n');
          const errorPreview = outputLines.slice(-5).join('\n'); // Last 5 lines
          const errorActivity: ActivityEvent = {
            id: makeActivityId(),
            kind: "error",
            label: `Command failed (exit ${exitCode})`,
            detail: errorPreview.substring(0, 300),
            status: "error",
            timestamp: nowIso(),
          };
          pushActivityEvent(errorActivity);

          // Also track error in per-action activities for inline display
          if (actionIndex !== null) {
            setPerActionActivities((prev) => {
              const next = new Map(prev);
              const existing = next.get(actionIndex) || [];
              next.set(actionIndex, [...existing, errorActivity]);
              return next;
            });
          }

          // SELF-HEALING: Find the action that triggered this command and trigger autonomous debugging
          if (actionIndex !== null) {
            // Find the message with this action
            const messageWithAction = [...messages].reverse().find(m =>
              m.actions && Array.isArray(m.actions) && m.actions.length > actionIndex
            );

            if (messageWithAction && messageWithAction.actions) {
              const action = messageWithAction.actions[actionIndex];
              if (action && action.type === 'runCommand') {
                console.log(`[NAVI] 🔧 Command failed with exit code ${exitCode}, triggering self-healing...`);
                // Trigger self-healing with full command output
                // Use entry.output (accumulated output) or msg data as fallback
                // DEBUG: Log all available error sources
                console.log(`[NAVI] 📋 DEBUG entry.output: "${entry.output?.substring(0, 200)}..." (${entry.output?.length || 0} chars)`);
                console.log(`[NAVI] 📋 DEBUG msg.stdout: "${msg.stdout?.substring(0, 200)}..." (${msg.stdout?.length || 0} chars)`);
                console.log(`[NAVI] 📋 DEBUG msg.stderr: "${msg.stderr?.substring(0, 200)}..." (${msg.stderr?.length || 0} chars)`);

                // Combine ALL sources - entry.output may have streaming output, msg has final output
                const combinedOutput = [
                  entry.output || '',
                  msg.stdout || '',
                  msg.stderr || ''
                ].filter(Boolean).join('\n').trim();

                const errorOutput = combinedOutput || `Command '${action.command}' failed with exit code ${exitCode}. No detailed error output was captured.`;
                console.log(`[NAVI] 📋 Final error context length: ${errorOutput.length} chars`);
                triggerSelfHealing(action, errorOutput, exitCode);
              }
            }
          }
        }

        // Update the activity event with final status and output
        const activityId = commandActivityRef.current.get(msg.commandId);
        const finalStatus = entry.exitCode !== undefined && entry.exitCode !== 0 ? "error" : "done";
        if (activityId) {
          setActivityEvents((prev) =>
            prev.map((event) =>
              event.id === activityId
                ? {
                  ...event,
                  status: finalStatus as "running" | "done" | "error",
                  output: entry.output, // Include the command output
                  exitCode: entry.exitCode,
                }
                : event
            )
          );

          // Also update per-action activities for inline display
          if (actionIndex !== null) {
            setPerActionActivities((prev) => {
              const next = new Map(prev);
              const existing = next.get(actionIndex) || [];
              const updatedActivities = existing.map((evt) =>
                evt.id === activityId
                  ? { ...evt, status: finalStatus as "running" | "done" | "error", output: entry.output, exitCode: entry.exitCode }
                  : evt
              );
              next.set(actionIndex, updatedActivities);
              return next;
            });
          }

          // Also update storedActivities on messages (for display after streaming ends)
          setMessages((prev) =>
            prev.map((m) => {
              if (m.storedActivities && m.storedActivities.some((a) => a.id === activityId)) {
                return {
                  ...m,
                  storedActivities: m.storedActivities.map((a) =>
                    a.id === activityId
                      ? { ...a, status: finalStatus as "running" | "done" | "error", output: entry.output, exitCode: entry.exitCode }
                      : a
                  ),
                };
              }
              return m;
            })
          );

          commandActivityRef.current.delete(msg.commandId);
        }

        reportCoverageIfNeeded(entry);
        if (activityPanel && entry.activityStepIndex !== undefined) {
          activityPanel.updateCommandStatus(
            entry.activityStepIndex,
            terminalId,
            finalStatus,
            entry.exitCode
          );
        } else if (activityPanel && activityPanel.steps.length > 0) {
          const fallbackStep = activityPanel.currentStep ?? 0;
          activityPanel.upsertCommand(fallbackStep, terminalId, {
            command: entry.command,
            status: entry.status,
          });
          activityPanel.updateCommandStatus(
            fallbackStep,
            terminalId,
            finalStatus,
            entry.exitCode
          );
        }
        return;
      }

      if (msg.type === "command.error" && msg.commandId) {
        const entry = commandStateRef.current.get(msg.commandId);
        if (!entry) return;
        const terminalId = String(msg.commandId);
        entry.status = "error";
        const errorText = msg.error ? String(msg.error) : "Command failed";
        const next = appendWithLimit(
          entry.output,
          `\n${errorText}`,
          MAX_COMMAND_OUTPUT
        );
        entry.output = next.text;
        entry.truncated = entry.truncated || next.truncated;
        const content = buildCommandMessage({
          command: entry.command,
          cwd: entry.cwd,
          output: entry.output,
          status: entry.status,
          truncated: entry.truncated,
          meta: entry.meta,
        });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === entry.messageId ? { ...m, content } : m
          )
        );
        setTerminalEntries((prev) =>
          prev.map((terminalEntry) => {
            if (terminalEntry.id !== terminalId) return terminalEntry;
            return {
              ...terminalEntry,
              output: next.text,
              status: "error",
            };
          })
        );
        const activityId = commandActivityRef.current.get(msg.commandId);
        const actionIndex = entry.actionIndex ?? null;
        if (activityId) {
          setActivityEvents((prev) =>
            prev.map((event) =>
              event.id === activityId
                ? {
                  ...event,
                  label: "Command failed",
                  detail: entry.command,
                  status: "error",
                  timestamp: nowIso(),
                }
                : event
            )
          );

          // Also update per-action activities for inline display
          if (actionIndex !== null) {
            setPerActionActivities((prev) => {
              const next = new Map(prev);
              const existing = next.get(actionIndex) || [];
              const updatedActivities = existing.map((evt) =>
                evt.id === activityId
                  ? { ...evt, label: "Command failed", detail: entry.command, status: "error" as const, timestamp: nowIso() }
                  : evt
              );
              next.set(actionIndex, updatedActivities);
              return next;
            });
          }

          commandActivityRef.current.delete(msg.commandId);
        } else {
          const errorActivity: ActivityEvent = {
            id: makeActivityId(),
            kind: "command",
            label: "Command failed",
            detail: entry.command,
            status: "error",
            timestamp: nowIso(),
          };
          pushActivityEvent(errorActivity);

          // Also track in per-action activities
          if (actionIndex !== null) {
            setPerActionActivities((prev) => {
              const next = new Map(prev);
              const existing = next.get(actionIndex) || [];
              next.set(actionIndex, [...existing, errorActivity]);
              return next;
            });
          }
        }
        commandStateRef.current.delete(msg.commandId);
        if (activityPanelState && entry.activityStepIndex !== undefined) {
          activityPanelState.appendCommandOutput(
            entry.activityStepIndex,
            terminalId,
            `\n${errorText}`,
            "stderr"
          );
          activityPanelState.updateCommandStatus(
            entry.activityStepIndex,
            terminalId,
            "error",
            entry.exitCode
          );
        } else if (activityPanelState && activityPanelState.steps.length > 0) {
          const fallbackStep = activityPanelState.currentStep ?? 0;
          activityPanelState.upsertCommand(fallbackStep, terminalId, {
            command: entry.command,
            status: entry.status,
          });
          activityPanelState.appendCommandOutput(
            fallbackStep,
            terminalId,
            `\n${errorText}`,
            "stderr"
          );
          activityPanelState.updateCommandStatus(
            fallbackStep,
            terminalId,
            "error",
            entry.exitCode
          );
        }
        return;
      }

      if (msg.type === "error") {
        const errorText =
          msg.error ||
          msg.message ||
          msg.text ||
          "Navi hit an error while processing your request.";

        // FIX: Only append to assistant message if it's a response to the CURRENT request
        // Otherwise create a new error message to avoid appending to old responses
        setMessages((prev) => {
          // Find the last user message (current request)
          const lastUserIndex = [...prev].reverse().findIndex(m => m.role === "user");
          const lastAssistantIndex = [...prev].reverse().findIndex(m => m.role === "assistant");

          // If there's an assistant message AND it comes AFTER the last user message,
          // append the error to it (it's the response to current request, maybe partial)
          if (lastAssistantIndex !== -1 && lastUserIndex !== -1) {
            const actualAssistantIndex = prev.length - 1 - lastAssistantIndex;
            const actualUserIndex = prev.length - 1 - lastUserIndex;

            if (actualAssistantIndex > actualUserIndex) {
              // Assistant message is after user message - append error to it
              const errorSuffix = `\n\n---\n⚠️ **Error:** ${errorText}`;
              const updated = [...prev];
              updated[actualAssistantIndex] = {
                ...updated[actualAssistantIndex],
                content: updated[actualAssistantIndex].content + errorSuffix,
              };
              return updated;
            }
          }

          // No assistant response for current request yet - create new error message
          return [...prev, {
            id: makeMessageId("assistant"),
            role: "assistant" as const,
            content: `⚠️ **Error:** ${errorText}`,
            createdAt: nowIso(),
          }];
        });

        setSending(false);
        clearSendTimeout();
        showToast(errorText, "error");
        pushActivityEvent({
          id: makeActivityId(),
          kind: "error",
          label: "Error",
          detail: String(errorText),
          status: "error",
          timestamp: nowIso(),
        });
        return;
      }

      // Handle command consent requests
      if (msg.type === "command.consent_required" && msg.data) {
        console.log("[NaviChatPanel] 🔐 Consent required:", msg.data.command);
        const consentRequest: CommandConsentRequest = {
          consent_id: msg.data.consent_id,
          command: msg.data.command,
          shell: msg.data.shell || "bash",
          cwd: msg.data.cwd,
          danger_level: msg.data.danger_level,
          warning: msg.data.warning,
          consequences: msg.data.consequences || [],
          alternatives: msg.data.alternatives || [],
          rollback_possible: msg.data.rollback_possible || false,
          timestamp: msg.timestamp || new Date().toISOString(),
        };
        setPendingConsents((prev) => new Map(prev).set(consentRequest.consent_id, consentRequest));
        return;
      }

      // Handle real-time command output streaming
      if (msg.type === "command.output") {
        const outputLine = msg.line;
        const stream = msg.stream; // 'stdout' or 'stderr'

        // Append to current bot message content (streamed output visible in real-time)
        setMessages((prevMessages) => {
          const updatedMessages = [...prevMessages];
          const lastMessage = updatedMessages[updatedMessages.length - 1];

          if (lastMessage && lastMessage.role === "assistant") {
            const prefix = stream === "stderr" ? "⚠️ " : "";
            const newLine = `${prefix}${outputLine}`;

            // Add to content with code block formatting for terminal output
            if (!lastMessage.content.includes("```")) {
              lastMessage.content += "\n```bash\n";
            }
            lastMessage.content += newLine + "\n";
          }

          return updatedMessages;
        });
        return;
      }

      // Handle action execution start
      if (msg.type === "action.start" && msg.action) {
        const action = msg.action;
        const actionIndex = typeof msg.actionIndex === 'number' ? msg.actionIndex : null;
        const actionType = action.type === "runCommand" ? "command" :
          action.type === "createFile" ? "file creation" :
            action.type === "editFile" ? "file edit" :
              "action";

        const detail = action.command || action.filePath || action.description || "";

        // Track current action index for associating activities
        currentActionIndexRef.current = actionIndex;

        // Add to execution plan steps
        const stepId = action.id || `step-${actionIndex ?? Date.now()}`;
        const stepTitle = action.type === "runCommand"
          ? `Run: ${(action.command || "").slice(0, 40)}${(action.command || "").length > 40 ? '...' : ''}`
          : action.type === "createFile"
            ? `Create: ${action.filePath?.split('/').pop() || 'file'}`
            : action.type === "editFile"
              ? `Edit: ${action.filePath?.split('/').pop() || 'file'}`
              : action.description || "Action";

        setExecutionSteps((prev) => {
          // Don't add duplicate steps
          if (prev.some((s) => s.id === stepId)) {
            return prev.map((s) => s.id === stepId ? { ...s, status: 'running' } : s);
          }
          return [...prev, { id: stepId, title: stepTitle, status: 'running' as const, description: detail }];
        });
        // Auto-expand when first step starts
        setPlanCollapsed(false);

        showToast(`Starting ${actionType}: ${detail}`, "info");
        if (action.type !== "runCommand") {
          const actionIndexKey = msg.actionIndex !== undefined ? String(msg.actionIndex) : undefined;
          const actionKey = String(action.id || actionIndexKey || `${action.type}-${Date.now()}`);
          const activityId = makeActivityId();
          actionActivityRef.current.set(actionKey, activityId);
          const activityKind =
            action.type === "createFile"
              ? "create"
              : action.type === "editFile"
                ? "edit"
                : "info";

          const newActivity: ActivityEvent = {
            id: activityId,
            kind: activityKind,
            label:
              activityKind === "create"
                ? "Creating file"
                : activityKind === "edit"
                  ? "Editing file"
                  : "Running action",
            detail: detail || actionType,
            filePath: action.filePath,
            status: "running",
            timestamp: nowIso(),
          };

          pushActivityEvent(newActivity);

          // Also track in per-action activities for inline display
          if (actionIndex !== null) {
            setPerActionActivities((prev) => {
              const next = new Map(prev);
              const existing = next.get(actionIndex) || [];
              next.set(actionIndex, [...existing, newActivity]);
              return next;
            });
          }

          if (action.filePath) {
            upsertActivityFile({
              path: String(action.filePath),
              status: action.type === "createFile" ? "pending" : "editing",
              lastTouched: nowIso(),
            });
          }
        }
        recordActionStart();
        return;
      }

      // Handle action execution complete
      if (msg.type === "action.complete") {
        const { action, success, message, data } = msg;

        // Update execution plan step status
        const stepId = action.id || `step-${msg.actionIndex ?? 'unknown'}`;
        setExecutionSteps((prev) =>
          prev.map((s) =>
            s.id === stepId ? { ...s, status: success ? 'done' : 'error' } : s
          )
        );
        // Briefly expand to show completion, then collapse
        setPlanCollapsed(false);
        setTimeout(() => setPlanCollapsed(true), 2000);

        // NaviActionRunner handles its own state updates via message listener
        // We just need to show completion summary in chat

        if (success) {
          const diffStats = data?.diffStats || {};
          const diffUnified = data?.diffUnified || action.diff || action.diffUnified;
          const computedStats = countUnifiedDiffStats(diffUnified);
          const isCreateOperation =
            action.type === "createFile" ||
            action.operation === "create" ||
            action.operation === "write" ||
            action.operation === "add";
          const hasInlineContent =
            typeof action.content === "string" && action.content.length > 0;
          let additions =
            typeof diffStats.additions === "number"
              ? diffStats.additions
              : computedStats?.additions;
          let deletions =
            typeof diffStats.deletions === "number"
              ? diffStats.deletions
              : computedStats?.deletions;

          if (isCreateOperation) {
            if (typeof additions !== "number" && hasInlineContent) {
              additions = countLines(action.content);
            }
            if (typeof additions === "number" && typeof deletions !== "number") {
              deletions = 0;
            }
          }

          // Determine success based on exit code for commands
          const actionExitCode = data?.exitCode;
          const isCommandSuccess = action.type === "runCommand"
            ? (actionExitCode === 0 || actionExitCode === undefined)
            : true; // File operations are successful if we got here

          recordActionSummary({
            type: action.type,
            filePath: action.filePath,
            command: action.command,
            additions,
            deletions,
            exitCode: actionExitCode,
            durationMs: data?.durationMs,
            success: isCommandSuccess,
            message: message ? String(message) : undefined,
            originalContent: data?.originalContent, // For undo functionality
            wasCreated: data?.wasCreated, // True if file was newly created (undo = delete)
          });

          pendingActionCountRef.current = Math.max(0, pendingActionCountRef.current - 1);
          // NOTE: Don't call scheduleActionSummaryFlush here - summary is flushed
          // only when ALL actions complete via NaviActionRunner.onAllComplete

          // NOTE: Individual action follow-ups removed to avoid multiple LLM calls
          // The LLM-generated follow-up is now triggered ONCE when ALL actions complete
          // via flushActionSummary() in NaviActionRunner.onAllComplete

          if (action.type !== "runCommand") {
            const actionIndexKey = msg.actionIndex !== undefined ? String(msg.actionIndex) : undefined;
            const actionIndex = typeof msg.actionIndex === 'number' ? msg.actionIndex : null;
            const actionKey = String(action.id || actionIndexKey || `${action.type}-${action.filePath || "action"}`);
            const activityId = actionActivityRef.current.get(actionKey);
            const activityLabel =
              action.type === "createFile"
                ? "File created"
                : action.type === "editFile"
                  ? "File edited"
                  : "Action completed";
            const diffStat =
              action.type === "editFile" && (typeof additions === "number" || typeof deletions === "number")
                ? ` (+${additions ?? 0} / -${deletions ?? 0})`
                : "";
            const activityDetail = action.command || (action.filePath ? `${action.filePath}${diffStat}` : "") || action.description || "";
            if (activityId) {
              setActivityEvents((prev) =>
                prev.map((event) =>
                  event.id === activityId
                    ? {
                      ...event,
                      label: activityLabel,
                      detail: activityDetail,
                      status: "done",
                      timestamp: nowIso(),
                    }
                    : event
                )
              );

              // Also update per-action activities for inline display
              if (actionIndex !== null) {
                setPerActionActivities((prev) => {
                  const next = new Map(prev);
                  const existing = next.get(actionIndex) || [];
                  const updatedActivities = existing.map((evt) =>
                    evt.id === activityId
                      ? { ...evt, label: activityLabel, detail: activityDetail, status: "done" as const, timestamp: nowIso() }
                      : evt
                  );
                  next.set(actionIndex, updatedActivities);
                  return next;
                });
              }

              actionActivityRef.current.delete(actionKey);
            } else {
              const newActivity: ActivityEvent = {
                id: makeActivityId(),
                kind:
                  action.type === "createFile"
                    ? "create"
                    : action.type === "editFile"
                      ? "edit"
                      : "info",
                label: activityLabel,
                detail: activityDetail,
                filePath: action.filePath,
                status: "done",
                timestamp: nowIso(),
              };
              pushActivityEvent(newActivity);

              // Also track in per-action activities
              if (actionIndex !== null) {
                setPerActionActivities((prev) => {
                  const next = new Map(prev);
                  const existing = next.get(actionIndex) || [];
                  next.set(actionIndex, [...existing, newActivity]);
                  return next;
                });
              }
            }
            if (action.filePath) {
              upsertActivityFile({
                path: String(action.filePath),
                additions,
                deletions,
                diff: diffUnified,
                scope: "working",
                status: "done",
                lastTouched: nowIso(),
              });
            }

            // Clear current action index
            currentActionIndexRef.current = null;
          }
        } else {
          // SELF-HEALING: Instead of just showing an error, automatically retry with error context
          const errorMsg = message || "Action execution failed";
          // FIXED: Use top-level stdout/stderr/commandOutput from action.complete message
          // These are sent by the extension when command execution fails
          const errorOutput = msg.commandOutput || msg.stderr || msg.stdout || data?.output || data?.stderr || data?.stdout || "";
          const exitCode = msg.exitCode ?? data?.exitCode;
          const commandDetail = action.command || action.filePath || action.description || "";

          // DEBUG: Log available error context
          console.log('[NaviChatPanel] 📋 action.complete error context:', {
            'msg.commandOutput': msg.commandOutput?.substring(0, 100),
            'msg.stdout': msg.stdout?.substring(0, 100),
            'msg.stderr': msg.stderr?.substring(0, 100),
            'msg.exitCode': msg.exitCode,
            'data?.output': data?.output?.substring(0, 100),
            'computed errorOutput length': errorOutput.length
          });

          // CONSOLIDATE: Append error info to existing message instead of creating new bubble
          const errorSuffix = `\n\n---\n⚠️ **Action failed:** \`${commandDetail}\`\n${errorMsg}${exitCode !== undefined ? `\nExit code: ${exitCode}` : ''}`;

          setMessages((prev) => {
            const lastAssistantIndex = [...prev].reverse().findIndex(m => m.role === "assistant");
            if (lastAssistantIndex === -1) return prev;

            const actualIndex = prev.length - 1 - lastAssistantIndex;
            const updated = [...prev];
            updated[actualIndex] = {
              ...updated[actualIndex],
              content: updated[actualIndex].content + errorSuffix,
            };
            return updated;
          });

          showToast(`Action failed - NAVI will attempt to fix...`, "warning");

          // Update activity events
          if (action.type !== "runCommand") {
            const actionIndexKey = msg.actionIndex !== undefined ? String(msg.actionIndex) : undefined;
            const actionIndex = typeof msg.actionIndex === 'number' ? msg.actionIndex : null;
            const actionKey = String(action.id || actionIndexKey || `${action.type}-${action.filePath || "action"}`);
            const activityId = actionActivityRef.current.get(actionKey);
            const activityLabel =
              action.type === "createFile"
                ? "File creation failed"
                : action.type === "editFile"
                  ? "File edit failed"
                  : "Action failed";
            if (activityId) {
              setActivityEvents((prev) =>
                prev.map((event) =>
                  event.id === activityId
                    ? {
                      ...event,
                      label: activityLabel,
                      detail: commandDetail,
                      status: "error",
                      timestamp: nowIso(),
                    }
                    : event
                )
              );

              // Also update per-action activities for inline display
              if (actionIndex !== null) {
                setPerActionActivities((prev) => {
                  const next = new Map(prev);
                  const existing = next.get(actionIndex) || [];
                  const updatedActivities = existing.map((evt) =>
                    evt.id === activityId
                      ? { ...evt, label: activityLabel, detail: commandDetail, status: "error" as const, timestamp: nowIso() }
                      : evt
                  );
                  next.set(actionIndex, updatedActivities);
                  return next;
                });
              }

              actionActivityRef.current.delete(actionKey);
            } else {
              const errorActivity: ActivityEvent = {
                id: makeActivityId(),
                kind: "error",
                label: activityLabel,
                detail: commandDetail,
                filePath: action.filePath,
                status: "error",
                timestamp: nowIso(),
              };
              pushActivityEvent(errorActivity);

              // Also track in per-action activities
              if (actionIndex !== null) {
                setPerActionActivities((prev) => {
                  const next = new Map(prev);
                  const existing = next.get(actionIndex) || [];
                  next.set(actionIndex, [...existing, errorActivity]);
                  return next;
                });
              }
            }
            if (action.filePath) {
              upsertActivityFile({
                path: String(action.filePath),
                status: "error",
                lastTouched: nowIso(),
              });
            }

            // Clear current action index
            currentActionIndexRef.current = null;
          }

          recordActionSummary({
            type: action.type,
            filePath: action.filePath,
            command: action.command,
            success: false,
            message: errorMsg,
          });
          pendingActionCountRef.current = Math.max(0, pendingActionCountRef.current - 1);
          // NOTE: Don't call scheduleActionSummaryFlush here - summary is flushed
          // only when ALL actions complete via NaviActionRunner.onAllComplete

          // SELF-HEALING: Check if this action should be retried or skipped due to dependency failure
          const actionSignature = `${action.type}:${action.command || action.filePath || ''}`;
          const hasDependency = action.requiresPreviousSuccess;

          // If this action requires previous success but previous failed, skip retry
          if (hasDependency && lastFailedActionRef.current && lastFailedActionRef.current !== actionSignature) {
            console.log('[NaviChatPanel] ⏭️ Skipping action due to previous failure:', actionSignature);

            // Show skip message
            setMessages((prev) => {
              const lastAssistantIndex = [...prev].reverse().findIndex(m => m.role === "assistant");
              if (lastAssistantIndex === -1) return prev;
              const actualIndex = prev.length - 1 - lastAssistantIndex;
              const updated = [...prev];
              updated[actualIndex] = {
                ...updated[actualIndex],
                content: updated[actualIndex].content + `\n\n⏭️ Skipped: \`${commandDetail}\` (requires previous command to succeed)`,
              };
              return updated;
            });
            return;
          }

          // Trigger self-healing retry with proper error context
          const fullErrorOutput = errorOutput || data?.error || data?.message || '';
          triggerSelfHealing(action, fullErrorOutput, exitCode, errorMsg);
        }
        return;
      }

      // Handle NAVI agent events forwarded from the VS Code extension
      if (msg.type === 'navi.agent.event' && msg.event) {
        const evt = msg.event;
        const kind = evt.type || evt.kind;
        const data = evt.data || {};

        // DEBUG: Log all agent events to trace activity flow
        console.log('[NaviChatPanel] 🎯 navi.agent.event received:', { kind, data, evt });

        // Lazy start analysis UI if not active yet
        if (!isAnalyzing && (kind === 'liveProgress' || kind === 'reviewEntry')) {
          setIsAnalyzing(true);
          setAnalysisProgress([]);
          setCurrentProgress(0);
          setStructuredReview(null);
          // setAnalysisSummary(null);
          // Ensure user sees the live stream immediately
          // setReviewViewMode('live');
        }

        if (kind === 'liveProgress') {
          const step: string = data.step || 'Processing...';
          // Skip generic progress messages - only show real file activities from backend
          // These generic messages are: "Planning response...", "Gathering workspace context...",
          // "Contacting model...", "Streaming response...", etc.
          const isGenericProgress = [
            'Planning response',
            'Gathering workspace',
            'Contacting model',
            'Streaming response',
            'Processing response',
            'Response ready',
          ].some(prefix => step.includes(prefix));

          if (!isGenericProgress && step && step !== lastLiveProgressRef.current) {
            lastLiveProgressRef.current = step;
            pushActivityEvent({
              id: makeActivityId(),
              kind: "info",
              label: step,
              detail: undefined,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
            });
          }
          setAnalysisProgress((prev) => {
            if (prev[prev.length - 1] === step) return prev;
            return [...prev, step];
          });

          // Prefer explicit percentage, else derive from processed/total
          const pct: number | undefined = typeof data.percentage === 'number' ? data.percentage : undefined;
          const derived = (typeof data.processedFiles === 'number' && typeof data.totalFiles === 'number' && data.totalFiles > 0)
            ? Math.round((data.processedFiles / data.totalFiles) * 100)
            : undefined;
          const next = (pct ?? derived ?? 0);
          setCurrentProgress((prev) => Math.max(prev, next));

          return;
        }

        if (kind === 'done') {
          setIsAnalyzing(false);
          setCurrentProgress((prev) => Math.max(prev, 100));
          // Mark all running activity events as done
          setActivityEvents((prev) =>
            prev.map((evt) =>
              evt.status === "running" ? { ...evt, status: "done" } : evt
            )
          );
          lastLiveProgressRef.current = "";
          return;
        }

        if (kind === 'error') {
          // Extract error message from various possible locations
          const message = data?.message || data?.error || evt?.message || 'An unexpected error occurred';
          console.error('[NaviChatPanel] ❌ NAVI error event:', { message, data, evt });
          setIsAnalyzing(false);
          // Mark all running activity events as done/error
          setActivityEvents((prev) =>
            prev.map((evt) =>
              evt.status === "running" ? { ...evt, status: "done" } : evt
            )
          );
          lastLiveProgressRef.current = "";

          // Only show toast for user-facing errors (not internal retries)
          const isInternalError = message.includes('retry') || message.includes('fallback');
          if (!isInternalError) {
            showToast(`Error: ${message}`, 'error');
          }

          const normalizedMessage = String(message).toLowerCase();
          if (
            normalizedMessage.includes("http 401") ||
            normalizedMessage.includes("unauthorized") ||
            normalizedMessage.includes("authorization header") ||
            normalizedMessage.includes("missing or invalid authorization")
          ) {
            setAuthRequired(true);
            setAuthRequiredDetail(String(message));
            pendingAuthRetryRef.current = true;
            showToast("Sign in required to continue.", "warning");
          }

          // Add error activity with full detail
          pushActivityEvent({
            id: makeActivityId(),
            kind: "error",
            label: "Error",
            detail: String(message).substring(0, 500), // Limit detail length
            status: "error",
            timestamp: msg.timestamp || nowIso(),
          });
          return;
        }

        // Handle file read activity events from streaming
        // UPDATE existing activity if status is "done", CREATE new if "running"
        if (kind === 'file_read' || kind === 'read') {
          const label = data.label || 'Read';
          const detail = data.detail || data.filePath || '';
          const status = data.status || 'done';
          const toolId = data.toolId;

          if (status === 'done') {
            // Update existing "running" activity to "done" instead of creating duplicate
            // Match by toolId first, then fall back to detail matching
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.kind === 'read' && evt.status === 'running' &&
                  (toolId ? (evt as any).toolId === toolId : evt.detail === detail)
              );
              if (existingIdx >= 0) {
                // Update the existing activity
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], status: 'done' };
                return updated;
              }
              // No running activity found, add as done
              return [...prev, {
                id: makeActivityId(),
                kind: "read" as const,
                label,
                detail,
                filePath: data.filePath || detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else {
            // Create new "running" activity with toolId for matching on completion
            pushActivityEvent({
              id: makeActivityId(),
              kind: "read",
              label,
              detail,
              filePath: data.filePath || detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
              ...(toolId ? { toolId } : {}),
            } as any);
          }
          return;
        }

        // Handle analysis activity events (Thinking)
        if (kind === 'analysis') {
          const label = data.label || 'Analyzing';
          const detail = data.detail || '';
          const status = data.status || 'running';

          if (status === 'done') {
            // Update existing "Thinking" activity to done
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.label === label && evt.status === 'running'
              );
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], status: 'done', detail };
                return updated;
              }
              return prev; // Don't add "done" without a running one
            });
          } else {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "info",
              label,
              detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
            });
          }
          return;
        }

        // Handle edit activity events
        if (kind === 'edit') {
          const label = data.label || 'Editing';
          const detail = data.detail || data.filePath || '';
          const status = data.status || 'done';
          const toolId = data.toolId;

          if (status === 'done') {
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.kind === 'edit' && evt.status === 'running' &&
                  (toolId ? (evt as any).toolId === toolId : evt.detail === detail)
              );
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], status: 'done' };
                return updated;
              }
              return [...prev, {
                id: makeActivityId(),
                kind: "edit" as const,
                label,
                detail,
                filePath: data.filePath || detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "edit",
              label,
              detail,
              filePath: data.filePath || detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
              ...(toolId ? { toolId } : {}),
            } as any);
          }
          return;
        }

        // Handle create activity events
        if (kind === 'create') {
          const label = data.label || 'Creating';
          const detail = data.detail || data.filePath || '';
          const status = data.status || 'done';
          const toolId = data.toolId;

          if (status === 'done') {
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.kind === 'create' && evt.status === 'running' &&
                  (toolId ? (evt as any).toolId === toolId : evt.detail === detail)
              );
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], status: 'done' };
                return updated;
              }
              return [...prev, {
                id: makeActivityId(),
                kind: "create" as const,
                label,
                detail,
                filePath: data.filePath || detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "create",
              label,
              detail,
              filePath: data.filePath || detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
              ...(toolId ? { toolId } : {}),
            } as any);
          }
          return;
        }

        // Handle intent classification activity events
        if (kind === 'intent') {
          const label = data.label || 'Intent classified';
          const detail = data.detail || '';
          const status = data.status || 'done';

          if (status === 'done') {
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.kind === 'intent' && evt.status === 'running'
              );
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], status: 'done', detail };
                return updated;
              }
              return [...prev, {
                id: makeActivityId(),
                kind: "intent" as const,
                label,
                detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "intent",
              label,
              detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
            });
          }
          return;
        }

        // Handle detection activity events (project type detection, etc.)
        if (kind === 'detection') {
          const label = data.label || 'Detecting';
          const detail = data.detail || '';
          const status = data.status || 'done';

          if (status === 'done') {
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.kind === 'detection' && evt.status === 'running'
              );
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], status: 'done', detail, label };
                return updated;
              }
              return [...prev, {
                id: makeActivityId(),
                kind: "detection" as const,
                label,
                detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "detection",
              label,
              detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
            });
          }
          return;
        }

        // Handle command execution activity events (from run_command tool)
        if (kind === 'command') {
          const label = data.label || 'Running command';
          const detail = data.detail || data.command || '';
          const status = data.status || 'running';
          // Context fields for command explanations (Bug 5 fix)
          const purpose = data.purpose || data.context?.purpose;
          const explanation = data.explanation || data.context?.explanation;
          const nextAction = data.nextAction || data.context?.nextAction;
          const output = data.output || data.result?.stdout || data.result?.output;

          if (status === 'done') {
            setActivityEvents((prev) => {
              const existingIdx = prev.findIndex(
                (evt) => evt.kind === 'command' && evt.status === 'running' && (data.toolId ? (evt as any).toolId === data.toolId : evt.detail === detail)
              );
              if (existingIdx >= 0) {
                const updated = [...prev];
                updated[existingIdx] = {
                  ...updated[existingIdx],
                  status: 'done',
                  detail,
                  output,
                  explanation,
                  nextAction,
                };
                return updated;
              }
              return [...prev, {
                id: makeActivityId(),
                kind: "command" as const,
                label,
                detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
                output,
                purpose,
                explanation,
                nextAction,
              }];
            });
          } else {
            pushActivityEvent({
              id: makeActivityId(),
              kind: "command",
              label,
              detail,
              status: "running",
              timestamp: msg.timestamp || nowIso(),
              purpose,
              ...(data.toolId ? { toolId: data.toolId } : {}),
            } as any);
          }
          return;
        }

        // Handle tool_result events (completion of any tool call)
        if (kind === 'tool_result') {
          const result = data.result || {};
          const toolId = data.toolId;
          const success = result.success !== false;
          const errorMsg = result.error || result.stderr;

          // Update the corresponding running activity to done
          setActivityEvents((prev) => {
            // Find the running activity with matching toolId
            const existingIdx = prev.findIndex(
              (evt) => evt.status === 'running' && (evt as any).toolId === toolId
            );
            if (existingIdx >= 0) {
              const updated = [...prev];
              const existing = updated[existingIdx];
              updated[existingIdx] = {
                ...existing,
                status: success ? 'done' : 'error',
                detail: success
                  ? (result.stdout ? `✓ ${result.stdout.substring(0, 100)}${result.stdout.length > 100 ? '...' : ''}` : existing.detail)
                  : (errorMsg ? `✗ ${errorMsg.substring(0, 100)}` : 'Failed'),
              };
              return updated;
            }
            return prev;
          });
          return;
        }

        if (kind === 'reviewEntry') {
          const entry = data.entry || {};
          const file = entry.filePath || entry.file || entry.path || 'unknown-file';
          const issuesArr = Array.isArray(entry.issues) ? entry.issues : [];

          setStructuredReview((prev) => {
            const base: StructuredReview = prev ?? { files: [] };
            // Find or create file record
            const idx = base.files.findIndex((f) => f.path === file);
            const mappedIssues = issuesArr.map((i: any, iidx: number) => ({
              id: i.id || `${file}-${iidx}`,
              title: i.title || i.description || i.summary || 'Issue',
              body: i.body || i.details || i.message || i.title || '',
              canAutoFix: !!i.canAutoFix,
            }));

            if (idx >= 0) {
              const existing = base.files[idx];
              const merged: StructuredReviewFile = {
                path: file,
                severity: entry.severity || existing.severity,
                diff: entry.diff || entry.patch || existing.diff,
                issues: [...(existing.issues || []), ...mappedIssues],
              };
              const next = { ...base, files: [...base.files] };
              next.files[idx] = merged;
              return next;
            }

            return {
              files: [
                ...base.files,
                {
                  path: file,
                  severity: entry.severity || 'info',
                  diff: entry.diff || entry.patch,
                  issues: mappedIssues,
                },
              ],
            };
          });
          return;
        }

        if (kind === 'reviewSummary') {
          // Convert to compact summary for the UI
          const total = Number(data.totalFiles || data.scannedFiles) || 0;
          const committed = Number(data.committedFiles) || 0;
          const uncommitted = Number(data.uncommittedFiles) || 0;
          const baseBranch = data.baseBranch || 'main';
          // const listed = Array.isArray(data.listedFiles) ? data.listedFiles.length : undefined;
          // const severities = data.severityCounts || {};
          const totalIssues = Number(data.totalIssues) || 0;
          const highlights: string[] = Array.isArray(data.highlights) ? data.highlights : [];

          // Build comprehensive highlights with branch comparison
          const summaryHighlights: string[] = [];
          if (totalIssues > 0) {
            summaryHighlights.push(`${totalIssues} issues found across ${total} files`);
          }
          if (committed > 0) {
            summaryHighlights.push(`${committed} files changed vs ${baseBranch}`);
          }
          if (uncommitted > 0) {
            summaryHighlights.push(`${uncommitted} files with uncommitted changes`);
          }
          summaryHighlights.push(...highlights);
          if (summaryHighlights.length === 0) {
            summaryHighlights.push('No issues detected.');
          }

          // setAnalysisSummary({
          //   total_files: total,
          //   detailed_files: listed ?? total,
          //   skipped_files: listed ? Math.max(0, total - listed) : 0,
          //   highlights: summaryHighlights,
          // });
          return;
        }

        if (kind === 'done') {
          setIsAnalyzing(false);
          setCurrentProgress((prev) => Math.max(prev, 100));
          lastLiveProgressRef.current = "";
          // Mark all running activity events as done
          setActivityEvents((prev) =>
            prev.map((evt) =>
              evt.status === "running" ? { ...evt, status: "done" } : evt
            )
          );
          // If no summary arrived, synthesize a minimal one so completion is visible
          // setAnalysisSummary((prev) => {
          //   if (prev) return prev;
          //   const filesLen = (structuredReview?.files?.length ?? 0);
          //   const highlights = filesLen > 0
          //     ? [`${filesLen} files analyzed${filesLen ? '' : ''}`]
          //     : ['No high-risk issues detected.'];
          //   return {
          //     total_files: filesLen,
          //     detailed_files: filesLen,
          //     skipped_files: 0,
          //     highlights,
          //   };
          // });
          showToast('Analysis complete.', 'info');
          return;
        }

        if (kind === 'error') {
          const message = data?.message || 'Agent reported an error';
          setIsAnalyzing(false);
          lastLiveProgressRef.current = "";
          // Mark all running activity events as done
          setActivityEvents((prev) =>
            prev.map((evt) =>
              evt.status === "running" ? { ...evt, status: "done" } : evt
            )
          );
          showToast(`Error: ${message}`, 'error');
          return;
        }

        // NEW (Phase 1.2): Handle repo diff summary from agent
        if (kind === 'repo.diff.summary') {
          const { base, unstagedCount, stagedCount, unstagedFiles, stagedFiles, totalChanges } = data;
          setRepoSummary({
            base: base || 'main',
            unstagedCount: unstagedCount || 0,
            stagedCount: stagedCount || 0,
            unstagedFiles: unstagedFiles || [],
            stagedFiles: stagedFiles || [],
            totalChanges: totalChanges || 0,
          });
          console.log('[NaviChatPanel] 📊 Received repo diff summary:', { base, unstagedCount, stagedCount });
          // Reset diff details when new summary arrives
          setDiffDetails([]);
          setChangeDetailsOpen(false);
          return;
        }

        // NEW (Phase 1.3): Handle individual file diff details
        if (kind === 'repo.diff.detail') {
          const { path, additions, deletions, diff, scope } = data;
          const additionsCount =
            typeof additions === "number" ? additions : undefined;
          const deletionsCount =
            typeof deletions === "number" ? deletions : undefined;
          const normalizedPath = path ? toWorkspaceRelativePath(String(path)) : "";
          if (!normalizedPath) return;
          setDiffDetails(prev => {
            const idx = prev.findIndex(d => d.path === normalizedPath);
            const newEntry = {
              path: normalizedPath,
              additions: typeof additions === "number" ? additions : 0,
              deletions: typeof deletions === "number" ? deletions : 0,
              diff: diff || '',
              scope: scope || 'unstaged'
            };
            if (idx >= 0) {
              // Update existing entry instead of adding duplicate
              const updated = [...prev];
              updated[idx] = newEntry;
              return updated;
            }
            return [...prev, newEntry];
          });
          if (normalizedPath) {
            upsertActivityFile({
              path: String(normalizedPath),
              additions: additionsCount,
              deletions: deletionsCount,
              diff: diff || undefined,
              scope: scope || 'unstaged',
              status: "done",
              lastTouched: nowIso(),
            });
          }
          console.log('[NaviChatPanel] 📄 Received diff for:', normalizedPath, `+${additions} -${deletions}`);
          return;
        }

        // NEW (Phase 1.4): Diagnostics summary scoped to changed files
        if (kind === 'diagnostics.summary') {
          const files = Array.isArray(data.files) ? data.files : [];
          setDiagnosticsByFile(files);
          return;
        }

        // NEW (Phase 1.3): Global assessment summary
        if (kind === 'navi.agent.assessment') {
          const a = data || {};
          setAssessment({
            totalDiagnostics: Number(a.totalDiagnostics || 0),
            introduced: Number(a.introduced || 0),
            preExisting: Number(a.preExisting || 0),
            errors: Number(a.errors || 0),
            warnings: Number(a.warnings || 0),
            filesAffected: Number(a.filesAffected || 0),
            // Phase 1.4: Scope breakdown
            scope: a.scope || 'changed-files',
            changedFileDiagsCount: Number(a.changedFileDiagsCount || 0),
            globalDiagsCount: Number(a.globalDiagsCount || 0),
            changedFileErrors: Number(a.changedFileErrors || 0),
            changedFileWarnings: Number(a.changedFileWarnings || 0),
            hasGlobalIssuesOutsideChanged: Boolean(a.hasGlobalIssuesOutsideChanged),
          });
          return;
        }

        // Phase 2.0 – Step 1.5: Canonical assessment counts
        if (kind === 'navi.assessment.updated') {
          const c = (data && data.counts) || {};
          setAssessment(prev => ({
            // Consume canonical counts; keep legacy fields if present
            totalDiagnostics: Number(c.totalIssues ?? prev?.totalDiagnostics ?? 0),
            introduced: Number(c.introducedIssues ?? prev?.introduced ?? 0),
            preExisting: Number(c.preExistingIssues ?? prev?.preExisting ?? 0),
            warnings: Number(c.warnings ?? prev?.warnings ?? 0),
            errors: Number(prev?.errors ?? 0),
            filesAffected: Number(prev?.filesAffected ?? 0),
            scope: prev?.scope || 'changed-files',
            changedFileDiagsCount: Number(prev?.changedFileDiagsCount ?? 0),
            globalDiagsCount: Number(prev?.globalDiagsCount ?? 0),
            changedFileErrors: Number(prev?.changedFileErrors ?? 0),
            changedFileWarnings: Number(prev?.changedFileWarnings ?? 0),
            hasGlobalIssuesOutsideChanged: Boolean(prev?.hasGlobalIssuesOutsideChanged ?? (c.preExistingIssues > 0)),
          }));
          return;
        }

        // NEW (Phase 1.5): Detailed diagnostics by file
        if (kind === 'navi.diagnostics.detailed') {
          const files = Array.isArray(data.files) ? data.files : [];
          setDetailedDiagnostics(files);
          console.log('[NaviChatPanel] 📊 Detailed diagnostics received:', files.length, 'files');
          return;
        }

        // Phase 2.0 – Step 2: Fix proposals
        if (kind === 'navi.fix.proposals') {
          const files = Array.isArray(data.files) ? data.files : [];
          setFixProposals(files);
          console.log('[NaviChatPanel] 🛠 Fix proposals received:', files.length, 'files');
          return;
        }

        // Phase 2.1 – Step 1: Fix application result
        if (kind === 'navi.fix.result') {
          const { proposalId, status, reason } = data;
          console.log(`[NaviChatPanel] Fix result for ${proposalId}:`, status, reason || '');

          // Show appropriate feedback based on status
          if (status === 'deferred') {
            showToast(reason || 'Opened in editor for review', 'info');
          } else if (status === 'cancelled') {
            showToast(reason || 'Fix cancelled by user', 'info');
          } else if (status === 'failed') {
            showToast(reason || 'Fix application failed', 'error');
          } else if (status === 'pending') {
            showToast(reason || 'Fix application pending', 'info');
          } else if (status === 'applied') {
            showToast('Fix applied successfully.', 'info');
          }
          return;
        }

        // GENERIC HANDLER: Handle all other activity types from backend
        // This includes: detection, context, prompt, llm_call, thinking, parsing, validation, rag, response
        // These are informational activities showing what NAVI is doing

        // SKIP llm_call activities BUT show streaming status for LLM calls
        // Use a single unified activity ID for both llm_call and thinking
        const unifiedThinkingId = 'llm-thinking-unified';

        if (kind === 'llm_call') {
          // Show live LLM activity without clutter
          if (data.status === 'running') {
            setIsAnalyzing(true);
            // Create/update the unified thinking activity
            setActivityEvents((prev) => {
              const existing = prev.find(e => e.id === unifiedThinkingId);
              if (existing) {
                return prev.map(e => e.id === unifiedThinkingId
                  ? { ...e, detail: data.detail || 'Processing with AI...', timestamp: msg.timestamp || nowIso() }
                  : e);
              }
              return [...prev, {
                id: unifiedThinkingId,
                kind: 'thinking',
                label: 'Thinking',
                detail: data.detail || 'Processing with AI...',
                status: 'running',
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else if (data.status === 'done') {
            setIsAnalyzing(false);
            // Mark the unified thinking activity as complete
            setActivityEvents(prev => prev.map(e =>
              e.id === unifiedThinkingId ? { ...e, status: 'done', timestamp: msg.timestamp || nowIso() } : e
            ));
          }
          return;
        }

        // Handle 'thinking' kind - update the SAME unified activity instead of creating a new one
        // This prevents duplicate spinners
        if (kind === 'thinking') {
          if (data.status === 'running') {
            setIsAnalyzing(true);
            // Update the existing unified thinking activity
            setActivityEvents((prev) => {
              const existing = prev.find(e => e.id === unifiedThinkingId);
              if (existing) {
                // Just update the existing activity
                return prev.map(e => e.id === unifiedThinkingId
                  ? { ...e, label: 'Thinking', detail: data.detail || '', timestamp: msg.timestamp || nowIso() }
                  : e);
              }
              // If no existing activity, create one
              return [...prev, {
                id: unifiedThinkingId,
                kind: 'thinking',
                label: 'Thinking',
                detail: data.detail || '',
                status: 'running',
                timestamp: msg.timestamp || nowIso(),
              }];
            });
          } else if (data.status === 'done') {
            // Mark as done
            setActivityEvents(prev => prev.map(e =>
              e.id === unifiedThinkingId ? { ...e, status: 'done', detail: data.detail || 'Complete', timestamp: msg.timestamp || nowIso() } : e
            ));
          }
          return;
        }

        const label = data.label || kind || 'Processing';
        const detail = data.detail || '';
        const status = data.status || 'done';

        // Map backend activity kinds to display-friendly kinds
        // IMPORTANT: Preserve 'detection' and 'intent' kinds for display filtering
        const displayKind = (() => {
          if (kind === 'detection') return 'detection';
          if (kind === 'intent') return 'intent';
          if (kind === 'context' || kind === 'prompt') return 'context';
          if (kind === 'parsing' || kind === 'validation') return 'info';
          if (kind === 'rag') return 'rag';
          if (kind === 'response') return 'response';
          return 'info';
        })();

        if (status === 'done') {
          // Update existing running activity to done
          setActivityEvents((prev) => {
            const existingIdx = prev.findIndex(
              (evt) => evt.label === label && evt.status === 'running'
            );
            if (existingIdx >= 0) {
              const updated = [...prev];
              updated[existingIdx] = { ...updated[existingIdx], status: 'done', detail };
              return updated;
            }
            // No running activity found - only add done activities for important ones
            if (kind === 'thinking' || kind === 'rag') {
              return [...prev, {
                id: makeActivityId(),
                kind: displayKind as any,
                label,
                detail,
                status: "done" as const,
                timestamp: msg.timestamp || nowIso(),
              }];
            }
            return prev;
          });
        } else if (status === 'running') {
          // Create new running activity
          pushActivityEvent({
            id: makeActivityId(),
            kind: displayKind as any,
            label,
            detail,
            status: "running",
            timestamp: msg.timestamp || nowIso(),
          });
        }
        return;
      }

      // NEW: Handle structured review messages
      if (msg.type === "aep.review" && msg.payload) {
        try {
          const reviewData = JSON.parse(msg.payload);
          setStructuredReview(reviewData);
          console.log('[NaviChatPanel] 📋 Received structured review:', reviewData);
        } catch (err) {
          console.warn('[NaviChatPanel] Failed to parse review data:', err);
        }
      }
    });

    // Return cleanup function
    return () => {
      window.removeEventListener('message', handleIframeMessage);
      unsub?.(); // unsub is the cleanup from vscodeApi.onMessage
    };
  }, []);

  // Parse progress updates from assistant messages to update activity panel
  useEffect(() => {
    if (!activityPanelState) return;

    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== 'assistant') return;

    // Parse progress markers from the message content
    activityPanelState.parseProgressUpdate(lastMessage.content);
  }, [messages, activityPanelState]);

  /* ---------- direct backend call (fallback) ---------- */

  const sendNaviChatRequest = async (
    message: string,
    attachmentsOverride?: AttachmentChipData[],
    modelOverride?: string,
    modeOverride?: ChatMode
  ): Promise<NaviChatResponse> => {
    const { effectiveRoot } = getEffectiveWorkspace();

    if (!effectiveRoot) {
      vscodeApi.postMessage({ type: "getWorkspaceRoot" });
    }

    const workspaceRootToSend = effectiveRoot;

    const conversationHistory = messages.slice(-MAX_CONVERSATION_HISTORY).map((msg) => ({
      id: msg.id,
      type: msg.role,
      content: msg.content,
      timestamp: msg.createdAt,
    }));

    const body = {
      message,
      workspace: null,
      workspace_root: workspaceRootToSend,
      branch: null,
      mode: modeOverride || chatMode,
      model: modelOverride || selectedModelId,
      execution: executionMode,
      scope,
      provider,
      conversation_id: activeSessionId,  // Send session ID for conversation tracking
      conversation_history: conversationHistory,  // Send as snake_case to match backend
      user_id: USER_ID,
      attachments: (attachmentsOverride ?? attachments).map((att) => ({
        kind: att.kind,
        path: att.path,
        language: att.language,
        content: (att as any).content,
      })),
    };

    const backendBase = resolveBackendBase();
    const url = `${backendBase}/api/navi/chat`;
    console.log("[NAVI Chat] Sending request:", { url, backendBase, body });

    const res = await fetch(url, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(body),
    });
    const rawText = await res.text();
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${rawText || res.statusText}`);
    }
    if (!rawText || !rawText.trim()) {
      throw new Error("Empty response from NAVI backend");
    }
    try {
      const parsed = JSON.parse(rawText) as NaviChatResponse;
      console.log("[NAVI Chat] Raw response:", parsed);
      return parsed;
    } catch (err) {
      console.error("[NAVI Chat] Failed to parse response:", rawText);
      throw new Error(`Invalid JSON from NAVI backend: ${rawText.substring(0, 200)}`);
    }
  };

  /* ---------- reply shaping ---------- */

  const buildAssistantReply = (
    data: NaviChatResponse,
    userText: string
  ): string => {
    const { effectiveRoot, effectiveRepoName } = getEffectiveWorkspace();
    const lowerUser = userText.toLowerCase();
    const state = data.state || {};

    const backendRepoName =
      typeof state.repo_name === "string" ? state.repo_name.trim() : "";
    const backendRepoRoot =
      typeof state.repo_root === "string" ? state.repo_root.trim() : "";

    const repoFastPathWhere =
      state?.repo_fast_path &&
      (state.kind === "where" ||
        state.kind === "which_repo" ||
        state.kind === "where_repo");

    const repoFastPathExplain =
      state?.repo_fast_path &&
      (state.kind === "explain" ||
        state.kind === "what" ||
        state.kind === "describe");

    const isWhichRepoQuestion =
      lowerUser.includes("which repo") ||
      lowerUser.includes("what repo") ||
      lowerUser.includes("which project") ||
      lowerUser.includes("what project") ||
      lowerUser.includes("which repository") ||
      lowerUser.includes("what repository") ||
      lowerUser.includes("where are we") ||
      lowerUser.includes("what repo are we in");

    const isExplainRepoQuestion =
      lowerUser.includes("explain this repo") ||
      lowerUser.includes("explain about this repo") ||
      (lowerUser.includes("explain") &&
        (lowerUser.includes("this repo") ||
          lowerUser.includes("the repo") ||
          lowerUser.includes("this project") ||
          lowerUser.includes("the project") ||
          lowerUser.includes("codebase")));

    const name =
      backendRepoName ||
      (effectiveRepoName && effectiveRepoName.trim().length > 0
        ? effectiveRepoName
        : "this repo");

    const root =
      backendRepoRoot ||
      effectiveRoot ||
      "";

    if (isWhichRepoQuestion || repoFastPathWhere) {
      if (root) {
        return `You're currently working in the **${name}** repo at \`${root}\`.`;
      }
      return `You're currently working in the **${name}** repo.`;
    }

    if (isExplainRepoQuestion || repoFastPathExplain) {
      const backendCandidate = (data.content || data.reply || "").trim();

      if (backendCandidate) {
        return backendCandidate;
      }

      const pathSuffix = root ? ` at \`${root}\`` : "";
      return `You're working in the **${name}** repo${pathSuffix}. Try asking me about specific files or directories.`;
    }

    if (data.content && data.content.trim()) {
      return data.content;
    }

    if (data.reply && data.reply.trim()) {
      return data.reply;
    }

    const hasActions = Array.isArray(data.actions) && data.actions.length > 0;
    const action: NaviAction | null = hasActions ? data.actions![0] : null;

    const intentKind = (action?.intent_kind || "").toLowerCase();
    const titleLower = (action?.title || "").toLowerCase();
    const isInspectRepo =
      intentKind.includes("inspect_repo") ||
      titleLower.includes("inspect_repo");

    if (action && isInspectRepo) {
      return (
        `Plan: **Inspect repository structure**\n\n` +
        `I'll scan the repository structure, git history, and linked tools so I can ` +
        `explain this project and propose fixes.`
      );
    }

    if (
      lowerUser.includes("explain") &&
      (lowerUser.includes("project") || lowerUser.includes("repo"))
    ) {
      if (data.reply && data.reply.trim()) return data.reply;
      if (hasActions) {
        const title = action?.title || "Explain project plan";
        const desc =
          action?.description ||
          "Navi will inspect the repo and then summarize what this project does.";
        return `Plan: **${title}**\n\n${desc}`;
      }
    }

    if (hasActions) {
      // Generate a conversational, contextual response based on action types
      const allActions = data.actions || [];
      const commandActions = allActions.filter((a: NaviAction) =>
        a.type === 'runCommand' || a.type === 'command' || a.intent_kind === 'runCommand' || a.intent_kind === 'command'
      );
      const fileActions = allActions.filter((a: NaviAction) =>
        a.type === 'editFile' || a.type === 'createFile' || a.type === 'edit' || a.type === 'create' ||
        a.intent_kind === 'editFile' || a.intent_kind === 'createFile' || a.intent_kind === 'edit' || a.intent_kind === 'create'
      );

      // Build a natural response based on what we're about to do
      const parts: string[] = [];

      // Describe file changes
      if (fileActions.length > 0) {
        const fileCount = fileActions.length;
        if (fileCount === 1) {
          const filePath = fileActions[0].filePath || '';
          const fileName = filePath.split('/').pop() || 'the file';
          const actionType = fileActions[0].type || fileActions[0].intent_kind || '';
          if (actionType.includes('create')) {
            parts.push(`I'll create \`${fileName}\` with the implementation you need.`);
          } else {
            parts.push(`I'll update \`${fileName}\` with the necessary changes.`);
          }
        } else {
          const createCount = fileActions.filter((a: NaviAction) =>
            (a.type || a.intent_kind || '').includes('create')
          ).length;
          const editCount = fileCount - createCount;
          if (createCount > 0 && editCount > 0) {
            parts.push(`I'll create ${createCount} new file${createCount > 1 ? 's' : ''} and update ${editCount} existing file${editCount > 1 ? 's' : ''}.`);
          } else if (createCount > 0) {
            parts.push(`I'll create ${createCount} new file${createCount > 1 ? 's' : ''} for you.`);
          } else {
            parts.push(`I'll update ${editCount} file${editCount > 1 ? 's' : ''} with the changes.`);
          }
        }
      }

      // Describe commands
      if (commandActions.length > 0) {
        const commands = commandActions.map((a: NaviAction) => a.command || '').filter(Boolean);
        if (commands.length === 1) {
          const cmd = commands[0];
          if (cmd.includes('install')) {
            parts.push(fileActions.length > 0 ? "Then I'll install the dependencies." : "I'll install the dependencies for you.");
          } else if (cmd.includes('test')) {
            parts.push(fileActions.length > 0 ? "Then I'll run the tests to verify everything works." : "I'll run the tests for you.");
          } else if (cmd.includes('build')) {
            parts.push(fileActions.length > 0 ? "Then I'll build the project." : "I'll build the project for you.");
          } else if (cmd.includes('dev') || cmd.includes('start')) {
            parts.push(fileActions.length > 0 ? "Then I'll start the development server." : "I'll start the development server.");
          } else {
            parts.push(fileActions.length > 0 ? `Then I'll run \`${cmd}\`.` : `I'll run \`${cmd}\` for you.`);
          }
        } else {
          parts.push(fileActions.length > 0 ? `Then I'll run ${commands.length} commands to complete the setup.` : `I'll run ${commands.length} commands for you.`);
        }
      }

      // Add encouragement to review
      if (fileActions.length > 0) {
        parts.push("\n\nReview the changes below and click **Allow** when you're ready.");
      } else if (commandActions.length > 0) {
        parts.push("\n\nClick **Allow** below to run the command.");
      }

      // If we generated something useful, return it
      if (parts.length > 0) {
        return parts.join(' ');
      }

      // Fallback to original behavior if we couldn't generate a better message
      const title = action?.title || action?.intent_kind || "Planned action";
      const desc =
        action?.description ||
        "I've prepared the changes. Review them below and click Allow when ready.";
      return `**${title}**\n\n${desc}`;
    }

    const fallback =
      (typeof data.reply === "string" && data.reply.trim().length > 0
        ? data.reply
        : data.content) || "";

    if (!fallback.trim()) return "(Navi returned an empty reply)";
    if (!isGreeting(userText) && looksLikeGenericGreeting(fallback)) {
      return "On it. If you want me to dive deeper, tell me what to inspect (file, diff, or task).";
    }
    if (isGreeting(userText)) {
      return stripContextSection(fallback);
    }
    return fallback;
  };

  /* ---------- send ---------- */

  const applyModelSelection = (nextModelId: string) => {
    const resolvedLabel = getModelLabel(nextModelId);
    const isAuto = nextModelId === AUTO_MODEL_ID || nextModelId === "auto";
    setLastRouterInfo(null);
    setSelectedModelId(nextModelId);
    setModelLabelOverride(null);
    setUseAutoModel(isAuto);
    if (!isAuto) {
      setLastManualModelId(nextModelId);
    }
    vscodeApi.postMessage({
      type: "setModel",
      modelId: nextModelId,
      modelLabel: resolvedLabel,
    });
  };

  const applyModeSelection = (nextModeId: ChatMode) => {
    setLastRouterInfo(null);
    setChatMode(nextModeId);
    vscodeApi.postMessage({
      type: "setMode",
      modeId: nextModeId,
      modeLabel: CHAT_MODE_LABELS[nextModeId],
    });
  };

  const resolveModelForMessage = (text: string) => {
    if (selectedModelId === AUTO_MODEL_ID && useAutoModel) {
      // Use intelligent LLM router to detect task type and recommend best model
      const recommendation = getRecommendedModel(text);
      console.log(`[NAVI Router] Detected task: ${recommendation.taskType}, using: ${recommendation.modelName} (${recommendation.reason})`);

      setLastRouterInfo({
        source: "auto",
        taskType: recommendation.taskType,
        modelId: recommendation.modelId,
        modelName: recommendation.modelName,
        reason: recommendation.reason,
      });

      return {
        modelId: recommendation.modelId,
        modelName: recommendation.modelName,
        taskType: recommendation.taskType,
      };
    }

    setLastRouterInfo(null);
    return {
      modelId: selectedModelId,
      modelName: getModelLabel(selectedModelId, modelLabelOverride || undefined),
      taskType: detectTaskType(text),
    };
  };

  // Cancel/stop the current request
  const handleCancelRequest = () => {
    // Abort any ongoing fetch requests
    if (chatAbortRef.current) {
      chatAbortRef.current.abort();
      chatAbortRef.current = null;
    }
    if (analysisAbortRef.current) {
      analysisAbortRef.current.abort();
      analysisAbortRef.current = null;
    }

    // Reset sending state
    setSending(false);
    setSendTimedOut(false);

    // Clear timeout
    if (sendTimeoutRef.current) {
      clearTimeout(sendTimeoutRef.current);
      sendTimeoutRef.current = null;
    }

    // Clean up progress message rotation
    if (progressIntervalRef.current) {
      progressIntervalRef.current();
      progressIntervalRef.current = null;
    }

    // Mark thinking activities as cancelled
    setActivityEvents((prev) =>
      prev.map((evt) =>
        evt.status === "running"
          ? { ...evt, status: "error" as const, label: "Cancelled" }
          : evt
      )
    );

    // Notify VS Code extension to cancel
    vscodeApi.postMessage({ type: "cancelRequest" });

    showToast("Request cancelled", "info");
  };

  // Helper function to trigger self-healing retry logic
  const triggerSelfHealing = (
    action: AgentAction,
    errorOutput: string,
    exitCode?: number,
    errorMsg?: string
  ) => {
    const actionSignature = `${action.type}-${action.command || action.filePath || ''}`;
    const commandDetail = action.command || action.filePath || action.description || '';

    // Check if this is the same action failing repeatedly or a new failure
    if (lastFailedActionRef.current === actionSignature) {
      selfHealingRetryCountRef.current += 1;
    } else {
      // New action failure - reset counter
      selfHealingRetryCountRef.current = 1;
      lastFailedActionRef.current = actionSignature;
    }

    const currentRetry = selfHealingRetryCountRef.current;
    const canRetry = currentRetry <= MAX_SELF_HEALING_RETRIES;

    if (canRetry) {
      const retryInfo = `(Attempt ${currentRetry}/${MAX_SELF_HEALING_RETRIES})`;
      // Capture error context with better fallbacks
      const fullErrorOutput = errorOutput || errorMsg || 'No error output available';
      let errorContext = fullErrorOutput.trim().substring(0, 2000);
      if (!errorContext) {
        errorContext = (errorMsg || 'No error output available').trim();
      }

      // Format exit code properly - only use 'unknown' if truly undefined/null
      const exitCodeStr = (exitCode !== undefined && exitCode !== null)
        ? String(exitCode)
        : (fullErrorOutput.includes('exit code') ? 'non-zero' : '1');

      const selfHealingPrompt = action.type === "runCommand"
        ? `The command \`${action.command}\` failed with exit code ${exitCodeStr}. ${retryInfo}\n\nError output:\n\`\`\`\n${errorContext}\n\`\`\`\n\nPlease analyze this error and fix it. Try a DIFFERENT approach than before - the previous approach didn't work.`
        : `The file operation on \`${action.filePath}\` failed: ${errorMsg} ${retryInfo}\n\nError output:\n\`\`\`\n${errorContext}\n\`\`\`\n\nPlease analyze this error and fix it. Try a DIFFERENT approach than before.`;

      // Update existing retry activity in place instead of creating new ones
      if (currentRetryActivityRef.current) {
        setActivityEvents((prev) =>
          prev.map((evt) =>
            evt.id === currentRetryActivityRef.current
              ? { ...evt, label: `Self-healing ${retryInfo}`, timestamp: nowIso() }
              : evt
          )
        );
      } else {
        // Create new retry activity and track it
        const retryActivityId = makeActivityId();
        currentRetryActivityRef.current = retryActivityId;
        pushActivityEvent({
          id: retryActivityId,
          kind: "info",
          label: `Self-healing ${retryInfo}`,
          detail: "Analyzing error and attempting fix",
          status: "running",
          timestamp: nowIso(),
        });
      }

      // Debug: Show what we're sending to LLM
      console.log(`[NAVI] 🔄 Self-healing: Retry ${currentRetry}/${MAX_SELF_HEALING_RETRIES}`);
      console.log(`[NAVI] 📋 Error output length: ${fullErrorOutput.length} chars`);
      console.log(`[NAVI] 📋 Error context (first 500 chars): ${errorContext.substring(0, 500)}`);
      console.log(`[NAVI] 📋 Exit code: ${exitCodeStr}`);

      showToast(`Action failed - NAVI will attempt to fix... ${retryInfo}`, "warning");

      // Trigger follow-up request after a short delay
      setTimeout(() => {
        handleSend(selfHealingPrompt);
      }, 500);
    } else {
      // Max retries reached - give up and notify user
      selfHealingRetryCountRef.current = 0;
      lastFailedActionRef.current = null;
      currentRetryActivityRef.current = null;

      // Append final failure message
      const finalErrorSuffix = `\n\n🛑 **Self-healing exhausted** - NAVI tried ${MAX_SELF_HEALING_RETRIES} times but couldn't fix this automatically.\n\nPlease review the error and provide guidance on how to proceed.`;

      setMessages((prev) => {
        const lastAssistantIndex = [...prev].reverse().findIndex(m => m.role === "assistant");
        if (lastAssistantIndex === -1) return prev;

        const actualIndex = prev.length - 1 - lastAssistantIndex;
        const updated = [...prev];
        updated[actualIndex] = {
          ...updated[actualIndex],
          content: updated[actualIndex].content + finalErrorSuffix,
        };
        return updated;
      });

      pushActivityEvent({
        id: makeActivityId(),
        kind: "error",
        label: "Self-healing failed",
        detail: `Could not fix ${commandDetail} after ${MAX_SELF_HEALING_RETRIES} attempts`,
        status: "error",
        timestamp: nowIso(),
      });

      showToast(`Self-healing exhausted after ${MAX_SELF_HEALING_RETRIES} attempts`, "error");
    }
  };

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text) return;

    // Cancel any existing request before starting new one
    if (chatAbortRef.current) {
      chatAbortRef.current.abort();
    }
    chatAbortRef.current = new AbortController();

    // Save to command history
    saveToHistory(text);
    setHistoryIndex(-1);
    setTempInput('');

    const modelSelection = resolveModelForMessage(text);
    const modelIdToSend = modelSelection.modelId;

    const lower = text.toLowerCase();
    const isReviewish = /review|audit|changes|working tree|diff|analy(s|z)e/.test(lower);
    if (isReviewish) {
      startRealTimeAnalysis();
    }

    // Track latest text for retry UX
    lastSentRef.current = text;
    lastAttachmentsRef.current = attachments;
    lastModelIdRef.current = modelIdToSend;
    lastModeIdRef.current = chatMode;

    const userMessage: ChatMessage = {
      id: makeMessageId("user"),
      role: "user",
      content: text,
      createdAt: nowIso(),
      attachments: attachments.length > 0 ? [...attachments] : undefined,
    };

    // Add user message and IMMEDIATE placeholder for assistant response
    // This ensures "Thinking..." appears instantly, not after backend responds
    const placeholderAssistantId = makeMessageId("assistant");
    const placeholderAssistant: ChatMessage = {
      id: placeholderAssistantId,
      role: "assistant",
      content: "",
      createdAt: nowIso(),
      isStreaming: true,  // Show streaming cursor immediately
    };
    setMessages((prev) => [...prev, userMessage, placeholderAssistant]);
    if (!overrideText) setInput("");
    setSending(true);
    setSendTimedOut(false);
    sentViaExtensionRef.current = false;
    // Clear previous activities, narratives, and next steps when starting a new request
    setLastNextSteps([]);
    setNarrativeLines([]);
    // Clear execution plan from previous request
    setExecutionPlan(null);
    // Clear accumulated thinking for new request
    setAccumulatedThinking("");
    setIsThinkingComplete(false);
    setThinkingExpanded(false);
    // Clear execution plan for new task
    setExecutionSteps([]);
    setPlanCollapsed(true);

    // Reset self-healing counters for NEW user-initiated messages (not self-healing retries)
    // Self-healing prompts contain specific patterns we can detect
    const isSelfHealingRetry = text.includes('failed with exit code') || text.includes('The file operation on');
    if (!isSelfHealingRetry) {
      selfHealingRetryCountRef.current = 0;
      lastFailedActionRef.current = null;
    }

    // IMMEDIATE FEEDBACK: Show a single "Thinking" activity
    // The backend will send detailed activity updates - no more frontend rotation
    // This prevents duplicate activities from multiple sources
    const activityLabel = isSelfHealingRetry
      ? `Self-healing (Attempt ${selfHealingRetryCountRef.current}/${MAX_SELF_HEALING_RETRIES})...`
      : "Thinking";

    // Create a SINGLE thinking activity - backend events will update/add more
    setActivityEvents([{
      id: makeActivityId(),
      kind: "thinking" as const,
      label: activityLabel,
      detail: modelSelection.modelName ? `Using ${modelSelection.modelName}` : "",
      status: "running" as const,
      timestamp: nowIso(),
    }]);

    // No more frontend progress rotation - let backend drive activities
    // This eliminates the source of duplicate "Structuring explanation..." etc.
    progressIntervalRef.current = null;

    // Start client-side timeout for responsiveness
    // Use 40 minutes (2,400,000ms) for complex/long-running tasks
    // The timeout only triggers the "still working" UI, not an abort
    if (sendTimeoutRef.current) {
      clearTimeout(sendTimeoutRef.current);
    }
    const LONG_TASK_TIMEOUT_MS = 40 * 60 * 1000; // 40 minutes
    sendTimeoutRef.current = window.setTimeout(() => {
      setSendTimedOut(true);
      showToast("NAVI is still working on your request.", "info");
    }, LONG_TASK_TIMEOUT_MS);

    const hasVsCodeHost = vscodeApi.hasVsCodeHost();

    if (hasVsCodeHost) {
      try {
        console.log(
          "[NAVI] 🚀 ROUTING MESSAGE THROUGH VS CODE EXTENSION:",
          text
        );
        console.log("[NAVI] 📎 Including attachments:", attachments);
        const conversationHistory = messages
          .slice(-MAX_CONVERSATION_HISTORY)
          .map((msg) => ({
            id: msg.id,
            type: msg.role,
            content: msg.content,
            timestamp: msg.createdAt || nowIso(),
          }));
        const lastAssistantState = [...messages]
          .reverse()
          .find((msg) => msg.role === "assistant" && msg.state)?.state;

        vscodeApi.postMessage({
          type: "sendMessage",
          text,
          attachments,
          modelId: modelIdToSend,
          modeId: chatMode,
          orgId: ORG,
          userId: USER_ID,
          conversationId: activeSessionId,  // Send session ID for conversation tracking
          conversationHistory,
          previousState: lastAssistantState,
        });
        sentViaExtensionRef.current = true;

        // We hand off to the extension; it will send botMessage / botThinking
        // We keep `sending=true` until we get a botThinking(false) or botMessage.
        setAttachments([]);
        return;
      } catch (err: any) {
        console.error("[NAVI Chat] Error during VS Code send, falling back:", err);
        showToast(
          "VS Code messaging failed, using direct backend call.",
          "warning"
        );
      }
    } else {
      const greetingKind = getGreetingKind(text);
      if (greetingKind) {
        const replyText = pickGreetingReply(greetingKind);
        const assistantMessage: ChatMessage = {
          id: makeMessageId("assistant"),
          role: "assistant",
          content: replyText,
          createdAt: nowIso(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setAttachments([]);
        setSending(false);
        if (sendTimeoutRef.current) {
          clearTimeout(sendTimeoutRef.current);
          sendTimeoutRef.current = null;
        }
        setSendTimedOut(false);
        setTimeout(() => inputRef.current?.focus(), 10);
        return;
      }

      console.log("[NAVI] No VS Code host detected, calling backend directly.");
    }

    // Direct backend path – used when no VS Code host or bridge errors
    try {
      const data = await sendNaviChatRequest(text, undefined, modelIdToSend, chatMode);
      const routingInfo = normalizeRoutingInfo((data as any)?.context?.llm);
      if (routingInfo) {
        const resolvedName =
          routingInfo.modelName ||
          (routingInfo.modelId
            ? getModelLabel(routingInfo.modelId, modelLabelOverride || undefined)
            : undefined) ||
          (routingInfo.provider ? formatProviderLabel(routingInfo.provider) : undefined);
        setLastRouterInfo({
          ...routingInfo,
          modelName: resolvedName || routingInfo.modelName,
        });
      }
      if (Array.isArray((data as any)?.files_read)) {
        (data as any).files_read.forEach((filePath: string) => {
          pushActivityEvent({
            id: makeActivityId(),
            kind: "read",
            label: "Read file",
            detail: String(filePath),
            filePath: String(filePath),
            status: "done",
            timestamp: nowIso(),
          });
        });
      }
      const replyText = buildAssistantReply(data, text);

      let finalReplyText = replyText;
      const suggestions = Array.isArray((data as any)?.suggestions)
        ? (data as any).suggestions.map((s: unknown) => String(s)).filter((s: string) => s.trim().length > 0)
        : [];
      const nextSteps = Array.isArray((data as any)?.next_steps)
        ? (data as any).next_steps.map((s: unknown) => String(s)).filter((s: string) => s.trim().length > 0)
        : [];
      const followUps = [
        ...suggestions,
        ...nextSteps.filter((step: string) => !suggestions.includes(step))
      ];
      // Store follow-ups for display in dedicated UI section, don't append to message
      if (followUps.length > 0) {
        setLastNextSteps(followUps);
      }
      if (data.progress_steps && data.progress_steps.length > 0) {
        finalReplyText +=
          "\n\n**Processing Steps:**\n" +
          data.progress_steps.map((step) => `Done: ${step}`).join("\n");
      }
      if (data.status) {
        finalReplyText += `\n\n*Status: ${data.status}*`;
      }

      const assistantMessage: ChatMessage = {
        id: makeMessageId("assistant"),
        role: "assistant",
        content: finalReplyText,
        createdAt: nowIso(),
        responseData: data,
        actions: Array.isArray((data as any).actions)
          ? ((data as any).actions as AgentAction[])
          : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setAttachments([]);
    } catch (err: any) {
      console.error("[NAVI Chat] Error during send:", err);
      const errorMessage: ChatMessage = {
        id: makeMessageId("system"),
        role: "system",
        content: `Error talking to Navi: ${err?.message ?? String(err ?? "Unknown error")
          }`,
        createdAt: nowIso(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      showToast("Error talking to Navi backend.", "error");
    } finally {
      setSending(false);
      if (sendTimeoutRef.current) {
        clearTimeout(sendTimeoutRef.current);
        sendTimeoutRef.current = null;
      }
      setSendTimedOut(false);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  };

  const handleDirectFallbackSend = async () => {
    const text = lastSentRef.current.trim();
    if (!text) return;

    if (sendTimeoutRef.current) {
      clearTimeout(sendTimeoutRef.current);
      sendTimeoutRef.current = null;
    }

    setSendTimedOut(false);
    setSending(true);

    try {
      const data = await sendNaviChatRequest(
        text,
        lastAttachmentsRef.current,
        lastModelIdRef.current,
        lastModeIdRef.current
      );
      const routingInfo = normalizeRoutingInfo((data as any)?.context?.llm);
      if (routingInfo) {
        const resolvedName =
          routingInfo.modelName ||
          (routingInfo.modelId
            ? getModelLabel(routingInfo.modelId, modelLabelOverride || undefined)
            : undefined) ||
          (routingInfo.provider ? formatProviderLabel(routingInfo.provider) : undefined);
        setLastRouterInfo({
          ...routingInfo,
          modelName: resolvedName || routingInfo.modelName,
        });
      }
      if (Array.isArray((data as any)?.files_read)) {
        (data as any).files_read.forEach((filePath: string) => {
          pushActivityEvent({
            id: makeActivityId(),
            kind: "read",
            label: "Read file",
            detail: String(filePath),
            filePath: String(filePath),
            status: "done",
            timestamp: nowIso(),
          });
        });
      }
      const replyText = buildAssistantReply(data, text);

      let finalReplyText = replyText;
      if (data.progress_steps && data.progress_steps.length > 0) {
        finalReplyText +=
          "\n\n**Processing Steps:**\n" +
          data.progress_steps.map((step) => `Done: ${step}`).join("\n");
      }
      if (data.status) {
        finalReplyText += `\n\n*Status: ${data.status}*`;
      }

      const assistantMessage: ChatMessage = {
        id: makeMessageId("assistant"),
        role: "assistant",
        content: finalReplyText,
        createdAt: nowIso(),
        responseData: data,
        actions: Array.isArray((data as any).actions)
          ? ((data as any).actions as AgentAction[])
          : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error("[NAVI Chat] Direct fallback error:", err);
      const errorMessage: ChatMessage = {
        id: makeMessageId("system"),
        role: "system",
        content: `Error talking to Navi: ${err?.message ?? String(err ?? "Unknown error")}`,
        createdAt: nowIso(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      showToast("Error talking to Navi backend.", "error");
    } finally {
      setSending(false);
    }
  };

  /* ---------- quick actions ---------- */

  const handleQuickPrompt = (prompt: string) => {
    console.log("[NaviChatPanel] Quick prompt clicked:", prompt);

    // Handle special real-time analysis
    if (prompt === "__LIVE_ANALYSIS__") {
      startRealTimeAnalysis();
      return;
    }

    void handleSend(prompt);
  };

  /* ---------- NAVI V2: approval flow handlers ---------- */

  const handleApproveActions = (planId: string, approvedIndices: number[]) => {
    console.log("[NaviChatPanel] Approving actions for plan:", planId, approvedIndices);
    vscodeApi.postMessage({
      type: "navi.approve",
      planId,
      approvedActionIndices: approvedIndices,
    });
  };

  const handleRejectPlan = (planId: string) => {
    console.log("[NaviChatPanel] Rejecting plan:", planId);
    vscodeApi.postMessage({
      type: "navi.reject",
      planId,
    });
  };

  const handleShowDiff = (planId: string, actionIndex: number) => {
    console.log("[NaviChatPanel] Showing diff for action:", planId, actionIndex);
    vscodeApi.postMessage({
      type: "navi.showDiff",
      planId,
      actionIndex,
    });
  };

  /* ---------- attachments ---------- */

  const handleApplyAllFixes = (reviews: ReviewComment[]) => {
    vscodeApi.postMessage({
      type: "agent.applyReviewFixes",
      reviews,
    });
  };

  const handleRemoveAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  /* ---------- consent handlers ---------- */

  const handleConsentAllow = async (consentId: string) => {
    console.log("[NaviChatPanel] User allowed consent:", consentId);
    const consent = pendingConsents.get(consentId);
    if (!consent) return;

    // Send approval to backend
    vscodeApi.postMessage({
      type: 'command.consent.response',
      consentId,
      approved: true,
      command: consent.command,
    });

    // Remove from pending consents
    setPendingConsents((prev) => {
      const next = new Map(prev);
      next.delete(consentId);
      return next;
    });

    // Send a follow-up message to tell the agent to continue with the approved consent
    // This will trigger the agent to retry the command with the consent_id
    setTimeout(() => {
      vscodeApi.postMessage({
        type: 'navi.user.message',
        content: `I approved the consent. Please retry the command with consent_id: ${consentId}`,
        mode: lastModeIdRef.current || 'agent-full',
        model: lastModelIdRef.current || 'auto',
      });
    }, 500); // Small delay to ensure approval is processed first
  };

  const handleConsentSkip = async (consentId: string) => {
    console.log("[NaviChatPanel] User skipped consent:", consentId);
    const consent = pendingConsents.get(consentId);
    if (!consent) return;

    vscodeApi.postMessage({
      type: 'command.consent.response',
      consentId,
      approved: false,
      command: consent.command,
    });

    setPendingConsents((prev) => {
      const next = new Map(prev);
      next.delete(consentId);
      return next;
    });
  };

  /* ---------- keyboard ---------- */

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    // Enter to send
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
      return;
    }

    // Up arrow - navigate through history
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (commandHistory.length === 0) return;

      if (historyIndex === -1) {
        // Save current input before navigating history
        setTempInput(input);
        setHistoryIndex(commandHistory.length - 1);
        setInput(commandHistory[commandHistory.length - 1]);
      } else if (historyIndex > 0) {
        setHistoryIndex(historyIndex - 1);
        setInput(commandHistory[historyIndex - 1]);
      }
      return;
    }

    // Down arrow - navigate forward in history
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIndex === -1) return;

      if (historyIndex < commandHistory.length - 1) {
        setHistoryIndex(historyIndex + 1);
        setInput(commandHistory[historyIndex + 1]);
      } else {
        // Return to original input
        setHistoryIndex(-1);
        setInput(tempInput);
      }
      return;
    }

    // Escape - clear input or exit history navigation
    if (e.key === "Escape") {
      if (historyIndex !== -1) {
        setHistoryIndex(-1);
        setInput(tempInput);
      } else if (input) {
        setInput("");
      }
      return;
    }
  };

  // Save command to history when sending
  const saveToHistory = (text: string) => {
    if (!text.trim()) return;
    const newHistory = [...commandHistory.filter(cmd => cmd !== text), text].slice(-50);
    setCommandHistory(newHistory);
    try {
      localStorage.setItem('navi-command-history', JSON.stringify(newHistory));
    } catch {
      // Ignore storage errors
    }
  };

  const insertTextAtCursor = (text: string) => {
    const el = inputRef.current;
    if (!el) {
      setInput((prev) => prev + text);
      return;
    }
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    setInput((prev) => prev.slice(0, start) + text + prev.slice(end));
    window.requestAnimationFrame(() => {
      try {
        const pos = start + text.length;
        el.setSelectionRange(pos, pos);
      } catch {
        // ignore
      }
    });
  };

  const copyTextToClipboard = async (text: string): Promise<boolean> => {
    if (vscodeApi.hasVsCodeHost()) {
      try {
        const ok = await vscodeApi.writeClipboard(text);
        if (ok) return true;
      } catch {
        // fall back to native clipboard
      }
    }

    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        return false;
      }
    }

    return false;
  };

  const handlePaste = async (e: ClipboardEvent<HTMLInputElement>) => {
    // Check for image files in clipboard first
    const items = e.clipboardData?.items;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) {
            // Convert image to base64
            const reader = new FileReader();
            reader.onload = (event) => {
              const base64 = event.target?.result as string;
              if (base64) {
                const newAttachment: AttachmentChipData = {
                  id: `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                  kind: 'image',
                  label: file.name || 'Pasted image',
                  content: base64,
                };
                setAttachments((prev) => [...prev, newAttachment]);
                showToast("Image attached", "info");
              }
            };
            reader.onerror = () => {
              console.error("[NAVI] Failed to read pasted image");
              showToast("Failed to process pasted image", "error");
            };
            reader.readAsDataURL(file);
          }
          return;
        }
      }
    }

    // Handle text paste
    const nativeText = e.clipboardData?.getData("text/plain") ?? "";
    if (nativeText) return; // Let native paste handle it
    const canReadNative =
      typeof navigator !== "undefined" && !!navigator.clipboard?.readText;
    if (!vscodeApi.hasVsCodeHost() && !canReadNative) return;
    e.preventDefault();
    try {
      let text = "";
      if (vscodeApi.hasVsCodeHost()) {
        text = (await vscodeApi.readClipboard()) || "";
      }
      if (!text && canReadNative) {
        text = await navigator.clipboard.readText();
      }
      if (!text) return;
      insertTextAtCursor(text);
    } catch (err) {
      console.warn("[NAVI] Clipboard read failed:", err);
    }
  };

  /* ---------- per-message actions ---------- */

  const handleCopyMessage = (msg: ChatMessage) => {
    copyTextToClipboard(msg.content)
      .then((success) => {
        if (success) {
          showToast("Copied to clipboard.", "info");
        } else {
          showToast("Copy failed. Select and copy the text manually.", "error");
        }
      })
      .catch((err) => {
        console.error("[NAVI] Clipboard write error:", err);
        showToast("Copy failed. Select and copy the text manually.", "error");
      });
  };

  const handleEditMessage = (msg: ChatMessage) => {
    // Find the index of the message being edited
    const msgIndex = messages.findIndex((m) => m.id === msg.id);
    if (msgIndex !== -1) {
      // Remove all messages after the edited message (including responses below)
      setMessages((prev) => prev.slice(0, msgIndex));
    }
    setInput(msg.content);
    setTimeout(() => inputRef.current?.focus(), 10);
  };

  const handleUndoMessage = (msg: ChatMessage) => {
    setMessages((prev) => prev.filter((m) => m.id !== msg.id));
  };

  const handleRedoMessage = (msg: ChatMessage) => {
    void handleSend(msg.content);
  };

  // Track liked/disliked messages
  const [likedMessages, setLikedMessages] = useState<Set<string>>(new Set());
  const [dislikedMessages, setDislikedMessages] = useState<Set<string>>(new Set());

  const handleLikeMessage = (msg: ChatMessage) => {
    setLikedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(msg.id)) {
        next.delete(msg.id);
      } else {
        next.add(msg.id);
        // Remove from disliked if it was there
        setDislikedMessages((d) => {
          const nd = new Set(d);
          nd.delete(msg.id);
          return nd;
        });
      }
      return next;
    });
    // Send feedback to backend
    vscodeApi.postMessage({
      type: "feedback",
      messageId: msg.id,
      feedback: "like",
      content: msg.content,
    });
    showToast("Thanks for the feedback!", "info");
  };

  const handleDislikeMessage = (msg: ChatMessage) => {
    setDislikedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(msg.id)) {
        next.delete(msg.id);
      } else {
        next.add(msg.id);
        // Remove from liked if it was there
        setLikedMessages((l) => {
          const nl = new Set(l);
          nl.delete(msg.id);
          return nl;
        });
      }
      return next;
    });
    // Send feedback to backend
    vscodeApi.postMessage({
      type: "feedback",
      messageId: msg.id,
      feedback: "dislike",
      content: msg.content,
    });
    showToast("Thanks for the feedback! We'll improve.", "info");
  };

  const clearCoverageGate = () => {
    setCoverageGate(null);
  };

  const formatActionTitle = (action: AgentAction) => {
    const description = action.description?.trim();
    if (description) return description;
    if (action.type === "runCommand") return "Run command";
    if (action.type === "editFile") return "Apply edit";
    if (action.type === "createFile") return "Create file";
    return "Apply action";
  };

  const formatActionDetail = (action: AgentAction) => {
    if (action.type === "runCommand") return action.command || "";
    if (action.filePath) return action.filePath;
    return action.description || "";
  };

  const renderActivityIcon = (kind: ActivityEvent["kind"]) => {
    switch (kind) {
      case "read":
        return <FileText className="h-3.5 w-3.5 navi-icon-3d" />;
      case "edit":
        return <Pencil className="h-3.5 w-3.5 navi-icon-3d" />;
      case "create":
        return <Plus className="h-3.5 w-3.5 navi-icon-3d" />;
      case "delete":
        return <Trash2 className="h-3.5 w-3.5 navi-icon-3d" />;
      case "command":
        return <Terminal className="h-3.5 w-3.5 navi-icon-3d" />;
      case "error":
        return <AlertTriangle className="h-3.5 w-3.5 navi-icon-3d" />;
      default:
        return <Info className="h-3.5 w-3.5 navi-icon-3d" />;
    }
  };

  const formatActivityStats = (stats?: { added: number; removed: number }) => {
    if (!stats) return "";
    const parts: string[] = [];
    if (typeof stats.added === "number") parts.push(`+${stats.added}`);
    if (typeof stats.removed === "number") parts.push(`-${stats.removed}`);
    return parts.join(" ");
  };

  const mapActivityPayload = (payload: ActivityEventPayload): ActivityEvent | null => {
    const timestamp = new Date(payload.ts || Date.now()).toISOString();
    switch (payload.type) {
      case "tool_search":
        return {
          id: payload.id,
          kind: "info",
          label: "Searched workspace",
          detail: payload.query,
          status: "done",
          timestamp,
        };
      case "file_read":
        return {
          id: payload.id,
          kind: "read",
          label: "Read file",
          detail: payload.path,
          filePath: payload.path,
          status: "done",
          timestamp,
        };
      case "analysis":
        return {
          id: payload.id,
          kind: "info",
          label: "Analysis",
          detail: payload.text,
          status: "done",
          timestamp,
        };
      case "edit": {
        const statsLabel = formatActivityStats(payload.stats);
        return {
          id: payload.id,
          kind: "edit",
          label: payload.summary || "Edited file",
          detail: statsLabel ? `${payload.path} ${statsLabel}` : payload.path,
          filePath: payload.path,
          status: "done",
          timestamp,
        };
      }
      case "progress":
        // Mark as done when progress reaches 100%
        const isDone = typeof payload.percent === "number" && payload.percent >= 100;
        return {
          id: payload.id,
          kind: "info",
          label: payload.label,
          detail: typeof payload.percent === "number" ? `${payload.percent}%` : undefined,
          status: isDone ? "done" : "running",
          timestamp,
        };
      case "error":
        return {
          id: payload.id,
          kind: "error",
          label: payload.message,
          detail: payload.details,
          status: "error",
          timestamp,
        };
      case "phase_start":
        return {
          id: payload.id,
          kind: "info",
          label: payload.title,
          detail: "Phase started",
          status: "running",
          timestamp,
        };
      case "phase_end":
        return {
          id: payload.id,
          kind: "info",
          label: "Phase completed",
          detail: payload.phaseId,
          status: "done",
          timestamp,
        };
      default:
        return null;
    }
  };

  const toWorkspaceRelativePath = (filePath: string) => {
    const { effectiveRoot } = getEffectiveWorkspace();
    if (!effectiveRoot) return filePath;
    const normalizedRoot = effectiveRoot.replace(/[\\/]+$/, "");
    if (filePath.startsWith(normalizedRoot)) {
      const trimmed = filePath.slice(normalizedRoot.length);
      return trimmed.replace(/^[/\\]/, "");
    }
    return filePath;
  };

  const handleOpenActivityDiff = (file: ActivityFile) => {
    if (!file.path) return;
    const scope = file.scope === "staged" ? "staged" : "working";
    vscodeApi.postMessage({
      type: "openDiff",
      path: toWorkspaceRelativePath(file.path),
      scope,
    });
  };

  const handleClearActivityPanel = () => {
    setActivityEvents([]);
    setActivityFiles([]);
    setExpandedActivityFiles(new Set());
    setNarrativeLines([]); // Clear narrative stream
    setActivityFilesOpen(false);
    setActivityOpen(true);
    setPerActionActivities(new Map());
    setPerActionNarratives(new Map());
    setPerActionOutputs(new Map());
    currentActionIndexRef.current = null;
  };

  // Handler for "Keep" button in inline change summary bar
  const handleKeepChanges = () => {
    // Simply dismiss the summary bar - changes are already applied
    setInlineChangeSummary(null);
    showToast("Changes kept", "info");
  };

  // Handler for "Undo" button in inline change summary bar
  const handleUndoChanges = async () => {
    if (!inlineChangeSummary) return;

    // Request undo for each file - either restore original content or delete if newly created
    const filesToUndo = inlineChangeSummary.files.filter(
      (f) => f.originalContent !== undefined || f.wasCreated
    );

    if (filesToUndo.length === 0) {
      showToast("Cannot undo: original content not available", "error");
      setInlineChangeSummary(null);
      return;
    }

    // Send undo request to extension
    for (const file of filesToUndo) {
      vscodeApi.postMessage({
        type: "undoFileChange",
        filePath: file.path,
        originalContent: file.originalContent,
        wasCreated: file.wasCreated, // If true, extension will delete the file
      });
    }

    setInlineChangeSummary(null);
    showToast(`Undone ${filesToUndo.length} file change${filesToUndo.length > 1 ? "s" : ""}`, "info");
  };

  // Handler for "Preview All" button - opens diff view for all changed files
  const handlePreviewAllChanges = () => {
    if (!inlineChangeSummary || inlineChangeSummary.files.length === 0) return;

    // Open diff view for each file
    for (const file of inlineChangeSummary.files) {
      if (file.path) {
        vscodeApi.postMessage({
          type: 'openNativeDiff',
          filePath: file.path,
          scope: 'working',
        });
      }
    }

    showToast(`Opening ${inlineChangeSummary.files.length} file diff${inlineChangeSummary.files.length > 1 ? "s" : ""}`, "info");
  };

  const handleApproveAction = (actions: AgentAction[], actionIndex: number) => {
    const action = actions[actionIndex];

    // Debug logging
    console.log('[NAVI] handleApproveAction called:', {
      actionIndex,
      actionType: action?.type,
      command: action?.command,
      totalActions: actions.length
    });

    if (
      coverageGate?.status === "fail" &&
      action?.type === "runCommand" &&
      action?.meta?.kind !== "coverage" &&
      typeof window !== "undefined"
    ) {
      const coverageValue =
        typeof coverageGate.coverage === "number"
          ? `${coverageGate.coverage.toFixed(1)}%`
          : "unknown";
      const thresholdValue =
        typeof coverageGate.threshold === "number"
          ? `${coverageGate.threshold}%`
          : "the required threshold";
      // Note: VS Code webview doesn't allow confirm() dialogs, so we show a warning toast and proceed
      showToast(
        `Coverage gate: ${coverageValue} vs ${thresholdValue}. Proceeding anyway.`,
        "warning"
      );
    }
    if (!vscodeApi.hasVsCodeHost()) {
      showToast("Command actions require the VS Code host.", "warning");
      return;
    }

    console.log('[NAVI] Posting agent.applyAction message to extension');

    // Open activity panel to show live progress
    if (activityPanelState && !activityPanelState.isVisible) {
      console.log('[NAVI] Auto-opening activity panel for action execution');
      activityPanelState.setIsVisible(true);
    }

    vscodeApi.postMessage({
      type: "agent.applyAction",
      decision: "approve",
      actionIndex,
      actions,
      approvedViaChat: true,
    });
  };

  const handleCopyActionCommand = (command?: string) => {
    if (!command) return;
    copyTextToClipboard(command)
      .then((success) => {
        if (success) {
          showToast("Command copied to clipboard.", "info");
        } else {
          showToast("Copy failed. Select and copy manually.", "error");
        }
      })
      .catch((err) => {
        console.error("[NAVI] Clipboard write error:", err);
        showToast("Copy failed. Select and copy manually.", "error");
      });
  };

  const fetchAutonomousSteps = async (taskId: string) => {
    try {
      const response = await fetch(
        `${resolveBackendBase()}/api/autonomous/tasks/${taskId}/steps`,
        { headers: buildHeaders() }
      );
      if (response.ok) {
        const steps = await response.json();
        setAutonomousSteps(prev => ({
          ...prev,
          [taskId]: steps
        }));

        // Initialize activity panel with the fetched steps
        if (activityPanelState) {
          const agentRun = messages.find(m => m.state?.task_id === taskId)?.agentRun;
          if (agentRun) {
            activityPanelState.initializeSteps(agentRun, steps);
          }
        }
      }
    } catch (error) {
      console.error('[Autonomous] Failed to fetch steps:', error);
    }
  };

  const renderMessageContent = (msg: ChatMessage) => {
    if (msg.meta?.kind === "command") {
      return (
        <pre className="navi-chat-command-output">{msg.content}</pre>
      );
    }

    // Check if this is an autonomous coding message
    if (msg.agentRun?.mode === 'autonomous_coding' && msg.state?.task_id) {
      const taskId = msg.state.task_id;
      const steps = autonomousSteps[taskId] || [];
      const currentStepIndex = msg.state.current_step || 0;
      const workspace = msg.state.workspace || '';

      return (
        <div>
          <div>{msg.content.split("\n").map((line, idx) => (
            <p key={idx}>{line}</p>
          ))}</div>

          {steps.length > 0 && (
            <AutonomousStepApproval
              taskId={taskId}
              steps={steps}
              currentStepIndex={currentStepIndex}
              workspace={workspace}
              onStepComplete={(result) => {
                console.log('[Autonomous] Step completed:', result);
                // Update the message state to move to next step
                if (result.status === 'completed' && result.next_step) {
                  setMessages(prev => prev.map(m => {
                    if (m.id === msg.id && m.state) {
                      return {
                        ...m,
                        state: {
                          ...m.state,
                          current_step: (m.state.current_step || 0) + 1,
                        }
                      };
                    }
                    return m;
                  }));
                }
              }}
              onTaskComplete={() => {
                console.log('[Autonomous] Task completed!');
                showToast('Autonomous task completed successfully!', 'info');
              }}
            />
          )}
        </div>
      );
    }

    // Render content with optional streaming cursor
    // Clean up content if it's wrapped in JSON format like { "message": "..." }
    let cleanContent = msg.content;

    // First, handle escaped newlines and other escape sequences from JSON streaming
    // This converts \\n to actual newlines, \\t to tabs, etc.
    cleanContent = cleanContent
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\r/g, '\r')
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\');

    // Also handle JSON-wrapped content
    if (cleanContent.trim().startsWith('{ "message":') || cleanContent.trim().startsWith('{"message":')) {
      try {
        const parsed = JSON.parse(cleanContent);
        if (parsed.message) {
          cleanContent = parsed.message;
        }
      } catch {
        // If parsing fails, try to extract message with regex
        const match = cleanContent.match(/"message"\s*:\s*"((?:[^"\\]|\\.)*)"/s);
        if (match) {
          cleanContent = match[1]
            .replace(/\\n/g, '\n')
            .replace(/\\t/g, '\t')
            .replace(/\\"/g, '"')
            .replace(/\\\\/g, '\\');
        }
      }
    }

    // Parse content into blocks (text blocks and code blocks)
    const parseContentBlocks = (content: string): Array<{ type: 'text' | 'code'; content: string; language?: string }> => {
      const blocks: Array<{ type: 'text' | 'code'; content: string; language?: string }> = [];
      const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g;
      let lastIndex = 0;
      let match;

      while ((match = codeBlockRegex.exec(content)) !== null) {
        // Add text before this code block
        if (match.index > lastIndex) {
          const textBefore = content.slice(lastIndex, match.index);
          if (textBefore.trim()) {
            blocks.push({ type: 'text', content: textBefore });
          }
        }
        // Add the code block
        const language = match[1] || 'plaintext';
        const code = match[2] || '';
        blocks.push({ type: 'code', content: code, language });
        lastIndex = match.index + match[0].length;
      }

      // Add remaining text after last code block
      if (lastIndex < content.length) {
        const remaining = content.slice(lastIndex);
        if (remaining.trim()) {
          blocks.push({ type: 'text', content: remaining });
        }
      }

      // If no code blocks found, treat entire content as text
      if (blocks.length === 0 && content.trim()) {
        blocks.push({ type: 'text', content });
      }

      return blocks;
    };

    // File icon color mapping by extension (VS Code-like colors)
    const FILE_ICON_COLORS: Record<string, string> = {
      '.ts': '#3178c6', '.tsx': '#3178c6',
      '.js': '#f7df1e', '.jsx': '#61dafb', '.mjs': '#f7df1e',
      '.py': '#3776ab', '.pyw': '#3776ab',
      '.json': '#cbcb41', '.jsonc': '#cbcb41',
      '.md': '#519aba', '.mdx': '#519aba', '.txt': '#6d8086',
      '.css': '#563d7c', '.scss': '#cd6799', '.sass': '#cd6799', '.less': '#1d365d',
      '.html': '#e34f26', '.htm': '#e34f26',
      '.yaml': '#cb171e', '.yml': '#cb171e', '.toml': '#9c4121', '.ini': '#6d8086', '.env': '#ecd53f',
      '.sql': '#e38c00', '.db': '#e38c00',
      '.png': '#a074c4', '.jpg': '#a074c4', '.jpeg': '#a074c4', '.gif': '#a074c4', '.svg': '#ffb13b', '.ico': '#a074c4',
      '.rs': '#dea584', '.go': '#00add8', '.rb': '#cc342d', '.java': '#b07219', '.kt': '#a97bff',
      '.sh': '#89e051', '.bash': '#89e051', '.zsh': '#89e051',
      '.vue': '#41b883', '.svelte': '#ff3e00',
      '.graphql': '#e535ab', '.gql': '#e535ab',
      '.dockerfile': '#384d54', '.docker': '#384d54',
      '.lock': '#6d8086',
      'default': '#6d8086'
    };

    const getFileIconColor = (path: string): string => {
      const ext = path.substring(path.lastIndexOf('.')).toLowerCase();
      if (path.toLowerCase().includes('dockerfile')) return '#384d54';
      return FILE_ICON_COLORS[ext] || FILE_ICON_COLORS['default'];
    };

    const getFileIconClass = (path: string): string => {
      const ext = path.substring(path.lastIndexOf('.')).toLowerCase().replace('.', '');
      if (path.toLowerCase().includes('dockerfile')) return 'docker';
      return ext || 'default';
    };

    // Get different SVG icon based on file type
    const getFileIconSvg = (path: string, color: string): string => {
      const ext = path.substring(path.lastIndexOf('.')).toLowerCase();
      const iconClass = getFileIconClass(path);
      const baseClass = `navi-file-svg navi-file-svg--${iconClass}`;
      const baseStyle = `color: ${color}`;

      // Code files - icon with brackets <>
      const codeExts = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.py', '.pyw', '.go', '.rs', '.rb', '.java', '.kt', '.c', '.cpp', '.h', '.cs', '.php', '.swift', '.vue', '.svelte', '.html', '.htm', '.css', '.scss', '.sass', '.less'];
      if (codeExts.includes(ext)) {
        return `<svg class="${baseClass}" width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="${baseStyle}"><path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M10 12L8 14L10 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M14 12L16 14L14 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      }

      // JSON files - brackets {}
      if (['.json', '.jsonc'].includes(ext)) {
        return `<svg class="${baseClass}" width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="${baseStyle}"><path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 12C8.45 12 8 12.45 8 13V13.5C8 14.05 7.55 14.5 7 14.5C7.55 14.5 8 14.95 8 15.5V16C8 16.55 8.45 17 9 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 12C15.55 12 16 12.45 16 13V13.5C16 14.05 16.45 14.5 17 14.5C16.45 14.5 16 14.95 16 15.5V16C16 16.55 15.55 17 15 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      }

      // Config/settings files - cog icon
      const configExts = ['.yaml', '.yml', '.toml', '.env', '.ini', '.conf', '.config', '.lock'];
      if (configExts.includes(ext) || path.toLowerCase().includes('dockerfile')) {
        return `<svg class="${baseClass}" width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="${baseStyle}"><path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="14.5" r="2" stroke="currentColor" stroke-width="1.5"/><path d="M12 11.5V12.5M12 16.5V17.5M14.12 13.38L13.41 13.38M10.59 15.62L9.88 15.62M14.12 15.62L13.41 14.91M10.59 13.38L9.88 14.09" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>`;
      }

      // Text/markdown files - document with lines
      const textExts = ['.md', '.mdx', '.txt', '.rst', '.doc', '.docx', '.rtf'];
      if (textExts.includes(ext)) {
        return `<svg class="${baseClass}" width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="${baseStyle}"><path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><line x1="8" y1="13" x2="16" y2="13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="8" y1="17" x2="13" y2="17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;
      }

      // SQL files - database icon
      if (['.sql'].includes(ext)) {
        return `<svg class="${baseClass}" width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="${baseStyle}"><path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><ellipse cx="12" cy="13" rx="4" ry="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M8 13V16C8 16.83 9.79 17.5 12 17.5C14.21 17.5 16 16.83 16 16V13" stroke="currentColor" stroke-width="1.5"/></svg>`;
      }

      // Default file icon
      return `<svg class="${baseClass}" width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="${baseStyle}"><path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    };

    // Make URLs and file paths clickable
    const makeLinksClickable = (html: string): string => {
      let result = html;

      // First, handle markdown links: [text](url) - convert to anchor tags
      // This prevents the URL from being matched again by the raw URL pattern
      // Handle URLs with accidental spaces ANYWHERE (LLM tokenization artifact)
      // Pattern allows spaces in: "http ://", "http: //", "http :/ /", etc.
      const markdownLinkPattern = /\[([^\]]+)\]\((https?\s*:\s*\/\s*\/\s*[^)]+)\)/g;
      result = result.replace(markdownLinkPattern, (_match, text, url) => {
        // Clean up URL: remove ALL spaces from the URL
        const cleanUrl = url.replace(/\s+/g, '');
        // Clean up display text too
        const cleanText = text.replace(/\s+/g, '');
        // If text matches URL (e.g., [http://localhost:3000](http://localhost:3000))
        // just show the URL once
        const displayText = cleanText === cleanUrl ? cleanUrl : cleanText;
        return `<a href="${cleanUrl}" class="navi-link navi-link--url" target="_blank" rel="noopener noreferrer">${displayText}</a>`;
      });

      // URL pattern - matches http/https links with potential spaces (LLM tokenization)
      // Pattern allows: "http://", "http ://", "http: //", "http :/ /" etc.
      // Skip URLs that are already converted (inside href="" or between > and <)
      const urlPattern = /(https?\s*:\s*\/\s*\/\s*[^\s<>"'\[\]]+)/g;
      result = result.replace(urlPattern, (url: string, _p1: string, position: number) => {
        // Check if this URL is already inside an anchor tag by looking at context
        const before = result.substring(Math.max(0, position - 15), position);
        // Skip if preceded by href=" or "> (already in anchor tag)
        if (/href="$/.test(before) || /">$/.test(before)) {
          return url; // Don't modify - already in anchor
        }
        // Clean up URL: remove all internal spaces
        let cleanUrl = url.replace(/\s+/g, '');
        // Only strip trailing period/comma if it's at the very end (likely punctuation, not part of URL)
        if (/[.,;:!?]$/.test(cleanUrl) && !/:\d+[.,;:!?]?$/.test(cleanUrl)) {
          cleanUrl = cleanUrl.replace(/[.,;:!?]+$/, '');
        }
        return `<a href="${cleanUrl}" class="navi-link navi-link--url" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>`;
      });

      // File path pattern - matches common code file paths
      // Only match paths that:
      // 1. Start with / (absolute path like /Users/foo/bar.txt)
      // 2. Start with ./ or ../ (relative path like ./src/file.ts)
      // 3. Have directory structure with common code directories
      // 4. Match filenames with extensions when wrapped in backticks
      // Do NOT match: Next.js, server.The, fresh.I've, Node.js, etc.
      const commonDirs = 'src|lib|components|pages|app|backend|frontend|extensions|webview|utils|services|api|hooks|types|tests|test|__tests__|spec|config|configs|scripts|bin|dist|build|public|static|assets|styles|css|templates|views|models|controllers|routes|middleware|helpers|core|common|shared|modules|features|domains';
      const filePathPattern = new RegExp(
        `(?:^|[\\s(])((\\/[\\w\\-.]+)+\\.\\w+|(\\.\\.\\/[\\w\\-./]+\\.\\w+)|((?:${commonDirs})\\/[\\w\\-./]+\\.\\w+)|([\\w\\-]+\\.(?:tsx?|jsx?|py|go|rs|rb|java|cs|cpp|c|h|css|scss|less|html|json|ya?ml|toml|md|sql)))(?::(\\d+))?(?=[\\s),.:;!?]|$)`,
        'g'
      );
      result = result.replace(filePathPattern, (match, fullPath, _p1, _p2, _p3, _p4, lineNum) => {
        // Preserve leading whitespace/punctuation
        const leadingMatch = match.match(/^[\s(]/) || [''];
        const leading = leadingMatch[0];
        const pathPart = match.slice(leading.length);
        const pathWithoutLine = pathPart.replace(/:(\d+)$/, '');
        const iconColor = getFileIconColor(pathWithoutLine);
        const dataLine = lineNum ? ` data-line="${lineNum}"` : '';
        // Use file-type specific SVG icon
        const svgIcon = getFileIconSvg(pathWithoutLine, iconColor);
        // Wrap in span with SVG icon
        return `${leading}<span class="navi-file-link">${svgIcon}<a href="#" class="navi-link navi-link--file" data-file-path="${pathWithoutLine}"${dataLine}>${pathWithoutLine}</a></span>`;
      });

      return result;
    };

    // Render a text block with markdown-like formatting
    const renderTextBlock = (text: string, keyPrefix: string, isStreaming = false) => {
      // During streaming, render as flowing text to avoid fragmentation
      // Only apply paragraph formatting after streaming completes
      if (isStreaming) {
        // Simple inline rendering during streaming
        let formatted = text
          .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
          .replace(/`([^`]+)`/g, '<code class="navi-inline-code">$1</code>');
        formatted = makeLinksClickable(formatted);
        // Convert newlines to spaces for flowing text during streaming
        formatted = formatted.replace(/\n/g, ' ');
        return <span key={keyPrefix} dangerouslySetInnerHTML={{ __html: formatted }} />;
      }

      // After streaming: full markdown-like formatting with paragraphs
      // First, normalize the text to prevent fragmented paragraphs from streaming artifacts
      // - Double newlines (\n\n) indicate intentional paragraph breaks
      // - Single newlines within flowing text should be treated as spaces (like markdown)
      // - Preserve newlines before markdown elements (headers, lists)

      // Split by double newlines to get true paragraphs
      const paragraphs = text.split(/\n\n+/);

      return paragraphs.map((paragraph, pIdx) => {
        // Check if this paragraph contains markdown elements that need line-by-line processing
        const lines = paragraph.split('\n');
        const hasMarkdownElements = lines.some(line =>
          line.startsWith('# ') ||
          line.startsWith('## ') ||
          line.startsWith('- ') ||
          line.startsWith('* ') ||
          /^\d+[\.\)]\s/.test(line)
        );

        if (hasMarkdownElements) {
          // Helper to format inline markdown (bold, code, links)
          const formatInline = (content: string): string => {
            let result = content
              .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
              .replace(/`([^`]+)`/g, '<code class="navi-inline-code">$1</code>');
            return makeLinksClickable(result);
          };

          // Process line by line for markdown elements
          return lines.map((line, idx) => {
            // Handle headers (with inline formatting)
            if (line.startsWith('# ')) {
              const content = formatInline(line.slice(2));
              return <h3 key={`${keyPrefix}-${pIdx}-${idx}`} className="navi-heading" dangerouslySetInnerHTML={{ __html: content }} />;
            }
            if (line.startsWith('## ')) {
              const content = formatInline(line.slice(3));
              return <h4 key={`${keyPrefix}-${pIdx}-${idx}`} className="navi-heading" dangerouslySetInnerHTML={{ __html: content }} />;
            }
            // Handle list items (with inline formatting)
            if (line.startsWith('- ') || line.startsWith('* ')) {
              const content = formatInline(line.slice(2));
              return <li key={`${keyPrefix}-${pIdx}-${idx}`} className="navi-list-item" dangerouslySetInnerHTML={{ __html: content }} />;
            }
            if (/^\d+[\.\)]\s/.test(line)) {
              const content = formatInline(line.replace(/^\d+[\.\)]\s/, ''));
              return <li key={`${keyPrefix}-${pIdx}-${idx}`} className="navi-list-item" dangerouslySetInnerHTML={{ __html: content }} />;
            }
            // Skip empty lines within markdown blocks
            if (line.trim() === '') {
              return null;
            }
            // Regular text line - format inline
            const formattedLine = formatInline(line);
            return <p key={`${keyPrefix}-${pIdx}-${idx}`} dangerouslySetInnerHTML={{ __html: formattedLine }} />;
          }).filter(Boolean);
        }

        // No markdown elements - treat as flowing paragraph
        // Join single newlines with spaces to create flowing text
        const flowingText = paragraph.replace(/\n/g, ' ').trim();
        if (!flowingText) {
          return <br key={`${keyPrefix}-${pIdx}`} />;
        }

        // Handle bold text
        const formattedLine = flowingText.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        // Handle inline code
        const withCode = formattedLine.replace(/`([^`]+)`/g, '<code class="navi-inline-code">$1</code>');
        // Make URLs and file paths clickable
        const withLinks = makeLinksClickable(withCode);
        return <p key={`${keyPrefix}-${pIdx}`} dangerouslySetInnerHTML={{ __html: withLinks }} />;
      });
    };

    // Render a code block with syntax highlighting
    const renderCodeBlock = (code: string, language: string, key: string) => {
      // Try to use Prism for syntax highlighting
      let highlightedCode = code;
      const prismLang = language === 'js' ? 'javascript'
        : language === 'ts' ? 'typescript'
          : language === 'py' ? 'python'
            : language === 'sh' ? 'bash'
              : language;

      if (Prism.languages[prismLang]) {
        try {
          highlightedCode = Prism.highlight(code, Prism.languages[prismLang], prismLang);
        } catch {
          // Fall back to plain code
        }
      }

      return (
        <div key={key} className="navi-code-block-wrapper">
          <div className="navi-code-block-header">
            <span className="navi-code-language">{language || 'code'}</span>
            <button
              className="navi-code-copy-btn"
              onClick={() => {
                navigator.clipboard.writeText(code);
                showToast('Code copied!', 'info');
              }}
            >
              <Copy size={12} /> Copy
            </button>
          </div>
          <pre className="navi-code-block">
            <code
              className={`language-${prismLang}`}
              dangerouslySetInnerHTML={{ __html: highlightedCode }}
            />
          </pre>
        </div>
      );
    };

    const blocks = parseContentBlocks(cleanContent);

    return (
      <div className="navi-message-content">
        {blocks.map((block, idx) => {
          if (block.type === 'code') {
            return renderCodeBlock(block.content, block.language || 'plaintext', `code-${idx}`);
          }
          return (
            <div key={`text-${idx}`}>
              {renderTextBlock(block.content, `text-${idx}`, msg.isStreaming)}
            </div>
          );
        })}
        {msg.isStreaming && (
          <span className="navi-streaming-cursor">▊</span>
        )}
      </div>
    );
  };

  const resetConversationState = () => {
    setMessages([]);
    setInput("");
    setAttachments([]);
    setStructuredReview(null);
    setAnalysisProgress([]);
    // setAnalysisSummary(null);
    setCurrentProgress(0);
    setIsAnalyzing(false);
    setCoverageGate(null);
    setTerminalEntries([]);
    setTerminalOpen(true);
    setActivityEvents([]);
    setActivityFiles([]);
    setExpandedActivityFiles(new Set());
    setNarrativeLines([]); // Clear narrative stream
    setActivityOpen(true);
    setActivityFilesOpen(false);
    setPerActionActivities(new Map());
    setPerActionNarratives(new Map());
    setPerActionOutputs(new Map());
    setRepoSummary(null);
    setDiffDetails([]);
    setChangeDetailsOpen(false);
    setLastRouterInfo(null);
    setInlineChangeSummary(null); // Reset inline change summary bar
    commandActivityRef.current.clear();
    actionActivityRef.current.clear();
    thinkingActivityRef.current = null;
    currentActionIndexRef.current = null;
    lastLiveProgressRef.current = "";
    pendingActionCountRef.current = 0;
    actionSummaryRef.current = [];
    if (actionSummaryTimerRef.current) {
      clearTimeout(actionSummaryTimerRef.current);
      actionSummaryTimerRef.current = null;
    }
    if (analysisAbortRef.current) {
      analysisAbortRef.current.abort();
      analysisAbortRef.current = null;
    }
    lastSentRef.current = "";
    lastAttachmentsRef.current = [];
    if (sendTimeoutRef.current) {
      clearTimeout(sendTimeoutRef.current);
      sendTimeoutRef.current = null;
    }
    setSendTimedOut(false);
    setSending(false);
  };

  const getStoredSessionSeed = () => {
    const storedId = getActiveSessionId();
    const storedSession = storedId ? getSession(storedId) : null;
    return {
      repoName: storedSession?.repoName,
      workspaceRoot: storedSession?.workspaceRoot,
    };
  };

  const requestExtensionReset = () => {
    if (!vscodeApi.hasVsCodeHost()) return;
    pendingResetRef.current = true;
    if (resetTimeoutRef.current) {
      clearTimeout(resetTimeoutRef.current);
      resetTimeoutRef.current = null;
    }
    // Send conversation.new to extension to create new conversation
    vscodeApi.postMessage({ type: "conversation.new" });
    resetTimeoutRef.current = window.setTimeout(() => {
      pendingResetRef.current = false;
      resetTimeoutRef.current = null;
    }, 1500);
  };

  const startNewSession = (seed?: { repoName?: string; workspaceRoot?: string }) => {
    const session = createSession(seed);
    persistActiveSessionId(session.id);
    setActiveSessionId(session.id);
    resetConversationState();
    setTimeout(() => inputRef.current?.focus(), 10);
  };

  /* ---------- clear chat ---------- */

  const handleClearChat = () => {
    resetConversationState();
    if (activeSessionId) {
      clearSessionMessages(activeSessionId);
      clearSessionDraft(activeSessionId);
      updateSession(activeSessionId, {
        title: "New chat",
        messageCount: 0,
        lastMessagePreview: undefined,
      });
    }
    requestExtensionReset();
    setHistoryOpen(false);
    setTimeout(() => inputRef.current?.focus(), 10);
  };

  const handleNewChat = () => {
    const { effectiveRoot, effectiveRepoName } = getEffectiveWorkspace();
    const storedSeed = getStoredSessionSeed();
    startNewSession({
      repoName: effectiveRepoName || storedSeed.repoName,
      workspaceRoot: effectiveRoot || storedSeed.workspaceRoot,
    });
    requestExtensionReset();
    setHistoryOpen(false);
  };

  const handleAutoFix = (fileName: string, issue: any) => {
    if (!vscodeApi.hasVsCodeHost()) {
      showToast("Auto-fix requires the VS Code host.", "warning");
      return;
    }

    showToast(`Applying auto-fix for ${fileName}...`, "info");
    vscodeApi.postMessage({
      type: "autoFix",
      fileName,
      issue,
    });
  };

  const startRealTimeAnalysis = async () => {
    setIsAnalyzing(true);
    setAnalysisProgress([]);
    setCurrentProgress(0);
    setStructuredReview(null);
    setReviewViewMode("issues");
    // setAnalysisSummary(null);

    try {
      if (analysisAbortRef.current) {
        analysisAbortRef.current.abort();
      }
      const controller = new AbortController();
      analysisAbortRef.current = controller;

      const { effectiveRoot } = getEffectiveWorkspace();

      const backendBase = resolveBackendBase();
      const response = await fetch(`${backendBase}/api/navi/analyze-changes`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          workspace_root: effectiveRoot
        }),
        signal: controller.signal,
      });

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const appendStep = (step: string) => {
        setAnalysisProgress((prev) => {
          if (prev[prev.length - 1] === step) return prev;
          return [...prev, step];
        });
      };

      const updateProgress = (value: unknown) => {
        if (typeof value !== "number" || Number.isNaN(value)) return;
        setCurrentProgress((prev) => Math.max(prev, value));
      };

      const handlePayload = (payload: string) => {
        if (!payload.trim()) return;
        try {
          const data = JSON.parse(payload);

          if (data.type === 'progress') {
            if (data.step) appendStep(String(data.step));
            updateProgress(data.progress);
          } else if (data.type === 'summary') {
            // setAnalysisSummary({
            //   total_files: data.total_files ?? 0,
            //   detailed_files: data.detailed_files ?? 0,
            //   skipped_files: data.skipped_files ?? 0,
            //   highlights: Array.isArray(data.highlights) ? data.highlights : [],
            // });
          } else if (data.type === 'review') {
            const reviewData = JSON.parse(data.payload);
            setStructuredReview(reviewData);
          } else if (data.type === 'complete') {
            updateProgress(data.progress ?? 100);
            setIsAnalyzing(false);
            if (Array.isArray(data.results)) {
              const files = data.results.map((item: any, index: number) => ({
                path: item?.path || `file-${index + 1}`,
                severity: item?.severity,
                diff: item?.diff,
                issues: Array.isArray(item?.issues)
                  ? item.issues.map((issue: any, issueIndex: number) => ({
                    id: issue?.id || `issue-${index + 1}-${issueIndex + 1}`,
                    title: issue?.title || "Issue",
                    body: issue?.body || issue?.message || "",
                    canAutoFix: Boolean(issue?.canAutoFix),
                  }))
                  : [],
              }));

              // const issueCount = files.reduce(
              //   (sum: number, file: StructuredReviewFile) => sum + (file.issues?.length || 0),
              //   0
              // );

              // const warning =
              //   typeof data.warning === "string" && data.warning.trim()
              //     ? data.warning.trim()
              //     : "";

              setStructuredReview({ files });
              // setAnalysisSummary({
              //   total_files: files.length,
              //   detailed_files: files.length,
              //   skipped_files: 0,
              //   highlights: [
              //     ...(warning ? [warning] : []),
              //     ...(issueCount
              //       ? [`${issueCount} issues detected across ${files.length} files`]
              //       : ["No issues detected in changed files"]),
              //   ],
              // });
            }
            showToast('Analysis complete.', 'info');
          } else if (data.type === 'error') {
            setIsAnalyzing(false);
            showToast(`Analysis failed: ${data.message}`, 'error');
          }
        } catch (e) {
          console.warn('Failed to parse SSE data:', payload);
        }
      };

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const payload = trimmed.replace(/^data:\s?/, "");
          handlePayload(payload);
        }
      }

      if (buffer.trim().startsWith("data:")) {
        const payload = buffer.trim().replace(/^data:\s?/, "");
        handlePayload(payload);
      }

      if (analysisAbortRef.current === controller) {
        analysisAbortRef.current = null;
      }
    } catch (error) {
      const message = String((error as any)?.message || error || "");
      if ((error as any)?.name === "AbortError" || message.toLowerCase().includes("aborted")) {
        return;
      }
      setIsAnalyzing(false);
      showToast(`Failed to start analysis: ${error}`, 'error');
      console.error('Analysis error:', error);
    }
  };

  /* ---------- render ---------- */

  const scopeIsChangedFiles = scopeDecision === "changed-files";
  const scopeIsWorkspace = scopeDecision === "workspace";
  const selectedModelName = getModelLabel(selectedModelId, modelLabelOverride || undefined);
  const autoBadgeLabel = "Auto -> server routing";
  const resolvedRouterName =
    lastRouterInfo?.modelName ||
    (lastRouterInfo?.modelId
      ? getModelLabel(lastRouterInfo.modelId, modelLabelOverride || undefined)
      : undefined) ||
    (lastRouterInfo?.provider ? formatProviderLabel(lastRouterInfo.provider) : undefined);
  const routerTaskLabel = formatTaskLabel(
    lastRouterInfo?.taskType || (lastRouterInfo?.source === "manual" ? "manual" : undefined)
  );
  const routerBadgeLabel = lastRouterInfo
    ? `${routerTaskLabel} -> ${resolvedRouterName || selectedModelName}`
    : useAutoModel && selectedModelId === AUTO_MODEL_ID
      ? autoBadgeLabel
      : `Manual -> ${selectedModelName}`;
  const quickActions = useMemo(() => {
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const contextSeed = input.trim() || lastAssistant?.content || lastUser?.content || "";
    return buildQuickActions(contextSeed);
  }, [input, messages]);
  const terminalRunning = terminalEntries.some((entry) => entry.status === "running");
  const hasActivityEvents = activityEvents.length > 0;
  const hasActivityFiles = activityFiles.length > 0;
  const hasRunningActivity = activityEvents.some((event) => event.status === "running");
  const activityLive = sending || isAnalyzing || hasRunningActivity;
  // Show activity stream while working OR when there are recent activities (keep visible after completion)
  const showActivityStream = activityLive || activityEvents.length > 0;
  // Get the current (latest) activity to display
  const currentActivity = activityEvents.length > 0
    ? activityEvents[activityEvents.length - 1]
    : null;
  const showTypingIndicator = sending && !showActivityStream;
  const changeSummary = useMemo(() => {
    const hasDiffs = diffDetails.length > 0;
    const hasActivityFiles = activityFiles.length > 0;
    if (!hasDiffs && !hasActivityFiles) return null;

    const byPath = new Map<
      string,
      {
        path: string;
        additions?: number;
        deletions?: number;
        scope: "staged" | "unstaged" | "working";
      }
    >();

    diffDetails.forEach((detail) => {
      const additions = typeof detail.additions === "number" ? detail.additions : undefined;
      const deletions = typeof detail.deletions === "number" ? detail.deletions : undefined;
      const existing = byPath.get(detail.path);
      if (existing) {
        if (typeof additions === "number") {
          existing.additions = (existing.additions ?? 0) + additions;
        }
        if (typeof deletions === "number") {
          existing.deletions = (existing.deletions ?? 0) + deletions;
        }
        existing.scope = existing.scope || detail.scope;
      } else {
        byPath.set(detail.path, {
          path: detail.path,
          additions,
          deletions,
          scope: detail.scope || "unstaged",
        });
      }
    });

    activityFiles.forEach((file) => {
      const additions = typeof file.additions === "number" ? file.additions : undefined;
      const deletions = typeof file.deletions === "number" ? file.deletions : undefined;
      const incomingHasNumbers =
        typeof additions === "number" || typeof deletions === "number";
      const existing = byPath.get(file.path);
      if (!existing) {
        byPath.set(file.path, {
          path: file.path,
          additions,
          deletions,
          scope: file.scope || "working",
        });
        return;
      }

      const existingHasNumbers =
        typeof existing.additions === "number" || typeof existing.deletions === "number";
      if (incomingHasNumbers && !existingHasNumbers) {
        existing.additions = additions;
        existing.deletions = deletions;
      } else if (incomingHasNumbers && existingHasNumbers) {
        if (typeof additions === "number") {
          existing.additions =
            typeof existing.additions === "number"
              ? Math.max(existing.additions, additions)
              : additions;
        }
        if (typeof deletions === "number") {
          existing.deletions =
            typeof existing.deletions === "number"
              ? Math.max(existing.deletions, deletions)
              : deletions;
        }
      }

      if (!existing.scope && file.scope) {
        existing.scope = file.scope;
      }
    });

    const files = Array.from(byPath.values());
    return {
      count: files.length,
      files,
    };
  }, [diffDetails, activityFiles]);
  const activityFileList = useMemo(() => {
    if (!changeSummary) return [];
    const activityByPath = new Map(
      activityFiles.map((file) => [file.path, file])
    );
    const diffByPath = new Map(
      diffDetails.map((detail) => [detail.path, detail])
    );
    return [...changeSummary.files]
      .map((file) => {
        const activityFile = activityByPath.get(file.path);
        const diffDetail = diffByPath.get(file.path);
        return {
          ...file,
          diff: activityFile?.diff ?? diffDetail?.diff,
          lastTouched: activityFile?.lastTouched,
        };
      })
      .sort((a, b) => {
        const at = a.lastTouched ? new Date(a.lastTouched).getTime() : 0;
        const bt = b.lastTouched ? new Date(b.lastTouched).getTime() : 0;
        return bt - at;
      });
  }, [changeSummary, activityFiles, diffDetails]);
  const changeTotals = useMemo(() => {
    if (!changeSummary) return null;
    let additions = 0;
    let deletions = 0;
    let hasStats = false;
    changeSummary.files.forEach((file) => {
      if (typeof file.additions === "number") {
        additions += file.additions;
        hasStats = true;
      }
      if (typeof file.deletions === "number") {
        deletions += file.deletions;
        hasStats = true;
      }
    });
    return { additions, deletions, hasStats };
  }, [changeSummary]);
  const activityFileSummary = useMemo(() => {
    if (changeSummary && changeTotals) {
      return {
        count: changeSummary.count,
        additions: changeTotals.additions,
        deletions: changeTotals.deletions,
        hasStats: changeTotals.hasStats,
      };
    }
    if (activityFiles.length === 0) {
      return { count: 0, additions: 0, deletions: 0, hasStats: false };
    }
    const totals = activityFiles.reduce(
      (acc, file) => {
        if (typeof file.additions === "number") {
          acc.additions += file.additions;
          acc.hasStats = true;
        }
        if (typeof file.deletions === "number") {
          acc.deletions += file.deletions;
          acc.hasStats = true;
        }
        return acc;
      },
      { additions: 0, deletions: 0, hasStats: false }
    );
    return {
      count: activityFiles.length,
      additions: totals.additions,
      deletions: totals.deletions,
      hasStats: totals.hasStats,
    };
  }, [changeSummary, changeTotals, activityFiles]);

  const historySessions = historyOpen ? listSessions() : [];
  const hasChangeSummary = Boolean(changeSummary && changeSummary.files.length > 0);

  // Get the last assistant message ID to attach activities to it
  const lastAssistantMessageId = useMemo(() => {
    const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
    return lastAssistant?.id || null;
  }, [messages]);

  // Check if we should show activities for a message (only for the last assistant message)
  const shouldShowActivitiesForMessage = (messageId: string): boolean => {
    return messageId === lastAssistantMessageId && activityEvents.length > 0;
  };

  // handleUndoChanges is defined earlier for inline change summary bar

  const handleReviewChanges = () => {
    setChangeDetailsOpen((prev) => {
      const next = !prev;
      if (next) {
        setTimeout(() => {
          diffSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 0);
      }
      return next;
    });
  };

  const handleOpenSummaryDiff = (path: string) => {
    // Try to find exact match in diffDetails
    let match = diffDetails.find((detail) => detail.path === path);

    // Try with workspace-relative path if no match
    if (!match) {
      const relativePath = toWorkspaceRelativePath(path);
      match = diffDetails.find((detail) =>
        detail.path === relativePath ||
        toWorkspaceRelativePath(detail.path) === relativePath
      );
    }

    // If still no match, just try to open the file directly
    if (match) {
      vscodeApi.postMessage({
        type: "openDiff",
        path: match.path,
        scope: match.scope,
      });
    } else {
      // Fallback: open the file directly (without diff)
      vscodeApi.postMessage({
        type: "openFile",
        filePath: path,
      });
    }
  };

  /**
   * Filter and prioritize suggestions based on actual execution results
   */
  const getContextualSuggestions = (
    originalSteps: string[],
    summary: TaskSummary | null
  ): string[] => {
    if (!summary) return originalSteps.slice(0, 4);

    const hasErrors = summary.verificationPassed === false;
    const hasFailures =
      summary.verificationDetails?.tests?.passed === false ||
      summary.verificationDetails?.typecheck?.passed === false ||
      summary.verificationDetails?.lint?.passed === false ||
      summary.verificationDetails?.build?.passed === false;
    const filesModified = (summary.filesModified || 0) + (summary.filesCreated || 0);
    const allPassed = summary.verificationPassed === true;

    // If tests/checks failed, prioritize debugging and fixing
    if (hasErrors || hasFailures) {
      const debugSuggestions: string[] = [];

      // Add specific debugging based on what failed
      if (summary.verificationDetails?.tests?.passed === false) {
        debugSuggestions.push('Debug failing tests');
      }
      if (summary.verificationDetails?.typecheck?.passed === false) {
        debugSuggestions.push('Fix type errors');
      }
      if (summary.verificationDetails?.lint?.passed === false) {
        debugSuggestions.push('Fix linting issues');
      }
      if (summary.verificationDetails?.build?.passed === false) {
        debugSuggestions.push('Fix build errors');
      }

      // Add generic debugging options
      if (debugSuggestions.length === 0) {
        debugSuggestions.push('Check error logs', 'Review recent changes');
      }

      // Filter out deployment/review suggestions from original steps
      const nonDeploySteps = originalSteps.filter(
        s => !s.toLowerCase().includes('deploy') &&
             !s.toLowerCase().includes('push') &&
             !s.toLowerCase().includes('merge')
      );

      return [...debugSuggestions, ...nonDeploySteps].slice(0, 4);
    }

    // If everything succeeded and files were modified, prioritize review/deployment
    if (allPassed && filesModified > 0) {
      const reviewSuggestions = [
        'Review all changes',
        'Run additional tests',
        'Create pull request',
      ];

      // Add original steps that aren't redundant
      const additionalSteps = originalSteps.filter(
        s => !reviewSuggestions.some(rs =>
          s.toLowerCase().includes(rs.toLowerCase().split(' ')[0])
        )
      );

      return [...reviewSuggestions, ...additionalSteps].slice(0, 4);
    }

    // Default: show original suggestions with slight filtering
    return originalSteps.slice(0, 4);
  };

  return (
    <div className="navi-chat-root navi-chat-root--no-header" data-testid="navi-interface">
      {/* Working Indicator - Floating with dynamic content */}
      {sending && (
        <div className="navi-floating-status">
          <span className="navi-working-dot" />
          <span className="navi-floating-status-text">
            {/* Show current activity or thinking if available */}
            {(() => {
              const runningActivity = activityEvents.find((evt) => evt.status === "running");
              if (runningActivity?.kind === "thinking" && runningActivity.detail) {
                // Show truncated thinking text
                const text = runningActivity.detail.slice(-80).trim();
                return text.length > 0 ? text : "NAVI is thinking...";
              }
              if (runningActivity?.label) {
                return `${runningActivity.label}${runningActivity.detail ? `: ${runningActivity.detail.slice(0, 50)}` : ''}`;
              }
              return "NAVI is working...";
            })()}
          </span>
          {/* Animated thinking bar */}
          <span className="navi-thinking-bar" />
        </div>
      )}

      {authRequired && (
        <div className="navi-auth-required">
          <div className="navi-auth-required-icon">
            <Shield className="h-4 w-4" />
          </div>
          <div className="navi-auth-required-content">
            <div className="navi-auth-required-title">Sign in required</div>
            <div className="navi-auth-required-detail">
              {authRequiredDetail || "Your session is missing a valid token. Please sign in to continue."}
            </div>
          </div>
          <div className="navi-auth-required-actions">
            <button
              type="button"
              className="navi-auth-required-btn"
              onClick={() => {
                setAuthRequired(false);
                setAuthRequiredDetail("");
                vscodeApi.postMessage({ type: "auth.signIn" });
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              className="navi-auth-required-dismiss"
              onClick={() => {
                setAuthRequired(false);
                setAuthRequiredDetail("");
                pendingAuthRetryRef.current = false;
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Enhanced History Panel - Modern Design */}
      {historyOpen && (
        <div className="navi-history-panel navi-history-panel--enhanced">
          {/* Header with title and New Chat button */}
          <div className="navi-history-header">
            <span className="navi-history-header-title">Chat History</span>
            <div className="navi-history-header-actions">
              <button
                type="button"
                className="navi-history-new-btn"
                onClick={() => {
                  handleNewChat();
                  setHistoryOpen(false);
                }}
                title="Start new chat"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New Chat</span>
              </button>
              <button
                type="button"
                className="navi-history-close navi-icon-button"
                onClick={() => setHistoryOpen(false)}
                aria-label="Close history"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Search Bar - Full Width */}
          <div className="navi-history-search-container">
            <div className="navi-history-search">
              <Search className="navi-history-search-icon h-4 w-4" />
              <input
                type="text"
                className="navi-history-search-input"
                placeholder="Search conversations..."
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
              />
              {historySearch && (
                <button
                  type="button"
                  className="navi-history-search-clear"
                  onClick={() => setHistorySearch("")}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Filter Row - All/Pinned/Starred/Archived tabs + Sort dropdown */}
          <div className="navi-history-filter-row">
            <div className="navi-history-filters">
              <button
                type="button"
                className={`navi-history-filter-btn navi-filter-all ${historyFilter === "all" ? "is-active" : ""}`}
                onClick={() => setHistoryFilter("all")}
              >
                <MessageSquare className="h-3.5 w-3.5 navi-icon-animated" />
                <span>All</span>
              </button>
              <button
                type="button"
                className={`navi-history-filter-btn navi-filter-pinned ${historyFilter === "pinned" ? "is-active" : ""}`}
                onClick={() => setHistoryFilter("pinned")}
              >
                <Pin className="h-3.5 w-3.5 navi-icon-animated navi-icon-pin" />
                <span>Pinned</span>
              </button>
              <button
                type="button"
                className={`navi-history-filter-btn navi-filter-starred ${historyFilter === "starred" ? "is-active" : ""}`}
                onClick={() => setHistoryFilter("starred")}
              >
                <Star className="h-3.5 w-3.5 navi-icon-animated navi-icon-star" />
                <span>Starred</span>
              </button>
              <button
                type="button"
                className={`navi-history-filter-btn navi-filter-archived ${historyFilter === "archived" ? "is-active" : ""}`}
                onClick={() => setHistoryFilter("archived")}
              >
                <Archive className="h-3.5 w-3.5 navi-icon-animated navi-icon-archive" />
                <span>Archived</span>
              </button>
            </div>
            <div className="navi-history-sort-container">
              <button
                type="button"
                className="navi-history-sort-btn"
                onClick={() => setHistorySortOpen(!historySortOpen)}
              >
                <span>{historySort === "recent" ? "Recent" : historySort === "oldest" ? "Oldest" : "Name"}</span>
                <ChevronDown className={`h-3.5 w-3.5 navi-sort-chevron ${historySortOpen ? "is-open" : ""}`} />
              </button>
              {historySortOpen && (
                <div className="navi-history-sort-dropdown">
                  <button
                    type="button"
                    className={`navi-sort-option ${historySort === "recent" ? "is-active" : ""}`}
                    onClick={() => { setHistorySort("recent"); setHistorySortOpen(false); }}
                  >
                    Recent
                  </button>
                  <button
                    type="button"
                    className={`navi-sort-option ${historySort === "oldest" ? "is-active" : ""}`}
                    onClick={() => { setHistorySort("oldest"); setHistorySortOpen(false); }}
                  >
                    Oldest
                  </button>
                  <button
                    type="button"
                    className={`navi-sort-option ${historySort === "name" ? "is-active" : ""}`}
                    onClick={() => { setHistorySort("name"); setHistorySortOpen(false); }}
                  >
                    Name
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Session List */}
          <div className="navi-history-list">
            {(() => {
              // Get sessions based on filter
              let sessions = historyFilter === "pinned"
                ? listPinnedSessions()
                : historyFilter === "starred"
                  ? listStarredSessions()
                  : historyFilter === "archived"
                    ? listArchivedSessions()
                    : listActiveSessions();

              // Apply search filter
              if (historySearch.trim()) {
                const query = historySearch.toLowerCase();
                sessions = sessions.filter(
                  (s) =>
                    s.title.toLowerCase().includes(query) ||
                    (s.lastMessagePreview?.toLowerCase().includes(query)) ||
                    (s.repoName?.toLowerCase().includes(query)) ||
                    (s.tags?.some(t => t.label.toLowerCase().includes(query)))
                );
              }

              // Apply sorting
              if (historySort === "oldest") {
                sessions = [...sessions].sort((a, b) =>
                  new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime()
                );
              } else if (historySort === "name") {
                sessions = [...sessions].sort((a, b) =>
                  a.title.localeCompare(b.title)
                );
              }
              // "recent" is default (already sorted by updatedAt desc)

              if (sessions.length === 0) {
                return (
                  <div className="navi-history-empty">
                    <MessageSquare className="h-10 w-10 navi-history-empty-icon" />
                    <span>
                      {historySearch
                        ? "No matching conversations"
                        : historyFilter === "pinned"
                          ? "No pinned conversations"
                          : historyFilter === "starred"
                            ? "No starred conversations"
                            : historyFilter === "archived"
                              ? "No archived conversations"
                              : "No conversations yet"}
                    </span>
                  </div>
                );
              }

              return sessions.map((session) => (
                <div
                  key={session.id}
                  className={`navi-history-item${session.id === activeSessionId ? " is-active" : ""}${session.isPinned ? " is-pinned" : ""}`}
                  onClick={() => {
                    persistActiveSessionId(session.id);
                    setActiveSessionId(session.id);
                    resetConversationState();
                    setHistoryOpen(false);
                    setTimeout(() => inputRef.current?.focus(), 10);
                  }}
                >
                  {/* Pin indicator */}
                  {session.isPinned && (
                    <div className="navi-history-pin-indicator">
                      <Pin className="h-3 w-3" />
                    </div>
                  )}

                  {/* Main content */}
                  <div className="navi-history-item-content">
                    {/* Title row with timestamp */}
                    <div className="navi-history-item-title-row">
                      <span className="navi-history-title">{session.title}</span>
                      <span className="navi-history-timestamp">{formatRelativeTime(session.updatedAt)}</span>
                    </div>

                    {/* Preview text */}
                    {session.lastMessagePreview && (
                      <div className="navi-history-preview">{session.lastMessagePreview}</div>
                    )}

                    {/* Meta row: message count, repo name, tags */}
                    <div className="navi-history-meta-row">
                      <div className="navi-history-meta-left">
                        <span className="navi-history-meta-item">
                          <MessageSquare className="h-3 w-3" />
                          {session.messageCount}
                        </span>
                        <span className="navi-history-meta-item">
                          <Folder className="h-3 w-3" />
                          {session.repoName || "this repo"}
                        </span>
                      </div>
                      {/* Tags */}
                      {session.tags && session.tags.length > 0 && (
                        <div className="navi-history-tags">
                          {session.tags.map((tag, idx) => (
                            <span
                              key={idx}
                              className={`navi-history-tag navi-tag-${tag.color || "blue"}`}
                            >
                              {tag.label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Action buttons - show on hover with animated icons */}
                  <div className="navi-history-item-actions">
                    <button
                      type="button"
                      className={`navi-history-action-btn navi-action-pin ${session.isPinned ? "is-active" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSessionPin(session.id);
                        setHistoryRefreshTrigger((n) => n + 1);
                      }}
                      title={session.isPinned ? "Unpin" : "Pin"}
                    >
                      <Pin className="h-3.5 w-3.5 navi-icon-animated navi-icon-pin" />
                    </button>
                    <button
                      type="button"
                      className={`navi-history-action-btn navi-action-star ${session.isStarred ? "is-active" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSessionStar(session.id);
                        setHistoryRefreshTrigger((n) => n + 1);
                      }}
                      title={session.isStarred ? "Unstar" : "Star"}
                    >
                      <Star className="h-3.5 w-3.5 navi-icon-animated navi-icon-star" />
                    </button>
                    <button
                      type="button"
                      className={`navi-history-action-btn navi-action-archive ${session.isArchived ? "is-active" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSessionArchive(session.id);
                        setHistoryRefreshTrigger((n) => n + 1);
                      }}
                      title={session.isArchived ? "Unarchive" : "Archive"}
                    >
                      <Archive className="h-3.5 w-3.5 navi-icon-animated navi-icon-archive" />
                    </button>
                    {deleteConfirmId === session.id ? (
                      <div className="navi-delete-confirm">
                        <button
                          type="button"
                          className="navi-delete-confirm-btn navi-delete-confirm-yes"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteSession(session.id);
                            setDeleteConfirmId(null);
                            setHistoryRefreshTrigger((n) => n + 1);
                          }}
                          title="Confirm delete"
                        >
                          <Check className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          className="navi-delete-confirm-btn navi-delete-confirm-no"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirmId(null);
                          }}
                          title="Cancel"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="navi-history-action-btn navi-action-delete navi-history-action-btn--danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteConfirmId(session.id);
                        }}
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5 navi-icon-animated navi-icon-trash" />
                      </button>
                    )}
                  </div>
                </div>
              ));
            })()}
          </div>

          {/* Footer */}
          <div className="navi-history-footer">
            <span className="navi-history-count">
              {(() => {
                const count = historyFilter === "pinned"
                  ? listPinnedSessions().length
                  : historyFilter === "starred"
                    ? listStarredSessions().length
                    : historyFilter === "archived"
                      ? listArchivedSessions().length
                      : listActiveSessions().length;
                return `${count} conversation${count === 1 ? "" : "s"}`;
              })()}
            </span>
          </div>
        </div>
      )}

      {/* Settings Panel */}
      {settingsOpen && (
        <div className="navi-settings-panel">
          <div className="navi-settings-header">
            <span>Settings</span>
            <button
              type="button"
              className="navi-settings-close navi-icon-button"
              onClick={() => setSettingsOpen(false)}
              aria-label="Close settings"
            >
              <X className="h-4 w-4 navi-icon-3d" />
            </button>
          </div>

          {/* Settings Tabs */}
          <div className="navi-settings-tabs">
            <button
              type="button"
              className={`navi-settings-tab ${settingsTab === "behavior" ? "is-active" : ""}`}
              onClick={() => setSettingsTab("behavior")}
            >
              <Brain className="h-4 w-4" />
              <span>AI Behavior</span>
            </button>
            <button
              type="button"
              className={`navi-settings-tab ${settingsTab === "appearance" ? "is-active" : ""}`}
              onClick={() => setSettingsTab("appearance")}
            >
              <Palette className="h-4 w-4" />
              <span>Appearance</span>
            </button>
            <button
              type="button"
              className={`navi-settings-tab ${settingsTab === "notifications" ? "is-active" : ""}`}
              onClick={() => setSettingsTab("notifications")}
            >
              <Bell className="h-4 w-4" />
              <span>Notifications</span>
            </button>
          </div>

          {/* Settings Content */}
          <div className="navi-settings-content">
            {/* AI Behavior Tab */}
            {settingsTab === "behavior" && (
              <div className="navi-settings-section">
                <div className="navi-settings-group">
                  <h4 className="navi-settings-group-title">
                    <Shield className="h-4 w-4" />
                    Safety & Approvals
                  </h4>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Require approval for destructive operations</span>
                      <span className="navi-settings-item-desc">Git force push, file deletions, database changes</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${aiSettings.requireApprovalDestructive ? "is-on" : ""}`}
                      onClick={() => setAiSettings(prev => ({ ...prev, requireApprovalDestructive: !prev.requireApprovalDestructive }))}
                    >
                      {aiSettings.requireApprovalDestructive ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Auto-execute safe operations</span>
                      <span className="navi-settings-item-desc">Skip confirmation for read-only commands</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${aiSettings.autoExecuteSafe ? "is-on" : ""}`}
                      onClick={() => setAiSettings(prev => ({ ...prev, autoExecuteSafe: !prev.autoExecuteSafe }))}
                    >
                      {aiSettings.autoExecuteSafe ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                </div>

                <div className="navi-settings-group">
                  <h4 className="navi-settings-group-title">
                    <Sparkles className="h-4 w-4" />
                    Response Style
                  </h4>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Explain changes before executing</span>
                      <span className="navi-settings-item-desc">Show detailed explanation of what will change</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${aiSettings.explainBeforeExecute ? "is-on" : ""}`}
                      onClick={() => setAiSettings(prev => ({ ...prev, explainBeforeExecute: !prev.explainBeforeExecute }))}
                    >
                      {aiSettings.explainBeforeExecute ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Prefer local codebase patterns</span>
                      <span className="navi-settings-item-desc">Match existing code style in your repository</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${aiSettings.preferLocalPatterns ? "is-on" : ""}`}
                      onClick={() => setAiSettings(prev => ({ ...prev, preferLocalPatterns: !prev.preferLocalPatterns }))}
                    >
                      {aiSettings.preferLocalPatterns ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Verbose explanations</span>
                      <span className="navi-settings-item-desc">More detailed responses with reasoning</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${aiSettings.verboseExplanations ? "is-on" : ""}`}
                      onClick={() => setAiSettings(prev => ({ ...prev, verboseExplanations: !prev.verboseExplanations }))}
                    >
                      {aiSettings.verboseExplanations ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Stream responses</span>
                      <span className="navi-settings-item-desc">Show responses as they are generated</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${aiSettings.streamResponses ? "is-on" : ""}`}
                      onClick={() => setAiSettings(prev => ({ ...prev, streamResponses: !prev.streamResponses }))}
                    >
                      {aiSettings.streamResponses ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                </div>
                <div className="navi-settings-group">
                  <h4 className="navi-settings-group-title">
                    <Activity className="h-4 w-4" />
                    Activity Panel
                  </h4>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Show commands</span>
                      <span className="navi-settings-item-desc">Display commands in the Activity panel</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${activityPanelPreferences.showCommands ? "is-on" : ""}`}
                      onClick={() => setActivityPanelPreferences({ showCommands: !activityPanelPreferences.showCommands })}
                    >
                      {activityPanelPreferences.showCommands ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Show command output</span>
                      <span className="navi-settings-item-desc">Include stdout/stderr preview in Activity panel</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${activityPanelPreferences.showCommandOutput ? "is-on" : ""}`}
                      onClick={() => setActivityPanelPreferences({ showCommandOutput: !activityPanelPreferences.showCommandOutput })}
                      disabled={!activityPanelPreferences.showCommands}
                    >
                      {activityPanelPreferences.showCommandOutput ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Show file changes</span>
                      <span className="navi-settings-item-desc">Display file changes in the Activity panel</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${activityPanelPreferences.showFileChanges ? "is-on" : ""}`}
                      onClick={() => setActivityPanelPreferences({ showFileChanges: !activityPanelPreferences.showFileChanges })}
                    >
                      {activityPanelPreferences.showFileChanges ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Appearance Tab */}
            {settingsTab === "appearance" && (
              <div className="navi-settings-section">
                <div className="navi-settings-group">
                  <h4 className="navi-settings-group-title">
                    <Palette className="h-4 w-4" />
                    Display
                  </h4>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Compact mode</span>
                      <span className="navi-settings-item-desc">Reduce spacing for more content</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${appearanceSettings.compactMode ? "is-on" : ""}`}
                      onClick={() => setAppearanceSettings(prev => ({ ...prev, compactMode: !prev.compactMode }))}
                    >
                      {appearanceSettings.compactMode ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Show timestamps</span>
                      <span className="navi-settings-item-desc">Display time on messages</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${appearanceSettings.showTimestamps ? "is-on" : ""}`}
                      onClick={() => setAppearanceSettings(prev => ({ ...prev, showTimestamps: !prev.showTimestamps }))}
                    >
                      {appearanceSettings.showTimestamps ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Syntax highlighting</span>
                      <span className="navi-settings-item-desc">Colorize code blocks</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${appearanceSettings.syntaxHighlighting ? "is-on" : ""}`}
                      onClick={() => setAppearanceSettings(prev => ({ ...prev, syntaxHighlighting: !prev.syntaxHighlighting }))}
                    >
                      {appearanceSettings.syntaxHighlighting ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Animations</span>
                      <span className="navi-settings-item-desc">Enable smooth transitions and effects</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${appearanceSettings.animationsEnabled ? "is-on" : ""}`}
                      onClick={() => setAppearanceSettings(prev => ({ ...prev, animationsEnabled: !prev.animationsEnabled }))}
                    >
                      {appearanceSettings.animationsEnabled ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Notifications Tab */}
            {settingsTab === "notifications" && (
              <div className="navi-settings-section">
                <div className="navi-settings-group">
                  <h4 className="navi-settings-group-title">
                    <Bell className="h-4 w-4" />
                    Alerts
                  </h4>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Sound notifications</span>
                      <span className="navi-settings-item-desc">Play sound when task completes</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${notificationSettings.soundEnabled ? "is-on" : ""}`}
                      onClick={() => setNotificationSettings(prev => ({ ...prev, soundEnabled: !prev.soundEnabled }))}
                    >
                      {notificationSettings.soundEnabled ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Desktop notifications</span>
                      <span className="navi-settings-item-desc">Show system notifications</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${notificationSettings.desktopNotifications ? "is-on" : ""}`}
                      onClick={() => setNotificationSettings(prev => ({ ...prev, desktopNotifications: !prev.desktopNotifications }))}
                    >
                      {notificationSettings.desktopNotifications ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                  <div className="navi-settings-item">
                    <div className="navi-settings-item-info">
                      <span className="navi-settings-item-label">Error alerts</span>
                      <span className="navi-settings-item-desc">Show alerts for errors and failures</span>
                    </div>
                    <button
                      type="button"
                      className={`navi-settings-toggle ${notificationSettings.showErrorAlerts ? "is-on" : ""}`}
                      onClick={() => setNotificationSettings(prev => ({ ...prev, showErrorAlerts: !prev.showErrorAlerts }))}
                    >
                      {notificationSettings.showErrorAlerts ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Settings Footer */}
          <div className="navi-settings-footer">
            <button
              type="button"
              className="navi-settings-reset-btn"
              onClick={() => {
                setAiSettings({
                  requireApprovalDestructive: true,
                  autoExecuteSafe: false,
                  explainBeforeExecute: true,
                  preferLocalPatterns: true,
                  verboseExplanations: false,
                  streamResponses: true,
                });
                setAppearanceSettings({
                  compactMode: false,
                  showTimestamps: true,
                  syntaxHighlighting: true,
                  animationsEnabled: true,
                });
                setNotificationSettings({
                  soundEnabled: false,
                  desktopNotifications: true,
                  showErrorAlerts: true,
                });
                showToast("Settings reset to defaults", "info");
              }}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset to Defaults
            </button>
          </div>
        </div>
      )}

      {coverageGate?.status === "fail" && (
        <div className="navi-coverage-gate navi-coverage-gate--fail">
          <div className="navi-coverage-gate-text">
            Coverage gate failed{" "}
            {typeof coverageGate.coverage === "number"
              ? `(${coverageGate.coverage.toFixed(1)}% vs ${coverageGate.threshold ?? "?"}%)`
              : "(unparsed output)"}.
            Resolve coverage or override to continue.
          </div>
          <div className="navi-coverage-gate-actions">
            <button
              type="button"
              className="navi-pill navi-pill--ghost"
              onClick={clearCoverageGate}
            >
              Override gate
            </button>
          </div>
        </div>
      )}

      <div className="navi-chat-body" ref={scrollerRef} data-testid="chat-messages">

        {messages.length === 0 && (
          <div className="navi-chat-empty">
            <div>Ask Navi anything about your repo, JIRA, or builds.</div>
            <div className="navi-chat-empty-example">
              Example: <code>check errors and fix them</code>
            </div>
          </div>
        )}

        {/* Pending consent requests - shown prominently at top */}
        {pendingConsents.size > 0 && (
          <div className="navi-pending-consents">
            {Array.from(pendingConsents.entries()).map(([consentId, consent]) => (
              <InlineCommandApproval
                key={consentId}
                command={consent.command}
                shell={consent.shell}
                status="pending"
                onAllow={() => handleConsentAllow(consentId)}
                onSkip={() => handleConsentSkip(consentId)}
              />
            ))}
          </div>
        )}

        {/* Messages with activities embedded inside assistant bubbles */}
        {messages.map((m, idx) => {
          const actionSource = Array.isArray(m.actions) ? m.actions : [];
          const showActivities = shouldShowActivitiesForMessage(m.id);

          // For streaming messages with no content yet, still render if we have activities
          // This prevents the "double bubble" issue where activities show in a separate bubble
          const hasActivitiesToShow = activityEvents.length > 0;
          if (m.isStreaming && (!m.content || m.content.trim() === "") && !hasActivitiesToShow) {
            return null;
          }

          // Check if this is a continuation of previous assistant message
          const prevMessage = idx > 0 ? messages[idx - 1] : null;
          const isContinuation = m.role === "assistant" && prevMessage?.role === "assistant";

          return (
            <div
              key={m.id}
              className={`navi-chat-bubble-row navi-chat-bubble-row--${m.role} ${isContinuation ? 'navi-chat-bubble-row--continuation' : ''}`}
            >
              <div className={`navi-chat-avatar navi-chat-avatar--${m.role}`}>
                {m.role === "user" && <User className="h-4 w-4 navi-icon-3d" />}
                {m.role === "assistant" && <Zap className="h-4 w-4 navi-icon-3d" />}
                {m.role === "system" && <AlertTriangle className="h-4 w-4 navi-icon-3d" />}
              </div>
              <div
                className={`navi-chat-bubble navi-chat-bubble--${m.role}`}
                data-testid={m.role === "assistant" ? "ai-response" : undefined}
              >
                {/* THINKING INDICATOR: Moved to bottom of chat for better UX */}
                {/* See "Bottom Thinking Indicator" section after messages map */}
                {/* After completion: Show thinking block only if there's stored thinking */}
                {m.role === "assistant" && !m.isStreaming && m.storedThinking && (
                  <div className="navi-thinking-block navi-thinking-block--complete">
                    <div
                      className="navi-thinking-header"
                      onClick={() => setThinkingExpanded(prev => !prev)}
                    >
                      <ChevronRight
                        size={14}
                        className={`navi-thinking-chevron ${thinkingExpanded ? 'expanded' : ''}`}
                      />
                      <span className="navi-thinking-label">Thinking</span>
                      <CheckCircle2 size={12} className="navi-thinking-complete-icon" />
                    </div>
                    {thinkingExpanded && (
                      <div className="navi-thinking-content">
                        {m.storedThinking}
                      </div>
                    )}
                  </div>
                )}

                {/* ASSISTANT MESSAGE: Show response text first, then activities inline */}
                {m.role === "assistant" && (
                  <div className="navi-response-stream">
                    {/* ExecutionPlanStepper moved to above input bar for better visibility */}
                    {(() => {
                      // Get activities and narratives (live during streaming, stored after)
                      // Use live state if streaming OR if we're the last message and activities exist in state
                      // This prevents activities from disappearing briefly during the transition
                      const isLastMessage = messages[messages.length - 1]?.id === m.id;
                      const hasLiveActivities = activityEvents.length > 0;
                      const shouldUseLiveActivities = m.isStreaming || (isLastMessage && hasLiveActivities && !m.storedActivities?.length);
                      const activitiesToUse = shouldUseLiveActivities ? activityEvents : (m.storedActivities || []);
                      const shouldUseLiveNarratives = m.isStreaming || (isLastMessage && narrativeLines.length > 0 && !m.storedNarratives?.length);
                      const narrativesToUse = shouldUseLiveNarratives ? narrativeLines : (m.storedNarratives || []);

                      // Only show actual tool activities - filter out meta/thinking activities
                      // Keep: read, edit, create, command (real file/command operations)
                      // Filter out: info, thinking, analysis, etc. (meta activities)
                      // Also deduplicate: if same command has both running and done, only show done
                      const toolActivities = activitiesToUse.filter(
                        (evt) => evt.kind === 'read' || evt.kind === 'edit' || evt.kind === 'create' || evt.kind === 'command'
                      );

                      // Deduplicate command activities - prefer done/error over running
                      const seenCommands = new Map<string, ActivityEvent>();
                      for (const evt of toolActivities) {
                        if (evt.kind === 'command') {
                          const key = evt.detail || evt.id;
                          const existing = seenCommands.get(key);
                          // Keep if: no existing, or existing is running and this is done/error
                          if (!existing || (existing.status === 'running' && evt.status !== 'running')) {
                            seenCommands.set(key, evt);
                          }
                        }
                      }

                      const filteredActivities = toolActivities.filter((evt) => {
                        if (evt.kind === 'command') {
                          const key = evt.detail || evt.id;
                          return seenCommands.get(key) === evt;
                        }
                        return true;
                      });

                      // Filter out redundant narratives that duplicate activity information
                      // Patterns like "Reading `file.py`..." or "Read `file.py`." are redundant when we show Read activities
                      const activityFilePaths = new Set(
                        filteredActivities
                          .filter(a => a.kind === 'read' || a.kind === 'edit' || a.kind === 'create')
                          .map(a => a.detail?.toLowerCase() || '')
                          .filter(Boolean)
                      );

                      const isRedundantNarrative = (text: string): boolean => {
                        const lower = text.toLowerCase();
                        // Skip narratives that are just about reading/editing files when we already show activities
                        const fileReadPatterns = [
                          /^reading\s+`?[^`]+`?\.{0,3}$/i,  // "Reading `file.py`..." or "Reading file.py"
                          /^read\s+`?[^`]+`?\.?$/i,         // "Read `file.py`." or "Read file.py"
                          /^i've\s+(read|analyzed)\s+`?[^`]+`?\.?$/i,  // "I've read `file.py`."
                          /^editing\s+`?[^`]+`?\.{0,3}$/i,  // "Editing `file.py`..."
                          /^edited\s+`?[^`]+`?\.?$/i,       // "Edited `file.py`."
                        ];
                        // Check if this matches a file read/edit pattern and the file is already in activities
                        for (const pattern of fileReadPatterns) {
                          if (pattern.test(text.trim())) {
                            // Extract file name from the narrative
                            const match = text.match(/`([^`]+)`/);
                            if (match) {
                              const fileName = match[1].toLowerCase();
                              // If we have an activity for this file, the narrative is redundant
                              for (const path of activityFilePaths) {
                                if (path.endsWith(fileName) || path.includes(fileName)) {
                                  return true;
                                }
                              }
                            }
                            // Even without a match, single file read narratives are often redundant
                            return activityFilePaths.size > 0;
                          }
                        }
                        return false;
                      };

                      const filteredNarratives = narrativesToUse.filter(n => !isRedundantNarrative(n.text));

                      // Check if we have any tool activities to show
                      const hasActivities = filteredActivities.length > 0 || filteredNarratives.length > 0;

                      // Build unified stream sorted by timestamp
                      type StreamItem =
                        | { itemType: 'narrative'; id: string; text: string; timestamp: string }
                        | { itemType: 'activity'; data: ActivityEvent };

                      const allItems: StreamItem[] = [
                        ...filteredNarratives.map(n => ({
                          itemType: 'narrative' as const,
                          id: n.id,
                          text: n.text,
                          timestamp: n.timestamp
                        })),
                        ...filteredActivities.map(a => ({
                          itemType: 'activity' as const,
                          data: a
                        })),
                      ];

                      // Sort by timestamp for chronological ordering
                      allItems.sort((a, b) => {
                        const timeA = a.itemType === 'narrative' ? a.timestamp : a.data.timestamp;
                        const timeB = b.itemType === 'narrative' ? b.timestamp : b.data.timestamp;
                        return new Date(timeA).getTime() - new Date(timeB).getTime();
                      });

                      // Combine consecutive narrative items to prevent broken markdown patterns
                      // (e.g., [text](url) split across chunks)
                      type MergedItem =
                        | { itemType: 'narrative'; id: string; text: string; timestamp: string }
                        | { itemType: 'activity'; data: ActivityEvent };

                      const mergedItems: MergedItem[] = [];
                      for (const item of allItems) {
                        if (item.itemType === 'narrative') {
                          const lastItem = mergedItems[mergedItems.length - 1];
                          if (lastItem && lastItem.itemType === 'narrative') {
                            // Combine with previous narrative - no space if last ends with opening bracket/paren
                            const lastChar = lastItem.text.slice(-1);
                            const separator = ['[', '(', '\n'].includes(lastChar) ? '' : ' ';
                            lastItem.text += separator + item.text;
                          } else {
                            mergedItems.push({ ...item });
                          }
                        } else {
                          mergedItems.push(item);
                        }
                      }

                      // Render activity item helper
                      const renderActivityItem = (evt: ActivityEvent) => {
                        const getLabel = () => {
                          switch (evt.kind) {
                            case 'read': return 'Read';
                            case 'edit': return 'Edit';
                            case 'create': return 'Write';
                            case 'command': return 'Bash';
                            default: return evt.label || evt.kind;
                          }
                        };
                        const isCommand = evt.kind === 'command';
                        const isFile = evt.kind === 'read' || evt.kind === 'edit' || evt.kind === 'create';
                        const hasStats = evt.status === 'done' && (evt.additions !== undefined || evt.deletions !== undefined);

                        // Handle file click - open in VS Code editor
                        const handleFileClick = (filePath: string) => {
                          vscodeApi.postMessage({ type: 'openFile', filePath });
                        };

                        return (
                          <div key={evt.id} className={`navi-claude-activity navi-claude-activity--${evt.status}`}>
                            <div className="navi-claude-activity-row">
                              <span className={`navi-claude-dot navi-claude-dot--${evt.status}`} />
                              <span className="navi-claude-activity-label">{getLabel()}</span>
                              {evt.detail && !isCommand && (
                                <span
                                  className={`navi-claude-activity-desc ${isFile ? 'navi-claude-activity-desc--file navi-clickable-file' : ''}`}
                                  onClick={isFile ? () => handleFileClick(evt.detail!) : undefined}
                                  title={isFile ? `Click to open ${evt.detail}` : undefined}
                                >
                                  {evt.detail}
                                </span>
                              )}
                              {hasStats && (
                                <span className="navi-claude-activity-stats">
                                  {evt.additions !== undefined && evt.additions > 0 && (
                                    <span className="navi-activity-change-add">+{evt.additions}</span>
                                  )}
                                  {evt.deletions !== undefined && evt.deletions > 0 && (
                                    <span className="navi-activity-change-del">-{evt.deletions}</span>
                                  )}
                                </span>
                              )}
                            </div>
                            {isCommand && evt.detail && (() => {
                              // Look up output from terminalEntries as fallback
                              const terminalEntry = [...terminalEntries].reverse().find(
                                (te) => te.command === evt.detail
                              );
                              const commandOutput = evt.output || terminalEntry?.output || '';
                              const commandExitCode = evt.exitCode ?? terminalEntry?.exitCode;
                              const commandStatus = evt.status || terminalEntry?.status || 'done';

                              return (
                                <NaviInlineCommand
                                  commandId={terminalEntry?.id}
                                  command={evt.detail}
                                  output={commandOutput}
                                  status={commandStatus}
                                  showOutput={false}
                                  purpose={evt.purpose}
                                  explanation={evt.explanation}
                                  nextAction={evt.nextAction}
                                  exitCode={commandExitCode}
                                  onOpenActivity={onOpenActivityForCommand}
                                  highlighted={terminalEntry?.id === inlineCommandHighlightId}
                                />
                              );
                            })()}
                          </div>
                        );
                      };

                      // Render narrative text block helper with markdown formatting
                      // Handles: **bold**, `code`, URLs, markdown links, lists, line breaks, fenced code blocks
                      const renderNarrativeItem = (text: string, id: string) => {
                        // First, check for fenced code blocks (```...```)
                        const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g;
                        const hasCodeBlocks = codeBlockRegex.test(text);

                        if (hasCodeBlocks) {
                          // Need formatMarkdown defined early for code block text parts
                          const formatMd = (input: string): string => {
                            let result = input;
                            result = result.replace(/^###\s+(.+)$/gm, '<h3 class="navi-heading-3">$1</h3>');
                            result = result.replace(/^##\s+(.+)$/gm, '<h2 class="navi-heading-2">$1</h2>');
                            result = result.replace(/^#\s+(.+)$/gm, '<h1 class="navi-heading-1">$1</h1>');
                            result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
                            result = result.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
                            result = result.replace(/`([^`]+)`/g, '<code class="navi-inline-code">$1</code>');
                            return result;
                          };

                          // Split text into parts (text and code blocks)
                          const parts: React.ReactNode[] = [];
                          let lastIndex = 0;
                          let partIdx = 0;
                          const regex = /```(\w*)\n?([\s\S]*?)```/g;
                          let match;

                          while ((match = regex.exec(text)) !== null) {
                            // Add text before code block (with markdown formatting)
                            if (match.index > lastIndex) {
                              const beforeText = text.slice(lastIndex, match.index).trim();
                              if (beforeText) {
                                parts.push(
                                  <div
                                    key={`${id}-text-${partIdx++}`}
                                    className="navi-narrative-para"
                                    dangerouslySetInnerHTML={{ __html: formatMd(beforeText) }}
                                  />
                                );
                              }
                            }

                            // Add code block
                            const language = match[1] || 'plaintext';
                            const code = match[2].trim();
                            parts.push(
                              <pre key={`${id}-code-${partIdx++}`} className={`navi-code-block language-${language}`}>
                                <code>{code}</code>
                              </pre>
                            );

                            lastIndex = match.index + match[0].length;
                          }

                          // Add remaining text after last code block (with markdown formatting)
                          if (lastIndex < text.length) {
                            const afterText = text.slice(lastIndex).trim();
                            if (afterText) {
                              parts.push(
                                <div
                                  key={`${id}-text-${partIdx++}`}
                                  className="navi-narrative-para"
                                  dangerouslySetInnerHTML={{ __html: formatMd(afterText) }}
                                />
                              );
                            }
                          }

                          return (
                            <div key={id} className="navi-narrative-block">
                              {parts}
                            </div>
                          );
                        }

                        // Format text with markdown-like syntax (for non-code-block content)
                        const formatMarkdown = (input: string): string => {
                          let result = input;
                          // Handle markdown headers (### Header)
                          result = result.replace(/^###\s+(.+)$/gm, '<h3 class="navi-heading-3">$1</h3>');
                          result = result.replace(/^##\s+(.+)$/gm, '<h2 class="navi-heading-2">$1</h2>');
                          result = result.replace(/^#\s+(.+)$/gm, '<h1 class="navi-heading-1">$1</h1>');
                          // Handle bold text **text**
                          result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
                          // Handle italic text *text* (but not **)
                          result = result.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
                          // Handle inline code `code`
                          result = result.replace(/`([^`]+)`/g, '<code class="navi-inline-code">$1</code>');
                          // Handle markdown links [text](url) - process these FIRST
                          // Also handle URLs with accidental spaces (LLM tokenization artifact)
                          result = result.replace(
                            /\[([^\]]+)\]\((https?:\/\/\s*[^)]+)\)/g,
                            (_match, linkText, url) => {
                              // Clean up URL: remove spaces that might have been introduced by LLM tokenization
                              const cleanUrl = url.replace(/\s+/g, '');
                              // If text is same as URL (with or without spaces), show URL once
                              const cleanText = linkText.replace(/\s+/g, '');
                              const displayText = cleanText === cleanUrl ? cleanUrl : linkText;
                              return `<a href="${cleanUrl}" class="navi-inline-link" target="_blank" rel="noopener noreferrer">${displayText}</a>`;
                            }
                          );
                          // Handle plain URLs (skip if preceded by [ or ]( which indicates markdown link syntax)
                          result = result.replace(
                            /(^|[^"'\[])(?<!\]\()(https?:\/\/[^\s<>)\]]+)/g,
                            '$1<a href="$2" class="navi-inline-link" target="_blank" rel="noopener noreferrer">$2</a>'
                          );
                          return result;
                        };

                        // Check if text has markdown structure (lists, multiple paragraphs)
                        const hasStructure = text.includes('\n') && (
                          text.includes('- ') ||
                          text.includes('* ') ||
                          /\d+\.\s/.test(text) ||
                          text.includes('\n\n')
                        );

                        if (hasStructure) {
                          // Render with proper structure
                          const lines = text.split('\n');
                          const elements: React.ReactNode[] = [];
                          let currentList: React.ReactNode[] = [];
                          let listType: 'ul' | 'ol' | null = null;

                          // Helper to check if a line is a list item
                          const isListItem = (line: string): boolean => {
                            const t = line.trim();
                            return t.startsWith('- ') || t.startsWith('* ') || /^\d+[\.\)]\s/.test(t);
                          };

                          // Helper to find next non-empty line
                          const findNextNonEmpty = (fromIdx: number): string | null => {
                            for (let i = fromIdx + 1; i < lines.length; i++) {
                              if (lines[i].trim()) return lines[i];
                            }
                            return null;
                          };

                          lines.forEach((line, idx) => {
                            const trimmed = line.trim();
                            if (!trimmed) {
                              // Empty line - only flush list if next non-empty line is NOT a list item
                              const nextLine = findNextNonEmpty(idx);
                              if (currentList.length > 0 && (!nextLine || !isListItem(nextLine))) {
                                const ListTag = listType === 'ol' ? 'ol' : 'ul';
                                elements.push(<ListTag key={`${id}-list-${idx}`} className="navi-narrative-list">{currentList}</ListTag>);
                                currentList = [];
                                listType = null;
                              }
                              return;
                            }

                            // Check for bullet points
                            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                              if (listType !== 'ul' && currentList.length > 0) {
                                const ListTag = listType === 'ol' ? 'ol' : 'ul';
                                elements.push(<ListTag key={`${id}-list-${idx}`} className="navi-narrative-list">{currentList}</ListTag>);
                                currentList = [];
                              }
                              listType = 'ul';
                              const content = trimmed.slice(2);
                              currentList.push(
                                <li key={`${id}-li-${idx}`} dangerouslySetInnerHTML={{ __html: formatMarkdown(content) }} />
                              );
                              return;
                            }

                            // Check for numbered lists
                            const numberedMatch = trimmed.match(/^(\d+)[\.\)]\s*(.+)/);
                            if (numberedMatch) {
                              if (listType !== 'ol' && currentList.length > 0) {
                                const ListTag = listType === 'ol' ? 'ol' : 'ul';
                                elements.push(<ListTag key={`${id}-list-${idx}`} className="navi-narrative-list">{currentList}</ListTag>);
                                currentList = [];
                              }
                              listType = 'ol';
                              currentList.push(
                                <li key={`${id}-li-${idx}`} dangerouslySetInnerHTML={{ __html: formatMarkdown(numberedMatch[2]) }} />
                              );
                              return;
                            }

                            // Regular text - flush list if any, then add paragraph
                            if (currentList.length > 0) {
                              const ListTag = listType === 'ol' ? 'ol' : 'ul';
                              elements.push(<ListTag key={`${id}-list-${idx}`} className="navi-narrative-list">{currentList}</ListTag>);
                              currentList = [];
                              listType = null;
                            }
                            elements.push(
                              <p key={`${id}-p-${idx}`} className="navi-narrative-para" dangerouslySetInnerHTML={{ __html: formatMarkdown(trimmed) }} />
                            );
                          });

                          // Flush remaining list
                          if (currentList.length > 0) {
                            const ListTag = listType === 'ol' ? 'ol' : 'ul';
                            elements.push(<ListTag key={`${id}-list-final`} className="navi-narrative-list">{currentList}</ListTag>);
                          }

                          return (
                            <div key={id} className="navi-narrative-block">
                              {elements}
                            </div>
                          );
                        }

                        // Simple text without structure - render inline
                        return (
                          <span
                            key={id}
                            className="navi-narrative-chunk"
                            dangerouslySetInnerHTML={{ __html: formatMarkdown(text) }}
                          />
                        );
                      };

                      return (
                        <div data-testid="ai-response-text" className="navi-interleaved-stream">
                          {/* Render items in chronological order - interleave text and activities */}
                          {/* Using mergedItems to combine consecutive narratives for proper markdown parsing */}
                          {mergedItems.map((item, idx) => {
                            if (item.itemType === 'narrative') {
                              return renderNarrativeItem(item.text, item.id);
                            } else {
                              return renderActivityItem(item.data);
                            }
                          })}
                          {/* If no narratives but we have message content, render it */}
                          {narrativesToUse.length === 0 && m.content && (
                            <div className="navi-narrative-chunk">
                              {renderMessageContent(m)}
                            </div>
                          )}
                          {/* Bottom processing indicator - shows when streaming and content exists */}
                          {/* This tells user NAVI is still working after activities have appeared */}
                          {m.isStreaming && (filteredActivities.length > 0 || narrativesToUse.length > 0) && (
                            <div className="navi-processing-indicator">
                              <span className="navi-thinking-label">
                                {"Thinking...".split("").map((char, i) => (
                                  <span key={i} className="navi-thinking-label-char">{char}</span>
                                ))}
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* Non-assistant messages render directly */}
                {m.role !== "assistant" && (
                  <div data-testid="user-message-text">
                    {/* Show attachments (images, files) for user messages */}
                    {m.attachments && m.attachments.length > 0 && (
                      <div className="navi-message-attachments" style={{ marginBottom: 8 }}>
                        {m.attachments.map((att, idx) => (
                          <div key={att.id || idx} className="navi-message-attachment-item">
                            {att.kind === 'image' && att.content ? (
                              <img
                                src={att.content}
                                alt={att.label || 'Attached image'}
                                className="navi-message-attachment-image"
                                style={{
                                  maxWidth: '120px',
                                  maxHeight: '90px',
                                  borderRadius: 6,
                                  marginBottom: 4,
                                  border: '1px solid rgba(255,255,255,0.15)',
                                  cursor: 'pointer',
                                  objectFit: 'cover'
                                }}
                                title="Click to view full size"
                              />
                            ) : (
                              <div className="navi-message-attachment-file" style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                padding: '4px 8px',
                                background: 'rgba(255,255,255,0.05)',
                                borderRadius: 4,
                                fontSize: 12,
                                marginBottom: 4
                              }}>
                                <Paperclip className="h-3 w-3" />
                                <span>{att.label || att.path || 'Attachment'}</span>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {renderMessageContent(m)}
                  </div>
                )}

                {/* NAVI V2: Show approval panel if requires approval */}
                {m.role === "assistant" && m.requiresApproval && m.actionsWithRisk && m.planId && (
                  <NaviApprovalPanel
                    planId={m.planId}
                    message={messages.filter(msg => msg.role === "user").slice(-1)[0]?.content || ""}
                    actionsWithRisk={m.actionsWithRisk}
                    onApprove={(approvedIndices) => handleApproveActions(m.planId!, approvedIndices)}
                    onReject={() => handleRejectPlan(m.planId!)}
                    onShowDiff={(actionIndex) => handleShowDiff(m.planId!, actionIndex)}
                  />
                )}

                {/* ACTION RUNNER: Command approvals with inline activities */}
                {m.role === "assistant" && actionSource.length > 0 && !m.requiresApproval && (
                  <NaviActionRunner
                    actions={actionSource}
                    messageId={m.id}
                    onRunAction={(action, actionIndex) => {
                      handleApproveAction(actionSource, actionIndex);
                    }}
                    onAllComplete={() => {
                      setCompletedActionMessages((prev) => {
                        const next = new Set(prev);
                        next.add(m.id);
                        return next;
                      });
                      // Flush action summary ONLY when ALL actions are complete
                      // This ensures the "Done!" message appears after all commands have run
                      flushActionSummary();
                      // Clear per-action activities after all complete
                      setPerActionActivities(new Map());
                      setPerActionNarratives(new Map());
                      setPerActionOutputs(new Map());
                    }}
                    actionActivities={perActionActivities}
                    narratives={perActionNarratives}
                    commandOutputs={perActionOutputs}
                  />
                )}

                {/* FILE ACTIVITIES: Show as collapsed summary below response */}
                {/* Only show if NOT currently streaming (activities shown inline during streaming) */}
                {/* This prevents duplicates - inline during streaming, summary after completion */}
                {m.role === "assistant" && showActivities && actionSource.length === 0 && !sending && (
                  (() => {
                    // Use stored activities for this message, or fall back to live events if streaming
                    // This ensures activities persist after reload/page refresh
                    const isLastMessage = messages[messages.length - 1]?.id === m.id;
                    const hasLiveActivities = activityEvents.length > 0;
                    const activitiesToShow = (m.isStreaming || (isLastMessage && hasLiveActivities && !m.storedActivities?.length))
                      ? activityEvents
                      : (m.storedActivities || []);

                    // ONLY show file-related activities below response
                    // Filter OUT: thinking, info, command, analysis, context, detection, prompt, llm_call, parsing, validation
                    // Keep ONLY: read, edit, create (file operations)
                    const fileActivities = [...activitiesToShow]
                      .filter((evt) => evt.kind === 'read' || evt.kind === 'edit' || evt.kind === 'create')
                      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

                    if (fileActivities.length === 0) return null;

                    // PHASE 3: Consolidate activities to reduce clutter
                    const consolidated = consolidateActivities(fileActivities);
                    const displayLimit = 5;
                    const hasMore = consolidated.length > displayLimit;

                    // Render a single activity row with proper styling
                    const renderActivityRow = (evt: ActivityEvent) => {
                      const isFileActivity = evt.kind === 'read' || evt.kind === 'edit' || evt.kind === 'create';
                      const filePath = evt.filePath || evt.detail;
                      // Extract just the filename from path for display
                      const fileName = filePath ? filePath.split('/').pop() : '';
                      const additions = (evt as any).additions;
                      const deletions = (evt as any).deletions;
                      const hasStats = additions !== undefined || deletions !== undefined;
                      const hasDiff = Boolean((evt as any).diff);

                      const handleFileClick = (e?: React.MouseEvent) => {
                        e?.stopPropagation();
                        if (isFileActivity && filePath) {
                          vscodeApi.postMessage({ type: 'openFile', filePath });
                        }
                      };

                      // For edit activities with diff data, render the FileDiffView
                      if (evt.kind === 'edit' && hasDiff && evt.status === 'done' && filePath) {
                        const diffLines = parseUnifiedDiff((evt as any).diff);
                        const diffData: FileDiff = {
                          path: filePath,
                          additions: additions || 0,
                          deletions: deletions || 0,
                          lines: diffLines,
                        };
                        return (
                          <FileDiffView
                            key={evt.id}
                            diff={diffData}
                            defaultExpanded={false}
                            onFileClick={handleFileClick}
                          />
                        );
                      }

                      // Default activity row rendering
                      return (
                        <div
                          key={evt.id}
                          className={`navi-inline-activity navi-inline-activity--${evt.status}`}
                        >
                          {evt.status === "running" ? (
                            <div className="navi-activity-spinner-sm"></div>
                          ) : evt.status === "done" ? (
                            <span className="navi-inline-activity-check">✓</span>
                          ) : (
                            <span className="navi-inline-activity-error">✗</span>
                          )}
                          <span className="navi-inline-activity-text">
                            <span className="navi-inline-activity-label">{evt.label}</span>
                            {filePath && (
                              <span
                                className="navi-clickable-file"
                                onClick={(e) => handleFileClick(e)}
                                title={`Click to open ${filePath}`}
                              >
                                {filePath}
                              </span>
                            )}
                            {hasStats && (
                              <span className="navi-activity-stats">
                                {additions !== undefined && additions > 0 && (
                                  <span className="navi-stat-additions">+{additions}</span>
                                )}
                                {deletions !== undefined && deletions > 0 && (
                                  <span className="navi-stat-deletions">-{deletions}</span>
                                )}
                              </span>
                            )}
                          </span>
                        </div>
                      );
                    };

                    // Render consolidated activity (single or group)
                    const renderConsolidated = (item: ConsolidatedActivity, idx: number) => {
                      if (item.type === 'single') {
                        return renderActivityRow(item.activity);
                      }
                      // Group: show summary with expandable file list
                      const groupKey = `${m.id}-group-${idx}`;
                      const isExpanded = expandedActivityGroups.has(groupKey);

                      return (
                        <div key={groupKey} className="navi-activity-group">
                          <div
                            className="navi-activity-group-header"
                            style={{ cursor: 'pointer' }}
                            onClick={() => {
                              setExpandedActivityGroups(prev => {
                                const next = new Set(prev);
                                if (next.has(groupKey)) {
                                  next.delete(groupKey);
                                } else {
                                  next.add(groupKey);
                                }
                                return next;
                              });
                            }}
                          >
                            <span className="navi-inline-activity-check">✓</span>
                            <span className="navi-inline-activity-label">{item.label}</span>
                            <span className="navi-activity-group-toggle" title="Click to expand/collapse">
                              {isExpanded ? '▼' : '▶'} ({item.activities.length} items)
                            </span>
                          </div>
                          {isExpanded && (
                            <div className="navi-activity-group-items">
                              {item.activities.map((evt) => {
                                const filePath = evt.filePath || evt.detail;
                                const isClickable = Boolean(filePath && (evt.kind === 'read' || evt.kind === 'edit' || evt.kind === 'create'));

                                return (
                                  <div
                                    key={evt.id}
                                    className={`navi-activity-group-item ${isClickable ? 'navi-activity-group-item--clickable' : ''}`}
                                    onClick={() => {
                                      if (isClickable && filePath) {
                                        // Open file in VS Code editor
                                        // For edit activities, we could open diff view
                                        if (evt.kind === 'edit') {
                                          vscodeApi.postMessage({
                                            type: 'openDiff',
                                            path: filePath,
                                          });
                                        } else {
                                          vscodeApi.postMessage({
                                            type: 'openFile',
                                            path: filePath,
                                          });
                                        }
                                      }
                                    }}
                                    title={isClickable ? `Click to open ${filePath}` : undefined}
                                  >
                                    <span className={`navi-activity-group-item-icon navi-activity-group-item-icon--${evt.kind}`}>
                                      {evt.kind === 'edit' ? '✎' : evt.kind === 'create' ? '+' : '✓'}
                                    </span>
                                    <span className={`navi-activity-group-item-path ${isClickable ? 'navi-activity-group-item-path--clickable' : ''}`}>
                                      {filePath || evt.label}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    };

                    return (
                      <div className="navi-inline-activities-section navi-inline-activities-section--post">
                        {consolidated.slice(0, displayLimit).map((item, idx) => renderConsolidated(item, idx))}
                        {hasMore && (
                          <div className="navi-show-more-activities">
                            +{consolidated.length - displayLimit} more activities
                          </div>
                        )}
                      </div>
                    );
                  })()
                )}

                {/* Timestamp - only show when no pending actions */}
                {(m.role === "user" || actionSource.length === 0 || completedActionMessages.has(m.id)) && (
                  <div
                    style={{
                      marginTop: 6,
                      fontSize: 11,
                      opacity: 0.6,
                      textAlign: m.role === "user" ? "right" : "left",
                    }}
                  >
                    {formatTime(m.createdAt)}
                  </div>
                )}

                {/* Reviews + apply fixes */}
                {m.role === "assistant" &&
                  m.responseData?.reviews &&
                  m.responseData.reviews.length > 0 && (
                    <div
                      className="navi-reviews-section"
                      style={{
                        marginTop: "16px",
                        padding: "12px",
                        backgroundColor: "#1f2430",
                        borderRadius: "6px",
                      }}
                    >
                      <h4
                        style={{
                          margin: "0 0 8px 0",
                          fontSize: "14px",
                          fontWeight: 600,
                        }}
                      >
                        Code Review ({m.responseData.reviews.length} issues)
                      </h4>
                      <div style={{ marginBottom: "12px" }}>
                        {m.responseData.reviews.slice(0, 3).map((review, idx) => (
                          <div
                            key={idx}
                            style={{ marginBottom: "8px", fontSize: "13px" }}
                          >
                            <strong>{review.path}</strong>
                            {review.line && ` (line ${review.line})`}:{" "}
                            {review.summary}
                          </div>
                        ))}
                        {m.responseData.reviews.length > 3 && (
                          <div
                            style={{ fontSize: "13px", color: "#aaa" }}
                          >{`...and ${m.responseData.reviews.length - 3
                            } more issues`}</div>
                        )}
                      </div>
                      <button
                        type="button"
                        className="navi-pill navi-pill--primary"
                        onClick={() =>
                          handleApplyAllFixes(m.responseData!.reviews!)
                        }
                        style={{ fontSize: "12px", padding: "6px 12px" }}
                      >
                        Apply all fixes
                      </button>
                    </div>
                  )}

                {m.role === "assistant" && (
                  <span style={{ display: "none" }} data-testid="response-complete">
                    complete
                  </span>
                )}

                {/* Only show action buttons when message is complete (not streaming) */}
                {!m.isStreaming && (
                  <div className="navi-chat-bubble-actions">
                    {/* Like/Dislike for assistant messages */}
                    {m.role === "assistant" && (
                      <>
                        <button
                          type="button"
                          className={`navi-icon-btn ${likedMessages.has(m.id) ? 'navi-icon-btn--active navi-icon-btn--liked' : ''}`}
                          title="Good response"
                          onClick={() => handleLikeMessage(m)}
                        >
                          <ThumbsUp className="h-3.5 w-3.5 navi-icon-3d" />
                        </button>
                        <button
                          type="button"
                          className={`navi-icon-btn ${dislikedMessages.has(m.id) ? 'navi-icon-btn--active navi-icon-btn--disliked' : ''}`}
                          title="Poor response"
                          onClick={() => handleDislikeMessage(m)}
                        >
                          <ThumbsDown className="h-3.5 w-3.5 navi-icon-3d" />
                        </button>
                        <div className="navi-icon-btn-separator" />
                      </>
                    )}
                    <button
                      type="button"
                      className="navi-icon-btn"
                      title="Copy"
                      onClick={() => handleCopyMessage(m)}
                    >
                      <Copy className="h-3.5 w-3.5 navi-icon-3d" />
                    </button>
                    {m.role === "user" && (
                      <button
                        type="button"
                        className="navi-icon-btn"
                        title="Edit and regenerate (removes responses below)"
                        onClick={() => handleEditMessage(m)}
                      >
                        <Pencil className="h-3.5 w-3.5 navi-icon-3d" />
                      </button>
                    )}
                    <button
                      type="button"
                      className="navi-icon-btn"
                      title="Undo (remove this message)"
                      onClick={() => handleUndoMessage(m)}
                    >
                      <RotateCcw className="h-3.5 w-3.5 navi-icon-3d" />
                    </button>
                    {m.role === "user" && (
                      <button
                        type="button"
                        className="navi-icon-btn"
                        title="Regenerate response"
                        onClick={() => handleRedoMessage(m)}
                      >
                        <RotateCw className="h-3.5 w-3.5 navi-icon-3d" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Live activity stream - DISABLED: Activities now show inside the streaming message bubble
            This was causing "double bubble" issue - one bubble for activities, one for response.
            Activities are now rendered inside the message bubble (see PRE-RESPONSE ACTIVITIES section above).
            Only show this if there's NO streaming message (edge case fallback) */}
        {sending && !messages.some(m => m.isStreaming) && (activityEvents.some(evt => evt.status === 'running') || narrativeLines.length > 0) && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">
              <Zap className="h-4 w-4 navi-icon-3d" />
            </div>
            <div className="navi-chat-bubble navi-chat-bubble--assistant">
              <div className="navi-inline-activities-section">
                {/* Claude Code-style stream - interleave narratives and activities by timestamp */}
                {(() => {
                  // Combine narratives and activities into a single sorted stream
                  type StreamItem =
                    | { type: 'narrative'; id: string; text: string; timestamp: string }
                    | { type: 'activity'; data: typeof activityEvents[0] };

                  const allItems: StreamItem[] = [
                    ...narrativeLines.map(n => ({ type: 'narrative' as const, ...n })),
                    ...activityEvents.map(a => ({ type: 'activity' as const, data: a })),
                  ];

                  // Sort by timestamp to maintain order
                  allItems.sort((a, b) => {
                    const timeA = a.type === 'narrative' ? a.timestamp : a.data.timestamp;
                    const timeB = b.type === 'narrative' ? b.timestamp : b.data.timestamp;
                    return new Date(timeA).getTime() - new Date(timeB).getTime();
                  });

                  return allItems.map((item, idx) => {
                    if (item.type === 'narrative') {
                      // Render narrative text (Claude Code conversational style)
                      return (
                        <div key={item.id} className="navi-narrative-line">
                          {item.text}
                        </div>
                      );
                    }

                    // Render activity item
                    const evt = item.data;
                    const getActivityDisplay = () => {
                      switch (evt.kind) {
                        case 'detection':
                          return { icon: '🔍', label: 'Detected', detail: evt.detail };
                        case 'context':
                          return { icon: '📋', label: evt.label, detail: evt.detail };
                        case 'rag':
                          return { icon: '🔎', label: 'Search', detail: evt.detail };
                        case 'read':
                          return { icon: '📄', label: 'Read', detail: evt.detail, isFile: true };
                        case 'edit':
                          return { icon: '✏️', label: 'Edit', detail: evt.detail, isFile: true };
                        case 'create':
                          return { icon: '📝', label: 'Create', detail: evt.detail, isFile: true };
                        case 'prompt':
                          return null;
                        case 'llm_call':
                          return null;
                        case 'thinking':
                          return { icon: '💡', label: 'Thinking', detail: null };
                        case 'response':
                          return { icon: '📝', label: evt.label, detail: evt.detail };
                        case 'command':
                          return { icon: '⚡', label: 'Run', detail: evt.detail, isCommand: true };
                        case 'validation':
                          return { icon: '✅', label: evt.label, detail: evt.detail };
                        case 'parsing':
                          return null;
                        default:
                          return { icon: '●', label: evt.label || evt.kind, detail: evt.detail };
                      }
                    };

                    const display = getActivityDisplay();
                    if (!display) return null;

                    return (
                      <div
                        key={evt.id}
                        className={`navi-activity-item navi-activity-item--${evt.status} ${display.isFile ? 'navi-activity-item--file' : ''} ${display.isCommand ? 'navi-activity-item--command' : ''}`}
                      >
                        <span className="navi-activity-item-icon">{display.icon}</span>
                        <span className="navi-activity-item-label">{display.label}</span>
                        {display.detail && (
                          <span className={`navi-activity-item-detail ${display.isFile ? 'navi-activity-item-detail--file' : ''}`}>
                            {display.detail}
                          </span>
                        )}
                        {evt.status === "running" && (
                          <div className="navi-activity-spinner-sm navi-activity-item-spinner"></div>
                        )}
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
          </div>
        )}

        {/* Progress indicator when NAVI is thinking (no activities yet) */}
        {showTypingIndicator && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">
              <Zap className="h-4 w-4 navi-icon-3d" />
            </div>
            <div
              className="navi-chat-bubble navi-chat-bubble--assistant"
              data-testid="typing-indicator"
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <div className="navi-thinking-spinner" />
                <span
                  style={{ fontStyle: "italic", color: "#666" }}
                >{`NAVI is working on your request...`}</span>
              </div>
            </div>
          </div>
        )}

        {sendTimedOut && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">
              <Zap className="h-4 w-4 navi-icon-3d" />
            </div>
            <div className="navi-chat-bubble navi-chat-bubble--assistant" style={{ border: "1px solid #60a5fa", background: "rgba(96, 165, 250, 0.1)" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Loader2 size={14} className="navi-spin" style={{ color: "#60a5fa" }} />
                  <span style={{ color: "#93c5fd" }}>Still working on your request...</span>
                </div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>
                  Complex tasks may take longer. Check if the backend is running.
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <button
                    type="button"
                    className="navi-pill navi-pill--ghost"
                    onClick={() => {
                      setSendTimedOut(false);
                      setSending(false);
                    }}
                    style={{ padding: "4px 10px", fontSize: 11 }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="navi-pill navi-pill--ghost"
                    onClick={() => lastSentRef.current && void handleSend(lastSentRef.current)}
                    style={{ padding: "4px 10px", fontSize: 11 }}
                  >
                    Retry
                  </button>
                  <button
                    type="button"
                    className="navi-pill navi-pill--primary"
                    onClick={handleDirectFallbackSend}
                    style={{ padding: "4px 10px", fontSize: 11 }}
                  >
                    Send directly
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Activity stream removed - activities now rendered inline in unified timeline */}

        {/* Inline change summary bar (Cursor-style) - shows after action completion */}
        {inlineChangeSummary && (
          <FileChangeSummary
            files={inlineChangeSummary.files.map((file) => ({
              path: file.path,
              additions: file.additions,
              deletions: file.deletions,
              originalContent: file.originalContent,
              wasCreated: file.wasCreated,
            }))}
            totalAdditions={inlineChangeSummary.totalAdditions}
            totalDeletions={inlineChangeSummary.totalDeletions}
            onKeep={handleKeepChanges}
            onUndo={handleUndoChanges}
            onFileClick={handleOpenSummaryDiff}
            onPreviewAll={handlePreviewAllChanges}
          />
        )}

        {/* Next steps suggestions - show when available and not streaming */}
        {/* Hide when Task Complete panel is visible (it has its own next steps section) */}
        {!sending && lastNextSteps.length > 0 && !taskSummary && (
          <div className="navi-next-steps">
            <div className="navi-next-steps-header">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Suggested next steps</span>
            </div>
            <div className="navi-next-steps-list">
              {getContextualSuggestions(lastNextSteps, taskSummary).map((step, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="navi-next-step-btn"
                  onClick={() => {
                    setInput(step);
                    handleSend();
                  }}
                >
                  {step}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Files edited summary - only show when we have files and not actively streaming */}
        {!showActivityStream && hasActivityFiles && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">
              <FolderTree className="h-4 w-4 navi-icon-3d" />
            </div>
            <div className="navi-chat-bubble navi-chat-bubble--activity">
              <div className="navi-files-summary">
                <button
                  type="button"
                  className="navi-files-summary-header"
                  onClick={() => setActivityFilesOpen((prev) => !prev)}
                >
                  {activityFilesOpen ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  <span className="navi-files-summary-title">
                    {activityFileSummary.count} file{activityFileSummary.count === 1 ? "" : "s"} edited
                  </span>
                  {activityFileSummary.hasStats && (
                    <span className="navi-files-summary-stats">
                      <span className="navi-files-add">+{activityFileSummary.additions}</span>
                      <span className="navi-files-del">-{activityFileSummary.deletions}</span>
                    </span>
                  )}
                </button>

                {activityFilesOpen && (
                  <div className="navi-files-summary-body">
                    {activityFileList.map((file) => {
                      const additions = typeof file.additions === "number" ? file.additions : undefined;
                      const deletions = typeof file.deletions === "number" ? file.deletions : undefined;
                      const hasStats = typeof additions === "number" || typeof deletions === "number";

                      return (
                        <div
                          key={file.path}
                          className="navi-files-summary-item"
                          onClick={() => handleOpenActivityDiff({ path: file.path, scope: file.scope })}
                        >
                          <span className="navi-files-summary-item-name">
                            {toWorkspaceRelativePath(file.path)}
                          </span>
                          {hasStats && (
                            <span className="navi-files-summary-item-stats">
                              {typeof additions === "number" && (
                                <span className="navi-files-add">+{additions}</span>
                              )}
                              {typeof deletions === "number" && (
                                <span className="navi-files-del">-{deletions}</span>
                              )}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Bottom Thinking Indicator - Shows at END of chat during initial streaming */}
        {/* BUG FIX: Moved here from inside message bubble to ensure it shows at bottom */}
        {(() => {
          // Check if there are any real tool activities (not just liveProgress/status)
          const hasRealActivities = activityEvents.some(
            evt => evt.kind === 'read' || evt.kind === 'edit' || evt.kind === 'create' || evt.kind === 'command'
          );
          // Show thinking indicator at bottom when:
          // 1. We are sending/streaming
          // 2. No real activities have started
          // 3. No message content yet in the last message
          const lastMessage = messages[messages.length - 1];
          const shouldShowBottomThinking = sending &&
            !hasRealActivities &&
            narrativeLines.length === 0 &&
            (!lastMessage?.content || lastMessage.content.trim() === '');

          if (!shouldShowBottomThinking) return null;

          return (
            <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
              <div className="navi-chat-avatar navi-chat-avatar--assistant">
                <Zap className="h-4 w-4 navi-icon-3d" />
              </div>
              <div className="navi-chat-bubble navi-chat-bubble--assistant">
                <div className="navi-thinking-block navi-thinking-block--bottom">
                  <div
                    className="navi-thinking-header"
                    onClick={() => accumulatedThinking ? setThinkingExpanded(prev => !prev) : undefined}
                    style={{ cursor: accumulatedThinking ? 'pointer' : 'default' }}
                  >
                    {accumulatedThinking && (
                      <ChevronRight
                        size={14}
                        className={`navi-thinking-chevron ${thinkingExpanded ? 'expanded' : ''}`}
                      />
                    )}
                    <span className="navi-thinking-label">
                      {"Thinking...".split("").map((char, i) => (
                        <span key={i} className="navi-thinking-label-char">{char}</span>
                      ))}
                    </span>
                  </div>
                  {thinkingExpanded && accumulatedThinking && (
                    <div className="navi-thinking-content navi-thinking-content--streaming">
                      {accumulatedThinking}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })()}

        {/* Task Complete Panel - shows after task finishes */}
        {!sending && taskSummary && (
          <div className="navi-task-complete-panel">
            <div className="navi-task-complete-header">
              <div className="navi-task-complete-title">
                <CheckCircle className="h-4 w-4 text-green-400" />
                <span>Task Complete</span>
              </div>
              <button
                type="button"
                className="navi-task-complete-close"
                onClick={() => setTaskSummary(null)}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Summary text */}
            {taskSummary.summaryText && (
              <div className="navi-task-complete-summary">
                {taskSummary.summaryText}
              </div>
            )}

            {/* Files changed section - Claude Code style */}
            {(taskSummary.filesModified > 0 || taskSummary.filesCreated > 0) && (() => {
              // Calculate total additions/deletions from file list
              const totalAdditions = taskSummary.filesList?.reduce((sum, f) => sum + (f.additions || 0), 0) || 0;
              const totalDeletions = taskSummary.filesList?.reduce((sum, f) => sum + (f.deletions || 0), 0) || 0;
              const fileCount = (taskSummary.filesModified || 0) + (taskSummary.filesCreated || 0);

              return (
                <div className="navi-task-complete-files">
                  <button
                    type="button"
                    className="navi-task-complete-files-header"
                    onClick={() => setTaskFilesExpanded((prev) => !prev)}
                  >
                    {taskFilesExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    <span className="navi-task-complete-files-summary">
                      <span className="navi-task-complete-files-count">{fileCount}</span>
                      <span className="navi-task-complete-files-label">file{fileCount !== 1 ? 's' : ''} changed</span>
                      {(totalAdditions > 0 || totalDeletions > 0) && (
                        <span className="navi-task-complete-files-stats">
                          {totalAdditions > 0 && <span className="navi-activity-change-add">+{totalAdditions}</span>}
                          {totalDeletions > 0 && <span className="navi-activity-change-del">-{totalDeletions}</span>}
                        </span>
                      )}
                    </span>
                  </button>
                  {taskFilesExpanded && taskSummary.filesList && (
                    <div className="navi-task-complete-files-list">
                      {taskSummary.filesList.map((file) => (
                        <div
                          key={file.path}
                          className="navi-task-complete-file-item"
                        >
                          <span className={`navi-task-complete-file-icon ${file.action === 'created' ? 'navi-file-created' : 'navi-file-modified'}`}>
                            {file.action === 'created' ? '+' : '~'}
                          </span>
                          <span
                            className="navi-task-complete-file-path"
                            onClick={() => handleOpenActivityDiff({ path: file.path, scope: 'working' })}
                          >
                            {toWorkspaceRelativePath(file.path)}
                          </span>
                          {(file.additions !== undefined || file.deletions !== undefined) && (
                            <span className="navi-task-complete-file-stats">
                              {file.additions !== undefined && (
                                <span className="navi-files-add">+{file.additions}</span>
                              )}
                              {file.deletions !== undefined && (
                                <span className="navi-files-del">-{file.deletions}</span>
                              )}
                            </span>
                          )}
                          <button
                            type="button"
                            className="navi-task-complete-file-diff-btn"
                            onClick={() => handleOpenActivityDiff({ path: file.path, scope: 'working' })}
                            title="View diff"
                          >
                            <Eye size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Verification status */}
            {taskSummary.verificationPassed !== null && (
              <div className="navi-task-complete-verification">
                <span className="navi-task-complete-verification-label">VERIFICATION</span>
                <div className="navi-task-complete-verification-badges">
                  {taskSummary.verificationDetails?.typecheck !== undefined && (
                    <span className={`navi-verification-badge ${taskSummary.verificationDetails.typecheck.passed ? 'navi-verification-badge--passed' : 'navi-verification-badge--failed'}`}>
                      {taskSummary.verificationDetails.typecheck.passed ? '✓' : '✗'} TypeScript
                    </span>
                  )}
                  {taskSummary.verificationDetails?.lint !== undefined && (
                    <span className={`navi-verification-badge ${taskSummary.verificationDetails.lint.passed ? 'navi-verification-badge--passed' : 'navi-verification-badge--failed'}`}>
                      {taskSummary.verificationDetails.lint.passed ? '✓' : '✗'} ESLint
                    </span>
                  )}
                  {taskSummary.verificationDetails?.build !== undefined && (
                    <span className={`navi-verification-badge ${taskSummary.verificationDetails.build.passed ? 'navi-verification-badge--passed' : 'navi-verification-badge--failed'}`}>
                      {taskSummary.verificationDetails.build.passed ? '✓' : '✗'} Build
                    </span>
                  )}
                  {taskSummary.verificationDetails?.tests !== undefined && (
                    <span className={`navi-verification-badge ${taskSummary.verificationDetails.tests.passed ? 'navi-verification-badge--passed' : 'navi-verification-badge--failed'}`}>
                      {taskSummary.verificationDetails.tests.passed ? '✓' : '✗'} Tests
                    </span>
                  )}
                  {!taskSummary.verificationDetails && (
                    <span className={`navi-verification-badge ${taskSummary.verificationPassed ? 'navi-verification-badge--passed' : 'navi-verification-badge--failed'}`}>
                      {taskSummary.verificationPassed ? '✓ Passed' : '✗ Failed'}
                    </span>
                  )}
                </div>
                {/* Show build errors if any */}
                {taskSummary.verificationDetails?.build && !taskSummary.verificationDetails.build.passed && taskSummary.verificationDetails.build.errors && taskSummary.verificationDetails.build.errors.length > 0 && (
                  <div className="navi-build-errors">
                    <div className="navi-build-errors-header">
                      <AlertCircle size={14} />
                      <span>Build Errors ({taskSummary.verificationDetails.build.errors.length})</span>
                    </div>
                    <div className="navi-build-errors-list">
                      {taskSummary.verificationDetails.build.errors.slice(0, 5).map((error, idx) => (
                        <div key={idx} className="navi-build-error-item">
                          <code>{error}</code>
                        </div>
                      ))}
                      {taskSummary.verificationDetails.build.errors.length > 5 && (
                        <div className="navi-build-error-more">
                          +{taskSummary.verificationDetails.build.errors.length - 5} more errors
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Action buttons: Keep / Review / Undo (Claude Code style) */}
            {(taskSummary.filesModified > 0 || taskSummary.filesCreated > 0) && (
              <div className="navi-task-complete-actions">
                <button
                  type="button"
                  className="navi-task-complete-accept-btn"
                  onClick={() => {
                    vscodeApi.postMessage({ type: 'task.accept' });
                    setTaskSummary(null);
                  }}
                >
                  <Check size={18} />
                  <span>Keep</span>
                </button>
                {taskSummary.filesList && (
                  <button
                    type="button"
                    className="navi-task-complete-review-btn"
                    onClick={() => {
                      const files = taskSummary.filesList?.map(f => f.path) || [];
                      vscodeApi.postMessage({ type: 'task.reviewAll', files });
                    }}
                  >
                    <Eye size={18} />
                    <span>Review</span>
                  </button>
                )}
                <button
                  type="button"
                  className="navi-task-complete-revert-btn"
                  onClick={() => {
                    vscodeApi.postMessage({ type: 'task.revert' });
                    setTaskSummary(null);
                  }}
                >
                  <RotateCcw size={18} />
                  <span>Undo</span>
                </button>
              </div>
            )}

            {/* Next steps suggestions */}
            {taskSummary.nextSteps.length > 0 && (
              <div className="navi-task-complete-next">
                <span className="navi-task-complete-next-label">SUGGESTED NEXT</span>
                <div className="navi-task-complete-next-btns">
                  {getContextualSuggestions(taskSummary.nextSteps, taskSummary).map((step, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="navi-task-complete-next-btn"
                      onClick={() => {
                        setInput(step);
                        inputRef.current?.focus();
                      }}
                    >
                      {step}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {structuredReview && structuredReview.files.length > 0 && (
          <div className="mt-2 space-y-2">
            <div className="flex items-center justify-between">
              <div className="navi-section-title">
                <ClipboardList className="navi-icon-3d" />
                Review Results
              </div>
              <div className="flex items-center gap-1 text-xs">
                <button
                  type="button"
                  className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 ${reviewViewMode === "issues"
                    ? "bg-gray-700 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200"
                    }`}
                  onClick={() => setReviewViewMode("issues")}
                >
                  Issues
                </button>
                <button
                  type="button"
                  className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 ${reviewViewMode === "diffs"
                    ? "bg-gray-700 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200"
                    }`}
                  onClick={() => setReviewViewMode("diffs")}
                >
                  Diffs
                </button>
              </div>
            </div>
            {reviewViewMode === "diffs" ? (
              <VisualDiffViewer review={structuredReview} onAutoFix={handleAutoFix} />
            ) : (
              <StructuredReviewComponent review={structuredReview} onAutoFix={handleAutoFix} />
            )}
          </div>
        )}

        {/* PHASE 1.2: Minimal repo diff summary (NO defaults, ONLY real agent data) */}
        {repoSummary && changeDetailsOpen && (
          <div className="p-3 bg-gray-900/70 border border-gray-700 rounded-lg mt-2 space-y-2">
            <div className="flex items-center justify-between">
              <div className="navi-section-title">
                <BarChart3 className="navi-icon-3d" />
                Working Tree Changes
              </div>
              <span className="text-xs text-gray-400">base: <span className="font-mono text-blue-300">{repoSummary.base}</span></span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 bg-gray-800/50 rounded border border-gray-700">
                <div className="text-xs text-gray-400">Unstaged</div>
                <div className="text-lg font-semibold text-yellow-400">{repoSummary.unstagedCount}</div>
              </div>
              <div className="p-2 bg-gray-800/50 rounded border border-gray-700">
                <div className="text-xs text-gray-400">Staged</div>
                <div className="text-lg font-semibold text-green-400">{repoSummary.stagedCount}</div>
              </div>
            </div>

            {repoSummary.unstagedFiles.length > 0 && (
              <div className="pt-1 border-t border-gray-700">
                <div className="text-xs font-medium text-gray-300 mb-1">Unstaged ({repoSummary.unstagedFiles.length}):</div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {repoSummary.unstagedFiles.map((f, idx) => (
                    <div key={idx} className="text-xs text-gray-400 font-mono">
                      <span className="text-yellow-500">{f.status}</span> {f.path}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {repoSummary.stagedFiles.length > 0 && (
              <div className="pt-1 border-t border-gray-700">
                <div className="text-xs font-medium text-gray-300 mb-1">Staged ({repoSummary.stagedFiles.length}):</div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {repoSummary.stagedFiles.map((f, idx) => (
                    <div key={idx} className="text-xs text-gray-400 font-mono">
                      <span className="text-green-500">{f.status}</span> {f.path}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {repoSummary.unstagedCount === 0 && repoSummary.stagedCount === 0 && (
              <div className="text-xs text-gray-500 italic">No changes in working tree.</div>
            )}
          </div>
        )}

        {/* PHASE 1.3: Diff Viewer (READ-ONLY, NO OPINIONS, NO ACTIONS) */}
        {diffDetails.length > 0 && changeDetailsOpen && (
          <div className="mt-2 space-y-2" ref={diffSectionRef}>
            <div className="navi-section-title">
              <FileText className="navi-icon-3d" />
              File Changes
            </div>
            {diffDetails.map((fileDiff, idx) => (
              <DiffFileCard key={`${fileDiff.path}-${idx}`} fileDiff={fileDiff} />
            ))}
          </div>
        )}

        {/* PHASE 1.3: Navi Assessment (read-only) */}
        {assessment && (
          <div className="mt-2 space-y-2 p-3 bg-gray-900/70 border border-gray-700 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="navi-section-title">
                <Brain className="navi-icon-3d" />
                Navi Assessment
              </div>
              <span className="text-xs text-gray-400">
                {assessment.totalDiagnostics} issue{assessment.totalDiagnostics !== 1 ? 's' : ''} ({assessment.introduced} introduced)
              </span>
            </div>
            <div className="text-xs text-gray-300 space-y-1">
              <div>- {assessment.totalDiagnostics} issues in scope</div>
              <div>- {assessment.introduced} introduced by your changes</div>
              <div>- {assessment.preExisting} pre-existing issues</div>
              <div>- {assessment.filesAffected} files affected</div>
            </div>
            <div className="text-xs text-gray-500 italic">No actions taken yet.</div>
          </div>
        )}

        {/* PHASE 1.4: Consent Card for Scope Expansion */}
        {assessment && assessment.hasGlobalIssuesOutsideChanged && scopeIsChangedFiles && (
          <div className="mt-2 p-3 bg-blue-950/40 border border-blue-700/60 rounded-lg space-y-3">
            <div className="flex items-start gap-2">
              <HelpCircle className="h-4 w-4 text-blue-300 navi-icon-3d mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-blue-200">Scope Decision</h4>
                <p className="text-xs text-blue-300 mt-1">
                  I found <span className="font-bold">{assessment.preExisting}</span> pre-existing issues in the workspace. Your current changes introduced <span className="font-bold">{assessment.introduced}</span> new issues.
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setScopeDecision('changed-files')}
                className={`text-xs px-3 py-2 rounded border transition ${scopeIsChangedFiles
                  ? 'bg-blue-700/60 border-blue-500 text-blue-100'
                  : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                  }`}
              >
                Review changed files only
              </button>
              <button
                onClick={() => setScopeDecision('workspace')}
                className={`text-xs px-3 py-2 rounded border transition ${scopeIsWorkspace
                  ? 'bg-blue-700/60 border-blue-500 text-blue-100'
                  : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                  }`}
              >
                Include all workspace issues
              </button>
            </div>
          </div>
        )}

        {/* PHASE 1.4: Diagnostics (Changed Files Only, or All if Workspace Scope Enabled) */}
        {diagnosticsByFile.length > 0 && scopeDecision === 'changed-files' && (
          <div className="mt-2 space-y-2 p-3 bg-gray-900/70 border border-gray-700 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="navi-section-title">
                <Activity className="navi-icon-3d" />
                Diagnostics (Changed Files)
              </div>
              <span className="text-xs text-gray-400">
                {(() => {
                  const flat = diagnosticsByFile.flatMap(f => f.diagnostics);
                  const errors = flat.filter(d => d.severity === 0).length;
                  const warnings = flat.filter(d => d.severity === 1).length;
                  return `Errors: ${errors} | Warnings: ${warnings}`;
                })()}
              </span>
            </div>

            {diagnosticsByFile.map((f, idx) => (
              <div key={`${f.path}-${idx}`} className="border-t border-gray-700 pt-2">
                <div className="text-xs font-mono text-gray-300">{f.path}</div>
                <div className="mt-1 space-y-1">
                  {f.diagnostics.map((d, j) => (
                    <div key={j} className="text-xs text-gray-300 flex items-center gap-2">
                      <span className={`navi-severity-badge ${d.severity === 0 ? "navi-severity-badge--error" : d.severity === 1 ? "navi-severity-badge--warn" : "navi-severity-badge--info"}`}>
                        {d.severity === 0 ? "ERR" : d.severity === 1 ? "WARN" : "INFO"}
                      </span>
                      <span className="font-mono text-gray-400">{d.line}:{d.character}</span>
                      <span className="text-gray-300">{d.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* PHASE 1.4: Workspace Scope Indicator */}
        {scopeDecision === 'workspace' && assessment && (
          <div className="mt-2 p-3 bg-green-950/40 border border-green-700/60 rounded-lg">
            <div className="text-xs text-green-300 flex items-center gap-2">
              <CheckCircle2 className="h-3.5 w-3.5 navi-icon-3d" />
              <span>
                <strong>Workspace Scope Enabled</strong> - Showing all {assessment.totalDiagnostics} issues ({assessment.changedFileDiagsCount} in changed files, {assessment.preExisting} pre-existing).
              </span>
            </div>
          </div>
        )}

        {/* PHASE 1.5: Diagnostics by File (Grouped, Expandable, Read-Only) */}
        {detailedDiagnostics.length > 0 && (() => {
          // Filter based on scope decision
          const changedFiles = new Set([
            ...diffDetails.map(d => d.path),
            ...(repoSummary?.unstagedFiles || []).map((f: any) => f.path),
            ...(repoSummary?.stagedFiles || []).map((f: any) => f.path)
          ]);
          const filteredDiagnostics = scopeDecision === 'changed-files'
            ? detailedDiagnostics.filter(fd => changedFiles.has(fd.filePath))
            : detailedDiagnostics;

          if (filteredDiagnostics.length === 0) return null;

          return (
            <div className="mt-2 space-y-2 p-3 bg-gray-900/70 border border-gray-700 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="navi-section-title">
                  <FolderTree className="navi-icon-3d" />
                  Diagnostics by File
                </div>
                <span className="text-xs text-gray-400">
                  {filteredDiagnostics.reduce((sum, f) => sum + f.diagnostics.length, 0)} issues in {filteredDiagnostics.length} files
                </span>
              </div>

              {filteredDiagnostics.map((fileGroup, idx) => {
                const isExpanded = expandedFiles.has(fileGroup.filePath);
                const errorCount = fileGroup.diagnostics.filter(d => d.severity === 'error').length;
                const warningCount = fileGroup.diagnostics.filter(d => d.severity === 'warning').length;

                return (
                  <div key={`${fileGroup.filePath}-${idx}`} className="border-t border-gray-700 pt-2">
                    <button
                      onClick={() => {
                        const newExpanded = new Set(expandedFiles);
                        if (isExpanded) {
                          newExpanded.delete(fileGroup.filePath);
                        } else {
                          newExpanded.add(fileGroup.filePath);
                        }
                        setExpandedFiles(newExpanded);
                      }}
                      className="w-full text-left flex items-center gap-2 hover:bg-gray-800/50 p-1 rounded transition"
                    >
                      <span className="navi-collapse-icon">
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5 navi-icon-3d" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 navi-icon-3d" />
                        )}
                      </span>
                      <span className="text-xs font-mono text-gray-300 flex-1">{fileGroup.filePath}</span>
                      <span className="text-xs text-gray-400">
                        ({fileGroup.diagnostics.length} | {errorCount > 0 ? `Errors: ${errorCount}` : 'No errors'} | {warningCount > 0 ? `Warnings: ${warningCount}` : 'No warnings'})
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="mt-2 ml-4 space-y-1">
                        {fileGroup.diagnostics.map((diag, j) => (
                          <div key={j} className="text-xs text-gray-300 flex items-start gap-2 py-1">
                            <span className={`navi-severity-badge ${diag.severity === 'error' ? "navi-severity-badge--error" : diag.severity === 'warning' ? "navi-severity-badge--warn" : "navi-severity-badge--info"}`}>
                              {diag.severity === 'error' ? "ERR" : diag.severity === 'warning' ? "WARN" : "INFO"}
                            </span>
                            <div className="flex-1">
                              <div className="text-gray-200">{diag.message}</div>
                              <div className="text-gray-500 text-xs mt-0.5">
                                Line {diag.line}:{diag.character} | {diag.source} | {diag.impact === 'introduced' ? 'Introduced' : 'Pre-existing'}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })()}

        {/* PHASE 2.0 STEP 2: Fix Proposals (Read-Only with Approval Controls) */}
        {fixProposals.length > 0 && (() => {
          const totalProposals = fixProposals.reduce((sum, f) => sum + f.proposals.length, 0);
          const approvedCount = Array.from(approvalState.values()).filter(v => v === 'approved').length;
          const ignoredCount = Array.from(approvalState.values()).filter(v => v === 'ignored').length;

          return (
            <div className="mt-2 space-y-2 p-3 bg-blue-950/30 border border-blue-700/50 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="navi-section-title navi-section-title--accent">
                  <Wrench className="navi-icon-3d" />
                  Fix Proposals
                </div>
                <span className="text-xs text-blue-300">
                  {totalProposals} fixable | {approvedCount} approved | {ignoredCount} ignored
                </span>
              </div>

              {fixProposals.map((fileGroup, idx) => (
                <div key={`proposal-file-${idx}`} className="border-t border-blue-700/30 pt-2">
                  <div className="text-xs font-mono text-blue-200 mb-2">{fileGroup.filePath}</div>
                  <div className="space-y-3">
                    {fileGroup.proposals.map((proposal, _j) => {
                      const isExpanded = expandedProposals.has(proposal.id);
                      const state = approvalState.get(proposal.id);
                      const isApproved = state === 'approved';
                      const isIgnored = state === 'ignored';
                      const severityClass =
                        proposal.severity === 'error'
                          ? "navi-severity-icon--error"
                          : proposal.severity === 'warning'
                            ? "navi-severity-icon--warn"
                            : "navi-severity-icon--info";
                      const severityIcon =
                        proposal.severity === 'error' ? (
                          <CircleX className="h-3.5 w-3.5 navi-icon-3d" />
                        ) : proposal.severity === 'warning' ? (
                          <AlertTriangle className="h-3.5 w-3.5 navi-icon-3d" />
                        ) : (
                          <Info className="h-3.5 w-3.5 navi-icon-3d" />
                        );
                      const impactLabel = proposal.impact === 'introduced' ? 'Introduced' : 'Pre-existing';
                      const impactClass =
                        proposal.impact === 'introduced'
                          ? "navi-impact-pill--introduced"
                          : "navi-impact-pill--existing";
                      const riskLabel = proposal.riskLevel
                        ? `${proposal.riskLevel.charAt(0).toUpperCase()}${proposal.riskLevel.slice(1)} risk`
                        : null;
                      const riskClass =
                        proposal.riskLevel === 'high'
                          ? "navi-risk-pill--high"
                          : proposal.riskLevel === 'medium'
                            ? "navi-risk-pill--medium"
                            : proposal.riskLevel === 'low'
                              ? "navi-risk-pill--low"
                              : "";
                      const confidenceLevel = proposal.confidence
                        ? proposal.confidence.toLowerCase()
                        : "low";
                      const confidenceClass =
                        confidenceLevel === "high"
                          ? "navi-confidence-pill--high"
                          : confidenceLevel === "medium"
                            ? "navi-confidence-pill--medium"
                            : "navi-confidence-pill--low";

                      return (
                        <div
                          key={proposal.id}
                          className={`p-2 rounded border ${isApproved
                            ? 'bg-green-950/40 border-green-700/50'
                            : isIgnored
                              ? 'bg-gray-800/40 border-gray-600/50'
                              : 'bg-gray-900/60 border-gray-700/50'
                            }`}
                        >
                          {/* Proposal Header */}
                          <div className="flex items-start gap-2 mb-2">
                            <span className={`navi-severity-icon ${severityClass}`}>
                              {severityIcon}
                            </span>
                            <div className="flex-1">
                              <div className="text-xs text-gray-200 font-semibold">{proposal.issue}</div>
                              <div className="text-xs text-gray-400 mt-0.5 flex flex-wrap items-center gap-2">
                                <span>Line {proposal.line}</span>
                                <span>{proposal.source}</span>
                                <span className={`navi-impact-pill ${impactClass}`}>{impactLabel}</span>
                                {riskLabel && (
                                  <span className={`navi-risk-pill ${riskClass}`}>{riskLabel}</span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className={`navi-confidence-pill ${confidenceClass}`}>
                                {proposal.confidence || "low"}
                              </span>
                            </div>
                          </div>

                          {/* Explanation */}
                          <div className="mb-2 p-2 bg-gray-800/50 rounded">
                            <div className="text-xs text-gray-400 font-semibold mb-1">Root Cause:</div>
                            <div className="text-xs text-gray-300">{proposal.rootCause}</div>
                          </div>

                          {/* Suggested Change */}
                          <button
                            onClick={() => {
                              const newExpanded = new Set(expandedProposals);
                              if (isExpanded) {
                                newExpanded.delete(proposal.id);
                              } else {
                                newExpanded.add(proposal.id);
                              }
                              setExpandedProposals(newExpanded);
                            }}
                            className="w-full text-left text-xs text-blue-300 hover:text-blue-200 mb-2 transition flex items-center gap-2"
                          >
                            {isExpanded ? (
                              <ChevronDown className="h-3.5 w-3.5 navi-icon-3d" />
                            ) : (
                              <ChevronRight className="h-3.5 w-3.5 navi-icon-3d" />
                            )}
                            Suggested Change
                          </button>

                          {isExpanded && (
                            <div className="mb-2 p-2 bg-gray-900/70 rounded border border-gray-700">
                              <div className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                                {proposal.suggestedChange}
                              </div>
                            </div>
                          )}

                          {/* Action Buttons */}
                          <div className="flex gap-2 mt-2">
                            <button
                              onClick={() => {
                                const newState = new Map(approvalState);
                                if (isApproved) {
                                  newState.delete(proposal.id);
                                  setApprovalState(newState);
                                  console.log(`[NaviUI] Proposal ${proposal.id} unapproved`);
                                } else {
                                  // Phase 2.1.2: Check if proposal requires choice
                                  if (proposal.requiresChoice && proposal.alternatives && proposal.alternatives.length > 0) {
                                    console.log(`[NaviUI] Proposal ${proposal.id} requires choice - opening modal...`);
                                    setAlternativeModal({
                                      proposalId: proposal.id,
                                      alternatives: proposal.alternatives
                                    });
                                  } else {
                                    newState.set(proposal.id, 'approved');
                                    setApprovalState(newState);
                                    console.log(`[NaviUI] Proposal ${proposal.id} approved - applying fix...`);
                                    // Phase 2.1: Send apply intent to extension via vscodeApi
                                    vscodeApi.postMessage({ type: 'navi.fix.apply', proposalId: proposal.id });
                                  }
                                }
                              }}
                              className={`text-xs px-3 py-1.5 rounded transition ${isApproved
                                ? 'bg-green-700 text-white hover:bg-green-600'
                                : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                                } flex items-center gap-1`}
                              disabled={isIgnored}
                            >
                              {isApproved ? (
                                <>
                                  <CheckCircle2 className="h-3.5 w-3.5 navi-icon-3d" />
                                  Approved
                                </>
                              ) : proposal.requiresChoice ? (
                                <>
                                  <Search className="h-3.5 w-3.5 navi-icon-3d" />
                                  Choose Fix
                                </>
                              ) : (
                                <>
                                  <CheckCircle2 className="h-3.5 w-3.5 navi-icon-3d" />
                                  Approve
                                </>
                              )}
                            </button>
                            <button
                              onClick={() => {
                                const newState = new Map(approvalState);
                                if (isIgnored) {
                                  newState.delete(proposal.id);
                                } else {
                                  newState.set(proposal.id, 'ignored');
                                }
                                setApprovalState(newState);
                                console.log(`[NaviUI] Proposal ${proposal.id} ${isIgnored ? 'un-ignored' : 'ignored'}`);
                              }}
                              className={`text-xs px-3 py-1.5 rounded transition ${isIgnored
                                ? 'bg-gray-600 text-white hover:bg-gray-500'
                                : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                                } flex items-center gap-1`}
                              disabled={isApproved}
                            >
                              {isIgnored ? (
                                <>
                                  <CircleX className="h-3.5 w-3.5 navi-icon-3d" />
                                  Ignored
                                </>
                              ) : (
                                <>
                                  <CircleX className="h-3.5 w-3.5 navi-icon-3d" />
                                  Ignore
                                </>
                              )}
                            </button>
                          </div>

                          {isApproved && (
                            <div className="mt-2 text-xs text-green-400 italic flex items-center gap-1">
                              <CheckCircle2 className="h-3.5 w-3.5 navi-icon-3d" />
                              Ready for application (no file edits yet - Phase 2.1)
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}

              {approvedCount > 0 && (
                <div className="mt-2 p-2 bg-blue-900/30 border border-blue-700/50 rounded text-xs text-blue-200 flex items-center gap-2">
                  <Info className="h-3.5 w-3.5 navi-icon-3d" />
                  <span>
                    {approvedCount} fix{approvedCount !== 1 ? 'es' : ''} approved. Actual file edits will be available in Phase 2.1.
                  </span>
                </div>
              )}
            </div>
          );
        })()}

        {/* LEGACY UI DISABLED FOR PHASE 1.2 - analysisSummary rendering removed */}
        {/* TODO: Re-enable after Phase 1.3 (diff + fix rendering) */}
      </div>

      {/* Scroll Navigation Buttons */}
      <div className="navi-scroll-nav">
        {showScrollTop && (
          <button
            type="button"
            className="navi-scroll-nav-btn navi-scroll-nav-btn--top"
            onClick={scrollToTop}
            aria-label="Scroll to top"
            title="Scroll to top"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
        {showScrollBottom && (
          <button
            type="button"
            className="navi-scroll-nav-btn navi-scroll-nav-btn--bottom"
            onClick={scrollToBottom}
            aria-label="Scroll to bottom"
            title="Scroll to bottom"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="navi-chat-footer">
        {/* Hide QuickActionsBar when we have specific next steps from the response */}
        {lastNextSteps.length === 0 && (
          <QuickActionsBar
            className="navi-chat-footer-actions"
            disabled={sending}
            onQuickPrompt={handleQuickPrompt}
            actions={quickActions}
          />
        )}

        {selectedModelId === AUTO_MODEL_ID && useAutoModel && lastRouterInfo?.source === "auto" && sending && (
          <div className="navi-chat-model-banner">
            <div className="navi-chat-model-banner-info">
              <Cpu className="navi-icon-3d" />
              <span className="navi-chat-model-banner-text">
                {lastRouterInfo.mode && (
                  <>
                    <span className="navi-chat-model-banner-mode">
                      {lastRouterInfo.mode === "chat" ? "Chat" : lastRouterInfo.mode === "agent-full-access" ? "Agent (Full)" : "Agent"}
                    </span>
                    <span className="navi-chat-model-banner-muted"> | </span>
                  </>
                )}
                <span className="navi-chat-model-banner-strong">
                  {formatTaskLabel(lastRouterInfo.taskType || "conversation")}
                </span>
                <span className="navi-chat-model-banner-muted"> → </span>
                <span className="navi-chat-model-banner-strong">
                  {resolvedRouterName || lastRouterInfo.modelName || selectedModelName}
                </span>
              </span>
            </div>
            <button
              type="button"
              className="navi-chat-model-banner-action"
              onClick={() => applyModelSelection(lastManualModelId)}
            >
              Override
            </button>
          </div>
        )}

        {selectedModelId !== AUTO_MODEL_ID && (
          <div className="navi-chat-model-banner navi-chat-model-banner--manual">
            <div className="navi-chat-model-banner-info">
              <Cpu className="navi-icon-3d" />
              <span className="navi-chat-model-banner-text">
                Manual model:{" "}
                <span className="navi-chat-model-banner-strong">
                  {selectedModelName}
                </span>
              </span>
            </div>
            <button
              type="button"
              className="navi-chat-model-banner-action"
              onClick={() => applyModelSelection(AUTO_MODEL_ID)}
            >
              Use Auto
            </button>
          </div>
        )}

        {hasChangeSummary && changeSummary && (
          <FileChangeSummary
            files={changeSummary.files.map((file) => ({
              path: toWorkspaceRelativePath(file.path),
              additions: file.additions,
              deletions: file.deletions,
            }))}
            totalAdditions={changeTotals?.additions}
            totalDeletions={changeTotals?.deletions}
            onKeep={handleKeepChanges}
            onUndo={handleUndoChanges}
            onFileClick={handleOpenSummaryDiff}
          />
        )}

        <AttachmentChips
          attachments={attachments}
          onRemove={handleRemoveAttachment}
        />

        {/* Execution Plan Stepper - Positioned ABOVE input bar for visibility */}
        {/* Shows task steps with real-time status during streaming */}
        {executionPlan && executionPlan.steps.length > 0 && (
          <div className="navi-plan-stepper-floating">
            <ExecutionPlanStepper
              planId={executionPlan.planId}
              steps={executionPlan.steps}
              isExecuting={executionPlan.isExecuting}
            />
          </div>
        )}

        <div className="navi-chat-input-row">
          <AttachmentToolbar className="navi-chat-input-tools" />

          {/* Slash Command Menu */}
          {showSlashMenu && filteredSlashCommands.length > 0 && (
            <div
              ref={slashMenuRef}
              className="navi-slash-menu"
            >
              <div className="navi-slash-menu-header">
                <span className="navi-slash-menu-title">Commands</span>
                <span className="navi-slash-menu-hint">Type to filter</span>
              </div>
              <div className="navi-slash-menu-list">
                {filteredSlashCommands.map((cmd, index) => (
                  <button
                    key={cmd.command}
                    type="button"
                    className={`navi-slash-menu-item ${index === selectedSlashIndex ? 'is-selected' : ''}`}
                    onClick={() => {
                      // Handle /help specially
                      if (cmd.command === '/help') {
                        setInput('');
                        setShowSlashMenu(false);
                        setSlashFilter('');
                        // Show help message
                        const helpText = "Available commands:\n" +
                          SLASH_COMMANDS.map(c => `${c.icon} ${c.command} - ${c.description}`).join('\n');
                        // Add as a system message
                        setMessages(prev => [...prev, {
                          id: `help-${Date.now()}`,
                          role: 'assistant',
                          content: `**NAVI Commands**\n\nHere are the available slash commands:\n\n${SLASH_COMMANDS.map(c => `- \`${c.command}\` ${c.icon} - ${c.description}`).join('\n')}\n\nType \`/\` to see this menu anytime!`,
                          createdAt: new Date().toISOString(),
                        }]);
                      } else {
                        // Insert the command prompt
                        setInput(cmd.prompt || cmd.command + ' ');
                        setShowSlashMenu(false);
                        setSlashFilter('');
                        setTimeout(() => inputRef.current?.focus(), 10);
                      }
                    }}
                    onMouseEnter={() => setSelectedSlashIndex(index)}
                  >
                    <span className="navi-slash-menu-icon">{cmd.icon}</span>
                    <div className="navi-slash-menu-content">
                      <span className="navi-slash-menu-command">{cmd.command}</span>
                      <span className="navi-slash-menu-desc">{cmd.description}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <input
            ref={inputRef}
            className="navi-chat-input navi-chat-input--animated-placeholder"
            placeholder={input ? "Ask NAVI..." : NAVI_SUGGESTIONS[placeholderIndex]}
            value={input}
            onChange={(e) => {
              const newValue = e.target.value;
              setInput(newValue);

              // Check for slash command trigger
              if (newValue === '/') {
                setShowSlashMenu(true);
                setSlashFilter('');
                setSelectedSlashIndex(0);
              } else if (newValue.startsWith('/') && !newValue.includes(' ')) {
                setShowSlashMenu(true);
                setSlashFilter(newValue.slice(1)); // Remove the / prefix for filtering
                setSelectedSlashIndex(0);
              } else {
                setShowSlashMenu(false);
                setSlashFilter('');
              }

              // Reset history navigation when typing
              if (historyIndex !== -1) {
                setHistoryIndex(-1);
                setTempInput('');
              }
            }}
            onKeyDown={(e) => {
              // Handle slash menu keyboard navigation
              if (showSlashMenu && filteredSlashCommands.length > 0) {
                if (e.key === 'ArrowDown') {
                  e.preventDefault();
                  setSelectedSlashIndex(prev =>
                    prev < filteredSlashCommands.length - 1 ? prev + 1 : 0
                  );
                  return;
                }
                if (e.key === 'ArrowUp') {
                  e.preventDefault();
                  setSelectedSlashIndex(prev =>
                    prev > 0 ? prev - 1 : filteredSlashCommands.length - 1
                  );
                  return;
                }
                if (e.key === 'Enter' || e.key === 'Tab') {
                  e.preventDefault();
                  const selectedCmd = filteredSlashCommands[selectedSlashIndex];
                  if (selectedCmd) {
                    if (selectedCmd.command === '/help') {
                      setInput('');
                      setShowSlashMenu(false);
                      setSlashFilter('');
                      setMessages(prev => [...prev, {
                        id: `help-${Date.now()}`,
                        role: 'assistant',
                        content: `**NAVI Commands**\n\nHere are the available slash commands:\n\n${SLASH_COMMANDS.map(c => `- \`${c.command}\` ${c.icon} - ${c.description}`).join('\n')}\n\nType \`/\` to see this menu anytime!`,
                        createdAt: new Date().toISOString(),
                      }]);
                    } else {
                      setInput(selectedCmd.prompt || selectedCmd.command + ' ');
                      setShowSlashMenu(false);
                      setSlashFilter('');
                    }
                  }
                  return;
                }
                if (e.key === 'Escape') {
                  e.preventDefault();
                  setShowSlashMenu(false);
                  setSlashFilter('');
                  setInput('');
                  return;
                }
              }
              // Default keyboard handling
              handleKeyDown(e);
            }}
            onPaste={handlePaste}
            onBlur={() => {
              // Delay hiding to allow click on menu items
              setTimeout(() => setShowSlashMenu(false), 200);
            }}
            data-testid="chat-input"
          />

          {sending ? (
            /* Stop/Cancel button when request is in progress */
            <button
              type="button"
              className="navi-chat-send-btn navi-chat-send-btn--stop"
              onClick={handleCancelRequest}
              data-testid="stop-btn"
              aria-label="Stop request"
            >
              {/* Modern stop icon - square with rounded corners */}
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="currentColor"
                stroke="none"
              >
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            </button>
          ) : (
            /* Send button when idle */
            <button
              type="button"
              className={`navi-chat-send-btn ${input.trim() ? 'has-input' : ''}`}
              onClick={() => void handleSend()}
              disabled={!input.trim()}
              data-testid="send-btn"
              aria-label="Send message"
            >
              {/* Modern sleek arrow icon */}
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </button>
          )}
        </div>

        <div className="navi-chat-mode-row">
          <select
            className="navi-chat-mode-select"
            value={chatMode}
            onChange={(e) => applyModeSelection(e.target.value as ChatMode)}
          >
            {(Object.keys(CHAT_MODE_LABELS) as ChatMode[]).map((key) => (
              <option key={key} value={key}>
                {CHAT_MODE_LABELS[key]}
              </option>
            ))}
          </select>

          <select
            className="navi-chat-mode-select"
            value={selectedModelId}
            onChange={(e) => applyModelSelection(e.target.value)}
          >
            {LLM_PROVIDERS.map((provider) => (
              <optgroup key={provider.id} label={provider.name}>
                {provider.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>

          <div className="navi-branch-dropdown-container">
            <button
              type="button"
              className="navi-chat-mode-pill navi-chat-mode-pill--branch"
              title={`Branch: ${currentBranch || repoName || "this repo"}`}
              onClick={handleBranchDropdownToggle}
            >
              <GitBranch className="navi-branch-icon" size={14} />
              <span className="navi-branch-name">{currentBranch || repoName || "this repo"}</span>
              <ChevronDown className={`navi-branch-chevron ${branchDropdownOpen ? "is-open" : ""}`} size={12} />
            </button>

            {branchDropdownOpen && (
              <>
                <div
                  className="navi-branch-dropdown-backdrop"
                  onClick={() => setBranchDropdownOpen(false)}
                />
                <div className="navi-branch-dropdown">
                  <div className="navi-branch-dropdown-header">
                    <span className="navi-branch-dropdown-title">Branches</span>
                    <button
                      type="button"
                      className="navi-branch-dropdown-close"
                      onClick={() => setBranchDropdownOpen(false)}
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <div className="navi-branch-dropdown-list">
                    {branchesLoading ? (
                      <div className="navi-branch-dropdown-loading">
                        Loading branches...
                      </div>
                    ) : branches.length > 0 ? (
                      branches.map((branch) => (
                        <button
                          key={branch}
                          type="button"
                          className={`navi-branch-dropdown-item ${branch === currentBranch ? "is-current" : ""}`}
                          onClick={() => handleBranchSelect(branch)}
                        >
                          <GitBranch size={12} />
                          <span className="navi-branch-dropdown-item-name">{branch}</span>
                          {branch === currentBranch && (
                            <CheckCircle2 className="navi-branch-dropdown-item-check" size={12} />
                          )}
                        </button>
                      ))
                    ) : (
                      <div className="navi-branch-dropdown-empty">
                        No branches found
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="navi-chat-model-tag">
            {routerBadgeLabel}
          </div>
        </div>

      </div>

      {/* Inline toast */}
      {toast && (
        <div className={`navi-toast navi-toast--${toast.kind}`}>
          {toast.message}
        </div>
      )}

      {/* Phase 2.1.2: Alternative Selection Modal */}
      {alternativeModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-blue-500/30 rounded-lg shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="sticky top-0 bg-gray-900 border-b border-blue-500/30 px-4 py-3 flex justify-between items-center">
              <div className="navi-section-title navi-section-title--modal">
                <Search className="navi-icon-3d" />
                Choose Fix Alternative
              </div>
              <button
                onClick={() => setAlternativeModal(null)}
                className="navi-modal-close navi-icon-button"
                aria-label="Close alternatives"
                title="Close"
              >
                <X className="h-4 w-4 navi-icon-3d" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <p className="text-xs text-gray-400 mb-4">
                Multiple fixes are possible for this issue. Select the one that best fits your intent.
              </p>
              {alternativeModal.alternatives.map((alt, index) => (
                <div
                  key={alt.id}
                  className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 hover:border-blue-500/50 transition cursor-pointer"
                  onClick={() => {
                    console.log(`[NaviUI] Alternative ${index} selected for ${alternativeModal.proposalId}`);
                    vscodeApi.postMessage({
                      type: 'navi.fix.apply',
                      proposalId: alternativeModal.proposalId,
                      selectedAlternativeIndex: index
                    });
                    const newState = new Map(approvalState);
                    newState.set(alternativeModal.proposalId, 'approved');
                    setApprovalState(newState);
                    setAlternativeModal(null);
                  }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="text-sm font-medium text-gray-200">
                      {alt.issue}
                    </div>
                    <div className="flex gap-2 ml-2">
                      <span className={`text-xs px-2 py-0.5 rounded ${alt.riskLevel === 'low' ? 'bg-green-900/50 text-green-300' :
                        alt.riskLevel === 'medium' ? 'bg-yellow-900/50 text-yellow-300' :
                          'bg-red-900/50 text-red-300'
                        }`}>
                        {alt.riskLevel === 'low' ? 'Low risk' : alt.riskLevel === 'medium' ? 'Medium risk' : 'High risk'}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${alt.confidence === 'high' ? 'bg-green-900/50 text-green-300' :
                        alt.confidence === 'medium' ? 'bg-yellow-900/50 text-yellow-300' :
                          'bg-gray-700 text-gray-300'
                        }`}>
                        {alt.confidence} confidence
                      </span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 mb-2">
                    {alt.suggestedChange}
                  </div>
                  {alt.replacementText && (
                    <div className="mt-2 p-2 bg-gray-900 border border-gray-700 rounded">
                      <div className="text-xs text-gray-500 mb-1">Preview:</div>
                      <pre className="text-xs text-green-400 font-mono overflow-x-auto whitespace-pre-wrap">
                        {alt.replacementText.substring(0, 200)}{alt.replacementText.length > 200 ? '...' : ''}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="sticky bottom-0 bg-gray-900 border-t border-blue-500/30 px-4 py-3">
              <button
                onClick={() => setAlternativeModal(null)}
                className="w-full px-4 py-2 bg-gray-700 text-gray-200 hover:bg-gray-600 rounded transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modern Toast Notifications - Temporarily disabled */}
      {/* <Toaster /> */}
    </div>
  );
}

/* ---------- Diff Viewer Component ---------- */

interface DiffViewerProps {
  review: StructuredReview;
  onAutoFix: (fileName: string, issue: any) => void;
}

function VisualDiffViewer({ review, onAutoFix }: DiffViewerProps) {
  const [openFiles, setOpenFiles] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Trigger PrismJS highlighting after component mounts/updates
    setTimeout(() => {
      Prism.highlightAll();
    }, 100);
  }, [review, openFiles]);

  const toggleFile = (path: string) => {
    setOpenFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  };

  return (
    <div className="p-2 space-y-2">
      <div className="flex justify-between items-center mb-3">
        <div className="navi-section-title">
          <Search className="navi-icon-3d" />
          Visual diff viewer
        </div>
        <div className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded-full text-xs border border-purple-500/30">
          {review.files.length} files
        </div>
      </div>

      {review.files.map((file, fileIndex) => {
        const isOpen = openFiles.has(file.path);

        return (
          <div key={fileIndex} className="border border-gray-800 rounded-lg bg-gray-950">
            <div
              className="flex justify-between items-center p-2 cursor-pointer hover:bg-gray-900/50 rounded-t-lg"
              onClick={() => toggleFile(file.path)}
            >
              <div className="flex items-center space-x-2">
                <span className="navi-collapse-icon">
                  {isOpen ? (
                    <ChevronDown className="h-3.5 w-3.5 navi-icon-3d" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 navi-icon-3d" />
                  )}
                </span>
                <span className="font-mono text-xs text-gray-300 truncate flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 navi-icon-3d" />
                  {file.path}
                </span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded text-xs border border-gray-700">
                  {file.issues?.length || 0}
                </div>
              </div>
            </div>            {isOpen && (
              <div className="border-t border-gray-800 p-2">
                {/* Real diff display */}
                {file.diff ? (
                  <div className="bg-gray-900/50 rounded border border-gray-700 overflow-hidden">
                    <div className="bg-gray-800 px-2 py-1 text-xs text-gray-400 border-b border-gray-700">
                      Changes in {file.path}
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                      <pre className="font-mono text-xs leading-tight p-2 text-gray-300">
                        <code className="language-diff">{file.diff}</code>
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="bg-gray-900/50 rounded border border-gray-700 p-2 text-center">
                    <div className="text-gray-400 text-xs">
                      {file.path} - No diff available
                    </div>
                    <div className="text-gray-500 text-xs mt-1">
                      File may be newly added or binary
                    </div>
                  </div>
                )}

                {/* Issues for this file */}
                <div className="mt-2 space-y-2">
                  {(file.issues || []).map((issue, issueIndex) => (
                    <div key={issueIndex} className="bg-gray-900/30 rounded p-2 border border-gray-800">
                      <div className="flex justify-between items-start mb-1">
                        <div className="text-xs font-semibold text-gray-200">
                          {issue.title || "Issue found"}
                        </div>
                        {issue.canAutoFix && (
                          <div className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-xs border border-green-500/30">
                            <Wrench className="h-3.5 w-3.5 navi-icon-3d" />
                          </div>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mb-2">
                        <span className="inline-flex items-center gap-2">
                          <Lightbulb className="h-3.5 w-3.5 navi-icon-3d" />
                          {issue.body || "No description available"}
                        </span>
                      </div>
                      <button
                        className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 ${issue.canAutoFix
                          ? 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white'
                          : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                          }`}
                        onClick={() => onAutoFix(file.path, issue)}
                        disabled={!issue.canAutoFix}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Sparkles className="h-3.5 w-3.5 navi-icon-3d" />
                          Auto-fix
                        </span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Structured Review Component ---------- */

interface StructuredReviewComponentProps {
  review: StructuredReview;
  onAutoFix: (fileName: string, issue: any) => void;
}

function StructuredReviewComponent({ review, onAutoFix }: StructuredReviewComponentProps) {
  const [collapsedFiles, setCollapsedFiles] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Trigger PrismJS highlighting after component mounts/updates
    setTimeout(() => {
      Prism.highlightAll();
    }, 100);
  }, [review]);

  const toggleFileCollapse = (filePath: string) => {
    setCollapsedFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(filePath)) {
        newSet.delete(filePath);
      } else {
        newSet.add(filePath);
      }
      return newSet;
    });
  };

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case "high": return "bg-red-500/20 text-red-400 border-red-500/30";
      case "medium": return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      case "low": return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      default: return "bg-gray-500/20 text-gray-400 border-gray-500/30";
    }
  };

  const getSeverityLabel = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case "high": return "High";
      case "medium": return "Medium";
      case "low": return "Low";
      default: return "Note";
    }
  };

  const renderSeverityIcon = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case "high":
        return <AlertTriangle className="h-3.5 w-3.5 navi-icon-3d" />;
      case "medium":
        return <Info className="h-3.5 w-3.5 navi-icon-3d" />;
      case "low":
        return <CheckCircle2 className="h-3.5 w-3.5 navi-icon-3d" />;
      default:
        return <Info className="h-3.5 w-3.5 navi-icon-3d" />;
    }
  };

  return (
    <div className="p-2 space-y-2">
      <div className="flex justify-between items-center mb-3">
        <div className="navi-section-title">
          <ClipboardList className="navi-icon-3d" />
          Code review results
        </div>
        <div
          className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded-full text-xs border border-blue-500/30"
          data-testid="files-analyzed"
        >
          {review.files.length} files
        </div>
      </div>

      {review.files.map((file, fileIndex) => {
        const isCollapsed = collapsedFiles.has(file.path);

        return (
          <div key={fileIndex} className="border border-gray-800 rounded-lg bg-gray-950">
            <div
              className="flex justify-between items-center p-2 cursor-pointer hover:bg-gray-900/50 rounded-t-lg"
              onClick={() => toggleFileCollapse(file.path)}
            >
              <div className="flex items-center space-x-2">
                <span className="navi-collapse-icon">
                  {isCollapsed ? (
                    <ChevronRight className="h-3.5 w-3.5 navi-icon-3d" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 navi-icon-3d" />
                  )}
                </span>
                <span className="font-mono text-xs text-gray-300 truncate flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 navi-icon-3d" />
                  {file.path || "Unknown file"}
                </span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded text-xs border border-gray-700">
                  {file.issues?.length || 0}
                </div>
                {file.severity && (
                  <div className={`px-1.5 py-0.5 rounded text-xs border inline-flex items-center gap-1 ${getSeverityBadgeClass(file.severity)}`}>
                    {renderSeverityIcon(file.severity)}
                    <span>{getSeverityLabel(file.severity)}</span>
                  </div>
                )}
              </div>
            </div>            {!isCollapsed && (
              <div className="border-t border-gray-800">
                {(file.issues || []).map((issue, issueIndex) => (
                  <div key={issueIndex} className="p-2 border-b border-gray-800 last:border-b-0 bg-gray-900/30">
                    <div className="flex justify-between items-start mb-1.5">
                      <div className="flex-1">
                        {issue.title && (
                          <div className="text-xs font-semibold text-gray-200 mb-1">
                            {issue.title}
                          </div>
                        )}
                        <div className="text-xs text-gray-400 whitespace-pre-wrap leading-tight">
                          {issue.body || issue.title || "No description available"}
                        </div>
                      </div>
                      {issue.canAutoFix && (
                        <div className="ml-2 px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-xs border border-green-500/30">
                          <Wrench className="h-3.5 w-3.5 navi-icon-3d" />
                        </div>
                      )}
                    </div>

                    <div className="flex justify-end mt-2">
                      <button
                        className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 ${issue.canAutoFix
                          ? 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white'
                          : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                          }`}
                        onClick={() => onAutoFix(file.path, issue)}
                        disabled={!issue.canAutoFix}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Sparkles className="h-3.5 w-3.5 navi-icon-3d" />
                          Auto-fix
                        </span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
