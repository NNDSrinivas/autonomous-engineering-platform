#!/usr/bin/env node
/**
 * Budget Policy Validator
 *
 * Fail-closed validation of budget policy files against JSON Schema.
 * Runs at startup to prevent deployment of invalid budget configurations.
 *
 * Usage:
 *   tsx scripts/validate_budget_policy.ts
 *   APP_ENV=prod tsx scripts/validate_budget_policy.ts
 */

import fs from "node:fs";
import path from "node:path";
import Ajv from "ajv";
import addFormats from "ajv-formats";

type Environment = "dev" | "staging" | "prod";

interface BudgetPolicy {
  version: number;
  day_boundary: string;
  units: string;
  defaults: {
    per_day: number;
  };
  orgs?: Record<string, { per_day: number; tags?: string[] }>;
  users?: Record<string, { per_day: number }>;
  providers?: Record<string, { per_day: number }>;
  models?: Record<string, { per_day: number }>;
}

function resolveRepoPath(p: string): string {
  return path.resolve(process.cwd(), p);
}

function getEnv(): Environment {
  const env = (process.env.APP_ENV ?? "dev").toLowerCase();
  if (env !== "dev" && env !== "staging" && env !== "prod") {
    console.warn(`⚠️  Unknown APP_ENV="${env}", defaulting to "dev"`);
    return "dev";
  }
  return env as Environment;
}

function getPolicyPath(env: Environment): string {
  const direct = process.env.BUDGET_POLICY_PATH;
  if (direct && direct.trim().length > 0) {
    return direct;
  }

  // Default mapping per environment
  if (env === "dev") return "shared/budget-policy-dev.json";
  if (env === "staging") return "shared/budget-policy-staging.json";
  return "shared/budget-policy-prod.json";
}

function validatePolicy(
  schemaPath: string,
  policyPath: string,
  env: Environment
): void {
  // Load schema and policy
  const schemaRaw = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const policyRaw = JSON.parse(fs.readFileSync(policyPath, "utf8"));

  // Validate against JSON Schema
  const ajv = new Ajv({ allErrors: true, strict: true });
  addFormats(ajv);

  const validate = ajv.compile<BudgetPolicy>(schemaRaw);
  const ok = validate(policyRaw);

  if (!ok) {
    const errors = validate.errors || [];
    const msg = errors.map((e) => `  ${e.instancePath}: ${e.message}`).join("\n");
    console.error(`❌ Budget policy validation failed | env=${env}`);
    console.error(`\nSchema violations:\n${msg}\n`);
    process.exit(1);
  }

  const policy: BudgetPolicy = policyRaw;

  // Extra guard rail: day_boundary must be UTC
  if (policy.day_boundary !== "UTC") {
    console.error(
      `❌ Budget policy validation failed | env=${env} | ` +
      `day_boundary must be "UTC", got "${policy.day_boundary}"`
    );
    process.exit(1);
  }

  // Count defined scopes
  const orgCount = Object.keys(policy.orgs || {}).length;
  const userCount = Object.keys(policy.users || {}).length;
  const providerCount = Object.keys(policy.providers || {}).length;
  const modelCount = Object.keys(policy.models || {}).length;

  console.log(
    `✅ Budget policy OK | env=${env} | ` +
    `version=${policy.version} | ` +
    `units=${policy.units} | ` +
    `default=${policy.defaults.per_day} | ` +
    `orgs=${orgCount} | ` +
    `users=${userCount} | ` +
    `providers=${providerCount} | ` +
    `models=${modelCount}`
  );

  // Audit mode output
  if (process.env.PROD_READINESS_AUDIT === "1") {
    console.log("\n[AUDIT] Budget Policy Scope Breakdown:");
    console.log(`  Default daily limit: ${policy.defaults.per_day} ${policy.units}`);

    if (orgCount > 0) {
      console.log(`  Organizations (${orgCount}):`);
      for (const [orgId, cfg] of Object.entries(policy.orgs || {})) {
        const tags = cfg.tags ? ` [${cfg.tags.join(", ")}]` : "";
        console.log(`    - ${orgId}: ${cfg.per_day} ${policy.units}${tags}`);
      }
    }

    if (providerCount > 0) {
      console.log(`  Providers (${providerCount}):`);
      for (const [providerId, cfg] of Object.entries(policy.providers || {})) {
        console.log(`    - ${providerId}: ${cfg.per_day} ${policy.units}`);
      }
    }

    if (modelCount > 0) {
      console.log(`  Models (${modelCount}):`);
      for (const [modelId, cfg] of Object.entries(policy.models || {})) {
        console.log(`    - ${modelId}: ${cfg.per_day} ${policy.units}`);
      }
    }
  }
}

function main(): void {
  const env = getEnv();
  const schemaPath = resolveRepoPath("shared/budget-policy.schema.json");
  const policyPath = resolveRepoPath(getPolicyPath(env));

  // Check files exist
  if (!fs.existsSync(schemaPath)) {
    console.error(`❌ Schema not found: ${schemaPath}`);
    process.exit(1);
  }

  if (!fs.existsSync(policyPath)) {
    if (env === "prod") {
      // Fail-closed in production
      console.error(
        `❌ Budget policy not found | env=${env} | path=${policyPath}\n` +
        `FATAL: Production requires explicit budget policy file (fail-closed, no fallback)`
      );
      process.exit(1);
    } else {
      // Allow fallback to dev in non-prod
      console.warn(
        `⚠️  Budget policy not found for env=${env}, falling back to dev policy`
      );
      const fallbackPath = resolveRepoPath("shared/budget-policy-dev.json");
      if (!fs.existsSync(fallbackPath)) {
        console.error(`❌ Fallback dev policy not found: ${fallbackPath}`);
        process.exit(1);
      }
      validatePolicy(schemaPath, fallbackPath, env);
      return;
    }
  }

  try {
    validatePolicy(schemaPath, policyPath, env);
    process.exit(0);
  } catch (err: any) {
    const msg = err?.message ? String(err.message) : String(err);
    console.error(`❌ Budget policy validation failed | env=${env} | ${msg}`);
    process.exit(1);
  }
}

main();
