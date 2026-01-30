/**
 * storage.js — Thin localStorage abstraction for Bristlenose report state.
 *
 * Every piece of user state (favourites, edits, tags, deleted badges) follows
 * the same pattern: read JSON from localStorage on load, mutate in memory,
 * write back after each change.  This module centralises that pattern so
 * individual feature modules never touch localStorage directly.
 *
 * Architecture
 * ────────────
 * - `createStore(key)` returns a `{ get, set }` pair bound to a single
 *   localStorage key.  Both are safe — corrupt/missing data returns the
 *   fallback value.
 * - Feature modules call `get()` once at init and `set(value)` after every
 *   mutation.  No debouncing — writes are rare and tiny.
 *
 * @module storage
 */

/* global localStorage */

/**
 * Create a read/write pair for a single localStorage key.
 *
 * @param {string} key  The localStorage key name.
 * @returns {{ get: (fallback?: *) => *, set: (value: *) => void }}
 */
function createStore(key) {
  return {
    get: function (fallback) {
      if (fallback === undefined) fallback = {};
      try {
        var raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (_) {
        return fallback;
      }
    },
    set: function (value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch (_) {
        /* quota exceeded — silently ignore */
      }
    },
  };
}
