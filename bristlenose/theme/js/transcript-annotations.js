/**
 * transcript-annotations.js — Right-margin annotations on transcript pages.
 *
 * Shows section/theme labels, tag badges, and vertical span bars alongside
 * quoted transcript segments.  Non-quoted segments are knocked back to 0.6
 * opacity by CSS, which conveys quote extent alongside the span bars.
 *
 * Design:
 *   - Section/theme labels appear only on first occurrence (not repeated)
 *   - Vertical span bars show the extent of each quote (greedy slot layout)
 *   - AI sentiment badges are deletable (click to remove, syncs to report)
 *   - User-applied tags have × delete button (syncs to report)
 *   - Codebook colour integration (reads bristlenose-codebook store)
 *   - Click any margin label to jump to the quote in the report
 *
 * Shares localStorage stores with the main report page:
 *   - bristlenose-tags (user tags per quote)
 *   - bristlenose-deleted-badges (deleted AI sentiment badges per quote)
 *   - bristlenose-codebook (tag colour assignments)
 *
 * Dependencies: storage.js (createStore), badge-utils.js (createUserTagBadge,
 *               animateBadgeRemoval, getTagColour)
 *
 * @module transcript-annotations
 */

/* global BRISTLENOSE_QUOTE_MAP, BRISTLENOSE_REPORT_URL, createStore,
          createUserTagBadge, animateBadgeRemoval, getTagColour */

/** @type {Object} Stores for cross-page sync. */
var _tagsStore;
var _deletedBadgesStore;
var _codebookStore;

/** @type {Object} In-memory copies of store data. */
var _userTags;
var _deletedBadges;

/**
 * Initialise margin annotations for all quoted transcript segments.
 */
function initTranscriptAnnotations() {
  if (typeof BRISTLENOSE_QUOTE_MAP === 'undefined') return;
  if (!Object.keys(BRISTLENOSE_QUOTE_MAP).length) return;

  _tagsStore = createStore('bristlenose-tags');
  _deletedBadgesStore = createStore('bristlenose-deleted-badges');
  _codebookStore = createStore('bristlenose-codebook');

  _userTags = _tagsStore.get({});
  _deletedBadges = _deletedBadgesStore.get({});

  _renderAllAnnotations();
  _installBadgeHandlers();

  // Listen for cross-window tag/codebook/deleted-badge changes
  window.addEventListener('storage', function (e) {
    if (
      e.key === 'bristlenose-tags' ||
      e.key === 'bristlenose-codebook' ||
      e.key === 'bristlenose-deleted-badges'
    ) {
      _userTags = _tagsStore.get({});
      _deletedBadges = _deletedBadgesStore.get({});
      _renderAllAnnotations();
    }
  });
}

/**
 * Install click handlers for badge deletion (event delegation).
 *
 * Runs once — handlers survive re-renders because they're on `document`.
 */
function _installBadgeHandlers() {
  // AI badge: click anywhere on badge to delete
  document.addEventListener('click', function (e) {
    var badge = e.target.closest('.segment-margin [data-badge-type="ai"]');
    if (!badge) return;
    e.preventDefault();

    var ann = badge.closest('.margin-annotation');
    var qid = ann ? ann.getAttribute('data-quote-id') : null;
    if (!qid) return;

    var badgeLabel = badge.textContent.trim();

    // Animate and remove from DOM.
    animateBadgeRemoval(badge);

    // Persist.
    if (!_deletedBadges[qid]) _deletedBadges[qid] = [];
    if (_deletedBadges[qid].indexOf(badgeLabel) === -1) {
      _deletedBadges[qid].push(badgeLabel);
    }
    _deletedBadgesStore.set(_deletedBadges);
  });

  // User tag: click × button to delete
  document.addEventListener('click', function (e) {
    var del = e.target.closest('.segment-margin .badge-delete');
    if (!del) return;
    e.preventDefault();
    e.stopPropagation();

    var tagEl = del.closest('.badge-user');
    if (!tagEl) return;
    var ann = tagEl.closest('.margin-annotation');
    var qid = ann ? ann.getAttribute('data-quote-id') : null;
    if (!qid) return;

    var tagName = tagEl.getAttribute('data-tag-name');

    // Animate and remove from DOM.
    animateBadgeRemoval(tagEl);

    // Persist.
    if (_userTags[qid]) {
      _userTags[qid] = _userTags[qid].filter(function (t) {
        return t !== tagName;
      });
      if (_userTags[qid].length === 0) delete _userTags[qid];
      _tagsStore.set(_userTags);
    }
  });
}

// ── Rendering ─────────────────────────────────────────────────────────────

/**
 * Render all annotations: span bars + margin labels.
 *
 * Two-pass approach:
 *   1. Build a map of quote-id → [segments] to know each quote's extent
 *   2. Render span bars and first-occurrence labels
 */
function _renderAllAnnotations() {
  // Clean up previous render
  var oldMargins = document.querySelectorAll('.segment-margin');
  for (var m = 0; m < oldMargins.length; m++) oldMargins[m].remove();
  var oldBars = document.querySelectorAll('.span-bar');
  for (var b = 0; b < oldBars.length; b++) oldBars[b].remove();

  var segments = document.querySelectorAll('.segment-quoted[data-quote-ids]');
  if (!segments.length) return;

  var codebook = _codebookStore.get({ groups: [], tags: {} });

  // Pass 1: Build quote-id → ordered list of segments
  var quoteSegments = {}; // qid → [segment, segment, ...]
  for (var i = 0; i < segments.length; i++) {
    var seg = segments[i];
    var qids = (seg.getAttribute('data-quote-ids') || '').split(' ');
    for (var j = 0; j < qids.length; j++) {
      var qid = qids[j];
      if (!qid || !BRISTLENOSE_QUOTE_MAP[qid]) continue;
      if (!quoteSegments[qid]) quoteSegments[qid] = [];
      quoteSegments[qid].push(seg);
    }
  }

  // Track last-shown label+sentiment to suppress repetition (show on change).
  // Mutable context object passed by reference through the render loop.
  var ctx = { lastLabel: '', lastSentiment: '' };

  // Pass 2: For each segment, render margin annotations
  for (var i = 0; i < segments.length; i++) {
    _renderSegmentAnnotations(
      segments[i], quoteSegments, ctx, codebook
    );
  }

  // Pass 3: Render span bars (positioned relative to transcript-body).
  // Multiple transcript bodies may exist (inline transcripts in Sessions tab).
  // Only render span bars in visible ones — hidden elements return zero rects.
  var bodies = document.querySelectorAll('.transcript-body');
  for (var k = 0; k < bodies.length; k++) {
    if (bodies[k].offsetParent !== null) {
      _renderSpanBars(quoteSegments, bodies[k]);
    }
  }
}

/**
 * Render margin annotations for a single segment.
 *
 * Labels and sentiment badges are shown only when they change from the
 * previous annotation (topic-change dedup).  Span bars provide visual
 * continuity for consecutive quotes in the same section.
 *
 * @param {Element} segment        The .transcript-segment element.
 * @param {Object}  quoteSegments  Map of qid → [segments].
 * @param {Object}  ctx            Mutable context: { lastLabel, lastSentiment }.
 * @param {Object}  codebook       Codebook data from localStorage.
 */
function _renderSegmentAnnotations(segment, quoteSegments, ctx, codebook) {
  var quoteIds = (segment.getAttribute('data-quote-ids') || '').split(' ');
  if (!quoteIds.length || !quoteIds[0]) return;

  var margin = document.createElement('aside');
  margin.className = 'segment-margin';

  for (var i = 0; i < quoteIds.length; i++) {
    var qid = quoteIds[i];
    var mapping = BRISTLENOSE_QUOTE_MAP[qid];
    if (!mapping) continue;

    // Only show annotation on the FIRST segment for this quote
    var segs = quoteSegments[qid];
    if (segs && segs[0] !== segment) continue;

    var ann = document.createElement('div');
    ann.className = 'margin-annotation';
    ann.setAttribute('data-quote-id', qid);

    // Section/theme label — show only when the topic changes
    var labelKey = mapping.label ? (mapping.type + ':' + mapping.label) : '';
    var showLabel = labelKey && labelKey !== ctx.lastLabel;
    if (showLabel) {
      ctx.lastLabel = labelKey;
      var labelEl = document.createElement('a');
      labelEl.className = 'margin-label';
      var labelPrefix = mapping.type === 'section' ? 'Section' : 'Theme';
      labelEl.title = labelPrefix + ': ' + mapping.label;
      labelEl.textContent = mapping.label;
      labelEl.href = BRISTLENOSE_REPORT_URL + '#' + qid;
      ann.appendChild(labelEl);
    }

    // Tags row: sentiment + user tags
    var tagsRow = document.createElement('div');
    tagsRow.className = 'margin-tags';

    // AI sentiment badge — show only when label or sentiment changes
    var showSentiment = showLabel || mapping.sentiment !== ctx.lastSentiment;
    var deletedList = _deletedBadges[qid] || [];
    if (
      showSentiment &&
      mapping.sentiment &&
      deletedList.indexOf(mapping.sentiment) === -1
    ) {
      ctx.lastSentiment = mapping.sentiment;
      var sentBadge = document.createElement('span');
      sentBadge.className = 'badge badge-ai badge-' + mapping.sentiment;
      sentBadge.setAttribute('data-badge-type', 'ai');
      sentBadge.textContent = mapping.sentiment;
      sentBadge.style.cursor = 'pointer';
      sentBadge.title = 'Click to remove';
      tagsRow.appendChild(sentBadge);
    }

    // User-applied tags
    var qTags = _userTags[qid] || [];
    for (var t = 0; t < qTags.length; t++) {
      var colourVar = getTagColour(qTags[t], codebook);
      var tagBadge = createUserTagBadge(qTags[t], colourVar);
      tagsRow.appendChild(tagBadge);
    }

    if (tagsRow.children.length > 0) {
      ann.appendChild(tagsRow);
    }

    if (ann.children.length > 0) {
      margin.appendChild(ann);
    }
  }

  if (margin.children.length > 0) {
    segment.appendChild(margin);
  }
}

// ── Span bars ─────────────────────────────────────────────────────────────

/**
 * Render vertical span bars showing the extent of each quote.
 *
 * Each bar uses the `.span-bar` atom (styled via --bn-span-bar-* tokens).
 * JS only sets position and height — visual properties come from CSS.
 *
 * @param {Object}  quoteSegments  Map of qid → [segments].
 * @param {Element} body           The .transcript-body container.
 */
function _renderSpanBars(quoteSegments, body) {
  // Ensure the body is the positioning context
  var bodyStyle = window.getComputedStyle(body);
  if (bodyStyle.position === 'static') {
    body.style.position = 'relative';
  }

  // Read layout tokens from CSS custom properties
  var rootStyle = getComputedStyle(document.documentElement);
  var barGap = parseFloat(rootStyle.getPropertyValue('--bn-span-bar-gap')) || 6;
  var barInset = parseFloat(rootStyle.getPropertyValue('--bn-span-bar-offset')) || 8;

  var bodyRect = body.getBoundingClientRect();

  // Position span bars between transcript text and margin labels.
  // Find the first .segment-margin to measure where the margin column starts.
  var firstMargin = body.querySelector('.segment-margin');
  var marginLeft;
  if (firstMargin) {
    var marginRect = firstMargin.getBoundingClientRect();
    // marginLeft is the left edge of the margin column, relative to body
    marginLeft = marginRect.left - bodyRect.left;
  } else {
    // Fallback: estimate from body width minus padding-right
    marginLeft = bodyRect.width - parseFloat(getComputedStyle(body).paddingRight);
  }

  // Collect all quote spans, then assign horizontal slots to avoid overlap
  var spans = [];
  var qids = Object.keys(quoteSegments);
  for (var i = 0; i < qids.length; i++) {
    var qid = qids[i];
    var segs = quoteSegments[qid];
    if (!segs || !segs.length) continue;

    var firstSeg = segs[0];
    var lastSeg = segs[segs.length - 1];
    var firstRect = firstSeg.getBoundingClientRect();
    var lastRect = lastSeg.getBoundingClientRect();

    var top = firstRect.top - bodyRect.top;
    var bottom = lastRect.bottom - bodyRect.top;

    spans.push({ qid: qid, top: top, bottom: bottom });
  }

  // Sort by top position for consistent slot assignment
  spans.sort(function (a, b) { return a.top - b.top; });

  // Assign horizontal slots: simple greedy — each bar gets the leftmost
  // slot that doesn't overlap vertically with another bar in that slot.
  var slots = []; // slots[slotIndex] = [{ top, bottom }, ...]
  for (var i = 0; i < spans.length; i++) {
    var span = spans[i];
    var assigned = false;
    for (var s = 0; s < slots.length; s++) {
      var overlaps = false;
      for (var k = 0; k < slots[s].length; k++) {
        if (span.top < slots[s][k].bottom && span.bottom > slots[s][k].top) {
          overlaps = true;
          break;
        }
      }
      if (!overlaps) {
        slots[s].push({ top: span.top, bottom: span.bottom });
        span.slot = s;
        assigned = true;
        break;
      }
    }
    if (!assigned) {
      span.slot = slots.length;
      slots.push([{ top: span.top, bottom: span.bottom }]);
    }
  }

  // Render bars — width, colour, opacity, radius come from the .span-bar atom;
  // JS only sets position and height (layout-dependent values).
  for (var i = 0; i < spans.length; i++) {
    var span = spans[i];
    var bar = document.createElement('div');
    bar.className = 'span-bar';
    bar.title = BRISTLENOSE_QUOTE_MAP[span.qid]
      ? BRISTLENOSE_QUOTE_MAP[span.qid].label || ''
      : '';

    var height = span.bottom - span.top;
    // Minimum height so single-segment quotes still show a visible bar
    if (height < 8) height = 8;

    bar.style.position = 'absolute';
    bar.style.top = span.top + 'px';
    bar.style.height = height + 'px';
    // Place bars just left of the margin column; slot 0 closest to margin,
    // additional slots extend leftward toward the transcript text.
    bar.style.left = (marginLeft - barInset - span.slot * barGap) + 'px';

    body.appendChild(bar);
  }
}

