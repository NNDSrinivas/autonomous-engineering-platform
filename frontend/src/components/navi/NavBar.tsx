import React from "react";
import "./NavBar.css";

export type NaviMode = "task" | "memory" | "plan" | "search";

const MODE_LABELS: Record<NaviMode, string> = {
    task: "Task Concierge",
    memory: "Memory Graph",
    plan: "Live Plan Mode",
    search: "RAG Search",
};

type NavBarProps = {
    mode: NaviMode;
    onModeChange?: (mode: NaviMode) => void;
};

const ALL_MODES: NaviMode[] = ["task", "memory", "plan", "search"];

const NavBar: React.FC<NavBarProps> = ({ mode, onModeChange }) => {
    const [menuOpen, setMenuOpen] = React.useState(false);

    const handleSelect = (next: NaviMode) => {
        setMenuOpen(false);
        if (next !== mode && onModeChange) {
            onModeChange(next);
        }
    };

    return (
        <header className="navi-header">
            <div className="navi-header-left">
                <div className="navi-logo-orb" />
                <div className="navi-title-block">
                    <div className="navi-title">NAVI</div>
                    <div className="navi-subtitle">
                        Autonomous Engineering Platform
                    </div>
                </div>
            </div>

            <div className="navi-header-right">
                <div
                    className="navi-mode-pill"
                    onClick={() => setMenuOpen((prev) => !prev)}
                >
                    <span className="navi-mode-dot" />
                    <span className="navi-mode-label">{MODE_LABELS[mode]}</span>
                    <span className="navi-mode-chevron">▾</span>
                </div>

                {menuOpen && (
                    <div className="navi-mode-menu">
                        {ALL_MODES.map((m) => (
                            <button
                                key={m}
                                type="button"
                                className={
                                    "navi-mode-item" + (m === mode ? " navi-mode-item--active" : "")
                                }
                                onClick={() => handleSelect(m)}
                            >
                                {MODE_LABELS[m]}
                                {m === mode && <span className="navi-mode-item-badge">Active</span>}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </header>
    );
};

export default NavBar;
