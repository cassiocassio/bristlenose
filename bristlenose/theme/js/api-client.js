/**
 * api-client.js — HTTP abstraction for Bristlenose serve mode.
 *
 * When running under `bristlenose serve`, the server injects
 * `window.BRISTLENOSE_API_BASE` (e.g. '/api/projects/1') into the HTML.
 * This module provides thin wrappers around `fetch` that fire-and-forget
 * PUT calls after each localStorage write.  When the global is absent
 * (static HTML opened from disk), all calls are silently skipped.
 *
 * Architecture
 * ────────────
 * - `isServeMode()` — returns true when the server injected the API base.
 * - `apiGet(path)` — GET JSON from the server.  Returns parsed data or null.
 * - `apiPut(path, data)` — PUT JSON to the server.  Shows toast on error.
 *
 * Dependencies: `showToast` from csv-export.js (optional — graceful if absent).
 *
 * @module api-client
 */

/* global BRISTLENOSE_API_BASE, showToast */

/**
 * Check whether the report is running under `bristlenose serve`.
 *
 * @returns {boolean}
 */
function isServeMode() {
  return typeof BRISTLENOSE_API_BASE === 'string' && BRISTLENOSE_API_BASE.length > 0;
}

/**
 * GET JSON from a serve-mode API endpoint.
 *
 * @param {string} path  Relative path appended to BRISTLENOSE_API_BASE.
 * @returns {Promise<*>}  Parsed JSON, or null on error.
 */
function apiGet(path) {
  if (!isServeMode()) return Promise.resolve(null);
  return fetch(BRISTLENOSE_API_BASE + path, {
    headers: { 'Accept': 'application/json' },
  })
    .then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .catch(function (err) {
      if (typeof console !== 'undefined') console.warn('[api-client] GET failed:', path, err);
      return null;
    });
}

/**
 * PUT JSON to a serve-mode API endpoint (fire-and-forget).
 *
 * The caller has already updated localStorage — this is a background sync.
 * On failure, a toast is shown but no rollback occurs (localStorage is the
 * source of truth for the current page session).
 *
 * @param {string} path  Relative path appended to BRISTLENOSE_API_BASE.
 * @param {*}      data  JSON-serialisable payload.
 * @returns {Promise<boolean>}  True on success, false on failure.
 */
function apiPut(path, data) {
  if (!isServeMode()) return Promise.resolve(false);
  return fetch(BRISTLENOSE_API_BASE + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
    .then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return true;
    })
    .catch(function (err) {
      if (typeof console !== 'undefined') console.warn('[api-client] PUT failed:', path, err);
      if (typeof showToast === 'function') showToast('Could not save to server');
      return false;
    });
}
