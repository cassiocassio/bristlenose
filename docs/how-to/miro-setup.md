---
title: Connect Bristlenose to Miro
description: Push your analysed quotes straight onto a Miro board — a one-time setup walkthrough, including the manual token "key dance".
---

<p class="kicker">Export · Integrations</p>

# Connect Bristlenose to Miro

<p class="lead">Push your analysed quotes straight onto a Miro board — a first-draft research wall you can rearrange with your team, instead of building it sticky by sticky.</p>

Bristlenose creates a **new** board every time and never touches your existing ones: one column per section, then one per theme — the same left-to-right order as the report's Quotes page, with pink section headers and yellow quote stickies stacked in session-then-time order.

> **The one-time hurdle: getting a Miro "key".** Miro won't let an outside app write to your boards until you grant it permission. The **Connect button** is one click and needs no setup — use it if you can. The **manual token** route involves creating a small Miro "app" and copying a token; it's a five-minute developer detour, and it's the part most researchers find fiddly. We've written it out step by step so you don't have to guess.

## Before you start

- **A Miro account.** A free plan works for trying this out. Note Miro's free plan limits how many editable boards you can keep ([Free plan limits](https://help.miro.com/hc/en-us/articles/360017730373-Free-Plan)) — a paid plan removes the cap.
- **A team where you can create boards.** If you're on a company Miro, some organisations restrict who may install apps or create developer tokens — you may need an admin's help.
- **Two permissions ("scopes"):** `boards:read` and `boards:write`. The setup screen asks for these; that's all Bristlenose needs.
- **A minute of comfort with copy-paste.** The manual route asks you to copy one token from Miro and paste it into Bristlenose. That's the whole "key dance".

## Option A — the Connect button

_Recommended · coming in v1._

In the report toolbar, choose **Export → Send to Miro → Connect to Miro**. Your browser opens Miro's permission screen, you click **Allow**, and you're returned to Bristlenose — done. No app to create, no token to copy. Bristlenose stores the connection securely in your system keychain and refreshes it automatically.

This uses Miro's standard OAuth 2.0 sign-in (with PKCE — no shared secret). If your organisation blocks third-party app authorisation, fall back to Option B. [How Miro OAuth works ↗](https://developers.miro.com/docs/getting-started-with-oauth)

## Option B — paste a token (the manual key dance)

_Available now._

If you can't use the Connect button, create a personal Miro app once and paste its token. You only do this a single time.

### 1. Open your Miro apps page

Go to [miro.com/app/settings/user-profile/apps](https://miro.com/app/settings/user-profile/apps) (Profile settings → **Your apps**), or the [Miro Developer dashboard](https://developers.miro.com/).

### 2. Create a new app

Click **Create new app**. Give it a name like _"Bristlenose export"_ and associate it with the team whose boards you'll write to. ([Miro: build your first app ↗](https://developers.miro.com/docs/rest-api-build-your-first-hello-world-app))

### 3. Tick the two permissions

In the app's **Permissions**, enable `boards:read` and `boards:write`. Leave everything else off — Bristlenose needs nothing more.

### 4. Install the app and copy the token

Click **Install app and get OAuth token**, choose your team, and confirm. Miro shows you an **access token** — a long string. Copy it. ([Miro: access tokens ↗](https://developers.miro.com/docs/getting-started-with-oauth))

Treat this token like a password — it can read and write your boards. Don't paste it into chats or commit it to a repository.

### 5. Paste it into Bristlenose

Either paste it into **Export → Send to Miro → Paste token** in the report, or from a terminal:

```
bristlenose configure miro
```

Bristlenose validates the token immediately (a harmless read of one board) and stores it in your system keychain. If it's wrong or missing a scope, you'll be told exactly which.

> **Where your data goes.** Bristlenose runs entirely on your machine — but sending a board to Miro **uploads the selected quotes to Miro's servers**, where your team can see them. Miro becomes a data sub-processor for that content. Bristlenose shows you how many quotes will be sent and asks you to confirm before anything leaves your laptop. **Participant names are never sent** — only speaker codes (P1, P2). Hidden quotes are never included.

## If something goes wrong

| You see | What it means |
|---|---|
| _Invalid or expired token_ | The token was mistyped, or it expired. Create a fresh one (Option B) or reconnect (Option A). |
| _Token lacks required scopes_ | The app is missing `boards:write`. Re-open the app's Permissions, enable it, reinstall, and copy the new token. |
| _Only 3 boards editable_ | A free _developer_ team keeps just the three most recent boards editable. Use a paid team, or delete old test boards. ([Free plan limits ↗](https://help.miro.com/hc/en-us/articles/360017730373-Free-Plan)) |
| _Export paused / retrying_ | Large boards can hit Miro's rate limit; Bristlenose backs off and resumes automatically. ([Miro rate limits ↗](https://developers.miro.com/reference/rate-limiting)) |

---

_Miro is a trademark of Miro (RealtimeBoard, Inc.). Bristlenose is not affiliated with Miro._
