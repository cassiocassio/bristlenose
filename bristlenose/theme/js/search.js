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

/**
 * Initialise the search filter: wire up toggle, input, and keyboard handlers.
 */
function initSearchFilter() {
  var container = document.getElementById('search-container');
  var toggle = document.getElementById('search-toggle');
  var input = document.getElementById('search-input');
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
  if (currentViewMode === 'participants') return;

  var query = _searchQuery;

  if (query.length < 3) {
    _restoreViewMode();
    return;
  }

  // Search across all quotes regardless of view mode.
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    bqs[i].style.display = _matchesQuery(bqs[i], query) ? '' : 'none';
  }

  _hideEmptySections();
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
  var sections = document.querySelectorAll('article > section');
  var hrs = document.querySelectorAll('article > hr');

  if (currentViewMode === 'favourites') {
    for (var i = 0; i < bqs.length; i++) {
      bqs[i].style.display = bqs[i].classList.contains('favourited') ? '' : 'none';
    }
  } else {
    for (var i = 0; i < bqs.length; i++) {
      bqs[i].style.display = '';
    }
  }

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
}

/**
 * Hide sections where ALL child blockquotes are display:none.
 * Also hide the preceding <hr> sibling of hidden sections.
 * Only processes sections that contain .quote-group (not Participants,
 * Sentiment, Friction, or Journeys).
 */
function _hideEmptySections() {
  var sections = document.querySelectorAll('article > section');
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
  } else {
    container.style.display = '';
    _applySearchFilter();
  }
}
