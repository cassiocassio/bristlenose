/**
 * tags.js — AI badge management and user-defined tagging system.
 *
 * This is the largest JS module in the report.  It handles two distinct but
 * related features:
 *
 * 1. **AI badge lifecycle** — badges rendered server-side (emotion, intent,
 *    intensity) can be deleted by the user (with a fade-out animation) and
 *    later restored via an undo button.
 *
 * 2. **User tags** — free-text tags added via an inline input with keyboard-
 *    navigable auto-suggest.  User tags are visually distinguished from AI
 *    badges by the `.badge-user` class.
 *
 * Both types persist in localStorage so changes survive reloads.
 *
 * Architecture
 * ────────────
 * Two stores back the two feature halves:
 *   - `bristlenose-tags`           → { quoteId: ["tag1", "tag2"] }
 *   - `bristlenose-deleted-badges` → { quoteId: ["confusion", …] }
 *
 * The auto-suggest dropdown collects *all* user tag names across the report
 * and filters them as the user types.  Keyboard navigation (↑/↓/Tab/Enter/Esc)
 * mirrors standard combobox UX conventions.
 *
 * Dependencies: `createStore` from storage.js.
 *
 * @module tags
 */

/* global createStore, renderUserTagsChart */

var tagsStore = createStore('bristlenose-tags');
var deletedBadgesStore = createStore('bristlenose-deleted-badges');

var userTags = tagsStore.get({});
var deletedBadges = deletedBadgesStore.get({});

// ── Shared helpers ────────────────────────────────────────────────────────

/**
 * Save user tags and notify the histogram chart to re-render.
 *
 * Every call-site that mutates `userTags` should go through this rather
 * than calling `tagsStore.set` directly, so the chart stays in sync.
 *
 * @param {object} tags The full tags map.
 */
function persistUserTags(tags) {
  tagsStore.set(tags);
  // Re-render the user-tags histogram if available (defined in histogram.js).
  if (typeof renderUserTagsChart === 'function') renderUserTagsChart();
}

/**
 * Collect every distinct user tag name across all quotes.
 *
 * Used by the auto-suggest dropdown to offer completions.
 *
 * @returns {string[]} Sorted array of unique tag names.
 */
function allTagNames() {
  var set = {};
  Object.keys(userTags).forEach(function (qid) {
    (userTags[qid] || []).forEach(function (t) {
      set[t.toLowerCase()] = t;
    });
  });
  return Object.keys(set)
    .sort()
    .map(function (k) {
      return set[k];
    });
}

/**
 * Create a user-tag badge DOM element.
 *
 * @param {string} name The tag text.
 * @returns {Element} A `<span class="badge badge-user">` with a delete button.
 */
function createUserTagEl(name) {
  var span = document.createElement('span');
  span.className = 'badge badge-user badge-appearing';
  span.setAttribute('data-badge-type', 'user');
  span.setAttribute('data-tag-name', name);
  span.textContent = name;

  var del = document.createElement('button');
  del.className = 'badge-delete';
  del.setAttribute('aria-label', 'Remove tag');
  del.textContent = '\u00d7'; // ×
  span.appendChild(del);

  setTimeout(function () {
    span.classList.remove('badge-appearing');
  }, 200);
  return span;
}

/**
 * Show or hide the restore button for a blockquote based on whether it
 * has any deleted AI badges.
 *
 * @param {Element} bq A blockquote element.
 */
function updateRestoreButton(bq) {
  var qid = bq.id;
  var btn = bq.querySelector('.badge-restore');
  if (!btn) return;
  var has = deletedBadges[qid] && deletedBadges[qid].length > 0;
  btn.style.display = has ? '' : 'none';
}

// ── Auto-suggest ──────────────────────────────────────────────────────────

/** Index of the highlighted suggestion (-1 = nothing highlighted). */
var suggestIndex = -1;

/**
 * Build (or rebuild) the auto-suggest dropdown below the tag input.
 *
 * @param {HTMLInputElement} input The tag input element.
 * @param {Element}          wrap  The `.tag-input-wrap` container.
 */
function buildSuggest(input, wrap) {
  var old = wrap.querySelector('.tag-suggest');
  if (old) old.remove();
  suggestIndex = -1;

  var val = input.value.trim().toLowerCase();
  if (!val) return;

  // Collect tags the current quote already has, so we don't suggest them.
  var bq = activeTagInput ? activeTagInput.bq : null;
  var existing = bq && bq.id && userTags[bq.id] ? userTags[bq.id].map(function (t) { return t.toLowerCase(); }) : [];

  var names = allTagNames().filter(function (n) {
    return n.toLowerCase().indexOf(val) !== -1 && n.toLowerCase() !== val && existing.indexOf(n.toLowerCase()) === -1;
  });
  if (!names.length) return;

  var list = document.createElement('div');
  list.className = 'tag-suggest';
  names.slice(0, 8).forEach(function (name) {
    var item = document.createElement('div');
    item.className = 'tag-suggest-item';
    item.textContent = name;
    item.addEventListener('mousedown', function (ev) {
      ev.preventDefault(); // keep focus on input
      input.value = name;
      closeTagInput(true);
    });
    list.appendChild(item);
  });
  wrap.appendChild(list);
}

/**
 * Highlight a suggestion item by index, scrolling it into view.
 *
 * @param {Element} wrap The `.tag-input-wrap` container.
 * @param {number}  idx  The index to highlight (-1 for none).
 */
function highlightSuggestItem(wrap, idx) {
  var items = wrap.querySelectorAll('.tag-suggest-item');
  if (!items.length) return;
  for (var i = 0; i < items.length; i++) {
    items[i].classList.toggle('active', i === idx);
  }
  if (idx >= 0 && idx < items.length) {
    items[idx].scrollIntoView({ block: 'nearest' });
  }
}

/** Get the text of the suggestion at `idx`, or null. */
function getSuggestValue(wrap, idx) {
  var items = wrap.querySelectorAll('.tag-suggest-item');
  if (idx >= 0 && idx < items.length) return items[idx].textContent;
  return null;
}

/** Return the number of visible suggestion items. */
function suggestCount(wrap) {
  return wrap.querySelectorAll('.tag-suggest-item').length;
}

// ── Tag input lifecycle ───────────────────────────────────────────────────

/** Currently active tag input state, or null. */
var activeTagInput = null; // { bq, wrap, input, addBtn }

/**
 * Close the active tag input, optionally committing the value.
 *
 * @param {boolean} commit If true and the input is non-empty, save the tag.
 */
function closeTagInput(commit) {
  if (!activeTagInput) return;
  var ati = activeTagInput;
  activeTagInput = null;
  var val = ati.input.value.trim();

  if (commit && val) {
    var qid = ati.bq.id;
    if (!userTags[qid]) userTags[qid] = [];
    // Avoid duplicates.
    if (userTags[qid].indexOf(val) === -1) {
      userTags[qid].push(val);
      persistUserTags(userTags);
      var tagEl = createUserTagEl(val);
      ati.addBtn.parentNode.insertBefore(tagEl, ati.addBtn);
    }
  }

  ati.wrap.remove();
  ati.addBtn.style.display = '';
}

/**
 * Open the inline tag input, replacing the "+" ghost-badge.
 *
 * @param {Element} addBtn The `.badge-add` element that was clicked.
 * @param {Element} bq     The parent blockquote.
 */
function openTagInput(addBtn, bq) {
  if (activeTagInput) closeTagInput(false);

  addBtn.style.display = 'none';

  // Build input wrapper.
  var wrap = document.createElement('span');
  wrap.className = 'tag-input-wrap';
  var input = document.createElement('input');
  input.className = 'tag-input';
  input.type = 'text';
  input.placeholder = 'tag';
  var sizer = document.createElement('span');
  sizer.className = 'tag-sizer';
  wrap.appendChild(input);
  wrap.appendChild(sizer);
  addBtn.parentNode.insertBefore(wrap, addBtn);
  input.focus();

  activeTagInput = { bq: bq, wrap: wrap, input: input, addBtn: addBtn };

  // Auto-resize input to fit typed text.
  input.addEventListener('input', function () {
    sizer.textContent = input.value || input.placeholder;
    var w = Math.max(sizer.offsetWidth + 16, 48);
    input.style.width = w + 'px';
    buildSuggest(input, wrap);
  });

  // Keyboard navigation within the suggest dropdown.
  input.addEventListener('keydown', function (ev) {
    var count = suggestCount(wrap);
    if (ev.key === 'ArrowDown' && count > 0) {
      ev.preventDefault();
      suggestIndex = Math.min(suggestIndex + 1, count - 1);
      highlightSuggestItem(wrap, suggestIndex);
    } else if (ev.key === 'ArrowUp' && count > 0) {
      ev.preventDefault();
      suggestIndex = Math.max(suggestIndex - 1, -1);
      highlightSuggestItem(wrap, suggestIndex);
    } else if (ev.key === 'Tab' && count > 0) {
      ev.preventDefault();
      // Tab picks the first or currently highlighted item.
      var pickIdx = suggestIndex >= 0 ? suggestIndex : 0;
      var val = getSuggestValue(wrap, pickIdx);
      if (val) {
        input.value = val;
        closeTagInput(true);
      }
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      if (suggestIndex >= 0) {
        var picked = getSuggestValue(wrap, suggestIndex);
        if (picked) input.value = picked;
      }
      closeTagInput(true);
    } else if (ev.key === 'Escape') {
      ev.preventDefault();
      closeTagInput(false);
    }
  });

  // Blur: commit non-empty values after a short delay (so mousedown on
  // a suggestion item can fire first).
  input.addEventListener('blur', function () {
    setTimeout(function () {
      if (activeTagInput && activeTagInput.input === input) {
        closeTagInput(input.value.trim() ? true : false);
      }
    }, 150);
  });
}

// ── Initialisation ────────────────────────────────────────────────────────

/**
 * Bootstrap the tag system: restore state, attach all event handlers.
 */
function initTags() {
  // ── Restore persisted state on load ──

  var allBq = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < allBq.length; i++) {
    var bq = allBq[i];
    var qid = bq.id;
    if (!qid) continue;

    // Hide deleted AI badges.
    var deleted = deletedBadges[qid] || [];
    if (deleted.length) {
      var aiBadges = bq.querySelectorAll('[data-badge-type="ai"]');
      for (var j = 0; j < aiBadges.length; j++) {
        var label = aiBadges[j].textContent.trim();
        if (deleted.indexOf(label) !== -1) {
          aiBadges[j].style.display = 'none';
        }
      }
      updateRestoreButton(bq);
    }

    // Render user tags before the "+" button.
    var tags = userTags[qid] || [];
    if (tags.length) {
      var addBtn = bq.querySelector('.badge-add');
      if (addBtn) {
        for (var k = 0; k < tags.length; k++) {
          var tagEl = createUserTagEl(tags[k]);
          addBtn.parentNode.insertBefore(tagEl, addBtn);
        }
      }
    }
  }

  // ── AI badge delete (click) ──

  document.addEventListener('click', function (e) {
    var badge = e.target.closest('[data-badge-type="ai"]');
    if (!badge) return;
    if (e.target.closest('.tag-input-wrap')) return; // ignore during input
    e.preventDefault();
    var bq = badge.closest('blockquote');
    if (!bq || !bq.id) return;
    var badgeLabel = badge.textContent.trim();

    // Animate removal.
    badge.classList.add('badge-removing');
    badge.addEventListener(
      'animationend',
      function () {
        badge.style.display = 'none';
        badge.classList.remove('badge-removing');
      },
      { once: true }
    );

    // Persist.
    var id = bq.id;
    if (!deletedBadges[id]) deletedBadges[id] = [];
    if (deletedBadges[id].indexOf(badgeLabel) === -1) {
      deletedBadges[id].push(badgeLabel);
    }
    deletedBadgesStore.set(deletedBadges);
    updateRestoreButton(bq);
  });

  // ── Restore deleted AI badges ──

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.badge-restore');
    if (!btn) return;
    e.preventDefault();
    var bq = btn.closest('blockquote');
    if (!bq || !bq.id) return;

    // Show all hidden AI badges with a fade-in animation.
    var aiBadges = bq.querySelectorAll('[data-badge-type="ai"]');
    for (var r = 0; r < aiBadges.length; r++) {
      if (aiBadges[r].style.display === 'none') {
        aiBadges[r].style.display = '';
        aiBadges[r].classList.add('badge-appearing');
        (function (el) {
          setTimeout(function () {
            el.classList.remove('badge-appearing');
          }, 200);
        })(aiBadges[r]);
      }
    }

    delete deletedBadges[bq.id];
    deletedBadgesStore.set(deletedBadges);
    updateRestoreButton(bq);
  });

  // ── User tag delete ──

  document.addEventListener('click', function (e) {
    var del = e.target.closest('.badge-delete');
    if (!del) return;
    e.preventDefault();
    e.stopPropagation();
    var tagEl = del.closest('.badge-user');
    if (!tagEl) return;
    var bq = tagEl.closest('blockquote');
    if (!bq || !bq.id) return;
    var tagName = tagEl.getAttribute('data-tag-name');

    // Animate removal.
    tagEl.classList.add('badge-removing');
    tagEl.addEventListener(
      'animationend',
      function () {
        tagEl.remove();
      },
      { once: true }
    );

    // Persist.
    var id = bq.id;
    if (userTags[id]) {
      userTags[id] = userTags[id].filter(function (t) {
        return t !== tagName;
      });
      if (userTags[id].length === 0) delete userTags[id];
      persistUserTags(userTags);
    }
  });

  // ── Add tag flow (click "+") ──

  document.addEventListener('click', function (e) {
    var addBtnEl = e.target.closest('.badge-add');
    if (!addBtnEl) return;
    e.preventDefault();
    var bq = addBtnEl.closest('blockquote');
    if (!bq || !bq.id) return;
    openTagInput(addBtnEl, bq);
  });

  // ── Close tag input on outside click ──

  document.addEventListener('click', function (e) {
    if (!activeTagInput) return;
    if (
      !activeTagInput.wrap.contains(e.target) &&
      !e.target.closest('.badge-add')
    ) {
      closeTagInput(false);
    }
  });
}
