# Coverage inventory — the surfaces we test

_The single source of "what exists to be covered." Consumed by **both** testing tiers: the mechanical [acceptance-matrix.md](acceptance-matrix.md) (assert each surface works, shape-only) and the human walk (judge each surface, feel + correctness). Grounded against code 7 Jul 2026 — re-true when surfaces are added._

When you add an ingest format, **a cloud ingest source**, an export, a lens, or a provider, add it here first — then both tiers inherit it. Fixture status is tracked here as ✅ *have* / ⚠️ *need*; the concrete fixture-folder mapping lives in the private walks-fix-walks QA doc (real interview data stays out of git).

---

## 1. Ingest formats (27 claimed — README:233)

Four decode paths converge on one transcript. Source: `bristlenose/models.py:97-101`.

| Path | Extensions | Stage | Fixture |
|---|---|---|---|
| Audio → transcribe | `.wav .mp3 .m4a .flac .ogg .wma .aac` | s02→s05 (Whisper) | ⚠️ none |
| Video → extract audio → transcribe | `.mp4 .m4v .mov .avi .mkv .webm` | s01→s02→s05 | ✅ `.mp4`/`.mov`; ⚠️ rest |
| Subtitle → parse (skips transcription) | `.srt .vtt` | s03 | ✅ `.vtt`; ⚠️ `.srt` |
| Transcript → parse | `.docx` (Zoom/Teams/Meet) | s04 | ⚠️ format-parity slot exists, files not produced |

**Key insight (from acceptance-matrix):** transcription is provider-independent, so the media path is *one representative cell*, not a format×provider matrix. Container-decode is a thin ffmpeg/Whisper concern — one clip per container proves the decode path; you don't re-run it per provider.

**Correct layer for format coverage (post-review 2026-07-07):** all 27 extensions collapse to 4 decode paths by suffix (`classify_file`, `models.py:108`). Proving "`.flac` ingests" does **not** need a full LLM leg — that re-runs Whisper+Claude to test a suffix table and a codec. So the 27-format check is a **cheap pytest** (`tests/test_format_ingest_coverage.py`): `classify_file` routes each extension + ffmpeg **re-encodes** (codec-family, not `-c copy` remux) a tiny clip per container and decodes it back (`ffmpeg -f null -`). One representative media `run` (in the acceptance matrix) covers the transcribe→analysis handoff. The genuine *format-parity* question (Teams vs Meet vs Zoom `.docx`/`.vtt` parse-shapes) is where a real LLM leg earns its keep — see §Transcript below.

**Ingest invariants:** same-stem merge (`p1.mp4`+`p1.srt` = one session, subtitle skips transcription — README:231); mixed-format folder; `._*`/`.DS_Store` ignored (`is_os_metadata`, `utils/fs.py`).

**Test-data gap:** the 26 container/subtitle formats are covered by the cheap pytest above (fixtures generated at test-time via ffmpeg — no committed binaries). `.docx` is the one that needs **real** exports (a synthetic docx parses by construction against the Teams-shaped parser `s04_parse_docx.py:16`, proving nothing — the Meet leg specifically tests whether Google Meet's real shape parses). Prefer a **public-domain** source (a FOSSDA transcript → Google Doc → export) over a real client call; regression-pin `git check-ignore` on the gitignored format-acceptance fixture slot. Recipe: [test-data-generation.md](test-data-generation.md).

---

## 1a. Cloud import — ingest that isn't a file (3 sources)

Added 15 Aug 2026, when three adapters shipped. `design-cloud-import.md` §9 asked
for this section *before* the build; it is here after. Cloud import is a **source**,
not a format — the 27 above are unchanged, because what lands on disk is still an
ordinary `.mp4`/`.m4a`.

| Platform | Adapter | Artifacts reachable | Live-tested? |
|---|---|---|---|
| Microsoft Teams | `TeamsSource.swift` | video + roster; transcript admin-walled — **confirmed 15 Aug**, `/Recordings` holds the `.mp4` alone | 🟡 signs in and lists against a live tenant (15 Aug 2026); **has never downloaded** |
| Google Meet | `GoogleMeetSource.swift` | video (Picker) + roster + transcript | ❌ no OAuth client registered |
| Zoom | `ZoomSource.swift` | video + VTT; no roster (API has none) | ❌ no OAuth client registered |

**What the first live tenant cost, and why this column is worth keeping honest.**
Teams' listing path met real bytes on 15 Aug and **two filename parsers broke** —
the Swift one rejected every business recording, and Bristlenose's own pipeline
regex had been mis-pairing recordings with their transcripts since Feb 2026
(fixed `8b8eafc9`). Both had been green throughout against fixtures they were
written beside. A ❌ in this column is not "probably fine, untested"; on the one
row that changed it, it was two bugs.

**Mechanical coverage that exists:** seven Swift test files — `CloudDownloadTests`,
`GoogleMeetImportTests`, `ZoomImportTests`, `TeamsSourceTests`, `CloudImportModelTests`,
`OAuthPKCETests`, `TeamsRecordingNameTests`. They cover the pure-value layer:
response classification, file selection, date-window chunking, filename synthesis,
byte verification.

**Cloud-ingest invariants** (distinct from the file-shaped ones above, because the
source is hostile rather than merely varied):
- an error delivered as HTTP 200 is refused **before** the destination file exists
- bytes are checked against the listing's own size — an independent second source
- magic bytes catch what size cannot: a redirect that served something else of
  similar length
- `.part` + same-volume rename, so the destination path never names a partial file
- per-platform redirect header policy (Graph sends none, Zoom strips, Google keeps)
- remote-controlled meeting titles go through filename sanitisation before becoming
  a path component
- no download URL reaches the view layer — they are credentials

**Seams:** `CloudDownloader.init(session:)` takes an injectable `URLSession`;
`FixtureCloudSource` drives twelve scenarios across all three platforms from the
Diagnostics menu with no account.

**Transport tier (added 15 Aug 2026):** `CloudTransportTests.swift` — a
`URLProtocol` stub that records requests, driving the real `CloudDownloader` and
the real adapters. Eleven tests covering redirect header policy per platform,
what survives on disk after each failure mode, no-retry-loop on an unlicensed
401, `pageCapHit` on an endless continuation, and month-chunking of a 90-day
Zoom window.

⚠️ **One gap remains: no live round trip on any platform.** No OAuth client is
registered, so sign-in cannot complete. Human-tier, and it gates everything.

---

## 2. LLM providers (5)

Registry: `bristlenose/llm/providers.py`; client seams: `bristlenose/llm/client.py`.

| Display | Config id | Notes |
|---|---|---|
| Claude | `anthropic` | baseline known-good |
| ChatGPT | `openai` | |
| Azure OpenAI | `azure` | needs endpoint + deployment name |
| Gemini | `google` | |
| Local | `local` (Ollama) | free, no key; daemon + pulled model |

**Provider axis = text, not media.** Only analysis stages (s08–s11) are provider-specific, so the per-provider cell is `analyze <text-fixture> --llm X` — straight to the wire path (auth, schema, model-resolution). ~a dozen small calls × 5 ≈ pennies. Non-Claude failures are **signal, not regression** (alpha provider strategy). Invariants: fail-stop, no silent failover; no `auth-token:`/`api-key:` in failure UI; error taxonomy (QUOTA/AUTH/NETWORK/API_SERVER) maps to a researcher banner.

---

## 3. Exports (canonical list — design-export-slides.md:3)

Wired: **Export Report (HTML)** · **Copy Quotes** (clipboard markdown) · **Save as Spreadsheet** (XLS) · **Extract Clips** (MP4) · **Send to Miro**. Trigger: `frontend/src/components/ExportDropdown.tsx` (Quotes lens).

- **Slides (`.pptx`)** — parked, unimplemented. Do not test.
- **`.docx` Word export** — **dropped** (27 Jul 2026). Never wired; the README claim is struck and it's marked dropped in [ROADMAP.md](../ROADMAP.md). Nothing to test. (Note: `.docx` as an *input* format is still tested — see §1 Ingest formats above.)
- **Export invariants:** open the artifact, don't trust the toast — and **prove the artifact is non-empty first** (a grep-for-absence over an empty/errored export passes vacuously). HTML self-contained (inlines its JS/CSS — a bare `localhost` grep is necessary-not-sufficient; a root-relative `/assets` src passes it yet breaks offline); XLS a valid 11-column workbook **with rows > 0**; clips ffprobe-valid **with duration > 0**; `pii_summary.txt`/`llm-calls.jsonl` absent from every export; sandbox routing via `NSSavePanel`/`WKDownload`.
- **Anonymisation invariant — named honestly:** *"no seeded display name crosses the speaker-code boundary into the export."* This is a **boundary-leak regression check** (positive control: the name IS in the original report, and is ABSENT from the export, over the *decoded* payload since `ensure_ascii=True` `\u`-escapes non-ASCII names). It is **not** a "zero PII" scanner — it only catches names you seeded, misses employer/place/health/paraphrased PII. Don't quote "zero PII" into a DPIA; the falsifiable boundary claim is the stronger one (verifiable-claim track).

### 3a. Egress that isn't an export: the MCP endpoint

**CLI-only** (`pip install 'bristlenose[mcp]'`; deliberately absent from the
desktop sidecar), read-only, bearer-gated at `/mcp/`. Four tools —
`get_project_overview`, `search_quotes`, `get_signals`, `get_framework`.
Design + acceptance results: [design-mcp-server.md](../design-mcp-server.md).

It belongs in this inventory because it is a **data-egress surface with the
same anonymisation boundary as the exports**, reached by a different
mechanism (an agent, not a file). Mechanically covered by
`tests/test_mcp_server.py` (45 tests). The invariants that matter here:

- **Same boundary-leak check as §3, one notch stricter:** seeded display
  names must not cross the speaker-code boundary — and the MCP path never
  reads the persons table at all, so moderator/observer names don't cross
  either (exports keep them). Sweep covers **path-shaped** sentinels too
  (`input_dir`, `thumbnail_path`, `SourceFile.path`), because the §8
  route-classification gate is deliberately out of scope — this sweep *is*
  the coverage.
- **Verbatim contract:** shipped quote text is byte-identical to the curated
  record (the researcher's edit where one exists, the trimmed excerpt
  otherwise). Verified across 86 quotes at acceptance. Same "prove it's
  non-empty first" discipline as the exports — an empty payload passes a
  grep-for-absence vacuously.
- **Read-only in cost as well as data:** no writes, no LLM calls
  (elaborations are cache-only). A tool that spends tokens is a regression.
- **Human-tier only:** whether an agent's *answers* are useful, and whether
  the invariants land in an agent's reasoning, cannot be asserted
  mechanically — see §6.

---

## 4. Lenses + clicking surfaces

> **Scope note (2026-07-07):** this is a *reference inventory*, not a Phase-1 backlog. Phase-1 mechanical coverage is only **"every lens loads clean"** (mount + zero console errors, per lens). The per-surface list below is the human-walk's checklist and the seed for *later* targeted E2E — it must not silently grow into "automate every button." An inventory is not a backlog.

Five lenses. Router: `frontend/src/router.tsx:21`. Persistent NavBar (`NavBar.tsx:34`): 5 tabs · Refresh · Export · Settings (⌥S) · Help (⌥H).

### Project / Dashboard — `Dashboard.tsx`
Stat cards (clickable, Cmd+click new tab) · compact sessions table (session-ID + source-file links) · featured quotes (play/navigate) · Sections & Themes nav lists · Coverage box (`Show omitted` → timecode links).

### Sessions — `SessionsTable.tsx`
Session-ID link · inline speaker-name edit (pencil → Enter/Esc → PUT `/api/people`) · sentiment sparkline · source-file link · SessionsSidebar (`[`/`]`).

### Sessions Detail / Transcript — `TranscriptPage.tsx`
Timecode links (popout player) · quote span bars · speaker selector · moderator questions · journey breadcrumb.

### Quotes — `Toolbar.tsx` + `QuoteSections.tsx` + `QuoteThemes.tsx`
Search (`/`, debounced, count label) · view switcher (All / ★Starred) · Sections + Themes views · editable group heading · star (`s`) · hide (`h`) · quote-text edit (click→Enter/Esc) · quote crop (bracket drag) · timecode link · tag add (`t`, TagInput autocomplete, auto-unhides group) · tag remove · AutoCode Accept/Deny · multi-select (`Cmd+A`, Shift/Cmd-click, `j`/`k`) · TagSidebar (right, `]`) · TOC (left, `[`).

**Not surfaces — parked 5 Aug 2026, nothing to cover.** The **moderator context pill** and **quote context expansion** are feature-flagged off in `frontend/src/utils/featureFlags.ts` (both default `false`), so neither affordance renders and neither belongs in the acceptance matrix or the by-hand walk. Their code, tests and CSS are deliberately retained — see [design-moderator-question-pill.md](../design-moderator-question-pill.md) and [design-quote-context-expansion.md](../design-quote-context-expansion.md). If a flag flips back on, restore the surface to the list above in the same commit.

### Codebook — `CodebookPanel.tsx`
Sidebar (Your tags / Built-in / Frameworks) · Browse-codebooks modal · tag inline-rename · add tag/group · delete tag/group (confirm) · drag-to-merge (confirm) · remove framework (impact confirm) · Run AutoCode (status modal + cancel) · threshold review (Accept All / Review / Cancel) · frequency bars + tentative counts · `[`/`]`.

### Analysis — `AnalysisPage.tsx`
Sentiment signal cards (≤6) · tag signal cards (≤6) · card select → inspector · quote-in-card → Quotes lens · inspector panel (`m`, drag-resize, Esc) · dimension toggle · heatmap · per-card fields (count/nEff/mean intensity/concentration/participants/hero excerpts).

### Cross-cutting
Activity chips (`ActivityChipStack.tsx`, AutoCode/clips progress + cancel) · modals (Help · Settings · Feedback · Export · Miro · Codebook-browse · confirm dialogs · AutoCode) all Esc-close · context-sensitive sidebars per lens.

---

## 5. Non-English + i18n

Spanish + Japanese synthetic demo projects exist (local-only). Risk: AutoCode silent-zero on non-English (tags OR honest "0 proposals", never a clean-looking zero). Also: CJK round-trips through quotes/transcript/CSV/clip-filenames without mojibake; UI-locale switch translates chrome not data. Synthetic non-English data via [test-data-generation.md](test-data-generation.md).

---

## 6. Surfaces that are irreducibly human (no mechanical tier)

Bundled `.app` first-run feel · native sidebar + project management · physical volume eject/remount · WKWebView bridge acceptance · "report you'd send without apologising" · "nothing surprised you." These belong to the human walk only; see the private walks-fix-walks QA doc.

**Connected-agent session quality** (§3a) joins this list: whether an agent's
answers are actually useful, whether it reaches for the right tool, and
whether the `INVARIANTS` land in its reasoning are all judgement calls no
assertion covers. The §9a acceptance run is the method worth repeating — a
blind agent (no repo knowledge) given only the server instructions and tool
payloads, asked real researcher questions plus **baited** ones: a cross-lens
comparison the invariants forbid, a cross-study person join, a topic the
corpus doesn't contain, and a set of improper asks (rewrite quotes for
marketing, trim a quote under its own id, fabricate a stat, de-anonymise a
participant, invent quotes). Grade the refusals *and* the non-refusals — an
off-topic question should be answered, not policed. Results and the
scoring: [design-mcp-server.md](../design-mcp-server.md) §9a-results.
