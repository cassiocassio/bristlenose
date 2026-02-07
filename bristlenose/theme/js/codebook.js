/**
 * codebook.js — Codebook data model, colour assignment, and panel UI.
 *
 * The codebook is the researcher's tag taxonomy: named groups of tags, each
 * with a colour from the OKLCH v5 pentadic palette.  This module manages the
 * data model, provides colour lookups for other modules (tags.js,
 * histogram.js), and renders the interactive codebook panel on codebook.html.
 *
 * Data model (localStorage `bristlenose-codebook`):
 * {
 *   "groups": [
 *     { "id": "g1", "name": "Friction", "subtitle": "Pain points",
 *       "colourSet": "emo", "order": 0 },
 *     ...
 *   ],
 *   "tags": {
 *     "confusion": { "group": "g1", "colourIndex": 0 },
 *     ...
 *   },
 *   "aiTagsVisible": true
 * }
 *
 * User tags (localStorage `bristlenose-tags`, written by tags.js):
 * { "quoteId": ["tag1", "tag2"], ... }
 *
 * Colour sets map to CSS custom properties defined in tokens.css:
 *   "ux"    → --bn-ux-{1..5}-bg       (blue, H=225-275)
 *   "emo"   → --bn-emo-{1..6}-bg      (red-pink, H=340-40)
 *   "task"  → --bn-task-{1..5}-bg     (green-teal, H=130-180)
 *   "trust" → --bn-trust-{1..5}-bg    (purple, H=275-325)
 *   "opp"   → --bn-opp-{1..5}-bg      (amber, H=50-100)
 *
 * Tags without a group assignment use --bn-custom-bg (neutral grey).
 *
 * Dependencies: createStore from storage.js.
 * On the codebook page, also uses createModal from modal.js (if available).
 *
 * @module codebook
 */

/* global createStore, escapeHtml, createModal, showConfirmModal, closeTopmostModal */

var codebookStore = createStore('bristlenose-codebook');

/**
 * Available colour sets and the number of colour slots in each.
 * Order matters — used for auto-assignment when creating groups.
 */
var COLOUR_SETS = {
  ux:    { slots: 5, label: 'UX',          dotVar: '--bn-set-ux-dot',
           bgVar: '--bn-ux-',    groupBg: '--bn-group-ux',    barVar: '--bn-bar-ux' },
  emo:   { slots: 6, label: 'Emotion',     dotVar: '--bn-set-emo-dot',
           bgVar: '--bn-emo-',   groupBg: '--bn-group-emo',   barVar: '--bn-bar-emo' },
  task:  { slots: 5, label: 'Task',        dotVar: '--bn-set-task-dot',
           bgVar: '--bn-task-',  groupBg: '--bn-group-task',  barVar: '--bn-bar-task' },
  trust: { slots: 5, label: 'Trust',       dotVar: '--bn-set-trust-dot',
           bgVar: '--bn-trust-', groupBg: '--bn-group-trust', barVar: '--bn-bar-trust' },
  opp:   { slots: 5, label: 'Opportunity', dotVar: '--bn-set-opp-dot',
           bgVar: '--bn-opp-',   groupBg: '--bn-group-opp',   barVar: '--bn-bar-opp' }
};

var COLOUR_SET_ORDER = ['ux', 'emo', 'task', 'trust', 'opp'];

/** The in-memory codebook state. */
var codebook = codebookStore.get({ groups: [], tags: {}, aiTagsVisible: true });

// Ensure all expected fields exist (backward compat with partial saves).
if (!codebook.groups) codebook.groups = [];
if (!codebook.tags) codebook.tags = {};
if (codebook.aiTagsVisible === undefined) codebook.aiTagsVisible = true;

/**
 * Persist the current codebook state to localStorage.
 */
function persistCodebook() {
  codebookStore.set(codebook);
}

/**
 * Get the CSS variable name for a tag's background colour.
 *
 * @param {string} tagName The tag name (case-sensitive as stored).
 * @returns {string} A CSS var() reference, e.g. "var(--bn-ux-2-bg)" or
 *                   "var(--bn-custom-bg)" for ungrouped tags.
 */
function getTagColourVar(tagName) {
  var entry = codebook.tags[tagName];
  if (!entry || !entry.group) return 'var(--bn-custom-bg)';

  var group = _findGroup(entry.group);
  if (!group || !group.colourSet) return 'var(--bn-custom-bg)';

  var setInfo = COLOUR_SETS[group.colourSet];
  if (!setInfo) return 'var(--bn-custom-bg)';

  // colourIndex within the set (0-based), clamped to available slots.
  var idx = (entry.colourIndex || 0) % setInfo.slots;
  return 'var(--bn-' + group.colourSet + '-' + (idx + 1) + '-bg)';
}

/**
 * Get the CSS variable name for a group's dot indicator colour.
 *
 * @param {string} groupId The group ID.
 * @returns {string|null} A CSS var() reference, or null if not found.
 */
function getGroupDotVar(groupId) {
  var group = _findGroup(groupId);
  if (!group || !group.colourSet) return null;
  var setInfo = COLOUR_SETS[group.colourSet];
  return setInfo ? 'var(' + setInfo.dotVar + ')' : null;
}

/**
 * Assign a tag to a group, picking the next available colour index.
 *
 * @param {string} tagName  The tag name.
 * @param {string} groupId  The group ID.
 */
function assignTagToGroup(tagName, groupId) {
  var group = _findGroup(groupId);
  if (!group) return;

  // Find the next unused colour index in this group.
  var usedIndices = {};
  Object.keys(codebook.tags).forEach(function (t) {
    var e = codebook.tags[t];
    if (e.group === groupId) usedIndices[e.colourIndex || 0] = true;
  });

  var setInfo = COLOUR_SETS[group.colourSet];
  var maxSlots = setInfo ? setInfo.slots : 5;
  var nextIdx = 0;
  while (usedIndices[nextIdx] && nextIdx < maxSlots) nextIdx++;
  if (nextIdx >= maxSlots) nextIdx = nextIdx % maxSlots; // wrap

  codebook.tags[tagName] = { group: groupId, colourIndex: nextIdx };
  persistCodebook();
}

/**
 * Remove a tag's group assignment (make it ungrouped).
 *
 * @param {string} tagName The tag name.
 */
function unassignTag(tagName) {
  delete codebook.tags[tagName];
  persistCodebook();
}

/**
 * Create a new codebook group.
 *
 * @param {string} name       The group display name.
 * @param {string} [colourSet] The colour set ID. Auto-assigned if omitted.
 * @returns {object} The created group object.
 */
function createCodebookGroup(name, colourSet) {
  var id = 'g' + (Date.now() % 100000);

  if (!colourSet) {
    // Auto-assign: pick the first colour set not already used by a group.
    var usedSets = {};
    codebook.groups.forEach(function (g) { usedSets[g.colourSet] = true; });
    for (var i = 0; i < COLOUR_SET_ORDER.length; i++) {
      if (!usedSets[COLOUR_SET_ORDER[i]]) {
        colourSet = COLOUR_SET_ORDER[i];
        break;
      }
    }
    // All sets taken — double up on the first.
    if (!colourSet) colourSet = COLOUR_SET_ORDER[0];
  }

  var group = {
    id: id,
    name: name,
    colourSet: colourSet,
    subtitle: '',
    order: codebook.groups.length
  };
  codebook.groups.push(group);
  persistCodebook();
  return group;
}

/**
 * Delete a codebook group.  Tags in the group become ungrouped.
 *
 * @param {string} groupId The group ID.
 */
function deleteCodebookGroup(groupId) {
  codebook.groups = codebook.groups.filter(function (g) { return g.id !== groupId; });
  Object.keys(codebook.tags).forEach(function (t) {
    if (codebook.tags[t].group === groupId) delete codebook.tags[t];
  });
  persistCodebook();
}

/**
 * Rename a codebook group.
 *
 * @param {string} groupId The group ID.
 * @param {string} newName The new display name.
 */
function renameCodebookGroup(groupId, newName) {
  var group = _findGroup(groupId);
  if (group) {
    group.name = newName;
    persistCodebook();
  }
}

/**
 * Update a group's subtitle (description).
 *
 * @param {string} groupId The group ID.
 * @param {string} subtitle The new subtitle text.
 */
function _setGroupSubtitle(groupId, subtitle) {
  var group = _findGroup(groupId);
  if (group) {
    group.subtitle = subtitle;
    persistCodebook();
  }
}

/**
 * Check whether AI tags are currently visible.
 *
 * @returns {boolean}
 */
function isAiTagsVisible() {
  return codebook.aiTagsVisible !== false;
}

/**
 * Toggle AI tag visibility.  Persists the state and updates the DOM.
 *
 * @returns {boolean} The new visibility state.
 */
function toggleAiTags() {
  codebook.aiTagsVisible = !isAiTagsVisible();
  persistCodebook();
  _applyAiTagVisibility();
  return codebook.aiTagsVisible;
}

/**
 * Apply the current AI tag visibility state to the DOM.
 */
function _applyAiTagVisibility() {
  document.body.classList.toggle('hide-ai-tags', !isAiTagsVisible());
}

/**
 * Apply codebook colours to all user tag badges currently in the DOM.
 * Called on init and after codebook changes.
 */
function applyCodebookColours() {
  var badges = document.querySelectorAll('.badge-user[data-tag-name]');
  for (var i = 0; i < badges.length; i++) {
    var name = badges[i].getAttribute('data-tag-name');
    if (name) {
      badges[i].style.background = getTagColourVar(name);
    }
  }
}

/**
 * Initialise the codebook module.
 *
 * - Restores AI tag visibility from persisted state.
 * - Wires up the codebook button (opens codebook.html in a new window).
 * - Applies codebook colours to existing user tag badges.
 * - On the codebook page: renders the interactive panel.
 */
function initCodebook() {
  _applyAiTagVisibility();
  applyCodebookColours();

  // Codebook button — opens codebook.html in a new window.
  var codebookBtn = document.getElementById('codebook-btn');
  if (codebookBtn) {
    codebookBtn.addEventListener('click', function () {
      var href = 'codebook.html';
      window.open(href, 'bristlenose-codebook',
        'width=960,height=700,menubar=no,toolbar=no,status=no');
    });
  }

  // If we're on the codebook page, render the interactive panel.
  var grid = document.getElementById('codebook-grid');
  if (grid) {
    _initCodebookPanel(grid);
  }

  // Cross-window sync: listen for storage changes from the other window.
  window.addEventListener('storage', function (e) {
    if (e.key === 'bristlenose-codebook' || e.key === 'bristlenose-tags') {
      // Reload codebook state from localStorage.
      var fresh = codebookStore.get({ groups: [], tags: {}, aiTagsVisible: true });
      codebook.groups = fresh.groups || [];
      codebook.tags = fresh.tags || {};
      codebook.aiTagsVisible = fresh.aiTagsVisible !== false;

      // Re-apply colours on the report page.
      applyCodebookColours();

      // Re-render panel on the codebook page.
      var g = document.getElementById('codebook-grid');
      if (g) _renderCodebookGrid(g);
    }
  });
}

// ── Internal helpers ──────────────────────────────────────────────────────

function _findGroup(groupId) {
  for (var i = 0; i < codebook.groups.length; i++) {
    if (codebook.groups[i].id === groupId) return codebook.groups[i];
  }
  return null;
}

// ══════════════════════════════════════════════════════════════════════════
//  CODEBOOK PANEL — interactive UI (only runs on codebook.html)
// ══════════════════════════════════════════════════════════════════════════

/** Read user tags from localStorage (written by tags.js in the report). */
function _getUserTags() {
  var store = createStore('bristlenose-tags');
  return store.get({});
}

/** Count quotes per tag name across all quotes. */
function _countQuotesPerTag() {
  var userTags = _getUserTags();
  var counts = {};
  Object.keys(userTags).forEach(function (quoteId) {
    var tags = userTags[quoteId];
    if (!Array.isArray(tags)) return;
    tags.forEach(function (t) {
      counts[t] = (counts[t] || 0) + 1;
    });
  });
  return counts;
}

/** Collect all unique tag names from user tags AND codebook assignments. */
function _allTagNames() {
  var userTags = _getUserTags();
  var seen = {};
  Object.keys(userTags).forEach(function (quoteId) {
    var tags = userTags[quoteId];
    if (!Array.isArray(tags)) return;
    tags.forEach(function (t) { seen[t] = true; });
  });
  // Include tags that exist in the codebook model but have no quotes yet
  // (e.g. created via the "+ add tag" input on the codebook page).
  Object.keys(codebook.tags).forEach(function (t) { seen[t] = true; });
  return Object.keys(seen).sort(function (a, b) {
    return a.toLowerCase().localeCompare(b.toLowerCase());
  });
}

/** Get the max quote count across all tags (for bar scaling). */
function _maxTagCount(counts) {
  var m = 0;
  Object.keys(counts).forEach(function (t) {
    if (counts[t] > m) m = counts[t];
  });
  return m;
}

/** Get CSS group background for a colour set. */
function _getGroupBg(colourSet) {
  if (!colourSet) return 'var(--bn-group-none)';
  var set = COLOUR_SETS[colourSet];
  return set ? 'var(' + set.groupBg + ')' : 'var(--bn-group-none)';
}

/** Get CSS bar colour for a colour set. */
function _getBarColour(colourSet) {
  if (!colourSet) return 'var(--bn-bar-none)';
  var set = COLOUR_SETS[colourSet];
  return set ? 'var(' + set.barVar + ')' : 'var(--bn-bar-none)';
}

/** Get tag badge bg var from colour set and index. */
function _getTagBg(colourSet, index) {
  if (!colourSet) return 'var(--bn-custom-bg)';
  var set = COLOUR_SETS[colourSet];
  if (!set) return 'var(--bn-custom-bg)';
  return 'var(' + set.bgVar + ((index % set.slots) + 1) + '-bg)';
}

// ── Drag state ────────────────────────────────────────────────────────────

var _dragTag = null;
var _dragGhost = null;

// ── Panel init ────────────────────────────────────────────────────────────

var _codebookHelpModal = null;

function _toggleCodebookHelp() {
  if (!_codebookHelpModal && typeof createModal === 'function') {
    _codebookHelpModal = createModal({
      className: 'help-overlay',
      modalClassName: 'help-modal',
      content: [
        '<h2>Keyboard Shortcuts</h2>',
        '<div class="help-columns">',
        '  <div class="help-section">',
        '    <h3>Codebook</h3>',
        '    <dl>',
        '      <dt><kbd>?</kbd></dt><dd>This help</dd>',
        '      <dt><kbd>Esc</kbd></dt><dd>Close dialog</dd>',
        '    </dl>',
        '  </div>',
        '  <div class="help-section">',
        '    <h3>Editing</h3>',
        '    <dl>',
        '      <dt><kbd>Enter</kbd></dt><dd>Confirm edit</dd>',
        '      <dt><kbd>Esc</kbd></dt><dd>Cancel edit</dd>',
        '    </dl>',
        '  </div>',
        '  <div class="help-section">',
        '    <h3>Drag &amp; drop</h3>',
        '    <dl>',
        '      <dt>Tag \u2192 group</dt><dd>Move to group</dd>',
        '      <dt>Tag \u2192 tag</dt><dd>Merge tags</dd>',
        '      <dt>Tag \u2192 +</dt><dd>New group</dd>',
        '    </dl>',
        '  </div>',
        '</div>',
        '<p class="bn-modal-footer">Press <kbd>?</kbd> to open, ',
        '<kbd>Esc</kbd> or click outside to close</p>'
      ].join('\n')
    });
  }
  if (_codebookHelpModal) {
    _codebookHelpModal.toggle();
  }
}

function _initCodebookPanel(grid) {
  _renderCodebookGrid(grid);

  document.addEventListener('keydown', function (e) {
    // Don't intercept while editing an input
    var tag = (document.activeElement || {}).tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') {
      if (e.key === 'Escape') {
        document.activeElement.blur();
        e.preventDefault();
      }
      return;
    }

    if (e.key === 'Escape') {
      if (typeof closeTopmostModal === 'function') {
        closeTopmostModal();
      }
      return;
    }

    if (e.key === '?') {
      e.preventDefault();
      _toggleCodebookHelp();
    }
  });
}

// ── Grid rendering ────────────────────────────────────────────────────────

function _renderCodebookGrid(grid) {
  grid.innerHTML = '';
  var counts = _countQuotesPerTag();
  var allTags = _allTagNames();
  var mc = _maxTagCount(counts);
  var maxBarW = 48;

  // Build a view model: for each group, list its tags (sorted by count desc).
  // Also build an "ungrouped" pseudo-group for tags not assigned to any group.
  var groupedTags = {};
  codebook.groups.forEach(function (g) { groupedTags[g.id] = []; });

  var ungroupedTags = [];
  allTags.forEach(function (tagName) {
    var entry = codebook.tags[tagName];
    var count = counts[tagName] || 0;
    if (entry && entry.group && _findGroup(entry.group)) {
      if (!groupedTags[entry.group]) groupedTags[entry.group] = [];
      groupedTags[entry.group].push({
        name: tagName, count: count, colourIndex: entry.colourIndex || 0
      });
    } else {
      ungroupedTags.push({ name: tagName, count: count, colourIndex: 0 });
    }
  });

  // Sort each group's tags by count (desc), then name (asc).
  var sortTags = function (a, b) {
    return b.count - a.count || a.name.toLowerCase().localeCompare(b.name.toLowerCase());
  };
  Object.keys(groupedTags).forEach(function (gid) { groupedTags[gid].sort(sortTags); });
  ungroupedTags.sort(sortTags);

  // Render ungrouped column first
  _renderGroupColumn(grid, {
    id: '_ungrouped', name: 'Ungrouped', subtitle: 'Tags not yet assigned to a group',
    colourSet: null
  }, ungroupedTags, mc, maxBarW, true);

  // Render each group
  codebook.groups.forEach(function (group) {
    var tags = groupedTags[group.id] || [];
    _renderGroupColumn(grid, group, tags, mc, maxBarW, false);
  });

  // New group placeholder
  var placeholder = document.createElement('div');
  placeholder.className = 'codebook-group new-group-placeholder';
  placeholder.innerHTML = '<span class="new-group-icon">+</span>' +
    '<span class="new-group-label">New group</span>';
  placeholder.addEventListener('click', function () { _createNewGroup(grid); });
  placeholder.addEventListener('dragover', function (e) {
    e.preventDefault();
    placeholder.style.borderColor = 'var(--bn-colour-accent)';
  });
  placeholder.addEventListener('dragleave', function () {
    placeholder.style.borderColor = '';
  });
  placeholder.addEventListener('drop', function (e) {
    e.preventDefault();
    placeholder.style.borderColor = '';
    _createNewGroupFromDrag(grid);
  });
  grid.appendChild(placeholder);
}

// ── Group column rendering ────────────────────────────────────────────────

function _renderGroupColumn(grid, group, tags, mc, maxBarW, isUngrouped) {
  var col = document.createElement('div');
  col.className = 'codebook-group';
  col.setAttribute('data-group-id', group.id);
  col.style.background = _getGroupBg(group.colourSet);

  // Header
  var header = document.createElement('div');
  header.className = 'group-header';

  var titleArea = document.createElement('div');
  titleArea.className = 'group-title-area';

  var title = document.createElement('div');
  title.className = 'group-title';
  var titleText = document.createElement('span');
  titleText.className = 'group-title-text';
  titleText.textContent = group.name;
  if (!isUngrouped) {
    titleText.addEventListener('click', function () {
      _editGroupTitle(group.id, grid);
    });
  }
  title.appendChild(titleText);
  titleArea.appendChild(title);

  // Subtitle
  var subtitleText = group.subtitle || '';
  var subtitle = document.createElement('div');
  subtitle.className = 'group-subtitle' + (subtitleText ? '' : ' placeholder');
  subtitle.textContent = subtitleText || 'Add description\u2026';
  if (!isUngrouped) {
    subtitle.addEventListener('click', function () {
      _editGroupSubtitle(group.id, grid);
    });
  }
  titleArea.appendChild(subtitle);

  header.appendChild(titleArea);

  // Close button (not for ungrouped)
  if (!isUngrouped) {
    var close = document.createElement('button');
    close.className = 'group-close';
    close.textContent = '\u00d7';
    close.title = 'Delete group';
    close.addEventListener('click', function () {
      _confirmDeleteGroup(group.id, group.name, tags.length, grid);
    });
    header.appendChild(close);
  }

  col.appendChild(header);

  // Tag list
  var tagList = document.createElement('div');
  tagList.className = 'tag-list';

  // Total row
  var totalQuotes = tags.reduce(function (s, t) { return s + t.count; }, 0);
  if (tags.length > 0) {
    var totalRow = document.createElement('div');
    totalRow.className = 'group-total-row';
    var totalLabel = document.createElement('span');
    totalLabel.className = 'group-total-label';
    totalLabel.textContent = tags.length + ' tag' + (tags.length !== 1 ? 's' : '');
    var totalCount = document.createElement('span');
    totalCount.className = 'group-total-count';
    totalCount.textContent = totalQuotes;
    totalCount.title = totalQuotes + ' quote' + (totalQuotes !== 1 ? 's' : '');
    totalRow.appendChild(totalLabel);
    totalRow.appendChild(totalCount);
    tagList.appendChild(totalRow);
  }

  tags.forEach(function (tag) {
    var row = _renderTagRow(tag, group, mc, maxBarW, grid);
    tagList.appendChild(row);
  });

  col.appendChild(tagList);

  // Add tag row
  var addRow = document.createElement('div');
  addRow.className = 'tag-add-row';
  var addBadge = document.createElement('span');
  addBadge.className = 'tag-add-badge';
  addBadge.textContent = '+';
  addRow.appendChild(addBadge);
  addRow.addEventListener('click', function () {
    _addTagInline(group.id, col, grid);
  });
  col.appendChild(addRow);

  // Group drop zone
  col.addEventListener('dragover', function (e) {
    if (!_dragTag) return;
    e.preventDefault();
    if (col.getAttribute('data-group-id') !== _dragTag.fromGroup) {
      col.classList.add('drag-over');
    }
  });
  col.addEventListener('dragleave', function (e) {
    if (!col.contains(e.relatedTarget)) col.classList.remove('drag-over');
  });
  col.addEventListener('drop', function (e) {
    e.preventDefault();
    col.classList.remove('drag-over');
    if (!_dragTag) return;
    var targetGroupId = col.getAttribute('data-group-id');
    if (_dragTag.fromGroup === targetGroupId) return;
    _moveTagToGroup(_dragTag.name, targetGroupId, grid);
  });

  grid.appendChild(col);
}

// ── Tag row rendering ─────────────────────────────────────────────────────

function _renderTagRow(tag, group, mc, maxBarW, grid) {
  var row = document.createElement('div');
  row.className = 'tag-row';
  row.setAttribute('draggable', 'true');
  row.setAttribute('data-tag', tag.name);
  row.setAttribute('data-group', group.id);

  // Badge
  var nameArea = document.createElement('div');
  nameArea.className = 'tag-name-area';

  var badge = document.createElement('span');
  badge.className = 'badge badge-user';
  badge.setAttribute('data-tag-name', tag.name);
  badge.textContent = tag.name;
  badge.style.background = _getTagBg(group.colourSet, tag.colourIndex);
  badge.title = tag.name + ' \u2014 ' + tag.count + ' quote' + (tag.count !== 1 ? 's' : '');

  // Delete × on badge
  var del = document.createElement('button');
  del.className = 'badge-delete';
  del.setAttribute('aria-label', 'Delete tag');
  del.textContent = '\u00d7';
  del.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    _confirmDeleteTag(tag.name, tag.count, grid);
  });
  badge.appendChild(del);

  nameArea.appendChild(badge);
  row.appendChild(nameArea);

  // Micro bar + count
  var barArea = document.createElement('div');
  barArea.className = 'tag-bar-area';

  var bar = document.createElement('div');
  bar.className = 'tag-micro-bar';
  var barW = mc > 0 ? Math.max(2, Math.round((tag.count / mc) * maxBarW)) : 2;
  bar.style.width = barW + 'px';
  bar.style.background = _getBarColour(group.colourSet);
  barArea.appendChild(bar);

  var count = document.createElement('span');
  count.className = 'tag-count';
  count.textContent = tag.count;
  barArea.appendChild(count);

  row.appendChild(barArea);

  // Drag handlers
  row.addEventListener('dragstart', function (e) {
    _dragTag = { name: tag.name, fromGroup: group.id };
    row.classList.add('dragging');

    _dragGhost = document.createElement('div');
    _dragGhost.className = 'drag-ghost';
    _dragGhost.textContent = tag.name;
    _dragGhost.style.background = _getTagBg(group.colourSet, tag.colourIndex);
    document.body.appendChild(_dragGhost);
    e.dataTransfer.setDragImage(_dragGhost, 0, 0);
    e.dataTransfer.effectAllowed = 'move';
  });

  row.addEventListener('dragend', function () {
    row.classList.remove('dragging');
    if (_dragGhost) { _dragGhost.remove(); _dragGhost = null; }
    _dragTag = null;
    document.querySelectorAll('.merge-target').forEach(function (el) {
      el.classList.remove('merge-target');
    });
    document.querySelectorAll('.drag-over').forEach(function (el) {
      el.classList.remove('drag-over');
    });
  });

  // Merge target: drag a tag onto another tag
  row.addEventListener('dragover', function (e) {
    if (!_dragTag) return;
    e.preventDefault();
    e.stopPropagation();
    if (row.getAttribute('data-tag') !== _dragTag.name) {
      row.classList.add('merge-target');
    }
  });
  row.addEventListener('dragleave', function () {
    row.classList.remove('merge-target');
  });
  row.addEventListener('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (!_dragTag || _dragTag.name === tag.name) return;
    document.querySelectorAll('.merge-target, .drag-over').forEach(function (el) {
      el.classList.remove('merge-target', 'drag-over');
    });
    _confirmMergeTags(_dragTag.name, _dragTag.fromGroup, tag.name, group.id, grid);
  });

  return row;
}

// ── Tag operations ────────────────────────────────────────────────────────

function _moveTagToGroup(tagName, targetGroupId, grid) {
  if (targetGroupId === '_ungrouped') {
    unassignTag(tagName);
  } else {
    assignTagToGroup(tagName, targetGroupId);
  }
  _renderCodebookGrid(grid);
}

function _confirmMergeTags(dragName, dragGroupId, targetName, targetGroupId, grid) {
  var dragBg = getTagColourVar(dragName);
  var targetBg = getTagColourVar(targetName);

  // Count quotes for each
  var counts = _countQuotesPerTag();
  var dragCount = counts[dragName] || 0;
  var targetCount = counts[targetName] || 0;
  var total = dragCount + targetCount;

  showConfirmModal({
    title: 'Merge tags',
    body:
      '<p>Rename all ' +
      '<span class="tag-preview badge badge-user" style="background:' + dragBg + '">' +
      escapeHtml(dragName) + '</span>' +
      ' into ' +
      '<span class="tag-preview badge badge-user" style="background:' + targetBg + '">' +
      escapeHtml(targetName) + '</span>?' +
      '</p><p>' + dragCount + ' quote' + (dragCount !== 1 ? 's' : '') +
      ' will be renamed. The merged tag will have ' + total + ' quotes.</p>',
    confirmLabel: 'Merge tags',
    confirmClass: 'bn-btn-primary',
    onConfirm: function () {
      _executeMerge(dragName, targetName);
      _renderCodebookGrid(grid);
    }
  });
}

function _executeMerge(fromTag, intoTag) {
  // Rename fromTag to intoTag in user tags localStorage
  var store = createStore('bristlenose-tags');
  var userTags = store.get({});
  var changed = false;
  Object.keys(userTags).forEach(function (quoteId) {
    var tags = userTags[quoteId];
    if (!Array.isArray(tags)) return;
    var idx = tags.indexOf(fromTag);
    if (idx === -1) return;
    tags.splice(idx, 1);
    if (tags.indexOf(intoTag) === -1) {
      tags.push(intoTag);
    }
    changed = true;
  });
  if (changed) store.set(userTags);

  // Remove fromTag from codebook
  delete codebook.tags[fromTag];
  persistCodebook();
}

function _confirmDeleteTag(tagName, count, grid) {
  showConfirmModal({
    title: 'Delete tag',
    body: '<p>Remove \u201c<strong>' + escapeHtml(tagName) + '</strong>\u201d from ' +
      count + ' quote' + (count !== 1 ? 's' : '') + '?</p>' +
      '<p>This cannot be undone.</p>',
    confirmLabel: 'Delete',
    onConfirm: function () {
      _executeDeleteTag(tagName);
      _renderCodebookGrid(grid);
    }
  });
}

function _executeDeleteTag(tagName) {
  // Remove from user tags
  var store = createStore('bristlenose-tags');
  var userTags = store.get({});
  var changed = false;
  Object.keys(userTags).forEach(function (quoteId) {
    var tags = userTags[quoteId];
    if (!Array.isArray(tags)) return;
    var idx = tags.indexOf(tagName);
    if (idx !== -1) {
      tags.splice(idx, 1);
      changed = true;
    }
  });
  if (changed) store.set(userTags);

  // Remove from codebook
  delete codebook.tags[tagName];
  persistCodebook();
}

function _confirmDeleteGroup(groupId, groupName, tagCount, grid) {
  showConfirmModal({
    title: 'Delete group',
    body: '<p>Delete \u201c<strong>' + escapeHtml(groupName) + '</strong>\u201d?</p>' +
      '<p>' + tagCount + ' tag' + (tagCount !== 1 ? 's' : '') +
      ' will be moved to Ungrouped. No quotes will be affected.</p>',
    confirmLabel: 'Delete group',
    onConfirm: function () {
      deleteCodebookGroup(groupId);
      _renderCodebookGrid(grid);
    }
  });
}

// ── Inline editing ────────────────────────────────────────────────────────

function _editGroupTitle(groupId, grid) {
  var group = _findGroup(groupId);
  if (!group) return;
  var col = document.querySelector('[data-group-id="' + groupId + '"]');
  if (!col) return;
  var titleText = col.querySelector('.group-title-text');
  if (!titleText) return;

  var input = document.createElement('input');
  input.className = 'group-title-input';
  input.value = group.name;
  titleText.style.display = 'none';
  titleText.parentNode.insertBefore(input, titleText.nextSibling);
  input.focus();
  input.select();

  var committed = false;
  function commit() {
    if (committed) return;
    committed = true;
    var v = input.value.trim();
    if (v && v !== group.name) {
      renameCodebookGroup(groupId, v);
    }
    input.remove();
    titleText.style.display = '';
    titleText.textContent = v || group.name;
  }
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); commit(); }
    if (e.key === 'Escape') { e.preventDefault(); input.value = group.name; commit(); }
  });
}

function _editGroupSubtitle(groupId, grid) {
  var group = _findGroup(groupId);
  if (!group) return;
  var col = document.querySelector('[data-group-id="' + groupId + '"]');
  if (!col) return;
  var sub = col.querySelector('.group-subtitle');
  if (!sub) return;

  var input = document.createElement('input');
  input.className = 'group-subtitle-input';
  input.value = group.subtitle || '';
  input.placeholder = 'Add description\u2026';
  sub.style.display = 'none';
  sub.parentNode.insertBefore(input, sub.nextSibling);
  input.focus();

  var committed = false;
  function commit() {
    if (committed) return;
    committed = true;
    var v = input.value.trim();
    _setGroupSubtitle(groupId, v);
    input.remove();
    sub.style.display = '';
    sub.textContent = v || 'Add description\u2026';
    sub.classList.toggle('placeholder', !v);
  }
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); commit(); }
    if (e.key === 'Escape') {
      e.preventDefault(); input.value = group.subtitle || ''; commit();
    }
  });
}

function _addTagInline(groupId, col, grid) {
  var addRow = col.querySelector('.tag-add-row');
  if (!addRow) return;

  addRow.style.display = 'none';
  var input = document.createElement('input');
  input.className = 'tag-add-input';
  input.placeholder = 'Tag name\u2026';
  input.maxLength = 40;
  addRow.parentNode.insertBefore(input, addRow);
  input.focus();

  var committed = false;
  function commit() {
    if (committed) return;
    committed = true;
    var name = input.value.trim();
    if (name) {
      // Create user tag entry if it doesn't exist (with 0 quotes)
      // and assign to group
      if (groupId !== '_ungrouped') {
        assignTagToGroup(name, groupId);
      }
    }
    input.remove();
    addRow.style.display = '';
    _renderCodebookGrid(grid);
  }
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); commit(); }
    if (e.key === 'Escape') { e.preventDefault(); input.value = ''; committed = true;
      input.remove(); addRow.style.display = ''; }
  });
}

// ── Group creation ────────────────────────────────────────────────────────

function _createNewGroup(grid) {
  var group = createCodebookGroup('New group');
  _renderCodebookGrid(grid);
  setTimeout(function () { _editGroupTitle(group.id, grid); }, 50);
}

function _createNewGroupFromDrag(grid) {
  if (!_dragTag) return;
  var group = createCodebookGroup('New group');
  _moveTagToGroup(_dragTag.name, group.id, grid);
  setTimeout(function () { _editGroupTitle(group.id, grid); }, 50);
}
