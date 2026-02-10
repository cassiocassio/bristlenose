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
 *   modal.js        → createModal(), closeTopmostModal() (used by focus.js, feedback.js)
 *   codebook.js     → codebook, getTagColourVar(), initCodebook() (used by tags.js, histogram.js)
 *   player.js       → seekTo(), initPlayer()
 *   starred.js      → initStarred(), toggleStar()
 *   editing.js      → initEditing()
 *   tags.js         → userTags, persistUserTags(), initTags()
 *   histogram.js    → renderUserTagsChart()   (called by tags.js)
 *   csv-export.js   → initCsvExport(), copyToClipboard(), showToast()
 *   view-switcher.js → initViewSwitcher()    (depends on csv-export.js)
 *   search.js       → initSearchFilter()   (depends on csv-export.js)
 *   tag-filter.js   → initTagFilter()      (depends on tags.js, search.js)
 *   names.js        → initNames()            (depends on csv-export.js)
 *   focus.js        → initFocus(), setFocus(), isEditing()
 *   feedback.js     → initFeedback(), showFeedbackModal()
 *   global-nav.js   → initGlobalNav(), switchToTab()
 *   transcript-names.js → initTranscriptNames()
 *   transcript-annotations.js → initTranscriptAnnotations()
 *   main.js         → this file (orchestrator)
 *
 * The Python renderer concatenates these files in order and wraps them
 * in a single `<script>` block (no module bundler needed).
 *
 * @module main
 */

// ── Boot sequence ─────────────────────────────────────────────────────────

var _bootFns = [
  ['initPlayer', initPlayer],
  ['initStarred', initStarred],
  ['initEditing', initEditing],
  ['initInlineEditing', initInlineEditing],
  ['initTags', initTags],
  ['initCodebook', initCodebook],
  ['renderUserTagsChart', renderUserTagsChart],
  ['initCsvExport', initCsvExport],
  ['initViewSwitcher', initViewSwitcher],
  ['initSearchFilter', initSearchFilter],
  ['initTagFilter', initTagFilter],
  ['initHidden', initHidden],
  ['initNames', initNames],
  ['initFocus', initFocus],
  ['initFeedback', initFeedback],
  ['initAnalysis', initAnalysis],
  ['initGlobalNav', initGlobalNav],
];
for (var _bi = 0; _bi < _bootFns.length; _bi++) {
  try { _bootFns[_bi][1](); }
  catch (e) { console.error('BOOT FAIL: ' + _bootFns[_bi][0], e); }
}
if (typeof initTranscriptNames === 'function') { try { initTranscriptNames(); } catch(e) { console.error('BOOT FAIL: initTranscriptNames', e); } }
if (typeof initTranscriptAnnotations === 'function' && typeof BRISTLENOSE_QUOTE_MAP !== 'undefined') { try { initTranscriptAnnotations(); } catch(e) { console.error('BOOT FAIL: initTranscriptAnnotations', e); } }
