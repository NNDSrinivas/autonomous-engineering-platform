import React from "react";
import Link from "next/link";
import { LayoutDashboard, MessageSquare, FolderKanban, Settings, Sparkles } from "lucide-react";

const appNav = [
  { href: "/app", label: "Overview", icon: LayoutDashboard },
  { href: "/app/chats", label: "Chats", icon: MessageSquare },
  { href: "/app/projects", label: "Projects", icon: FolderKanban },
  { href: "/app/settings", label: "Settings", icon: Settings },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto grid min-h-screen max-w-[1400px] grid-cols-1 lg:grid-cols-[240px_1fr]">
        <aside className="border-r border-border/70 bg-card/55 backdrop-blur-md">
          <div className="sticky top-0 flex h-full flex-col p-5">
            <Link href="/app" className="mb-8 inline-flex items-center gap-3">
              <img
                src="/navi-logo.svg"
                alt="NAVI"
                className="h-9 w-9 rounded-full object-contain"
              />
              <div>
                <div className="text-sm font-semibold tracking-wide">NAVI</div>
                <div className="text-xs text-muted-foreground">Web App</div>
              </div>
            </Link>

            <nav className="space-y-1.5">
              {appNav.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className="group flex items-center gap-2.5 rounded-lg border border-transparent px-3 py-2 text-sm text-muted-foreground transition hover:border-primary/30 hover:bg-primary/5 hover:text-foreground"
                >
                  <Icon className="h-4 w-4" />
                  <span>{label}</span>
                </Link>
              ))}
            </nav>

            <div className="mt-auto rounded-xl border border-border/70 bg-secondary/20 p-3 text-xs text-muted-foreground">
              <div className="mb-1 inline-flex items-center gap-1.5 text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                Authenticated workspace
              </div>
              Browser app shell is now live for extension handoff continuity.
            </div>
          </div>
        </aside>

        <div className="flex min-h-screen flex-col">
          <header className="border-b border-border/70 bg-card/45 px-6 py-4 backdrop-blur-md">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h1 className="text-lg font-semibold tracking-tight">NAVI Workspace</h1>
                <p className="text-sm text-muted-foreground">Authenticated workspace shell</p>
              </div>
              <div className="flex items-center gap-3">
                <Link href="/profile" className="text-sm text-muted-foreground transition hover:text-foreground">
                  Profile
                </Link>
                <a
                  href="/api/auth/logout"
                  className="inline-flex items-center rounded-md border border-border bg-secondary/30 px-3 py-1.5 text-sm transition hover:bg-secondary/55"
                >
                  Sign out
                </a>
              </div>
            </div>
          </header>

          <main className="flex-1 p-6 lg:p-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
