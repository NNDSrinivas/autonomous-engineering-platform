import React from "react";
import { MessageCircle, Clock3, ArrowRight } from "lucide-react";

const chatRows = [
  { title: "Repo onboarding plan", when: "Updated 2h ago", status: "Ready" },
  { title: "Security policy review", when: "Updated yesterday", status: "Needs follow-up" },
  { title: "Release checklist generation", when: "Updated 3 days ago", status: "Completed" },
];

export default function AppChatsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Chats</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Conversation history and multi-surface continuity will be expanded in Phase 2.
        </p>
      </header>

      <section className="rounded-xl border border-border/70 bg-card/35">
        {chatRows.map((row) => (
          <div
            key={row.title}
            className="flex items-center justify-between gap-4 border-b border-border/60 px-5 py-4 last:border-b-0"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
                <MessageCircle className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{row.title}</p>
                <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock3 className="h-3.5 w-3.5" />
                  {row.when}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                {row.status}
              </span>
              <button className="inline-flex items-center gap-1 text-xs text-primary">
                Open <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
