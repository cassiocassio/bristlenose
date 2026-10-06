---
status: parked
last-trued: 2026-10-06
---

# The CLI welcome, built on the Mac Welcome

**The question this answers:** how much of a CLI-context welcome do we get for
free by building on the Mac app's Welcome pane, rather than writing a new page?

**The short answer: most of it.** Eleven of the thirteen illustrations already
have a web form in this repo. All 138 caption strings are localised across 21
locales and are addressed by *key*, not by string. Every CTA already points at
`bristlenose.app/docs/`. And the expensive half of the Mac work — the ~80
English strings baked into the illustrations, inventoried in
`design-welcome-illustrations-i18n.md` as "the higher-value half" — **is not
needed at all here**, because that doc's own premise is that the docs site is
English and stays English. The blocker for the Mac is a non-issue on the web.

This doc is a reuse register, not a plan. It exists so the two surfaces can be
kept in sync deliberately rather than drifting into two unrelated welcomes.

---

## Status — parked 6 Oct 2026, by the owner

**No page was written, and that was the finding, not an omission.** The brief
this came from scoped a four-section page; of those sections, 1 (what you're
looking at), 1b (Signals), 2 (shortcuts) and 4 (the app) are already live,
actively-maintained pages on the docs site — `how-it-works`, `signals`,
`keyboard-shortcuts`, `install` — and `signals.md` is tighter than the orphaned
`help.signals.*` corpus it would have been harvested from. The `welcome` slug is
taken by the alpha-tester onboarding page. Writing the page as scoped would have
duplicated most of a curated Diátaxis tree and given the sentiment taxonomy, the
metrics and the install claim each a second home.

**The genuine gap was the entry point, not the prose:** `?` opens the
keyboard-shortcuts reference and Help opens the docs index, so nothing greets
someone who has just run `bristlenose serve` from a terminal. That gap, and this
register's reuse buckets, are what a future session should pick up.

**Closed since this was written:** the 130 orphaned `help.*` keys are gone —
deleted in `1ff44e60` ("delete the help block: 2,794 translated values for a
modal retired in July"), which was this register's largest open item.

**Still open, each independent and none blocking the others:**

| Item | Where |
|---|---|
| `?` opens the shortcuts reference, not a front door | `frontend/src/layouts/AppLayout.tsx:177` |
| `DEFAULT_HELP_URL` defined and never put in the payload | `bristlenose/server/routes/health.py:19` |
| Man page SEE ALSO points at the GitHub repo, not the docs site | `bristlenose/data/bristlenose.1:750` |
| Typer app has no `epilog`, so `--help` carries no docs pointer | `bristlenose/cli.py` |
| No telemetry paragraph on either privacy page | website repo: `docs-src/privacy.md`, `content/privacy.html` |
| The accepted export gap is unrecorded | `docs/design-export-html.md` |

**Before taking the `?` row, read the website keyboard-shortcuts item in the
maintainer's private planning notes, kept outside the public tree.** It already
owns that page, records that `?` opens it on **both** channels, and carries an
outstanding correctness fix: the page advertises `j` / `↓` as equivalent, which
stopped being true when the arrows became geometric while `j`/`k` stayed
reading-order. Repointing `?` and fixing what it opens are one piece of work, not
two — and the page lives in the website repo, so it cannot be fixed from here.

The telemetry one is the only one with a clock on it. Both privacy pages make an
absolute claim — *"no usage tracking"*, and what leaves the machine *"only in
these cases"* — which is **true today**: `BRISTLENOSE_TELEMETRY_ENABLED` defaults
`True` and the endpoint ships in the `/api/health` payload, but nothing sends
anything (verified 21 Sep 2026: `DEFAULT_TELEMETRY_URL` appears only in its own
default literal in `frontend/src/utils/health.ts`, no `fetch`, nothing in Swift or
Python). Telemetry Phase 2 would make that sentence false silently, on a page in
another repo that nobody editing a sender would think to open.

**Two truing notes for whoever reads the table in §1a next:**

- **`WelcomeIllustrationHTML` now holds 11 `static func`s, and that is not
  drift.** Two of them — `curtain` and `stringsBlock` — are shared helpers, not
  illustrations; `WelcomeIllustration` still has the same 13 cases, so `ingest`
  and `clips` are still the only pair with no web ancestor. Count the enum, not
  the builders.
- **The Mac Welcome became its own window on 3 Oct 2026** (Model 2 —
  `design-welcome-screen.md`, commits `e9e1d5f6` → `79a7ee2b`). That does not
  move anything between the buckets below: the φ-spiral geometry was already in
  §3 *Drop*, and the reusable assets are the content pools and the illustrations,
  which the window change did not touch.

---

---

## 1. Free — reuse as-is

### 1a. The illustrations: 11 of 13 have a web form

The webview illustrations are self-contained HTML strings returned by
`WelcomeIllustrationHTML` (`WelcomeIllustrations.swift:795`), rendered through a
transparent `WKWebView` that loads with `baseURL: nil` and pulls **no external
resources**. They already inline the shipped report CSS (`badge.css`,
`blockquote.css`) — and the comment at `AutoCodeIllustrationView:398` records
that this is *why* report-chrome illustrations are webviews and not native
rebuilds: so they re-sync when the report styling changes. That reasoning
transfers to a docs page unchanged.

| Illustration | Form in the app | Web original | Cost |
|---|---|---|---|
| `quote` | HTML | — | free |
| `signal` | HTML | — | free |
| `emergentThemes` | HTML | — | free |
| `autocode` | HTML | `welcome-studytools-animations.html` §1 | free |
| `manualTags` | HTML | `welcome-studytools-animations.html` §2 | free |
| `tag` | HTML | `welcome-studytools-animations.html` §3 | free |
| `starHide` | HTML | `welcome-studytools-animations.html` §4 | free |
| `agentChat` | HTML | — | free |
| `miro` | HTML | — | free |
| `sentimentFan` | **native SwiftUI** | `welcome-science-animations.html` §1 (`class="fan"`) | recover the web original |
| `books` (`BookShelfView`) | **native SwiftUI** | `welcome-science-animations.html` §4 (`class="shelf"`) | recover the web original |
| `ingest` | **native SwiftUI** | none | author, or drop |
| `clips` | **native SwiftUI** | none | author, or drop |

Only `ingest` and `clips` were authored native-first (14 Aug 2026, converting
the last PNG screenshots). Everything else either is HTML today or was ported
*from* HTML that is still in the tree.

### 1b. The prose: 138 keys, 21 locales, green

`desktop.welcome.home.*` carries 138 keys in `en` — 135 renderable plus three
English-only editorial notes (`_divergent_*`, `_comment`), which
`check-locales.py` drops by design (`PSEUDO_KEY_PREFIXES`, line 80). Each of the
other 20 full locales carries all 135; `zh-Hant-HK` carries 4 genuine overrides
and inherits the rest. `check-locales.py` is green.

| Group | Keys | Words |
|---|---|---|
| `tips` | 75 | ~574 |
| `tools` | 31 | ~266 |
| `science` | 8 | ~73 |
| `aiConfigured` | 6 | ~38 |
| `tags` | 5 | ~66 |
| `ingestRows` | 5 | ~56 |
| `books` | 4 | ~51 |
| chrome (`learnMore`, `more`, `rotatorPosition`, `clipsIllustration`) | 4 | ~10 |

Two properties make this portable rather than merely present:

- **Slots carry a key, not a string** (`SlotItem.key`, resolved by
  `resolve(_:_:)` at render), so a web surface reorders or subsets the pools at
  no translation cost.
- **Every `href` already points at `bristlenose.app/docs/`**
  (`WelcomeContent.docs`, `WelcomeHomeView.swift:108`). There is nothing to
  re-point — the Mac Welcome is *already* a docs-linking surface.

### 1c. `tools.redactPii` — content the CLI gets that the Mac cannot show

The one slot withheld from the desktop pool
(`WelcomeHomeView.swift:128–139`, commented out). The withholding is real and
current, for one reason: `piiEnabled` has no **writing** call site, so there is
no Privacy control and redaction stays CLI-only (`--redact-pii`). Presidio and
spaCy have been bundled since 12 Sep 2026, so the capability is in the binary;
it is the UI that is missing.

Its strings — `title`, `text`, `link` — are **translated and waiting in all 21
locales**. A CLI welcome restores the slot at zero cost, and is the only surface
that can honestly show it.

### 1d. A prior web port already exists

`docs/mockups/website-bento-welcome.html` ports the Welcome content into a web
bento and tags every cell with its provenance (`data-src`): **20 cells from the
Welcome, 10 merged, 6 site-only** — bands A (tools), B (science), C (tips),
mirroring the Welcome's own structure. It is framed as a marketing homepage
rather than a CLI welcome, but the content mapping is done and the ratio is the
evidence for "most of it".

---

## 2. Adapt — small, bounded work

- **Un-bake the HTML template parameters.** The illustration strings are Swift
  string-interpolated on `dark:`, `palette:` and `reduce:`
  (`\(dark ? "dark" : "light")`). On the web these become
  `prefers-color-scheme` / `prefers-reduced-motion` media queries and a palette
  class. This is the one genuine engineering cost, and it is mechanical.
- **Add back the two CLI-only tips.** The Mac pool deliberately skips
  `/docs/cli.html` and `/docs/redact-pii.html` as CLI-only
  (`design-welcome-screen.md` §Cell 3). Both are core for a CLI reader.
- **`tools.agent` needs its fallback.** Its primary CTA is a native destination
  (`primaryDestination: .mcpAgentsSettings`, `href: ""`) because the first step
  is setup in a Settings pane that does not exist off the Mac. `href2` already
  holds `/docs/connect-an-agent.html` — promote it.
- **Author or drop `ingest` and `clips`.** The only two illustrations with no
  web ancestor.

---

## 3. Drop — Mac-only by construction

- **The φ-spiral geometry** (`GoldenSplit`, `welcomeCell`, the 0.618 framing).
  It is explicitly *fixed architecture that does not reflow*
  (`design-welcome-screen.md` §2) and is tuned to a Mac window. A docs page is a
  scrolling column at arbitrary width; the constraint that makes the spiral good
  is absent.
- **`WelcomeClauseFit`.** Clause-cutting exists because the cells cannot
  reflow. CSS reflow does this job natively.
- **`WelcomeBaton` / `WelcomeTempo`.** Baton-passing so only one cell animates
  at a time, with a 0.6 speed and 3-second rests. A page can scope animation to
  the viewport instead.
- **`SlotRotator` per-visit rotation.** Rotation earns its keep on a surface
  seen daily at a fixed size. A docs page is arrived at deliberately and can
  show the set.
- **Three Mac-only tips:** `import-recordings`, `recording-permissions`,
  `windows` — all macOS-app features.

---

## 4. Keeping the two in sync

The pools are the shared asset; the layouts are not. Sync discipline:

- **The pools stay single-source in `WelcomeContent`** (`WelcomeHomeView.swift`)
  and `desktop.welcome.home.*`. A web surface subsets them; it does not fork
  them. A second copy of the tips list is a second list to true.
- **Tip order mirrors the website NAV** (`build.py` `NAV` → `ORDER`) — already
  the stated rule, and it is what lets both surfaces walk the same curriculum.
- **An illustration that reproduces report chrome stays a webview**, for the
  reason already recorded at `AutoCodeIllustrationView:398`: it re-syncs with
  the shipped CSS. Porting one to native on either surface breaks that.

---

## 5. Found on the way — a gap in the Mac tips pool

The tips pool covers 24 of the 37 NAV pages. Nine of the thirteen absences are
covered by a documented rule (four pure-chrome pages; three provider pages
collapsed into Claude + Ollama; two CLI-only). **Four are not:**

- `import-recordings`, `recording-permissions`, `windows` — macOS-app features
  with no tip, on the macOS surface. Arguably the Mac pool's own gap.
- `read-transcripts` — cross-platform, and covered by neither rule nor tip.

Not blocking anything here; recorded because the audit surfaced it.
