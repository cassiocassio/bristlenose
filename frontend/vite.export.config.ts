/// Single-file export build.
///
/// Produces ONE self-contained JS chunk + ONE CSS file (no code-splitting, all
/// assets inlined) that the export endpoint inlines into a self-contained HTML.
/// This is what makes an exported report render when opened directly from disk
/// (file://): a code-split bundle loaded via blob: URLs is blocked from an
/// opaque file:// origin, and data: URL modules can't resolve their own
/// sub-imports — one inline module sidesteps both.
///
/// Output: bristlenose/server/static-export/{app.js, app.css}. Consumed by
/// bristlenose/server/routes/export.py `_build_export_html`.
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
  build: {
    outDir: path.resolve(__dirname, "../bristlenose/server/static-export"),
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000, // inline every asset (fonts/images) as data URLs
    rollupOptions: {
      input: path.resolve(__dirname, "index.html"),
      output: {
        inlineDynamicImports: true, // ONE js chunk — no cross-chunk imports
        entryFileNames: "app.js",
        assetFileNames: "app.[ext]",
      },
    },
  },
});
