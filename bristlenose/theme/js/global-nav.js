/**
 * global-nav.js — Top-level tab bar for report navigation.
 *
 * Manages switching between tab panels (Project, Sessions, Quotes, Codebook,
 * Analysis, Settings, About) and the session drill-down sub-navigation.
 *
 * @module global-nav
 */

/* Module-level references for session drill-down (set by _initSessionDrillDown). */
var _sessGrid = null;
var _sessSubnav = null;
var _sessLabel = null;
var _sessPages = null;

/** Currently displayed session ID, or null if showing the grid. */
var _currentSessionId = null;

/** Valid tab names for hash-based navigation. */
var _validTabs = ['project', 'sessions', 'quotes', 'codebook', 'analysis', 'settings', 'about'];

/**
 * Switch to a specific tab by name.
 * Exported for use by other modules (e.g. focus.js "?" key → About tab).
 *
 * @param {string} tabName     One of "project", "sessions", "quotes", "codebook",
 *                             "analysis", "settings", "about".
 * @param {boolean} [pushHash] If false, skip updating the URL hash (used by
 *                             popstate handler to avoid re-pushing state).
 */
function switchToTab(tabName, pushHash) {
  var tabs = document.querySelectorAll('.bn-tab');
  var panels = document.querySelectorAll('.bn-tab-panel');

  for (var i = 0; i < tabs.length; i++) {
    var isTarget = tabs[i].getAttribute('data-tab') === tabName;
    tabs[i].classList.toggle('active', isTarget);
    tabs[i].setAttribute('aria-selected', isTarget ? 'true' : 'false');
  }

  for (var j = 0; j < panels.length; j++) {
    panels[j].classList.toggle('active', panels[j].getAttribute('data-tab') === tabName);
  }

  // Update URL hash so reload returns to this tab.
  if (pushHash !== false) {
    history.pushState(null, '', '#' + tabName);
  }

  // Restore session drill-down state when returning to the Sessions tab
  if (tabName === 'sessions' && _currentSessionId && _sessGrid) {
    _showSession(_currentSessionId);
  }
}

/**
 * Initialise global tab navigation and session drill-down.
 */
function initGlobalNav() {
  // --- Tab switching ---
  var tabs = document.querySelectorAll('.bn-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].addEventListener('click', function () {
      var target = this.getAttribute('data-tab');
      switchToTab(target);
    });
  }

  // --- Restore tab from URL hash (survives reload) ---
  var hash = window.location.hash.replace('#', '');
  if (hash && _validTabs.indexOf(hash) !== -1) {
    switchToTab(hash, false);
  }

  // --- Back/forward button support ---
  window.addEventListener('popstate', function () {
    var h = window.location.hash.replace('#', '');
    if (h && _validTabs.indexOf(h) !== -1) {
      switchToTab(h, false);
    }
  });

  // --- Session drill-down ---
  _initSessionDrillDown();

  // --- Speaker links (navigate to Sessions tab + drill into session) ---
  _initSpeakerLinks();

  // --- Featured quotes reshuffle based on stars/hidden ---
  _reshuffleFeaturedQuotes();
}

/**
 * Set up click handlers on the session table rows to drill into transcript
 * views, and the back button to return to the grid.
 */
function _initSessionDrillDown() {
  var sessionsPanel = document.querySelector('.bn-tab-panel[data-tab="sessions"]');
  if (!sessionsPanel) return;

  _sessGrid = sessionsPanel.querySelector('.bn-session-grid');
  _sessSubnav = sessionsPanel.querySelector('.bn-session-subnav');
  var backBtn = sessionsPanel.querySelector('.bn-session-back');
  _sessLabel = sessionsPanel.querySelector('.bn-session-label');
  _sessPages = sessionsPanel.querySelectorAll('.bn-session-page');

  if (!_sessGrid || !_sessSubnav || !backBtn || !_sessPages.length) return;

  // Click handler on session table rows
  var rows = _sessGrid.querySelectorAll('tr[data-session]');
  for (var i = 0; i < rows.length; i++) {
    rows[i].style.cursor = 'pointer';
    rows[i].addEventListener('click', function (e) {
      // Don't intercept clicks on links within the row
      if (e.target.closest('a')) return;

      var sid = this.getAttribute('data-session');
      _showSession(sid);
    });
  }

  // Also intercept the session number link clicks
  var sessionLinks = _sessGrid.querySelectorAll('a[data-session-link]');
  for (var j = 0; j < sessionLinks.length; j++) {
    sessionLinks[j].addEventListener('click', function (e) {
      e.preventDefault();
      var sid = this.getAttribute('data-session-link');
      _showSession(sid);
    });
  }

  // Back button
  backBtn.addEventListener('click', function () {
    _showGrid();
  });
}

/**
 * Set up click handlers on speaker links (data-nav-session) in quote cards.
 * Navigates to Sessions tab → drills into the session → scrolls to anchor.
 */
function _initSpeakerLinks() {
  var links = document.querySelectorAll('a[data-nav-session]');
  for (var i = 0; i < links.length; i++) {
    links[i].addEventListener('click', function (e) {
      e.preventDefault();
      var sid = this.getAttribute('data-nav-session');
      var anchor = this.getAttribute('data-nav-anchor');
      if (!sid || !_sessGrid) return;

      switchToTab('sessions');
      _showSession(sid);

      // Scroll to the specific timecode anchor after layout settles
      if (anchor) {
        requestAnimationFrame(function () {
          var target = document.getElementById(anchor);
          if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        });
      }
    });
  }
}

/** Show a specific session transcript and hide the grid. */
function _showSession(sid) {
  if (!_sessGrid || !_sessSubnav || !_sessPages) return;

  _currentSessionId = sid;
  _sessGrid.style.display = 'none';
  _sessSubnav.style.display = '';

  for (var i = 0; i < _sessPages.length; i++) {
    if (_sessPages[i].getAttribute('data-session') === sid) {
      _sessPages[i].style.display = '';
      // Update the sub-nav label from the page's data attribute
      var label = _sessPages[i].getAttribute('data-session-label') || sid;
      if (_sessLabel) _sessLabel.textContent = label;
    } else {
      _sessPages[i].style.display = 'none';
    }
  }

  // Scroll to top of sessions panel
  _sessSubnav.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Re-render transcript annotations (span bars need layout measurements)
  if (typeof _renderAllAnnotations === 'function') {
    requestAnimationFrame(function () {
      _renderAllAnnotations();
    });
  }
}

/** Return to the session grid and hide all transcript pages. */
function _showGrid() {
  if (!_sessGrid || !_sessSubnav || !_sessPages) return;

  _currentSessionId = null;
  _sessGrid.style.display = '';
  _sessSubnav.style.display = 'none';

  for (var i = 0; i < _sessPages.length; i++) {
    _sessPages[i].style.display = 'none';
  }
}

/**
 * Reshuffle featured quotes on the Project tab based on localStorage state.
 *
 * Server-side rendering picks the top 3 quotes by score and renders up to 9
 * backup candidates (hidden via inline display:none).  This function:
 *   1. Boosts starred quotes (moves them to the front).
 *   2. Removes hidden quotes and promotes the next backup.
 *   3. Ensures only 3 cards are visible at a time.
 */
function _reshuffleFeaturedQuotes() {
  var row = document.querySelector('.bn-featured-row');
  if (!row) return;

  var cards = row.querySelectorAll('.bn-featured-quote');
  if (!cards.length) return;

  var starred = {};
  var hidden = {};
  try { starred = JSON.parse(localStorage.getItem('bristlenose-starred') || '{}'); } catch (_e) { /* empty */ }
  try { hidden = JSON.parse(localStorage.getItem('bristlenose-hidden') || '{}'); } catch (_e) { /* empty */ }

  // Build ordered list: starred first (by original rank), then unstarred.
  var starredCards = [];
  var normalCards = [];
  var hiddenCards = [];

  for (var i = 0; i < cards.length; i++) {
    var qid = cards[i].getAttribute('data-quote-id');
    if (hidden[qid]) {
      hiddenCards.push(cards[i]);
    } else if (starred[qid]) {
      starredCards.push(cards[i]);
    } else {
      normalCards.push(cards[i]);
    }
  }

  // Merge: starred first, then normal (hidden excluded).
  var ordered = starredCards.concat(normalCards);

  // Show top 3, hide the rest.
  var visibleCount = parseInt(row.getAttribute('data-visible-count'), 10) || 3;
  for (var j = 0; j < ordered.length; j++) {
    ordered[j].style.display = j < visibleCount ? '' : 'none';
  }
  for (var k = 0; k < hiddenCards.length; k++) {
    hiddenCards[k].style.display = 'none';
  }

  // If nothing is visible, hide the entire row.
  var anyVisible = false;
  for (var m = 0; m < ordered.length && m < visibleCount; m++) {
    anyVisible = true;
    break;
  }
  row.style.display = anyVisible ? '' : 'none';
}
