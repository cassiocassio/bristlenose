/**
 * histogram.js — Dynamic user-tags histogram chart.
 *
 * Renders a horizontal bar chart of user-tag frequencies alongside the
 * AI-generated sentiment charts.  Re-renders automatically whenever user
 * tags are added or removed (via the `persistUserTags` wrapper in tags.js).
 *
 * Architecture
 * ────────────
 * - The chart container (`#user-tags-chart`) is rendered empty by Python.
 * - `renderUserTagsChart()` reads the in-memory `userTags` map (owned by
 *   tags.js), counts occurrences, and builds DOM elements matching the
 *   same `.sentiment-bar-group` structure used by the AI charts.
 * - The chart auto-hides when there are no user tags and reappears when
 *   the first tag is added.
 * - Bar widths are normalised against the maximum of the user count and
 *   the AI chart's max count (read from `data-max-count` on the parent
 *   `.sentiment-row`) so the two charts are visually comparable.
 *
 * Dependencies: `userTags` from tags.js (shared global).
 *
 * @module histogram
 */

/* global userTags */

/**
 * (Re-)render the user-tags histogram.
 *
 * Safe to call at any time — it clears the container first.
 */
function renderUserTagsChart() {
  var container = document.getElementById('user-tags-chart');
  if (!container) return;

  // Count all user tags across quotes.
  var counts = {};
  Object.keys(userTags).forEach(function (qid) {
    (userTags[qid] || []).forEach(function (tag) {
      counts[tag] = (counts[tag] || 0) + 1;
    });
  });

  var entries = Object.keys(counts).map(function (t) {
    return { tag: t, count: counts[t] };
  });
  entries.sort(function (a, b) {
    return b.count - a.count;
  });

  container.innerHTML = '';

  if (!entries.length) {
    container.style.display = 'none';
    return;
  }
  container.style.display = '';

  // Title.
  var title = document.createElement('div');
  title.className = 'sentiment-chart-title';
  title.textContent = 'User tags';
  container.appendChild(title);

  // Normalise bar widths against both AI and user max counts.
  var row = container.closest('.sentiment-row');
  var aiMax = row ? parseInt(row.getAttribute('data-max-count'), 10) : 0;
  var maxCount = Math.max(entries[0].count, aiMax || 0);
  var maxBarPx = 180;

  entries.forEach(function (e) {
    var group = document.createElement('div');
    group.className = 'sentiment-bar-group';

    var label = document.createElement('span');
    label.className = 'sentiment-bar-label badge';
    label.textContent = e.tag;

    var bar = document.createElement('div');
    bar.className = 'sentiment-bar';
    var w = Math.max(4, Math.round((e.count / maxCount) * maxBarPx));
    bar.style.width = w + 'px';
    bar.style.background = '#9ca3af';

    var cnt = document.createElement('span');
    cnt.className = 'sentiment-bar-count';
    cnt.style.color = '#6b7280';
    cnt.textContent = e.count;

    group.appendChild(label);
    group.appendChild(bar);
    group.appendChild(cnt);
    container.appendChild(group);
  });
}
