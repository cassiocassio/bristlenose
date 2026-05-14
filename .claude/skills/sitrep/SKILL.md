---
name: sitrep
description: Situation report — compare planning docs against git delivery over a window, surface lateral wins, and lay out forward candidates respecting dependencies. User picks; skill does not pick.
user-invocable: true
allowed-tools: Bash, Read, Edit, Glob, Grep
---

Two motions in one skill:

1. **Backward truth check** — what shipped vs what the planning docs claim shipped, over a rolling window (default 7 days, configurable: `/sitrep 14` for last 14 days)
2. **Forward candidate ladder** — what's at the top of the Critical Path right now, respecting dependencies, with enough context that the user can mood-pick

The skill **presents**; the user **picks**. After running the skill the user will typically haggle — that's expected and welcome. Don't push hard for one option.

## Phase 1: Read the window

```bash
git log main --since="<N> days ago" --pretty=format:"%h %ad %s" --date=short
```

Default `N=7`. If the user passed an arg (`/sitrep 14`, `/sitrep 30`), use that.

**Branch filter:** restrict to `main` plus any branches listed in the active table of `docs/BRANCHES.md`. Don't use `--all` — it pulls in parked experimental branches (symbology, highlighter, living-fish, drag-push, etc.) whose commits would surface as false lateral wins.

Group the output mentally into:
- **Substantive merges** (`merge <branch>: …`) and the immediately-preceding feature commits — the shipped work. **Substantive = touches `bristlenose/`, `frontend/`, `desktop/`, or ships a new `docs/design-*.md`.** Pure tracker-shuffling (`100days.md` edits, `TODO.md` edits, `BRANCHES.md` updates) is not substantive.
- **Housekeeping** (`add … branch to BRANCHES.md`, `close … branch`, `bump to vX.Y.Z`, `true-the-docs …`, typo fixes) — skip
- **Releases** — note version bumps and roughly what they shipped

## Phase 2: Read the plan docs

**Working-tree check first.** Run `git status --porcelain docs/private/100days.md TODO.md docs/BRANCHES.md docs/private/THIS\ IS\ NEXT.md` before reading. If any of these are dirty, the skill is reading working-tree intent and comparing to committed reality — false stale findings will follow. Flag the dirty files in the preamble so the user knows the audit was against in-flight edits.

**Boundary with `/sync-board`:** sitrep *reads* plan docs vs git; sync-board *writes* GitHub Projects cards from `100days.md`. If both surface the same item it's because both consult the same source — not duplication, just two skills with two motions over one source-of-truth.

Read these in parallel where possible. They're authoritative for different things:

- `docs/private/100days.md` — esp. §Critical Path to Internal TF block + canonical §1–§3 entries (the §1 cluster entries are usually the most current; the Now/Next/Then ladder is the summary)
- `docs/private/THIS IS NEXT.md` — head-of-session pointer (often the most stale file in the tree; trust it least)
- `docs/private/plans/*.md` — chunk decompositions; check the status banner at top if one exists
- `TODO.md` — "Next session focus" + Ideas (Ideas is the antechamber for captured-but-not-triaged design docs)
- `docs/private/road-to-app-store.md` — 14-checkpoint table around line 290 + "Current status summary"
- `.claude/plans/<current-branch>.md` — branch-specific status if you're not on main
- `docs/BRANCHES.md` — currently-open branches (in-flight signal)
- `CHANGELOG.md` — release-level shipped record

**Identify the current sprint.** Parse the Sprint schedule table near the top of `100days.md` (`| Tag | Dates | Theme |`). Use today's date (from the `currentDate` system note) to find the active sprint. If today falls in a gap between sprints, name the most recent and the next. Then collect every `[S<n>]` tag in the document for the current sprint — these are the sprint contents. Track which are struck-through (`~~text~~`) vs open, and which carry ✅ done markers with dates/shas vs no marker.

## Phase 3: Two-pass cross-reference

**Pass A — plan→git (catches stale done markers):**
For each item the plan docs call "in-flight" / "not started" / "promote-next" / "unblocked":
- grep the commit log for the matching merge or feature commit
- if you find it → the plan is stale; note the merge ref
- if you don't → genuinely open, leave alone

**Pass B — git→plan (catches lateral wins):**
For each substantive merge in the window:
- does it appear in *some* plan / tracker / CHANGELOG entry?
- if yes → fine
- if no → lateral win; surface it
- if it's a new `docs/design-*.md` with no implementation tracker → captured-idea-with-no-home; flag for TODO.md Ideas

**Pitfalls to avoid** (provisional — three of four come from one session; revisit after 3 runs and prune the ones that don't recur):
- Treat plan/handoff/coherence docs as **specs, not status**. Their execution-order sections describe how the work was meant to flow, not whether it has flowed. Canonical entries in `100days.md` §1–§3 are usually the most current; prefer them when summary and canonical disagree.
- **Verify any specific file:line claim with grep before recommending a strike.** Sub-agents and audit tools can invert cause/effect (e.g. "Node 24 bump fixed X" when it actually *caused* X). One grep saves an embarrassing wrong-direction edit.
- **Runtime currency tradeoffs:** if a "bug" is "version bump tripped a size/bundle gate by < a few kB", it's not a bug — it's an expected re-baseline. See memory `feedback_runtime_currency_beats_size_headroom`.

## Phase 4: Present the punch list

**Shape: prose bookends, tables in the middle.** Prose carries synthesis (momentum, posture, picking); tables carry state (scannable, stable schema). Output in this order:

### Preamble (prose, 2–4 sentences)
Big-picture read on the window: what changed in posture or momentum, one sentence on overall health, what the gating question has shifted to. Reference the current sprint posture (e.g. "S3 day 3, three musts already shipped"). This is the synthesis layer — what tables can't do. Don't list items here; that's the tables' job. If nothing changed in posture, say so plainly.

### 1. Sprint frame (table)

| Sprint | Dates | Theme | Day | Shipped | Open | At risk |
|---|---|---|---|---|---|---|
| S<n> | DD–DD Mon | one-phrase theme | N of M | comma-list of shipped items (short tags) | comma-list of open items | none / specific risk |

Single row for the current sprint. "Day N of M" is calendar days elapsed / total. "Shipped" counts items that landed in this window *or* earlier in the sprint. Use short tags (A4, B1, "mp Phase 1") not full names — full names go in the contents table.

### 2. Current sprint contents (table)

| Item | Status | Evidence |
|---|---|---|
| canonical item name | ✅ shipped / 🟡 in-flight / ⏳ open / 🔴 at risk / ⏸ deferred | merge sha + date / branch name / blocker |

One row per `[S<current>]`-tagged item in `100days.md`. Pull shipped/deferred markers from strike-throughs and `✅`/`⏸` annotations. Date the shipped items via grep against the commit log.

### Sprint-close projection (prose, 1–2 sentences)
Lands right after the contents table. Answer: *can we close this sprint by the end date?* What would have to ship in the remaining days, the realistic call, what slips if it doesn't all fit. This is where calendar pressure becomes visible.

### 3. Recent ships (table)

| Version | Date | Headline | Reaches users? |
|---|---|---|---|
| X.Y.Z | DD Mon | one-line headline | ✅ PyPI + brew / via X.Y.Z / desktop-only |

Include all version bumps in the window. The "Reaches users?" column catches the case where a source-tree version is ahead of PyPI/brew (e.g. release pipeline broken).

### 4. In-flight branches (table)

| Branch | Kind | Opened | Last activity | Next move | Gate |
|---|---|---|---|---|---|
| `branch-name` | feature/spike/chore | DD Mon | DD Mon or "(no commits)" | one phrase | what it unblocks |

Source: `docs/BRANCHES.md` + `git branch` + recent commit log. Skip `parked` branches unless they moved in the window.

### 5. Forward ladder / haggle list (table)

| Candidate | Sprint | Type | Why now | Blocker | Plan doc |
|---|---|---|---|---|---|
| Name | S3 / — | in-flight / unblocked CP / mechanical / Apple-side parallel / ⏸ capture-only | one-line rationale | none / specific blocker | path |

The "Sprint" column flags whether the candidate is tagged for the current sprint (so the user can see at a glance which picks close the sprint vs which are orthogonal). Use `—` for items with no sprint tag.

Order: in-flight first (top priority by default), then unblocked critical-path, then Apple-side parallel work (doesn't compete for clean-walk state), then ⏸ capture-only stubs.

Hidden: Snap CI (known persistent failure), Won't-100-days, post-alpha icebox.

**Do not rank with a single recommended pick in the table.** That's the recommendation prose block's job, after the tables.

### 6. Open follow-ups (table)

| Item | Class | Where surfaced | Action |
|---|---|---|---|
| description | flake / cosmetic / deferred / parked | PR ref / window | one phrase or "none" |

Source: TODO.md "Next session focus" + the window's commit log. Only items the window confirms are still open (no fix merged).

### Stale-done findings (table, only when non-empty)

| File | Current claim | Truth | Edit | Bucket |
|---|---|---|---|---|
| path:section | one line | one line + sha | proposed strike | load-bearing / cosmetic |

Omit the whole section if Pass A found nothing — common after a `/true-the-docs` sweep.

### Captured ideas without a home (bullets, only when non-empty)
Design docs (`docs/design-*.md`) created in the window with no implementation entry. Most-at-risk-of-being-lost — propose adding to `TODO.md` Ideas. Omit when empty.

### Recommendation (prose, 2–4 sentences)
Top pick + the main tradeoff vs the runner-up. Optionally one "if you only do one small thing" minimal-effort fallback. Note whether the top pick closes a sprint item or is orthogonal — both can be the right call, but make the tradeoff visible. This is where the skill picks *with eyes open*, having presented the unranked grid above. The user can still haggle — that's expected.

### Suggestions (bullet list, 2–5 items)
Lateral observations the user can ignore or pluck:
- Doc edits offered (`THIS IS NEXT.md` header refresh, lateral-wins block, stale-done strikes)
- Things worth flagging for the next window (half-life concerns, parked-too-long branches)
- **Sprint-slip candidates** — if the close-projection says not everything fits, propose what should slip to S<n+1> or beta-Must
- Chip candidates if any surfaced during the audit

Keep tight: bullets, one line each.

## Phase 5: Offer edits

After presenting, ask the user which stale-done / cosmetic / lateral-win findings they want applied. Common edits:

- Strike-through with `~~text~~` + `✅ shipped <date> (`<sha>`)` for shipped items
- Status banner at top of plan docs that lack one
- New entries in `TODO.md` Ideas for orphaned design docs
- Lateral-wins block in `100days.md` (between §Critical Path and §quality reset) if not already present
- Refresh `THIS IS NEXT.md` head + suggested-next-move block

Do **not** apply edits without confirmation. Some "stale" claims are intentional historical record (e.g. dated execution-order sections in plan docs); the user knows which.

## Length budget

The full output should fit in one screen. Tables are the centre of gravity; **preamble + recommendation + suggestions ≤ 200 words combined**. If a prose section bloats, it's a sign the content belongs in a chip or a separate doc, not the sitrep. If a table row needs more than one line per cell, the cell is doing too much — split the row or trim.

## Worked example (14 May 2026)

The skill was scaffolded after a session that surfaced:
- 2 stale done markers (A2, A4 marked in-flight, shipped 12 May)
- 8 lateral wins (CLI just-works preflight, pipeline diagnostic popover infrastructure, generic-failure-surface, SPA trust-UX, session-handoff-sentinels, ci-version-pinning, James Bach agent, true-the-docs v2)
- 4 captured design docs with no home (incremental-analysis, ASR backend strategy, native-vs-web surfaces, cli-analysis-register)
- 1 inverted audit claim (sub-agent said Node 24 bump *fixed* size-limit; actually *caused* it — caught by grep before edit)

That session is the canonical reference for what "good" looks like.
