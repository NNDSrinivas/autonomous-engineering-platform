// frontend/src/components/navi/NaviChatPanel.tsx
"use client";

import {
  ClipboardEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { resolveBackendBase } from "../../api/navi/client";
import { ORG, USER_ID } from "../../api/client";
import {
  clearSessionDraft,
  clearSessionMessages,
  createSession,
  ensureActiveSession,
  getActiveSessionId,
  getSession,
  loadSessionDraft,
  loadSessionMessages,
  saveSessionDraft,
  saveSessionMessages,
  setActiveSessionId as persistActiveSessionId,
  updateSession,
} from "../../utils/chatSessions";
import { QuickActionsBar } from "./QuickActionsBar";
import { AttachmentToolbar } from "./AttachmentToolbar";
import {
  AttachmentChips,
  AttachmentChipData,
} from "./AttachmentChips";
import * as vscodeApi from "../../utils/vscodeApi";
import "./NaviChatPanel.css";
import Prism from 'prismjs';
// import * as Diff from 'diff';
// Temporarily commenting out components with missing dependencies
// import { LiveProgressDiagnostics } from '../ui/LiveProgressDiagnostics';
// import { Toaster } from '../ui/toaster';
import EnhancedLiveReview from '../ui/EnhancedLiveReview';

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
}

type ExecutionMode = "plan_propose" | "plan_and_run";
type ScopeMode = "this_repo" | "current_file" | "service";
type ProviderId = "openai_navra" | "openai_byok" | "anthropic_byok";

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
  plan_propose: "Plan + propose",
  plan_and_run: "Plan + run",
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

interface NaviAction {
  id?: string;
  title?: string;
  description?: string;
  intent_kind?: string;
  context?: Record<string, unknown>;
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
}

/* ---------- Utils ---------- */

const makeMessageId = (role: ChatRole): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${role}-${(crypto as any).randomUUID()}`;
  }
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

const nowIso = () => new Date().toISOString();

const formatTime = (iso?: string): string => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const MAX_SESSION_MESSAGES = 200;

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
  return `${trimmed.slice(0, max - 1)}…`;
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
          <span className="text-xs">📄</span>
          <span className="text-xs font-mono text-gray-300">{fileDiff.path}</span>
          <span className={`text-xs px-1 rounded ${fileDiff.scope === 'staged' ? 'bg-green-900/30 text-green-400' : 'bg-yellow-900/30 text-yellow-400'}`}>
            {fileDiff.scope}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-green-400">+{fileDiff.additions}</span>
          <span className="text-xs text-red-400">−{fileDiff.deletions}</span>
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

export default function NaviChatPanel() {
  const { workspaceRoot, repoName, isLoading } = useWorkspace();

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AttachmentChipData[]>([]);
  const [sending, setSending] = useState(false);
  const [sendTimedOut, setSendTimedOut] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "error">("checking");
  const [backendError, setBackendError] = useState<string>("");
  const [coverageGate, setCoverageGate] = useState<CoverageGateState | null>(null);

  const [executionMode, setExecutionMode] =
    useState<ExecutionMode>("plan_propose");
  const [scope, setScope] = useState<ScopeMode>("this_repo");
  const [provider, setProvider] = useState<ProviderId>("openai_navra");

  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const sendTimeoutRef = useRef<number | null>(null);
  const lastSentRef = useRef<string>("");
  const lastAttachmentsRef = useRef<AttachmentChipData[]>([]);
  const sentViaExtensionRef = useRef(false);
  const pendingResetRef = useRef(false);
  const resetTimeoutRef = useRef<number | null>(null);
  const analysisAbortRef = useRef<AbortController | null>(null);
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
        meta?: {
          kind?: string;
          threshold?: number;
          [key: string]: any;
        };
        coverageReported?: boolean;
      }
    >()
  );

  const [toast, setToast] = useState<ToastState | null>(null);
  const [structuredReview, setStructuredReview] = useState<StructuredReview | null>(null);
  const [reviewViewMode, setReviewViewMode] = useState<"issues" | "diffs" | "live">("issues");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState<string[]>([]);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [analysisSummary, setAnalysisSummary] = useState<{
    total_files: number;
    detailed_files: number;
    skipped_files: number;
    highlights: string[];
  } | null>(null);

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

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
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
        }));
      setMessages(normalized);
      setInput(loadSessionDraft(activeSessionId));
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
        const res = await fetch(`${backendBase}/api/navi/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Org-Id": ORG,
          },
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

  // Allow native copy/paste; only mirror to VS Code clipboard when available
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

    const copyHandler = () => {
      if (!vscodeApi.hasVsCodeHost()) return;
      let selection = window.getSelection()?.toString() ?? "";
      if (!selection.trim()) {
        selection = getActiveInputSelection();
      }
      if (!selection.trim()) return;
      vscodeApi.writeClipboard(selection).catch(() => {
        // ignore; native copy already happened
      });
    };
    window.addEventListener("copy", copyHandler as any);
    return () => {
      window.removeEventListener("copy", copyHandler as any);
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
        summary = `Coverage: ${coverage.toFixed(1)}% (target ${threshold}%) — ${status}`;
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

    return vscodeApi.onMessage((msg) => {
      if (!msg || typeof msg !== "object") return;

      // NEW: inline toast from extension
      if (msg.type === 'toast' && msg.message) {
        showToast(msg.message, msg.kind || 'info');
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

      if (msg.type === "botMessage" && msg.text) {
        const assistantMessage: ChatMessage = {
          id: makeMessageId("assistant"),
          role: "assistant",
          content: msg.text,
          createdAt: nowIso(),
          actions: Array.isArray(msg.actions) ? msg.actions : undefined,
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setSending(false);
        clearSendTimeout();
      }

      if (msg.type === "botThinking") {
        setSending(msg.value === true);
        if (msg.value === false) {
          clearSendTimeout();
        }
      }

      if (msg.type === "command.start" && msg.commandId && msg.command) {
        const messageId = makeMessageId("system");
        const command = String(msg.command);
        const cwd = typeof msg.cwd === "string" ? msg.cwd : undefined;
        const meta =
          msg.meta && typeof msg.meta === "object" ? msg.meta : undefined;
        const entry = {
          messageId,
          command,
          cwd,
          output: "",
          truncated: false,
          status: "running" as const,
          meta,
        };
        commandStateRef.current.set(msg.commandId, entry);
        const content = buildCommandMessage({
          command,
          cwd,
          output: "",
          status: "running",
          meta,
        });
        setMessages((prev) => [
          ...prev,
          {
            id: messageId,
            role: "system",
            content,
            createdAt: nowIso(),
            meta: { kind: "command", commandId: String(msg.commandId) },
          },
        ]);
        return;
      }

      if (msg.type === "command.output" && msg.commandId && msg.text) {
        const entry = commandStateRef.current.get(msg.commandId);
        if (!entry) return;
        const next = appendWithLimit(entry.output, String(msg.text), MAX_COMMAND_OUTPUT);
        entry.output = next.text;
        entry.truncated = entry.truncated || next.truncated;
        const content = buildCommandMessage({
          command: entry.command,
          cwd: entry.cwd,
          output: entry.output,
          status: entry.status,
          exitCode: entry.exitCode,
          durationMs: entry.durationMs,
          truncated: entry.truncated,
          meta: entry.meta,
        });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === entry.messageId ? { ...m, content } : m
          )
        );
        return;
      }

      if (msg.type === "command.done" && msg.commandId) {
        const entry = commandStateRef.current.get(msg.commandId);
        if (!entry) return;
        entry.status = "done";
        entry.exitCode =
          typeof msg.exitCode === "number" ? msg.exitCode : entry.exitCode;
        entry.durationMs =
          typeof msg.durationMs === "number" ? msg.durationMs : entry.durationMs;
        const content = buildCommandMessage({
          command: entry.command,
          cwd: entry.cwd,
          output: entry.output,
          status: entry.status,
          exitCode: entry.exitCode,
          durationMs: entry.durationMs,
          truncated: entry.truncated,
          meta: entry.meta,
        });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === entry.messageId ? { ...m, content } : m
          )
        );
        reportCoverageIfNeeded(entry);
        commandStateRef.current.delete(msg.commandId);
        return;
      }

      if (msg.type === "command.error" && msg.commandId) {
        const entry = commandStateRef.current.get(msg.commandId);
        if (!entry) return;
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
        commandStateRef.current.delete(msg.commandId);
        return;
      }

      if (msg.type === "error") {
        const errorText =
          msg.error ||
          msg.message ||
          msg.text ||
          "Navi hit an error while processing your request.";

        const errorMessage: ChatMessage = {
          id: makeMessageId("system"),
          role: "system",
          content: `⚠️ ${errorText}`,
          createdAt: nowIso(),
        };

        setMessages((prev) => [...prev, errorMessage]);
        setSending(false);
        clearSendTimeout();
        showToast(errorText, "error");
        return;
      }

      // Handle NAVI agent events forwarded from the VS Code extension
      if (msg.type === 'navi.agent.event' && msg.event) {
        const evt = msg.event;
        const kind = evt.type || evt.kind;
        const data = evt.data || {};

        // Lazy start analysis UI if not active yet
        if (!isAnalyzing && (kind === 'liveProgress' || kind === 'reviewEntry')) {
          setIsAnalyzing(true);
          setAnalysisProgress([]);
          setCurrentProgress(0);
          setStructuredReview(null);
          setAnalysisSummary(null);
          // Ensure user sees the live stream immediately
          setReviewViewMode('live');
        }

        if (kind === 'liveProgress') {
          const step: string = data.step || 'Processing...';
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
          const listed = Array.isArray(data.listedFiles) ? data.listedFiles.length : undefined;
          const severities = data.severityCounts || {};
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

          setAnalysisSummary({
            total_files: total,
            detailed_files: listed ?? total,
            skipped_files: listed ? Math.max(0, total - listed) : 0,
            highlights: summaryHighlights,
          });
          return;
        }

        if (kind === 'done') {
          setIsAnalyzing(false);
          setCurrentProgress((prev) => Math.max(prev, 100));
          // If no summary arrived, synthesize a minimal one so completion is visible
          setAnalysisSummary((prev) => {
            if (prev) return prev;
            const filesLen = (structuredReview?.files?.length ?? 0);
            const highlights = filesLen > 0
              ? [`${filesLen} files analyzed${filesLen ? '' : ''}`]
              : ['No high-risk issues detected.'];
            return {
              total_files: filesLen,
              detailed_files: filesLen,
              skipped_files: 0,
              highlights,
            };
          });
          showToast('Analysis complete.', 'info');
          return;
        }

        if (kind === 'error') {
          const message = data?.message || 'Agent reported an error';
          setIsAnalyzing(false);
          showToast(`❌ ${message}`, 'error');
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
          return;
        }

        // NEW (Phase 1.3): Handle individual file diff details
        if (kind === 'repo.diff.detail') {
          const { path, additions, deletions, diff, scope } = data;
          setDiffDetails(prev => [...prev, {
            path,
            additions: additions || 0,
            deletions: deletions || 0,
            diff: diff || '',
            scope: scope || 'unstaged'
          }]);
          console.log('[NaviChatPanel] 📄 Received diff for:', path, `+${additions} -${deletions}`);
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

        // NEW (Phase 1.5): Detailed diagnostics by file
        if (kind === 'navi.diagnostics.detailed') {
          const files = Array.isArray(data.files) ? data.files : [];
          setDetailedDiagnostics(files);
          console.log('[NaviChatPanel] 📊 Detailed diagnostics received:', files.length, 'files');
          return;
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
          console.warn('[NaviChatPanel] ⚠️ Failed to parse review data:', err);
        }
      }
    });
  }, []);

  /* ---------- direct backend call (fallback) ---------- */

  const sendNaviChatRequest = async (
    message: string,
    attachmentsOverride?: AttachmentChipData[]
  ): Promise<NaviChatResponse> => {
    const { effectiveRoot } = getEffectiveWorkspace();

    if (!effectiveRoot) {
      vscodeApi.postMessage({ type: "getWorkspaceRoot" });
    }

    const workspaceRootToSend = effectiveRoot;

    const conversationHistory = messages.slice(-10).map((msg) => ({
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
      mode: "concierge",
      execution: executionMode,
      scope,
      provider,
      conversationHistory,
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
      headers: {
        "Content-Type": "application/json",
        "X-Org-Id": ORG,
      },
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
      const title = action?.title || action?.intent_kind || "Planned action";
      const desc =
        action?.description ||
        "Navi has prepared a plan. Use the file changes panel on the right to review edits.";
      return `Plan: **${title}**\n\n${desc}`;
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

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text) return;

    const lower = text.toLowerCase();
    const isReviewish = /review|audit|changes|working tree|diff|analy(s|z)e/.test(lower);
    if (isReviewish) {
      startRealTimeAnalysis();
    }

    // Track latest text for retry UX
    lastSentRef.current = text;
    lastAttachmentsRef.current = attachments;

    const userMessage: ChatMessage = {
      id: makeMessageId("user"),
      role: "user",
      content: text,
      createdAt: nowIso(),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!overrideText) setInput("");
    setSending(true);
    setSendTimedOut(false);
    sentViaExtensionRef.current = false;

    // Start client-side timeout for responsiveness
    if (sendTimeoutRef.current) {
      clearTimeout(sendTimeoutRef.current);
    }
    sendTimeoutRef.current = window.setTimeout(() => {
      setSendTimedOut(true);
      showToast("Navi is taking longer than expected. You can retry.", "warning");
    }, 20000);

    const hasVsCodeHost = vscodeApi.hasVsCodeHost();

    if (hasVsCodeHost) {
      try {
        console.log(
          "[NAVI] 🚀 ROUTING MESSAGE THROUGH VS CODE EXTENSION:",
          text
        );
        console.log("[NAVI] 📎 Including attachments:", attachments);

        vscodeApi.postMessage({
          type: "sendMessage",
          text,
          attachments,
          modelId: "default",
          modeId: "concierge",
          orgId: ORG,
          userId: USER_ID,
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
      const data = await sendNaviChatRequest(text);
      const replyText = buildAssistantReply(data, text);

      let finalReplyText = replyText;
      if (data.progress_steps && data.progress_steps.length > 0) {
        finalReplyText +=
          "\n\n**Processing Steps:**\n" +
          data.progress_steps.map((step) => `✅ ${step}`).join("\n");
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
      const data = await sendNaviChatRequest(text, lastAttachmentsRef.current);
      const replyText = buildAssistantReply(data, text);

      let finalReplyText = replyText;
      if (data.progress_steps && data.progress_steps.length > 0) {
        finalReplyText +=
          "\n\n**Processing Steps:**\n" +
          data.progress_steps.map((step) => `✅ ${step}`).join("\n");
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

  /* ---------- keyboard ---------- */

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    // Existing Enter-to-send logic
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
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
    const nativeText = e.clipboardData?.getData("text/plain") ?? "";
    if (nativeText) return;
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
    setInput(msg.content);
    setTimeout(() => inputRef.current?.focus(), 10);
  };

  const handleUndoMessage = (msg: ChatMessage) => {
    setMessages((prev) => prev.filter((m) => m.id !== msg.id));
  };

  const handleRedoMessage = (msg: ChatMessage) => {
    void handleSend(msg.content);
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

  const handleApproveAction = (actions: AgentAction[], actionIndex: number) => {
    const action = actions[actionIndex];
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
      const proceed = window.confirm(
        `Coverage gate failed (${coverageValue} vs ${thresholdValue}). Continue anyway?`
      );
      if (!proceed) {
        return;
      }
    }
    if (!vscodeApi.hasVsCodeHost()) {
      showToast("Command actions require the VS Code host.", "warning");
      return;
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

  const renderMessageContent = (msg: ChatMessage) => {
    if (msg.meta?.kind === "command") {
      return (
        <pre className="navi-chat-command-output">{msg.content}</pre>
      );
    }
    return msg.content.split("\n").map((line, idx) => (
      <p key={idx}>{line}</p>
    ));
  };

  const resetConversationState = () => {
    setMessages([]);
    setInput("");
    setAttachments([]);
    setStructuredReview(null);
    setAnalysisProgress([]);
    setAnalysisSummary(null);
    setCurrentProgress(0);
    setIsAnalyzing(false);
    setCoverageGate(null);
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
    vscodeApi.postMessage({ type: "newChat" });
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
  };

  const handleAutoFix = (fileName: string, issue: any) => {
    showToast(`Applying auto-fix for ${fileName}...`, "info");

    // Send auto-fix request to extension
    vscodeApi.postMessage({
      type: "autoFix",
      fileName,
      issue
    });

    // Simulate progress feedback
    setTimeout(() => {
      showToast(`✅ Auto-fix applied to ${fileName}`, "info");
    }, 2000);
  };

  const startRealTimeAnalysis = async () => {
    setIsAnalyzing(true);
    setAnalysisProgress([]);
    setCurrentProgress(0);
    setStructuredReview(null);
    setAnalysisSummary(null);

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
        headers: {
          'Content-Type': 'application/json',
          'X-Org-Id': ORG,
        },
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
            setAnalysisSummary({
              total_files: data.total_files ?? 0,
              detailed_files: data.detailed_files ?? 0,
              skipped_files: data.skipped_files ?? 0,
              highlights: Array.isArray(data.highlights) ? data.highlights : [],
            });
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

              const issueCount = files.reduce(
                (sum: number, file: StructuredReviewFile) => sum + (file.issues?.length || 0),
                0
              );

              const warning =
                typeof data.warning === "string" && data.warning.trim()
                  ? data.warning.trim()
                  : "";

              setStructuredReview({ files });
              setAnalysisSummary({
                total_files: files.length,
                detailed_files: files.length,
                skipped_files: 0,
                highlights: [
                  ...(warning ? [warning] : []),
                  ...(issueCount
                    ? [`${issueCount} issues detected across ${files.length} files`]
                    : ["No issues detected in changed files"]),
                ],
              });
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
      if ((error as any)?.name === "AbortError") {
        return;
      }
      setIsAnalyzing(false);
      showToast(`❌ Failed to start analysis: ${error}`, 'error');
      console.error('Analysis error:', error);
    }
  };

  /* ---------- render ---------- */

  return (
    <div className="navi-chat-root" data-testid="navi-interface">
      <header className="navi-chat-header">
        <div className="navi-chat-title">AEP: NAVI ASSISTANT</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span
            className="navi-pill"
            style={{
              background:
                backendStatus === "ok"
                  ? "rgba(34,197,94,0.15)"
                  : backendStatus === "error"
                    ? "rgba(239,68,68,0.15)"
                    : "rgba(59,130,246,0.15)",
              color:
                backendStatus === "ok"
                  ? "#22c55e"
                  : backendStatus === "error"
                    ? "#ef4444"
                    : "#3b82f6",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
            title={backendError ? `Backend error: ${backendError}` : "Backend status"}
          >
            {backendStatus === "ok" && "Backend: OK"}
            {backendStatus === "error" && "Backend: Unreachable"}
            {backendStatus === "checking" && "Backend: Checking..."}
          </span>
          <button
            type="button"
            className="navi-pill navi-pill--primary"
            onClick={handleNewChat}
          >
            New chat
          </button>
          <button
            type="button"
            className="navi-pill navi-pill--ghost"
            onClick={handleClearChat}
          >
            Clear chat
          </button>
        </div>
      </header>

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

        {messages.map((m) => {
          const actionSource = Array.isArray(m.actions) ? m.actions : [];
          const actionItems = actionSource
            .map((action, index) => ({ action, index }))
            .filter(({ action }) => action && typeof action.type === "string");

          return (
            <div
              key={m.id}
              className={`navi-chat-bubble-row navi-chat-bubble-row--${m.role}`}
            >
              <div className={`navi-chat-avatar navi-chat-avatar--${m.role}`}>
                {m.role === "user" ? "🧑‍💻" : m.role === "assistant" ? "🪐" : "!"}
              </div>
              <div
                className={`navi-chat-bubble navi-chat-bubble--${m.role}`}
                data-testid={m.role === "assistant" ? "ai-response" : undefined}
              >
                <div
                  data-testid={m.role === "assistant" ? "ai-response-text" : undefined}
                >
                  {renderMessageContent(m)}
                </div>

                {m.role === "assistant" && actionItems.length > 0 && (
                  <div className="navi-action-list">
                    {actionItems.map(({ action, index }) => (
                      <div
                        key={`${m.id}-action-${index}`}
                        className="navi-action-card"
                      >
                        <div className="navi-action-info">
                          <div className="navi-action-title">
                            {formatActionTitle(action)}
                          </div>
                          <div className="navi-action-detail">
                            {action.type === "runCommand" ? (
                              <code>{action.command || ""}</code>
                            ) : (
                              formatActionDetail(action)
                            )}
                          </div>
                        </div>
                        <div className="navi-action-buttons">
                          {action.type === "runCommand" ? (
                            <>
                              <button
                                type="button"
                                className="navi-pill navi-pill--primary navi-action-btn"
                                onClick={() =>
                                  handleApproveAction(actionSource, index)
                                }
                              >
                                Run
                              </button>
                              <button
                                type="button"
                                className="navi-pill navi-pill--ghost navi-action-btn"
                                onClick={() =>
                                  handleCopyActionCommand(action.command)
                                }
                              >
                                Copy
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              className="navi-pill navi-pill--primary navi-action-btn"
                              onClick={() =>
                                handleApproveAction(actionSource, index)
                              }
                            >
                              Apply
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Timestamp */}
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

                <div className="navi-chat-bubble-actions">
                  <button
                    type="button"
                    className="navi-icon-btn"
                    title="Copy"
                    onClick={() => handleCopyMessage(m)}
                  >
                    ⧉
                  </button>
                  {m.role === "user" && (
                    <button
                      type="button"
                      className="navi-icon-btn"
                      title="Edit"
                      onClick={() => handleEditMessage(m)}
                    >
                      ✎
                    </button>
                  )}
                  <button
                    type="button"
                    className="navi-icon-btn"
                    title="Undo (remove this message)"
                    onClick={() => handleUndoMessage(m)}
                  >
                    ↺
                  </button>
                  <button
                    type="button"
                    className="navi-icon-btn"
                    title="Redo (resend this message)"
                    onClick={() => handleRedoMessage(m)}
                  >
                    ↻
                  </button>
                </div>
              </div>
            </div>
          );
        })}

        {/* Progress indicator when NAVI is thinking */}
        {sending && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">
              🪐
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
                <div className="navi-thinking-spinner">⚡</div>
                <span
                  style={{ fontStyle: "italic", color: "#666" }}
                >{`NAVI is working on your request...`}</span>
              </div>
            </div>
          </div>
        )}

        {sendTimedOut && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">🪐</div>
            <div className="navi-chat-bubble navi-chat-bubble--assistant" style={{ border: "1px solid #f59e0b" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <span style={{ color: "#fbbf24" }}>Taking longer than expected.</span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className="navi-pill navi-pill--ghost"
                    onClick={() => lastSentRef.current && void handleSend(lastSentRef.current)}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Retry via VS Code
                  </button>
                  <button
                    type="button"
                    className="navi-pill navi-pill--primary"
                    onClick={handleDirectFallbackSend}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Send directly
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Live Progress Viewer */}
        {(isAnalyzing || analysisProgress.length > 0) && (
          <LiveProgressViewer
            steps={analysisProgress}
            currentProgress={currentProgress}
            isActive={isAnalyzing}
          />
        )}

        {/* PHASE 1.2: Minimal repo diff summary (NO defaults, ONLY real agent data) */}
        {repoSummary && (
          <div className="p-3 bg-gray-900/70 border border-gray-700 rounded-lg mt-2 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-100">📊 Working Tree Changes</h3>
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
        {diffDetails.length > 0 && (
          <div className="mt-2 space-y-2">
            <div className="text-xs font-semibold text-gray-300 mb-2">📄 File Changes</div>
            {diffDetails.map((fileDiff, idx) => (
              <DiffFileCard key={`${fileDiff.path}-${idx}`} fileDiff={fileDiff} />
            ))}
          </div>
        )}

        {/* PHASE 1.3: Navi Assessment (read-only) */}
        {assessment && (
          <div className="mt-2 space-y-2 p-3 bg-gray-900/70 border border-gray-700 rounded-lg">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-100">🧠 Navi Assessment</h3>
              <span className="text-xs text-gray-400">
                {assessment.totalDiagnostics} issue{assessment.totalDiagnostics !== 1 ? 's' : ''} ({assessment.introduced} introduced)
              </span>
            </div>
            <div className="text-xs text-gray-300 space-y-1">
              <div>• {assessment.totalDiagnostics} issues in scope</div>
              <div>• {assessment.introduced} introduced by your changes</div>
              <div>• {assessment.preExisting} pre-existing issues</div>
              <div>• {assessment.filesAffected} files affected</div>
            </div>
            <div className="text-xs text-gray-500 italic">No actions taken yet.</div>
          </div>
        )}

        {/* PHASE 1.4: Consent Card for Scope Expansion */}
        {assessment && assessment.hasGlobalIssuesOutsideChanged && scopeDecision === 'changed-files' && (
          <div className="mt-2 p-3 bg-blue-950/40 border border-blue-700/60 rounded-lg space-y-3">
            <div className="flex items-start gap-2">
              <div className="text-blue-400 text-sm mt-0.5">💭</div>
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
                className={`text-xs px-3 py-2 rounded border transition ${scopeDecision === 'changed-files'
                  ? 'bg-blue-700/60 border-blue-500 text-blue-100'
                  : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                  }`}
              >
                ✓ Review changed files only
              </button>
              <button
                onClick={() => setScopeDecision('workspace')}
                className={`text-xs px-3 py-2 rounded border transition ${scopeDecision === 'workspace'
                  ? 'bg-blue-700/60 border-blue-500 text-blue-100'
                  : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
                  }`}
              >
                🌍 Include all workspace issues
              </button>
            </div>
          </div>
        )}

        {/* PHASE 1.4: Diagnostics (Changed Files Only, or All if Workspace Scope Enabled) */}
        {diagnosticsByFile.length > 0 && scopeDecision === 'changed-files' && (
          <div className="mt-2 space-y-2 p-3 bg-gray-900/70 border border-gray-700 rounded-lg">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-100">🩺 Diagnostics (Changed Files)</h3>
              <span className="text-xs text-gray-400">
                {(() => {
                  const flat = diagnosticsByFile.flatMap(f => f.diagnostics);
                  const errors = flat.filter(d => d.severity === 0).length;
                  const warnings = flat.filter(d => d.severity === 1).length;
                  return `❌ ${errors} • ⚠️ ${warnings}`;
                })()}
              </span>
            </div>

            {diagnosticsByFile.map((f, idx) => (
              <div key={`${f.path}-${idx}`} className="border-t border-gray-700 pt-2">
                <div className="text-xs font-mono text-gray-300">{f.path}</div>
                <div className="mt-1 space-y-1">
                  {f.diagnostics.map((d, j) => (
                    <div key={j} className="text-xs text-gray-300 flex items-center gap-2">
                      <span className="inline-block w-4 text-center">
                        {d.severity === 0 ? '❌' : d.severity === 1 ? '⚠️' : 'ℹ️'}
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
            <div className="text-xs text-green-300">
              <strong>✓ Workspace Scope Enabled</strong> — Showing all {assessment.totalDiagnostics} issues ({assessment.changedFileDiagsCount} in changed files, {assessment.preExisting} pre-existing).
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
                <h3 className="text-sm font-semibold text-gray-100">📂 Diagnostics by File</h3>
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
                      <span className="text-xs text-gray-400">{isExpanded ? '▼' : '▶'}</span>
                      <span className="text-xs font-mono text-gray-300 flex-1">{fileGroup.filePath}</span>
                      <span className="text-xs text-gray-400">
                        ({fileGroup.diagnostics.length} • {errorCount > 0 ? `❌ ${errorCount}` : ''} {warningCount > 0 ? `⚠️ ${warningCount}` : ''})
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="mt-2 ml-4 space-y-1">
                        {fileGroup.diagnostics.map((diag, j) => (
                          <div key={j} className="text-xs text-gray-300 flex items-start gap-2 py-1">
                            <span className="inline-block w-4 text-center mt-0.5">
                              {diag.severity === 'error' ? '❌' : diag.severity === 'warning' ? '⚠️' : 'ℹ️'}
                            </span>
                            <div className="flex-1">
                              <div className="text-gray-200">{diag.message}</div>
                              <div className="text-gray-500 text-xs mt-0.5">
                                Line {diag.line}:{diag.character} • {diag.source} • {diag.impact === 'introduced' ? '🟢 Introduced' : '🔵 Pre-existing'}
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

        {/* LEGACY UI DISABLED FOR PHASE 1.2 - analysisSummary rendering removed */}
        {/* TODO: Re-enable after Phase 1.3 (diff + fix rendering) */}
      </div>

      {/* Quick actions */}
      <QuickActionsBar
        className="mb-2"
        disabled={sending}
        onQuickPrompt={handleQuickPrompt}
      />

      {/* Attachment tools + chips */}
      <AttachmentToolbar className="mb-1" />
      <AttachmentChips
        attachments={attachments}
        onRemove={handleRemoveAttachment}
      />

      {/* Input row */}
      <div className="navi-chat-input-row">
        <input
          ref={inputRef}
          className="navi-chat-input"
          placeholder={`Ask Navi: e.g. "check errors and fix them"`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          data-testid="chat-input"
        />

        <button
          type="button"
          className="navi-pill navi-pill--primary navi-chat-send-btn"
          onClick={() => void handleSend()}
          disabled={!input.trim()}
          data-testid="send-btn"
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>

      {/* Mode row */}
      <div className="navi-chat-mode-row">
        <select
          className="navi-chat-mode-select navi-pill"
          value={executionMode}
          onChange={(e) =>
            setExecutionMode(e.target.value as ExecutionMode)
          }
        >
          {(Object.keys(EXECUTION_LABELS) as ExecutionMode[]).map(
            (key) => (
              <option key={key} value={key}>
                {EXECUTION_LABELS[key]}
              </option>
            )
          )}
        </select>

        <select
          className="navi-chat-mode-select navi-pill"
          value={scope}
          onChange={(e) => setScope(e.target.value as ScopeMode)}
        >
          {(Object.keys(SCOPE_LABELS) as ScopeMode[]).map((key) => (
            <option key={key} value={key}>
              {SCOPE_LABELS[key]}
            </option>
          ))}
        </select>

        <select
          className="navi-chat-mode-select navi-pill"
          value={provider}
          onChange={(e) => setProvider(e.target.value as ProviderId)}
        >
          {(Object.keys(PROVIDER_LABELS) as ProviderId[]).map(
            (key) => (
              <option key={key} value={key}>
                {PROVIDER_LABELS[key]}
              </option>
            )
          )}
        </select>
      </div>

      {/* Inline toast */}
      {toast && (
        <div className={`navi-toast navi-toast--${toast.kind}`}>
          {toast.message}
        </div>
      )}

      {/* Modern Toast Notifications - Temporarily disabled */}
      {/* <Toaster /> */}
    </div>
  );
}

/* ---------- Live Progress Component ---------- */

function LiveProgressViewer({
  steps,
  currentProgress,
  isActive
}: {
  steps: string[];
  currentProgress: number;
  isActive: boolean;
}) {
  return (
    <div className="p-2 bg-gray-950 border border-gray-800 rounded-lg" data-testid="analysis-progress">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-100" data-testid="analysis-stage">
          🔍 Analyzing Changes
        </h2>
        {isActive && (
          <div className="flex items-center space-x-1.5">
            <div className="animate-spin h-3 w-3 border-2 border-purple-500 border-t-transparent rounded-full"></div>
            <span className="text-xs text-purple-400">{currentProgress}%</span>
          </div>
        )}
      </div>

      <div className="space-y-1 mb-2">
        {steps.map((step, index) => (
          <div key={index} className="flex items-center space-x-1.5 text-xs">
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full"></div>
            <span className="text-gray-300">{step}</span>
          </div>
        ))}
        {isActive && steps.length > 0 && (
          <div className="flex items-center space-x-2 text-sm">
            <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse"></div>
            <span className="text-purple-400">Processing...</span>
          </div>
        )}
      </div>

      <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
        <div
          className="bg-gradient-to-r from-purple-600 to-blue-600 h-full transition-all duration-300"
          style={{ width: `${currentProgress}%` }}
        />
      </div>
      {!isActive && steps.length > 0 && currentProgress >= 100 && (
        <span style={{ display: "none" }} data-testid="analysis-complete">
          complete
        </span>
      )}
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
        <h3 className="text-sm font-medium text-gray-100">🔍 Visual Diff Viewer</h3>
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
                <span className="text-gray-400 transition-transform duration-200 text-xs">
                  {isOpen ? '▼' : '▶'}
                </span>
                <span className="font-mono text-xs text-gray-300 truncate">
                  📄 {file.path}
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
                      📄 {file.path} - No diff available
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
                            🔧
                          </div>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mb-2">
                        💡 {issue.body || "No description available"}
                      </div>
                      <button
                        className={`px-2 py-1 rounded text-xs font-medium transition-all duration-200 ${issue.canAutoFix
                          ? 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white'
                          : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                          }`}
                        onClick={() => onAutoFix(file.path, issue)}
                        disabled={!issue.canAutoFix}
                      >
                        ✨ Auto-fix
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

  const getSeverityIcon = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case "high": return "🔴";
      case "medium": return "🟡";
      case "low": return "🟢";
      default: return "📝";
    }
  };

  return (
    <div className="p-2 space-y-2">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm font-medium text-gray-100">📋 Code Review Results</h3>
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
                <span className="text-gray-400 transition-transform duration-200 text-xs">
                  {isCollapsed ? '▶' : '▼'}
                </span>
                <span className="font-mono text-xs text-gray-300 truncate">
                  📄 {file.path || "Unknown file"}
                </span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded text-xs border border-gray-700">
                  {file.issues?.length || 0}
                </div>
                {file.severity && (
                  <div className={`px-1.5 py-0.5 rounded text-xs border ${getSeverityBadgeClass(file.severity)}`}>
                    {getSeverityIcon(file.severity)}
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
                          🔧
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
                        ✨ Auto-fix
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
