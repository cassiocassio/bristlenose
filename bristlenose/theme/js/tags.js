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

/* global createStore, createUserTagBadge, animateBadgeRemoval, renderUserTagsChart, getTagColourVar */

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
  // Re-apply tag filter to account for added/removed tags.
  if (typeof _applyTagFilter === 'function') _applyTagFilter();
  if (typeof _updateTagFilterButton === 'function') _updateTagFilterButton();
  // Update dashboard stat card.
  _updateDashboardTagsStat();
}

/**
 * Update the "user tags in N groups" stat card on the Project dashboard.
 * Reads the live userTags map and codebook group count.
 */
function _updateDashboardTagsStat() {
  var el = document.getElementById('dashboard-user-tags-stat');
  if (!el) return;
  var valEl = document.getElementById('dashboard-user-tags-value');
  var lblEl = document.getElementById('dashboard-user-tags-label');
  if (!valEl || !lblEl) return;

  // Count distinct tag names across all quotes.
  var tagSet = {};
  Object.keys(userTags).forEach(function (qid) {
    (userTags[qid] || []).forEach(function (t) { tagSet[t] = true; });
  });
  var nTags = Object.keys(tagSet).length;
  if (nTags === 0) { el.style.display = 'none'; return; }

  valEl.textContent = nTags;
  lblEl.textContent = 'user tags';
  el.style.display = '';
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
 * Create a user-tag badge DOM element with fade-in animation.
 *
 * Thin wrapper around shared `createUserTagBadge()` (badge-utils.js) that
 * adds the report-specific fade-in animation and codebook colour lookup.
 *
 * @param {string} name The tag text.
 * @returns {Element} A `<span class="badge badge-user">` with a delete button.
 */
function createUserTagEl(name) {
  var colourVar = (typeof getTagColourVar === 'function') ? getTagColourVar(name) : null;
  var span = createUserTagBadge(name, colourVar);
  span.classList.add('badge-appearing');
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
 * Also updates the inline ghost text with the best prefix match.
 *
 * @param {HTMLInputElement} input The tag input element.
 * @param {Element}          wrap  The `.tag-input-wrap` container.
 */
function buildSuggest(input, wrap) {
  var old = wrap.querySelector('.tag-suggest');
  if (old) old.remove();
  suggestIndex = -1;

  var ghost = activeTagInput ? activeTagInput.ghost : null;
  var val = input.value.trim().toLowerCase();
  var rawVal = input.value; // preserve case for ghost text matching

  // Clear ghost if no input.
  if (!val) {
    if (ghost) ghost.textContent = '';
    return;
  }

  // Collect tags that ALL target quotes already have (intersection).
  // Only filter out a tag if every target quote has it.
  var existing = [];
  if (activeTagInput && activeTagInput.targetIds && activeTagInput.targetIds.length > 0) {
    // Bulk mode: compute intersection of existing tags across all targets
    var targetIds = activeTagInput.targetIds;
    var firstTags = userTags[targetIds[0]] || [];
    existing = firstTags.filter(function(t) {
      var tLower = t.toLowerCase();
      return targetIds.every(function(qid) {
        var qTags = userTags[qid] || [];
        return qTags.some(function(qt) { return qt.toLowerCase() === tLower; });
      });
    }).map(function(t) { return t.toLowerCase(); });
  } else {
    // Single quote mode
    var bq = activeTagInput ? activeTagInput.bq : null;
    existing = bq && bq.id && userTags[bq.id] ? userTags[bq.id].map(function (t) { return t.toLowerCase(); }) : [];
  }

  var names = allTagNames().filter(function (n) {
    return n.toLowerCase().indexOf(val) !== -1 && n.toLowerCase() !== val && existing.indexOf(n.toLowerCase()) === -1;
  });

  // Find best prefix match for ghost text (must start with typed text).
  var prefixMatches = names.filter(function (n) {
    return n.toLowerCase().indexOf(val) === 0;
  });

  // Update ghost text: show suffix of best prefix match.
  if (ghost) {
    if (prefixMatches.length > 0) {
      // Show the part of the suggestion after what's typed.
      var best = prefixMatches[0];
      ghost.textContent = best.substring(rawVal.length);
    } else {
      ghost.textContent = '';
    }
  }

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
      if (ghost) ghost.textContent = '';
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
 * @param {boolean} [reopenAfterCommit=false] If true and a tag was committed,
 *        immediately open a fresh input for adding another tag.
 */
function closeTagInput(commit, reopenAfterCommit) {
  if (!activeTagInput) return;
  var ati = activeTagInput;
  activeTagInput = null;
  var val = ati.input.value.trim();
  var didCommit = false;

  if (commit && val) {
    // Determine target quote IDs: bulk mode or single quote
    var targetIds = ati.targetIds && ati.targetIds.length > 0 ? ati.targetIds : [ati.bq.id];

    targetIds.forEach(function(qid) {
      if (!userTags[qid]) userTags[qid] = [];
      // Avoid duplicates per quote
      if (userTags[qid].indexOf(val) === -1) {
        userTags[qid].push(val);
        // Insert DOM element for this quote
        var bq = document.getElementById(qid);
        if (bq) {
          var addBtn = bq.querySelector('.badge-add');
          if (addBtn) {
            var tagEl = createUserTagEl(val);
            addBtn.parentNode.insertBefore(tagEl, addBtn);
          }
        }
        didCommit = true;
      }
    });

    if (didCommit) {
      persistUserTags(userTags);
    }
  }

  ati.wrap.remove();
  ati.addBtn.style.display = '';

  // Re-open for another tag if requested and we actually added one.
  // In bulk mode, re-open with same targetIds.
  if (reopenAfterCommit && didCommit) {
    openTagInput(ati.addBtn, ati.bq, ati.targetIds);
  }
}

/**
 * Open the inline tag input, replacing the "+" ghost-badge.
 *
 * @param {Element} addBtn The `.badge-add` element that was clicked.
 * @param {Element} bq     The parent blockquote.
 * @param {string[]} [targetIds] Optional array of quote IDs for bulk tagging.
 */
function openTagInput(addBtn, bq, targetIds) {
  if (activeTagInput) closeTagInput(false);

  addBtn.style.display = 'none';

  // Build input wrapper with ghost text support.
  // Structure: .tag-input-wrap > .tag-input-box > (input + .tag-ghost-layer > spacer + ghost) + .tag-sizer
  // The ghost layer is stacked on top of input via CSS grid. Spacer pushes ghost to align after typed text.
  var wrap = document.createElement('span');
  wrap.className = 'tag-input-wrap';

  var box = document.createElement('span');
  box.className = 'tag-input-box';

  var input = document.createElement('input');
  input.className = 'tag-input';
  input.type = 'text';
  input.placeholder = 'tag';

  var ghostLayer = document.createElement('span');
  ghostLayer.className = 'tag-ghost-layer';

  var ghostSpacer = document.createElement('span');
  ghostSpacer.className = 'tag-ghost-spacer';

  var ghost = document.createElement('span');
  ghost.className = 'tag-ghost';

  ghostLayer.appendChild(ghostSpacer);
  ghostLayer.appendChild(ghost);

  var sizer = document.createElement('span');
  sizer.className = 'tag-sizer';

  box.appendChild(input);
  box.appendChild(ghostLayer);
  wrap.appendChild(box);
  wrap.appendChild(sizer);
  addBtn.parentNode.insertBefore(wrap, addBtn);
  input.focus();

  activeTagInput = { bq: bq, wrap: wrap, input: input, addBtn: addBtn, ghost: ghost, ghostSpacer: ghostSpacer, sizer: sizer, targetIds: targetIds || null };

  // Auto-resize box to fit typed text + ghost; update spacer to align ghost.
  function updateSize() {
    var fullText = input.value + ghost.textContent;
    sizer.textContent = fullText || input.placeholder;
    var w = Math.max(sizer.offsetWidth + 16, 48);
    box.style.width = w + 'px';
    // Spacer mirrors the typed text so ghost appears right after it.
    ghostSpacer.textContent = input.value;
  }

  // Set initial width so the box opens close to its final size.
  buildSuggest(input, wrap);
  updateSize();

  input.addEventListener('input', function () {
    buildSuggest(input, wrap);
    updateSize();
  });

  // Update ghost text to reflect the highlighted suggestion.
  function updateGhostForSelection(idx) {
    if (!ghost) return;
    if (idx >= 0) {
      var sel = getSuggestValue(wrap, idx);
      if (sel && sel.toLowerCase().indexOf(input.value.toLowerCase()) === 0) {
        ghost.textContent = sel.substring(input.value.length);
      } else {
        // Highlighted item doesn't start with typed text — show full replacement hint.
        ghost.textContent = '';
      }
    } else {
      // No selection — rebuild ghost from best prefix match.
      buildSuggest(input, wrap);
    }
    updateSize();
  }

  // Keyboard navigation within the suggest dropdown.
  input.addEventListener('keydown', function (ev) {
    var count = suggestCount(wrap);

    if (ev.key === 'ArrowRight' && ghost.textContent) {
      // Accept ghost text (like fish shell).
      ev.preventDefault();
      input.value = input.value + ghost.textContent;
      ghost.textContent = '';
      updateSize();
      buildSuggest(input, wrap); // refresh dropdown
    } else if (ev.key === 'ArrowDown' && count > 0) {
      ev.preventDefault();
      // Loop: at bottom, go back to -1 (no selection).
      if (suggestIndex >= count - 1) {
        suggestIndex = -1;
      } else {
        suggestIndex++;
      }
      highlightSuggestItem(wrap, suggestIndex);
      updateGhostForSelection(suggestIndex);
    } else if (ev.key === 'ArrowUp' && count > 0) {
      ev.preventDefault();
      // Loop: at -1, go to bottom.
      if (suggestIndex <= -1) {
        suggestIndex = count - 1;
      } else {
        suggestIndex--;
      }
      highlightSuggestItem(wrap, suggestIndex);
      updateGhostForSelection(suggestIndex);
    } else if (ev.key === 'Tab') {
      ev.preventDefault();
      // Tab commits and re-opens for another tag.
      // If ghost text visible, accept it first.
      if (ghost.textContent) {
        input.value = input.value + ghost.textContent;
        ghost.textContent = '';
      } else if (suggestIndex >= 0) {
        var picked = getSuggestValue(wrap, suggestIndex);
        if (picked) input.value = picked;
      } else if (count > 0) {
        // No highlight but suggestions exist — pick the first one.
        var first = getSuggestValue(wrap, 0);
        if (first) input.value = first;
      }
      // Only re-open if there's something to commit.
      var hasValue = input.value.trim().length > 0;
      closeTagInput(hasValue, hasValue);
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      ev.stopPropagation();  // Don't let focus.js intercept this
      // Accept ghost text or highlighted suggestion.
      if (ghost.textContent) {
        input.value = input.value + ghost.textContent;
        ghost.textContent = '';
      } else if (suggestIndex >= 0) {
        var pickedEnter = getSuggestValue(wrap, suggestIndex);
        if (pickedEnter) input.value = pickedEnter;
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

    // Animate and hide (not remove — may be restored).
    animateBadgeRemoval(badge, { hide: true });

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

    // Animate and remove from DOM.
    animateBadgeRemoval(tagEl);

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
    // Use multi-select only if the clicked quote is part of the selection.
    // Otherwise tag only the clicked quote — don't leak the selection from
    // a previously-focused quote (the user explicitly clicked [+] on this one).
    var targetIds = null;
    if (typeof getSelectedQuoteIds === 'function') {
      var selected = getSelectedQuoteIds();
      if (selected && selected.size > 0 && selected.has(bq.id)) {
        targetIds = Array.from(selected);
      }
    }
    openTagInput(addBtnEl, bq, targetIds);
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

  // Populate dashboard stat card on initial load.
  _updateDashboardTagsStat();
}
