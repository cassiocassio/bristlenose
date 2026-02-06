/**
 * feedback.js — Feedback modal for the Bristlenose report footer.
 *
 * Gated behind the BRISTLENOSE_FEEDBACK feature flag injected by render_html.py.
 * When the flag is false (default), initFeedback() returns immediately and the
 * footer links stay hidden via CSS.
 *
 * Dependencies: storage.js (createStore), modal.js (createModal),
 *               csv-export.js (copyToClipboard, showToast).
 *
 * @module feedback
 */

/* global BRISTLENOSE_FEEDBACK, BRISTLENOSE_FEEDBACK_URL, createStore,
          createModal, copyToClipboard, showToast */

var feedbackDraftStore = null;
var feedbackModal = null;

/**
 * Sentiment options: [value, emoji, label].
 */
var FEEDBACK_SENTIMENTS = [
  ['hate',    '\uD83D\uDE20', 'Frustrating'],
  ['dislike', '\uD83D\uDE15', 'Needs work'],
  ['neutral', '\uD83D\uDE10', "It's okay"],
  ['like',    '\uD83D\uDE42', 'Good'],
  ['love',    '\uD83D\uDE0A', 'Excellent']
];

// ── Modal creation ────────────────────────────────────────────────────────

/**
 * Build the feedback modal content HTML (everything inside the card).
 * @returns {string}
 */
function buildFeedbackContent() {
  var html = [
    '<h2>How is Bristlenose working for you?</h2>',
    '<div class="feedback-sentiments">'
  ];

  for (var i = 0; i < FEEDBACK_SENTIMENTS.length; i++) {
    var s = FEEDBACK_SENTIMENTS[i];
    html.push(
      '<button type="button" class="feedback-sentiment" data-value="' + s[0] + '">',
      '  <span class="feedback-sentiment-face">' + s[1] + '</span>',
      '  <span class="feedback-sentiment-label">' + s[2] + '</span>',
      '</button>'
    );
  }

  html.push(
    '</div>',
    '<label class="feedback-label">Help us improve</label>',
    '<textarea class="feedback-textarea"',
    '  placeholder="Tell us what\u2019s useful and what needs fixing\u2026"',
    '  rows="3"></textarea>',
    '<div class="feedback-actions">',
    '  <button type="button" class="feedback-btn feedback-btn-cancel">Cancel</button>',
    '  <button type="button" class="feedback-btn feedback-btn-send" disabled>Send</button>',
    '</div>',
    '<p class="bn-modal-footer">Anonymous \u2014 only your rating and message are shared.</p>'
  );

  return html.join('\n');
}

/**
 * Lazily create the feedback modal and wire all interactive behaviour.
 * @returns {{show: function, hide: function, isVisible: function, el: HTMLElement, card: HTMLElement}}
 */
function getFeedbackModal() {
  if (feedbackModal) return feedbackModal;

  feedbackModal = createModal({
    className: 'feedback-overlay',
    modalClassName: 'feedback-modal',
    content: buildFeedbackContent(),
    onHide: function () {
      saveFeedbackDraft(feedbackModal.card);
    }
  });

  var card = feedbackModal.card;

  // --- Wire sentiment buttons ---
  var sentimentBtns = card.querySelectorAll('.feedback-sentiment');
  for (var j = 0; j < sentimentBtns.length; j++) {
    sentimentBtns[j].addEventListener('click', function () {
      for (var k = 0; k < sentimentBtns.length; k++) {
        sentimentBtns[k].classList.remove('selected');
      }
      this.classList.add('selected');
      card.querySelector('.feedback-btn-send').disabled = false;
      saveFeedbackDraft(card);
    });
  }

  // --- Wire cancel ---
  card.querySelector('.feedback-btn-cancel').addEventListener('click', function () {
    feedbackModal.hide();
  });

  // --- Wire send ---
  card.querySelector('.feedback-btn-send').addEventListener('click', function () {
    submitFeedback(card);
  });

  // --- Restore draft ---
  var draft = feedbackDraftStore.get({ message: '', rating: '' });
  if (draft.message) {
    card.querySelector('.feedback-textarea').value = draft.message;
  }
  if (draft.rating) {
    var saved = card.querySelector(
      '.feedback-sentiment[data-value="' + draft.rating + '"]'
    );
    if (saved) {
      saved.classList.add('selected');
      card.querySelector('.feedback-btn-send').disabled = false;
    }
  }

  // --- Auto-save draft on textarea input ---
  card.querySelector('.feedback-textarea').addEventListener('input', function () {
    saveFeedbackDraft(card);
  });

  return feedbackModal;
}

// ── Draft persistence ─────────────────────────────────────────────────────

/**
 * Save current form state as a draft in localStorage.
 * @param {HTMLElement} card
 */
function saveFeedbackDraft(card) {
  var selected = card.querySelector('.feedback-sentiment.selected');
  var rating = selected ? selected.getAttribute('data-value') : '';
  var message = card.querySelector('.feedback-textarea').value;
  feedbackDraftStore.set({ rating: rating, message: message });
}

// ── Show / hide ───────────────────────────────────────────────────────────

/**
 * Show the feedback modal.
 */
function showFeedbackModal() {
  var m = getFeedbackModal();
  m.show();
  var ta = m.card.querySelector('.feedback-textarea');
  if (ta) {
    setTimeout(function () { ta.focus(); }, 100);
  }
}

// ── Submit ────────────────────────────────────────────────────────────────

/**
 * Read the Bristlenose version from the footer link text.
 * @returns {string}
 */
function getFeedbackVersion() {
  var link = document.querySelector('.footer-version');
  if (link) {
    var text = link.textContent || '';
    var match = text.match(/version\s+([\d.]+)/);
    if (match) return match[1];
  }
  return 'unknown';
}

/**
 * Submit feedback — try fetch to endpoint, fall back to clipboard.
 * @param {HTMLElement} card
 */
function submitFeedback(card) {
  var selected = card.querySelector('.feedback-sentiment.selected');
  if (!selected) return;

  var rating = selected.getAttribute('data-value');
  var message = card.querySelector('.feedback-textarea').value.trim();
  var version = getFeedbackVersion();

  var payload = { version: version, rating: rating, message: message };

  // Disable send button to prevent double-clicks
  var sendBtn = card.querySelector('.feedback-btn-send');
  sendBtn.disabled = true;

  // Try fetch if endpoint is configured and page is served over HTTP(S)
  var url = (typeof BRISTLENOSE_FEEDBACK_URL !== 'undefined') ? BRISTLENOSE_FEEDBACK_URL : '';
  var isHttp = location.protocol === 'http:' || location.protocol === 'https:';

  if (url && isHttp) {
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (resp) {
      if (resp.ok) {
        onFeedbackSent(card, 'Feedback sent \u2014 thank you!');
      } else {
        fallbackToClipboard(card, payload);
      }
    }).catch(function () {
      fallbackToClipboard(card, payload);
    });
  } else {
    fallbackToClipboard(card, payload);
  }
}

/**
 * Format feedback as plain text and copy to clipboard.
 * @param {HTMLElement} card
 * @param {Object} payload
 */
function fallbackToClipboard(card, payload) {
  var ratingLabel = payload.rating;
  for (var i = 0; i < FEEDBACK_SENTIMENTS.length; i++) {
    if (FEEDBACK_SENTIMENTS[i][0] === payload.rating) {
      ratingLabel = FEEDBACK_SENTIMENTS[i][2];
      break;
    }
  }

  var text = 'Bristlenose feedback (v' + payload.version + ')\n' +
             'Rating: ' + ratingLabel + '\n';
  if (payload.message) {
    text += 'Message: ' + payload.message + '\n';
  }

  copyToClipboard(text).then(function () {
    onFeedbackSent(card, 'Copied to clipboard \u2014 paste into an email or issue.');
  }).catch(function () {
    onFeedbackSent(card, 'Could not copy \u2014 please submit feedback manually.');
  });
}

/**
 * Clean up after feedback is sent: clear form, clear draft, close modal, toast.
 * @param {HTMLElement} card
 * @param {string} toastMsg
 */
function onFeedbackSent(card, toastMsg) {
  var btns = card.querySelectorAll('.feedback-sentiment');
  for (var i = 0; i < btns.length; i++) {
    btns[i].classList.remove('selected');
  }
  card.querySelector('.feedback-textarea').value = '';
  card.querySelector('.feedback-btn-send').disabled = true;
  feedbackDraftStore.set({ rating: '', message: '' });
  feedbackModal.hide();
  showToast(toastMsg);
}

// ── Init ──────────────────────────────────────────────────────────────────

/**
 * Initialise feedback feature. Returns immediately if the flag is off.
 */
function initFeedback() {
  if (typeof BRISTLENOSE_FEEDBACK === 'undefined' || !BRISTLENOSE_FEEDBACK) {
    return;
  }
  document.body.classList.add('feedback-enabled');
  feedbackDraftStore = createStore('bristlenose-feedback-draft');

  // Wire the footer "Feedback" link (can't use inline onclick — IIFE scope)
  var trigger = document.querySelector('.feedback-trigger');
  if (trigger) {
    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      showFeedbackModal();
    });
  }
}
