/**
 * transcript-names.js -- Read-only name propagation for transcript pages.
 *
 * On page load, reads name edits from the shared localStorage store
 * (written by names.js on the report page) and updates the page heading
 * to reflect them.  Segment speaker labels show raw codes (p1, m1).
 *
 * This is intentionally lightweight: no editing, no export, no
 * reconciliation.  Transcript pages are read-only consumers of the
 * name data that the report page produces.
 *
 * Dependencies: storage.js (for createStore).
 *
 * @module transcript-names
 */

/* global createStore */

/**
 * Resolve the display name for a participant.
 *
 * Priority: localStorage short_name > localStorage full_name > pid.
 * (No BN_PARTICIPANTS baked-in data on transcript pages.)
 *
 * @param {string} pid
 * @param {Object} edits  The nameEdits object from localStorage.
 * @returns {string}
 */
function _resolveTranscriptName(pid, edits) {
  var edit = edits[pid] || {};
  if (edit.short_name) return edit.short_name;
  if (edit.full_name) return edit.full_name;
  return '';
}

/**
 * Bootstrap: apply any localStorage name edits to the transcript page.
 */
function initTranscriptNames() {
  var store = createStore('bristlenose-names');
  var edits = store.get({});
  if (!edits || Object.keys(edits).length === 0) return;

  // Update speaker name spans inside the <h1> heading.
  // Format: "m1 Sarah Chen" — code prefix preserved.
  var headingSpeakers = document.querySelectorAll('h1 .heading-speaker[data-participant]');
  for (var j = 0; j < headingSpeakers.length; j++) {
    var hEl = headingSpeakers[j];
    var hPid = hEl.getAttribute('data-participant');
    var hName = _resolveTranscriptName(hPid, edits);
    if (hName) {
      hEl.textContent = hPid + ' ' + hName;
    }
  }
}
