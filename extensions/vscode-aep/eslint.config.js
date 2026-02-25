import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    // Ignore build outputs, dependencies, and webview directory
    // NOTE: webview/ contains React/TSX code with its own build process (Vite).
    // It uses different TypeScript configurations and globals (browser vs. Node.js).
    // Consider setting up a separate ESLint config for webview/ if linting is needed.
    ignores: ["out/", "dist/", "node_modules/", "webview/"],
  },
  {
    // Extension backend code (VS Code extension host, Node.js environment)
    files: ["src/**/*.ts"],
    extends: [tseslint.configs.recommended],
    languageOptions: {
      globals: {
        ...globals.node,
      },
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
        project: "./tsconfig.json",
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-require-imports": "off",
      "@typescript-eslint/naming-convention": "off",
      "prefer-const": "off",
      "no-case-declarations": "off",
      "curly": "off",
      "eqeqeq": "off",
      "no-throw-literal": "off",
      "semi": "off",
    },
  }
);
