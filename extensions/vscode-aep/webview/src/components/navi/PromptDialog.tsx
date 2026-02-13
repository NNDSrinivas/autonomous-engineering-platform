import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { MessageCircle, AlertCircle } from "lucide-react";
import type {
  NaviPromptRequest,
  NaviPromptResponse,
} from "../../types/naviChat";

interface PromptDialogProps {
  prompt: NaviPromptRequest;
  onSubmit: (response: NaviPromptResponse) => void;
  onCancel: (prompt_id: string) => void;
}

export const PromptDialog: React.FC<PromptDialogProps> = ({
  prompt,
  onSubmit,
  onCancel,
}) => {
  const [value, setValue] = useState<string | string[] | boolean>(() => {
    if (prompt.prompt_type === "multiselect") {
      return [];
    }
    if (prompt.prompt_type === "confirm") {
      return false;
    }
    return prompt.default_value || "";
  });
  const [error, setError] = useState<string>("");
  const [timeRemaining, setTimeRemaining] = useState<number | null>(
    prompt.timeout_seconds || null
  );

  // Countdown timer
  useEffect(() => {
    if (!timeRemaining || timeRemaining <= 0) return;

    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (!prev || prev <= 1) {
          // Timeout - auto-cancel
          handleCancel();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [timeRemaining]);

  const handleSubmit = () => {
    // Validation
    if (prompt.required && !isValueProvided()) {
      setError("This field is required");
      return;
    }

    if (prompt.validation_pattern && typeof value === "string") {
      try {
        const regex = new RegExp(prompt.validation_pattern);
        if (!regex.test(value)) {
          setError("Invalid format");
          return;
        }
      } catch (e) {
        console.error("Invalid regex pattern:", e);
      }
    }

    onSubmit({
      prompt_id: prompt.prompt_id,
      response: value,
      cancelled: false,
    });
  };

  const handleCancel = () => {
    onCancel(prompt.prompt_id);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && prompt.prompt_type === "text") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const renderInput = () => {
    switch (prompt.prompt_type) {
      case "text":
        return (
          <div className="space-y-2">
            <Input
              value={value as string}
              onChange={(e) => {
                setValue(e.target.value);
                setError("");
              }}
              onKeyDown={handleKeyDown}
              placeholder={prompt.placeholder || "Enter your response..."}
              autoFocus
              className="w-full"
            />
          </div>
        );

      case "select":
        return (
          <div className="space-y-2">
            <select
              value={value as string}
              onChange={(e) => {
                setValue(e.target.value);
                setError("");
              }}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              autoFocus
            >
              <option value="">Select an option...</option>
              {prompt.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {prompt.options && value && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {
                  prompt.options.find((opt) => opt.value === value)
                    ?.description
                }
              </p>
            )}
          </div>
        );

      case "confirm":
        return (
          <div className="flex gap-4 justify-center py-4">
            <Button
              onClick={() => {
                setValue(true);
                setError("");
              }}
              variant={value === true ? "primary" : "outline"}
            >
              Yes
            </Button>
            <Button
              onClick={() => {
                setValue(false);
                setError("");
              }}
              variant={value === false ? "primary" : "outline"}
            >
              No
            </Button>
          </div>
        );

      case "multiselect":
        return (
          <div className="space-y-2">
            {prompt.options?.map((option) => (
              <label
                key={option.value}
                className="flex items-start gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={(value as string[]).includes(option.value)}
                  onChange={(e) => {
                    const current = value as string[];
                    if (e.target.checked) {
                      setValue([...current, option.value]);
                    } else {
                      setValue(current.filter((v) => v !== option.value));
                    }
                    setError("");
                  }}
                  className="mt-0.5"
                />
                <div className="flex-1">
                  <div className="font-medium text-sm">{option.label}</div>
                  {option.description && (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {option.description}
                    </div>
                  )}
                </div>
              </label>
            ))}
          </div>
        );

      default:
        return (
          <textarea
            value={value as string}
            onChange={(e) => {
              setValue(e.target.value);
              setError("");
            }}
            placeholder={prompt.placeholder}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 min-h-[100px]"
            autoFocus
          />
        );
    }
  };

  const isValueProvided = () => {
    if (prompt.prompt_type === "multiselect") {
      return (value as string[]).length > 0;
    }
    if (prompt.prompt_type === "confirm") {
      return true; // Confirm always has a value (true/false)
    }
    return Boolean(value);
  };

  return (
    <Dialog open={true} onOpenChange={(open) => !open && handleCancel()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-blue-500" />
            <DialogTitle>{prompt.title}</DialogTitle>
          </div>
          <DialogDescription className="text-left">
            {prompt.description}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {renderInput()}
          {error && (
            <div className="flex items-center gap-2 mt-2 text-red-500 text-sm">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
        </div>

        {timeRemaining && timeRemaining > 0 && (
          <div className="text-sm text-gray-500 dark:text-gray-400 text-center">
            Time remaining: {Math.floor(timeRemaining / 60)}:
            {(timeRemaining % 60).toString().padStart(2, "0")}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={prompt.required && !isValueProvided()}
          >
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
