import React, { useCallback, useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    __NAVI_WORKSPACE_ROOT__?: string | null;
  }
}

type Role = "user" | "assistant" | "system";

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
}

interface NaviAction {
  id?: string;
  title?: string;
  description?: string;
  intent_kind?: string;
  [key: string]: any;
}

interface NaviChatResponse {
  content?: string;
  reply?: string;
  actions?: NaviAction[];
  sources?: any[];
  [key: string]: any;
}

/** Execution / scope / persona controls */
type ExecutionMode = "explain" | "plan" | "auto";
type ScopeMode = "file" | "service" | "repo" | "org";
type Persona = "ic" | "tech_lead" | "sre" | "qa" | "em_tpm";

const EXECUTION_LABELS: Record<ExecutionMode, string> = {
  explain: "Explain only",
  plan: "Plan + propose",
  auto: "Auto-apply",
};

const SCOPE_LABELS: Record<ScopeMode, string> = {
  file: "This file",
  service: "This service",
  repo: "This repo",
  org: "Org-wide",
};

const PERSONA_LABELS: Record<Persona, string> = {
  ic: "IC engineer",
  tech_lead: "Tech lead",
  sre: "SRE / DevOps",
  qa: "QA / Tester",
  em_tpm: "EM / TPM",
};

const BACKEND_BASE = "http://127.0.0.1:8787";

function getWorkspaceRoot(): string | null {
  if (typeof window === "undefined") return null;
  return window.__NAVI_WORKSPACE_ROOT__ ?? null;
}

function getRepoName(workspaceRoot: string | null): string {
  if (!workspaceRoot) return "this workspace";
  const parts = workspaceRoot.split(/[/\\]/).filter(Boolean);
  return parts[parts.length - 1] || "this workspace";
}

async function sendNaviChat(
  message: string,
  executionMode: ExecutionMode,
  scope: ScopeMode,
  persona: Persona
): Promise<NaviChatResponse> {
  const workspaceRoot = getWorkspaceRoot();
  const url = `${BACKEND_BASE}/api/navi/chat`;

  const body = {
    message,
    model: "gpt-4o-mini",
    mode: "concierge",
    attachments: [],
    context: {},
    workspace: workspaceRoot,
    workspace_root: workspaceRoot,
    branch: null,
    user_id: "default-user",
    // NEW: behavior controls for planner
    execution_mode: executionMode,
    scope,
    persona,
  };

  console.log("[NAVI Chat] Sending request:", { url, body });

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const text = await res.text();
  console.log("[NAVI Chat] Raw response:", res.status, text);

  if (!res.ok) {
    throw new Error(`Navi chat failed (${res.status}): ${text}`);
  }

  const data = JSON.parse(text);
  console.log("[NAVI Chat] Parsed response:", data);
  return data;
}

export default function NaviChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  // NEW: behavior state
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("plan");
  const [scope, setScope] = useState<ScopeMode>("repo");
  const [persona, setPersona] = useState<Persona>("ic");

  const inputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    const userMessage: ChatMessage = {
      id: `m-${Date.now()}-user`,
      role: "user",
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSending(true);

    try {
      const data = await sendNaviChat(trimmed, executionMode, scope, persona);

      const workspaceRoot = getWorkspaceRoot();
      const repoName = getRepoName(workspaceRoot);
      const hasActions = Array.isArray(data.actions) && data.actions.length > 0;
      const action = hasActions ? data.actions![0] : null;

      let replyText: string;

      if (action && action.intent_kind === "inspect_repo") {
        replyText =
          `You're currently working in the **${repoName}** repo` +
          (workspaceRoot ? ` at \`${workspaceRoot}\`.` : ".") +
          "\n\n" +
          "I can also run a deeper repo inspection (files, Git history, JIRA/CI signals).\n" +
          "Use the repo tools panel to start an inspection run.";
      } else if (hasActions) {
        const title = action?.title || action?.intent_kind || "Planned action";
        const desc =
          action?.description ||
          "Navi has prepared a plan. Use the tools panel to execute it.";
        replyText = `Plan: **${title}**\n\n${desc}`;
      } else {
        replyText =
          (typeof data.reply === "string" && data.reply.trim().length > 0
            ? data.reply
            : data.content) || "(Navi returned an empty reply)";
      }

      const assistantMessage: ChatMessage = {
        id: `m-${Date.now()}-assistant`,
        role: "assistant",
        content: replyText,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error("[NAVI Chat] Error during send:", err);
      const errorMessage: ChatMessage = {
        id: `m-${Date.now()}-error`,
        role: "system",
        content: `Error talking to Navi: ${err.message ?? String(err)}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setSending(false);
    }
  }, [input, sending, executionMode, scope, persona]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt);
    inputRef.current?.focus();
  };

  const handleClearChat = () => {
    setMessages([]);
    setInput("");
    inputRef.current?.focus();
  };

  return (
    <div className="navi-chat-root">
      <div className="navi-chat-body">
        {/* Behavior controls row */}
        <div className="navi-chat-controls">
          <div className="navi-chat-control-group">
            <span className="navi-chat-control-label">Execution</span>
            <select
              className="navi-chat-select"
              value={executionMode}
              onChange={(e) => setExecutionMode(e.target.value as ExecutionMode)}
            >
              {(Object.keys(EXECUTION_LABELS) as ExecutionMode[]).map((key) => (
                <option key={key} value={key}>
                  {EXECUTION_LABELS[key]}
                </option>
              ))}
            </select>
          </div>

          <div className="navi-chat-control-group">
            <span className="navi-chat-control-label">Scope</span>
            <select
              className="navi-chat-select"
              value={scope}
              onChange={(e) => setScope(e.target.value as ScopeMode)}
            >
              {(Object.keys(SCOPE_LABELS) as ScopeMode[]).map((key) => (
                <option key={key} value={key}>
                  {SCOPE_LABELS[key]}
                </option>
              ))}
            </select>
          </div>

          <div className="navi-chat-control-group">
            <span className="navi-chat-control-label">Persona</span>
            <select
              className="navi-chat-select"
              value={persona}
              onChange={(e) => setPersona(e.target.value as Persona)}
            >
              {(Object.keys(PERSONA_LABELS) as Persona[]).map((key) => (
                <option key={key} value={key}>
                  {PERSONA_LABELS[key]}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Toolbar / quick actions */}
        <div className="navi-chat-toolbar">
          <span className="navi-chat-toolbar-label">Quick actions:</span>
          <button
            type="button"
            className="navi-chat-toolbar-btn"
            onClick={() => handleQuickPrompt("check errors and fix them in this repo")}
          >
            Check errors & fix
          </button>
          <button
            type="button"
            className="navi-chat-toolbar-btn"
            onClick={() =>
              handleQuickPrompt("explain what this repo does and its key components")
            }
          >
            Explain this repo
          </button>
          <button
            type="button"
            className="navi-chat-toolbar-btn"
            onClick={() =>
              handleQuickPrompt("create an engineering plan for improving this repo")
            }
          >
            Create plan
          </button>
          <button
            type="button"
            className="navi-chat-toolbar-btn navi-chat-toolbar-btn--ghost"
            onClick={handleClearChat}
          >
            Clear chat
          </button>
        </div>

        {/* Messages list */}
        <div className="navi-chat-messages">
          {messages.map((m) => (
            <div
              key={m.id}
              className={
                "navi-chat-row " +
                (m.role === "user"
                  ? "navi-chat-row--user"
                  : m.role === "assistant"
                  ? "navi-chat-row--assistant"
                  : "navi-chat-row--system")
              }
            >
              <div className="navi-chat-avatar" />
              <div className="navi-chat-bubble">
                {m.content.split("\n").map((line, idx) => (
                  <p
                    key={`${m.id}-line-${idx}`}
                    style={{ margin: idx === 0 ? 0 : "4px 0 0" }}
                  >
                    {line}
                  </p>
                ))}
              </div>
            </div>
          ))}

          {messages.length === 0 && (
            <div className="navi-chat-empty">
              Ask Navi anything about your repo, JIRA, or builds.
              <br />
              Example: <code>check errors and fix them</code>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="navi-chat-input-bar">
          <input
            ref={inputRef}
            className="navi-chat-input"
            placeholder={`Ask Navi: e.g. "check errors and fix them"`}
            value={input}
            disabled={sending}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          <button
            className="navi-chat-send-btn"
            disabled={sending || !input.trim()}
            onClick={() => void handleSend()}
          >
            {sending ? "Sending..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
