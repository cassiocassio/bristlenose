/**
 * main.js — Bristlenose report entry point.
 *
 * This file bootstraps all interactive features of the research report.
 * It runs inside a self-executing IIFE so no names leak into the global
 * scope (except the intentional `window.*` hooks set by player.js).
 *
 * Module load order matters — later modules depend on globals defined by
 * earlier ones:
 *
 *   storage.js      → createStore()           (used by all stateful modules)
 *   player.js       → seekTo(), initPlayer()
 *   favourites.js   → initFavourites()
 *   editing.js      → initEditing()
 *   tags.js         → userTags, persistUserTags(), initTags()
 *   histogram.js    → renderUserTagsChart()   (called by tags.js)
 *   csv-export.js   → initCsvExport()
 *   main.js         → this file (orchestrator)
 *
 * The Python renderer concatenates these files in order and wraps them
 * in a single `<script>` block (no module bundler needed).
 *
 * @module main
 */

// ── Boot sequence ─────────────────────────────────────────────────────────

initPlayer();
initFavourites();
initEditing();
initTags();
renderUserTagsChart();
initCsvExport();
