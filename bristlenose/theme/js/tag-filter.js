/**
 * tag-filter.js — Filter quotes by user-created tags via a dropdown menu.
 *
 * A dropdown button in the toolbar lists all user tags with checkboxes.
 * Unchecking a tag hides quotes whose only visible tags are unchecked.
 * A special "(No tags)" entry controls visibility of untagged quotes.
 *
 * State is persisted in localStorage.  The default is all-checked.
 *
 * Dependencies:
 *   - storage.js: createStore()
 *   - tags.js: allTagNames(), userTags
 *   - csv-export.js: currentViewMode
 *   - search.js: _hideEmptySections(), _hideEmptySubsections()
 *
 * @module tag-filter
 */

/* global createStore, allTagNames, userTags, currentViewMode */
/* global _hideEmptySections, _hideEmptySubsections */

var _tagFilterStore = createStore('bristlenose-tag-filter');
var _tagFilterState = _tagFilterStore.get({ unchecked: [], noTagsUnchecked: false, clearAll: false });

// Sentinel value for the "(No tags)" checkbox.
var _NO_TAGS_KEY = '__no_tags__';

/**
 * Initialise the tag-filter dropdown and wire up handlers.
 */
function initTagFilter() {
  var btn = document.getElementById('tag-filter-btn');
  var menu = document.getElementById('tag-filter-menu');
  if (!btn || !menu) return;

  // Toggle menu open/closed.
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    // Close view-switcher menu if open.
    var vsMenu = document.getElementById('view-switcher-menu');
    if (vsMenu) {
      vsMenu.classList.remove('open');
      var vsBtn = document.getElementById('view-switcher-btn');
      if (vsBtn) vsBtn.setAttribute('aria-expanded', 'false');
    }

    var willOpen = !menu.classList.contains('open');
    if (willOpen) {
      menu.style.width = '';  // Reset so content determines natural width.
      _buildTagFilterMenu(menu);
    }
    menu.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(willOpen));

    // Lock width after opening so search filtering doesn't cause shrinkage.
    if (willOpen) {
      menu.style.width = menu.offsetWidth + 'px';

      var searchInput = menu.querySelector('.tag-filter-search-input');
      if (searchInput) {
        searchInput.focus();
      } else {
        var firstCb = menu.querySelector('input[type="checkbox"]');
        if (firstCb) firstCb.focus();
      }
    } else {
      menu.style.width = '';
    }
  });

  // Close on outside click.
  document.addEventListener('click', function () {
    if (menu.classList.contains('open')) {
      menu.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });

  // Prevent clicks inside menu from closing it.
  menu.addEventListener('click', function (e) {
    e.stopPropagation();
  });

  // Close either dropdown on Escape, returning focus to its button.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var closed = false;
    if (menu.classList.contains('open')) {
      menu.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
      btn.focus();
      closed = true;
    }
    var vsMenu = document.getElementById('view-switcher-menu');
    var vsBtn = document.getElementById('view-switcher-btn');
    if (vsMenu && vsMenu.classList.contains('open')) {
      vsMenu.classList.remove('open');
      if (vsBtn) {
        vsBtn.setAttribute('aria-expanded', 'false');
        vsBtn.focus();
      }
      closed = true;
    }
    if (closed) e.preventDefault();
  });

  // Apply persisted filter state on load.
  _updateTagFilterButton();
  _applyTagFilter();
}

// ── Menu building ─────────────────────────────────────────────────────────

/**
 * Build the tag-filter menu contents.  Called every time the menu opens
 * because user tags are dynamic.
 *
 * @param {Element} menu The .tag-filter-menu container.
 */
function _buildTagFilterMenu(menu) {
  menu.innerHTML = '';
  menu.setAttribute('role', 'group');
  menu.setAttribute('aria-label', 'Filter by tag');

  var names = allTagNames();
  var uncheckedSet = {};
  for (var u = 0; u < _tagFilterState.unchecked.length; u++) {
    uncheckedSet[_tagFilterState.unchecked[u].toLowerCase()] = true;
  }

  // ── Actions row ──
  var actions = document.createElement('div');
  actions.className = 'tag-filter-actions';

  var selectAll = document.createElement('button');
  selectAll.className = 'tag-filter-action';
  selectAll.textContent = 'Select all';
  selectAll.addEventListener('click', function (e) {
    e.preventDefault();
    _onSelectAll(menu);
  });

  var sep = document.createElement('span');
  sep.className = 'tag-filter-separator';
  sep.textContent = '\u00b7'; // ·

  var clearAll = document.createElement('button');
  clearAll.className = 'tag-filter-action';
  clearAll.textContent = 'Clear';
  clearAll.addEventListener('click', function (e) {
    e.preventDefault();
    _onClearAll(menu);
  });

  actions.appendChild(selectAll);
  actions.appendChild(sep);
  actions.appendChild(clearAll);
  menu.appendChild(actions);

  // ── Search input (only for 8+ tags) ──
  if (names.length >= 8) {
    var searchWrap = document.createElement('div');
    searchWrap.className = 'tag-filter-search';

    var searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'tag-filter-search-input';
    searchInput.placeholder = 'Search tags\u2026';
    searchInput.setAttribute('aria-label', 'Search tags');
    searchInput.addEventListener('input', function () {
      _filterMenuItems(menu, searchInput.value.toLowerCase());
    });
    // Prevent menu-level stopPropagation from eating keystrokes.
    searchInput.addEventListener('keydown', function (e) {
      e.stopPropagation();
    });

    searchWrap.appendChild(searchInput);
    menu.appendChild(searchWrap);
  }

  // ── Count quotes per tag ──
  var tagCounts = _countQuotesPerTag(names);

  // ── (No tags) checkbox ──
  var noTagsChecked = !_tagFilterState.noTagsUnchecked && !_tagFilterState.clearAll;
  var noTagsCount = tagCounts[_NO_TAGS_KEY] || 0;
  var noTagsLabel = _createCheckboxItem(_NO_TAGS_KEY, '(No tags)', noTagsChecked, true, noTagsCount);
  menu.appendChild(noTagsLabel);

  // ── Divider ──
  if (names.length > 0) {
    var divider = document.createElement('div');
    divider.className = 'tag-filter-divider';
    menu.appendChild(divider);
  }

  // ── User tags ──
  for (var i = 0; i < names.length; i++) {
    var name = names[i];
    var checked = _tagFilterState.clearAll ? false : !uncheckedSet[name.toLowerCase()];
    var count = tagCounts[name.toLowerCase()] || 0;
    var item = _createCheckboxItem(name, name, checked, false, count);
    menu.appendChild(item);
  }
}

/**
 * Filter visible tag items in the dropdown by a search query.
 * Hides items that don't match; shows all if query is empty.
 * "(No tags)" and the divider are hidden when a query is active.
 *
 * @param {Element} menu  The .tag-filter-menu container.
 * @param {string}  query Lowercase search query.
 */
function _filterMenuItems(menu, query) {
  var items = menu.querySelectorAll('.tag-filter-item');
  var divider = menu.querySelector('.tag-filter-divider');

  for (var i = 0; i < items.length; i++) {
    var tag = items[i].querySelector('input').getAttribute('data-tag');
    if (tag === _NO_TAGS_KEY) {
      // Hide "(No tags)" while searching.
      items[i].style.display = query ? 'none' : '';
    } else {
      var matches = !query || tag.toLowerCase().indexOf(query) !== -1;
      items[i].style.display = matches ? '' : 'none';
    }
  }

  // Hide divider while searching.
  if (divider) divider.style.display = query ? 'none' : '';
}

/**
 * Count how many quotes have each user tag (and how many have no tags).
 * Counts all quotes regardless of current filter/view state.
 *
 * @param {string[]} names All user tag names.
 * @returns {Object} Map of lowercase tag name → count, plus _NO_TAGS_KEY.
 */
function _countQuotesPerTag(names) {
  var counts = {};
  counts[_NO_TAGS_KEY] = 0;
  for (var n = 0; n < names.length; n++) {
    counts[names[n].toLowerCase()] = 0;
  }

  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    var badges = bqs[i].querySelectorAll('.badges [data-badge-type="user"]');
    var hasTags = false;
    for (var j = 0; j < badges.length; j++) {
      var tagName = badges[j].getAttribute('data-tag-name');
      if (tagName) {
        var key = tagName.toLowerCase();
        if (counts[key] !== undefined) counts[key]++;
        hasTags = true;
      }
    }
    if (!hasTags) counts[_NO_TAGS_KEY]++;
  }

  return counts;
}

/**
 * Create a checkbox label element for the tag-filter menu.
 *
 * @param {string}  tag     The tag key (tag name or _NO_TAGS_KEY).
 * @param {string}  label   Display text.
 * @param {boolean} checked Whether the checkbox is checked.
 * @param {boolean} muted   Whether to use muted/italic styling.
 * @param {number}  count   Number of quotes with this tag.
 * @returns {Element}
 */
function _createCheckboxItem(tag, label, checked, muted, count) {
  var el = document.createElement('label');
  el.className = 'tag-filter-item';

  var cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.checked = checked;
  cb.setAttribute('data-tag', tag);

  cb.addEventListener('change', function () {
    _onTagFilterChange(tag, cb.checked);
  });

  var span = document.createElement('span');
  span.className = muted ? 'tag-filter-item-muted' : 'tag-filter-item-name';
  span.textContent = label;
  if (!muted && label.length > 31) span.title = label;

  el.appendChild(cb);
  el.appendChild(span);

  // Append quote count.
  if (count !== undefined) {
    var countSpan = document.createElement('span');
    countSpan.className = 'tag-filter-count';
    countSpan.textContent = count;
    el.appendChild(countSpan);
  }

  return el;
}

// ── Filter state changes ──────────────────────────────────────────────────

/**
 * Handle a single checkbox toggle.
 *
 * @param {string}  tag     Tag name or _NO_TAGS_KEY.
 * @param {boolean} checked New checked state.
 */
function _onTagFilterChange(tag, checked) {
  if (tag === _NO_TAGS_KEY) {
    _tagFilterState.noTagsUnchecked = !checked;
    // If "(No tags)" is being checked while clearAll is on, materialise the
    // clearAll into explicit unchecked entries so we can track mixed state.
    if (checked && _tagFilterState.clearAll) {
      _tagFilterState.clearAll = false;
      _tagFilterState.unchecked = allTagNames().slice();
    }
  } else {
    var lower = tag.toLowerCase();
    if (checked) {
      // If clearAll is on, materialise: put every OTHER tag into unchecked.
      if (_tagFilterState.clearAll) {
        var names = allTagNames();
        _tagFilterState.unchecked = [];
        for (var n = 0; n < names.length; n++) {
          if (names[n].toLowerCase() !== lower) {
            _tagFilterState.unchecked.push(names[n]);
          }
        }
        _tagFilterState.clearAll = false;
      } else {
        _tagFilterState.unchecked = _tagFilterState.unchecked.filter(function (t) {
          return t.toLowerCase() !== lower;
        });
      }
    } else {
      // Avoid duplicates.
      var exists = _tagFilterState.unchecked.some(function (t) {
        return t.toLowerCase() === lower;
      });
      if (!exists) _tagFilterState.unchecked.push(tag);
    }
  }
  _tagFilterStore.set(_tagFilterState);
  _updateTagFilterButton();
  _applyTagFilter();
}

/**
 * Check all checkboxes in the menu and clear the filter.
 *
 * @param {Element} menu The .tag-filter-menu container.
 */
function _onSelectAll(menu) {
  _tagFilterState.unchecked = [];
  _tagFilterState.noTagsUnchecked = false;
  _tagFilterState.clearAll = false;
  _tagFilterStore.set(_tagFilterState);

  var cbs = menu.querySelectorAll('input[type="checkbox"]');
  for (var i = 0; i < cbs.length; i++) cbs[i].checked = true;

  _updateTagFilterButton();
  _applyTagFilter();
}

/**
 * Uncheck all checkboxes in the menu and hide all quotes.
 *
 * @param {Element} menu The .tag-filter-menu container.
 */
function _onClearAll(menu) {
  _tagFilterState.unchecked = [];
  _tagFilterState.clearAll = true;
  _tagFilterState.noTagsUnchecked = true;
  _tagFilterStore.set(_tagFilterState);

  var cbs = menu.querySelectorAll('input[type="checkbox"]');
  for (var i = 0; i < cbs.length; i++) cbs[i].checked = false;

  _updateTagFilterButton();
  _applyTagFilter();
}

// ── Core filtering ────────────────────────────────────────────────────────

/**
 * Remove unchecked entries for tags that no longer exist.
 * Prevents deleted tags from accumulating in localStorage.
 */
function _pruneStaleUnchecked() {
  var names = allTagNames();
  var nameSet = {};
  for (var i = 0; i < names.length; i++) {
    nameSet[names[i].toLowerCase()] = true;
  }

  var pruned = [];
  for (var u = 0; u < _tagFilterState.unchecked.length; u++) {
    if (nameSet[_tagFilterState.unchecked[u].toLowerCase()]) {
      pruned.push(_tagFilterState.unchecked[u]);
    }
  }

  if (pruned.length !== _tagFilterState.unchecked.length) {
    _tagFilterState.unchecked = pruned;
    _tagFilterStore.set(_tagFilterState);
  }
}

/**
 * Apply the tag filter to all blockquotes.
 *
 * Quotes with no user tags are shown/hidden based on the "(No tags)" state.
 * Quotes with tags are shown if at least one tag is checked (not unchecked).
 * Also respects the current view mode (starred).
 */
function _applyTagFilter() {
  if (currentViewMode === 'participants') return;

  _pruneStaleUnchecked();

  var isClearAll = _tagFilterState.clearAll;
  var uncheckedSet = {};
  if (!isClearAll) {
    for (var u = 0; u < _tagFilterState.unchecked.length; u++) {
      uncheckedSet[_tagFilterState.unchecked[u].toLowerCase()] = true;
    }
  }
  var noTagsHidden = _tagFilterState.noTagsUnchecked || isClearAll;
  var isActive = _isTagFilterActive();

  // If no filter active, ensure all quotes visible (respecting view mode) and bail.
  if (!isActive) {
    _restoreQuotesForViewMode();
    _updateVisibleQuoteCount();
    return;
  }

  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    var bq = bqs[i];

    // Respect hidden quotes — never show them regardless of filter state.
    if (bq.classList.contains('bn-hidden')) {
      bq.style.display = 'none';
      continue;
    }

    // Respect starred view mode.
    if (currentViewMode === 'starred' && !bq.classList.contains('starred')) {
      bq.style.display = 'none';
      continue;
    }

    // Collect visible user tags on this quote.
    var userBadges = bq.querySelectorAll('.badges [data-badge-type="user"]');
    var quoteTags = [];
    for (var j = 0; j < userBadges.length; j++) {
      if (userBadges[j].style.display === 'none') continue;
      var name = userBadges[j].getAttribute('data-tag-name');
      if (name) quoteTags.push(name.toLowerCase());
    }

    var visible;
    if (quoteTags.length === 0) {
      // Quote has no user tags — governed by "(No tags)" checkbox.
      visible = !noTagsHidden;
    } else if (isClearAll) {
      // clearAll means every tag is unchecked.
      visible = false;
    } else {
      // Quote has tags — visible if at least one is not unchecked.
      visible = false;
      for (var k = 0; k < quoteTags.length; k++) {
        if (!uncheckedSet[quoteTags[k]]) {
          visible = true;
          break;
        }
      }
    }

    bq.style.display = visible ? '' : 'none';
  }

  if (typeof _hideEmptySections === 'function') _hideEmptySections();
  if (typeof _hideEmptySubsections === 'function') _hideEmptySubsections();
  _updateVisibleQuoteCount();
}

/**
 * Restore quote visibility based on view mode only (no tag filter).
 * Used when tag filter is inactive.
 */
function _restoreQuotesForViewMode() {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i].classList.contains('bn-hidden')) {
      bqs[i].style.display = 'none';
      continue;
    }
    if (currentViewMode === 'starred') {
      bqs[i].style.display = bqs[i].classList.contains('starred') ? '' : 'none';
    } else {
      bqs[i].style.display = '';
    }
  }

  // Restore sections.
  var sections = document.querySelectorAll('.bn-tab-panel section');
  var hrs = document.querySelectorAll('.bn-tab-panel hr');
  for (var i = 0; i < sections.length; i++) sections[i].style.display = '';
  for (var i = 0; i < hrs.length; i++) hrs[i].style.display = '';

  // Restore subsections.
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) {
    groups[i].style.display = '';
    var prev = groups[i].previousElementSibling;
    if (prev && prev.classList && prev.classList.contains('description')) {
      prev.style.display = '';
      prev = prev.previousElementSibling;
    }
    if (prev && prev.tagName === 'H3') prev.style.display = '';
  }
}

// ── Label and state helpers ───────────────────────────────────────────────

/**
 * Returns true if the tag filter is active (any tag unchecked or no-tags hidden).
 */
function _isTagFilterActive() {
  return _tagFilterState.clearAll || _tagFilterState.unchecked.length > 0 || _tagFilterState.noTagsUnchecked;
}

/**
 * Update the tag-filter button label and active state.
 *
 * "Tags" when no tags exist, "16 tags" when all checked,
 * "12 of 16 tags" when a subset is checked.
 *
 * Sets a stable min-width on the label using the widest possible text
 * ("X of Y tags") to prevent layout shift as the label changes.
 */
function _updateTagFilterButton() {
  var btn = document.getElementById('tag-filter-btn');
  if (!btn) return;

  var label = btn.querySelector('.tag-filter-label');
  if (!label) return;

  var names = allTagNames();
  var totalTags = names.length;

  if (totalTags === 0) {
    label.textContent = 'Tags';
    label.style.minWidth = '';
    return;
  }

  // Set stable min-width using the widest label to prevent layout shift.
  var suffix = totalTags !== 1 ? 's' : '';
  var widestText = totalTags + ' of ' + totalTags + ' tag' + suffix;
  label.textContent = widestText;
  var widestWidth = label.offsetWidth;
  label.style.minWidth = widestWidth + 'px';

  // Count how many tags are checked.
  var checkedCount;
  if (_tagFilterState.clearAll) {
    checkedCount = 0;
  } else {
    var uncheckedSet = {};
    for (var u = 0; u < _tagFilterState.unchecked.length; u++) {
      uncheckedSet[_tagFilterState.unchecked[u].toLowerCase()] = true;
    }
    checkedCount = 0;
    for (var i = 0; i < names.length; i++) {
      if (!uncheckedSet[names[i].toLowerCase()]) checkedCount++;
    }
  }

  if (checkedCount === totalTags && !_tagFilterState.noTagsUnchecked) {
    label.textContent = totalTags + ' tag' + suffix;
  } else {
    label.textContent = checkedCount + ' of ' + totalTags + ' tag' + suffix;
  }
}

/**
 * Count visible quotes and update the view-switcher button label.
 * Sets a stable min-width on the view-switcher label span to prevent
 * layout shift as the quote count changes.
 */
function _updateVisibleQuoteCount() {
  var vsLabel = document.querySelector('.view-switcher-label');

  if (!_isTagFilterActive()) {
    // Restore the normal view-mode label directly (avoids stale _savedViewLabel).
    if (vsLabel) {
      vsLabel.style.minWidth = '';
      var modeLabel = 'All quotes';
      if (currentViewMode === 'starred') modeLabel = 'Starred quotes';
      if (currentViewMode === 'participants') modeLabel = 'Participant data';
      vsLabel.textContent = modeLabel + ' ';
    }
    return;
  }

  // Set stable min-width using the default "All quotes " text.
  if (vsLabel && !vsLabel.style.minWidth) {
    var saved = vsLabel.textContent;
    vsLabel.textContent = 'All quotes ';
    vsLabel.style.minWidth = vsLabel.offsetWidth + 'px';
    vsLabel.textContent = saved;
  }

  var bqs = document.querySelectorAll('.quote-group blockquote');
  var count = 0;
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i].style.display !== 'none') count++;
  }

  var text = count === 0 ? '0 quotes '
    : count === 1 ? '1 quote '
    : count + ' quotes ';

  if (vsLabel) vsLabel.textContent = text;
}

/**
 * Called by view-switcher.js when the view mode changes.
 * Hides or shows the tag-filter button; re-applies filter.
 */
function _onTagFilterViewChange() {
  var container = document.querySelector('.tag-filter');
  if (!container) return;

  if (currentViewMode === 'participants') {
    container.style.display = 'none';
  } else {
    container.style.display = '';
    _applyTagFilter();
  }
}
