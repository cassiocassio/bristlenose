/**
 * codebook.js — Codebook data model and colour assignment.
 *
 * The codebook is the researcher's tag taxonomy: named groups of tags, each
 * with a colour from the OKLCH v5 pentadic palette.  This module manages the
 * data model and provides colour lookups for other modules (tags.js,
 * histogram.js).
 *
 * Data model (localStorage `bristlenose-codebook`):
 * {
 *   "groups": [
 *     { "id": "g1", "name": "Friction", "colourSet": "emo", "order": 0 },
 *     ...
 *   ],
 *   "tags": {
 *     "confusion": { "group": "g1", "colourIndex": 0 },
 *     ...
 *   },
 *   "aiTagsVisible": true
 * }
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
 *
 * @module codebook
 */

/* global createStore */

var codebookStore = createStore('bristlenose-codebook');

/**
 * Available colour sets and the number of colour slots in each.
 * Order matters — used for auto-assignment when creating groups.
 */
var COLOUR_SETS = {
  ux:    { slots: 5, label: 'UX',          dotVar: '--bn-set-ux-dot' },
  emo:   { slots: 6, label: 'Emotion',     dotVar: '--bn-set-emo-dot' },
  task:  { slots: 5, label: 'Task',        dotVar: '--bn-set-task-dot' },
  trust: { slots: 5, label: 'Trust',       dotVar: '--bn-set-trust-dot' },
  opp:   { slots: 5, label: 'Opportunity', dotVar: '--bn-set-opp-dot' }
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
 * - Wires up the AI tag toggle button.
 * - Applies codebook colours to existing user tag badges.
 */
function initCodebook() {
  _applyAiTagVisibility();
  applyCodebookColours();

  // AI tag toggle button.
  var toggleBtn = document.getElementById('ai-tag-toggle');
  if (toggleBtn) {
    // Set initial visual state.
    toggleBtn.classList.toggle('active', isAiTagsVisible());

    toggleBtn.addEventListener('click', function (e) {
      e.preventDefault();
      var visible = toggleAiTags();
      toggleBtn.classList.toggle('active', visible);
    });
  }
}

// ── Internal helpers ──────────────────────────────────────────────────────

function _findGroup(groupId) {
  for (var i = 0; i < codebook.groups.length; i++) {
    if (codebook.groups[i].id === groupId) return codebook.groups[i];
  }
  return null;
}
