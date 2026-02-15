/**
 * editing.js — Inline quote text editing via contenteditable.
 *
 * Clicking the pencil icon on a blockquote turns the `.quote-text` span into
 * an editable field.  The user can type a corrected transcription, then press
 * Enter to accept or Escape to cancel.  Edits persist in localStorage and are
 * restored on reload (the `.edited` class provides a visual indicator).
 *
 * Also handles inline editing of section/theme titles and descriptions via
 * `.editable-text` spans.  Same UX: pencil icon, contenteditable, Enter/Escape.
 * Edits to titles also update the corresponding Table of Contents entry.
 *
 * Architecture
 * ────────────
 * - `activeEdit` tracks the currently-editing quote (at most one at a time).
 * - `activeInlineEdit` tracks the currently-editing heading/description.
 * - Smart-quotes (`\u201c` / `\u201d`) are stripped before editing and
 *   re-applied on save so the user works with plain text.  (Inline edits
 *   have no smart-quote wrapping.)
 * - Three commit paths: Enter key, click-outside, pencil-toggle.
 * - Escape always cancels without saving.
 *
 * Dependencies: `createStore` from storage.js.
 *
 * @module editing
 */

/* global createStore, isServeMode, apiPut, BRISTLENOSE_API_BASE */

var editsStore = createStore('bristlenose-edits');
var edits = editsStore.get({});

var activeEdit = null; // { bq, span, original }

// ── Helpers ───────────────────────────────────────────────────────────────

/** Regex to strip leading/trailing smart-quotes or straight quotes. */
var QUOTE_RE = /^[\u201c\u201d"]+|[\u201c\u201d"]+$/g;

/**
 * Enter edit mode on a blockquote.
 *
 * @param {Element} bq The blockquote element.
 */
function startEdit(bq) {
  if (activeEdit) cancelEdit();
  var span = bq.querySelector('.quote-text');
  if (!span) return;

  var raw = span.textContent.replace(QUOTE_RE, '').trim();
  activeEdit = { bq: bq, span: span, original: raw };

  bq.classList.add('editing');
  span.setAttribute('contenteditable', 'true');
  span.textContent = raw;
  span.focus();

  // Select all text for easy replacement.
  var range = document.createRange();
  range.selectNodeContents(span);
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

/**
 * Cancel the active edit, restoring the previous text.
 */
function cancelEdit() {
  if (!activeEdit) return;
  var ae = activeEdit;
  activeEdit = null;

  ae.bq.classList.remove('editing');
  ae.span.removeAttribute('contenteditable');

  // Restore: prefer the saved edit, fall back to the original.
  var qid = ae.bq.id;
  var saved = edits[qid];
  var text = saved !== undefined ? saved : ae.original;
  ae.span.textContent = '\u201c' + text + '\u201d';
  if (saved !== undefined) ae.span.classList.add('edited');
}

/**
 * Accept the active edit, saving the new text to localStorage.
 */
function acceptEdit() {
  if (!activeEdit) return;
  var ae = activeEdit;
  activeEdit = null;

  ae.bq.classList.remove('editing');
  ae.span.removeAttribute('contenteditable');

  var newText = ae.span.textContent.trim();
  ae.span.textContent = '\u201c' + newText + '\u201d';

  if (newText !== ae.original) {
    edits[ae.bq.id] = newText;
    ae.span.classList.add('edited');
    editsStore.set(edits);
    if (isServeMode()) apiPut(BRISTLENOSE_API_BASE + '/edits', edits);
  }
}

// ── Initialisation ────────────────────────────────────────────────────────

/**
 * Bootstrap inline editing: restore saved edits and attach event handlers.
 */
function initEditing() {
  // Restore edits from localStorage.
  Object.keys(edits).forEach(function (qid) {
    var bq = document.getElementById(qid);
    if (!bq) return;
    var span = bq.querySelector('.quote-text');
    if (!span) return;
    span.textContent = '\u201c' + edits[qid] + '\u201d';
    span.classList.add('edited');
  });

  // Pencil click — toggle edit mode.
  document.addEventListener('click', function (e) {
    var pencil = e.target.closest('.edit-pencil');
    if (!pencil) return;
    e.preventDefault();
    var bq = pencil.closest('blockquote');
    if (!bq) return;
    if (bq.classList.contains('editing')) {
      cancelEdit();
    } else {
      startEdit(bq);
    }
  });

  // Keyboard: Enter to accept, Escape to cancel.
  document.addEventListener('keydown', function (e) {
    if (!activeEdit) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelEdit();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      acceptEdit();
    }
  });

  // Click outside the blockquote accepts the edit.
  document.addEventListener('click', function (e) {
    if (!activeEdit) return;
    if (!activeEdit.bq.contains(e.target)) {
      acceptEdit();
    }
  });
}

// ── Inline editing (section/theme titles & descriptions) ─────────────────

var activeInlineEdit = null; // { span, original, editKey }

/**
 * Enter edit mode on an `.editable-text` span.
 *
 * @param {Element} span The `.editable-text` span element.
 */
function startInlineEdit(span) {
  if (activeInlineEdit) cancelInlineEdit();
  if (activeEdit) cancelEdit();

  var editKey = span.getAttribute('data-edit-key');
  if (!editKey) return;

  var raw = span.textContent.trim();
  activeInlineEdit = { span: span, original: raw, editKey: editKey };

  span.classList.add('editing');
  span.setAttribute('contenteditable', 'true');
  span.focus();

  var range = document.createRange();
  range.selectNodeContents(span);
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

/**
 * Cancel the active inline edit, restoring the previous text.
 */
function cancelInlineEdit() {
  if (!activeInlineEdit) return;
  var ae = activeInlineEdit;
  activeInlineEdit = null;

  ae.span.classList.remove('editing');
  ae.span.removeAttribute('contenteditable');

  var saved = edits[ae.editKey];
  var text = saved !== undefined ? saved : ae.original;
  ae.span.textContent = text;
  if (saved !== undefined) ae.span.classList.add('edited');
}

/**
 * Sync all `.editable-text` siblings that share the same `data-edit-key`,
 * excluding the source span that was just edited.
 *
 * @param {string} editKey  The key to match.
 * @param {string} newText  The updated text.
 * @param {Element} source  The span that was edited (skip it).
 */
function _syncSiblings(editKey, newText, source) {
  document.querySelectorAll(
    '.editable-text[data-edit-key="' + editKey + '"]'
  ).forEach(function (span) {
    if (span === source) return;
    span.textContent = newText;
    span.classList.add('edited');
  });
}

/**
 * Accept the active inline edit, saving to localStorage.
 * Syncs all other spans with the same edit key (ToC ↔ heading).
 */
function acceptInlineEdit() {
  if (!activeInlineEdit) return;
  var ae = activeInlineEdit;
  activeInlineEdit = null;

  ae.span.classList.remove('editing');
  ae.span.removeAttribute('contenteditable');

  var newText = ae.span.textContent.trim();
  ae.span.textContent = newText;

  if (newText !== ae.original) {
    edits[ae.editKey] = newText;
    ae.span.classList.add('edited');
    editsStore.set(edits);
    if (isServeMode()) apiPut(BRISTLENOSE_API_BASE + '/edits', edits);
    _syncSiblings(ae.editKey, newText, ae.span);
  }
}

/**
 * Bootstrap inline heading/description editing.
 */
function initInlineEditing() {
  // Restore saved inline edits from localStorage.
  document.querySelectorAll('.editable-text').forEach(function (span) {
    var editKey = span.getAttribute('data-edit-key');
    if (!editKey || edits[editKey] === undefined) return;
    span.textContent = edits[editKey];
    span.classList.add('edited');
  });

  // Pencil click — toggle inline edit mode.
  document.addEventListener('click', function (e) {
    var pencil = e.target.closest('.edit-pencil-inline');
    if (!pencil) return;
    e.preventDefault();
    var span = pencil.parentElement.querySelector('.editable-text');
    if (!span) return;
    if (span.classList.contains('editing')) {
      cancelInlineEdit();
    } else {
      startInlineEdit(span);
    }
  });

  // Keyboard: Enter to accept, Escape to cancel.
  document.addEventListener('keydown', function (e) {
    if (!activeInlineEdit) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelInlineEdit();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      acceptInlineEdit();
    }
  });

  // Click outside the span accepts the edit.
  document.addEventListener('click', function (e) {
    if (!activeInlineEdit) return;
    if (!activeInlineEdit.span.contains(e.target) &&
        !e.target.closest('.edit-pencil-inline')) {
      acceptInlineEdit();
    }
  });
}
