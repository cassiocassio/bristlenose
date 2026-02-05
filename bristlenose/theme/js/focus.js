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
 * Handle click on a quote — set focus to it.
 *
 * @param {MouseEvent} e
 */
function handleQuoteClick(e) {
  // Don't interfere with clicks on interactive elements
  if (e.target.closest('button, a, input, [contenteditable="true"]')) return;

  var bq = e.target.closest('.quote-group blockquote[id]');
  if (bq) {
    setFocus(bq.id, { scroll: false });
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
  // Clear focus
  setFocus(null);
}

// ── Help overlay ─────────────────────────────────────────────────────────────

var helpOverlayVisible = false;

/**
 * Create the help overlay element (once, on first show).
 * @returns {HTMLElement}
 */
function createHelpOverlay() {
  var overlay = document.createElement('div');
  overlay.className = 'help-overlay';
  overlay.innerHTML = [
    '<div class="help-modal">',
    '  <h2>Keyboard Shortcuts</h2>',
    '  <div class="help-columns">',
    '    <div class="help-section">',
    '      <h3>Navigation</h3>',
    '      <dl>',
    '        <dt><kbd>j</kbd> / <kbd>↓</kbd></dt><dd>Next quote</dd>',
    '        <dt><kbd>k</kbd> / <kbd>↑</kbd></dt><dd>Previous quote</dd>',
    '      </dl>',
    '    </div>',
    '    <div class="help-section">',
    '      <h3>Actions</h3>',
    '      <dl>',
    '        <dt><kbd>s</kbd></dt><dd>Star quote</dd>',
    '        <dt><kbd>t</kbd></dt><dd>Add tag</dd>',
    '        <dt><kbd>Enter</kbd></dt><dd>Play in video</dd>',
    '      </dl>',
    '    </div>',
    '    <div class="help-section">',
    '      <h3>Global</h3>',
    '      <dl>',
    '        <dt><kbd>/</kbd></dt><dd>Search</dd>',
    '        <dt><kbd>?</kbd></dt><dd>This help</dd>',
    '        <dt><kbd>Esc</kbd></dt><dd>Close / clear</dd>',
    '      </dl>',
    '    </div>',
    '  </div>',
    '  <p class="help-footer">Press <kbd>Esc</kbd> or click outside to close</p>',
    '</div>'
  ].join('\n');
  document.body.appendChild(overlay);
  // Close on click outside modal
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      hideHelpOverlay();
    }
  });
  return overlay;
}

/**
 * Show the help overlay.
 */
function showHelpOverlay() {
  var overlay = document.querySelector('.help-overlay') || createHelpOverlay();
  overlay.classList.add('visible');
  helpOverlayVisible = true;
}

/**
 * Hide the help overlay.
 */
function hideHelpOverlay() {
  var overlay = document.querySelector('.help-overlay');
  if (overlay) {
    overlay.classList.remove('visible');
  }
  helpOverlayVisible = false;
}

/**
 * Toggle the help overlay.
 */
function toggleHelpOverlay() {
  if (helpOverlayVisible) {
    hideHelpOverlay();
  } else {
    showHelpOverlay();
  }
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
 * Open the tag input on the focused quote.
 */
function tagFocusedQuote() {
  if (!focusedQuoteId) return;
  var bq = document.getElementById(focusedQuoteId);
  if (!bq) return;
  var addTagBtn = bq.querySelector('.badge-add');
  if (addTagBtn) {
    addTagBtn.click();
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

  // Escape — close help, clear search, or clear focus (in that order)
  if (key === 'Escape') {
    if (helpOverlayVisible) {
      e.preventDefault();
      hideHelpOverlay();
      return;
    }
    if (clearSearch()) {
      e.preventDefault();
      return;
    }
    if (focusedQuoteId) {
      e.preventDefault();
      setFocus(null);
      return;
    }
    return;
  }

  // ? — toggle help overlay (only when not editing)
  if (key === '?' && !isEditing()) {
    e.preventDefault();
    toggleHelpOverlay();
    return;
  }

  // Don't intercept other keys while editing or help is open
  if (isEditing() || helpOverlayVisible) return;

  // / — focus search
  if (key === '/') {
    e.preventDefault();
    focusSearchInput();
    return;
  }

  // j or ArrowDown — next quote
  if (key === 'j' || key === 'ArrowDown') {
    e.preventDefault();
    moveFocus(1);
    return;
  }

  // k or ArrowUp — previous quote
  if (key === 'k' || key === 'ArrowUp') {
    e.preventDefault();
    moveFocus(-1);
    return;
  }

  // Actions on focused quote
  if (focusedQuoteId) {
    // s — toggle star
    if (key === 's') {
      e.preventDefault();
      starFocusedQuote();
      return;
    }

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
}
