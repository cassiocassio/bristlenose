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
 * - Each tag label has a hover delete button that removes the tag from
 *   all quotes after confirmation.
 *
 * Dependencies: `userTags` from tags.js, `createModal` from modal.js,
 *               `persistUserTags` from tags.js.
 *
 * @module histogram
 */

/* global userTags, persistUserTags, createModal */

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
    if (e.tag.length > 18) label.title = e.tag;

    // Delete button (visible on hover).
    var del = document.createElement('button');
    del.type = 'button';
    del.className = 'histogram-bar-delete';
    del.setAttribute('aria-label', 'Delete tag');
    del.textContent = '\u00d7';
    del.setAttribute('data-tag', e.tag);
    del.setAttribute('data-count', e.count);
    label.appendChild(del);

    var bar = document.createElement('div');
    bar.className = 'sentiment-bar';
    var w = Math.max(4, Math.round((e.count / maxCount) * maxBarPx));
    bar.style.width = w + 'px';
    bar.style.background = 'var(--bn-colour-muted)';

    var cnt = document.createElement('span');
    cnt.className = 'sentiment-bar-count';
    cnt.style.color = 'var(--bn-colour-muted)';
    cnt.textContent = e.count;

    group.appendChild(label);
    group.appendChild(bar);
    group.appendChild(cnt);
    container.appendChild(group);
  });
}

/**
 * Delete a user tag from every quote and update the UI.
 *
 * @param {string} tagName The tag to remove.
 */
function _deleteTagFromAllQuotes(tagName) {
  // Remove from in-memory userTags map.
  Object.keys(userTags).forEach(function (qid) {
    if (!userTags[qid]) return;
    userTags[qid] = userTags[qid].filter(function (t) {
      return t !== tagName;
    });
    if (userTags[qid].length === 0) delete userTags[qid];
  });

  // Remove badge elements from the DOM.
  var badges = document.querySelectorAll('.badge-user[data-tag-name="' + tagName + '"]');
  for (var i = 0; i < badges.length; i++) {
    badges[i].classList.add('badge-removing');
    (function (el) {
      el.addEventListener('animationend', function () { el.remove(); }, { once: true });
    })(badges[i]);
  }

  // Persist — triggers histogram re-render and tag-filter update.
  persistUserTags(userTags);
}

// ── Delete-from-histogram click handler (event delegation) ──

document.addEventListener('click', function (e) {
  var del = e.target.closest('.histogram-bar-delete');
  if (!del) return;
  e.preventDefault();
  e.stopPropagation();

  var tagName = del.getAttribute('data-tag');
  var count = parseInt(del.getAttribute('data-count'), 10) || 0;
  var noun = count === 1 ? 'quote' : 'quotes';

  var modal = createModal({
    className: 'confirm-delete-overlay',
    modalClassName: 'confirm-delete-modal',
    content:
      '<h2>Delete tag</h2>' +
      '<p>Remove \u201c<strong>' + tagName.replace(/</g, '&lt;') + '</strong>\u201d from ' +
      count + ' ' + noun + '?</p>' +
      '<div class="bn-modal-actions">' +
      '<button type="button" class="bn-btn bn-btn-cancel">Cancel</button>' +
      '<button type="button" class="bn-btn bn-btn-danger">Delete all</button>' +
      '</div>'
  });

  // Wire buttons.
  var actions = modal.card.querySelector('.bn-modal-actions');
  actions.querySelector('.bn-btn-cancel').addEventListener('click', function () {
    modal.hide();
  });
  actions.querySelector('.bn-btn-danger').addEventListener('click', function () {
    _deleteTagFromAllQuotes(tagName);
    modal.hide();
  });

  modal.show();
});
