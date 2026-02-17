/**
 * starred.js — Star / un-star quotes and reorder them within their group.
 *
 * Users click the star icon on a quote to mark it as starred.  Starred
 * quotes float to the top of their section group with a smooth FLIP animation.
 * State is persisted in localStorage so starred quotes survive page reloads.
 *
 * Architecture
 * ────────────
 * - `starred` (object): an in-memory map of quote ID → `true`.
 * - `originalOrder` (object): snapshot of DOM indices taken on load so that
 *   un-starred quotes return to their original position.
 * - `reorderGroup(group, animate)` implements the FLIP (First-Last-Invert-Play)
 *   animation technique:
 *     1. Record each blockquote's bounding rect            (FIRST)
 *     2. DOM-reorder: starred first, rest in original order
 *     3. Compute the delta between old and new positions    (INVERT)
 *     4. Animate the transform back to zero                 (PLAY)
 *
 * Dependencies: `createStore` from storage.js, `getPref` from preferences.js.
 *
 * @module starred
 */

/* global createStore, getPref, isServeMode, apiPut, selectedQuoteIds */

// Migrate from old localStorage key if present (one-time migration).
var _oldStarredData = localStorage.getItem('bristlenose-favourites');
if (_oldStarredData && !localStorage.getItem('bristlenose-starred')) {
  localStorage.setItem('bristlenose-starred', _oldStarredData);
  localStorage.removeItem('bristlenose-favourites');
}

var starStore = createStore('bristlenose-starred');
var starred = starStore.get({});

// Capture original DOM order per group so un-starred quotes go home.
var originalOrder = {};

/**
 * Sort blockquotes inside a `.quote-group` — starred first.
 *
 * @param {Element} group    The `.quote-group` container.
 * @param {boolean} animate  Whether to run the FLIP animation.
 */
function reorderGroup(group, animate) {
  var quotes = Array.prototype.slice.call(group.querySelectorAll('blockquote'));
  if (!quotes.length) return;

  // Separate hidden quotes — they don't participate in reorder (display: none).
  var visible = [];
  var hidden = [];
  quotes.forEach(function (bq) {
    (bq.classList.contains('bn-hidden') ? hidden : visible).push(bq);
  });
  if (!visible.length) return;

  // --- FIRST: record current positions ---
  var rects = {};
  if (animate) {
    visible.forEach(function (bq) {
      rects[bq.id] = bq.getBoundingClientRect();
    });
  }

  // --- Partition: starred first, rest in original order ---
  var starredQuotes = [];
  var rest = [];
  visible.forEach(function (bq) {
    (bq.classList.contains('starred') ? starredQuotes : rest).push(bq);
  });
  rest.sort(function (a, b) {
    return (originalOrder[a.id] || 0) - (originalOrder[b.id] || 0);
  });
  starredQuotes.concat(rest).concat(hidden).forEach(function (bq) {
    group.appendChild(bq);
  });

  if (!animate) return;

  // --- INVERT: offset each element back to where it was ---
  visible.forEach(function (bq) {
    var old = rects[bq.id];
    var cur = bq.getBoundingClientRect();
    var dy = old.top - cur.top;
    if (Math.abs(dy) < 1) return;
    bq.style.transform = 'translateY(' + dy + 'px)';
    bq.style.transition = 'none';
  });

  // --- PLAY: animate to final position ---
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      visible.forEach(function (bq) {
        bq.classList.add('star-animating');
        bq.style.transform = '';
        bq.style.transition = '';
      });
      setTimeout(function () {
        visible.forEach(function (bq) {
          bq.classList.remove('star-animating');
        });
      }, 250);
    });
  });
}

/**
 * Toggle star state on a quote by ID.
 * Called by keyboard shortcut handler in focus.js.
 *
 * @param {string} quoteId  The ID of the quote to toggle.
 * @returns {boolean}       The new starred state.
 */
function toggleStar(quoteId) {
  var bq = document.getElementById(quoteId);
  if (!bq) return false;

  var isStarred = bq.classList.toggle('starred');
  if (isStarred) {
    starred[quoteId] = true;
  } else {
    delete starred[quoteId];
  }
  starStore.set(starred);
  if (isServeMode()) apiPut('/starred', starred);

  var group = bq.closest('.quote-group');
  if (group) {
    var shouldAnimate = typeof getPref === 'function' ? getPref('animations_enabled') : true;
    reorderGroup(group, shouldAnimate);
  }

  return isStarred;
}

/**
 * Bootstrap starred: restore state from localStorage, reorder groups,
 * and attach the star-click handler.
 */
function initStarred() {
  // Snapshot original DOM order for every group.
  var allGroups = document.querySelectorAll('.quote-group');
  for (var g = 0; g < allGroups.length; g++) {
    var bqs = Array.prototype.slice.call(
      allGroups[g].querySelectorAll('blockquote')
    );
    bqs.forEach(function (bq, idx) {
      originalOrder[bq.id] = idx;
    });
  }

  // Restore starred class from localStorage.
  Object.keys(starred).forEach(function (qid) {
    var bq = document.getElementById(qid);
    if (bq) bq.classList.add('starred');
  });

  // Initial reorder (no animation on page load).
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) {
    reorderGroup(groups[i], false);
  }

  // Delegate star clicks — selection-aware bulk when clicking a selected quote.
  document.addEventListener('click', function (e) {
    var star = e.target.closest('.star-btn');
    if (!star) return;
    e.preventDefault();
    var bq = star.closest('blockquote');
    if (!bq || !bq.id) return;

    if (typeof selectedQuoteIds !== 'undefined' && selectedQuoteIds.size > 0 && selectedQuoteIds.has(bq.id)) {
      // Bulk: follow the clicked quote's state.
      _clearStarPreview();
      var willStar = !bq.classList.contains('starred');
      selectedQuoteIds.forEach(function (id) {
        var target = document.getElementById(id);
        if (!target) return;
        var targetIsStarred = target.classList.contains('starred');
        if (willStar && !targetIsStarred) toggleStar(id);
        else if (!willStar && targetIsStarred) toggleStar(id);
      });
    } else {
      toggleStar(bq.id);
    }
  });

  // Hover preview — show directional tint on all selected quotes' stars.
  document.addEventListener('mouseover', function (e) {
    var star = e.target.closest('.star-btn');
    if (!star) return;
    var bq = star.closest('blockquote');
    if (!bq || !bq.id) return;
    if (typeof selectedQuoteIds === 'undefined' || selectedQuoteIds.size < 2 || !selectedQuoteIds.has(bq.id)) return;

    var willStar = !bq.classList.contains('starred');
    var cls = willStar ? 'bn-preview-star' : 'bn-preview-unstar';
    selectedQuoteIds.forEach(function (id) {
      var target = document.getElementById(id);
      if (target) target.classList.add(cls);
    });
  });

  document.addEventListener('mouseout', function (e) {
    var star = e.target.closest('.star-btn');
    if (!star) return;
    var related = e.relatedTarget;
    if (related && star.contains(related)) return;
    _clearStarPreview();
  });
}

/**
 * Remove all star preview classes from the DOM.
 */
function _clearStarPreview() {
  var els = document.querySelectorAll('.bn-preview-star, .bn-preview-unstar');
  for (var i = 0; i < els.length; i++) {
    els[i].classList.remove('bn-preview-star', 'bn-preview-unstar');
  }
}
