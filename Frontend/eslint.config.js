// Revisión de estilo y errores probables del frontend: `npm run lint`.
// Los tipos los revisa TypeScript (`npm run typecheck`).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  // src/types/api.ts lo genera openapi-typescript (`npm run tipos`).
  { ignores: ["dist", "src/types/api.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Los parámetros que se ignoran a propósito empiezan con _.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Un contexto exporta su proveedor y su hook (useAuth), y routes.tsx el
    // router; ninguno se edita con recarga en caliente, así que el aviso no aplica.
    files: ["src/context/**/*.tsx", "src/routes.tsx"],
    rules: { "react-refresh/only-export-components": "off" },
  },
);
