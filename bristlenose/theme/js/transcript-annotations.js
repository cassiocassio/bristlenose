/**
 * transcript-annotations.js — Right-margin annotations on transcript pages.
 *
 * Shows section/theme labels and tag badges alongside quoted transcript
 * segments.  Reads quote assignment data from BRISTLENOSE_QUOTE_MAP (baked
 * in by the Python renderer) and user tags from localStorage.
 *
 * Features:
 *   - Section/theme labels in the right margin, linking back to the report
 *   - AI sentiment badges (from pipeline data)
 *   - User-applied tag badges (from localStorage, synced cross-window)
 *   - Codebook colour integration (reads bristlenose-codebook store)
 *   - Click any margin annotation to jump to the quote in the report
 *
 * Dependencies: storage.js (createStore, escapeHtml)
 *
 * @module transcript-annotations
 */

/* global BRISTLENOSE_QUOTE_MAP, BRISTLENOSE_REPORT_URL, createStore, escapeHtml */

/**
 * Initialise margin annotations for all quoted transcript segments.
 */
function initTranscriptAnnotations() {
  if (typeof BRISTLENOSE_QUOTE_MAP === 'undefined') return;
  if (!Object.keys(BRISTLENOSE_QUOTE_MAP).length) return;

  var userTagsStore = createStore('bristlenose-tags');
  var codebookStore = createStore('bristlenose-codebook');

  // Render annotations for each quoted segment
  var segments = document.querySelectorAll('.segment-quoted[data-quote-ids]');
  for (var i = 0; i < segments.length; i++) {
    _renderMargin(segments[i], userTagsStore, codebookStore);
  }

  // Listen for cross-window tag/codebook changes
  window.addEventListener('storage', function (e) {
    if (e.key === 'bristlenose-tags' || e.key === 'bristlenose-codebook') {
      _refreshAllMargins(userTagsStore, codebookStore);
    }
  });
}

/**
 * Render the margin annotation for a single transcript segment.
 *
 * @param {Element} segment       The .transcript-segment element.
 * @param {Object}  tagsStore     The bristlenose-tags localStorage store.
 * @param {Object}  codebookStore The bristlenose-codebook localStorage store.
 */
function _renderMargin(segment, tagsStore, codebookStore) {
  var quoteIds = (segment.getAttribute('data-quote-ids') || '').split(' ');
  if (!quoteIds.length || !quoteIds[0]) return;

  // Remove existing margin if re-rendering
  var existing = segment.querySelector('.segment-margin');
  if (existing) existing.remove();

  var margin = document.createElement('aside');
  margin.className = 'segment-margin';

  var userTags = tagsStore.get({});
  var codebook = codebookStore.get({ groups: [], tags: {} });

  for (var i = 0; i < quoteIds.length; i++) {
    var qid = quoteIds[i];
    var mapping = BRISTLENOSE_QUOTE_MAP[qid];
    if (!mapping) continue;

    var ann = document.createElement('div');
    ann.className = 'margin-annotation';

    // Section/theme label
    if (mapping.label) {
      var labelPrefix = mapping.type === 'section' ? 'Section' : 'Theme';
      var labelEl = document.createElement('a');
      labelEl.className = 'margin-label';
      labelEl.title = labelPrefix + ': ' + mapping.label;
      labelEl.textContent = mapping.label;
      // Link back to the quote in the report
      labelEl.href = BRISTLENOSE_REPORT_URL + '#' + qid;
      ann.appendChild(labelEl);
    }

    // Tags row: sentiment + user tags
    var tagsRow = document.createElement('div');
    tagsRow.className = 'margin-tags';

    // AI sentiment badge
    if (mapping.sentiment) {
      var sentBadge = document.createElement('span');
      sentBadge.className = 'badge badge-ai badge-' + mapping.sentiment;
      sentBadge.textContent = mapping.sentiment;
      tagsRow.appendChild(sentBadge);
    }

    // User-applied tags
    var qTags = userTags[qid] || [];
    for (var t = 0; t < qTags.length; t++) {
      var tagBadge = document.createElement('span');
      tagBadge.className = 'badge badge-user';
      tagBadge.textContent = qTags[t];

      // Apply codebook colour
      var colour = _getTagColour(qTags[t], codebook);
      if (colour) {
        tagBadge.style.background = colour;
      }
      tagsRow.appendChild(tagBadge);
    }

    if (tagsRow.children.length > 0) {
      ann.appendChild(tagsRow);
    }

    margin.appendChild(ann);
  }

  if (margin.children.length > 0) {
    segment.appendChild(margin);
  }
}

/**
 * Look up the codebook colour for a tag name.
 *
 * @param {string} tagName  The tag to look up.
 * @param {Object} codebook The codebook data from localStorage.
 * @returns {string|null}   CSS colour value, or null if ungrouped.
 */
function _getTagColour(tagName, codebook) {
  var tagEntry = codebook.tags ? codebook.tags[tagName] : null;
  if (!tagEntry || tagEntry.groupIndex === undefined) return null;

  var group = codebook.groups ? codebook.groups[tagEntry.groupIndex] : null;
  if (!group) return null;

  // Return the CSS custom property reference for this colour slot
  var colourSet = group.colourSet || 'ux';
  var colourIndex = (tagEntry.colourIndex !== undefined) ? tagEntry.colourIndex + 1 : 1;
  return 'var(--bn-' + colourSet + '-' + colourIndex + '-bg)';
}

/**
 * Re-render all margin annotations (called on localStorage changes).
 *
 * @param {Object} tagsStore     The bristlenose-tags store.
 * @param {Object} codebookStore The bristlenose-codebook store.
 */
function _refreshAllMargins(tagsStore, codebookStore) {
  var segments = document.querySelectorAll('.segment-quoted[data-quote-ids]');
  for (var i = 0; i < segments.length; i++) {
    _renderMargin(segments[i], tagsStore, codebookStore);
  }
}
