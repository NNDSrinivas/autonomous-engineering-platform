import fs from "node:fs";
import path from "node:path";
import Ajv from "ajv";

function readJson(p: string) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function validateOne(schemaPath: string, policyPath: string) {
  const schema = readJson(schemaPath);
  const policy = readJson(policyPath);

  const ajv = new Ajv({ allErrors: true, strict: true });
  const validate = ajv.compile(schema);
  const ok = validate(policy);

  if (!ok) {
    console.error(`❌ Budget policy invalid: ${policyPath}`);
    console.error(validate.errors);
    process.exit(1);
  }

  // Extra guardrail (fail-closed)
  if (policy.day_boundary !== "UTC") {
    console.error(`❌ day_boundary must be "UTC": ${policyPath}`);
    process.exit(1);
  }

  console.log(`✅ Budget policy valid: ${policyPath}`);
}

function main() {
  const repoRoot = process.cwd();
  const schemaPath = path.join(repoRoot, "shared", "budget-policy.schema.json");

  const policies = [
    path.join(repoRoot, "shared", "budget-policy-dev.json"),
    path.join(repoRoot, "shared", "budget-policy-staging.json"),
    path.join(repoRoot, "shared", "budget-policy-prod.json")
  ];

  for (const p of policies) {
    if (!fs.existsSync(p)) {
      console.error(`❌ Missing policy file: ${p}`);
      process.exit(1);
    }
    validateOne(schemaPath, p);
  }
}

main();
