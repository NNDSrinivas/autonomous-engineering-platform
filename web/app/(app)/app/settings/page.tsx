import React from "react";
import { Bell, Shield, Globe } from "lucide-react";

const settingsItems = [
  {
    title: "Notifications",
    description: "Control alerts for long-running operations and approvals.",
    icon: Bell,
  },
  {
    title: "Security",
    description: "Manage session policy, trusted devices, and account posture.",
    icon: Shield,
  },
  {
    title: "Workspace Defaults",
    description: "Set default model routing and environment preferences.",
    icon: Globe,
  },
];

export default function AppSettingsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Settings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Account and workspace controls for browser sessions.
        </p>
      </header>

      <div className="space-y-3">
        {settingsItems.map(({ title, description, icon: Icon }) => (
          <section key={title} className="rounded-xl border border-border/70 bg-card/35 p-5">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-foreground/90">{title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{description}</p>
              </div>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
