import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  jsxA11y.flatConfigs.recommended,
  {
    rules: {
      // `PersonBadge` (and similar) take a domain prop literally named
      // `role` ("participant" / "moderator") that collides with the DOM
      // `role` ARIA attribute. `ignoreNonDOM` scopes the check to lowercase
      // DOM elements, so real `<div role="...">` typos are still caught
      // while custom-component props are left alone.
      "jsx-a11y/aria-role": ["error", { ignoreNonDOM: true }],
      // `role="separator"` with `aria-valuenow` is the WAI-ARIA focusable-
      // splitter / drag-resize-handle pattern (InspectorPanel grip,
      // SidebarLayout drag handles). The rule's default role list excludes
      // it; allow `separator` to accept `tabIndex={0}` on these handles.
      "jsx-a11y/no-noninteractive-tabindex": [
        "error",
        { roles: ["separator"] },
      ],
    },
  },
  {
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // React Compiler compatibility lints (eslint-plugin-react-hooks@7).
      // These flag patterns the React Compiler would optimise differently —
      // latest-value refs written during render, sync setState in mount
      // effects that derive initial state, in-place mutation of render-scoped
      // values. The project does NOT use the React Compiler, and these
      // patterns are established and working. Downgraded to `warn` so they
      // stay visible without blocking CI; revisit if/when we adopt the
      // compiler. The classic correctness rules (rules-of-hooks,
      // exhaustive-deps) are left untouched.
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
    },
  },
  {
    // Underscore-prefixed args/vars are intentionally unused (no-op stubs,
    // documented signatures). Standard convention.
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  { ignores: ["dist/"] },
);
