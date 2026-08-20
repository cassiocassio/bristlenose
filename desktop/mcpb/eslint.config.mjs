// Lint config for the .mcpb proxy — one rule that matters, plus its friends.
//
// Why this exists: on 20 Aug 2026 `callUpstream` referenced `hs.port` where
// `hs` was not in scope (every binding is a local const in another function).
// It threw ReferenceError on EVERY tool call, the surrounding try/catch
// swallowed it, and the user was told "Bristlenose is starting — ask again in
// a moment" for eleven days across six reinstall attempts.
//
// `node --check` cannot catch this — it is syntax-only, and
// `function f(){ try { return g.port } catch {} }` parses fine. An unbound
// identifier is a STATIC property, so a linter catches the whole class at
// pack time for free, which is cheaper and broader than any runtime test
// (review Finding 33; a stdio harness targets a different class and is
// deferred until one of those actually ships).
//
// eslint is already a frontend devDependency — nothing new is installed, and
// the SHIPPED proxy keeps its zero-dependency guarantee: this file is not in
// build-mcpb.sh's two-member allowlist and never enters the archive.
export default [
  {
    files: ["server/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "commonjs",
      globals: {
        // Node 18+ built-ins the proxy actually uses. Deliberately explicit
        // rather than pulling in the `globals` package: a short list that
        // fails loudly on a typo beats a broad one that hides it.
        require: "readonly",
        module: "writable",
        process: "readonly",
        console: "readonly",
        Buffer: "readonly",
        fetch: "readonly",
        AbortController: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        URL: "readonly",
        TextDecoder: "readonly",
        __dirname: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
      // Same family: a name that exists but is never read is often the other
      // half of a half-finished rename.
      // ignoreRestSiblings: `const { project, ...rest } = args` is the
      // deliberate omit-by-destructuring idiom in stripProject, not a
      // forgotten variable.
      "no-unused-vars": ["error", { args: "none", caughtErrors: "none", ignoreRestSiblings: true }],
      "no-unreachable": "error",
    },
  },
];
