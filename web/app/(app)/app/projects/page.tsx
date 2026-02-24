import React from "react";
import { FolderKanban, Shield, Cpu } from "lucide-react";

const projects = [
  {
    name: "NAVI Extension",
    owner: "Platform Engineering",
    posture: "Compliant",
    route: "Multi-model routing active",
  },
  {
    name: "Web Workspace",
    owner: "Product Engineering",
    posture: "Monitoring",
    route: "Guardrails and approval gates enabled",
  },
  {
    name: "Enterprise Rollout",
    owner: "Solutions",
    posture: "Planning",
    route: "Readiness review in progress",
  },
];

export default function AppProjectsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold tracking-tight">Projects</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Governance-oriented workspace for project state, policy posture, and routing strategy.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects.map((project) => (
          <article key={project.name} className="rounded-xl border border-border/70 bg-card/35 p-5">
            <div className="mb-3 inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
              <FolderKanban className="h-4 w-4" />
            </div>
            <h3 className="text-base font-semibold">{project.name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{project.owner}</p>
            <div className="mt-4 space-y-2 text-sm">
              <div className="inline-flex items-center gap-1.5 text-foreground">
                <Shield className="h-3.5 w-3.5 text-primary" />
                {project.posture}
              </div>
              <div className="inline-flex items-center gap-1.5 text-muted-foreground">
                <Cpu className="h-3.5 w-3.5" />
                {project.route}
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
