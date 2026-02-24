import React from "react";
import Link from "next/link";
import { Activity, ShieldCheck, GitBranch, Compass } from "lucide-react";

const cards = [
  {
    title: "Workspace health",
    value: "Healthy",
    detail: "Policies, auth, and runtime checks are active.",
    icon: ShieldCheck,
  },
  {
    title: "Active sessions",
    value: "1",
    detail: "Your authenticated browser session is ready.",
    icon: Activity,
  },
  {
    title: "Projects",
    value: "Explore",
    detail: "Move to project control surfaces and governance views.",
    icon: GitBranch,
  },
  {
    title: "Roadmap",
    value: "Phase 1",
    detail: "Shell and auth are live; chat/tools parity is next.",
    icon: Compass,
  },
];

export default function AppOverviewPage() {
  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-border/70 bg-card/40 p-6 lg:p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-primary">NAVI Browser Workspace</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight">Enterprise shell is live</h2>
        <p className="mt-3 max-w-3xl text-muted-foreground">
          This authenticated browser surface is the canonical destination for extension signup handoff and upcoming
          cross-device chat/tool continuity.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href="/app/chats" className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            Open chats
          </Link>
          <Link href="/app/projects" className="rounded-md border border-border px-4 py-2 text-sm text-foreground">
            View projects
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ title, value, detail, icon: Icon }) => (
          <article key={title} className="rounded-xl border border-border/70 bg-card/35 p-5">
            <div className="mb-3 inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Icon className="h-4 w-4" />
            </div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="mt-1 text-xl font-semibold tracking-tight">{value}</p>
            <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
