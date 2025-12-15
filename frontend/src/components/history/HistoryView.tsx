import React, { useState } from "react";
import "./HistoryView.css";

const vscodeApi =
    typeof acquireVsCodeApi !== "undefined" ? acquireVsCodeApi() : null;

interface SessionSummary {
    id: string;
    title: string;
    repo: string;
    lastUsed: string;
    messages: number;
    tokenCostUsd: number;
}

const MOCK_SESSIONS: SessionSummary[] = [
    {
        id: "1",
        title: "Fix TypeScript errors",
        repo: "navra-labs/aep",
        lastUsed: "Today, 3:12 PM",
        messages: 18,
        tokenCostUsd: 0.42,
    },
    {
        id: "2",
        title: "Explain SignCollection flow",
        repo: "oracle/specimen-collection-service",
        lastUsed: "Yesterday, 9:04 PM",
        messages: 11,
        tokenCostUsd: 0.19,
    },
];

export default function HistoryView() {
    const [sessions] = useState<SessionSummary[]>(MOCK_SESSIONS);

    const openSession = (id: string) => {
        vscodeApi?.postMessage({ type: "navi.openSession", id });
    };

    return (
        <div className="navi-history-root">
            <div className="navi-history-header">
                <h2 className="navi-history-title">History</h2>
                <p className="navi-history-subtitle">
                    Browse past Navi sessions with token cost and reopen them.
                </p>
            </div>

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
                                    {s.title}
                                </span>
                                <span className="navi-history-token">
                                    ${s.tokenCostUsd.toFixed(2)}
                                </span>
                            </div>
                            <div className="navi-history-repo">{s.repo}</div>
                            <div className="navi-history-meta">
                                {s.lastUsed} • {s.messages} messages
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
