# Project storage — policy

**Status: decided (28 Jul 2026). This is the standing answer to "should Bristlenose do something about where the media lives?"**

Short version: **no, except read files correctly.** Bristlenose does not manage, tier, sync, compress, or evict the researcher's media. It reads whatever folder it is pointed at — including one whose files are cloud-backed placeholders — and stays useful when those files are absent. Everything beyond that is either rejected or gated behind a named condition.

This doc exists because the question recurs in several disguises (iCloud sync, archives, proxies, storage budgets, File Provider extensions) and each time it takes a long session to re-derive the same answer.

**Scope note.** This doc is about media Bristlenose *already has* — on disk, on a volume, in a cloud-synced folder. Fetching originals down from Teams / Zoom / Drive in the first place is a separate feature with separate gates: **`docs/design-cloud-import.md`**. The two meet at one point: import produces *captured originals*, and the retention clock in §5 runs against those.

---

## 1. The decision table

| | Item | Why |
|---|---|---|
| **YES** | Coordinated reads of cloud-backed files | Uncoordinated reads of a dataless file can fail with `EDEADLK`; see §3 |
| **YES** | Free-space precheck before a run; legible `ENOSPC` | Materialising a corpus can fill the disk that eviction was protecting |
| **YES** | Never blind-`copyItem` a user-supplied file | Blocks forever on a dataless source and can't be cancelled |
| **YES** | Stay fully useful when source media is absent | Analysis is the product; playback is the only thing that should degrade |
| **YES** | Reconnect silently when media returns | BN follows, never fights — renames/moves/re-downloads resolve without UI |
| **YES** | Cut quote clips at analysis time | Keeps a project browsable and playable without its source files |
| **NO** | BN-managed iCloud library / ubiquity container | Apple-only, needs an entitlement, and cannot deliver its own promise (§3) |
| **NO** | BN ships a File Provider extension | Only coherent with a backend; that is a different company |
| **NO** | Transcode / proxy media | The content *is* fine text in a prototype; any resolution loss destroys it |
| **NO** | LRU or size-budget auto-eviction | BN cannot know which old project matters; recency is not value |
| **NO** | Meeting bot / calendar-joining recorder | Requires an always-on service reachable by the tenant |
| **NO** | Deleting the researcher's source media, ever | It may be the only copy, and it cost weeks of fieldwork |
| **MAYBE** | Archive = a user-nominated folder | Gate: cohort asks for it. Storage-agnostic, no entitlement — see §5 |
| **MAYBE** | Retention / expiry of the raw tier | Gate: consent-gradient sequencing. Real professional need — see §5 |
| **MAYBE** | Folder-watch trigger ("2 new files — analyse?") | Cheap; detection already exists. Likely the first thing to build |
| **MAYBE** | iPad + iCloud sync | Existing hard gate: paying Mac customers asking by name |
| **AVOID** | Framing any of this as privacy or local-first | Not the product's stance |
| **AVOID** | Making BN the storage layer | Workbench, not vault |
| **AVOID** | Archiving to the researcher's *personal* cloud | The team's governed store is usually the canonical home — §5 |
| **AVOID** | Assuming "macOS materialises on read" | It does not reliably — §3 |
| **AVOID** | Assuming clips can replace originals | Re-analysis for new angles is routine — §4 |

---

## 2. What the corpus actually looks like

Correcting a figure that has misled planning: a study is **not** 500 GB.

| Source | Resolution | Bitrate | Per hour | Study |
|---|---|---|---|---|
| Platform recordings (Teams / Zoom / Meet) — **~99% of real corpora** | 720p | 2.5–3 Mbps | ~1.3 GB | **6–20 GB** |
| Local macOS Screen Recording — rare, mostly dev artefacts | 3456×2234 | 17–33 Mbps | ~9 GB | ~180 GB |

A study is **5 sessions normal, 10 common, 15+ a big one** — so 6–20 GB, and a heavy year is perhaps 100 GB. A laptop holds two or three years of work.

**The problem is placement, not size** — and placement is a human decision, not a heuristic.

The lab era (Morae, Silverback, disk arrays, capture settings) is over. The video comes from remote calls, already compressed by the platform. Do not inherit lab-era media management.

---

## 3. Platform findings that constrain the design

Researched 28 Jul 2026. These are the facts that kill most of the attractive options.

**Uncoordinated reads of dataless files are not safe.** iCloud Drive, OneDrive/SharePoint, Google Drive, Dropbox and Box are all File Providers on modern macOS. With eviction enabled, files become *dataless* (attributes and xattrs, no extents). An uncoordinated read can fail with **`EDEADLK` (errno 35, "Resource deadlock avoided")** rather than materialising — observed via `cat`, `cp`, `dd`, Python `os.read()` and Node `fs.readFileSync()`. The fix is `NSFileCoordinator`-wrapped access, which signals the provider to materialise before the accessor runs.

This contradicts the previous assumption (recorded in `design-desktop-project-status.md`) that "the CLI is right to do nothing about iCloud — macOS materialises the file on read." It usually does. It is not guaranteed. The same failure has already been hit locally in an unrelated `rsync` script, where the fix was `brctl download` pre-materialisation.

**Third-party apps cannot pin files.** Apple's Developer Relations, on the Files app's "Keep Downloaded":

> "The option is designed to be used via user interaction only. There is no API for developers to programmatically set the option."

`startDownloadingUbiquitousItem` *requests* a download; nothing prevents Optimise Storage evicting it again. `NSFileProviderContentPolicy.downloadEagerlyAndKeepDownloaded` does prevent eviction — but it is available to a File Provider *extension*, i.e. to the provider, not to a client of someone else's provider.

**Consequence:** no design in which Bristlenose consumes iCloud Drive can promise "this project stays local and fast." That promise is not expressible. Every model that depended on it is dead.

**Storage economics.** CloudKit private-database assets come out of the *user's* iCloud quota and hard-error when full; there is no developer-subsidised path for private user data. "Limitless" is always the researcher's paid tier.

**macOS 27 ("Golden Gate", ships ~Sept 2026)** is a refinement release. No FileProvider or iCloud storage API changes were found in the beta release notes or the published change list. Absence of evidence rather than proof — but do not plan around a macOS 27 unlock.

---

## 4. Two things that look true and are not

**"Clips can replace the originals."** No. Clips are *deliverables* — star quotes, export, drag five into a deck, make the meeting. They are a disposable derivative that can be regenerated at any time. The source recording is the irreplaceable asset: it represents weeks of recruiting, scheduling, consent and incentives, and it cannot be regenerated at all.

**"Re-analysis is rare."** No — it is routine. A client asks *"do we have anything about dogfood?"*, a code nobody created, about something participants were keen to talk about. Old studies get re-coded for new angles regularly.

Usefully, most of that work is a **text** operation: re-coding runs against transcripts, which are tiny and stay local forever, and `analyze` already skips transcription. The researcher re-codes from text, finds twelve quotes across three sessions, and needs *those three files* to cut clips. So restore is **selective, not wholesale** — which is what makes a slow archive tier workable at all. The exceptions are re-transcription with a better model and PII re-runs, which are genuinely bulk.

---

## 5. Where the source lives, and who owns the clock

**Bristlenose holds captured originals — it never references cloud files as its source.** A link to a Teams or Zoom recording can vanish at any moment, so the bytes must be pulled down and owned. Once captured, Bristlenose owns the retention clock for that copy, and the researcher's own GDPR lifecycle runs against it rather than against someone else's expiry policy. (How they get pulled down: `docs/design-cloud-import.md`.)

Two storage locations get conflated and must not be:

- **The platform recording** (Teams `/Recordings`, Zoom cloud) — auto-expiring, on a schedule the researcher does not control and may not know. **Never reference this; capture from it.**
- **The team raw-data folder on SharePoint** — durable, governed, team-visible, paid for by the employer or client. A legitimate place a copy also lives, and the reason an archive feature must never default to the researcher's *personal* cloud: that would move raw research out of the team's governance boundary, which for a client engagement is probably a contract breach.

**Both are already File Providers with on-demand materialisation.** So a folder Bristlenose is pointed at may hold dataless placeholders whichever of these it is — which is why §1's YES column is unconditional, not iCloud-specific.

**Platform retention is finite and not the researcher's to set.** Teams applies a default expiration to meeting recordings (120 days in Microsoft's documentation, commonly configured to 60, admin-settable); Zoom retention is org-set, commonly 365 days to 3 years. So "they can always re-fetch from Teams" holds for roughly two months and then quietly stops. This is why raw data has a lifecycle at all — and why the mature version of this problem is **expiry**, not archiving. Note that retention caps growth but does not solve it: a 2-year policy still leaves a couple of years of studies live.

Anonymised analysis outliving raw data is normal practice, and Bristlenose already has the boundary in the pipeline (PII removal at s07, anonymised exports). The identifiable residue in `.bristlenose/` — `pii_summary.txt`, `llm-calls.jsonl` — currently has **no expiry at all** and should be the first thing to go, not the last.

---

## 6. Models considered and rejected

Kept so they are not re-proposed. Each was worked through in full on 28 Jul 2026.

1. **Oblivious** — BN ignores cloud entirely. Not a model; it is the status quo, and it leaks (§3).
2. **Auto-tier** — projects created in iCloud, media pushed up after transcription. Right instinct, wrong lever: cannot promise local-and-fast (§3), and first playback becomes a multi-GB fetch.
3. **Per-project "keep local" checkbox** — honest about consent, dishonest about performance: the checkbox cannot be honoured.
4. **Cloud Archive folder** — best interaction shape of the four; survives as the gated MAYBE in §1, in its storage-agnostic nominated-folder form.
5. **File Provider extension** — the only architecture that delivers residency guarantees; requires a backend; different company.
6. **Proxy / transcode media** — dead on fine text (§1) and on "already efficiently encoded" (§2).
7. **Local media budget with LRU** — dead: BN cannot know which old project matters.
8. **Archive-as-truth, disk-as-cache** — same defect as 7, applied globally.
9. **Do nothing structural, but stop lying** — this is §1's YES column, and it is the floor for every other option.

---

## 7. Related

- **`docs/design-cloud-import.md`** — fetching the originals down in the first place; the other half of this pair
- `docs/methodology/consent-gradient.md` — the governance model retention and placement sit inside; authoritative over code
- `docs/design-icloud-sync.md` — the parked iPad + iCloud-sync speculation, with its own hard gate
- `docs/design-multi-project.md` — `location.type = "cloud"`, placeholder directories, volume-relative resolution
- `docs/design-desktop-project-status.md` — the availability split (`inCloud` vs `cantFind`) and the precedence chain
- `desktop/CLAUDE.md` — the `copyItem`-blocks-on-dataless gotcha
