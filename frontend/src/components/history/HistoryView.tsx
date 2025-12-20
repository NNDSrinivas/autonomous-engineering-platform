import React, { useEffect, useState } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import {
    ChatSessionSummary,
    createSession,
    listSessions,
    setActiveSessionId,
} from "../../utils/chatSessions";
import "./HistoryView.css";

const formatLastUsed = (iso: string) => {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "Unknown time";
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 60_000) return "Just now";
    if (diffMs < 60 * 60_000) {
        const minutes = Math.max(1, Math.round(diffMs / 60_000));
        return `${minutes} min ago`;
    }
    const sameDay =
        date.toDateString() === now.toDateString();
    if (sameDay) {
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleDateString();
};

const getRepoLabel = (session: ChatSessionSummary) => {
    if (session.repoName) return session.repoName;
    if (!session.workspaceRoot) return "Unknown repo";
    const segments = session.workspaceRoot.split(/[\\/]/).filter(Boolean);
    return segments[segments.length - 1] || "Unknown repo";
};

type HistoryViewProps = {
    onSelectSession?: () => void;
};

export default function HistoryView({ onSelectSession }: HistoryViewProps) {
    const { workspaceRoot, repoName } = useWorkspace();
    const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);

    useEffect(() => {
        setSessions(listSessions());
    }, []);

    const openSession = (id: string) => {
        setActiveSessionId(id);
        onSelectSession?.();
    };

    const handleNewChat = () => {
        const session = createSession({
            repoName: repoName || undefined,
            workspaceRoot: workspaceRoot || undefined,
        });
        setSessions(listSessions());
        setActiveSessionId(session.id);
        onSelectSession?.();
    };

    return (
        <div className="navi-history-root">
            <div className="navi-history-header">
                <div className="navi-history-header-row">
                    <div>
                        <h2 className="navi-history-title">History</h2>
                        <p className="navi-history-subtitle">
                            Browse past Navi sessions and reopen them.
                        </p>
                    </div>
                    <button
                        type="button"
                        className="navi-pill navi-pill--primary"
                        onClick={handleNewChat}
                    >
                        New chat
                    </button>
                </div>
            </div>

            {sessions.length === 0 ? (
                <div className="navi-history-empty">
                    No saved sessions yet. Start a new chat to create one.
                </div>
            ) : (
                <div className="navi-history-list">
                    {sessions.map((s) => (
                        <div
                            key={s.id}
                            className="navi-history-card"
                            onClick={() => openSession(s.id)}
                        >
                            <div className="navi-history-main">
                                <div className="navi-history-title-row">
                                    <span className="navi-history-session-title">
                                        {s.title || "New chat"}
                                    </span>
                                    <span className="navi-history-token">
                                        {s.messageCount} msgs
                                    </span>
                                </div>
                                <div className="navi-history-repo">{getRepoLabel(s)}</div>
                                <div className="navi-history-meta">
                                    {formatLastUsed(s.updatedAt)} • {s.messageCount} messages
                                </div>
                                {s.lastMessagePreview && (
                                    <div className="navi-history-preview">
                                        {s.lastMessagePreview}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
