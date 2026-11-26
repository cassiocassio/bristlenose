/// <reference types="vitest" />
import { defineConfig, searchForWorkspaceRoot } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@locales": path.resolve(__dirname, "../bristlenose/locales"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test-setup.ts"],
    // Vitest swaps every CSS import for "" unless it is included here, `?raw` too. The theme's
    // files are included so a test can read them as text (the keyline lab pins its shipped
    // values to them); no module imports theme CSS for its styles, so nothing else changes.
    css: { include: [/bristlenose\/theme\/.*\.css/] },
    // jsdom withholds localStorage/sessionStorage on an OPAQUE origin, and
    // an explicit `url` is the only way to get a real one. Without this,
    // `localStorage` is `undefined` — not empty, undefined — so every
    // `localStorage.clear()` in a beforeEach throws "Cannot read properties
    // of undefined", failing whole files (170 tests across 10 files) for a
    // reason that looks nothing like its cause. Storage is load-bearing here
    // (appearance, palette, feedback drafts, the pre-serve-mode stores), so
    // this stays until every such test moves to an injected store.
    environmentOptions: { jsdom: { url: "http://localhost:5173" } },
  },
  server: {
    port: 5173,
    origin: "http://localhost:5173",
    // The default (the workspace root) plus the theme CSS, which the keyline lab's tests read
    // as text (`?raw`) to pin the lab's shipped values to the shipped files. A `?raw` import
    // outside `fs.allow` is refused ("Denied ID"); the theme is public CSS the app serves anyway.
    fs: {
      allow: [searchForWorkspaceRoot(process.cwd()), path.resolve(__dirname, "../bristlenose/theme")],
    },
    proxy: {
      "/api": "http://localhost:8484",
      "/report": "http://localhost:8484",
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../bristlenose/server/static"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, "index.html"),
        "visual-diff": path.resolve(__dirname, "visual-diff.html"),
      },
    },
  },
});
