import Ajv from "ajv";
import addFormats from "ajv-formats";
import fs from "fs";
import path from "path";
import type {
  ModelRegistryFile,
  ModelRegistryEntry,
  RegistryEnvironment,
} from "./model_registry_types";

export class ModelRegistryError extends Error {
  constructor(
    public code: string,
    message: string
  ) {
    super(message);
    this.name = "ModelRegistryError";
  }
}

export interface LoadRegistryOptions {
  registryPath: string;
  schemaPath: string;
  runtimeEnv: RegistryEnvironment;
  strictProdApproval?: boolean;
  auditMode?: boolean;
}

export function loadModelRegistry(opts: LoadRegistryOptions): {
  registry: ModelRegistryFile;
  models: ModelRegistryEntry[];
} {
  const {
    registryPath,
    schemaPath,
    runtimeEnv,
    strictProdApproval = true,
    auditMode = false,
  } = opts;

  // 1. Load schema and registry files
  const schemaRaw = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const registryRaw = JSON.parse(fs.readFileSync(registryPath, "utf8"));

  // 2. Validate against JSON Schema (fail-closed)
  // Create fresh Ajv instance for each call to avoid schema ID conflicts in tests
  const ajv = new Ajv({ allErrors: true, strict: true, validateSchema: false });
  addFormats(ajv);
  const validate = ajv.compile<ModelRegistryFile>(schemaRaw);
  const ok = validate(registryRaw);
  if (!ok) {
    const errors = validate.errors || [];
    const msg = errors.map((e) => `${e.instancePath}: ${e.message}`).join("; ");
    throw new ModelRegistryError(
      "SCHEMA_VALIDATION_FAILED",
      `Registry failed schema validation: ${msg}`
    );
  }

  const registry: ModelRegistryFile = registryRaw;

  // 3. Environment binding (fail-closed)
  if (registry.environment !== runtimeEnv) {
    throw new ModelRegistryError(
      "ENVIRONMENT_MISMATCH",
      `Registry environment="${registry.environment}" but runtime="${runtimeEnv}"`
    );
  }

  // 4. Filter enabled models
  let models = registry.models.filter((m) => m.enabled);

  // 5. Assert all models allowed in this environment
  assertEnvironmentAllowed(models, runtimeEnv);

  // 6. Production approval gate (fail-closed in prod)
  if (strictProdApproval && runtimeEnv === "prod") {
    assertProdApproval(models);
  }

  // 7. Deprecation enforcement
  assertDeprecationConsistency(models);

  // 8. Duplicate ID check
  assertNoDuplicateIds(models);

  // 9. Deterministic sorting
  models = stableSortModels(models);

  if (auditMode) {
    console.log(
      `[AUDIT] Loaded ${models.length} models from ${registryPath} (env=${runtimeEnv})`
    );
  }

  return { registry, models };
}

function assertEnvironmentAllowed(
  models: ModelRegistryEntry[],
  env: RegistryEnvironment
): void {
  for (const m of models) {
    if (!m.governance.allowedEnvironments.includes(env)) {
      throw new ModelRegistryError(
        "MODEL_NOT_ALLOWED_IN_ENVIRONMENT",
        `Model ${m.id} not allowed in environment "${env}"`
      );
    }
  }
}

function assertProdApproval(models: ModelRegistryEntry[]): void {
  for (const m of models) {
    if (!m.productionApproved) {
      throw new ModelRegistryError(
        "PRODUCTION_UNAPPROVED_MODEL",
        `Model ${m.id} enabled in prod but productionApproved=false`
      );
    }
  }
}

function assertDeprecationConsistency(models: ModelRegistryEntry[]): void {
  for (const m of models) {
    if (m.deprecation?.status === "disabled") {
      throw new ModelRegistryError(
        "DEPRECATED_MODEL_ENABLED",
        `Model ${m.id} has deprecation.status="disabled" but is still enabled`
      );
    }
  }
}

function assertNoDuplicateIds(models: ModelRegistryEntry[]): void {
  const seen = new Set<string>();
  for (const m of models) {
    if (seen.has(m.id)) {
      throw new ModelRegistryError(
        "DUPLICATE_MODEL_ID",
        `Duplicate model ID: ${m.id}`
      );
    }
    seen.add(m.id);
  }
}

function stableSortModels(
  models: ModelRegistryEntry[]
): ModelRegistryEntry[] {
  return [...models].sort((a, b) => {
    if (a.provider !== b.provider) return a.provider.localeCompare(b.provider);
    return a.id.localeCompare(b.id);
  });
}
