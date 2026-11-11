---
status: proposal
updated: 11 Nov 2026
---

# Export transcripts

> **Status: a proposal, post-beta, nothing built.** Owner direction, 11 Nov 2026: "I don't think users are
> messing around in the raw transcripts folders very much; the right thing to do is to offer an export
> transcript(s) menu item in the share menu from the transcripts grid and each transcript with a range of
> sensible formats like vtt, md, docx." The app's own word for these menus is **Export** (the toolbar's export
> popover and File ▸ Export…), so this doc says Export where the owner said "share".
> It answers a question about `transcripts-raw/` (decision #120: that folder is raw, rewritten by `run`, and
> not the researcher's to edit): the supported way to take a transcript out is an export, not the folder.

## Positioning (owner, 11 Nov 2026)

For v1 the majority case is a researcher who **already has the transcripts** from Teams, Zoom or Meet.
Transcription is a commodity and not what Bristlenose is valued for, so exporting transcripts is **an elegant
convenience, worth doing only if it is done well**, not a headline feature. That shapes the design:

- **Small and cheap.** Reuse what exists (the loader extraction, the subtitle serialisers, python-docx). No new
  engine, no new surface beyond one menu item and a format choice. If it needs more than that, it waits.
- **The value is in the edits and the consistency, not the text.** For a study built from platform transcripts
  the original file is already in the researcher's input folder, so an export adds nothing unless they changed
  something here (renamed speakers, split or joined paragraphs, re-attributed a turn) or want the same format
  across studies that came from different platforms. For a recording Bristlenose transcribed itself, the
  export is the only transcript they have.
- **Don't overwrite the original's character.** An export of a platform transcript is Bristlenose's rendering
  of it (paragraphs, labels), not the platform's file. The copy should not suggest otherwise.
- **Ranked below the core.** It sits behind the lenses, the report and the exports researchers use to share
  findings. It earns its place by being quick to build on the pieces above and hard to get wrong.

## Why

Today a researcher who wants a transcript reaches for **Quotes ▸ Show Transcripts in Finder**, which opens
`transcripts-raw/`: files named `s1.txt`, in the pipeline's format, without the corrections they made in the
report (speaker renames, splits, joins, re-attributed paragraphs), and with a README telling them not to edit
them. That is a poor deliverable. What they want is the transcript **as they see it**, in a format their next
tool reads (a subtitle player, a word processor, a QDA tool, a colleague's inbox).

## What already exists (investigated 11 Nov 2026)

Most of the pieces are there. The gap is one loader and a few serialisers.

**The data, with the researcher's edits applied.** `bristlenose/server/routes/transcript.py`
`get_transcript` (lines ~203–443) builds the transcript page: segments in reading order from
`transcript_layout.ordered(db, session_pk)` (the order that already has splits, joins and re-attributions
applied), speakers from `speaker_slots.session_slots` (name or code per slot), session metadata, and the
quote annotations. It is one long route function, not a reusable loader. **The first piece of work is to
extract the "ordered paragraphs with speaker labels" part into a function the route and the export share.**

**Serialisers, partly there.**
- **Plain text and Markdown:** `bristlenose/utils/markdown.py` holds the single style template, and
  `stages/s06_merge_transcript.py` `write_raw_transcripts` / `write_raw_transcripts_md` write them from
  pipeline objects (before the database, so without the researcher's edits). The templates are reusable; the
  writers are not, because they take pipeline objects.
- **WebVTT and SRT:** `bristlenose/server/clip_subtitles.py` is pure logic (no database, no filesystem):
  `to_webvtt`, `to_srt`, `build_cues`, word timings via `tokens_for_segment`, and a proportional spread of a
  segment's text over its time when the transcript has no word timings (platform transcripts, redacted
  projects). **Its cue rules do not fit a transcript:** it follows the BBC subtitle guidelines for burned-in
  clips (two lines, 37 characters, no speaker labels, speakers told apart by colour). A transcript export
  wants a cue per paragraph, longer, with the speaker named. So reuse the timestamp formatting, the
  serialisers and the timing logic; write a different cue builder.
- **DOCX:** `python-docx` is already a dependency (`pyproject.toml`), used to read Teams and Google Meet
  exports (`s04_parse_docx.py`). Writing a `.docx` is new but uses the same library.
- **CSV and XLSX:** `routes/quotes_export.py` with `export_core.py` shows the delivery pattern: a `GET` that
  streams a file with a safe `Content-Disposition` (`export_core.attachment_disposition`), `csv_safe`,
  `excel_sheet_name`, and an `anonymise` query flag. Not for transcripts, but the same shape.

**Anonymise, with an established rule.** `export_core.extract_quotes_for_export(..., anonymise=True)` blanks
the participant name. The HTML export's `_anonymise_data` blanks participant speaker-name fields only
(shallow); moderator and observer names stay, by decision (design-people, §E decision 2); names that appear
inside the text are not touched (decision T30, post-v1). The clip export already warns in plain words that
clips carry the original audio. A transcript export follows the same rule and says the same kind of thing.

**Delivery patterns already in the product.** Quotes: a file download. Clips: a background job that writes a
**folder** and reveals it (the owner's rule: a folder, not a zip). HTML report: a download via an anchor
(`ExportDialog.tsx`, no fetch, cookie auth), with a save panel on the Mac whose accessory view carries the
Anonymise checkbox. The Mac surfaces: the toolbar export popover (rows for quotes, clips, Miro, FigJam) and
File ▸ Export Report… / Export Screens…, routed through `bridgeHandler.menuAction`.

**An earlier design.** The superseded `docs/design-export-sharing.md` ("Transcript export details") already
specifies the `.txt` shape (a header, `[mm:ss] Speaker: text`), human filenames (`{code} {name}.txt`, with
a session-number prefix for several speakers), anonymised filenames (`p01.txt`), moderator names kept, role
titles dropped, and says the renderer should reuse `utils/markdown.py`. `design-export-html.md` Stage 1
planned "Include transcripts (.txt)" in the report zip; I did not check whether that shipped.

## Every idea, as a possibility, with where it came from

A merged list of everything proposed for this, so you can see which ideas are old and which are new.
**Early** = the February–March 2026 sketches, never built. **Existing** = a decision or code already in the
tree. **New** = 11 Nov 2026 (owner direction or this investigation). Nothing in the list is committed to.

| Idea | Age | Where it came from |
|---|---|---|
| Plain text, `[mm:ss] Speaker: text` with a header | Early | Sketch in the superseded export-sharing doc, 5 Feb 2026. Pipeline writers for raw files exist (`s06_merge_transcript`). |
| Markdown, bold speaker labels | Existing | `write_raw_transcripts_md`; style template in `utils/markdown.py`. |
| WebVTT | New | Owner, 11 Nov. The serialiser exists from 29 Sep 2026 (`clip_subtitles.to_webvtt`). |
| SRT | New | Added in this investigation, same day. Serialiser exists (`to_srt`). |
| DOCX | New | Owner, 11 Nov. `python-docx` is already a dependency (reads Teams and Meet exports). |
| Participants as codes when anonymised; moderators and observers keep names | Existing | design-people §E decision 2; the HTML export's anonymise rule. |
| Role titles dropped when anonymised | Early | 5 Feb 2026 sketch. |
| Source file name shown as `[REDACTED]` when anonymised | Existing | Cooked transcripts, 1 Oct 2026. |
| Names inside the text left alone, with a plain-words warning | Existing | Decision T30 (9 Nov 2026); the clip export's `piiWarning`. |
| Redacted projects export the redacted text only | New | Follows the existing rule; stated here. |
| Researcher quote corrections not applied to the transcript | New | This investigation. Open question 1. |
| Filenames `{code} {name}`, a session-number prefix for several speakers, `p01` when anonymised | Early | 5 Feb 2026 sketch. |
| Several transcripts as a folder of files, not a zip | Existing | The owner's clip-export rule. |
| Transcripts bundled as `.txt` inside the report zip | Early | design-export-html Stage 1, 25 Mar 2026; the doc still calls it aspirational. |
| An Export popover row plus a File ▸ Export Transcripts… twin | New | This investigation; the pairing every other export has. |
| Reachable from the Sessions grid and from an open transcript | New | Owner, 11 Nov. |
| A remembered format choice | New | This investigation; the burn-in subtitles preference (29 Sep 2026) is the pattern. |
| Retitle "Show Transcripts in Finder" once this exists | New | This investigation. |
| README in `transcripts-raw/` mentions `analyze` | New | Found 11 Nov when checking the README was true. |
| One shared loader extracted from the transcript page route | New | This investigation. The one risky edit. |
| Classify the new route in `routes/export.py` | Existing | A repository rule, enforced by `test_serve_export_coverage.py`. |
| A `bristlenose` CLI verb for it | New | This investigation; out of scope. |
| Positioned as a small convenience, not a headline | New | Owner, 11 Nov. |

## Proposal

### One loader, several writers

```
load_export_transcript(db, project_id, session_id, *, anonymise) -> ExportTranscript   # server-side, the one place
render_txt(t) / render_md(t) / render_vtt(t) / render_srt(t) / render_docx(t) -> bytes  # pure functions
```

- `ExportTranscript` is a frozen dataclass (as `clip_subtitles` uses): session code, date, duration,
  project name, and a list of paragraphs (start, end, speaker code, display label, text, optional word
  timings). Everything format-specific lives in the writers; nothing in them touches the database.
- The transcript page route calls the same loader for its ordered paragraphs, so the page and the export cannot
  disagree about what "the transcript" is. That extraction is the one risky edit (a working route), so it goes
  first and is pinned by the existing transcript tests.
- Formats: **plain text** (the earlier design's shape), **Markdown** (bold speaker labels), **WebVTT** (a cue per
  paragraph, speaker as a `<v Name>` voice tag), **SRT** (a cue per paragraph, `Name:` prefix, since SRT has no
  voice tag), **DOCX** (title, metadata line, then paragraphs with a bold speaker run and the timecode).
  One list of formats, declared once and read by the route, the web app and the Mac (the seams rule).

### Content rules

- **Reading order and edits:** exactly what the transcript page shows (splits, joins, re-attribution, names).
- **Speaker label:** the identity's name, or its code when Anonymise is on. Participants anonymise; moderators
  and observers keep their names (the standing rule); role titles are dropped when anonymised.
- **Redaction:** when PII redaction is on, the database already holds the redacted text; the export never reads
  the unredacted files.
- **Source file name and header:** omitted or shown as `[REDACTED]` when anonymised (the cooked-transcript
  precedent), since a recording's file name can identify a person.
- **Names inside the text are not changed**, as with every other export (T30). The export says so in plain
  words, as the clip export does.
- **Researcher quote corrections** (a fixed acronym on a quote): not applied in v1. They belong to quotes, and
  a transcript that silently differs from the recording is the wrong default. (`clip_subtitles` does apply them,
  by word diff, because a subtitle must match what is on screen. Open question 1.)

### Names and delivery

- One transcript: one file, named `{code} {name}.{ext}` (anonymised: `p01.{ext}`), through the platform's save
  panel on the Mac and a download in the browser.
- Several transcripts: a **folder** of files (the clips rule) written where the researcher chooses. A browser
  download of many files is the one place a zip is the only way to answer a single request; decide with the
  folder rule in mind (open question 2).
- Filenames use `safe_filename()` and the "as typed" rule; the Anonymise flag changes the name too.

### Where it lives (UI, behind the UX gate)

- **Toolbar export popover** and **File ▸ Export Transcripts…**, the same pairing every other export has
  (a menu twin of the popover row).
- Reachable **from the Sessions grid** (the selected sessions, or all) and from **an open transcript** (that
  one). Today's per-lens routing of Export applies.
- A **format choice** that is remembered, the way the burn-in subtitles preference is (`subtitlePrefs.ts`),
  and the existing **Anonymise checkbox** on the save panel's accessory view.
- **Quotes ▸ Show Transcripts in Finder** stays, but should be retitled to say what it opens (the raw files),
  once this exists. The README in that folder tells the truth for `run` and the Mac app (the merge stage
  rewrites the folder), but `bristlenose analyze` reads those files as they are; decide whether the README says
  so.
- **New UI needs a mockup and owner approval first** (the 28 Oct UX gate), reusing the existing popover rows
  and save panel, and new strings in all 21 locales.

### Plumbing the repository already enforces

- A new project `GET` route must be classified embed or server-only in `routes/export.py`
  (`tests/test_serve_export_coverage.py` fails otherwise). Transcript export is server-only: the offline HTML
  leave-behind has no export.
- Any new rendered format value is registered in `docs/design-shared-formats.md` or reuses an existing
  formatter (VTT's `HH:MM:SS.mmm` is `clip_subtitles`'s).
- CLI terminal text is English by design. A `bristlenose` verb for it is nearly free, since the writers are
  pure Python, but is out of scope here.

## Phasing

1. **Extract the loader** from the transcript route; pin it with the existing tests. Add the loader's own tests
   (layout edits applied, anonymise, a session with no word timings).
2. **Writers and route:** txt, md, VTT, SRT; one route, `GET /projects/{id}/export/transcripts`
   with `format`, `sessions` and `anonymise`; classify it; golden-file tests per format.
3. **DOCX writer,** with a test that reads it back through python-docx.
4. **UI** (gated): popover row, menu item, format preference, Mac save panel and folder choice, strings.
5. **Several sessions as a folder,** and optionally the CLI verb.

## Tests

Pure writer tests with golden files; a VTT whose cue times are monotonic and parse in a real WebVTT parser; an
SRT likewise; a DOCX read back; the loader against a project whose paragraphs were split, joined and
re-attributed; anonymise (no participant name in the file body, header or file name; moderators kept); a redacted
project (no unredacted text reachable); the route's classification in the coverage test; and a structural test
that every listed format has a writer, since a name with no runner is a gate that cannot fail.

## Open questions

1. Apply researcher quote corrections to the transcript text? Recommend no for v1.
2. Several sessions: a folder of files (the clips rule), a zip, or both by platform?
3. VTT speaker syntax: `<v Name>` voice tags (the standard, ignored by some players) or a `Name:` prefix
   everywhere? SRT has no voice tag, so it takes the prefix regardless.
4. DOCX: how much styling (title page, a table of timecodes), or plain paragraphs? A researcher's next step is
   usually pasting into their own document.
5. Keep **Show Transcripts in Finder**, retitle it, or fold it into this export?
6. Does the README in `transcripts-raw/` mention `analyze`?
7. Does the Sessions grid selection model already give "the selected sessions" to an export, or only a single
   session?

## Related

`design-export-quotes.md` (CSV/XLSX, selection, anonymise), `design-export-clips.md` (the folder rule, subtitles),
`design-export-html.md` (the report export and its anonymise pass), `design-people.md` (§E decision 2: moderators
keep their names), `design-shared-formats.md` (formats that must agree across languages), and
`design-export-sharing.md` (the superseded monolith with the earlier transcript-export sketch).
