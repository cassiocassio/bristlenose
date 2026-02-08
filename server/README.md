# Feedback endpoint

A single PHP file that receives anonymous feedback from Bristlenose HTML reports.

## What it does

1. Receives `POST { version, rating, message }` from the report's feedback modal
2. Appends a row to `data/feedback.csv` on the server
3. Emails you a notification
4. Returns `200 OK`

The report JS (`feedback.js`) tries `fetch()` first; falls back to clipboard copy on `file://` or if the endpoint is unreachable.

## Payload

```json
{ "version": "0.8.1", "rating": "like", "message": "great tool" }
```

Rating is one of: `hate`, `dislike`, `neutral`, `like`, `love`.

The endpoint also logs a timestamp and IP address in the CSV (for spam detection — not sent by the client).

## Deploy to Dreamhost

### 1. Generate a download token

On your Mac (Python — no PHP needed locally):

```bash
python3 -c "import secrets; print(secrets.token_hex(20))"
```

Save this string — you'll need it in step 3 and to download the CSV later.

### 2. Upload the PHP file

SFTP into your Dreamhost account and upload `feedback.php` to your web root:

```
cassiocassio.co.uk/feedback.php
```

### 3. Edit the config values

Open `feedback.php` on the server (or edit locally before uploading) and set:

```php
$EMAIL_TO       = 'your@email.com';
$DOWNLOAD_TOKEN = 'paste_the_token_from_step_1';
```

### 4. Create the data directory and protect it

SSH into Dreamhost:

```bash
cd ~/cassiocassio.co.uk   # or wherever your web root is
mkdir data
echo "Deny from all" > data/.htaccess
```

The `.htaccess` prevents anyone browsing to `cassiocassio.co.uk/data/feedback.csv` directly.

### 5. Test it

```bash
curl -X POST https://cassiocassio.co.uk/feedback.php \
  -H 'Content-Type: application/json' \
  -d '{"version":"0.8.1","rating":"like","message":"test from curl"}'
```

Should return `{"ok":true}` and you should get an email.

### 6. Download the CSV

```
https://cassiocassio.co.uk/feedback.php?download=1&token=YOUR_TOKEN
```

Bookmark this. Returns `bristlenose-feedback.csv` as a download.

## Wire up the report

In `bristlenose/stages/render_html.py`, change:

```python
_w("var BRISTLENOSE_FEEDBACK = true;")
_w("var BRISTLENOSE_FEEDBACK_URL = 'https://cassiocassio.co.uk/feedback.php';")
```

Then re-render any report to get the footer links.

## CORS

The endpoint sends `Access-Control-Allow-Origin: *` so it works from:
- `file://` origins (local HTML reports opened directly)
- `http://localhost` (if you ever run `bristlenose serve`)
- Any other origin

This is fine — the endpoint only appends to a CSV. There's nothing to steal.

## Gotchas

- **`From:` header must be a real mailbox** — Dreamhost silently drops `mail()` calls where the `From` address doesn't exist as a mailbox on the domain. Use a real address (e.g. `martin@cassiocassio.co.uk`), not `noreply@`
- **`www.` redirects to bare domain** — use `https://cassiocassio.co.uk/feedback.php` (no `www.`), otherwise POST requests get a 301 redirect which `fetch()` won't follow

## Security

- **Download token** — unguessable URL parameter. Same approach as "anyone with the link" sharing. Fine for anonymous feedback data
- **Input limits** — version truncated to 20 chars, rating to 20, message to 2000. No SQL, no eval, no shell — just `fputcsv()` and `mail()`
- **No authentication on POST** — the feedback is anonymous by design. Worst case: someone spams the CSV. Rate-limit at the web server level if that happens (Dreamhost supports `.htaccess` rate limiting)

## Files

```
server/
├── README.md        ← you are here
└── feedback.php     ← the endpoint (upload this to Dreamhost)
```

Not part of the Python package — this directory is for server-side infrastructure only.
