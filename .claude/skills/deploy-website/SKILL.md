---
name: deploy-website
description: Deploy website/ to bristlenose.app via rsync over SSH
user-invocable: true
allowed-tools: Bash, Read, AskUserQuestion
---

Deploy the static website from `website/` to bristlenose.app on DreamHost.

**Target:** `dreamhost:/home/cassiocassio/bristlenose.app/`

**What gets deployed:** `index.html`, `manual.html`, `style.css` — everything in `website/` except working notes.

## Step 1: Pre-flight checks

1. Confirm you're in the main repo:
   ```bash
   cd /Users/cassio/Code/bristlenose
   ```

2. Check `website/` has files:
   ```bash
   ls website/
   ```

3. Scan for known placeholders that shouldn't go live:
   ```bash
   grep -r 'PUBLICATION_NAME' website/
   grep -r 'href="#"' website/*.html
   ```
   If any placeholders are found, **warn the user** and list them. Ask whether to proceed or fix first (AskUserQuestion).

## Step 2: Dry run

Show what will be synced:

```bash
rsync -avz --dry-run --delete \
  --exclude='draft text for*' \
  --exclude='weeknotes/' \
  website/ \
  dreamhost:/home/cassiocassio/bristlenose.app/
```

Show the output to the user. The excludes skip the draft markdown file (working notes) and the weeknotes archive (raw markdown mirror of the Substack feed — kept in the repo for portability, not served). `--delete` removes files on the remote that no longer exist locally.

## Step 3: Confirm and deploy

Ask the user to confirm (AskUserQuestion): "Deploy these files to bristlenose.app?"

If confirmed, run the real deploy:

```bash
rsync -avz --delete \
  --exclude='draft text for*' \
  --exclude='weeknotes/' \
  website/ \
  dreamhost:/home/cassiocassio/bristlenose.app/
```

## Step 4: Verify

Check the live site responds:

```bash
curl -s -o /dev/null -w '%{http_code}' https://bristlenose.app/
curl -s -o /dev/null -w '%{http_code}' https://bristlenose.app/manual.html
```

Both should return `200`. Report success or failure.
