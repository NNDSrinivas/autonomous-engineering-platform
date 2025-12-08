// src/components/navi/chat/NaviChatMessage.tsx
import React from "react";
import type {
    NaviChatMessage,
    NaviChatMessageIntent,
    NaviChatMessageText,
} from "../../../types/naviChat";
import { NaviCheckErrorsAndFixPanel } from "../NaviCheckErrorsAndFixPanel";
import { NaviActionsBar } from "../NaviActionsBar";
import { NaviSourcesBar } from "../NaviSourcesBar";
import { NaviMarkdown } from "../NaviMarkdown";

type Props = {
    message: NaviChatMessage;
    /**
     * Called when a child component (like actions bar) wants to append new messages.
     */
    onAppendMessages?: (msgs: NaviChatMessage[]) => void;
};

export const NaviChatMessageView: React.FC<Props> = ({
    message,
    onAppendMessages,
}) => {
    const isUser = message.role === "user";
    const meta = message.meta;

    const handleActionResult = (msg: NaviChatMessage) => {
        if (onAppendMessages) {
            onAppendMessages([msg]);
        }
    };

    return (
        <div
            className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-3`}
        >
            <div
                className={`max-w-xl rounded-2xl px-3 py-2.5 text-sm shadow-md ${isUser
                    ? "rounded-br-sm bg-sky-600 text-white shadow-sky-900/40"
                    : "rounded-bl-sm bg-slate-900/90 text-slate-50 shadow-slate-950/40 border border-slate-800/60"
                    }`}
            >
                {/* Text content */}
                {message.kind === "text" && (
                    <TextMessageBubble message={message} isUser={isUser} />
                )}

                {message.kind === "navi-intent" && (
                    <IntentMessageBubble message={message} isUser={isUser} />
                )}

                {/* Sources bar (assistant-only) */}
                {!isUser && meta && meta.sources && (meta.sources as any[]).length > 0 && (
                    <div className="mt-2">
                        <NaviSourcesBar sources={meta.sources || []} />
                    </div>
                )}

                {/* Actions bar (assistant-only) */}
                {!isUser && meta && meta.actions && (meta.actions as any[]).length > 0 && (
                    <div className="mt-2">
                        <NaviActionsBar
                            actions={meta.actions || []}
                            repoPath={
                                (message as NaviChatMessageIntent).repoPath ?? undefined
                            }
                            branch={(message as NaviChatMessageIntent).branch ?? undefined}
                            onActionResult={handleActionResult}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};

const TextMessageBubble: React.FC<{
    message: NaviChatMessageText;
    isUser: boolean;
}> = ({ message }) => {
    return (
        <div className="text-[13px]">
            <NaviMarkdown>{message.text}</NaviMarkdown>
        </div>
    );
};

const IntentMessageBubble: React.FC<{
    message: NaviChatMessageIntent;
    isUser: boolean;
}> = ({ message }) => {
    const { intent, text, repoPath, branch } = message;

    return (
        <div className="flex flex-col gap-2">
            {/* Optional explanation text from Navi */}
            {text && (
                <div className="text-[13px]">
                    <NaviMarkdown>{text}</NaviMarkdown>
                </div>
            )}

            {/* Intent-specific attachments */}
            {intent === "CHECK_ERRORS_AND_FIX" && (
                <div className="mt-1">
                    <NaviCheckErrorsAndFixPanel
                        repoPath={repoPath}
                        branch={branch}
                        autoStart={true}
                    />
                </div>
            )}

            {/* Fallback for unknown intents */}
            {intent !== "CHECK_ERRORS_AND_FIX" && (
                <div className="mt-1 rounded-xl bg-slate-950/70 px-3 py-2 text-[11px] text-slate-300">
                    NAVI triggered intent&nbsp;
                    <span className="font-semibold text-slate-100">{intent}</span>. UI
                    rendering for this intent is not yet implemented.
                </div>
            )}
        </div>
    );
};
