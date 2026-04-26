# Server endpoints (DreamHost)

Two PHP files staged in `website/` to deploy alongside the rest of the site to bristlenose.app:

- **`feedback.php`** — anonymous free-text feedback from the HTML report footer
- **`telemetry.php`** — batched Level 0 tag-rejection events from TestFlight alpha testers

Both are simple single-file endpoints (no DB, no framework) that append to CSV files under `data/`. They share the same `data/` directory and the same download-token mechanism.

> **Deployment status — 26 Apr 2026.** Neither file is live on bristlenose.app yet. `feedback.php` is still served from the legacy `cassiocassio.co.uk` URL during the 90-day overlap (see §Migration state). `telemetry.php` is intentionally not deployed until alpha-telemetry Phase 2 starts — there's no client emitting events, so an unreachable URL on the health payload is the correct state. Run `/deploy-website` only when Phase 2 is ready to test against production. Both files refuse to run (503) while `$DOWNLOAD_TOKEN` is still the placeholder, so a forgotten rotation fails loud rather than silent.

## What they do

### feedback.php

1. Receives `POST { version, rating, message }` from the report's feedback modal
2. Appends a row to `data/feedback.csv` on the server
3. Emails a notification to the configured address
4. Returns `200 OK`

Rating is one of: `hate`, `dislike`, `neutral`, `like`, `love`. Timestamp and IP are logged server-side for spam detection.

### telemetry.php

1. Receives `POST { events: [...] }` where each event has exactly four fields: `tag_id`, `prompt_version`, `event_type`, `researcher_id`
2. Validates each event (`event_type ∈ {suggested, accepted, rejected, edited}`, no empty fields, reasonable length caps)
3. Appends one row per event to `data/telemetry.csv`
4. Returns `200 OK` with `{"ok": true, "received": N}`

Batched on purpose — per-event emails would be spammy and per-event HTTP requests would waste cycles. See `docs/methodology/tag-rejections-are-great.md` for why the four-field minimum exists and what it deliberately excludes (no timestamps, no study IDs, no quote content).

## Deploy

Deployed via rsync as part of the `/deploy-website` skill (or `deploy-website` shell alias). The skill needs SSH agent access, which Claude Code's sandbox can't reach, so the user runs it manually. See `docs/private/deploy-website.md`.

First-time setup on DreamHost (in the bristlenose.app web root):

```bash
mkdir data
echo "Deny from all" > data/.htaccess
```

The `.htaccess` prevents anyone browsing to `bristlenose.app/data/feedback.csv` or `bristlenose.app/data/telemetry.csv` directly.

## Config values

Both PHP files have placeholder config values that must be edited on the server before first use (or locally before the first deploy):

### feedback.php

```php
$EMAIL_TO       = 'martin@cassiocassio.co.uk';   // notification recipient
$DOWNLOAD_TOKEN = 'CHANGE_ME_TO_A_RANDOM_STRING'; // bin2hex(random_bytes(20))
```

### telemetry.php

```php
$DOWNLOAD_TOKEN = 'CHANGE_ME_TO_A_RANDOM_STRING'; // can reuse the feedback token or mint a new one
```

Generate a fresh token locally:

```bash
python3 -c "import secrets; print(secrets.token_hex(20))"
```

## CSV downloads

Token-gated GET requests return the CSV as a file download:

```
https://bristlenose.app/feedback.php?download=1&token=YOUR_TOKEN
https://bristlenose.app/telemetry.php?download=1&token=YOUR_TOKEN
```

Bookmark both. Both endpoints use `hash_equals()` for constant-time token comparison and refuse to serve anything (503) if `$DOWNLOAD_TOKEN` is still the placeholder string — so a forgotten deploy-time rotation fails loud rather than silent.

## CORS

Both endpoints send `Access-Control-Allow-Origin: *` so they work from:

- `file://` origins (local HTML reports opened directly)
- `http://localhost` (the bundled Mac-app sidecar)
- Any other origin

This is fine — the endpoints only append to CSVs. There's nothing to steal.

## Migration state (April 2026)

The feedback.php endpoint used to live at `cassiocassio.co.uk/feedback.php`. During the 90-day overlap, both URLs are live:

- **New default**: `bristlenose.app/feedback.php` — what `frontend/src/utils/health.ts` now points to
- **Legacy**: `cassiocassio.co.uk/feedback.php` stays up until the user retires it manually — out of scope for the alpha-telemetry branch

Existing baked-into-HTML reports still hit the old URL. New serve-mode / export paths hit the new one.

## Gotchas

- **`From:` header must be a real mailbox on the domain** — DreamHost silently drops `mail()` calls where the `From` address doesn't exist as a mailbox. Use a real address (e.g. `martin@cassiocassio.co.uk`), not `noreply@`
- **`www.` redirects to bare domain** — use `https://bristlenose.app/feedback.php` (no `www.`), otherwise POST requests get a 301 redirect which `fetch()` won't follow
- **Shared `data/` directory** — both endpoints write to the same `data/` dir. Don't mkdir twice, don't .htaccess twice. The first endpoint to get hit creates both files; that's fine

## Security

- **Download token** — unguessable URL parameter. Same approach as "anyone with the link" sharing. Fine for anonymous feedback + pseudonymous telemetry data
- **Input limits** — all string fields are length-capped before writing; no SQL, no eval, no shell — just `fputcsv()`. `mail()` is called only from `feedback.php` and only after the rating is capped to 20 chars
- **No authentication on POST** — feedback and telemetry are pseudonymous by design. Worst case: someone spams the CSVs. DreamHost `.htaccess` rate limiting is available if that happens
- **No PII in telemetry** — the four-field discipline is enforced server-side as well as client-side. The endpoint rejects POSTs that include any field outside `{tag_id, prompt_version, event_type, researcher_id}` with a 400 — no silent field-drop, so client-side bugs that try to add a timestamp or study ID fail loudly rather than pollute the CSV quietly
- **CSV cell safety** — both endpoints strip `\r\n\0` and prefix `=+-@\t` with `'` before writing, so an operator opening the CSV in Excel won't execute a forged `=HYPERLINK()` cell
- **Batch + body caps** — `telemetry.php` rejects POSTs larger than 128 KB (`413`) or with more than 500 events per batch (`400`), so a runaway Swift retry loop can't fill the inode quota overnight
