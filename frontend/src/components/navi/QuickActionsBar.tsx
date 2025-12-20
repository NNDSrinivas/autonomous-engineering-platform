// frontend/src/components/navi/QuickActionsBar.tsx
import React from "react";
import * as vscodeApi from "../../utils/vscodeApi";

interface QuickActionsBarProps {
  className?: string;
  disabled?: boolean;
  onQuickPrompt?: (prompt: string) => void;
}

interface QuickAction {
  id: string;
  label: string;
  prompt: string;
  emoji?: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "check_errors",
    label: "Check errors & fix",
    // keep this EXACT phrase – backend looks for it
    prompt: "check errors and fix them",
    emoji: "🧹",
  },
  {
    id: "live_analysis",
    label: "Live Code Analysis",
    prompt: "__LIVE_ANALYSIS__", // Special marker for real-time analysis
    emoji: "⚡",
  },
  {
    id: "review_working",
    label: "Review working changes",
    prompt: "review my working tree changes and suggest improvements",
    emoji: "🔍",
  },
  {
    id: "review_staged",
    label: "Review staged changes",
    prompt: "review my staged changes and prepare PR comments",
    emoji: "📋",
  },
  {
    id: "review_last_commit",
    label: "Review last commit",
    prompt: "review my last commit and point out any issues",
    emoji: "⏪",
  },
  {
    id: "explain_repo",
    label: "Explain this repo",
    prompt: "explain this repo, what it does, and the key components",
    emoji: "📁",
  },
  {
    id: "scan_repo",
    label: "Scan repo",
    prompt: "scan repo",
    emoji: "🛰️",
  },
  {
    id: "clear_chat",
    label: "Clear chat",
    prompt: "/clear-chat",
    emoji: "🧼",
  },
];

const cx = (...parts: Array<string | false | null | undefined>) =>
  parts.filter(Boolean).join(" ");

export function QuickActionsBar({
  className,
  disabled,
  onQuickPrompt,
}: QuickActionsBarProps) {
  const handleClick = (action: QuickAction) => {
    if (disabled) return;

    // Special local command for clear chat – handled by extension
    if (action.id === "clear_chat") {
      vscodeApi.postMessage({ type: "clearChat" });
      return;
    }

    if (onQuickPrompt) {
      onQuickPrompt(action.prompt);
      return;
    }

    // Fallback: fire a normal message through the extension
    vscodeApi.postMessage({
      type: "sendMessage",
      text: action.prompt,
      modelId: "default",
      modeId: "concierge",
      attachments: [],
    });
  };

  return (
    <div className={cx("navi-quick-actions", className)}>
      <div className="navi-quick-actions__header">
        <span className="navi-quick-actions__label">Quick actions</span>
      </div>

      <div className="navi-quick-actions__list">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.id}
            type="button"
            className={cx(
              "navi-pill",
              "navi-quick-actions__btn",
              disabled && "navi-quick-actions__btn--disabled",
            )}
            onClick={() => handleClick(action)}
            disabled={disabled}
            data-testid={
              action.id === "live_analysis"
                ? "smart-workspace-btn"
                : `quick-${action.id}`
            }
          >
            {action.emoji && (
              <span className="navi-quick-actions__icon">
                {action.emoji}
              </span>
            )}
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
