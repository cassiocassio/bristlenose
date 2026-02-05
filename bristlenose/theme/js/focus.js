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

/**
 * Handle keydown for focus navigation.
 *
 * @param {KeyboardEvent} e
 */
function handleKeydown(e) {
  // Don't intercept while editing
  if (isEditing()) return;

  var key = e.key;

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

  // Escape — clear focus
  if (key === 'Escape') {
    if (focusedQuoteId) {
      e.preventDefault();
      setFocus(null);
    }
    return;
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
