/**
 * view-switcher.js — Dropdown menu to switch between report views.
 *
 * Three views:
 * - "all"          — show all content sections (default)
 * - "favourites"   — show only favourited quotes
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
 * @param {string} view        One of "all", "favourites", "participants".
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
  if (view === 'favourites') label = 'Favourite quotes';
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
  var sections = document.querySelectorAll('article > section');
  var hrs = document.querySelectorAll('article > hr');

  if (view === 'all') {
    _showAll(sections, hrs);
    _showAllQuotes();
  } else if (view === 'favourites') {
    _showAll(sections, hrs);
    _showFavouritesOnly();
  } else if (view === 'participants') {
    _showParticipantsOnly(sections, hrs);
  }
}

/** Show all sections and horizontal rules. */
function _showAll(sections, hrs) {
  for (var i = 0; i < sections.length; i++) sections[i].style.display = '';
  for (var j = 0; j < hrs.length; j++) hrs[j].style.display = '';
}

/** Ensure all blockquotes are visible. */
function _showAllQuotes() {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) bqs[i].style.display = '';
}

/** Show all blockquotes but hide those that are not favourited. */
function _showFavouritesOnly() {
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    bqs[i].style.display = bqs[i].classList.contains('favourited') ? '' : 'none';
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
