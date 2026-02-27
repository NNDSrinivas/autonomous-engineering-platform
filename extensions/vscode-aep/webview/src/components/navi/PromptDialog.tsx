import React, { useEffect, useMemo, useState } from "react";
import { AlertCircle, Clock3, MessageSquareText } from "lucide-react";
import type {
  NaviPromptRequest,
  NaviPromptResponse,
  PromptOption,
} from "../../types/naviChat";

interface PromptDialogProps {
  prompt: NaviPromptRequest;
  onSubmit: (response: NaviPromptResponse) => Promise<void> | void;
  onCancel: (prompt_id: string) => Promise<void> | void;
}

const PROMPT_TYPE_LABEL: Record<NaviPromptRequest["prompt_type"], string> = {
  text: "Text input",
  select: "Select one",
  confirm: "Confirmation",
  multiselect: "Select multiple",
};

const normalizeOptions = (
  options: NaviPromptRequest["options"] | string[] | undefined
): PromptOption[] => {
  if (!options || options.length === 0) return [];
  return options
    .map((option) => {
      if (typeof option === "string") {
        return { value: option, label: option };
      }
      if (option && typeof option === "object") {
        const value = String(option.value ?? option.label ?? "").trim();
        if (!value) return null;
        return {
          value,
          label: String(option.label ?? value),
          description: option.description ? String(option.description) : undefined,
        };
      }
      return null;
    })
    .filter((option): option is PromptOption => Boolean(option));
};

export const PromptDialog: React.FC<PromptDialogProps> = ({
  prompt,
  onSubmit,
  onCancel,
}) => {
  const [value, setValue] = useState<string | string[] | boolean>(() => {
    if (prompt.prompt_type === "multiselect") return [];
    if (prompt.prompt_type === "confirm") {
      const confirmOptions = normalizeOptions(
        prompt.options as unknown as PromptOption[] | string[]
      );
      if (confirmOptions.length > 0) {
        return String(prompt.default_value || "").trim();
      }
      const normalizedDefault = String(prompt.default_value || "").trim().toLowerCase();
      if (["true", "1", "yes", "y", "approve", "allow"].includes(normalizedDefault)) {
        return true;
      }
      if (["false", "0", "no", "n", "deny", "reject"].includes(normalizedDefault)) {
        return false;
      }
      return "";
    }
    return prompt.default_value || "";
  });
  const [error, setError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(
    prompt.timeout_seconds || null
  );

  const options = useMemo(
    () => normalizeOptions(prompt.options as unknown as PromptOption[] | string[]),
    [prompt.options]
  );
  const hasCustomConfirmOptions = prompt.prompt_type === "confirm" && options.length > 0;
  const confirmOptionButtons = useMemo(() => {
    if (prompt.prompt_type !== "confirm") return [];
    if (options.length > 0) return options;
    return [
      { value: "yes", label: "Yes" },
      { value: "no", label: "No" },
    ] as PromptOption[];
  }, [prompt.prompt_type, options]);

  useEffect(() => {
    if (!timeRemaining || timeRemaining <= 0) return;
    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (!prev || prev <= 1) {
          onCancel(prompt.prompt_id);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [timeRemaining, onCancel, prompt.prompt_id]);

  const isValueProvided = () => {
    if (prompt.prompt_type === "multiselect") {
      return (value as string[]).length > 0;
    }
    if (prompt.prompt_type === "confirm") {
      return hasCustomConfirmOptions ? Boolean(String(value ?? "").trim()) : typeof value === "boolean";
    }
    return Boolean(String(value ?? "").trim());
  };

  const submitResponse = async (responseValue: string | string[] | boolean) => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSubmit({
        prompt_id: prompt.prompt_id,
        response: responseValue,
        cancelled: false,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onCancel(prompt.prompt_id);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async () => {
    if (prompt.required && !isValueProvided()) {
      setError("This field is required.");
      return;
    }

    if (prompt.validation_pattern && typeof value === "string") {
      try {
        const regex = new RegExp(prompt.validation_pattern);
        if (!regex.test(value)) {
          setError("Value does not match required format.");
          return;
        }
      } catch {
        // Ignore invalid regex from backend and let user continue.
      }
    }

    let responseValue: string | string[] | boolean = value;
    if (prompt.prompt_type === "confirm") {
      responseValue = hasCustomConfirmOptions ? String(value ?? "").trim() : value === true;
    }

    await submitResponse(responseValue);
  };

  const handleToggleMulti = (optionValue: string, checked: boolean) => {
    const current = Array.isArray(value) ? value : [];
    if (checked) {
      setValue([...current, optionValue]);
      return;
    }
    setValue(current.filter((entry) => entry !== optionValue));
  };

  const getConfirmToneClass = (option: PromptOption): string => {
    const token = `${option.value} ${option.label}`.toLowerCase();
    if (/\b(yes|y|approve|allow|continue|proceed|confirm|accept|run)\b/.test(token)) {
      return "is-approve";
    }
    if (/\b(no|n|deny|reject|cancel|decline|stop|block)\b/.test(token)) {
      return "is-deny";
    }
    return "";
  };

  const renderInput = () => {
    switch (prompt.prompt_type) {
      case "text":
        return (
          <input
            className="navi-inline-prompt__input"
            value={value as string}
            disabled={isSubmitting}
            onChange={(e) => {
              setValue(e.target.value);
              setError("");
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSubmit();
              }
            }}
            placeholder={prompt.placeholder || "Enter a value"}
            autoFocus
          />
        );

      case "confirm":
        return (
          <div className="navi-inline-prompt__confirm-grid">
            {confirmOptionButtons.map((option) => {
              const toneClass = getConfirmToneClass(option);
              const isActive = hasCustomConfirmOptions
                ? value === option.value
                : (option.value.toLowerCase() === "yes" && value === true) ||
                  (option.value.toLowerCase() === "no" && value === false);
              return (
                <button
                  type="button"
                  key={option.value}
                  className={`navi-inline-prompt__option-btn ${
                    isActive ? `is-active ${toneClass}`.trim() : ""
                  }`}
                  disabled={isSubmitting}
                  onClick={() => {
                    const selectedValue: string | boolean = hasCustomConfirmOptions
                      ? option.value
                      : option.value.toLowerCase() === "yes";
                    setValue(selectedValue);
                    setError("");
                    void submitResponse(
                      hasCustomConfirmOptions ? String(selectedValue).trim() : selectedValue === true
                    );
                  }}
                >
                  <span className="navi-inline-prompt__option-label">{option.label}</span>
                  {option.description && (
                    <span className="navi-inline-prompt__option-desc">{option.description}</span>
                  )}
                </button>
              );
            })}
          </div>
        );

      case "select":
        return (
          <div className="navi-inline-prompt__option-list">
            {options.map((option) => {
              const isActive = value === option.value;
              return (
                <button
                  type="button"
                  key={option.value}
                  className={`navi-inline-prompt__option-btn ${isActive ? "is-active" : ""}`}
                  disabled={isSubmitting}
                  onClick={() => {
                    setValue(option.value);
                    setError("");
                  }}
                >
                  <span className="navi-inline-prompt__option-label">{option.label}</span>
                  {option.description && (
                    <span className="navi-inline-prompt__option-desc">{option.description}</span>
                  )}
                </button>
              );
            })}
          </div>
        );

      case "multiselect":
        return (
          <div className="navi-inline-prompt__option-list">
            {options.map((option) => {
              const selected = Array.isArray(value) && value.includes(option.value);
              return (
                <label
                  key={option.value}
                  className={`navi-inline-prompt__multi-item ${selected ? "is-active" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={isSubmitting}
                    onChange={(e) => {
                      handleToggleMulti(option.value, e.target.checked);
                      setError("");
                    }}
                  />
                  <span className="navi-inline-prompt__multi-text">
                    <span className="navi-inline-prompt__option-label">{option.label}</span>
                    {option.description && (
                      <span className="navi-inline-prompt__option-desc">{option.description}</span>
                    )}
                  </span>
                </label>
              );
            })}
          </div>
        );
    }
  };

  return (
    <div className="navi-inline-consent navi-inline-consent--prompt">
      <div className="navi-inline-consent__header">
        <div className="navi-inline-consent__title-wrap">
          <span className="navi-inline-consent__icon">
            <MessageSquareText className="h-3.5 w-3.5" />
          </span>
          <div className="navi-inline-consent__title-group">
            <div className="navi-inline-consent__title">{prompt.title || "Input required"}</div>
            <div className="navi-inline-consent__meta">{PROMPT_TYPE_LABEL[prompt.prompt_type]}</div>
          </div>
        </div>
        {typeof timeRemaining === "number" && timeRemaining > 0 && (
          <div className="navi-inline-consent__timer">
            <Clock3 className="h-3.5 w-3.5" />
            {Math.floor(timeRemaining / 60)}:{(timeRemaining % 60).toString().padStart(2, "0")}
          </div>
        )}
      </div>

      {prompt.description && (
        <div className="navi-inline-consent__description">{prompt.description}</div>
      )}

      <div className="navi-inline-prompt__body">{renderInput()}</div>

      {error && (
        <div className="navi-inline-consent__error">
          <AlertCircle className="h-3.5 w-3.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="navi-inline-consent__actions">
        <button
          type="button"
          className="navi-inline-consent__btn navi-inline-consent__btn--ghost"
          onClick={() => void handleCancel()}
          disabled={isSubmitting}
        >
          Cancel
        </button>
        {prompt.prompt_type !== "confirm" && (
          <button
            type="button"
            className="navi-inline-consent__btn navi-inline-consent__btn--primary"
            onClick={() => void handleSubmit()}
            disabled={isSubmitting || (prompt.required && !isValueProvided())}
          >
            Submit
          </button>
        )}
      </div>
    </div>
  );
};
