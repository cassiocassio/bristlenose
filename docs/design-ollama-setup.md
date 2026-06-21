---
status: implemented
last-trued: 2026-06-04
trued-against: beat3-provider-activation @ implemented + QA-verified (ea4c2e5, 065698a; 4 Jun 2026)
---

# Design: Ollama setup flow (first-run on-device AI)

_3 Jun 2026 — functional + UX spec. Supersedes the silent browser-open + blind
120s daemon-spin in the original `OllamaSetupSheet` / `OllamaDownloadModel`
flow (review-log Finding 3, branch `beat3-provider-activation`)._

> **Status (`implemented`):** Shipped on `beat3-provider-activation` (`ea4c2e5`
> flow-B pill + popovers; `065698a` menu-bar Debug state harness) and walked
> through every state in a screenshot QA pass (4 Jun 2026). The silent-open +
> blind-120s behaviour this doc removes is gone. **This doc is the canonical
> spec** (the implementation map is §16); the earlier terse plan
> (`.claude/plans/archive/finding-3-ollama-setup.md`) is superseded and archived.
> Model catalogue + RAM recommendation logic lives in
> `docs/design-gemma4-local-models.md` and is referenced, not redefined, here.
>
> **Flow shape: model-first ("Ollama incidental").** The user chooses a model
> *first*; the Ollama dependency is revealed only if the daemon is down (§5/§6).
> Copy is frozen against the medium-fidelity mock
> `docs/mockups/ollama-setup-popovers.html` — strings here are quoted verbatim
> from it. The mock is the layout + copy contract; this doc is the structure +
> rationale; the locale `desktop.json` files hold the runtime strings.

---

## 1. Summary

When a first-run user chooses to keep analysis **on-device**, Bristlenose needs
the [Ollama](https://ollama.com) runtime present and a suitable model pulled.
Ollama is a third-party app we **do not bundle** — the user installs it
themselves from ollama.com, and the model weights (2–20 GB) are fetched by
Ollama's own daemon.

This doc specifies the flow, the state machine, and the two surfaces it drives
(the toolbar **pill** and its **popover**), built on a single hard constraint:
**Bristlenose can observe exactly one thing — whether the local Ollama daemon
is reachable.** Everything the user sees is built honestly on that one bit.

## 2. The problem being replaced

The current `OllamaDownloadModel.run(tag:)` does two user-hostile things:

1. **Silent browser-open.** If the daemon is unreachable it calls
   `NSWorkspace.shared.open("https://ollama.com/download")` with no consent and
   no in-app acknowledgement — a Safari tab just appears.
2. **Blind 120s spin → false failure.** It then `waitForDaemon(timeout: 120)`.
   Installing Ollama (a few-hundred-MB download + drag-to-Applications + launch)
   routinely takes longer than two minutes, so the normal case trips the
   timeout and is classified as `.runtimeDidNotStart` — surfaced as a **red
   error** for something that isn't an error.

Both stem from the same mistake: pretending Bristlenose has more visibility and
agency than it does.

## 3. Core principle — one observable bit

Bristlenose's entire observable surface is a single polled boolean:

> Is `GET http://127.0.0.1:11434/api/tags` reachable?

It flips `false → true` at exactly one moment: when Ollama is **both installed
AND running** (the menu-bar app with its daemon up). We **cannot** see:

- the browser, the download, the `.dmg` mount, the drag to Applications;
- whether the user launched Ollama after dragging it (the **installed ≠ running**
  gap — a dragged-but-never-opened Ollama reads as unreachable);
- anything happening in Safari after `NSWorkspace.open` hands off (one-way).

Two consequences drive the whole design:

- **Animation is a truth signal.** A moving progress indicator is a promise that
  *Bristlenose is doing work*. While we wait for the human to install/launch
  Ollama, Bristlenose is doing nothing but polling a port — so that state shows a
  **static** indicator, never a spinner. Motion appears only when Bristlenose is
  actually streaming model bytes.
- **Copy must say _launch_, not just _install_.** Because installed-but-not-running
  is invisible to us and common, the guidance tells the user to open/launch
  Ollama, not merely install it.

## 3a. Why the model choice is deliberate, not a silent auto-pull

An earlier draft tried to be helpful by auto-pulling the RAM-aware default the
moment the daemon came up — zero choice, "just works." **That instinct is wrong
for a multi-gigabyte commitment**, and being wrong here is _unhelpfully_ helpful.

**The download is an emotional commitment, not a logical one.** Even on a 1 Gbit
fibre line in central London you'd think twice before kicking off a multi-GB
fetch — it's not about whether you _can_, it's about whether you want to spend
the data, the disk, and the wait right now. The PlayStation analogy is exact:
you start a top-tier game download, you can't play until it's done, and you go do
something else while it grinds. Pretending a multi-GB model is a frictionless
background detail disrespects that.

**The numbers say none of the options are small** (full data in §Appendix A):

- A 3 GB default is ~1–4 min on median fixed broadband across our markets, but
  ~16 min on a 25 Mbps line (rural, hotel Wi-Fi, congested evening, tether) —
  and half of every market is below median.
- The _good_ models — the ones a capable Mac actually wants — are 16–20 GB:
  20–26 min even on a fast line, **over an hour and a half** on a slow one.
- Disk is arguably the harder limit: base Macs still ship 256 GB, and after
  macOS + apps + photos many users sit under 50 GB free. A 20 GB model is a
  quarter of their headroom; even 3 GB matters on a near-full drive.

**So step 1 (the model picker) is the tradeoff-and-education surface, by design.**
It exists to:

- show the size ⇄ quality tradeoff, scoped to _this Mac's_ RAM;
- tell the honest truth that **none of the options are small**, and set
  expectations about disk before the commitment;
- carry the **foreshadow** of the Ollama dependency (daemon-down) so step 2's
  reveal isn't a surprise.

**First-run-local is often an education pathway that does not succeed on the
first sitting** — and the design accepts this rather than fighting it. Many users
who pick "I'll do it locally" will, once they see the real size, **defer**:
explore with a Claude key + test data now, and come back to Ollama later when
they have the bandwidth, disk, and an evening. That deferral is a **first-class,
respected outcome** (see §7.4), not a funnel failure to paper over.

This is why the flow is **model-first** (§5): the **choice** comes _first_ —
before Ollama is even mentioned — because choosing needs no daemon (it's catalogue
data + a deferred fetch). The Ollama dependency is revealed only _after_ the
choice, and only when the daemon is down. The choice is decoupled from the
**fetch**, which waits for the daemon. The persuasive risk of leading with the
reward then revealing the cost is defused by the foreshadow line (§9.1, §15).

## 4. The signal: `daemonSnapshot()`

`GET /api/tags` returns reachability **and** the installed-model list in one
round-trip. The current `isDaemonReachable()` checks only the status code and
discards the body. It is replaced by:

```swift
struct InstalledModel { let name: String; let sizeBytes: Int64 }
func daemonSnapshot() async -> [InstalledModel]?   // nil = unreachable
```

- `nil` → daemon down → Ollama not running.
- `[]` → daemon up, no models pulled yet.
- `[…]` → daemon up, these models already on disk.

**Curated-only use.** We use the parsed list solely to cross-reference our
*curated* catalogue — marking which curated models are already on disk (the
skip-the-download win). We deliberately do **not** enumerate non-curated models
the user pulled themselves (a power user could have a whole arbitrary universe);
surfacing that "bring your own model" library is a later slice (§15). Parsing the
list now (rather than a bare bool) is the foundation for that, and avoids a second
round-trip. Endpoint is hard-pinned to `127.0.0.1` (security finding 12).

## 5. State machine

```swift
enum Phase: Equatable {
    case idle
    case choosingModel        // step 1 — pick the model FIRST (model-first); needs no daemon
    case needsOllama          // step 2 — model chosen, daemon down → go get Ollama
    case waitingForOllama     // step 3 — Ollama opening; polling — PASSIVE (human installing)
    case downloading          // daemon up; fetching the chosen model — Bristlenose working
    case finishing
    case failed(Failure)
}
```

Removed from the current enum: `.installing`, `.starting` (dishonest
"we-opened-a-browser-and-are-spinning" pair), and `Failure.runtimeDidNotStart`
(daemon-not-up is no longer a failure). The `DaemonTimeout` struct and its
`classify` mapping are deleted.

**Model-first ("Ollama incidental").** The conceptual sequence is **1 → 2 → 3**:
_which model?_ → _(if needed) get Ollama_ → _now we wait_. The user's actual goal
is "pick an on-device model"; Ollama is plumbing, surfaced only as an exception
when the daemon is down. So `choosingModel` is the **universal first act**;
`needsOllama` + `waitingForOllama` are a downstream branch only the fresh-Mac user
ever sees. The model **choice** (1) is decoupled from the model **fetch** — the
user commits to a model before Ollama even exists; the daemon acts on that
committed choice once it comes up. See §3a for why the choice leads and is a
required, deliberate step rather than a silent auto-pull.

| Phase | Who is working | Entered when | Pill label | Pill accessory |
|---|---|---|---|---|
| `idle` | — | nothing in flight / Cancel pressed | hidden | — |
| `choosingModel` | the human | activation (always — model-first) | "Set up on-device AI" | static glyph |
| `needsOllama` | the human (about to) | model chosen, daemon down | "Get Ollama" | static glyph |
| `waitingForOllama` | the human | user clicked **Get Ollama…** | "Waiting for Ollama" | **static hourglass**, dimmed |
| `downloading` | Bristlenose | daemon reachable + model absent | "Downloading {model}" | **animated** bar + % (or spinner if totals unknown) |
| `finishing` | Bristlenose | fetch completed | "Finishing up" | spinner |
| `failed(_)` | — | fetch errored (not daemon-absence) | "Couldn't get model" | none (red icon) |

**Transitions:**

```
activation ──► daemonSnapshot()  ──►  choosingModel            (ALWAYS — model-first)
                                          │
                       user confirms "Use {model}"
                                          │
   daemon was nil ──► needsOllama ──(Get Ollama…)──► waitingForOllama ──(daemon up)──► downloading
   daemon up, model absent ─────────────────────────────────────────────────────────► downloading
   daemon up, model present ───────────────────────────────────────────────────────► active (no fetch)
waitingForOllama ──(daemon up)──► downloading ──► finishing ──► idle
waitingForOllama ──(Cancel)──► idle (pill hides; provider choice retained — §7.4)
waitingForOllama ──(click-away/Esc)──► popover hides, poll CONTINUES, chip stays
downloading/finishing ──(Cancel)──► idle
failed ──(Retry)──► downloading
```

There is **no give-up timer**. `waitingForOllama` is passive and honest, so it
persists until one real event: the daemon appears, the user presses Cancel, or
the user switches provider. No deadline, no auto-revert, no fake urgency.

## 6. Activation decision tree

On first-run consent the user picks "keep on-device" (`activateLocalDefault()`
in `AIConsentView.swift`): provider set to `local`, RAM-aware default tag chosen
via `OllamaCatalog.recommendedTag()`, consent recorded, `.bristlenosePrefsChanged`
posted, sheet dismissed, `start(tag:)` called. `start` then routes **always to
the model picker first** (model-first):

```
start(tag:) ──► choosingModel           (ALWAYS — pick/confirm the model)
                   │
        user confirms "Use {model}" ; snapshot = daemonSnapshot()
                   ├─ nil                       → needsOllama  (fresh Mac — §7.1)
                   ├─ non-nil, model absent     → downloading  (§7.3)
                   └─ non-nil, model present    → active, no fetch (§7.2)
```

**Choice rule:** the model choice (step 1) is **always shown**, because choosing
is catalogue data + a deferred fetch — it needs no running daemon. The default
(`OllamaCatalog.recommendedTag()`) is **pre-selected** so the considered path is
one click, but it is shown and changeable, not silently auto-pulled. What the
daemon changes is only what the picker can _annotate_:

- **daemon down** → curated, RAM-fit catalogue only, plus the foreshadow line
  ("These run on Ollama…");
- **daemon up** → curated models already installed are marked "ready · no
  download" (an "Already on this Mac" group), and a chosen model that's already
  present skips the fetch entirely.

The richer "bring your own arbitrary model" picker is a later slice; this doc
requires only the curated choice + pre-selection + installed-marking now.

## 7. Flow sequences

### 7.1 Fresh Mac — happy path (primary)

No Ollama installed; everything goes right.

| # | Step | Surface | Computer (state + text) | Human |
|---|---|---|---|---|
| 1 | — | Consent sheet | "Choose how Bristlenose analyses your interviews." On-device option | Clicks **Use Ollama** |
| 2 | — | (transition) | `activateLocalDefault()` → `choosingModel`; sheet dismisses | — |
| 3 | **1** | Pill + popover (auto-presents once) | Pill "Set up on-device AI". Popover §9.1: *Choose your on-device model* — RAM-fit rows, none small, foreshadow "These run on Ollama…" | Picks a model, clicks **Use {model}** |
| 4 | **2** | Pill + popover | `daemonSnapshot()` = nil → `needsOllama`. Pill "Get Ollama". Popover §9.2: *Get Ollama to run {model}* | Clicks **Get Ollama…** |
| 5 | — | Browser opens | `getOllama()` opens ollama.com → `waitingForOllama` | (in browser: download → install → launch Ollama) |
| 6 | **3** | Pill + popover | Pill "Waiting for Ollama" (static ⌛). Popover §9.3: numbered steps; *Bristlenose will download {model} automatically…* | **launches Ollama** |
| 7 | — | (poll, 2s) | `daemonSnapshot()` non-nil → `run(tag:)` → `downloading` | (waits, can keep working) |
| 8 | — | Pill | "Downloading Gemma 4 E4B" + **animated** bar + % | (waits) |
| 9 | — | Pill | "Finishing up" spinner → `idle` → pill self-hides | — |
| 10 | — | Report | On-device model active; analysis runs | Uses Bristlenose |

Two honesty lines: the **commitment** is made deliberately at step 1 (sizes and
tradeoffs shown, not hidden); and the **animation** is static (hourglass) while
the _human_ works (steps 1–3) and only moves once _Bristlenose_ streams bytes
(step 8).

### 7.2 Ollama already installed, model already present

`daemonSnapshot()` non-nil and the chosen model in the list. The user still sees
step 1 (`choosingModel`), but the model shows in the "Already on this Mac" group,
pre-selected. Confirming it → instant active, no fetch, no pill. The fastest path,
but still a deliberate confirmation, not a silent skip. No `needsOllama`, no
`waitingForOllama`.

### 7.3 Ollama installed, model absent

`daemonSnapshot()` non-nil but the chosen tag missing → after confirm, **skip
`needsOllama` and `waitingForOllama`** (daemon's already up) → straight to
`downloading`. No browser-open.

### 7.4 User cancels the wait

In `waitingForOllama`, the popover's `[Cancel]` → stop polling, `phase = .idle`,
**pill hides entirely**. This is distinct from click-away/Esc, which only hides
the popover and keeps the chip + poll alive.

**What Cancel actually means: "not now."** The user has decided that waiting for
a multi-GB install + pull isn't worth it _right now_ — they have a meeting in 15
minutes, on-device is a bigger task than they have time for. Critically, they are
**not blocked from the app** — they have a fully working Bristlenose instance to
explore (browse the UI, look at sample data, understand what it does). Cancel
removes the setup pressure, not the app.

**Re-entry is failure-driven, not a nag.** We do **not** chase them with a
persistent chip, a modal, or a Settings breadcrumb they must hunt for. Instead,
the app's own structure surfaces the need at the exact moment it becomes real:
the first time they try to **analyse a real project**, there is no working
backend, so that attempt fails and routes them to **provider choice** (§11).
There they may re-pick on-device (now that they have time), or — just as likely —
choose a cloud provider and paste a key because the meeting is looming. The
choice that was deferred re-presents itself naturally, driven by intent, not by
attention-theft. (Consistent with: absence is information; no toasts; the sidebar
is an attention surface, not an affordance switchboard.) **This routing does not
exist today** — it's a net-new dependency this design leans on (Finding 20 / §15).

### 7.5 User never launches Ollama

`waitingForOllama` persists indefinitely as a passive, static chip. No timeout,
no error. The user resumes whenever they finally launch Ollama, or dismisses via
Cancel.

### 7.6 Pull fails

A genuine pull error (network drop mid-download, disk full, daemon crash) →
`failed(Failure)`. Pill shows the red ✗ icon; popover shows the typed reason +
**[ Retry ]** (§9.5). Daemon-absence is **not** a failure and never reaches this
state.

## 8. Surface: the toolbar pill

Lives at `placement: .status` (per `desktop/CLAUDE.md`). Self-hides when `idle`.
Uses a Capsule + secondary-stroke envelope. (It originally mirrored the toolbar
`CopyProgressPill`; that pill was deleted 19 Jun 2026 when copy progress moved onto
the project row, so `OllamaDownloadPill` is now the sole toolbar pill.) The pill is
the **only** persistent control; clicking
it opens the phase-appropriate popover. No inline buttons on the pill itself.

| Phase | Icon | Label | Accessory |
|---|---|---|---|
| `choosingModel` | `hourglass` (.secondary) | "Set up on-device AI" | none |
| `needsOllama` | `hourglass` (.secondary) | "Get Ollama" | none |
| `waitingForOllama` | `hourglass` (.secondary) | "Waiting for Ollama" | none (static) |
| `downloading` (totals known) | `arrow.down.circle` (.secondary) | "Downloading {model}" | linear bar + % (animated) |
| `downloading`/`finishing` (totals unknown) | `arrow.down.circle` | "Downloading…" / "Finishing up" | `ProgressView()` spinner |
| `failed` | `xmark.circle.fill` (.red) | "Couldn't get model" | none |

**Colour discipline:** red is reserved for genuine failure (`failed`). All setup
states stay neutral (`.secondary`). VoiceOver: label = phase status; value =
download % only during a determinate pull.

## 9. Surface: the popovers

Standard popovers 280pt; the model picker is 360pt. Anchored to the pill
(`arrowEdge: .bottom`). Action buttons are **trailing** (bottom-right), default
rightmost, Cancel to its left — macOS convention, matching the existing
`OllamaDownloadPill` (`HStack { Spacer(); Button }`). No centered buttons.

### 9.1 `choosingModel` — "Choose your on-device model" (step 1)

The tradeoff-and-education surface (§3a), and the warm, model-first open. 360pt to
carry the rows. **Daemon-down** variant:

```
   Choose your on-device model

   Tuned to your Mac (16 GB RAM). Bigger models are smarter but
   need more memory; all are a sizeable download.

   ┌─────────────────────────────────────────────────────┐
   │ ◉  Gemma 4 E4B        · balanced · recommended       │
   │    ~3 GB download                                    │
   ├─────────────────────────────────────────────────────┤
   │ ○  Llama 3.2 3B       · smallest · fastest           │
   │    ~2 GB download                                    │
   ├─────────────────────────────────────────────────────┤
   │ ⊘  Gemma 4 26B        · best quality · needs 24 GB   │   ← disabled; "needs 24 GB" in red
   │    ~16 GB download                                   │
   └─────────────────────────────────────────────────────┘

   ⚠ Low disk space                                          ← red, only when disk < threshold

   These run on Ollama, free software you'll set up next.    ← foreshadow (daemon-down only)

                                  [ Use Gemma 4 E4B ]
```

**Daemon-up** variant — same four curated rows, same order, grouped by install state:

```
   Choose your on-device model

   Tuned to your Mac (16 GB RAM). One model is already on this Mac.

   ── Already on this Mac ───────────────────────────────
   │ ◉  Gemma 4 E4B        · ready · no download          │
   │    3.0 GB on disk                                    │
   ── Download ──────────────────────────────────────────
   │ ○  Llama 3.2 3B       · smallest · fastest           │
   │    ~2 GB download                                    │
   │ ⊘  Gemma 4 26B        · best quality · needs 24 GB   │
   │    ~16 GB download                                   │

                                  [ Use Gemma 4 E4B ]
   Already installed — starts right away.
```

- **Default pre-selected** (RAM-aware `recommendedTag()`); the considered path is
  one click, but the alternatives, their sizes, and the honest "none are small"
  framing are present — a deliberate commitment, not a silent pull.
- **One size per row, framed by cost:** not-installed → `~N GB download`;
  installed → `N GB on disk`. Never both — for Ollama, download ≈ on-disk (no
  expansion), so showing both is the same number twice. Quality is carried by the
  descriptor words, never by size.
- **Over-RAM models are disabled** (unselectable), with the RAM reason in **red**
  (no ⚠ glyph on the row — the disabled state is the signal). Ollama *can*
  technically run them by swapping, so the framing is "needs N GB", not "can't run".
- **Low disk space** — a single red ⚠-triangle line, shown only when free disk is
  below threshold (trigger basis: §15 / Finding 19). Advisory; does not block the
  button. The OS/Ollama reports an actual out-of-space failure post-download — we
  do **not** model `diskFull` as a typed failure.
- **Foreshadow line** (daemon-down only): names Ollama *before* step 2 reveals the
  dependency, so the reveal isn't a bait-and-switch (§3a, §15 / Finding 17).
- **No help links** — removed until real manual anchors exist; revisit when there's
  a page to point at.
- **No time estimates** — we don't know the user's connection at choice time, so
  per-row "~N min" guesses are removed; size only (§15).
- **Verb "Use {model}"** — the user chooses; Ollama fetches (§10).
- On confirm: → `needsOllama` (daemon down), `downloading` (daemon up, absent), or
  instant-active (daemon up, present).

### 9.2 `needsOllama` — "Get Ollama to run {model}" (step 2)

The "ah, but" reveal, softened because foreshadowed at step 1. 280pt.

```
   Get Ollama to run Gemma 4 E4B

   Bristlenose runs models locally through Ollama — free. Opens
   ollama.com to download and install it.

                                  [ Get Ollama… ]
```

- **Title names the chosen model** — the dependency is framed as "the one step
  between you and *your* model" (endowment), not a generic chore.
- Body folds the old "opens in your browser" caption into one honest sentence
  ("download **and install** it" — it's a `.dmg`, there's a real install step).
- **"Get Ollama…"** (ellipsis = opens an external destination). Names the action;
  doesn't over-promise "Install" (we can't install for them).
- Clicking → `getOllama()` opens ollama.com → `waitingForOllama`.

### 9.3 `waitingForOllama` — "Finish installing Ollama" (step 3)

```
   Finish installing Ollama

   ollama.com is open in your browser.        ← "ollama.com" is a link (reopen if closed)

     1.  Download Ollama for macOS
     2.  Open the download, install and launch Ollama

   Bristlenose will download Gemma 4 E4B automatically once Ollama
   is running.

   ⌛ Waiting for Ollama install                          [ Cancel ]
```

- **`ollama.com` is a link** in the body — a user who closed the tab by accident
  can click to reopen (this replaces the separate "Open again" affordance, cut as
  fluff).
- The footnote names the **chosen** model — the commitment was already made at
  step 1; the fetch is the honest delivery of that choice. ("download", not
  "install" — install is Ollama-the-app, download is the model.)
- **`[Cancel]` is licensed by the adjacent label.** A lone Cancel is orphaned;
  here "Waiting for Ollama install" supplies the object, so Cancel reads as
  "cancel _that_" — the standard macOS progress-row idiom. Behaviour: §7.4.
- Step 2 says **launch**, per §3 (installed≠running gap).
- **Resilient wording.** The numbered steps are our own paraphrase — ollama.com
  carries *no* install instructions of its own (§14), and its download button is
  literally "Download for macOS" (step 1 tracks it loosely).

### 9.4 `downloading`

```
   Downloading Gemma 4 E4B

   1.2 GB of 3.0 GB

                                         [ Cancel ]
```

Byte detail via `ByteCountFormatter`. `[Cancel]` aborts the pull → `idle`.

### 9.5 `failed`

Title always "Couldn't get model"; body is the typed detail; `[Retry]`.

```
   Couldn't get model

   {detail}

                                         [ Retry ]
```

| Case | Detail string |
|---|---|
| `noInternet` | No internet connection. Check your network and try again. |
| `timedOut` | The download timed out. Check your connection and try again. |
| `cantReach` | Lost connection to Ollama. Make sure it's running, then try again. |
| `generic` | The download couldn't finish. %@ |

**Taxonomy note (§15 / Finding 18):** BN's pull targets `127.0.0.1`, so a
*localhost* `URLError.notConnectedToInternet` likely never fires — the genuine
"internet down, can't fetch weights" case happens inside Ollama's daemon and
reaches BN as an error in the `/api/pull` stream body, landing in **`generic`**,
not `noInternet`. `cantReach` / `timedOut` are honest for the BN↔daemon link.
Keep all four strings; friendlier stream-parsing is a later slice. Daemon-absence
is **not** a failure and never reaches this state.

## 10. Copy & verb conventions

- **"Use {model}"** wherever a model is chosen/confirmed — the user *chooses*,
  Ollama *fetches*. Never "Download model" (implies the user downloads). The
  download size lives in the row's sub-line (`~N GB download`), not in the verb
  and not in a separate caption.
- **"Get Ollama…"** not "Install Ollama" — name the action, don't over-promise.
- **Launch / open** Ollama, not just "install" — the installed≠running gap.
- **One size per row, framed by cost** (§9.1): `~N GB download` vs `N GB on disk`.
- User-facing chrome says **Ollama** (product) and avoids "daemon"/"runtime"
  jargon in the popovers.

## 11. Re-entry paths

After §7.4 Cancel there is no toolbar chip. Re-entry is **Settings →
provider/model**, which must carry a "Set up Ollama" action that re-calls
`start(tag:)`. (The first-run consent picker already has this hook; Settings
needs the equivalent.) Plus the failure-driven route in §7.4 — neither exists
today (Finding 20). This is the one downstream dependency this redesign adds.

## 12. Honesty principles (summary)

1. **Motion ⇔ Bristlenose is moving bytes.** Static indicator whenever we are
   merely waiting on the human.
2. **No fake progress.** No determinate bar without real byte totals; spinner
   for genuinely-indeterminate Bristlenose work only.
3. **Neutral until truly broken.** Setup states are `.secondary`; red is for
   `failed` alone. Daemon-absence is a normal state, not an error.
4. **No timeout-to-failure.** Waiting on the human has no deadline.
5. **Say what's observable.** Copy never claims knowledge of the user's browser/
   download/install activity we don't have.

## 13. Localisation

All keys in the 6 `desktop.json` files (en, es, fr, de, ko, ja). Strings are
quoted verbatim from the frozen mock (`docs/mockups/ollama-setup-popovers.html`).

- **Remove:** `installingRuntime`, `startingRuntime`, `runtimeDidNotStart`.
- **Pills:** `pillChoosingModel` ("Set up on-device AI"), `pillNeedsOllama`
  ("Get Ollama"), `pillWaiting` ("Waiting for Ollama"), `pillDownloading`
  ("Downloading %@"), `pillDownloadingNoModel` ("Downloading…"), `pillFinishing`
  ("Finishing up"), `pillFailed` ("Couldn't get model").
- **Step 1 (choose model):** `chooseTitle`, `chooseBody` (`%@` = RAM),
  `chooseBodyHasInstalled` (`%@` = RAM), `tagBalanced`, `tagSmallest`, `tagBest`,
  `tagReady`, `rowNeedsRam` (`%@` = GB), `rowDownloadSize` (`%@`), `rowOnDisk`
  (`%@`), `groupInstalled`, `groupDownload`, `foreshadow`, `lowDisk`,
  `useModel` (`%@`), `chooseInstalledCaption`.
- **Step 2 (needs Ollama):** `needsTitle` (`%@` = model), `needsBody`,
  `getOllamaButton`.
- **Step 3 (waiting):** `waitingTitle`, `waitingBody` (carries the `ollama.com`
  link), `waitingStep1`, `waitingStep2`, `waitingFootnote` (`%@` = model),
  `waitingStatusLabel`.
- **Downloading / finishing:** `downloadingTitle` (`%@`), `bytesProgress`
  (`%@`, `%@`), `finishingTitle`, `finishingBody` (`%@`).
- **Failed:** `failedTitle`, `failNoInternet`, `failTimedOut`, `failCantReach`,
  `failGeneric` (`%@`).
- **Buttons:** reuse `common.buttons.cancel` / `common.buttons.retry`.
- Machine-fill es/fr/de/ko; ja delayed per the established playbook. Use
  targeted text-replace, not JSON round-tripping (per `CLAUDE.md` i18n gotcha).

## 14. Maintenance — quarterly review

ollama.com/download is **a third-party page we don't control.** Verified
3 Jun 2026: the download button reads **"Download for macOS"**, the artefact is
**`Ollama.dmg`**, and the page carries **no install instructions of its own** —
so the §9.3 numbered steps are necessarily our own paraphrase. Add to the
quarterly review (`docs/methodology/framework-arc-quarterly-review.md`), alongside
the OllamaCatalog models / weights / RAM thresholds / pricing review:

> Re-verify the ollama.com macOS download page still matches the §9.3 step copy
> (a download affordance present, launch-after-install still required). If Ollama
> redesigns onboarding (e.g. an auto-launching installer), revisit whether the
> step-3 guidance is still accurate. **Also re-check the §9.1 model sizes** (the
> only per-row numbers we now show) against current OllamaCatalog weights.

## 15. Open questions (logged as review-log findings)

Recorded as `open` findings (17–20) in the branch review log, to be checked off
at impl-review:

1. **Flow-B sequencing / manipulation-adjacency** (Finding 17). Model-first-then-
   reveal-dependency is the more persuasive ordering; accepted **with the
   foreshadow line** (§9.1) defusing the bait-and-switch risk. Sanity-check at
   impl-review.
2. **Failure taxonomy** (Finding 18). `noInternet` likely unreachable from a
   localhost `URLError`; real no-internet routes through `generic` (§9.5).
   Friendlier `/api/pull` stream-parsing deferred.
3. **Low-disk trigger basis** (Finding 19). Warn when free disk < the largest
   **selectable** (RAM-fit) model, or < the largest **shown** model (incl.
   disabled)? The former fires only when genuinely tight; the latter fires on
   almost any 256 GB Mac. Pin at implementation.
4. **Failure-driven re-entry to provider choice** (Finding 20, §7.4/§11).
   Confirmed it does **not** exist today — a no-backend project-create attempt
   does not route to provider choice. Net-new dependency this design leans on.

Deferred slices (not blocking):
- **Bring-your-own-model picker** — enumerating the user's full installed-model
  universe (non-curated). This doc only marks *curated* models as installed (§4/§6).
- **Auto-present** the step-1 popover once when the pill first appears post-consent
  (leaning yes — present once, anchored, dismissible).
- **Settings re-entry** (§11) — confirm the Settings provider section can host a
  "Set up Ollama" action at implementation time.

## 16. Implementation map

| Concern | File / symbol |
|---|---|
| State machine, signal, getOllama, poll | `OllamaDownloadModel.swift` |
| Pill + popovers | `OllamaDownloadPill.swift` |
| Activation entry | `AIConsentView.swift` → `activateLocalDefault()` |
| Model pull | `LLMValidator.pullModel(tag:baseURL:onProgress:)` |
| Catalogue / RAM default | `OllamaCatalog` (`LLMProvider.swift`), `docs/design-gemma4-local-models.md` |
| Settings re-entry | desktop settings provider section (§11) |

Frozen copy + layout reference: `docs/mockups/ollama-setup-popovers.html`.
(The earlier terse checklist `.claude/plans/archive/finding-3-ollama-setup.md`
is superseded by this doc and archived — the table above is the live map.)

## Appendix A — download-time reality (the basis for §3a)

Median **fixed broadband** download speed, Speedtest.net, March 2026. These are
_medians_ — half of every market is slower, and the mobile/tethered/rural/hotel
tail is far worse. "Real-world" ≈ 50–60% of median (CDN distance, Wi-Fi,
congestion). _Note: these figures inform our design rationale only — they are
**not** shown to the user (§9.1 removed per-row time estimates)._

| Market (lang) | Median | 3 GB ideal | 3 GB real | 16 GB ideal | 20 GB ideal |
|---|---|---|---|---|---|
| France (fr) | 352 Mbps | 1.1 min | ~2–3 min | 6 min | 8 min |
| US (en) | 310 Mbps | 1.3 min | ~3 min | 7 min | 9 min |
| Spain (es) | 278 Mbps | 1.4 min | ~3 min | 8 min | 10 min |
| Canada (en) | 278 Mbps | 1.4 min | ~3 min | 8 min | 10 min |
| Korea (ko) | 258 Mbps | 1.6 min | ~3 min | 8 min | 10 min |
| Japan (ja) | 255 Mbps | 1.6 min | ~3 min | 8 min | 10 min |
| UK (en) | 172 Mbps | 2.3 min | ~4 min | 12 min | 16 min |
| Italy | 117 Mbps | 3.4 min | ~6 min | 18 min | 23 min |
| **Germany (de)** | **104 Mbps** | **3.9 min** | **~7 min** | **21 min** | **26 min** |
| _A 25 Mbps line_ | 25 Mbps | 16 min | ~28 min | **85 min** | **107 min** |

Model sizes per `OllamaCatalog` / `docs/design-gemma4-local-models.md`:
llama3.2:3b ≈ 2 GB, gemma4:e4b ≈ 3 GB, gemma4:26b ≈ 16 GB, gemma4:31b ≈ 20 GB.

**Disk:** base Macs ship 256 GB; after macOS (~15 GB) + apps + photos, many users
have < 50 GB free. A 20 GB model is ~¼ of remaining headroom; even 3 GB is
meaningful on a near-full drive.

**Takeaway for the design:** the default (2–3 GB) is a few minutes on most
connections but an emotional + disk commitment regardless; the quality models
(16–20 GB) are a "start now, use later" download. §9.1 tells this truth via size
(not guessed time), and §3a justifies why the choice is deliberate.

Sources:
- [List of countries by Internet connection speeds — Wikipedia (Speedtest.net, Mar 2026)](https://en.wikipedia.org/wiki/List_of_countries_by_Internet_connection_speeds)
- [Internet Speeds by Country 2026 — World Population Review](https://worldpopulationreview.com/country-rankings/internet-speeds-by-country)
