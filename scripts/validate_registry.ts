#!/usr/bin/env node
import path from "node:path";
import { loadModelRegistry } from "../backend/services/model_registry_loader";
import type { RegistryEnvironment } from "../backend/services/model_registry_types";

function resolveRepoPath(p: string): string {
  return path.resolve(process.cwd(), p);
}

function getEnv(): RegistryEnvironment {
  // Use APP_ENV (Python standard) for consistency
  const env = (process.env.APP_ENV ?? process.env.NAVI_ENV ?? "dev").toLowerCase();
  if (env !== "dev" && env !== "staging" && env !== "prod") return "dev";
  return env as RegistryEnvironment;
}

function getRegistryPath(env: RegistryEnvironment): string {
  const direct = process.env.MODEL_REGISTRY_PATH;
  if (direct && direct.trim().length > 0) return direct;

  // Default mapping per environment
  if (env === "dev") return "shared/model-registry-dev.json";
  if (env === "staging") return "shared/model-registry-staging.json";
  return "shared/model-registry-prod.json";
}

function main(): void {
  const runtimeEnv = getEnv();
  const auditMode = process.env.PROD_READINESS_AUDIT === "1";

  const schemaPath = resolveRepoPath("shared/model-registry.schema.json");
  const registryPath = resolveRepoPath(getRegistryPath(runtimeEnv));

  try {
    const { registry, models } = loadModelRegistry({
      registryPath,
      schemaPath,
      runtimeEnv,
      strictProdApproval: true,
      auditMode
    });

    const approved = models.filter(m => m.productionApproved).length;
    const unapproved = models.length - approved;

    console.log(
      `✅ Registry OK | env=${runtimeEnv} | schemaVersion=${registry.schemaVersion} | models=${models.length} | approved=${approved} | unapproved=${unapproved}`
    );

    if (auditMode) {
      console.log("[AUDIT] Loaded model IDs:");
      for (const m of models) console.log(`  - ${m.id}`);
    }

    process.exit(0);
  } catch (err: any) {
    const msg = err?.message ? String(err.message) : String(err);
    console.error(`❌ Registry validation failed | env=${runtimeEnv} | ${msg}`);
    process.exit(1);
  }
}

main();
