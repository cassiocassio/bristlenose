---
status: partial
last-trued: 2026-08-18
trued-against: HEAD@main on 2026-08-18 (04e7c72e)
---

# Project storage — policy

## Changelog

- _2026-08-18_ — trued up: §3's provider-classifier finding was reported open
  and had been fixed structurally; flipped it, re-anchored (`ProjectIndex.swift:650`
  had rotted onto `setFolderCollapsed`), and recorded the larger unstated win —
  the old allowlist reported BN's own default project location as "On this Mac"
  on any Mac with iCloud Drive on. Cloud-import passages checked and left
  untouched: all three are correct cross-references. Anchors:
  `ProjectIndex.swift:907-928`, `:914-919`.

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
| **AVOID** | Archiving to the researcher's *personal* cloud | If a team store exists it is the governed one; and the store is a role, not a product — §5 |
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

**Uncoordinated reads of dataless files are not safe.** iCloud Drive, OneDrive/SharePoint, Google Drive, Dropbox and Box are all File Providers on modern macOS. With eviction enabled, files become *dataless* (attributes and xattrs, no extents). An uncoordinated read can fail with **`EDEADLK` ("Resource deadlock avoided")** rather than materialising — but **only for a process whose materialisation policy is OFF**, and on macOS that errno is **11**, not 35 (35 is `EAGAIN`; the number originally recorded here is Linux's). ~~The fix is `NSFileCoordinator`-wrapped access.~~ **Corrected 4 Sep 2026:** Bristlenose's sandboxed app measures policy **ON** (`DatalessPolicyProbeTests`), and so does the sidecar it spawns — so this app never takes the `EDEADLK` path. Under ON, a read *blocks* until the bytes arrive, and `NSFileCoordinator` changes nothing about that. The fix for this app is detect-then-bounded-materialise, which `bristlenose/utils/fs.py` already implements. Full account: `design-copy-error-surfacing.md` §5.

> **Read and copy do not differ — the caller's policy does.** The 19 Jun 2026 `copyItem` hang (`sample <pid>` → `libcopyfile → com.apple.CloudDocs`, no error, `Task.cancel()` inert) is the policy-**ON** behaviour, which every syscall in this app shares. The `EDEADLK` sentence above is policy-**OFF** behaviour, which this app never sees. An earlier note here on 4 Sep 2026 put the difference on the operation; that was wrong and is replaced by this one. `desktop/CLAUDE.md` §Gotchas has the hang; `design-copy-error-surfacing.md` §5 has the measured policy and the corrected picture.

This contradicts the previous assumption (recorded in `design-desktop-project-status.md`) that "the CLI is right to do nothing about iCloud — macOS materialises the file on read." It usually does. It is not guaranteed. The same failure has already been hit locally in an unrelated `rsync` script, where the fix was `brctl download` pre-materialisation — a subcommand that **no longer exists on macOS 26.4** (verified 4 Sep 2026; `brctl evict` is gone too). `startDownloadingUbiquitousItem` / `evictUbiquitousItem` are the surviving API.

**Third-party apps cannot pin files.** Apple's Developer Relations, on the Files app's "Keep Downloaded":

> "The option is designed to be used via user interaction only. There is no API for developers to programmatically set the option."

`startDownloadingUbiquitousItem` *requests* a download; nothing prevents Optimise Storage evicting it again. `NSFileProviderContentPolicy.downloadEagerlyAndKeepDownloaded` does prevent eviction — but it is available to a File Provider *extension*, i.e. to the provider, not to a client of someone else's provider.

**Consequence:** no design in which Bristlenose consumes iCloud Drive can promise "this project stays local and fast." That promise is not expressible. Every model that depended on it is dead.

**Storage economics.** CloudKit private-database assets come out of the *user's* iCloud quota and hard-error when full; there is no developer-subsidised path for private user data. "Limitless" is always the researcher's paid tier.

**macOS 27 ("Golden Gate", ships ~Sept 2026)** is a refinement release. No FileProvider or iCloud storage API changes were found in the beta release notes or the published change list. Absence of evidence rather than proof — but do not plan around a macOS 27 unlock.

### Reproduced end-to-end, 29 Jul 2026

Not theory — run against a real project on Dropbox with three 307–649 MB screen recordings.

**Recipe.** Put a project in `~/Library/CloudStorage/Dropbox/`. Finder → right-click the media → **Make online-only** (BN must not be holding the files — see below). Confirm with `stat -f '%Sf'` → `dataless`. Run Analyse.

**Result — the run fails, with a message that means the opposite of what happened:**

```
13:46:55  Could not probe Screen Recording 2026-01-27 at 23.37.37.mov … timed out after 30 seconds
13:47:25  Could not probe Screen Recording 2026-01-28 at 00.13.56.mov … timed out after 30 seconds
13:47:55  Could not probe Screen Recording 2026-01-28 at 00.18.49.mov … timed out after 30 seconds
```

Row shows a red ✗ and `ffprobe timed out after 30s probing <file>` — which a researcher reads as **"my video is broken"** when it means **"my file was still downloading."** Opposite remedies. Two sites: [`audio.py:48`](../bristlenose/utils/audio.py:48) catches and warns; [`audio.py:141`](../bristlenose/utils/audio.py:141) raises `AudioToolError` and kills the run.

**Control case:** same project, same path, files made available offline → runs clean. The only variable is residency. Nothing is wrong with cloud paths, the sandbox, or the pipeline.

**Raising the timeout is not the fix.** Measured: 90+ seconds after requesting the fetch, *zero bytes* had landed. Any wall-clock number fails on a 1.3 GB interview.

**What is and isn't detectable** (verified on a Dropbox file — the `ubiquitousItem*` keys are not iCloud-only):

| Question | API | Available |
|---|---|---|
| Is this file evicted? | `st_flags & SF_DATALESS` (0x40000000) · `ubiquitousItemDownloadingStatus` | **Yes**, both layers, cross-provider |
| Is it downloading right now? | `ubiquitousItemIsDownloading` | **Yes** |
| How far along? | — | **No.** See below |

**Progress is not observable, and that is permanent.** Dropbox stages the download and swaps the file in atomically: measured at ~50% on Finder's pie, `st_blocks` was still **0** and the file still flagged `dataless`. A POSIX-derived ring would sit at zero then snap to 100. iCloud's `percentDownloaded` is deprecated; `NSFileProviderManager.globalProgress` is per-provider aggregate (and would attribute the researcher's unrelated syncing to BN's fetch). So the wait must be **indeterminate** — that is the honest shape, not a compromise. Corollary: BN also cannot distinguish a healthy fetch from a stalled one, so the only legitimate wall-clock number is a soft *hint* after several minutes ("still fetching — is Dropbox running?"), never a failure.

**`.inCloud` is unreachable in the normal case.** [`ProjectAvailability.swift:141`](../desktop/Bristlenose/Bristlenose/ProjectAvailability.swift:141) short-circuits on `fileExists(atPath: path)` — the project *folder*. With every file in the folder evicted, `os.path.exists()` is still true and `listdir` still returns entries, so availability resolves to `.ready` and step 5 never runs. The cloud glyph therefore cannot appear for evicted media in an existing folder, at any free-space level. Meanwhile [`ProjectFolderWatcher.swift:228`](../desktop/Bristlenose/Bristlenose/ProjectFolderWatcher.swift:228) *already* calls `isCloudEvicted` on every non-resident file and discards the result with `continue` — the count is computed and thrown away. Turning that into `evictedFiles` gives whole-vs-partial for free.

**~~The provider classifier is an allowlist of three.~~ Fixed — it is structural now.** _Trued 18 Aug 2026._ The finding was right and the prescription was taken verbatim: [`ProjectIndex.swift:907`](../desktop/Bristlenose/Bristlenose/ProjectIndex.swift:907) matches `/Library/CloudStorage/`, takes the first path component and splits it on `-`, so **Box and Google Drive work without being enumerated** — the code comment says so in this doc's own words. `providerNames` ([`:924`](../desktop/Bristlenose/Bristlenose/ProjectIndex.swift:924)) now maps only the three whose on-disk container name differs from the product name a researcher would recognise (`GoogleDrive`, `ProtonDrive`, `pCloudDrive`); an unknown provider keeps its own name rather than being flattened to a generic "Cloud".

_(The original anchor in this bullet, `ProjectIndex.swift:650`, had rotted — it now lands on `setFolderCollapsed`. Worth noting as a mechanism rather than a typo: a line-number anchor into a file under active work is a citation with a short half-life, and it fails **silently** because the link still resolves.)_

**The fix carried a win this bullet never predicted, and it is the more serious of the two.** The old three-prefix allowlist had no way to catch a *home* folder that Desktop & Documents sync had taken over — `~/Documents` has no distinguishing path shape at all — so it reported **Bristlenose's own default project location as "On this Mac" on any Mac with iCloud Drive turned on** ([`:914-919`](../desktop/Bristlenose/Bristlenose/ProjectIndex.swift:914)). The stated symptom was two named third-party providers going unclassified; the unstated one was the default case being wrong for a large fraction of users. Resolved by falling through to the File Provider flag (`isUbiquitous`) once the path-shape tests miss.

**Name the provider, and say so — attribution is the point.** "Dropbox / Google Drive are not special-cased" (`design-sidebar-activity-indicators.md`) rejected provider-specific *behaviour* — download buttons, progress affordances, integrations. It does not forbid *naming what is already happening*, and the sibling state already sets the precedent: `cantFind(.unmountedVolume(name:))` names the volume rather than saying "a drive is missing". Two reasons it earns its place: each provider has a **different fix path** (Dropbox's menu-bar item, iCloud's Settings pane, the OneDrive client), so a generic "the cloud" leaves the researcher nowhere to go — which matters given BN can't tell a healthy fetch from a stalled one. And **it is right for BN to say when the slowness is not its own**: an unexplained three-minute stall reads as "Bristlenose is slow"; "Fetching from Dropbox…" reads as "the network is slow". Explaining a wait you don't control is not offloading work onto the user (`feedback_appliance_copes_dont_offload_to_user`) — it is the opposite of pretending.

**Scope of any such messaging — decided by the maintainer, 4 Sep 2026: iCloud Drive, Google Drive and OneDrive/SharePoint only, and nothing clever.** Those are the stores that pair with the researcher's meeting platforms (iCloud for the personal Mac; Google Drive with Meet; OneDrive with Teams). Dropbox, Box, pCloud, Proton, a NAS: no custom materialisation messaging. Two things this does *not* change. The Dropbox examples in this section were the **measurement test bed**, not a scope statement — the findings hold, the messaging scope is narrower. And §5's rule that Bristlenose must *read* any File Provider correctly stays **unconditional**; this scopes the label, never the correctness.

**Eviction is blocked while BN holds the file** — Finder reports "Unable to Remove Download" with no explanation. Fine once BN releases it.

**What already works and should not be disturbed:** a run against a cloud folder with resident files is completely normal; the failure surfaced on the row *and* in the detail pane; the context-menu retry recovered cleanly with no corrupted state. The defect is a missing pre-check and a wrong label, not architecture.

---

## 4. Two things that look true and are not

**"Clips can replace the originals."** No. Clips are *deliverables* — star quotes, export, drag five into a deck, make the meeting. They are a disposable derivative that can be regenerated at any time. The source recording is the irreplaceable asset: it represents weeks of recruiting, scheduling, consent and incentives, and it cannot be regenerated at all.

**"Re-analysis is rare."** No — it is routine. A client asks *"do we have anything about dogfood?"*, a code nobody created, about something participants were keen to talk about. Old studies get re-coded for new angles regularly.

Usefully, most of that work is a **text** operation: re-coding runs against transcripts, which are tiny and stay local forever, and `analyze` already skips transcription. The researcher re-codes from text, finds twelve quotes across three sessions, and needs *those three files* to cut clips. So restore is **selective, not wholesale** — which is what makes a slow archive tier workable at all. The exceptions are re-transcription with a better model and PII re-runs, which are genuinely bulk.

---

## 5. Where the source lives, and who owns the clock

There are **three places**, and they are roles rather than products. Naming them by brand is what caused an earlier draft of this doc to reason badly.

| Role | What it is | Examples | Durability |
|---|---|---|---|
| **Origin** | Where the recording is made and first lives | Teams, Google Meet, Zoom | **Expiring**, on a schedule the researcher does not set and may not know |
| **Captured original** | Bristlenose's own copy, on the researcher's machine | — | Bristlenose owns the retention clock from capture onward |
| **Store** | Wherever the researcher keeps their raw data | Team SharePoint, Google Drive, Dropbox, a NAS on the desk, a Samsung T7 — **or nowhere; it just sits on the Mac** | Theirs. May be governed, may be a drive, may not exist |

**Bristlenose holds captured originals — it never references the origin as its source.** A link to a Teams or Zoom recording can vanish at any moment, so the bytes are pulled down and owned. Originals arrive either by integration (`docs/design-cloud-import.md`) or by the researcher downloading and dragging them in; both produce the same thing.

Three consequences:

- **The store is optional, and often absent.** Plenty of researchers — freelancers especially — have no team raw-data location at all. In that case Bristlenose's captured original is genuinely the only copy once the origin expires, which is the strongest argument for never deleting source media and for the archive MAYBE in §1.
- **Bristlenose has no opinion about which store.** SharePoint, Drive, Dropbox, NAS, external SSD — all the same to it. That is why any archive feature must be a **user-nominated folder**, not a cloud integration. The one rule: if a *team* store exists, never default to the researcher's *personal* cloud — that moves raw research out of the team's governance boundary, which for a client engagement is probably a contract breach.
- **Any of them may be a File Provider.** SharePoint, OneDrive, Drive, Dropbox and iCloud all present dataless placeholders; a NAS or T7 presents an unmounted volume instead. Either way a folder Bristlenose is pointed at may not have readable bytes behind it — which is why §1's YES column is unconditional rather than iCloud-specific.

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
