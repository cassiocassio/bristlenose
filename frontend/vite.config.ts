/// <reference types="vitest" />
import { defineConfig } from "vite";
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
    cors: true,
    origin: "http://localhost:5173",
    proxy: {
      "/api": "http://localhost:8150",
      "/report": "http://localhost:8150",
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
