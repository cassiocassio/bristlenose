# Bristlenose on iPad — iCloud sync (parked speculation)

**Status: FUTURE MADNESS — parked, not planned.**
This is a captured thought experiment, not a commitment. It stays behind a hard
gate: **do not start building any of this until there are paying Mac customers
asking for iPad review by name.** It is the same contingent bet as full-native
macOS (see `project_native_direction_is_contingent_bet` memory and
`docs/design-modularity.md`), only further down the same gated path. The durable
primary remains the web SPA; Linux stays first-class.

Diagrams: [docs/mockups/icloud-sync-architecture.html](mockups/icloud-sync-architecture.html)
(auto-discovered by `bristlenose serve --dev` → About → Design).

---

## The dream

Open a Swift app from the App Store on an iPad, already signed into the same
Apple ID, and every project is just *there* — synchronised sidebar, ready to
review. Take yourself to a quiet corner and flick-and-tap through a thousand
quotes in a flow state: star, star, tag, star. The tablet is for the three-hour
*read*, not the twenty-minute *crunch*.

The insight underneath: Bristlenose is really two products sharing a codebase.

- **Production** — ingest → transcribe → PII → segment → extract → cluster →
  theme. Heavy, subprocess-hungry, LLM-orchestrating. Irreducibly Python,
  irreducibly Mac/Linux. **Never runs on iPadOS** (silicon is fine; the OS
  process model and App Store posture are not).
- **Curation** — read, triage, star / tag / hide, rename a heading. Lean-back,
  keyboard-free, quiet-corner work. This is the half that *wants* a tablet.

So the iPad app is necessarily a **review-only sibling**, not "the same app."

## The architecture that could work

### The checkbox is the seam (and the reason it must be a checkbox)

The folder/path model is the **shared substrate** — Linux, the CLI/Snap, and the
SPA all stand on it. Three of the four worlds can't have iCloud and don't want a
managed library. So iCloud can never be the substrate; it can only ever be an
**Apple-only, opt-in overlay**. A single macOS setting — *"keep everything on
iCloud"* — is the seam between the durable folder-native core and that overlay.
This is what lets the iPad dream exist **without forking the product**
(the no-fork / "CLI ≡ macOS Python, packaging differences only" principle).

### Relocate, don't replace

The overlay does **not** introduce a second data model. A managed iCloud library
is *still folders and paths* — it just lives inside the iCloud container
directory instead of `~/Documents`, and import **copies** media in rather than
referencing it in place. The Python core never learns the word "iCloud"; it reads
the identical project structure whether that folder is on a Linux box, in a CLI
user's home dir, or inside `~/Library/Mobile Documents/…`. Only two things change
when the box is ticked, and both are *policy*, not data model:

1. **where** the library lives (synced container vs. arbitrary Finder location), and
2. **copy-vs-reference** on import (copy — never *move*; never delete the user's original).

The CLI could run against a synced library folder and be none the wiser.

This also collapses into the **consent switch**: checkbox on = managed iCloud
library (the freelancer default); checkbox off = reference-in-place, local-only
(the IRB / clinical default). One control, two coherent worlds, and the app never
has to guess which kind of researcher you are — you told it.

### Records vs media (the one genuinely Apple-specific seam)

Not everything syncs the same way:

- **Media + derived assets** — write-once-ish. Sync fine as plain files in the
  iCloud container, with lazy download / eviction (the Photos "optimise storage"
  model). **Do not** sync the raw `.sqlite` file as a blob — whole-file conflicts
  and corruption.
- **Curation state** (star / tag / hide / rename) — mutable, edited on two
  devices. Wants **record-level merge (CloudKit)**, not file-level sync. This is
  the one slice where the overlay does more than relocate a folder. Even here the
  Python core still owns the local DB + folder; a thin Swift layer projects
  changes in and out.

### Where the review UI lives

Two options, both keep Python off the iPad:

1. **Native Swift data layer** (SwiftData / GRDB over the same schema) +
   either a native SwiftUI review surface, or the React SPA in a WKWebView with a
   native shim (`WKScriptMessageHandler` / local `URLProtocol`) answering its
   `fetch()` calls instead of HTTP-to-FastAPI.
2. **In-browser data layer** — React talks to a local store (`sql.js` WASM, or
   JSON + IndexedDB). This is the existing **Export HTML** artifact (React bundle
   + JSON, zero Python) grown a write-back spine.

The clean synthesis: keep the shared React review UI in a WKWebView on *both*
Mac and iPad, but change what it talks to — `React → native shim → Swift data
layer` instead of `React → HTTP → FastAPI`. Same review UI written once; native,
CloudKit-syncable data layer underneath; **FastAPI shrinks to a pipeline engine
that only runs when there's analysis to do.** The AppKit-chrome work proceeds
orthogonally.

> The realisation that forced all of this: the macOS native experiment was only
> ever a *presentation-layer* move (native chrome around a webview, Python still
> serving through localhost). It never had to answer "where does the data come
> from" because the sidecar was always there. iPad removes that crutch — Python
> can't come — so "go native" stops being a skin choice and becomes the whole
> stack, data included. **FastAPI was doing two jobs that were never really one;
> the iPad is what forces you to cleave the curation CRUD off the pipeline.**

## The staircase (build order, if the gate ever opens)

Each step ships value with a fraction of the risk of the one after it. **Do not
start at the top.**

1. **Registry-only sync.** Sync just the project list (names, IDs, last-modified,
   review progress). Tiny, append-mostly, near-zero conflict. Delivers "my
   projects appear on all my devices" — the delightful part, almost for free.
   Ships value even before an iPad app exists (two Macs agree).
2. **Read-only iPad review** over synced text. **No write-back → zero conflict
   resolution.** "Read my report anywhere."
3. **Write-back, one field at a time**, earning each merge policy as you go:
   **star** (idempotent boolean, trivial) → **tags** (a set, add/remove) →
   **renames** (a value, last-writer-wins with care).

## Pre-mortem — how this sinks the project

Ranked worst-first. (Written 2026-07-13.)

1. **It didn't fail technically — it ate the runway.** *Most likely real cause.*
   A robust two-platform offline-sync engine is a multi-month effort for a team.
   Solo, pre-alpha, not through external TestFlight on the *first* platform, the
   sync work becomes an invisible black hole: never quite shippable, so the
   cohort never sees the actual product, so nothing gets validated, so the window
   closes. Cohort validates the product, not the engineering. **This pre-mortem
   hardens the gate; it does not open it.**
2. **The impedance mismatch is yours to own, not Apple's.** Python owns folders +
   SQLite; CloudKit owns records. Keeping two sources of truth identical on every
   write means building a change-capture / outbox layer and a watcher for the
   core's mutations — *your code to write and debug*. Unlike a greenfield
   SwiftData app, you can't let CloudKit own the model, because the folder-native
   core is the whole no-fork substrate. You're gluing a filesystem app to a
   record-sync engine down the middle.
3. **Silent data loss, asymmetric downside.** Two devices tag the same quote
   offline; last-writer-wins throws away someone's coding work. Every field
   merges differently (boolean vs set vs value). Lose a researcher's afternoon
   once and they never trust the tool again — "the user leaves forever," not "a
   bug."
4. **Media reality breaks the exact scenario it was sold on.** A real corpus is
   tens of GB — past the 5 GB free tier on day one, so the feature *requires* paid
   iCloud+; when quota fills, sync stalls with opaque errors. First sync is an
   overnight upload (Mac awake, plugged in). Eviction means the clip you want in
   the quiet corner with no wifi is precisely the one not downloaded. Text quotes
   can be offline-cheap; video basically can't.
5. **The privacy story inverts under load.** Advanced Data Protection is *off* by
   default, so "never readable by anyone else" is false unless the user enabled
   it; standard iCloud is Apple-accessible and subpoenable. "Everything syncs"
   quietly includes the `pii_summary` / `llm-calls.jsonl` re-identification keys
   that hard rules say never leave the hidden dir. And a second device holding
   participant footage *doubles* the breach surface the feature claimed to reduce.
6. **Schema drift across two independently-updated App Store apps.** Pre-1.0
   schema churns constantly; CloudKit migrations are append-mostly and painful;
   two clients that update out of step drop fields or break sync in the field
   where you can't see it.
7. **Untestable with current tooling; second App Store SKU.** Distributed,
   eventually-consistent, offline bugs are non-deterministic and brutal to
   reproduce — the Playwright/single-serve harness can't touch them. And it's a
   second submission (signing, entitlements, sandbox, TestFlight) before the first
   has shipped.

**What the pre-mortem is really telling us:** one requirement imports ~90% of the
pain — *"works offline with no Mac reachable."* Everything above exists to serve
that one line. The **LAN-serve** model (iPad Safari → the Mac's `serve` on the
LAN; single source of truth on the Mac; iPad as a thin live client) has *none* of
the nightmare and covers "same house / same office," which is most real review
sessions. The honest hybrid is probably **LAN-live at the desk + a thin offline
*text* cache with a write *outbox* that flushes on reconnect** — a weekend of
risk, not a quarter of it. The ambition is fine; the *sequencing* is the trap.
The version that isn't a nightmare is "registry sync + read-only iPad," and you
only climb toward bidirectional write-back when a paying Mac customer asks for it.

## Decisions captured

- iPad is a **review-only sibling**, never the pipeline. Python never touches iPad.
- iCloud is an **opt-in Apple overlay**, not the substrate. A single checkbox.
- The overlay **relocates** the folder library (into the container) and **copies**
  media in on import — **never moves/deletes** the original. It does not replace
  the data model.
- **Copy, never move.** Media as synced files; **curation state as CloudKit
  records** (never the raw `.sqlite` as a blob).
- The checkbox **is** the consent switch (managed+synced vs. local-only).
- Cleave FastAPI: **pipeline (Python, Mac-only)** vs. **curation CRUD (portable →
  Swift)**; the CRUD is the part the iPad reimplements.
- Build order is the **staircase** (registry → read-only → per-field write-back),
  never the full engine first.
