/**
 * player.js — Popout video/audio player integration.
 *
 * Handles clickable timecodes in the report.  When the user clicks a
 * `<a class="timecode">` link the module either opens a new popout player
 * window or sends a seek message to the existing one via `postMessage`.
 *
 * Also handles glowing timecodes: when the popout player is playing,
 * transcript segments and report blockquotes whose time range contains
 * the current playhead position glow.  Playing = pulsating glow;
 * paused = steady glow.
 *
 * Architecture
 * ────────────
 * - The Python renderer writes a `BRISTLENOSE_VIDEO_MAP` global that maps
 *   participant IDs to media file URIs.
 * - `seekTo(pid, seconds)` is the single entry point.
 * - The popout window (`bristlenose-player.html`) listens for
 *   `{ type: 'bristlenose-seek', ... }` messages.
 * - `bristlenose_onTimeUpdate` and `bristlenose_onPlayState` hooks
 *   receive playback position and play/pause state changes from the
 *   player window, driving the glow highlight.
 *
 * @module player
 */

/* global BRISTLENOSE_VIDEO_MAP, BRISTLENOSE_PLAYER_URL */

var playerWin = null;

// --- Glow highlight state ---

/** @type {Object<string, Array<{el: Element, start: number, end: number}>>|null} */
var _glowIndex = null;

/** @type {Set<Element>} */
var _glowActive = new Set();

/** @type {boolean} */
var _playerPlaying = false;

/**
 * Build the glow index — a lookup from participant ID to an array of
 * { el, start, end } objects.
 *
 * On transcript pages: indexes `.transcript-segment[data-start-seconds]` divs.
 * On report pages: indexes `blockquote[data-participant]` elements via their
 * child `.timecode` link's data-seconds / data-end-seconds.
 */
function _buildGlowIndex() {
  _glowIndex = {};
  _glowActive = new Set();

  // Transcript page segments
  var segments = document.querySelectorAll(
    '.transcript-segment[data-start-seconds][data-end-seconds]'
  );
  for (var i = 0; i < segments.length; i++) {
    var seg = segments[i];
    var pid = seg.getAttribute('data-participant');
    if (!pid) continue;
    var start = parseFloat(seg.getAttribute('data-start-seconds'));
    var end = parseFloat(seg.getAttribute('data-end-seconds'));
    if (isNaN(start) || isNaN(end)) continue;
    if (!_glowIndex[pid]) _glowIndex[pid] = [];
    _glowIndex[pid].push({ el: seg, start: start, end: end });
  }

  // Fix zero-length segments: when end_time == start_time (parsed from .txt
  // files where only start timecodes exist), use the next segment's start
  // time as the effective end so the glow covers the full segment duration.
  var pids = Object.keys(_glowIndex);
  for (var p = 0; p < pids.length; p++) {
    var entries = _glowIndex[pids[p]];
    for (var k = 0; k < entries.length; k++) {
      if (entries[k].end <= entries[k].start) {
        entries[k].end = (k + 1 < entries.length) ? entries[k + 1].start : Infinity;
      }
    }
  }

  // Report page blockquotes
  var quotes = document.querySelectorAll('blockquote[data-participant]');
  for (var j = 0; j < quotes.length; j++) {
    var bq = quotes[j];
    var qpid = bq.getAttribute('data-participant');
    if (!qpid) continue;
    var tc = bq.querySelector('a.timecode[data-seconds][data-end-seconds]');
    if (!tc) continue;
    var qstart = parseFloat(tc.getAttribute('data-seconds'));
    var qend = parseFloat(tc.getAttribute('data-end-seconds'));
    if (isNaN(qstart) || isNaN(qend)) continue;
    if (!_glowIndex[qpid]) _glowIndex[qpid] = [];
    _glowIndex[qpid].push({ el: bq, start: qstart, end: qend });
  }
}

/**
 * Update glow highlights for the given playback position.
 *
 * @param {string} pid       Participant ID currently playing.
 * @param {number} seconds   Current playhead position in seconds.
 * @param {boolean} playing  Whether the player is actively playing.
 */
function _updateGlow(pid, seconds, playing) {
  if (!_glowIndex) _buildGlowIndex();

  var entries = _glowIndex[pid] || [];
  var newActive = new Set();

  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i];
    if (seconds >= entry.start && seconds < entry.end) {
      newActive.add(entry.el);
    }
  }

  // Remove glow from elements no longer active
  _glowActive.forEach(function(el) {
    if (!newActive.has(el)) {
      el.classList.remove('bn-timecode-glow');
      el.classList.remove('bn-timecode-playing');
    }
  });

  // Add glow to newly active elements; auto-scroll transcript segments
  newActive.forEach(function(el) {
    if (!_glowActive.has(el) && el.classList.contains('transcript-segment')) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    el.classList.add('bn-timecode-glow');
    if (playing) {
      el.classList.add('bn-timecode-playing');
    } else {
      el.classList.remove('bn-timecode-playing');
    }
  });

  _glowActive = newActive;
}

/**
 * Update the playing/paused visual state on already-glowing elements.
 *
 * @param {boolean} playing
 */
function _updatePlayState(playing) {
  _playerPlaying = playing;
  _glowActive.forEach(function(el) {
    if (playing) {
      el.classList.add('bn-timecode-playing');
    } else {
      el.classList.remove('bn-timecode-playing');
    }
  });
}

/**
 * Remove all glow classes from the document.
 * Called when the player window is closed.
 */
function _clearAllGlow() {
  _glowActive.forEach(function(el) {
    el.classList.remove('bn-timecode-glow');
    el.classList.remove('bn-timecode-playing');
  });
  _glowActive = new Set();
}

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

  var playerUrl = (typeof BRISTLENOSE_PLAYER_URL !== 'undefined')
    ? BRISTLENOSE_PLAYER_URL
    : 'assets/bristlenose-player.html';

  if (!playerWin || playerWin.closed) {
    playerWin = window.open(
      playerUrl + hash,
      'bristlenose-player',
      'width=720,height=480,resizable=yes,scrollbars=no'
    );
  } else {
    playerWin.postMessage(msg, '*');
    playerWin.focus();
  }
}

/**
 * Initialise click delegation for timecode links and playback-sync hooks.
 *
 * Any `<a class="timecode" data-participant="…" data-seconds="…">` in the
 * document will trigger `seekTo` on click.
 */
function initPlayer() {
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a.timecode');
    if (!link) return;
    var pid = link.dataset.participant;
    var seconds = parseFloat(link.dataset.seconds);
    // Only intercept if this is a player-enabled timecode (has data attributes).
    // Coverage section links use class="timecode" but navigate to transcript pages.
    if (pid && !isNaN(seconds)) {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      seekTo(pid, seconds);
    }
  });

  // Listen for postMessage from the player window.
  // The player posts bristlenose-timeupdate (~4x/sec during playback)
  // and bristlenose-playstate (on play/pause events).
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || typeof d.type !== 'string') return;
    if (d.type === 'bristlenose-timeupdate' && d.pid) {
      var playing = d.playing !== undefined ? d.playing : true;
      _playerPlaying = playing;
      _updateGlow(d.pid, d.seconds, playing);
    } else if (d.type === 'bristlenose-playstate' && d.pid) {
      _playerPlaying = d.playing;
      _updatePlayState(d.playing);
    }
  });

  // Poll for player window closure to clean up glow state.
  setInterval(function() {
    if (playerWin && playerWin.closed) {
      playerWin = null;
      _clearAllGlow();
    }
  }, 1000);
}

// ── Expose to window for React island interop ────────────────────────────
window.seekTo = seekTo;
