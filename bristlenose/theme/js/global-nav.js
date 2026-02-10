/**
 * global-nav.js — Top-level tab bar for report navigation.
 *
 * Manages switching between tab panels (Project, Sessions, Quotes, Codebook,
 * Analysis, Settings, About) and the session drill-down sub-navigation.
 *
 * @module global-nav
 */

/**
 * Switch to a specific tab by name.
 * Exported for use by other modules (e.g. focus.js "?" key → About tab).
 *
 * @param {string} tabName  One of "project", "sessions", "quotes", "codebook",
 *                          "analysis", "settings", "about".
 */
function switchToTab(tabName) {
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

  // --- Session drill-down ---
  _initSessionDrillDown();
}

/**
 * Set up click handlers on the session table rows to drill into transcript
 * views, and the back button to return to the grid.
 */
function _initSessionDrillDown() {
  var sessionsPanel = document.querySelector('.bn-tab-panel[data-tab="sessions"]');
  if (!sessionsPanel) return;

  var grid = sessionsPanel.querySelector('.bn-session-grid');
  var subnav = sessionsPanel.querySelector('.bn-session-subnav');
  var backBtn = sessionsPanel.querySelector('.bn-session-back');
  var sessionLabel = sessionsPanel.querySelector('.bn-session-label');
  var pages = sessionsPanel.querySelectorAll('.bn-session-page');

  if (!grid || !subnav || !backBtn || pages.length === 0) return;

  // Click handler on session table rows
  var rows = grid.querySelectorAll('tr[data-session]');
  for (var i = 0; i < rows.length; i++) {
    rows[i].style.cursor = 'pointer';
    rows[i].addEventListener('click', function (e) {
      // Don't intercept clicks on links within the row
      if (e.target.closest('a')) return;

      var sid = this.getAttribute('data-session');
      _showSession(sid, grid, subnav, sessionLabel, pages);
    });
  }

  // Also intercept the session number link clicks
  var sessionLinks = grid.querySelectorAll('a[data-session-link]');
  for (var j = 0; j < sessionLinks.length; j++) {
    sessionLinks[j].addEventListener('click', function (e) {
      e.preventDefault();
      var sid = this.getAttribute('data-session-link');
      _showSession(sid, grid, subnav, sessionLabel, pages);
    });
  }

  // Back button
  backBtn.addEventListener('click', function () {
    _showGrid(grid, subnav, pages);
  });
}

/** Show a specific session transcript and hide the grid. */
function _showSession(sid, grid, subnav, sessionLabel, pages) {
  grid.style.display = 'none';
  subnav.style.display = '';

  for (var i = 0; i < pages.length; i++) {
    if (pages[i].getAttribute('data-session') === sid) {
      pages[i].style.display = '';
      // Update the sub-nav label from the page's data attribute
      var label = pages[i].getAttribute('data-session-label') || sid;
      if (sessionLabel) sessionLabel.textContent = label;
    } else {
      pages[i].style.display = 'none';
    }
  }

  // Scroll to top of sessions panel
  subnav.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/** Return to the session grid and hide all transcript pages. */
function _showGrid(grid, subnav, pages) {
  grid.style.display = '';
  subnav.style.display = 'none';

  for (var i = 0; i < pages.length; i++) {
    pages[i].style.display = 'none';
  }
}
