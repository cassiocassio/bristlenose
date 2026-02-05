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
 *   starred.js      → initStarred(), toggleStar()
 *   editing.js      → initEditing()
 *   tags.js         → userTags, persistUserTags(), initTags()
 *   histogram.js    → renderUserTagsChart()   (called by tags.js)
 *   csv-export.js   → initCsvExport(), copyToClipboard(), showToast()
 *   preferences.js  → initPreferences(), getPref(), setPref()
 *   view-switcher.js → initViewSwitcher()    (depends on csv-export.js)
 *   search.js       → initSearchFilter()   (depends on csv-export.js)
 *   names.js        → initNames()            (depends on csv-export.js)
 *   focus.js        → initFocus(), setFocus(), isEditing()
 *   main.js         → this file (orchestrator)
 *
 * The Python renderer concatenates these files in order and wraps them
 * in a single `<script>` block (no module bundler needed).
 *
 * @module main
 */

// ── Boot sequence ─────────────────────────────────────────────────────────

initPlayer();
initStarred();
initEditing();
initInlineEditing();
initTags();
renderUserTagsChart();
initCsvExport();
initPreferences();
initViewSwitcher();
initSearchFilter();
initNames();
initFocus();
