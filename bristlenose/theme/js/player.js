/**
 * player.js — Popout video/audio player integration.
 *
 * Handles clickable timecodes in the report.  When the user clicks a
 * `<a class="timecode">` link the module either opens a new popout player
 * window or sends a seek message to the existing one via `postMessage`.
 *
 * Architecture
 * ────────────
 * - The Python renderer writes a `BRISTLENOSE_VIDEO_MAP` global that maps
 *   participant IDs to media file URIs.
 * - `seekTo(pid, seconds)` is the single entry point.
 * - The popout window (`bristlenose-player.html`) listens for
 *   `{ type: 'bristlenose-seek', ... }` messages.
 * - Two no-op hooks (`bristlenose_onTimeUpdate`, `bristlenose_scrollToQuote`)
 *   are exposed on `window` for future bi-directional communication.
 *
 * @module player
 */

/* global BRISTLENOSE_VIDEO_MAP */

var playerWin = null;

/**
 * Seek a participant's media to a given timestamp.
 *
 * Opens the player window on first call; posts a seek message on
 * subsequent calls.
 *
 * @param {string} pid     Participant ID (key into BRISTLENOSE_VIDEO_MAP).
 * @param {number} seconds Timestamp in seconds.
 */
function seekTo(pid, seconds) {
  var uri = BRISTLENOSE_VIDEO_MAP[pid];
  if (!uri) return;

  var msg = { type: 'bristlenose-seek', pid: pid, src: uri, t: seconds };
  var hash =
    '#src=' + encodeURIComponent(uri) +
    '&t=' + seconds +
    '&pid=' + encodeURIComponent(pid);

  if (!playerWin || playerWin.closed) {
    playerWin = window.open(
      'bristlenose-player.html' + hash,
      'bristlenose-player',
      'width=720,height=480,resizable=yes,scrollbars=no'
    );
  } else {
    playerWin.postMessage(msg, '*');
    playerWin.focus();
  }
}

/**
 * Initialise click delegation for timecode links.
 *
 * Any `<a class="timecode" data-participant="…" data-seconds="…">` in the
 * document will trigger `seekTo` on click.
 */
function initPlayer() {
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a.timecode');
    if (!link) return;
    e.preventDefault();
    var pid = link.dataset.participant;
    var seconds = parseFloat(link.dataset.seconds);
    if (pid && !isNaN(seconds)) seekTo(pid, seconds);
  });

  // Extension hooks — currently unused but reserved for future features
  // such as synced scrolling or real-time highlight during playback.
  window.bristlenose_onTimeUpdate = function (/* pid, seconds */) {};
  window.bristlenose_scrollToQuote = function (/* pid, seconds */) {};
}
