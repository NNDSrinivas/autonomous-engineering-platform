"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface PasswordStrengthMeterProps {
  password: string;
}

function getPasswordStrength(password: string): {
  score: number;
  label: string;
  color: string;
} {
  let score = 0;

  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 1) {
    return { score, label: "Weak", color: "bg-destructive" };
  } else if (score <= 2) {
    return { score, label: "Fair", color: "bg-status-warning" };
  } else if (score <= 3) {
    return { score, label: "Good", color: "bg-status-info" };
  } else if (score <= 4) {
    return { score, label: "Strong", color: "bg-status-success" };
  } else {
    return { score, label: "Very Strong", color: "gradient-ai" };
  }
}

export function PasswordStrengthMeter({ password }: PasswordStrengthMeterProps) {
  const { score, label, color } = getPasswordStrength(password);

  if (!password) {
    return null;
  }

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1 h-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className={cn(
              "flex-1 rounded-full transition-colors duration-300",
              i <= score ? color : "bg-muted"
            )}
          />
        ))}
      </div>
      <p
        className={cn(
          "text-xs",
          score <= 1
            ? "text-destructive"
            : score <= 2
            ? "text-status-warning"
            : score <= 3
            ? "text-status-info"
            : "text-status-success"
        )}
      >
        {label}
      </p>
    </div>
  );
}

export function getPasswordRequirements(password: string): {
  met: boolean;
  label: string;
}[] {
  return [
    { met: password.length >= 8, label: "At least 8 characters" },
    { met: /[A-Z]/.test(password), label: "One uppercase letter" },
    { met: /[0-9]/.test(password), label: "One number" },
    { met: /[^A-Za-z0-9]/.test(password), label: "One special character" },
  ];
}
