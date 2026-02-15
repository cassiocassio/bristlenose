/**
 * names.js -- Inline participant name and role editing in the participant table.
 *
 * Clicking the pencil icon on a Name or Role cell turns the text span into
 * a contenteditable field.  Enter/Escape/click-outside to accept/cancel.
 * Edits persist in localStorage and update all downstream references
 * (quote attributions, transcript links) immediately.
 *
 * An "Export names" toolbar button copies edited names as a YAML snippet
 * that the user can paste into people.yaml.
 *
 * Architecture
 * ────────────
 * - Follows the same lifecycle pattern as editing.js (start/accept/cancel).
 * - Uses `createStore` from storage.js.
 * - Uses `copyToClipboard` and `showToast` from csv-export.js.
 * - `BN_PARTICIPANTS` is a global JSON object emitted by the Python renderer,
 *   containing the baked-in name data from people.yaml.
 *
 * Dependencies: storage.js, csv-export.js (for copyToClipboard/showToast).
 *
 * @module names
 */

/* global createStore, copyToClipboard, showToast, BN_PARTICIPANTS, isServeMode, apiPut, BRISTLENOSE_API_BASE */

var namesStore = createStore('bristlenose-names');
var nameEdits = namesStore.get({});

var activeNameEdit = null; // { cell, span, pid, field, original }

// ── Short name suggestion (mirrors Python suggest_short_names) ──────────

/**
 * Suggest a short_name from a full_name.
 *
 * Takes the first token.  Does NOT handle disambiguation here — that
 * requires knowledge of all participants, which the Python side handles
 * on the next pipeline run.
 *
 * @param {string} fullName
 * @returns {string}
 */
function suggestShortName(fullName) {
  if (!fullName) return '';
  var parts = fullName.trim().split(/\s+/);
  return parts[0] || '';
}

// ── Name resolution ─────────────────────────────────────────────────────

/**
 * Resolve the display name for a participant.
 *
 * Priority: localStorage short_name > baked short_name >
 *           localStorage full_name > baked full_name > pid.
 *
 * @param {string} pid
 * @returns {string}
 */
function resolveDisplayName(pid) {
  var edit = nameEdits[pid] || {};
  var baked = (typeof BN_PARTICIPANTS !== 'undefined' && BN_PARTICIPANTS[pid]) || {};

  if (edit.short_name) return edit.short_name;
  if (baked.short_name) return baked.short_name;
  if (edit.full_name) return edit.full_name;
  if (baked.full_name) return baked.full_name;
  return pid;
}

// ── Update all downstream references ────────────────────────────────────

/**
 * After a name edit, update every place the participant name appears.
 *
 * @param {string} pid
 */
function updateAllReferences(pid) {
  var edit = nameEdits[pid] || {};
  var baked = (typeof BN_PARTICIPANTS !== 'undefined' && BN_PARTICIPANTS[pid]) || {};
  var fullName = edit.full_name || baked.full_name || '';
  var roleName = edit.role || baked.role || '';

  // Quote attributions intentionally show raw pid (p1, p2) for anonymisation
  // when researchers copy quotes into external tools.  Only the participant
  // table name/role cells are updated here.

  // Participant table: update name and role cells.
  var row = document.querySelector('tr[data-participant="' + pid + '"]');
  if (row) {
    var nameSpan = row.querySelector('.name-text');
    if (nameSpan) {
      if (fullName) {
        nameSpan.textContent = fullName;
        nameSpan.classList.remove('unnamed');
        nameSpan.classList.add('edited');
      } else {
        nameSpan.innerHTML = '<span class="unnamed">Unnamed</span>';
        nameSpan.classList.remove('edited');
      }
    }
    var roleSpan = row.querySelector('.role-text');
    if (roleSpan) {
      roleSpan.textContent = roleName || '\u2014'; // em-dash
      if (roleName) {
        roleSpan.classList.add('edited');
      }
    }
  }
}

// ── Edit lifecycle ──────────────────────────────────────────────────────

/**
 * Enter edit mode on a table cell.
 *
 * @param {Element} cell  The <td> element with data-field attribute.
 */
function startNameEdit(cell) {
  if (activeNameEdit) cancelNameEdit();

  var span = cell.querySelector('.name-text, .role-text');
  if (!span) return;

  var row = cell.closest('tr');
  if (!row) return;
  var pid = row.getAttribute('data-participant');
  if (!pid) return;

  var field = cell.getAttribute('data-field'); // "full_name" or "role"
  if (!field) return;

  // Get the current text (strip "Unnamed" placeholder).
  var raw = span.textContent.trim();
  if (raw === 'Unnamed' || raw === '\u2014') raw = '';

  activeNameEdit = { cell: cell, span: span, pid: pid, field: field, original: raw };

  cell.classList.add('editing');
  span.textContent = raw;
  span.setAttribute('contenteditable', 'true');
  span.focus();

  // Select all text for easy replacement.
  var range = document.createRange();
  range.selectNodeContents(span);
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

/**
 * Cancel the active name edit, restoring the previous text.
 */
function cancelNameEdit() {
  if (!activeNameEdit) return;
  var ae = activeNameEdit;
  activeNameEdit = null;

  ae.cell.classList.remove('editing');
  ae.span.removeAttribute('contenteditable');

  // Restore from localStorage or original.
  var saved = nameEdits[ae.pid] && nameEdits[ae.pid][ae.field];
  var text = saved !== undefined && saved !== '' ? saved : ae.original;
  if (!text) {
    if (ae.field === 'full_name') {
      ae.span.innerHTML = '<span class="unnamed">Unnamed</span>';
    } else {
      ae.span.textContent = '\u2014';
    }
  } else {
    ae.span.textContent = text;
  }
}

/**
 * Accept the active name edit, saving to localStorage.
 */
function acceptNameEdit() {
  if (!activeNameEdit) return;
  var ae = activeNameEdit;
  activeNameEdit = null;

  ae.cell.classList.remove('editing');
  ae.span.removeAttribute('contenteditable');

  var newText = ae.span.textContent.trim();

  // Ensure the pid entry exists in nameEdits.
  if (!nameEdits[ae.pid]) {
    var baked = (typeof BN_PARTICIPANTS !== 'undefined' && BN_PARTICIPANTS[ae.pid]) || {};
    nameEdits[ae.pid] = {
      full_name: baked.full_name || '',
      short_name: baked.short_name || '',
      role: baked.role || '',
    };
  }

  nameEdits[ae.pid][ae.field] = newText;

  // Auto-suggest short_name when full_name is edited and short_name is empty.
  if (ae.field === 'full_name' && !nameEdits[ae.pid].short_name) {
    nameEdits[ae.pid].short_name = suggestShortName(newText);
  }

  namesStore.set(nameEdits);
  if (isServeMode()) apiPut(BRISTLENOSE_API_BASE + '/people', nameEdits);
  updateAllReferences(ae.pid);
}

// ── YAML export ─────────────────────────────────────────────────────────

/**
 * Build a YAML snippet of edited names for pasting into people.yaml.
 *
 * @returns {string} YAML text, or empty string if no edits.
 */
function buildNamesYaml() {
  var lines = [];
  var pids = Object.keys(nameEdits);
  pids.sort();
  for (var i = 0; i < pids.length; i++) {
    var pid = pids[i];
    var e = nameEdits[pid];
    if (!e) continue;
    var baked = (typeof BN_PARTICIPANTS !== 'undefined' && BN_PARTICIPANTS[pid]) || {};
    // Only include fields that differ from the baked-in values.
    var diffs = [];
    if (e.full_name && e.full_name !== baked.full_name) {
      diffs.push("      full_name: '" + e.full_name + "'");
    }
    if (e.short_name && e.short_name !== baked.short_name) {
      diffs.push("      short_name: '" + e.short_name + "'");
    }
    if (e.role && e.role !== baked.role) {
      diffs.push("      role: '" + e.role + "'");
    }
    if (diffs.length === 0) continue;
    lines.push('  ' + pid + ':');
    lines.push('    editable:');
    for (var j = 0; j < diffs.length; j++) {
      lines.push(diffs[j]);
    }
  }
  return lines.length ? lines.join('\n') + '\n' : '';
}

// ── Reconciliation ──────────────────────────────────────────────────────

/**
 * Prune localStorage entries that match the baked-in BN_PARTICIPANTS.
 *
 * When the user pastes edits into people.yaml and re-renders, the HTML
 * already contains the updated names.  We can safely remove those
 * localStorage overrides.
 */
function reconcileWithBaked() {
  if (typeof BN_PARTICIPANTS === 'undefined') return;
  var changed = false;
  var pids = Object.keys(nameEdits);
  for (var i = 0; i < pids.length; i++) {
    var pid = pids[i];
    var baked = BN_PARTICIPANTS[pid];
    var edit = nameEdits[pid];
    if (!baked || !edit) continue;
    if (
      (baked.full_name || '') === (edit.full_name || '') &&
      (baked.short_name || '') === (edit.short_name || '') &&
      (baked.role || '') === (edit.role || '')
    ) {
      delete nameEdits[pid];
      changed = true;
    }
  }
  if (changed) namesStore.set(nameEdits);
}

// ── Initialisation ──────────────────────────────────────────────────────

/**
 * Bootstrap name editing: reconcile state, restore edits, attach handlers.
 */
function initNames() {
  reconcileWithBaked();

  // Restore edits from localStorage and update the DOM.
  var pids = Object.keys(nameEdits);
  for (var i = 0; i < pids.length; i++) {
    updateAllReferences(pids[i]);
  }

  // Pencil click — toggle edit mode.
  document.addEventListener('click', function (e) {
    var pencil = e.target.closest('.name-pencil');
    if (!pencil) return;
    e.preventDefault();
    var cell = pencil.closest('td');
    if (!cell) return;
    if (cell.classList.contains('editing')) {
      cancelNameEdit();
    } else {
      startNameEdit(cell);
    }
  });

  // Keyboard: Enter to accept, Escape to cancel.
  document.addEventListener('keydown', function (e) {
    if (!activeNameEdit) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelNameEdit();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      acceptNameEdit();
    }
  });

  // Click outside the cell accepts the edit.
  document.addEventListener('click', function (e) {
    if (!activeNameEdit) return;
    if (!activeNameEdit.cell.contains(e.target)) {
      acceptNameEdit();
    }
  });

  // Export names button.
  var exportBtn = document.getElementById('export-names');
  if (exportBtn) {
    exportBtn.addEventListener('click', function () {
      var yaml = buildNamesYaml();
      if (!yaml) {
        showToast('No name edits to export');
        return;
      }
      copyToClipboard(yaml).then(
        function () { showToast('Names copied as YAML'); },
        function () { showToast('Could not copy to clipboard'); }
      );
    });
  }
}
