// src/components/navi/chat/NaviChatMessage.tsx
import React from "react";
import type {
    NaviChatMessage,
} from "../../../types/naviChat";
import { NaviActionsBar } from "../NaviActionsBar";
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
}) => {
    const isUser = message.role === "user";

    const handleActionClick = (actionId: string) => {
        console.log("[NAVI] Action clicked:", actionId);
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
                <div className="text-[13px]">
                    <NaviMarkdown content={message.content} />
                </div>

                {/* Actions bar (assistant-only) */}
                {!isUser && message.actions && message.actions.length > 0 && (
                    <div className="mt-2">
                        <NaviActionsBar
                            actions={message.actions}
                            onActionClick={handleActionClick}
                        />
                    </div>
                )}
            </div>
        </div>
    );
};
;;
