/**
 * modal.js — Shared modal overlay helper.
 *
 * Provides createModal() which handles the boilerplate shared by all
 * modal dialogs: overlay backdrop, click-outside-to-close, close button,
 * Escape key, and show/hide with visibility tracking.
 *
 * Usage:
 *   var modal = createModal({
 *     className: 'help-overlay',          // overlay CSS class (adds bn-overlay)
 *     modalClassName: 'help-modal',        // inner card CSS class (adds bn-modal)
 *     content: '<h2>Title</h2><p>Body</p>' // innerHTML for the card
 *   });
 *   modal.show();
 *   modal.hide();
 *   modal.isVisible();  // boolean
 *   modal.el;           // the overlay element
 *   modal.card;         // the inner card element
 *
 * The Escape key is handled centrally — createModal registers each modal
 * so handleEscape() can close the topmost visible one.
 *
 * @module modal
 */

/**
 * Registry of all modals, checked by handleEscape().
 * @type {Array<{isVisible: function, hide: function}>}
 */
var _modalRegistry = [];

/**
 * Close the topmost visible modal. Called from the Escape key handler
 * in focus.js. Returns true if a modal was closed, false otherwise.
 *
 * @returns {boolean}
 */
function closeTopmostModal() {
  // Walk backwards — last-registered modals are on top
  for (var i = _modalRegistry.length - 1; i >= 0; i--) {
    if (_modalRegistry[i].isVisible()) {
      _modalRegistry[i].hide();
      return true;
    }
  }
  return false;
}

/**
 * Create a modal overlay with standard behaviour.
 *
 * @param {Object} opts
 * @param {string} opts.className     — CSS class for the overlay (e.g. 'help-overlay')
 * @param {string} opts.modalClassName — CSS class for the card (e.g. 'help-modal')
 * @param {string} opts.content       — innerHTML for the card body
 * @param {function} [opts.onHide]    — optional callback after hide
 * @returns {{show: function, hide: function, isVisible: function, el: HTMLElement, card: HTMLElement}}
 */
function createModal(opts) {
  var visible = false;

  // Build DOM
  var overlay = document.createElement('div');
  overlay.className = 'bn-overlay ' + opts.className;

  var card = document.createElement('div');
  card.className = 'bn-modal ' + opts.modalClassName;

  // Close button
  var closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'bn-modal-close';
  closeBtn.setAttribute('aria-label', 'Close');
  closeBtn.textContent = '\u00d7';

  card.appendChild(closeBtn);

  // Content — set via innerHTML on a wrapper so the close button isn't clobbered
  var body = document.createElement('div');
  body.innerHTML = opts.content;
  card.appendChild(body);

  overlay.appendChild(card);
  document.body.appendChild(overlay);

  // --- Behaviour ---

  function show() {
    overlay.classList.add('visible');
    visible = true;
  }

  function hide() {
    overlay.classList.remove('visible');
    visible = false;
    if (opts.onHide) opts.onHide();
  }

  function isVisible() {
    return visible;
  }

  // Click outside card → close
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) {
      hide();
    }
  });

  // Close button
  closeBtn.addEventListener('click', function () {
    hide();
  });

  // Register for Escape handling
  var handle = { isVisible: isVisible, hide: hide };
  _modalRegistry.push(handle);

  return { show: show, hide: hide, isVisible: isVisible, el: overlay, card: card };
}
