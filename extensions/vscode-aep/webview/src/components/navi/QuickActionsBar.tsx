// frontend/src/components/navi/QuickActionsBar.tsx
// import React from "react";
import * as vscodeApi from "../../utils/vscodeApi";

export interface QuickAction {
  id: string;
  label: string;
  prompt: string;
}

interface QuickActionsBarProps {
  className?: string;
  disabled?: boolean;
  onQuickPrompt?: (prompt: string) => void;
  actions?: QuickAction[];
}

const DEFAULT_ACTIONS: QuickAction[] = [
  { id: "tell_more", label: "Tell me more", prompt: "tell me more" },
  { id: "explain_further", label: "Can you explain further?", prompt: "can you explain further?" },
  { id: "next_steps", label: "What are the next steps?", prompt: "what are the next steps?" },
  { id: "alternatives", label: "Any alternatives?", prompt: "any alternatives?" },
];

const cx = (...parts: Array<string | false | null | undefined>) =>
  parts.filter(Boolean).join(" ");

export function QuickActionsBar({
  className,
  disabled,
  onQuickPrompt,
  actions,
}: QuickActionsBarProps) {
  const actionsToRender = actions && actions.length > 0 ? actions : DEFAULT_ACTIONS;

  const handleClick = (action: QuickAction) => {
    if (disabled) return;

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
      <div className="navi-quick-actions__list">
        {actionsToRender.map((action) => (
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
            data-testid={`quick-${action.id}`}
          >
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
