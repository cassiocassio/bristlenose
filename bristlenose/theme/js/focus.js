/**
 * focus.js — Keyboard focus navigation for quotes.
 *
 * Focus is the keyboard cursor — at most one quote can be focused at a time.
 * Users navigate with j/k (vim-style) or arrow keys. Focus is logical, not
 * visual: scrolling away doesn't lose focus, and j/k resumes from where you
 * were.
 *
 * States:
 *   focusedQuoteId = null    → no focus (initial state, after Escape)
 *   focusedQuoteId = string  → ID of focused blockquote
 *
 * Visual: focused quotes get the `.bn-focused` class (white bg + shadow lift).
 *
 * See docs/design-keyboard-navigation.md for the full spec.
 *
 * Dependencies: none (standalone module).
 *
 * @module focus
 */

/**
 * Currently focused quote ID, or null if no focus.
 * @type {string|null}
 */
var focusedQuoteId = null;

/**
 * Set of selected quote IDs for multi-select operations.
 * @type {Set<string>}
 */
var selectedQuoteIds = new Set();

/**
 * Anchor quote ID for Shift-extend selection ranges.
 * @type {string|null}
 */
var anchorQuoteId = null;

/**
 * Check if user is currently editing (in an input, textarea, or contenteditable).
 * Keyboard shortcuts should not fire while editing.
 *
 * @returns {boolean}
 */
function isEditing() {
  var el = document.activeElement;
  if (!el) return false;
  var tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return true;
  if (el.isContentEditable) return true;
  // Also check for open dropdowns / suggest boxes
  if (el.closest('.tag-suggest')) return true;
  return false;
}

/**
 * Get all visible quotes in DOM order.
 * A quote is visible if it's not hidden by CSS (display:none, visibility:hidden)
 * and not filtered out by search.
 *
 * @returns {HTMLElement[]}
 */
function getVisibleQuotes() {
  var all = document.querySelectorAll('.quote-group blockquote[id]');
  var visible = [];
  for (var i = 0; i < all.length; i++) {
    var bq = all[i];
    // Skip if hidden by search filter or view mode
    if (bq.offsetParent === null) continue;
    // Skip if inside a collapsed/hidden section
    var section = bq.closest('section');
    if (section && section.offsetParent === null) continue;
    visible.push(bq);
  }
  return visible;
}

/**
 * Set focus to a quote by ID. Pass null to clear focus.
 *
 * @param {string|null} quoteId
 * @param {Object} [options]
 * @param {boolean} [options.scroll=true] - Whether to scroll into view
 */
function setFocus(quoteId, options) {
  options = options || {};
  var shouldScroll = options.scroll !== false;

  // Remove focus from previous quote
  if (focusedQuoteId) {
    var prev = document.getElementById(focusedQuoteId);
    if (prev) prev.classList.remove('bn-focused');
  }

  focusedQuoteId = quoteId;

  // Add focus to new quote
  if (quoteId) {
    var next = document.getElementById(quoteId);
    if (next) {
      next.classList.add('bn-focused');
      if (shouldScroll) {
        // Scroll into view with some padding from top
        next.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }
}

// ── Selection ────────────────────────────────────────────────────────────────

/**
 * Toggle selection on a quote by ID.
 *
 * @param {string} quoteId
 */
function toggleSelection(quoteId) {
  var bq = document.getElementById(quoteId);
  if (!bq) return;

  if (selectedQuoteIds.has(quoteId)) {
    selectedQuoteIds.delete(quoteId);
    bq.classList.remove('bn-selected');
  } else {
    selectedQuoteIds.add(quoteId);
    bq.classList.add('bn-selected');
  }
  updateSelectionCount();
}

/**
 * Clear all selections.
 */
function clearSelection() {
  selectedQuoteIds.forEach(function(id) {
    var bq = document.getElementById(id);
    if (bq) bq.classList.remove('bn-selected');
  });
  selectedQuoteIds.clear();
  updateSelectionCount();
}

/**
 * Select a range of quotes between two IDs (inclusive).
 *
 * @param {string} fromId - Start of range
 * @param {string} toId - End of range
 */
function selectRange(fromId, toId) {
  var quotes = getVisibleQuotes();
  var fromIdx = -1, toIdx = -1;
  for (var i = 0; i < quotes.length; i++) {
    if (quotes[i].id === fromId) fromIdx = i;
    if (quotes[i].id === toId) toIdx = i;
  }
  if (fromIdx === -1 || toIdx === -1) return;

  var start = Math.min(fromIdx, toIdx);
  var end = Math.max(fromIdx, toIdx);

  for (var j = start; j <= end; j++) {
    selectedQuoteIds.add(quotes[j].id);
    quotes[j].classList.add('bn-selected');
  }
  updateSelectionCount();
}

/**
 * Get the set of selected quote IDs.
 * Exposed for other modules (csv-export, etc).
 *
 * @returns {Set<string>}
 */
function getSelectedQuoteIds() {
  return selectedQuoteIds;
}

/**
 * Update the header label with selection count.
 * Calls _updateViewLabel from view-switcher.js if available.
 */
function updateSelectionCount() {
  if (typeof _updateViewLabel === 'function') {
    _updateViewLabel(selectedQuoteIds.size);
  }
}

/**
 * Move focus to the next or previous quote.
 *
 * @param {number} direction - 1 for next, -1 for previous
 */
function moveFocus(direction) {
  var quotes = getVisibleQuotes();
  if (!quotes.length) return;

  // If no focus, start from beginning (next) or end (prev)
  if (!focusedQuoteId) {
    var idx = direction > 0 ? 0 : quotes.length - 1;
    setFocus(quotes[idx].id);
    return;
  }

  // Find current position
  var currentIdx = -1;
  for (var i = 0; i < quotes.length; i++) {
    if (quotes[i].id === focusedQuoteId) {
      currentIdx = i;
      break;
    }
  }

  // If focused quote is no longer visible, start from beginning/end
  if (currentIdx === -1) {
    var fallbackIdx = direction > 0 ? 0 : quotes.length - 1;
    setFocus(quotes[fallbackIdx].id);
    return;
  }

  // Move to next/prev, clamping at boundaries
  var newIdx = currentIdx + direction;
  if (newIdx < 0) newIdx = 0;
  if (newIdx >= quotes.length) newIdx = quotes.length - 1;

  // Only move if index actually changed
  if (newIdx !== currentIdx) {
    setFocus(quotes[newIdx].id);
  }
}

/**
 * Handle click on a quote — set focus, with modifier support for selection.
 *
 * - Plain click: focus only, clear selection
 * - Cmd/Ctrl+click: toggle selection
 * - Shift+click: range selection from anchor
 *
 * Ignores clicks when user is selecting text (non-empty window selection).
 *
 * @param {MouseEvent} e
 */
function handleQuoteClick(e) {
  // Don't interfere with clicks on interactive elements
  if (e.target.closest('button, a, input, [contenteditable="true"]')) return;
  // Don't interfere with tag input (preserves selection during bulk tagging)
  if (e.target.closest('.badge-add, .tag-input-wrap')) return;

  // Don't interfere with text selection — if user selected text, ignore the click
  var sel = window.getSelection();
  if (sel && sel.toString().length > 0) return;

  var bq = e.target.closest('.quote-group blockquote[id]');
  if (!bq) return;

  if (e.metaKey || e.ctrlKey) {
    // Cmd/Ctrl+Click: toggle selection
    e.preventDefault();
    toggleSelection(bq.id);
    anchorQuoteId = bq.id;
    setFocus(bq.id, { scroll: false });
  } else if (e.shiftKey && anchorQuoteId) {
    // Shift+Click: range selection
    e.preventDefault();
    selectRange(anchorQuoteId, bq.id);
    setFocus(bq.id, { scroll: false });
  } else {
    // Plain click: focus + single-select (like Finder)
    clearSelection();
    toggleSelection(bq.id);
    setFocus(bq.id, { scroll: false });
    anchorQuoteId = bq.id;
  }
}

/**
 * Handle click on background — clear focus.
 *
 * @param {MouseEvent} e
 */
function handleBackgroundClick(e) {
  // If click was on a quote, handleQuoteClick will handle it
  if (e.target.closest('.quote-group blockquote')) return;
  // If click was on toolbar/header/nav, ignore
  if (e.target.closest('.toolbar, header, nav, .toc')) return;
  // Clear focus and selection (like Finder)
  clearSelection();
  setFocus(null);
}

// ── Help overlay ─────────────────────────────────────────────────────────────

/* global createModal */

var helpModal = null;

/**
 * Lazily create the help modal (once, on first show).
 * @returns {{show: function, hide: function, isVisible: function}}
 */
function getHelpModal() {
  if (!helpModal) {
    helpModal = createModal({
      className: 'help-overlay',
      modalClassName: 'help-modal',
      content: [
        '<h2>Keyboard Shortcuts</h2>',
        '<div class="help-columns">',
        '  <div class="help-section">',
        '    <h3>Navigation</h3>',
        '    <dl>',
        '      <dt><kbd>j</kbd> / <kbd>↓</kbd></dt><dd>Next quote</dd>',
        '      <dt><kbd>k</kbd> / <kbd>↑</kbd></dt><dd>Previous quote</dd>',
        '    </dl>',
        '  </div>',
        '  <div class="help-section">',
        '    <h3>Selection</h3>',
        '    <dl>',
        '      <dt><kbd>x</kbd></dt><dd>Toggle select</dd>',
        '      <dt><kbd>Shift</kbd>+<kbd>j</kbd>/<kbd>k</kbd></dt><dd>Extend</dd>',
        '    </dl>',
        '  </div>',
        '  <div class="help-section">',
        '    <h3>Actions</h3>',
        '    <dl>',
        '      <dt><kbd>s</kbd></dt><dd>Star quote(s)</dd>',
        '      <dt><kbd>h</kbd></dt><dd>Hide quote(s)</dd>',
        '      <dt><kbd>t</kbd></dt><dd>Add tag(s)</dd>',
        '      <dt><kbd>Enter</kbd></dt><dd>Play in video</dd>',
        '    </dl>',
        '  </div>',
        '  <div class="help-section">',
        '    <h3>Global</h3>',
        '    <dl>',
        '      <dt><kbd>/</kbd></dt><dd>Search</dd>',
        '      <dt><kbd>?</kbd></dt><dd>This help</dd>',
        '      <dt><kbd>Esc</kbd></dt><dd>Close / clear</dd>',
        '    </dl>',
        '  </div>',
        '</div>',
        '<p class="bn-modal-footer">Press <kbd>?</kbd> to open this help, <kbd>Esc</kbd> or click outside to close</p>'
      ].join('\n')
    });
  }
  return helpModal;
}

/**
 * Toggle the help overlay.
 */
function toggleHelpOverlay() {
  getHelpModal().toggle();
}

// ── Quote actions ────────────────────────────────────────────────────────────

/**
 * Toggle star on the focused quote.
 */
function starFocusedQuote() {
  if (!focusedQuoteId) return;
  var bq = document.getElementById(focusedQuoteId);
  if (!bq) return;
  var starBtn = bq.querySelector('.star-btn');
  if (starBtn) {
    starBtn.click();
  }
}

/**
 * Bulk star/unstar all selected quotes.
 * If any selected quote is unstarred, star all. Otherwise unstar all.
 */
function bulkStarSelected() {
  if (selectedQuoteIds.size === 0) return;

  // Check if any selected quote is unstarred
  var anyUnstarred = false;
  selectedQuoteIds.forEach(function(id) {
    var bq = document.getElementById(id);
    if (bq && !bq.classList.contains('starred')) {
      anyUnstarred = true;
    }
  });

  // Star or unstar all based on anyUnstarred
  selectedQuoteIds.forEach(function(id) {
    var bq = document.getElementById(id);
    if (!bq) return;
    var isStarred = bq.classList.contains('starred');
    // If anyUnstarred, we want to star all unstarred ones
    // If !anyUnstarred (all starred), we want to unstar all
    if (anyUnstarred && !isStarred) {
      if (typeof toggleStar === 'function') toggleStar(id);
    } else if (!anyUnstarred && isStarred) {
      if (typeof toggleStar === 'function') toggleStar(id);
    }
  });
}

/**
 * Open the tag input on the focused quote.
 * If there's a selection, pass all selected IDs for bulk tagging.
 */
function tagFocusedQuote() {
  if (!focusedQuoteId) return;
  var bq = document.getElementById(focusedQuoteId);
  if (!bq) return;
  var addTagBtn = bq.querySelector('.badge-add');
  if (addTagBtn) {
    // If we have a selection, open tag input with bulk targetIds
    if (selectedQuoteIds.size > 0 && typeof openTagInput === 'function') {
      openTagInput(addTagBtn, bq, Array.from(selectedQuoteIds));
    } else {
      addTagBtn.click();
    }
  }
}

/**
 * Open video player at the focused quote's timecode.
 */
function playFocusedQuote() {
  if (!focusedQuoteId) return;
  var bq = document.getElementById(focusedQuoteId);
  if (!bq) return;
  // Find the timecode link with data-seconds
  var timecode = bq.querySelector('.timecode[data-seconds]');
  if (timecode) {
    timecode.click();
  }
}

// ── Global shortcuts ─────────────────────────────────────────────────────────

/**
 * Focus the search input — expand the search container first if needed.
 */
function focusSearchInput() {
  var container = document.getElementById('search-container');
  var searchInput = document.getElementById('search-input');
  if (!searchInput) return;

  // Expand the search container if collapsed
  if (container && !container.classList.contains('expanded')) {
    container.classList.add('expanded');
  }

  searchInput.focus();
  searchInput.select();
}

/**
 * Clear the search input.
 */
function clearSearch() {
  var searchInput = document.querySelector('.search-input');
  if (searchInput && searchInput.value) {
    searchInput.value = '';
    // Trigger input event to update filter
    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  }
  return false;
}

// ── Keydown handler ──────────────────────────────────────────────────────────

/**
 * Handle keydown for focus navigation.
 *
 * @param {KeyboardEvent} e
 */
function handleKeydown(e) {
  var key = e.key;

  // Escape — close modal, clear search, clear selection, or clear focus (in that order)
  if (key === 'Escape') {
    if (typeof closeTopmostModal !== 'undefined' && closeTopmostModal()) {
      e.preventDefault();
      return;
    }
    if (clearSearch()) {
      e.preventDefault();
      return;
    }
    if (selectedQuoteIds.size > 0) {
      e.preventDefault();
      clearSelection();
      return;
    }
    if (focusedQuoteId) {
      e.preventDefault();
      setFocus(null);
      return;
    }
    return;
  }

  // ? — switch to About tab (only when not editing)
  if (key === '?' && !isEditing()) {
    e.preventDefault();
    if (typeof switchToTab === 'function') {
      switchToTab('about');
    } else {
      toggleHelpOverlay();
    }
    return;
  }

  // Don't intercept other keys while editing or a modal is open
  if (isEditing()) return;
  var anyModalOpen = typeof _modalRegistry !== 'undefined' &&
    _modalRegistry.some(function (m) { return m.isVisible(); });
  if (anyModalOpen) return;

  // / — focus search
  if (key === '/') {
    e.preventDefault();
    focusSearchInput();
    return;
  }

  // Shift+j/ArrowDown — extend selection down
  if ((key === 'j' || key === 'ArrowDown') && e.shiftKey) {
    e.preventDefault();
    if (focusedQuoteId) {
      if (!selectedQuoteIds.has(focusedQuoteId)) {
        toggleSelection(focusedQuoteId);
      }
      if (!anchorQuoteId) anchorQuoteId = focusedQuoteId;
    }
    moveFocus(1);
    if (focusedQuoteId && !selectedQuoteIds.has(focusedQuoteId)) {
      toggleSelection(focusedQuoteId);
    }
    return;
  }

  // Shift+k/ArrowUp — extend selection up
  if ((key === 'k' || key === 'ArrowUp') && e.shiftKey) {
    e.preventDefault();
    if (focusedQuoteId) {
      if (!selectedQuoteIds.has(focusedQuoteId)) {
        toggleSelection(focusedQuoteId);
      }
      if (!anchorQuoteId) anchorQuoteId = focusedQuoteId;
    }
    moveFocus(-1);
    if (focusedQuoteId && !selectedQuoteIds.has(focusedQuoteId)) {
      toggleSelection(focusedQuoteId);
    }
    return;
  }

  // j or ArrowDown — next quote (no shift)
  if (key === 'j' || key === 'ArrowDown') {
    e.preventDefault();
    moveFocus(1);
    return;
  }

  // k or ArrowUp — previous quote (no shift)
  if (key === 'k' || key === 'ArrowUp') {
    e.preventDefault();
    moveFocus(-1);
    return;
  }

  // x — toggle selection on focused quote
  if (key === 'x' && focusedQuoteId) {
    e.preventDefault();
    toggleSelection(focusedQuoteId);
    if (!anchorQuoteId) anchorQuoteId = focusedQuoteId;
    return;
  }

  // h — hide (bulk if selection, single if focused)
  if (key === 'h') {
    if (selectedQuoteIds.size > 0) {
      e.preventDefault();
      if (typeof bulkHideSelected === 'function') bulkHideSelected();
      return;
    } else if (focusedQuoteId) {
      e.preventDefault();
      if (typeof hideQuote === 'function') hideQuote(focusedQuoteId);
      moveFocus(1);
      return;
    }
  }

  // s — star (bulk if selection, single if focused)
  if (key === 's') {
    if (selectedQuoteIds.size > 0) {
      e.preventDefault();
      bulkStarSelected();
      return;
    } else if (focusedQuoteId) {
      e.preventDefault();
      starFocusedQuote();
      return;
    }
  }

  // Actions on focused quote
  if (focusedQuoteId) {
    // t — add tag
    if (key === 't') {
      e.preventDefault();
      tagFocusedQuote();
      return;
    }

    // Enter — play in video player
    if (key === 'Enter') {
      e.preventDefault();
      playFocusedQuote();
      return;
    }
  }
}

/**
 * Initialize focus system — attach event listeners.
 */
function initFocus() {
  document.addEventListener('keydown', handleKeydown);
  document.addEventListener('click', handleQuoteClick);
  document.addEventListener('click', handleBackgroundClick);

  // Wire the footer "? for Help" link (can't use inline onclick — IIFE scope)
  var helpLink = document.querySelector('.footer-keyboard-hint');
  if (helpLink) {
    helpLink.addEventListener('click', function (e) {
      e.preventDefault();
      toggleHelpOverlay();
    });
  }
}
