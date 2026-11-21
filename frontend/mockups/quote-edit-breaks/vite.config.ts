/// One-chunk build of the quote-edit-breaks mockup. Run by
/// docs/mockups/quote-edit-breaks.gen.py, which inlines the result, with the
/// shipped theme stylesheet, into docs/mockups/quote-edit-breaks.html.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const SRC = path.resolve(__dirname, "../../src");

export default defineConfig({
  root: __dirname,
  plugins: [react()],
  define: { BN_BUILT_FROM: JSON.stringify(process.env.BN_BUILT_FROM ?? "a local build") },
  resolve: {
    alias: {
      "@locales": path.resolve(__dirname, "../../../bristlenose/locales"),
      // English only, as the export build does: keeps 21 locales out of the page.
      "./localeLoader": path.join(SRC, "i18n/localeLoader.export.ts"),
    },
  },
  build: {
    outDir: process.env.BN_MOCKUP_OUT ?? path.resolve(__dirname, "dist"),
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000,
    rollupOptions: {
      input: path.resolve(__dirname, "main.tsx"),
      output: { codeSplitting: false, entryFileNames: "app.js", assetFileNames: "app.[ext]" },
    },
  },
});
