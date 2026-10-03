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
      // The export carries its locale resources in BRISTLENOSE_EXPORT, embedded
      // by the server for the chosen language and its fallback chain. Swap the
      // serve-mode loader for a stub so its dynamic import never enters this
      // build's module graph.
      //
      // This has to be an alias, not a build-time flag: vite's
      // dynamic-import-vars plugin expands `locales/${locale}/${ns}.json` into a
      // glob over all 192 files during *transform*, before any dead-code pass
      // could remove an unreachable branch — and inlineDynamicImports then folds
      // every one of them into the single chunk. That was 1,802 KB of a 3.38 MB
      // report. See docs/design-export-locale.md.
      "./localeLoader": path.resolve(__dirname, "src/i18n/localeLoader.export.ts"),
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
