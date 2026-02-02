/**
 * transcript-names.js -- Read-only name propagation for transcript pages.
 *
 * On page load, reads name edits from the shared localStorage store
 * (written by names.js on the report page) and updates the page heading
 * and speaker labels to reflect them.
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

  // Update the <h1> heading (has data-participant="p1").
  var h1 = document.querySelector('h1[data-participant]');
  if (h1) {
    var pid = h1.getAttribute('data-participant');
    var name = _resolveTranscriptName(pid, edits);
    if (name) {
      h1.textContent = pid + ' ' + name;
    }
  }

  // Update all segment speaker labels.
  var speakers = document.querySelectorAll('.segment-speaker[data-participant]');
  for (var i = 0; i < speakers.length; i++) {
    var el = speakers[i];
    var sPid = el.getAttribute('data-participant');
    var sName = _resolveTranscriptName(sPid, edits);
    if (sName) {
      el.textContent = sName + ':';
    }
  }
}
