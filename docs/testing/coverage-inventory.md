# Coverage inventory — the surfaces we test

_The single source of "what exists to be covered." Consumed by **both** testing tiers: the mechanical [acceptance-matrix.md](acceptance-matrix.md) (assert each surface works, shape-only) and the human walk (judge each surface, feel + correctness). Grounded against code 7 Jul 2026 — re-true when surfaces are added._

When you add an ingest format, an export, a lens, or a provider, add it here first — then both tiers inherit it. Fixture status is tracked here as ✅ *have* / ⚠️ *need*; the concrete fixture-folder mapping lives in the private walks-fix-walks QA doc (real interview data stays out of git).

---

## 1. Ingest formats (16 claimed — README:229 / manual:117)

Four decode paths converge on one transcript. Source: `bristlenose/models.py:97-101`.

| Path | Extensions | Stage | Fixture |
|---|---|---|---|
| Audio → transcribe | `.wav .mp3 .m4a .flac .ogg .wma .aac` | s02→s05 (Whisper) | ⚠️ none |
| Video → extract audio → transcribe | `.mp4 .m4v .mov .avi .mkv .webm` | s01→s02→s05 | ✅ `.mp4`/`.mov`; ⚠️ rest |
| Subtitle → parse (skips transcription) | `.srt .vtt` | s03 | ✅ `.vtt`; ⚠️ `.srt` |
| Transcript → parse | `.docx` (Zoom/Teams/Meet) | s04 | ⚠️ format-parity slot exists, files not produced |

**Key insight (from acceptance-matrix):** transcription is provider-independent, so the media path is *one representative cell*, not a format×provider matrix. Container-decode is a thin ffmpeg/Whisper concern — one clip per container proves the decode path; you don't re-run it per provider.

**Correct layer for format coverage (post-review 2026-07-07):** all 16 extensions collapse to 4 decode paths by suffix (`classify_file`, `models.py:108`). Proving "`.flac` ingests" does **not** need a full LLM leg — that re-runs Whisper+Claude to test a suffix table and a codec. So the 16-format check is a **cheap pytest** (`tests/test_format_ingest_coverage.py`): `classify_file` routes each extension + ffmpeg **re-encodes** (codec-family, not `-c copy` remux) a tiny clip per container and decodes it back (`ffmpeg -f null -`). One representative media `run` (in the acceptance matrix) covers the transcribe→analysis handoff. The genuine *format-parity* question (Teams vs Meet vs Zoom `.docx`/`.vtt` parse-shapes) is where a real LLM leg earns its keep — see §Transcript below.

**Ingest invariants:** same-stem merge (`p1.mp4`+`p1.srt` = one session, subtitle skips transcription — README:231); mixed-format folder; `._*`/`.DS_Store` ignored (`is_os_metadata`, `utils/fs.py`).

**Test-data gap:** the 10 container/subtitle formats are covered by the cheap pytest above (fixtures generated at test-time via ffmpeg — no committed binaries). `.docx` is the one that needs **real** exports (a synthetic docx parses by construction against the Teams-shaped parser `s04_parse_docx.py:16`, proving nothing — the Meet leg specifically tests whether Google Meet's real shape parses). Prefer a **public-domain** source (a FOSSDA transcript → Google Doc → export) over a real client call; regression-pin `git check-ignore` on the gitignored format-acceptance fixture slot. Recipe: [test-data-generation.md](test-data-generation.md).

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
- **`.docx` Word export** — claimed README:288 but not in the toolbar scan. ⚠️ **verify wired or strike the claim.**
- **Export invariants:** open the artifact, don't trust the toast — and **prove the artifact is non-empty first** (a grep-for-absence over an empty/errored export passes vacuously). HTML self-contained (inlines its JS/CSS — a bare `localhost` grep is necessary-not-sufficient; a root-relative `/assets` src passes it yet breaks offline); XLS a valid 11-column workbook **with rows > 0**; clips ffprobe-valid **with duration > 0**; `pii_summary.txt`/`llm-calls.jsonl` absent from every export; sandbox routing via `NSSavePanel`/`WKDownload`.
- **Anonymisation invariant — named honestly:** *"no seeded display name crosses the speaker-code boundary into the export."* This is a **boundary-leak regression check** (positive control: the name IS in the original report, and is ABSENT from the export, over the *decoded* payload since `ensure_ascii=True` `\u`-escapes non-ASCII names). It is **not** a "zero PII" scanner — it only catches names you seeded, misses employer/place/health/paraphrased PII. Don't quote "zero PII" into a DPIA; the falsifiable boundary claim is the stronger one (verifiable-claim track).

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
Search (`/`, debounced, count label) · view switcher (All / ★Starred) · Sections + Themes views · editable group heading · star (`s`) · hide (`h`) · quote-text edit (click→Enter/Esc) · quote crop (bracket drag) · timecode link · tag add (`t`, TagInput autocomplete, auto-unhides group) · tag remove · AutoCode Accept/Deny · moderator context pill · context expansion · multi-select (`Cmd+A`, Shift/Cmd-click, `j`/`k`) · TagSidebar (right, `]`) · TOC (left, `[`).

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
