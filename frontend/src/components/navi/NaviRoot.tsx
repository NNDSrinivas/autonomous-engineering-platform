import React, { useState, useEffect } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import NaviChatPanel from "./NaviChatPanel";
import ConnectionsView from "../connections/ConnectionsView";
import HistoryView from "../history/HistoryView";
import AccountView from "../account/AccountView";
import "./NaviRoot.css";

type NaviView = "chat" | "connections" | "history" | "account";

export default function NaviRoot() {
  const { workspaceRoot, repoName, isLoading } = useWorkspace();
  const [activeView, setActiveView] = useState<NaviView>("chat");

  // Debug log whenever workspace context changes
  useEffect(() => {
    const currentUrl = window.location.href;
    const urlParams = new URLSearchParams(window.location.search);
    const workspaceParam = urlParams.get('workspaceRoot');

    console.log('[NaviRoot] 📍 URL Analysis:', {
      fullUrl: currentUrl,
      searchParams: window.location.search,
      workspaceFromUrl: workspaceParam,
      contextWorkspaceRoot: workspaceRoot,
      contextRepoName: repoName,
      contextIsLoading: isLoading,
    });
  }, [workspaceRoot, repoName, isLoading]);

  return (
    <div className="navi-root">
      <aside className="navi-sidebar">
        <SidebarButton
          label="Chat"
          icon="💬"
          active={activeView === "chat"}
          onClick={() => setActiveView("chat")}
        />
        <SidebarButton
          label="Connections"
          icon="🔌"
          active={activeView === "connections"}
          onClick={() => setActiveView("connections")}
        />
        <SidebarButton
          label="History"
          icon="🕒"
          active={activeView === "history"}
          onClick={() => setActiveView("history")}
        />
        <SidebarButton
          label="Account"
          icon="⚙️"
          active={activeView === "account"}
          onClick={() => setActiveView("account")}
        />
      </aside>

      <main className="navi-main">
        {activeView === "chat" && <NaviChatPanel />}
        {activeView === "connections" && <ConnectionsView />}
        {activeView === "history" && <HistoryView />}
        {activeView === "account" && <AccountView />}
      </main>
    </div>
  );
}

type SidebarButtonProps = {
  label: string;
  icon: string;
  active: boolean;
  onClick: () => void;
};

const SidebarButton: React.FC<SidebarButtonProps> = ({
  label,
  icon,
  active,
  onClick,
}) => {
  return (
    <button
      type="button"
      className={`navi-sidebar-btn ${active ? "navi-sidebar-btn--active" : ""}`}
      onClick={onClick}
      title={label}
    >
      <span className="navi-sidebar-icon" aria-hidden="true">
        {icon}
      </span>
    </button>
  );
};
