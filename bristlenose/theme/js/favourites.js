/**
 * favourites.js — Star / un-star quotes and reorder them within their group.
 *
 * Users click the star icon on a quote to mark it as a favourite.  Favourited
 * quotes float to the top of their section group with a smooth FLIP animation.
 * State is persisted in localStorage so favourites survive page reloads.
 *
 * Architecture
 * ────────────
 * - `favourites` (object): an in-memory map of quote ID → `true`.
 * - `originalOrder` (object): snapshot of DOM indices taken on load so that
 *   un-favourited quotes return to their original position.
 * - `reorderGroup(group, animate)` implements the FLIP (First-Last-Invert-Play)
 *   animation technique:
 *     1. Record each blockquote's bounding rect            (FIRST)
 *     2. DOM-reorder: favourites first, rest in original order
 *     3. Compute the delta between old and new positions    (INVERT)
 *     4. Animate the transform back to zero                 (PLAY)
 *
 * Dependencies: `createStore` from storage.js.
 *
 * @module favourites
 */

/* global createStore */

var favStore = createStore('bristlenose-favourites');
var favourites = favStore.get({});

// Capture original DOM order per group so un-favourited quotes go home.
var originalOrder = {};

/**
 * Sort blockquotes inside a `.quote-group` — favourites first.
 *
 * @param {Element} group    The `.quote-group` container.
 * @param {boolean} animate  Whether to run the FLIP animation.
 */
function reorderGroup(group, animate) {
  var quotes = Array.prototype.slice.call(group.querySelectorAll('blockquote'));
  if (!quotes.length) return;

  // --- FIRST: record current positions ---
  var rects = {};
  if (animate) {
    quotes.forEach(function (bq) {
      rects[bq.id] = bq.getBoundingClientRect();
    });
  }

  // --- Partition: favourited first, rest in original order ---
  var favs = [];
  var rest = [];
  quotes.forEach(function (bq) {
    (bq.classList.contains('favourited') ? favs : rest).push(bq);
  });
  rest.sort(function (a, b) {
    return (originalOrder[a.id] || 0) - (originalOrder[b.id] || 0);
  });
  favs.concat(rest).forEach(function (bq) {
    group.appendChild(bq);
  });

  if (!animate) return;

  // --- INVERT: offset each element back to where it was ---
  quotes.forEach(function (bq) {
    var old = rects[bq.id];
    var cur = bq.getBoundingClientRect();
    var dy = old.top - cur.top;
    if (Math.abs(dy) < 1) return;
    bq.style.transform = 'translateY(' + dy + 'px)';
    bq.style.transition = 'none';
  });

  // --- PLAY: animate to final position ---
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      quotes.forEach(function (bq) {
        bq.classList.add('fav-animating');
        bq.style.transform = '';
        bq.style.transition = '';
      });
      setTimeout(function () {
        quotes.forEach(function (bq) {
          bq.classList.remove('fav-animating');
        });
      }, 250);
    });
  });
}

/**
 * Bootstrap favourites: restore state from localStorage, reorder groups,
 * and attach the star-click handler.
 */
function initFavourites() {
  // Snapshot original DOM order for every group.
  var allGroups = document.querySelectorAll('.quote-group');
  for (var g = 0; g < allGroups.length; g++) {
    var bqs = Array.prototype.slice.call(
      allGroups[g].querySelectorAll('blockquote')
    );
    bqs.forEach(function (bq, idx) {
      originalOrder[bq.id] = idx;
    });
  }

  // Restore favourited class from localStorage.
  Object.keys(favourites).forEach(function (qid) {
    var bq = document.getElementById(qid);
    if (bq) bq.classList.add('favourited');
  });

  // Initial reorder (no animation on page load).
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) {
    reorderGroup(groups[i], false);
  }

  // Delegate star clicks.
  document.addEventListener('click', function (e) {
    var star = e.target.closest('.fav-star');
    if (!star) return;
    e.preventDefault();
    var bq = star.closest('blockquote');
    if (!bq || !bq.id) return;

    var isFav = bq.classList.toggle('favourited');
    if (isFav) {
      favourites[bq.id] = true;
    } else {
      delete favourites[bq.id];
    }
    favStore.set(favourites);

    var group = bq.closest('.quote-group');
    if (group) reorderGroup(group, true);
  });
}
