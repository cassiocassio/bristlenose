# Footer Feedback in React Serve Mode

## Summary

This note documents the restoration of the footer feedback flow in the React-served app.

Goals:

- Restore "Report a bug" and "Feedback" links in the footer.
- Open a dedicated feedback modal (not the Help modal).
- Preserve legacy submit behavior: POST to endpoint when possible, clipboard fallback otherwise.
- Keep serve mode and export mode on one shared config shape.

## Scope

In scope:

- Serve mode React app (`bristlenose serve`)
- Exported React HTML reports (`/api/projects/{id}/export`)
- Footer feedback configuration in health payload

Out of scope:

- Static vanilla JS feedback implementation (`bristlenose/theme/js/feedback.js`) behavior changes
- New `/api/feedback` backend endpoint (not added)

## API Contract

`GET /api/health` now returns:

```json
{
  "status": "ok",
  "version": "0.x.y",
  "links": {
    "github_issues_url": "https://github.com/cassiocassio/bristlenose/issues/new"
  },
  "feedback": {
    "enabled": true,
    "url": "https://cassiocassio.co.uk/feedback.php"
  }
}
```

Compatibility:

- Existing keys `status` and `version` are unchanged.
- New keys are additive: `links` and `feedback`.

Export parity:

- `BRISTLENOSE_EXPORT.health` embeds the same shape as `/api/health`.

## Configuration

Defaults:

- `links.github_issues_url`: `https://github.com/cassiocassio/bristlenose/issues/new`
- `feedback.enabled`: `true`
- `feedback.url`: `https://cassiocassio.co.uk/feedback.php`

Environment overrides:

- `BRISTLENOSE_GITHUB_ISSUES_URL`
- `BRISTLENOSE_FEEDBACK_ENABLED`
- `BRISTLENOSE_FEEDBACK_URL`

Truthy parsing for `BRISTLENOSE_FEEDBACK_ENABLED`: `1`, `true`, `yes`, `on` (case-insensitive).

## Frontend Design

### Shared type

`frontend/src/utils/health.ts` defines the shared `HealthResponse` type and defaults.  
All consumers should use this type to avoid shape drift.

### Footer behavior

`Footer`:

- Uses health config for bug-link target and feedback enablement.
- Uses separate handlers:
  - `onOpenFeedback` for "Feedback"
  - `onToggleHelp` for `? for Help`
- Keeps version text behavior (`version x.y.z`).

### Feedback modal behavior

`FeedbackModal`:

- 5 sentiment options (`hate`, `dislike`, `neutral`, `like`, `love`)
- Optional message textarea
- Send button disabled until a sentiment is chosen
- Close on:
  - overlay click
  - Escape
  - Cancel button
- Draft persistence:
  - localStorage key: `bristlenose-feedback-draft`
  - autosave on input/selection change
  - restore on reopen

Submit logic:

1. Build payload `{ version, rating, message }`.
2. If `feedback.url` is set and protocol is HTTP(S), `POST` JSON.
3. On non-OK/fetch error/non-HTTP protocol, fallback to clipboard text copy.
4. Show toast message and clear draft/form state.

## CSS Visibility Rules

Footer feedback links are hidden by default and can be shown via two independent paths:

- Legacy static path: `body.feedback-enabled .feedback-links`
- React serve/export path: `.feedback-links.feedback-links-visible`

This allows React mode to show feedback links without relying on legacy JS body class toggling.

## Key Files

Backend:

- `bristlenose/server/routes/health.py`
- `bristlenose/server/routes/export.py`

Frontend:

- `frontend/src/utils/health.ts`
- `frontend/src/components/Footer.tsx`
- `frontend/src/components/FeedbackModal.tsx`
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/utils/exportData.ts`
- `bristlenose/theme/atoms/footer.css`

## Tests

Backend:

- `tests/test_serve.py` (health contract + env override checks)
- `tests/test_serve_export_api.py` (export health shape checks)

Frontend:

- `frontend/src/components/FeedbackModal.test.tsx`
- `frontend/src/components/Footer.test.tsx`
- `frontend/src/utils/exportData.test.ts`

## Manual QA Checklist

In `bristlenose serve`:

1. Footer shows `Report a bug` and `Feedback`.
2. Clicking `Feedback` opens the feedback modal (not Help).
3. Selecting a sentiment enables `Send`.
4. Successful submit shows success toast and closes modal.
5. Forced submit failure falls back to clipboard + toast.
6. `? for Help` still opens Help modal.

