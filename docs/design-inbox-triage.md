# Inbox triage — `email-catch` design

> **Status**: MVP shipped Apr 2026 — `~/bin/email-catch.py` + `~/.claude/inbox-rules.json` + SessionStart hook. Single-account (`martin@cassiocassio.co.uk`) configured at launch; multi-account architecture from day 1 (bristlenose mailbox added later by config + Keychain entry, no code change). Read + `\Flagged` only. Future iterations (`/email-skim`, `/email-tidy`, `/email-dig`, public repo) deferred.
> **Scope**: Personal tooling — *not* a Bristlenose product feature. Lives outside the Bristlenose tree (`~/bin/`, `~/.claude/`). This doc is in `docs/` because the design touches Bristlenose-adjacent operational hygiene (Weblate notifications, PyPI 2FA, DreamHost-as-recovery-email risk) that future contributors might need to understand.
> **Trigger**: Weblate emailed warnings (`Your translation project is scheduled for removal`) that landed in `martin@cassiocassio.co.uk` and got buried under 100+ LinkedIn job alerts and 18 years of accumulated noise. By the time the warning surfaced, the project had been removed and a Weblate Care ticket (#2013688) was needed to recover.

## Context

**MVP goal: never miss the next Weblate-class warning.** That's it. Everything else (digests, filing, corpus queries, public repo, triage-bot forwarding, multi-account, bristlenose aliases) is deferred to future iterations.

## MVP scope

**One job, multi-account ready, one mailbox configured at launch.**

- IMAP via DreamHost: `imap.dreamhost.com:993` (TLS)
- One Python script: `~/bin/email-catch.py` — uses stdlib `imaplib`, no MCP server, no third-party deps. **Multi-account from day one** — main loop iterates over `accounts[]` in the rules file. v1 ships with one account configured (`martin@cassiocassio.co.uk`); adding the bristlenose mailbox later is config + a second Keychain entry, ~5 minutes. No code change.
- One rules file: `~/.claude/inbox-rules.json` — accounts list + must-not-miss patterns. Most patterns are account-agnostic (Weblate, password resets, GitHub security). Account-specific patterns use `recipient:` matchers (e.g. anything to `security@bristlenose.app` → flag).
- One Claude Code integration: `SessionStart` hook calls the script.

When you open Claude Code, the hook iterates each configured account, fetches recent unseen mail, matches against the patterns, sets `\Flagged` on hits, and prints a one-line summary across all accounts. Silent if zero hits. Mail.app picks up the flags via IMAP within seconds, on Mac and iPhone.

That's the whole MVP. No slash commands. No folders. No tier classification. No digest. No corpus query.

**DreamHost gotcha baked in:** the script reads `To:` (and `X-Original-To:` if present) for alias matching, **never `Delivered-To:`** — DreamHost rewrites the latter to internal MX hostnames (`x10950589@pdx1-sub0-mail-mx206.dreamhost.com`) that are useless for routing rules. Confirmed by the earlier 319-message export.

## Approach

```
SessionStart hook
  └── ~/bin/email-catch.py
        ├── reads creds from macOS Keychain
        ├── connects to imap.dreamhost.com:993 over TLS
        ├── SELECT INBOX
        ├── SEARCH (UNSEEN SINCE <14 days ago>)
        ├── FETCH headers (From, To, Subject, Date, Message-ID)
        ├── matches each against inbox-rules.json must-not-miss patterns
        ├── STORE +FLAGS \Flagged on matches
        ├── appends to ~/.claude/inbox-log/YYYY-MM-DD.jsonl
        └── prints "2 must-not-miss flagged: Weblate × 1, GitHub OAuth × 1 — see Mail.app"
```

State lives on the IMAP server (`\Flagged` keyword). No local DB. Re-running is idempotent because already-`\Flagged` messages are skipped from re-flagging (the script's `STORE` is conditional on the flag not already being set).

**Why imaplib not MCP:** ~150 lines of stdlib code, no third-party vetting, no fork/pin/lockfile, no supply-chain surface. The MCP path makes sense once we want slash commands (`/email-skim` etc.) — at that point the MCP server's tool surface earns its keep. For pure SessionStart-hook catch, it's overkill.

## Files

| Path | Purpose |
|---|---|
| `~/bin/email-catch.py` | The script. ~150 lines. No deps beyond stdlib. |
| `~/.claude/inbox-rules.json` | Must-not-miss patterns + (later) sweep allowlist + folder rules |
| `~/.claude/settings.json` | Adds the SessionStart hook entry |
| `~/.claude/inbox-log/YYYY-MM-DD.jsonl` | Append-only audit log of every flag set |
| Keychain entry: `dreamhost-imap.cassiocassio` | IMAP password |

Nothing in `/home/user/bristlenose/`. Nothing in any new git repo (yet). The branch `claude/integrate-imap-email-99J93` will be deleted.

## `inbox-rules.json` initial patterns

```json
{
  "must_not_miss": [
    {"sender": "^noreply@weblate\\.org$",         "reason": "Weblate project status"},
    {"sender": "^care@weblate\\.org$",            "reason": "Weblate support"},
    {"sender": "^noreply@github\\.com$",          "reason": "GitHub account/security events"},
    {"sender": "^.+@login\\.ubuntu\\.com$",       "reason": "Ubuntu account/password"},
    {"sender": "^.+@dreamhost\\.com$",            "reason": "Hosting/billing"},
    {"sender": "^.+@stripe\\.com$",               "reason": "Payments"},
    {"sender": "^.+@(apple|developer\\.apple)\\.com$", "reason": "Apple Developer Program"},
    {"sender": "^.+@pypi\\.org$",                 "reason": "PyPI account"},
    {"sender": "^mailer-daemon@",                 "reason": "Bounces"},
    {"subject": "(?i)\\bpassword\\s+reset\\b",    "reason": "Password reset (any sender)"},
    {"subject": "(?i)\\bsecurity\\s+alert\\b",    "reason": "Security alert (any sender)"},
    {"subject": "(?i)scheduled for removal",      "reason": "The Weblate-class warning"},
    {"subject": "(?i)domain.*expir",              "reason": "Domain expiry"}
  ]
}
```

Patterns are anchored regexes matched against the envelope `From:` (header `From:` if no envelope) or the `Subject:`. Designed to start small — extend as you encounter new categories.

## Security hardening (MVP)

Threat model is unchanged: **the actual risk is my own homegrown script misbehaving, not external attackers.** Defences:

1. **`--max-age 30d` floor.** The script never reads or modifies mail older than 30 days. The 18-year corpus stays sacred. (Implemented as `SEARCH SINCE <30-days-ago>` in IMAP.)
2. **Read + flag only.** No `MOVE`, no `\Deleted`, no `EXPUNGE`. The only mutating IMAP operation is `STORE +FLAGS \Flagged`. Worst case: a flag goes on the wrong message. Recoverable in seconds in Mail.app.
3. **Keychain for creds.** Password retrieved at runtime via `security find-generic-password -w -s dreamhost-imap.cassiocassio`. Never on disk in plaintext, never in shell history. Script holds it in memory only.
4. **Append-only audit log** at `~/.claude/inbox-log/YYYY-MM-DD.jsonl`. One line per `STORE +FLAGS` call: `{timestamp, message-id, from, subject, matched-rule, flag-set}`. Greppable.
5. **Silent on failure.** Keychain locked, network down, IMAP timeout — hook prints nothing, never blocks the session start. The nudge is decoration, not load-bearing.

## Pre-flight hardening (one-time, before first run)

The MVP script's threat surface is small (read + flag only, no third-party deps, no LLM in the loop). The bigger residual risk is **the IMAP credential itself** — basic-auth over TLS, no protocol-level 2FA, full read/write/delete on every historical message. These five steps tighten everything around it. All cheap, high-leverage, do once.

1. **DreamHost panel 2FA.** Enable TOTP or hardware-key 2FA on the DreamHost web panel (separate from the mailbox password). Highest-leverage mitigation — locks down the credential-reset surface that would otherwise let an attacker change your IMAP password remotely without ever needing it.
2. **Strong unique IMAP password** generated by password manager, stored only in macOS Keychain:
   ```bash
   security add-generic-password \
     -s dreamhost-imap.cassiocassio \
     -a martin@cassiocassio.co.uk \
     -w '<paste-strong-random-password>'
   ```
   Never on disk in plaintext, never in shell history (use `-w` followed by the password as an argument; better, omit `-w` and `security` will prompt without echoing).
3. **Quarterly password rotation.** Calendar reminder. Cheapest meaningful defence against stale-password-leak-from-old-breach scenarios.
4. **2FA audit on accounts using `martin@cassiocassio.co.uk` as recovery email.** This is the actual load-bearing mitigation — the structural weakness isn't IMAP itself, it's "many account-recovery flows funnel through cassiocassio." Verify TOTP or hardware-key 2FA on:
   - **PyPI** (publishes `bristlenose`) — should be mandatory since Jan 2024 but verify
   - **Anthropic Console**
   - **Apple Developer Program / Apple ID**
   - **Domain registrars** for `cassiocassio.co.uk` and `bristlenose.app`
   - **npm / Homebrew tap GitHub org** (if anything's published there)
   - **Weblate / Crowdin / any translation platform**
   - **DreamHost panel** itself (covered by #1)
   - GitHub + LinkedIn already confirmed 2FA-enabled
5. **Little Snitch egress rule** confining `~/bin/email-catch.py` to `imap.dreamhost.com:993` only. If the script is ever modified or compromised, it can't exfiltrate to a different host. Belt-and-braces against "the homegrown tool itself misbehaves" — the same threat model that drives the rest of the design.

**Provider choice rationale (not migrating away from DreamHost):** technical IMAP 2FA on Gmail/iCloud is genuinely better, but **recoverability is a security property too** — DreamHost's human-responsive support for individual customers beats free-Gmail's notorious lockout pattern, and that matters most for the 1A mailbox. The structural weakness is "lots of recovery flows depend on this address," which is fixed by item #4 above, not by changing provider.

**Known escape hatch:** DreamHost's panel offers a "move my email to Google" migration. On the *free* Google tier this is "better crypto, worse service" — you get XOAUTH2 + 2FA but lose the human-responsive support that makes DreamHost the right home for a 1A recovery email. With a paid Google Workspace account ($6+/month) the support trade flips and migration becomes attractive. Not the right move now; revisit if/when commercial scale changes the equation.

## Verification

1. **Install.** Place script, rules file, hook entry. Add Keychain entry for the IMAP password.
2. **Smoke test.** `~/bin/email-catch.py --dry-run` — connects, fetches, prints what *would* be flagged. No IMAP writes. Confirms creds + connectivity + pattern matching.
3. **First real run.** `~/bin/email-catch.py` — flags whatever's currently unseen and matching. Confirm flags appear in Mail.app on Mac and iPhone within seconds.
4. **The Weblate test.** Send yourself a test message from `noreply@weblate.org`-looking sender (or temporarily add a test pattern). Re-run script. Confirm caught and flagged. Remove test rule.
5. **Idempotency.** Re-run script. Already-flagged messages stay flagged, no duplicate audit-log entries.
6. **Open a new Claude Code session.** SessionStart hook runs the script, prints summary line if anything flagged.

## Future iterations (deferred, captured for later)

Each of these is *additional* once MVP is proven useful — not prerequisites to ship.

- **`/email-skim`** — weekly aggregate digest (job-market pulse, conferences, Substack roundup). Useful when MVP catches enough that you trust it.
- **`/email-tidy`** — file noise into `Filed/Jobs/`, `Filed/Conferences/`, etc. Builds queryable corpus. Add when INBOX clutter starts to bother you.
- **`/email-dig <question>`** — corpus queries against `Filed/*` (e.g. "which London companies hired UX in last 6 months"). Add when job-hunting becomes real.
- **MCP migration.** When slash commands arrive, replace the bespoke script with `thegreystone/mcp-email` (after vetting: pin to SHA, fork, lockfile audit, Little Snitch egress allowlist). The MCP earns its keep when there are multiple slash commands sharing IMAP plumbing.
- **Bristlenose aliases.** Add `martin@`/`hello@`/`support@`/`security@bristlenose.app` once they generate any traffic. Currently brand new and clean — trivial triage.
- **Triage-bot forwarding.** Create `triage-bot@bristlenose.app`, set up DreamHost forwards from all five aliases (including cross-domain from cassiocassio), so the MCP only ever holds one scoped credential. Defence-in-depth for when destructive operations (`/email-tidy`'s folder moves) come in.
- **Public repo `claude-inbox-triage`.** Extract `email-catch.py`, the SKILL.md files (when they exist), and `inbox-rules.example.json` to a generic MIT-licensed GitHub repo. Two reference configs: `examples/busy-old-mailbox.example.json` (cassiocassio shape) and `examples/new-clean-mailbox.example.json` (bristlenose shape). Validates the abstraction.
- **2FA audit on accounts using `martin@cassiocassio.co.uk` as recovery email** — PyPI especially. Adjacent hygiene, not specific to this tool.
- **Denylist (`never_flag` rules) built from 3 months of real false positives.** The audit log at `~/.claude/inbox-log/YYYY-MM-DD.jsonl` records every flag set. After ~3 months of v1 use, review which flags you manually unflagged in Mail.app, group by sender pattern, add high-frequency offenders to a new `never_flag` array. ~15 lines of script + JSON changes when the time comes. Evidence-driven, not speculation-driven — same discipline as the must-not-miss rules themselves. Calendar reminder at install + 90 days.

## Out of scope (won't build)

- Reply drafting / sending mail / SMTP — not the problem.
- Real-time IDLE watcher — wrong shape, only useful if always-on.
- `.emlx` direct-read fast path — only if IMAP feels slow.
- iPhone-side automation — Apple Mail picks up flags via IMAP automatically.
- Per-message tier classification (Red/Orange/Noise) — Apple Intelligence's tabs already do this; reinventing is redundant.
- `Filed/*` folder taxonomy — deferred to `/email-tidy` future iteration.
- Auto-delete / `/email-sweep` — bulk deletion stays manual in Mail.app when IMAP performance demands it.
