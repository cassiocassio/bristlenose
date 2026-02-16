/**
 * hidden.js — Hide / unhide quotes for volume management.
 *
 * Researchers can hide "volume quotes" — quotes that serve as evidence but
 * create visual overload.  Hidden quotes are persistent (localStorage) and
 * independent of the search, tag-filter, and starred view filters.
 *
 * Each `.quote-group` that contains hidden quotes gets a badge showing the
 * count and a dropdown listing truncated previews.  Clicking the preview
 * text unhides the quote back to its original position.
 *
 * Architecture
 * ────────────
 * - `hiddenQuotes` (object): in-memory map of quote ID → `true`.
 * - `.bn-hidden` class on the blockquote provides `display: none !important`
 *   as defence-in-depth.  JS also sets inline `style.display = 'none'`.
 * - All visibility-restore paths in other modules (view-switcher, search,
 *   tag-filter) guard against `.bn-hidden` so they never accidentally show
 *   a hidden quote.
 * - Badge + dropdown are JS-injected (not in static HTML) — they only
 *   appear when hidden quotes exist.
 *
 * Dependencies: `createStore` (storage.js), `showToast` (csv-export.js).
 *
 * @module hidden
 */

/* global createStore, showToast, currentViewMode, isServeMode, apiPut */

var hiddenStore = createStore('bristlenose-hidden');
var hiddenQuotes = hiddenStore.get({});

// ── Animation constants ──────────────────────────────────────────────────

var _HIDE_DURATION = 300; // ms

// ── Core hide / unhide ───────────────────────────────────────────────────

/**
 * Collect bounding rects for all visible siblings below `bq` in its group.
 *
 * @param {Element} group  The `.quote-group` container.
 * @param {Element} bq     The quote being hidden/shown (excluded).
 * @returns {Array<{el: Element, top: number}>}
 */
function _snapshotSiblings(group, bq) {
  var siblings = [];
  var bqs = group.querySelectorAll('blockquote');
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i] === bq) continue;
    if (bqs[i].style.display === 'none') continue;
    siblings.push({ el: bqs[i], top: bqs[i].getBoundingClientRect().top });
  }
  return siblings;
}

/**
 * Animate sibling quotes from their old positions to their new positions.
 *
 * @param {Array<{el: Element, top: number}>} siblings  Snapshot from before layout change.
 */
function _animateSiblings(siblings) {
  for (var i = 0; i < siblings.length; i++) {
    var s = siblings[i];
    var newTop = s.el.getBoundingClientRect().top;
    var dy = s.top - newTop;
    if (Math.abs(dy) < 1) continue;
    s.el.style.transform = 'translateY(' + dy + 'px)';
    s.el.style.transition = 'none';
  }
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      for (var j = 0; j < siblings.length; j++) {
        siblings[j].el.style.transition = 'transform ' + _HIDE_DURATION + 'ms ease';
        siblings[j].el.style.transform = '';
      }
      setTimeout(function () {
        for (var k = 0; k < siblings.length; k++) {
          siblings[k].el.style.transition = '';
        }
      }, _HIDE_DURATION + 50);
    });
  });
}

/**
 * Hide a quote by ID with animation.
 *
 * The quote shrinks and fades toward the hidden-quotes badge while
 * sibling quotes slide up to fill the gap.
 *
 * @param {string} quoteId
 */
function hideQuote(quoteId) {
  var bq = document.getElementById(quoteId);
  if (!bq) return;

  var group = bq.closest('.quote-group');

  // Snapshot sibling positions before layout change.
  var siblings = group ? _snapshotSiblings(group, bq) : [];

  // Record the quote's current rect for the shrink animation.
  var bqRect = bq.getBoundingClientRect();

  // Update state immediately.
  hiddenQuotes[quoteId] = true;
  hiddenStore.set(hiddenQuotes);
  if (isServeMode()) apiPut('/hidden', hiddenQuotes);

  // Create a ghost clone BEFORE hiding (needs visible content + dimensions).
  var ghost = bq.cloneNode(true);
  ghost.style.position = 'fixed';
  ghost.style.left = bqRect.left + 'px';
  ghost.style.top = bqRect.top + 'px';
  ghost.style.width = bqRect.width + 'px';
  ghost.style.height = bqRect.height + 'px';
  ghost.style.margin = '0';
  ghost.style.zIndex = '500';
  ghost.style.pointerEvents = 'none';
  ghost.style.opacity = '1';
  ghost.style.overflow = 'hidden';
  ghost.classList.remove('bn-hidden');
  ghost.classList.remove('bn-focused');
  ghost.removeAttribute('id');
  document.body.appendChild(ghost);

  // Hide the real quote so siblings can fill the gap.
  bq.classList.add('bn-hidden');
  bq.style.display = 'none';

  // Animate siblings sliding up.
  _animateSiblings(siblings);

  // Build the badge AFTER adding .bn-hidden so the count is correct.
  // (Previously built before — caused off-by-one: first hide showed no badge.)
  if (group) _updateBadgeForGroup(group);
  var badge = group ? group.querySelector('.bn-hidden-badge') : null;

  // Compute the target rect (badge position) for the shrink.
  var targetRect = badge ? badge.getBoundingClientRect() : null;

  // Animate the ghost shrinking toward the badge.
  if (targetRect) {
    requestAnimationFrame(function () {
      ghost.style.transition = 'all ' + _HIDE_DURATION + 'ms ease';
      ghost.style.left = targetRect.left + 'px';
      ghost.style.top = targetRect.top + 'px';
      ghost.style.width = targetRect.width + 'px';
      ghost.style.height = '0px';
      ghost.style.opacity = '0';
    });
  } else {
    requestAnimationFrame(function () {
      ghost.style.transition = 'opacity ' + _HIDE_DURATION + 'ms ease';
      ghost.style.opacity = '0';
    });
  }

  setTimeout(function () {
    ghost.remove();
  }, _HIDE_DURATION + 50);

  // Hide empty sections / subsections.
  if (typeof _hideEmptySections === 'function') _hideEmptySections();

  showToast('Quote hidden');
}

/**
 * Unhide a quote by ID with animation, respecting current view mode
 * and tag filter.
 *
 * The quote expands from the badge position into its slot while sibling
 * quotes slide down to make room.
 *
 * @param {string} quoteId
 */
function unhideQuote(quoteId) {
  var bq = document.getElementById(quoteId);
  if (!bq) return;

  var group = bq.closest('.quote-group');
  var badge = group ? group.querySelector('.bn-hidden-badge') : null;
  var badgeRect = badge ? badge.getBoundingClientRect() : null;

  // Snapshot sibling positions before layout change.
  var siblings = group ? _snapshotSiblings(group, bq) : [];

  // Update state.
  bq.classList.remove('bn-hidden');
  delete hiddenQuotes[quoteId];
  hiddenStore.set(hiddenQuotes);
  if (isServeMode()) apiPut('/hidden', hiddenQuotes);

  // Determine visibility based on current view mode.
  var shouldShow = true;
  if (currentViewMode === 'starred' && !bq.classList.contains('starred')) {
    shouldShow = false;
  }

  if (shouldShow) {
    bq.style.display = '';
  } else {
    bq.style.display = 'none';
  }

  if (group) _updateBadgeForGroup(group);

  // Re-apply tag filter if active — it may need to hide this quote.
  if (typeof _isTagFilterActive === 'function' && _isTagFilterActive()) {
    if (typeof _applyTagFilter === 'function') _applyTagFilter();
  }

  // Restore sections that may have been hidden.
  if (typeof _hideEmptySections === 'function') _hideEmptySections();

  // Animate if the quote is actually visible.
  if (bq.style.display !== 'none') {
    // Animate siblings sliding down.
    _animateSiblings(siblings);

    // Animate the quote expanding from the badge position.
    var bqRect = bq.getBoundingClientRect();

    if (badgeRect) {
      var dy = badgeRect.top - bqRect.top;
      var scaleX = badgeRect.width / Math.max(bqRect.width, 1);
      bq.style.transform = 'translateY(' + dy + 'px) scaleY(0.01)';
      bq.style.transformOrigin = 'top right';
      bq.style.opacity = '0';
      bq.style.transition = 'none';

      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          bq.style.transition = 'all ' + _HIDE_DURATION + 'ms ease';
          bq.style.transform = '';
          bq.style.opacity = '1';
        });
      });

      setTimeout(function () {
        bq.style.transition = '';
        bq.style.transform = '';
        bq.style.transformOrigin = '';
        bq.style.opacity = '';
      }, _HIDE_DURATION + 50);
    }

    // Scroll to the restored quote.
    bq.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

/**
 * Check if a quote is hidden.
 *
 * @param {string} quoteId
 * @returns {boolean}
 */
function isHidden(quoteId) {
  return !!hiddenQuotes[quoteId];
}

/**
 * Hide all currently selected quotes (bulk operation).
 * Called by focus.js when `h` is pressed with a multi-select active.
 */
function bulkHideSelected() {
  if (typeof getSelectedQuoteIds !== 'function') return;
  var ids = getSelectedQuoteIds();
  if (!ids || !ids.size) return;

  // Collect affected groups for badge updates.
  var groups = new Set();
  ids.forEach(function (id) {
    var bq = document.getElementById(id);
    if (!bq || bq.classList.contains('bn-hidden')) return;

    bq.classList.add('bn-hidden');
    bq.style.display = 'none';
    hiddenQuotes[id] = true;

    var g = bq.closest('.quote-group');
    if (g) groups.add(g);
  });

  hiddenStore.set(hiddenQuotes);
  if (isServeMode()) apiPut('/hidden', hiddenQuotes);

  groups.forEach(function (g) {
    _updateBadgeForGroup(g);
  });

  if (typeof _hideEmptySections === 'function') _hideEmptySections();
  if (typeof clearSelection === 'function') clearSelection();

  var count = ids.size;
  showToast(count + ' quote' + (count !== 1 ? 's' : '') + ' hidden');
}

// ── Badge management ─────────────────────────────────────────────────────

/**
 * Truncate quote text to a maximum length.
 *
 * @param {string} text
 * @param {number} max
 * @returns {string}
 */
function _truncateQuote(text, max) {
  if (!text) return '';
  // Strip smart quotes for the preview.
  text = text.replace(/^[\u201c\u201d"]+|[\u201c\u201d"]+$/g, '').trim();
  if (text.length <= max) return '\u201c' + text + '\u201d';
  return '\u201c' + text.substring(0, max).trim() + '\u2026\u201d';
}

/**
 * Create or update the hidden-quotes badge for a single `.quote-group`.
 * Removes the badge if no quotes are hidden in the group.
 *
 * @param {Element} group  The `.quote-group` container.
 */
function _updateBadgeForGroup(group) {
  var hiddenBqs = group.querySelectorAll('blockquote.bn-hidden');
  var badge = group.querySelector('.bn-hidden-badge');

  if (!hiddenBqs.length) {
    // No hidden quotes — remove badge if present.
    if (badge) badge.remove();
    return;
  }

  if (!badge) {
    badge = document.createElement('div');
    badge.className = 'bn-hidden-badge';
    group.insertBefore(badge, group.firstChild);
  }

  var count = hiddenBqs.length;
  var label = count + ' hidden quote' + (count !== 1 ? 's' : '');

  // Build badge content.
  badge.innerHTML = '';

  // Toggle button.
  var toggle = document.createElement('button');
  toggle.className = 'bn-hidden-toggle';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.innerHTML = label + ' <span class="bn-hidden-chevron">&#x25BE;</span>';
  badge.appendChild(toggle);

  // Dropdown.
  var dropdown = document.createElement('div');
  dropdown.className = 'bn-hidden-dropdown';
  dropdown.style.display = 'none';

  var header = document.createElement('div');
  header.className = 'bn-hidden-header';
  header.textContent = 'Unhide:';
  dropdown.appendChild(header);

  var list = document.createElement('div');
  list.className = 'bn-hidden-list';

  for (var i = 0; i < hiddenBqs.length; i++) {
    var bq = hiddenBqs[i];
    var item = document.createElement('div');
    item.className = 'bn-hidden-item';
    item.setAttribute('data-quote-id', bq.id);

    // Timecode.
    var tcText = bq.getAttribute('data-timecode') || '';
    var tcEl = bq.querySelector('.timecode');
    if (tcEl && tcEl.getAttribute('data-seconds')) {
      var tc = document.createElement('a');
      tc.href = '#';
      tc.className = 'timecode';
      tc.setAttribute('data-participant', bq.getAttribute('data-participant') || '');
      tc.setAttribute('data-seconds', tcEl.getAttribute('data-seconds'));
      if (tcEl.getAttribute('data-end-seconds')) {
        tc.setAttribute('data-end-seconds', tcEl.getAttribute('data-end-seconds'));
      }
      tc.setAttribute('title', 'Play video');
      tc.textContent = '[' + tcText + ']';
      item.appendChild(tc);
    } else {
      var tcSpan = document.createElement('span');
      tcSpan.className = 'timecode';
      tcSpan.textContent = '[' + tcText + ']';
      item.appendChild(tcSpan);
    }

    // Quote preview — clicking this unhides.
    var quoteText = bq.querySelector('.quote-text');
    var rawText = quoteText ? quoteText.textContent : '';
    var preview = document.createElement('span');
    preview.className = 'bn-hidden-preview';
    preview.setAttribute('title', 'Unhide');
    preview.setAttribute('data-quote-id', bq.id);
    preview.textContent = _truncateQuote(rawText, 50);
    item.appendChild(preview);

    // Participant link.
    var speakerLink = bq.querySelector('.speaker-link');
    if (speakerLink) {
      var pid = document.createElement('a');
      pid.href = speakerLink.href;
      pid.className = 'speaker-link';
      pid.setAttribute('title', 'Open transcript');
      pid.textContent = bq.getAttribute('data-participant') || '';
      item.appendChild(pid);
    } else {
      var pidSpan = document.createElement('span');
      pidSpan.className = 'speaker-link';
      pidSpan.textContent = bq.getAttribute('data-participant') || '';
      item.appendChild(pidSpan);
    }

    list.appendChild(item);
  }

  dropdown.appendChild(list);
  badge.appendChild(dropdown);
}

/**
 * Rebuild badges for all `.quote-group` elements.
 */
function _updateAllBadges() {
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) {
    _updateBadgeForGroup(groups[i]);
  }
}

// ── Initialisation ───────────────────────────────────────────────────────

/**
 * Bootstrap hidden quotes: restore state from localStorage, build badges,
 * and attach event delegation for hide buttons, toggle buttons, and unhide.
 */
function initHidden() {
  // Restore hidden state and prune stale IDs.
  var changed = false;
  var ids = Object.keys(hiddenQuotes);
  for (var i = 0; i < ids.length; i++) {
    var bq = document.getElementById(ids[i]);
    if (bq) {
      bq.classList.add('bn-hidden');
      bq.style.display = 'none';
    } else {
      // Quote no longer in DOM — prune.
      delete hiddenQuotes[ids[i]];
      changed = true;
    }
  }
  if (changed) hiddenStore.set(hiddenQuotes);

  // Build initial badges.
  _updateAllBadges();

  // ── Event delegation ──

  document.addEventListener('click', function (e) {
    // Hide button on quote card.
    var hideBtn = e.target.closest('.hide-btn');
    if (hideBtn) {
      e.preventDefault();
      var bq = hideBtn.closest('blockquote');
      if (bq && bq.id) hideQuote(bq.id);
      return;
    }

    // Badge toggle — open/close dropdown.
    var toggle = e.target.closest('.bn-hidden-toggle');
    if (toggle) {
      e.stopPropagation();
      var badge = toggle.closest('.bn-hidden-badge');
      if (!badge) return;
      var dropdown = badge.querySelector('.bn-hidden-dropdown');
      if (!dropdown) return;

      var willOpen = dropdown.style.display === 'none';

      // Close all other open dropdowns first.
      var allDropdowns = document.querySelectorAll('.bn-hidden-dropdown');
      for (var d = 0; d < allDropdowns.length; d++) {
        allDropdowns[d].style.display = 'none';
        var t = allDropdowns[d].closest('.bn-hidden-badge');
        if (t) {
          var b = t.querySelector('.bn-hidden-toggle');
          if (b) b.setAttribute('aria-expanded', 'false');
        }
      }

      if (willOpen) {
        // Rebuild dropdown content to reflect current state.
        var group = badge.closest('.quote-group');
        if (group) _updateBadgeForGroup(group);
        // Re-fetch after rebuild.
        dropdown = badge.querySelector('.bn-hidden-dropdown');
        if (dropdown) dropdown.style.display = '';
        toggle.setAttribute('aria-expanded', 'true');
      }
      return;
    }

    // Unhide via preview text click.
    var preview = e.target.closest('.bn-hidden-preview');
    if (preview) {
      e.preventDefault();
      var qid = preview.getAttribute('data-quote-id');
      if (qid) unhideQuote(qid);
      return;
    }

    // Click inside dropdown — don't close (timecode/speaker links navigate normally).
    if (e.target.closest('.bn-hidden-dropdown')) return;

    // Outside click — close all open dropdowns.
    var openDropdowns = document.querySelectorAll('.bn-hidden-dropdown');
    for (var j = 0; j < openDropdowns.length; j++) {
      if (openDropdowns[j].style.display !== 'none') {
        openDropdowns[j].style.display = 'none';
        var parent = openDropdowns[j].closest('.bn-hidden-badge');
        if (parent) {
          var btn = parent.querySelector('.bn-hidden-toggle');
          if (btn) btn.setAttribute('aria-expanded', 'false');
        }
      }
    }
  });
}
