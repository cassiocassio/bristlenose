/**
 * search.js — Search-as-you-type filtering for report quotes.
 *
 * A collapsible search field in the toolbar filters blockquotes by
 * matching against .quote-text, .speaker-link, and .badge text content.
 *
 * Search overrides the view-switcher: an active query (>= 3 chars)
 * searches across ALL quotes regardless of the current view mode.
 * When the query is cleared, the view-switcher state is restored.
 *
 * In "participants" view the search container is hidden (no quotes).
 *
 * Dependencies: csv-export.js (currentViewMode global).
 *
 * @module search
 */

/* global currentViewMode */

var _searchTimer = null;
var _searchQuery = '';
var _savedViewLabel = '';

/**
 * Initialise the search filter: wire up toggle, input, and keyboard handlers.
 */
function initSearchFilter() {
  var container = document.getElementById('search-container');
  var toggle = document.getElementById('search-toggle');
  var input = document.getElementById('search-input');
  var clear = document.getElementById('search-clear');
  if (!container || !toggle || !input) return;

  toggle.addEventListener('click', function () {
    if (container.classList.contains('expanded')) {
      if (!input.value) {
        _collapseSearch(container, input);
      } else {
        input.focus();
      }
    } else {
      _expandSearch(container, input);
    }
  });

  input.addEventListener('input', function () {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(function () {
      _searchQuery = input.value.trim().toLowerCase();
      _applySearchFilter();
    }, 150);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      input.value = '';
      _searchQuery = '';
      _applySearchFilter();
      _collapseSearch(container, input);
    }
  });

  if (clear) {
    clear.addEventListener('click', function () {
      input.value = '';
      _searchQuery = '';
      _applySearchFilter();
      input.focus();
    });
  }
}

function _expandSearch(container, input) {
  container.classList.add('expanded');
  input.focus();
}

function _collapseSearch(container, input) {
  container.classList.remove('expanded');
  input.value = '';
  _searchQuery = '';
  _applySearchFilter();
}

/**
 * Apply the current search filter to all blockquotes.
 *
 * When query >= 3 chars: search across ALL quotes (overrides view mode).
 * When query < 3 chars: restore the view-switcher's visibility state.
 */
function _applySearchFilter() {
  var container = document.getElementById('search-container');
  if (currentViewMode === 'participants') return;

  _clearHighlights();

  var query = _searchQuery;

  if (query.length < 3) {
    if (container) container.classList.remove('has-query');
    _restoreViewMode();
    return;
  }

  if (container) container.classList.add('has-query');

  // Search across all quotes regardless of view mode.
  var bqs = document.querySelectorAll('.quote-group blockquote');
  var matchCount = 0;
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i].classList.contains('bn-hidden')) {
      bqs[i].style.display = 'none';
      continue;
    }
    var matches = _matchesQuery(bqs[i], query);
    bqs[i].style.display = matches ? '' : 'none';
    if (matches) matchCount++;
  }

  _highlightMatches(query);
  _setNonQuoteVisibility('none');

  var label = matchCount === 0 ? 'No matching quotes '
    : matchCount === 1 ? '1 matching quote '
    : matchCount + ' matching quotes ';
  _overrideViewLabel(label);
  _hideEmptySections();
}

/**
 * Show or hide the ToC row and Participants section during search.
 *
 * @param {string} display '' to show, 'none' to hide.
 */
function _setNonQuoteVisibility(display) {
  var toc = document.querySelector('.toc-row');
  if (toc) toc.style.display = display;

  // Find Participants section by its h2 text.
  var sections = document.querySelectorAll('.bn-tab-panel section');
  for (var i = 0; i < sections.length; i++) {
    var h2 = sections[i].querySelector('h2');
    if (h2 && h2.textContent.trim() === 'Participants') {
      sections[i].style.display = display;
      // Also hide the preceding <hr>.
      var prev = sections[i].previousElementSibling;
      if (prev && prev.tagName === 'HR') prev.style.display = display;
      break;
    }
  }
}

/**
 * Override the view-switcher button label during an active search.
 *
 * Saves the current label on first call so it can be restored later.
 *
 * @param {string} label The temporary label text.
 */
function _overrideViewLabel(label) {
  var btn = document.getElementById('view-switcher-btn');
  if (!btn || !btn.firstChild) return;
  if (!_savedViewLabel) _savedViewLabel = btn.firstChild.textContent;
  btn.firstChild.textContent = label;
}

/**
 * Restore the view-switcher button label saved before search override.
 */
function _restoreViewLabel() {
  if (!_savedViewLabel) return;
  var btn = document.getElementById('view-switcher-btn');
  if (btn && btn.firstChild) btn.firstChild.textContent = _savedViewLabel;
  _savedViewLabel = '';
}

/**
 * Wrap matched substrings in visible .quote-text elements with <mark>.
 *
 * @param {string} query Lowercase query string (>= 3 chars).
 */
function _highlightMatches(query) {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i].style.display === 'none') continue;
    var span = bqs[i].querySelector('.quote-text');
    if (span) _highlightTextNodes(span, query);
  }
}

/**
 * Walk text nodes inside an element and wrap query matches in <mark>.
 *
 * @param {Element} el    The element to search within.
 * @param {string}  query Lowercase query string.
 */
function _highlightTextNodes(el, query) {
  var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
  var nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    var text = node.nodeValue;
    var lower = text.toLowerCase();
    var idx = lower.indexOf(query);
    if (idx === -1) continue;

    var frag = document.createDocumentFragment();
    var pos = 0;
    while (idx !== -1) {
      if (idx > pos) frag.appendChild(document.createTextNode(text.slice(pos, idx)));
      var mark = document.createElement('mark');
      mark.className = 'search-mark';
      mark.textContent = text.slice(idx, idx + query.length);
      frag.appendChild(mark);
      pos = idx + query.length;
      idx = lower.indexOf(query, pos);
    }
    if (pos < text.length) frag.appendChild(document.createTextNode(text.slice(pos)));
    node.parentNode.replaceChild(frag, node);
  }
}

/**
 * Remove all <mark class="search-mark"> elements, unwrapping their text.
 */
function _clearHighlights() {
  var marks = document.querySelectorAll('.search-mark');
  for (var i = 0; i < marks.length; i++) {
    var mark = marks[i];
    var parent = mark.parentNode;
    parent.replaceChild(document.createTextNode(mark.textContent), mark);
    parent.normalize();
  }
}

/**
 * Check if a blockquote matches the current search query.
 *
 * @param {Element} bq    A blockquote element.
 * @param {string}  query Lowercase query string (>= 3 chars).
 * @returns {boolean}
 */
function _matchesQuery(bq, query) {
  var textEl = bq.querySelector('.quote-text');
  if (textEl && textEl.textContent.toLowerCase().indexOf(query) !== -1) {
    return true;
  }

  var speakerEl = bq.querySelector('.speaker-link');
  if (speakerEl && speakerEl.textContent.toLowerCase().indexOf(query) !== -1) {
    return true;
  }

  var badges = bq.querySelectorAll('.badge');
  for (var j = 0; j < badges.length; j++) {
    if (badges[j].classList.contains('badge-add')) continue;
    var tagText = (
      badges[j].getAttribute('data-tag-name') || badges[j].textContent
    ).trim().toLowerCase();
    if (tagText.indexOf(query) !== -1) return true;
  }

  return false;
}

/**
 * Restore the view-switcher's visibility state (no active search).
 *
 * Re-applies quote and section visibility for the current view mode,
 * then clears any section hiding left over from a previous search.
 */
function _restoreViewMode() {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  var sections = document.querySelectorAll('.bn-tab-panel section');
  var hrs = document.querySelectorAll('.bn-tab-panel hr');

  if (currentViewMode === 'starred') {
    for (var i = 0; i < bqs.length; i++) {
      if (bqs[i].classList.contains('bn-hidden')) {
        bqs[i].style.display = 'none';
        continue;
      }
      bqs[i].style.display = bqs[i].classList.contains('starred') ? '' : 'none';
    }
  } else {
    for (var i = 0; i < bqs.length; i++) {
      if (bqs[i].classList.contains('bn-hidden')) continue;
      bqs[i].style.display = '';
    }
  }

  // Restore ToC, Participants, and view-switcher label.
  _setNonQuoteVisibility('');
  _restoreViewLabel();

  // Restore all sections and hrs.
  for (var i = 0; i < sections.length; i++) sections[i].style.display = '';
  for (var i = 0; i < hrs.length; i++) hrs[i].style.display = '';

  // Restore subsection elements (h3, descriptions, quote-groups).
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) {
    groups[i].style.display = '';
    var prev = groups[i].previousElementSibling;
    if (prev && prev.classList && prev.classList.contains('description')) {
      prev.style.display = '';
      prev = prev.previousElementSibling;
    }
    if (prev && prev.tagName === 'H3') {
      prev.style.display = '';
    }
  }

  // Re-apply tag filter after restoring view mode.
  if (typeof _applyTagFilter === 'function') _applyTagFilter();
}

/**
 * Hide sections where ALL child blockquotes are display:none.
 * Also hide the preceding <hr> sibling of hidden sections.
 * Only processes sections that contain .quote-group (not Participants,
 * Sentiment or Journeys).
 *
 * Sections with hidden-quotes badges remain visible even if all
 * blockquotes are hidden — the badge is the evidence indicator.
 */
function _hideEmptySections() {
  var sections = document.querySelectorAll('.bn-tab-panel section');
  for (var i = 0; i < sections.length; i++) {
    var section = sections[i];
    var quoteGroups = section.querySelectorAll('.quote-group');
    if (!quoteGroups.length) continue;

    var hasVisible = false;
    var allBqs = section.querySelectorAll('.quote-group blockquote');
    for (var j = 0; j < allBqs.length; j++) {
      if (allBqs[j].style.display !== 'none') {
        hasVisible = true;
        break;
      }
    }

    // Keep section visible if it has hidden-quotes badges.
    if (!hasVisible && section.querySelector('.bn-hidden-badge')) {
      hasVisible = true;
    }

    section.style.display = hasVisible ? '' : 'none';

    var prev = section.previousElementSibling;
    if (prev && prev.tagName === 'HR') {
      prev.style.display = hasVisible ? '' : 'none';
    }
  }

  _hideEmptySubsections();
}

/**
 * Within a section, hide individual h3 + .description + .quote-group
 * clusters where all quotes are hidden.
 *
 * Groups with hidden-quotes badges remain visible — the badge shows
 * the researcher that evidence exists even when all quotes are hidden.
 */
function _hideEmptySubsections() {
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) {
    var group = groups[i];
    var allBqs = group.querySelectorAll('blockquote');
    var hasVisible = false;
    for (var j = 0; j < allBqs.length; j++) {
      if (allBqs[j].style.display !== 'none') {
        hasVisible = true;
        break;
      }
    }

    // Keep group visible if it has a hidden-quotes badge.
    if (!hasVisible && group.querySelector('.bn-hidden-badge')) {
      hasVisible = true;
    }

    var visible = hasVisible ? '' : 'none';
    group.style.display = visible;

    var prev = group.previousElementSibling;
    if (prev && prev.classList && prev.classList.contains('description')) {
      prev.style.display = visible;
      prev = prev.previousElementSibling;
    }
    if (prev && prev.tagName === 'H3') {
      prev.style.display = visible;
    }
  }
}

/**
 * Called by the view-switcher when the view mode changes.
 * Hides or shows the search container and re-applies the filter.
 */
function _onViewModeChange() {
  var container = document.getElementById('search-container');
  if (!container) return;

  if (currentViewMode === 'participants') {
    container.style.display = 'none';
    var input = document.getElementById('search-input');
    if (input) {
      input.value = '';
      _searchQuery = '';
    }
    container.classList.remove('expanded');
    container.classList.remove('has-query');
  } else {
    container.style.display = '';
    _applySearchFilter();
  }
}
