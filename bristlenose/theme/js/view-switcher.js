/**
 * view-switcher.js — Dropdown menu to switch between report views.
 *
 * Three views:
 * - "all"          — show all content sections (default)
 * - "starred"      — show only starred quotes
 * - "participants" — show only the participant table
 *
 * The active view is reflected in the `currentViewMode` global (defined in
 * csv-export.js) so the CSV export button adapts its behaviour.
 *
 * @module view-switcher
 */

/**
 * Initialise the view-switcher dropdown and wire up click handlers.
 */
function initViewSwitcher() {
  var btn = document.getElementById('view-switcher-btn');
  var menu = document.getElementById('view-switcher-menu');
  if (!btn || !menu) return;

  // Toggle menu open/closed.
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    // Close tag-filter menu if open.
    var tfMenu = document.getElementById('tag-filter-menu');
    if (tfMenu) {
      tfMenu.classList.remove('open');
      var tfBtn = document.getElementById('tag-filter-btn');
      if (tfBtn) tfBtn.setAttribute('aria-expanded', 'false');
    }
    var open = menu.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(open));
  });

  // Close on outside click.
  document.addEventListener('click', function () {
    menu.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  });

  // Handle menu item selection.
  var items = menu.querySelectorAll('li[data-view]');
  for (var i = 0; i < items.length; i++) {
    items[i].addEventListener('click', function (e) {
      e.stopPropagation();
      var view = this.getAttribute('data-view');
      _applyView(view, btn, menu, items);
    });
  }
}

/**
 * Apply a view mode: update the active menu item, button label, and
 * toggle visibility of report sections.
 *
 * @param {string} view        One of "all", "starred", "participants".
 * @param {Element} btn        The dropdown trigger button.
 * @param {Element} menu       The dropdown menu element.
 * @param {NodeList} items     All menu item elements.
 */
function _applyView(view, btn, menu, items) {
  currentViewMode = view;

  // Update active class.
  for (var i = 0; i < items.length; i++) {
    if (items[i].getAttribute('data-view') === view) {
      items[i].classList.add('active');
    } else {
      items[i].classList.remove('active');
    }
  }

  // Update button label (text only, keep the arrow).
  var label = 'All quotes';
  if (view === 'starred') label = 'Starred quotes';
  if (view === 'participants') label = 'Participant data';
  btn.firstChild.textContent = label + ' ';

  // Close menu.
  menu.classList.remove('open');
  btn.setAttribute('aria-expanded', 'false');

  // Toggle export buttons.
  var csvBtn = document.getElementById('export-csv');
  var namesBtn = document.getElementById('export-names');
  if (csvBtn) csvBtn.style.display = view === 'participants' ? 'none' : '';
  if (namesBtn) namesBtn.style.display = view === 'participants' ? '' : 'none';

  // Toggle section visibility.
  var sections = document.querySelectorAll('.bn-tab-panel section');
  var hrs = document.querySelectorAll('.bn-tab-panel hr');

  if (view === 'all') {
    _showAll(sections, hrs);
    _showAllQuotes();
  } else if (view === 'starred') {
    _showAll(sections, hrs);
    _showStarredOnly();
  } else if (view === 'participants') {
    _showParticipantsOnly(sections, hrs);
  }

  // Notify search module of view change.
  if (typeof _onViewModeChange === 'function') _onViewModeChange();

  // Notify tag-filter module of view change.
  if (typeof _onTagFilterViewChange === 'function') _onTagFilterViewChange();
}

/** Show all sections and horizontal rules. */
function _showAll(sections, hrs) {
  for (var i = 0; i < sections.length; i++) sections[i].style.display = '';
  for (var j = 0; j < hrs.length; j++) hrs[j].style.display = '';
}

/** Ensure all blockquotes are visible (except hidden quotes). */
function _showAllQuotes() {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i].classList.contains('bn-hidden')) continue;
    bqs[i].style.display = '';
  }
}

/** Show all blockquotes but hide those that are not starred (and hidden quotes). */
function _showStarredOnly() {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    if (bqs[i].classList.contains('bn-hidden')) {
      bqs[i].style.display = 'none';
      continue;
    }
    bqs[i].style.display = bqs[i].classList.contains('starred') ? '' : 'none';
  }
}

/** Hide everything except the participant table section. */
function _showParticipantsOnly(sections, hrs) {
  for (var i = 0; i < sections.length; i++) {
    var h2 = sections[i].querySelector('h2');
    var isParticipants = h2 && h2.textContent.trim() === 'Participants';
    sections[i].style.display = isParticipants ? '' : 'none';
  }
  for (var j = 0; j < hrs.length; j++) hrs[j].style.display = 'none';
}

/**
 * Update the view-switcher button label to show selection count.
 * Called by focus.js when selection changes.
 *
 * @param {number} selectionCount - Number of selected quotes (0 to restore normal label)
 */
function _updateViewLabel(selectionCount) {
  var btn = document.getElementById('view-switcher-btn');
  if (!btn) return;

  if (selectionCount > 0) {
    btn.firstChild.textContent = selectionCount + ' quote' + (selectionCount !== 1 ? 's' : '') + ' selected ';
  } else {
    // Let tag filter update the label if it's active; otherwise restore view mode.
    if (typeof _isTagFilterActive === 'function' && _isTagFilterActive()) {
      if (typeof _updateVisibleQuoteCount === 'function') _updateVisibleQuoteCount();
    } else {
      var label = 'All quotes';
      if (currentViewMode === 'starred') label = 'Starred quotes';
      if (currentViewMode === 'participants') label = 'Participant data';
      btn.firstChild.textContent = label + ' ';
    }
  }
}
