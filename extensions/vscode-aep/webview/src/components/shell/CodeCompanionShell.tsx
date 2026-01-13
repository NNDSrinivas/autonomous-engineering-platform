import React, { useState } from "react";
import {
  LayoutGrid,
  GitBranch,
  History,
  Plus,
  Settings,
  UserCircle2,
  Link,
  Activity,
  Search,
  Zap,
  ClipboardList,
  Shield,
  Bell,
  Workflow,
  BarChart3,
} from "lucide-react";
import { ConnectorsPanel } from "../connectors/ConnectorsPanel";
import NaviChatPanel from "../navi/NaviChatPanel";
import { ActivityPanel } from "../ActivityPanel";
import { useActivityPanel } from "../../hooks/useActivityPanel";

type SidebarItem = {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick?: () => void;
};

export function CodeCompanionShell() {
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [activityPanelOpen, setActivityPanelOpen] = useState(false);

  const activityPanelState = useActivityPanel();

  const sidebarItems: SidebarItem[] = [
    { id: "home", label: "Home", icon: LayoutGrid },
    { id: "tasks", label: "Tasks", icon: ClipboardList },
    { id: "activity", label: "Activity", icon: Activity, onClick: () => setActivityPanelOpen(!activityPanelOpen) },
    { id: "search", label: "Search", icon: Search },
    { id: "workflow", label: "Workflow", icon: Workflow },
    { id: "insights", label: "Insights", icon: BarChart3 },
  ];

  return (
    <div className="aep-webview-container bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="flex h-full flex-col">
        <header className="sticky top-0 z-40 flex h-14 items-center gap-4 border-b border-white/10 bg-slate-950/80 px-5 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-violet-500 text-slate-900">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-wide">NAVI</div>
              <div className="text-[11px] text-slate-400">Autonomous Engineering Intelligence</div>
            </div>
          </div>

          <div className="flex-1" />

          <div className="flex items-center gap-2 text-slate-200">
            <button
              className="rounded-lg border border-white/10 bg-white/5 p-2 hover:bg-white/10"
              title="Connectors"
              onClick={() => setConnectorsOpen(true)}
            >
              <Link className="h-4 w-4" />
            </button>
            <button
              className="rounded-lg border border-white/10 bg-white/5 p-2 hover:bg-white/10"
              title="History"
            >
              <History className="h-4 w-4" />
            </button>
            <button
              className="rounded-lg border border-white/10 bg-white/5 p-2 hover:bg-white/10"
              title="New Chat"
            >
              <Plus className="h-4 w-4" />
            </button>
            <button
              className="rounded-lg border border-white/10 bg-white/5 p-2 hover:bg-white/10"
              title="Settings"
            >
              <Settings className="h-4 w-4" />
            </button>
            <button
              className="rounded-lg border border-white/10 bg-white/5 p-2 hover:bg-white/10"
              title="Profile"
            >
              <UserCircle2 className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          <aside className="flex w-16 flex-col items-center gap-3 border-r border-white/10 bg-slate-950/40 py-4">
            {sidebarItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/5 bg-white/5 text-slate-300 hover:bg-white/10"
                  title={item.label}
                  onClick={item.onClick}
                >
                  <Icon className="h-4 w-4" />
                </button>
              );
            })}

            <div className="mt-auto flex flex-col items-center gap-3">
              <button
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/5 bg-white/5 text-slate-300 hover:bg-white/10"
                title="Approvals"
              >
                <Shield className="h-4 w-4" />
              </button>
              <button
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/5 bg-white/5 text-slate-300 hover:bg-white/10"
                title="Notifications"
              >
                <Bell className="h-4 w-4" />
              </button>
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/5 bg-white/5 text-slate-400"
                title="Branch"
              >
                <GitBranch className="h-4 w-4" />
              </div>
            </div>
          </aside>

          <main className="flex min-h-0 flex-1 flex-col px-6 py-6">
            <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
              <div className="flex min-h-0 flex-1 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60 shadow-2xl">
                <NaviChatPanel activityPanelState={activityPanelState} />
              </div>
              {activityPanelOpen && (
                <div className="w-96 flex-shrink-0">
                  <ActivityPanel
                    steps={activityPanelState.steps}
                    currentStep={activityPanelState.currentStep}
                    onFileClick={(filePath) => {
                      // Send message to VSCode to open the file
                      window.vscode?.postMessage({
                        type: 'openFile',
                        filePath: filePath
                      });
                    }}
                    onAcceptAll={() => {
                      // Handle accept all changes
                      console.log('Accept all changes');
                    }}
                    onRejectAll={() => {
                      // Handle reject all changes
                      console.log('Reject all changes');
                    }}
                  />
                </div>
              )}
            </div>
          </main>
        </div>
      </div>

      <ConnectorsPanel open={connectorsOpen} onClose={() => setConnectorsOpen(false)} />
    </div>
  );
}
