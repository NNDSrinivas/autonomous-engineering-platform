import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    include: ["backend/tests/**/*.test.ts"],
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/*.spec.ts", // Exclude Playwright specs
      "tests/e2e/**", // Exclude e2e tests
      "frontend/tests/**", // Exclude frontend Playwright tests
      "extensions/**/*.test.ts" // Exclude extension tests (they use Jest)
    ],
    environment: "node"
  }
});
