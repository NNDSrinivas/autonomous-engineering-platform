// frontend/src/components/navi/NaviChatPanel.tsx
"use client";

import {
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { QuickActionsBar } from "./QuickActionsBar";
import { AttachmentToolbar } from "./AttachmentToolbar";
import {
  AttachmentChips,
  AttachmentChipData,
} from "./AttachmentChips";
import * as vscodeApi from "../../utils/vscodeApi";
import "./NaviChatPanel.css";

/* ---------- Types ---------- */

type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;           // NEW: timestamp for each message
  responseData?: NaviChatResponse;
}

type ExecutionMode = "plan_propose" | "plan_and_run";
type ScopeMode = "this_repo" | "current_file" | "service";
type ProviderId = "openai_navra" | "openai_byok" | "anthropic_byok";

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

/* ---------- Toast ---------- */

interface ToastState {
  id: number;
  message: string;
  kind: "info" | "warning" | "error";
}

/* ---------- Component ---------- */

export default function NaviChatPanel() {
  const { workspaceRoot, repoName, isLoading } = useWorkspace();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AttachmentChipData[]>([]);
  const [sending, setSending] = useState(false);

  const [executionMode, setExecutionMode] =
    useState<ExecutionMode>("plan_propose");
  const [scope, setScope] = useState<ScopeMode>("this_repo");
  const [provider, setProvider] = useState<ProviderId>("openai_navra");

  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  const [toast, setToast] = useState<ToastState | null>(null);

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

  // Scroll on new message
  useEffect(() => {
    if (!scrollerRef.current) return;
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [messages.length]);

  // Note: Removed global keydown handler to let OS handle Cmd/Ctrl-C naturally
  // This prevents VS Code clipboard blocking errors in webviews

  // Listen for VS Code messages
  useEffect(() => {
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

      if (msg.type === "botMessage" && msg.text) {
        const assistantMessage: ChatMessage = {
          id: makeMessageId("assistant"),
          role: "assistant",
          content: msg.text,
          createdAt: nowIso(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setSending(false);
      }

      if (msg.type === "botThinking") {
        setSending(msg.value === true);
      }
    });
  }, []);

  /* ---------- direct backend call (fallback) ---------- */

  const sendNaviChatRequest = async (
    message: string
  ): Promise<NaviChatResponse> => {
    const { effectiveRoot } = getEffectiveWorkspace();

    if (!effectiveRoot) {
      vscodeApi.postMessage({ type: "getWorkspaceRoot" });
    }

    const workspaceRootToSend = effectiveRoot;

    const body = {
      message,
      workspace: null,
      workspace_root: workspaceRootToSend,
      branch: null,
      mode: "concierge",
      execution: executionMode,
      scope,
      provider,
      attachments: attachments.map((att) => ({
        kind: att.kind,
        path: att.path,
        language: att.language,
        content: (att as any).content,
      })),
    };

    const url = "http://127.0.0.1:8787/api/navi/chat";
    console.log("[NAVI Chat] Sending request:", { url, body });

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const raw = (await res.json()) as NaviChatResponse;
    console.log("[NAVI Chat] Raw response:", raw);
    return raw;
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
    return fallback;
  };

  /* ---------- send ---------- */

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text) return;

    const userMessage: ChatMessage = {
      id: makeMessageId("user"),
      role: "user",
      content: text,
      createdAt: nowIso(),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!overrideText) setInput("");
    setSending(true);

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
      });

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

    // Fallback path – only reached if the VS Code bridge throws
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
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  };

  /* ---------- quick actions ---------- */

  const handleQuickPrompt = (prompt: string) => {
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
    const isMeta = e.metaKey || e.ctrlKey;

    // Custom paste handling: Cmd+V / Ctrl+V
    if (isMeta && e.key.toLowerCase() === 'v') {
      e.preventDefault();

      vscodeApi.readClipboard().then((text) => {
        if (!text) return;

        setInput((prev) => {
          const el = inputRef.current;
          if (!el) return prev + text;

          const start = el.selectionStart ?? prev.length;
          const end = el.selectionEnd ?? prev.length;

          const before = prev.slice(0, start);
          const after = prev.slice(end);
          const next = before + text + after;

          // restore caret after React updates value
          setTimeout(() => {
            const caret = start + text.length;
            try {
              el.setSelectionRange(caret, caret);
            } catch {
              // ignore
            }
          }, 0);

          return next;
        });
      });

      return;
    }

    // Existing Enter-to-send logic
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  /* ---------- per-message actions ---------- */

  const handleCopyMessage = (msg: ChatMessage) => {
    // Delegate clipboard to the VS Code extension and wait for result
    vscodeApi
      .writeClipboard(msg.content)
      .then((success) => {
        if (success) {
          showToast("Copied to clipboard.", "info");
        } else {
          showToast(
            "Copy failed – try selecting and copying the text manually.",
            "error"
          );
        }
      })
      .catch((err) => {
        console.error("[NAVI] Clipboard write error:", err);
        showToast(
          "Copy failed – try selecting and copying the text manually.",
          "error"
        );
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

  /* ---------- clear chat ---------- */

  const handleClearChat = () => {
    setMessages([]);
    setInput("");
    setAttachments([]);
    setTimeout(() => inputRef.current?.focus(), 10);
  };

  /* ---------- render ---------- */

  return (
    <div className="navi-chat-root">
      <header className="navi-chat-header">
        <div className="navi-chat-title">AEP: NAVI ASSISTANT</div>
        <button
          type="button"
          className="navi-pill navi-pill--ghost"
          onClick={handleClearChat}
        >
          Clear chat
        </button>
      </header>

      <div className="navi-chat-body" ref={scrollerRef}>
        {messages.length === 0 && (
          <div className="navi-chat-empty">
            <div>Ask Navi anything about your repo, JIRA, or builds.</div>
            <div className="navi-chat-empty-example">
              Example: <code>check errors and fix them</code>
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`navi-chat-bubble-row navi-chat-bubble-row--${m.role}`}
          >
            <div className={`navi-chat-avatar navi-chat-avatar--${m.role}`}>
              {m.role === "user" ? "🧑‍💻" : m.role === "assistant" ? "🪐" : "!"}
            </div>
            <div className={`navi-chat-bubble navi-chat-bubble--${m.role}`}>
              {m.content.split("\n").map((line, idx) => (
                <p key={idx}>{line}</p>
              ))}

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
        ))}

        {/* Progress indicator when NAVI is thinking */}
        {sending && (
          <div className="navi-chat-bubble-row navi-chat-bubble-row--assistant">
            <div className="navi-chat-avatar navi-chat-avatar--assistant">
              🪐
            </div>
            <div className="navi-chat-bubble navi-chat-bubble--assistant">
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
        />

        <button
          type="button"
          className="navi-pill navi-pill--primary navi-chat-send-btn"
          onClick={() => void handleSend()}
          disabled={!input.trim()}
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
    </div>
  );
}