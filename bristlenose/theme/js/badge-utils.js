/**
 * badge-utils.js — Shared badge DOM helpers used across all pages.
 *
 * Provides factory functions for creating and removing badge elements so
 * that the report page (tags.js), transcript pages (transcript-annotations.js),
 * and codebook page (codebook.js) share a single source of truth for badge
 * markup, animation, and colour resolution.
 *
 * This module is pure DOM — no localStorage access, no side-effects.
 * Load after storage.js and before any feature module.
 *
 * @module badge-utils
 */

/**
 * Create a user-tag badge element with a delete button.
 *
 * Returns a `<span class="badge badge-user">` with `data-badge-type="user"`,
 * `data-tag-name`, and a `<button class="badge-delete">×</button>` child.
 *
 * Does NOT add the `badge-appearing` class — callers opt-in to the fade-in
 * animation themselves if desired.
 *
 * @param {string}      name      The tag text.
 * @param {string|null} colourVar CSS var string for background, or null/undefined.
 * @returns {Element}   The badge span element.
 */
function createUserTagBadge(name, colourVar) {
  var span = document.createElement('span');
  span.className = 'badge badge-user';
  span.setAttribute('data-badge-type', 'user');
  span.setAttribute('data-tag-name', name);
  span.textContent = name;

  if (colourVar) {
    span.style.background = colourVar;
  }

  var del = document.createElement('button');
  del.className = 'badge-delete';
  del.setAttribute('aria-label', 'Remove tag');
  del.textContent = '\u00d7'; // ×
  span.appendChild(del);

  return span;
}

/**
 * Create a read-only user-tag badge (no delete button).
 *
 * Same markup as `createUserTagBadge()` but without the `×` button — for
 * contexts where the badge is informational, not editable (e.g. the tag
 * filter dropdown, tooltips, previews).
 *
 * @param {string}      name      The tag text.
 * @param {string|null} colourVar CSS var string for background, or null/undefined.
 * @returns {Element}   The badge span element.
 */
function createReadOnlyBadge(name, colourVar) {
  var span = document.createElement('span');
  span.className = 'badge badge-user';
  span.setAttribute('data-badge-type', 'user');
  span.setAttribute('data-tag-name', name);
  span.textContent = name;

  if (colourVar) {
    span.style.background = colourVar;
  }

  return span;
}

/**
 * Animate a badge's removal with a fade-out + scale animation.
 *
 * Adds `.badge-removing` and listens for `animationend`.  By default the
 * element is removed from the DOM.  Pass `opts.hide = true` to set
 * `display: none` instead (useful for AI badges that may be restored).
 * An optional `opts.onDone` callback fires after the animation.
 *
 * @param {Element} el   The badge element to remove.
 * @param {Object}  [opts]
 * @param {boolean} [opts.hide]   If true, hide instead of removing from DOM.
 * @param {Function} [opts.onDone] Callback after animation completes.
 */
function animateBadgeRemoval(el, opts) {
  opts = opts || {};
  el.classList.add('badge-removing');
  el.addEventListener(
    'animationend',
    function () {
      if (opts.hide) {
        el.style.display = 'none';
        el.classList.remove('badge-removing');
      } else {
        el.remove();
      }
      if (typeof opts.onDone === 'function') opts.onDone();
    },
    { once: true }
  );
}

/**
 * Resolve a tag's background colour from codebook data.
 *
 * Pure function — takes the full codebook object as a parameter (no global
 * state).  Returns a CSS `var()` reference or `null` for ungrouped tags.
 *
 * The codebook structure is:
 *   `{ groups: [{ id, colourSet, ... }], tags: { name: { group, colourIndex } } }`
 *
 * @param {string} tagName      The tag name (case-sensitive as stored).
 * @param {Object} codebookData The codebook object from localStorage.
 * @returns {string|null}       A CSS var() reference, or null if ungrouped.
 */
function getTagColour(tagName, codebookData) {
  if (!codebookData || !codebookData.tags) return null;
  var entry = codebookData.tags[tagName];
  if (!entry || !entry.group) return null;

  // Find the group by ID
  var group = null;
  var groups = codebookData.groups || [];
  for (var i = 0; i < groups.length; i++) {
    if (groups[i].id === entry.group) {
      group = groups[i];
      break;
    }
  }
  if (!group || !group.colourSet) return null;

  var idx = (entry.colourIndex || 0);
  return 'var(--bn-' + group.colourSet + '-' + (idx + 1) + '-bg)';
}
