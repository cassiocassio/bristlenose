/**
 * csv-export.js — CSV export and clipboard copy for quotes.
 *
 * Provides "Export all" and "Export favourites" buttons that build a CSV
 * string from the DOM and copy it to the clipboard.  A toast notification
 * confirms the action.
 *
 * Architecture
 * ────────────
 * - `buildCsv(onlyFavs)` walks every `<blockquote>` inside `.quote-group`
 *   elements, extracts text (respecting inline edits), metadata from
 *   `data-*` attributes, and both AI and user tags.
 * - `copyToClipboard(text)` uses the Clipboard API with an
 *   `execCommand('copy')` fallback for older browsers.
 * - `showToast(msg)` renders a transient notification that auto-dismisses
 *   after 2 seconds.
 *
 * @module csv-export
 */

// ── Helpers ───────────────────────────────────────────────────────────────

/** Regex to strip leading/trailing smart-quotes or straight quotes. */
var CSV_QUOTE_RE = /^[\u201c\u201d"]+|[\u201c\u201d"]+$/g;

/**
 * Walk up from a blockquote to find the preceding `<h3>` section title.
 *
 * @param {Element} bq A blockquote element.
 * @returns {string} The section title, or empty string.
 */
function getSection(bq) {
  var el = bq.closest('.quote-group');
  while (el) {
    el = el.previousElementSibling;
    if (el && el.tagName === 'H3') return el.textContent.trim();
  }
  return '';
}

/**
 * Extract the visible quote text from a blockquote.
 *
 * Prefers the `.quote-text` span (which reflects inline edits); falls
 * back to cloning the node and stripping non-text children.
 *
 * @param {Element} bq A blockquote element.
 * @returns {string} Plain quote text without surrounding quotes.
 */
function getQuoteText(bq) {
  var span = bq.querySelector('.quote-text');
  if (span) {
    return span.textContent.replace(CSV_QUOTE_RE, '').trim();
  }
  // Fallback: clone and strip known non-text elements.
  var clone = bq.cloneNode(true);
  var rm = clone.querySelectorAll(
    '.context, .timecode, a.timecode, .speaker, .badges, .fav-star, .edit-pencil'
  );
  for (var i = 0; i < rm.length; i++) rm[i].remove();
  return clone.textContent.trim().replace(CSV_QUOTE_RE, '').trim();
}

/**
 * Escape a value for CSV (RFC 4180).
 *
 * @param {*} v The value to escape.
 * @returns {string} CSV-safe string.
 */
function csvEsc(v) {
  v = String(v);
  if (v.indexOf('"') !== -1 || v.indexOf(',') !== -1 || v.indexOf('\n') !== -1) {
    return '"' + v.replace(/"/g, '""') + '"';
  }
  return v;
}

/**
 * Collect visible tag labels of a given type from a blockquote.
 *
 * @param {Element} bq   A blockquote element.
 * @param {string}  type Either "ai" or "user".
 * @returns {string} Semicolon-separated tag names.
 */
function getQuoteTagsByType(bq, type) {
  var tags = [];
  var badges = bq.querySelectorAll('.badges [data-badge-type="' + type + '"]');
  for (var j = 0; j < badges.length; j++) {
    if (badges[j].style.display === 'none') continue;
    var name = (
      badges[j].getAttribute('data-tag-name') || badges[j].textContent
    ).trim();
    if (name) tags.push(name);
  }
  return tags.join('; ');
}

// ── CSV builder ───────────────────────────────────────────────────────────

/**
 * Build a CSV string from all (or only favourited) quotes in the report.
 *
 * Columns: Timecode, Quote, Participant, Section, Emotion, Intent,
 *          AI tags, User tags.
 *
 * @param {boolean} onlyFavs If true, include only favourited quotes.
 * @returns {string} The complete CSV text.
 */
function buildCsv(onlyFavs) {
  var rows = ['Timecode,Quote,Participant,Section,Emotion,Intent,AI tags,User tags'];
  var bqs = document.querySelectorAll('.quote-group blockquote');
  for (var i = 0; i < bqs.length; i++) {
    var bq = bqs[i];
    if (onlyFavs && !bq.classList.contains('favourited')) continue;
    rows.push(
      [
        csvEsc(bq.getAttribute('data-timecode') || ''),
        csvEsc(getQuoteText(bq)),
        csvEsc(bq.getAttribute('data-participant') || ''),
        csvEsc(getSection(bq)),
        csvEsc(bq.getAttribute('data-emotion') || ''),
        csvEsc(bq.getAttribute('data-intent') || ''),
        csvEsc(getQuoteTagsByType(bq, 'ai')),
        csvEsc(getQuoteTagsByType(bq, 'user')),
      ].join(',')
    );
  }
  return rows.join('\n');
}

// ── Clipboard ─────────────────────────────────────────────────────────────

/**
 * Copy text to the clipboard.
 *
 * Uses the modern Clipboard API where available, falling back to the
 * legacy `execCommand('copy')` technique.
 *
 * @param {string} text The text to copy.
 * @returns {Promise} Resolves on success, rejects on failure.
 */
function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  var ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (_) {
    /* ignored */
  }
  document.body.removeChild(ta);
  return ok ? Promise.resolve() : Promise.reject();
}

// ── Toast ─────────────────────────────────────────────────────────────────

/**
 * Show a transient toast notification.
 *
 * Only one toast is visible at a time — calling this removes any existing
 * toast first.  The toast auto-dismisses after 2 seconds.
 *
 * @param {string} msg The message to display.
 */
function showToast(msg) {
  var old = document.querySelector('.clipboard-toast');
  if (old) old.remove();

  var t = document.createElement('div');
  t.className = 'clipboard-toast';
  t.textContent = msg;
  document.body.appendChild(t);
  t.offsetHeight; // force reflow to trigger transition
  t.classList.add('show');

  setTimeout(function () {
    t.classList.remove('show');
    setTimeout(function () {
      t.remove();
    }, 300);
  }, 2000);
}

// ── Initialisation ────────────────────────────────────────────────────────

/**
 * Attach click handlers for the export buttons.
 */
function initCsvExport() {
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('#export-favourites');
    if (btn) {
      var csv = buildCsv(true);
      var n = csv.split('\n').length - 1;
      if (n === 0) {
        showToast('No favourites to export');
        return;
      }
      copyToClipboard(csv).then(
        function () {
          showToast(
            n + ' favourite' + (n !== 1 ? 's' : '') + ' copied as CSV'
          );
        },
        function () {
          showToast('Could not copy to clipboard');
        }
      );
      return;
    }
    btn = e.target.closest('#export-all');
    if (btn) {
      var csvAll = buildCsv(false);
      var nAll = csvAll.split('\n').length - 1;
      copyToClipboard(csvAll).then(
        function () {
          showToast(
            nAll + ' quote' + (nAll !== 1 ? 's' : '') + ' copied as CSV'
          );
        },
        function () {
          showToast('Could not copy to clipboard');
        }
      );
    }
  });
}
