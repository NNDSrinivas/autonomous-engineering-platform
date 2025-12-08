"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { sendNaviChat, mapChatResponseToNaviChatMessage } from "../../../api/navi/client";
import { NaviChatMessageList } from "./NaviChatMessageList";
import type { NaviChatMessage } from "../../../types/naviChat";

/**
 * Simple utility to join tailwind classes conditionally.
 */
function classNames(...classes: Array<string | null | undefined | false>) {
    return classes.filter(Boolean).join(" ");
}

export interface NaviConversationViewProps {
    initialMessages?: NaviChatMessage[];
    initialRepoPath?: string | null;
    initialBranch?: string | null;
}

// Heuristic phrases that mean "run diagnostics / check errors"
const DIAGNOSTIC_TRIGGERS = [
    "check errors",
    "check for errors",
    "diagnose errors",
    "fix errors",
    "fix the errors",
    "run diagnostics",
    "run diag",
    "run lint",
    "run lints",
    "run tests",
    "check build",
];

const DIAGNOSTIC_STEPS = [
    "Scanning workspace…",
    "Inspecting package.json & config files…",
    "Running lint / test commands…",
    "Summarizing diagnostics and suggested fixes…",
];

function isDiagnosticsPrompt(text: string): boolean {
    const lower = text.toLowerCase();
    return DIAGNOSTIC_TRIGGERS.some((phrase) => lower.includes(phrase));
}

export const NaviConversationView: React.FC<NaviConversationViewProps> = ({
    initialMessages = [],
    initialRepoPath,
    initialBranch,
}) => {
    const [messages, setMessages] = useState<NaviChatMessage[]>(initialMessages);
    const [input, setInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // diagnostics progress state (purely frontend / cosmetic)
    const [diagnosticsActive, setDiagnosticsActive] = useState(false);
    const [diagnosticsStepIndex, setDiagnosticsStepIndex] = useState(0);

    const workspacePath =
        initialRepoPath ||
        (typeof window !== "undefined"
            ? ((window as any).__WORKSPACE_ROOT__ as string | null)
            : null);

    const branch = initialBranch || null;

    const addMessages = useCallback((newMessages: NaviChatMessage[]) => {
        setMessages((prev) => [...prev, ...newMessages]);
    }, []);

    // Progress animation for diagnostics: step through the phases every ~1.2s
    useEffect(() => {
        if (!diagnosticsActive) {
            return;
        }

        setDiagnosticsStepIndex(0);

        const interval = window.setInterval(() => {
            setDiagnosticsStepIndex((prev) => {
                if (prev >= DIAGNOSTIC_STEPS.length - 1) {
                    return prev;
                }
                return prev + 1;
            });
        }, 1200);

        return () => {
            window.clearInterval(interval);
        };
    }, [diagnosticsActive]);

    const handleSend = useCallback(async () => {
        const trimmed = input.trim();
        if (!trimmed || isSending) return;

        setError(null);

        const now = new Date().toISOString();
        const userMessage: NaviChatMessage = {
            id: `user-${Date.now()}`,
            createdAt: now,
            role: "user",
            kind: "text",
            text: trimmed,
        };
        addMessages([userMessage]);
        setInput("");

        const shouldRunDiagnostics = isDiagnosticsPrompt(trimmed);
        if (shouldRunDiagnostics) {
            setDiagnosticsActive(true);
        }

        setIsSending(true);
        try {
            const response = await sendNaviChat(trimmed, {
                workspace_root: workspacePath,
                branch: branch,
            });

            // This mapper already exists in your codebase; keep using it.
      const assistantMessage = mapChatResponseToNaviChatMessage({
        response,
        lastUserMessage: trimmed,
        role: "assistant",
        repoPath: workspacePath ?? undefined,
        branch: branch ?? undefined,
      });            addMessages([assistantMessage]);
        } catch (err: any) {
            console.error("Failed to send NAVI chat:", err);
            setError(
                err?.message ||
                "Failed to send message to NAVI. Please check the backend logs and try again.",
            );

            const errorMessage: NaviChatMessage = {
                id: `err-${Date.now()}`,
                createdAt: new Date().toISOString(),
                role: "assistant",
                kind: "text",
                text: "Something went wrong while processing this command. Please check server logs or retry.",
            };
            addMessages([errorMessage]);
        } finally {
            setIsSending(false);
            if (shouldRunDiagnostics) {
                // Give the user a tiny moment to see the final step tick, then hide.
                setTimeout(() => setDiagnosticsActive(false), 500);
            }
        }
    }, [addMessages, branch, input, isSending, workspacePath]);

    const diagnosticsStepLabel = useMemo(
        () => DIAGNOSTIC_STEPS[Math.min(diagnosticsStepIndex, DIAGNOSTIC_STEPS.length - 1)],
        [diagnosticsStepIndex],
    );

    return (
        <div className="flex h-full flex-col bg-slate-950/90">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto">
                <NaviChatMessageList messages={messages} onAppendMessages={addMessages} />
            </div>

            {/* Error bar */}
            {error && (
                <div className="border-t border-red-800 bg-red-950/90 px-3 py-1.5 text-xs text-red-100">
                    {error}
                </div>
            )}

            {/* Diagnostics live progress (purely visual) */}
            {diagnosticsActive && (
                <div className="border-t border-slate-800 bg-slate-900/95 px-3 py-2 text-xs text-slate-200">
                    <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                        <span className="font-semibold">Running workspace diagnostics…</span>
                    </div>
                    <ol className="mt-2 space-y-1">
                        {DIAGNOSTIC_STEPS.map((step, index) => {
                            const isDone = index < diagnosticsStepIndex;
                            const isActive = index === diagnosticsStepIndex;

                            return (
                                <li key={step} className="flex items-center gap-2">
                                    <span
                                        className={classNames(
                                            "inline-flex h-4 w-4 items-center justify-center rounded-full border text-[9px]",
                                            isDone &&
                                            "border-emerald-500 bg-emerald-500/20 text-emerald-300",
                                            !isDone &&
                                            isActive &&
                                            "border-sky-400 bg-sky-500/10 text-sky-200 animate-pulse",
                                            !isDone &&
                                            !isActive &&
                                            "border-slate-600 bg-slate-800/80 text-slate-500",
                                        )}
                                    >
                                        {isDone ? "✓" : index + 1}
                                    </span>
                                    <span
                                        className={classNames(
                                            "text-[11px]",
                                            isDone && "text-slate-500 line-through",
                                            !isDone && isActive && "text-sky-100",
                                            !isDone && !isActive && "text-slate-500",
                                        )}
                                    >
                                        {step}
                                    </span>
                                </li>
                            );
                        })}
                    </ol>
                    <div className="mt-2 text-[10px] text-slate-500">
                        Current step: {diagnosticsStepLabel}
                    </div>
                </div>
            )}

            {/* Composer */}
            <div className="border-t border-slate-800 bg-slate-900/95 px-3 py-2">
                <div className="flex items-center gap-2">
                    <input
                        className="flex-1 rounded-xl border border-slate-700/70 bg-slate-900 px-3 py-2 text-sm text-slate-50 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-pink-500/70 focus:ring-offset-1 focus:ring-offset-slate-950 disabled:opacity-60"
                        placeholder='Ask Navi: e.g. "check errors and fix them"'
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        disabled={isSending}
                    />
                    <button
                        type="button"
                        onClick={handleSend}
                        disabled={isSending}
                        className="inline-flex items-center rounded-xl bg-gradient-to-r from-purple-500 via-pink-500 to-cyan-400 px-3 py-2 text-xs font-semibold text-white shadow-md shadow-purple-900/40 transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-pink-400/80 focus:ring-offset-1 focus:ring-offset-slate-950 disabled:opacity-60"
                    >
                        {isSending ? "Thinking…" : "Send"}
                    </button>
                </div>
            </div>
        </div>
    );
};
