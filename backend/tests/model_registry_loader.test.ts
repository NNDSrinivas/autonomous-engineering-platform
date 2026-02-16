import fs from "node:fs";
import path from "node:path";

import { loadModelRegistry, ModelRegistryError } from "../services/model_registry_loader";
import type { ModelRegistryFile } from "../services/model_registry_types";

function tmpDir(): string {
  const d = path.join(process.cwd(), ".tmp-registry-loader-tests");
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function writeJson(p: string, content: unknown): void {
  fs.writeFileSync(p, JSON.stringify(content, null, 2), "utf8");
}

function loadSchemaFromRepo(): object {
  const schemaPath = path.join(process.cwd(), "shared", "model-registry.schema.json");
  return JSON.parse(fs.readFileSync(schemaPath, "utf8"));
}

function minimalRegistry(overrides: Partial<ModelRegistryFile>): ModelRegistryFile {
  return {
    schemaVersion: 1,
    environment: "dev",
    generatedAt: new Date().toISOString(),
    models: [
      {
        id: "openai/gpt-4o",
        provider: "openai",
        displayName: "GPT-4o",
        enabled: true,
        productionApproved: true,
        capabilities: ["chat", "json", "streaming"],
        pricing: { currency: "USD", inputPer1KTokens: 0.0025, outputPer1KTokens: 0.01 },
        limits: { maxInputTokens: 8192, maxOutputTokens: 2048 },
        governance: { tier: "standard", allowedEnvironments: ["dev", "staging", "prod"] }
      }
    ],
    ...overrides
  };
}

describe("model_registry_loader", () => {
  test("fails when registry env != runtime env", () => {
    const d = tmpDir();
    const schemaPath = path.join(d, "schema.json");
    const regPath = path.join(d, "registry.json");

    writeJson(schemaPath, loadSchemaFromRepo());
    writeJson(regPath, minimalRegistry({ environment: "dev" }));

    expect(() =>
      loadModelRegistry({
        registryPath: regPath,
        schemaPath,
        runtimeEnv: "prod"
      })
    ).toThrow(/ENVIRONMENT_MISMATCH|environment/i);
  });

  test("fails in prod when enabled model lacks productionApproved", () => {
    const d = tmpDir();
    const schemaPath = path.join(d, "schema.json");
    const regPath = path.join(d, "registry.json");

    writeJson(schemaPath, loadSchemaFromRepo());
    const reg = minimalRegistry({
      environment: "prod",
      models: [
        {
          ...(minimalRegistry({}).models[0] as any),
          productionApproved: false
        }
      ]
    });

    writeJson(regPath, reg);

    expect(() =>
      loadModelRegistry({
        registryPath: regPath,
        schemaPath,
        runtimeEnv: "prod",
        strictProdApproval: true
      })
    ).toThrow(/PRODUCTION_UNAPPROVED_MODEL|productionApproved=false/i);
  });

  test("fails if model present but not allowed in env", () => {
    const d = tmpDir();
    const schemaPath = path.join(d, "schema.json");
    const regPath = path.join(d, "registry.json");

    writeJson(schemaPath, loadSchemaFromRepo());
    writeJson(
      regPath,
      minimalRegistry({
        environment: "staging",
        models: [
          {
            ...(minimalRegistry({}).models[0] as any),
            governance: { tier: "standard", allowedEnvironments: ["prod"] }
          }
        ]
      })
    );

    expect(() =>
      loadModelRegistry({
        registryPath: regPath,
        schemaPath,
        runtimeEnv: "staging"
      })
    ).toThrow(/MODEL_NOT_ALLOWED_IN_ENVIRONMENT|not allowed/i);
  });

  test("blocks duplicate model IDs", () => {
    const d = tmpDir();
    const schemaPath = path.join(d, "schema.json");
    const regPath = path.join(d, "registry.json");

    writeJson(schemaPath, loadSchemaFromRepo());
    const base = minimalRegistry({});
    writeJson(regPath, {
      ...base,
      models: [base.models[0], base.models[0]]
    });

    expect(() =>
      loadModelRegistry({
        registryPath: regPath,
        schemaPath,
        runtimeEnv: "dev"
      })
    ).toThrow(/DUPLICATE_MODEL_ID|Duplicate model/i);
  });

  test("returns deterministic sorted models", () => {
    const d = tmpDir();
    const schemaPath = path.join(d, "schema.json");
    const regPath = path.join(d, "registry.json");

    writeJson(schemaPath, loadSchemaFromRepo());

    const reg = minimalRegistry({
      models: [
        {
          id: "openai/gpt-4o",
          provider: "openai",
          displayName: "GPT-4o",
          enabled: true,
          productionApproved: true,
          capabilities: ["chat"],
          pricing: { currency: "USD", inputPer1KTokens: 0.0025, outputPer1KTokens: 0.01 },
          limits: { maxInputTokens: 8192, maxOutputTokens: 2048 },
          governance: { tier: "standard", allowedEnvironments: ["dev", "staging", "prod"] }
        },
        {
          id: "anthropic/claude-sonnet-4",
          provider: "anthropic",
          displayName: "Claude Sonnet",
          enabled: true,
          productionApproved: true,
          capabilities: ["chat"],
          pricing: { currency: "USD", inputPer1KTokens: 0.003, outputPer1KTokens: 0.015 },
          limits: { maxInputTokens: 8192, maxOutputTokens: 2048 },
          governance: { tier: "standard", allowedEnvironments: ["dev", "staging", "prod"] }
        }
      ]
    });

    writeJson(regPath, reg);

    const { models } = loadModelRegistry({
      registryPath: regPath,
      schemaPath,
      runtimeEnv: "dev"
    });

    expect(models.map(m => m.id)).toEqual([
      "anthropic/claude-sonnet-4",
      "openai/gpt-4o"
    ]);
  });
});
