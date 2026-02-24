import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["out/", "dist/", "node_modules/", "webview/"],
  },
  {
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
