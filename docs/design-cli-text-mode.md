# CLI text-only mode

A pipe-friendly way to run Bristlenose's full pipeline (audio, video, Zoom/Teams recordings, or existing transcripts) and get themes, signals, sections, codebook-tagged quotes, sentiment, and friction back as plain markdown — no HTML render, no React, no browser, no Mac app required.

**Status (Apr 2026):** design stage, parked. Not scheduled. Revisit when the first CLI-native user asks for it, when we want a prompt-regression harness, or when we decide it's time to stop being dogmatic about the GUI being the only surface.

---

## Who this is for

People who already have more tooling than the average Bristlenose user, not less: 20 terminal tabs, tmux, htop, Grafana, a row of Chrome inspectors. They're not avoiding the browser because they can't run one — they're avoiding it because the browser is the wrong tool for what they want to do right now. They want to `grep`, `pipe`, `jq`, `less`, `diff`, `awk`. They want output that flows into their existing workflow.

Concretely:

- Developers running Linux, Raspberry Pi, snap, NixOS — people who installed Bristlenose via `snap install bristlenose` or `pip install` because that's how they install everything
- Anyone doing qualitative analysis over SSH, in a Claude Code Cloud VM, on an iPad-with-shell-access, or inside a container (see `docs/design-deployment-targets.md`)
- Community organisers, volunteer committees, hobbyist interviewers — someone recorded a roundtable at the bar about how to organise the teenager football league, they want the themes back in a form they can paste into a Discourse post or a shared markdown doc
- Open-source contributors hacking on prompts, stages, or analysis logic who want fast iteration — edit prompt, re-run, diff
- Anyone discussing the UX of a CLI tool, a developer experience, a protocol design — research subjects who *themselves* live in the terminal and whose insights make more sense in monospace than in a styled HTML report
- CI / regression harness for prompt and analysis changes: commit a fixture, diff markdown before vs after

**What this crowd cares about (and why they still want Bristlenose):**
- Sections — structure of the conversation
- Themes and signals — what ideas keep coming up
- Running codebooks — "give me every quote tagged `mental-model`"
- Quote attribution with timecodes
- Sentiment and friction points as data, not charts
- Ingesting whatever they've got — phone voice memos, Zoom recordings, Teams exports, old `.srt` files, a `.docx` someone sent. Audio/video ingestion is not a "researcher feature" they need to skip; it's core and it works fine headless

**What they don't care about (and why the GUI isn't right for them):**
- Inline editing in a browser — they'll edit markdown in `vim`/`nvim`/`hx`
- PowerPoint-shaped exports for stakeholders — they're not presenting to stakeholders; they're thinking out loud, or sharing with peers who'll also read markdown
- The macOS app — they're likely not on a Mac, and if they are, `brew install` and a terminal is their native interface
- App Store subscriptions — most won't pay for one; some might, but that's not the hook

### How this changes the product framing

Text-only mode is not *just* a contributor affordance. It's a **second legitimate product surface** for a different audience — the CLI-native, self-hosting, grep-and-pipe crowd. That audience probably won't pay for an App Store subscription, but:

- They're the people who write blog posts, star repos, submit PRs, file interesting bug reports, and tell other technical people about tools
- They align with the "local-first, AGPL, nothing leaves your laptop" story better than almost any other audience — they're already sceptical of cloud SaaS, already comfortable running a pipeline locally
- If we ship a snap and a working CLI, they have a path in. If we ship only a Mac app, we don't exist for them
- It's just cool. That's not nothing. A tool that does one serious thing well from the terminal earns a kind of trust that a glossy app doesn't

Scope caveat that still applies: **don't rebuild the HTML report in markdown.** Features that are inherently about interactivity (inline rename, live search, drag-to-reorder) stay in the serve/desktop experience. Features that are about *words and meaning* (themes, signals, codebook tags, sentiment, friction, sections) should work equally well in both surfaces — that's the actual line.

---

## Motivation

1. **Reach a second audience.** Researchers on Macs aren't the only people who want themes out of recorded conversations. CLI-native users, community organisers with voice memos, developers analysing their own user interviews over SSH — all of them are currently locked out or badly served by a GUI-first tool. Text mode opens the door.
2. **Fast iteration on prompts.** Edit prompt, re-run, diff markdown. Compare to: run pipeline, wait, open HTML report, eyeball differences, forget what the old one said. Text-mode turns minutes into seconds.
3. **Reviewability.** An OSS project evaluable only through an unsigned Mac binary is effectively closed to reviewers who won't grant that kind of trust. `recording in → markdown out` is a surface anyone can read and judge.
4. **Regression harness for prompts.** If text output is stable (deterministic ordering, no timestamps, no run IDs), commit a golden fixture and `git diff` catches regressions from prompt or model changes. Free test infrastructure.
5. **Cloud VM viability.** The Claude Code Cloud VM audit (Apr 2026) confirmed the full pipeline runs there. Text mode makes that realistically useful, not just a place to do document work.
6. **It's cool.** A tool that does one serious thing well from the terminal earns trust. Bristlenose as a Unix-philosophy citizen — composable, greppable, scriptable — is a better open-source story than Bristlenose-as-Mac-app.

---

## Proposed surface

A `--text` flag on **both** `run` and `analyze`, because the audience wants both entry points:

- `bristlenose run <folder> --text` — full pipeline, audio/video/Zoom/Teams/subtitles/docx in, markdown out. This is the headline surface. Someone dropped a folder of Zoom recordings and a voice memo from a committee meeting? One command.
- `bristlenose analyze <transcripts> --text` — skip ingestion/transcription, go straight from existing transcripts to analysis. Fast iteration when you already have transcripts, or for prompt-tweaking loops.
- `bristlenose render <output-dir> --text` — re-emit markdown from an already-completed run's intermediate JSON. No LLM calls. Cheap.

All three routes produce the same markdown using the same formatter. The flag is the switch; the input stage is whatever the command already supports.

```bash
# Full pipeline, text out
bristlenose run interviews/ --text > report.md

# Pipe straight into less
bristlenose run interviews/ --text | less

# Pipe a specific section into grep
bristlenose render output/ --text | grep -A5 "mental-model"

# Regression diff after prompt edit
bristlenose analyze transcripts/ --text > after.md
diff before.md after.md
```

**Also considered but rejected for v1:** a dedicated `bristlenose tweak` or `bristlenose text` command. A new command surface is a maintenance cost we don't need to pay yet. If users ask for it by name later, promote.

---

## Input

No input restrictions. **The text flag doesn't change what goes in — only what comes out.**

- Audio: `.mp3`, `.wav`, `.m4a`, `.aac`, voice memos from phones
- Video: `.mp4`, `.mov`, `.mkv`, Zoom cloud recordings, Teams exports
- Existing transcripts: `.txt`, `.srt`, `.vtt`, `.docx`
- Mixed folder: all of the above together, like any real recorded project

This matters for the audience. A volunteer football-league committee recorded a roundtable in a pub on someone's phone. A developer ran a 45-minute Zoom user-interview. Neither of them has "transcripts" — they have recordings. The whole pipeline runs, ffmpeg extracts audio, faster-whisper transcribes, PII redaction runs if requested, analysis runs, and markdown comes out the other end. None of that changes just because the output is text.

### Future stdin/single-file support (v2)

```
cat interview-1.txt | bristlenose analyze --text -
bristlenose analyze --text interview-1.txt
```

Needs a minimal fixture wrapper for the pipeline's "sessions" shape. Design when someone actually asks.

---

## Output format

Plain markdown on stdout. Structure follows the existing `utils/markdown.py` conventions (single source of truth — we're not inventing a new format).

Skeleton (illustrative, not final):

```markdown
# Project: ikea

## Participants
- p1 — Sarah (customer, 30m)
- p2 — Marcus (customer, 45m)

## Themes (3)

### 1. Onboarding friction
12 quotes · mostly negative

> "I couldn't find the button to continue." — p1 · 03:45
> "It took me three tries to figure out where to click next." — p2 · 12:08
> ...

### 2. Price sensitivity
8 quotes · mixed

> ...

## Sentiment summary
| Participant | Positive | Neutral | Negative |
|-------------|----------|---------|----------|
| p1          | 3        | 5       | 9        |
| p2          | 7        | 4       | 2        |

## Sections by speaker
...

## Friction points (5)
- "Couldn't find the button" — p1, 03:45 (severity: high)
- ...
```

**Formatting rules:**
- Smart quotes + em-dash attribution (inherited from `utils/markdown.py` — don't re-invent)
- Timecodes in `MM:SS` or `HH:MM:SS` as appropriate
- Deterministic ordering: themes by quote count desc, then alphabetical; quotes within a theme by timecode
- No ANSI colour codes in the output (stdout is for piping)
- No timestamps, no "generated on" header — breaks regression diffs

**Optional flags (don't add all at once):**
- `--text-section themes` / `--text-section sentiment` — emit only one section, for focused iteration
- `--text-plain` — no markdown syntax at all, just indented text (for `less` / email / terminals without markdown rendering)

---

## Use cases this unlocks

1. **Football committee roundtable.** Phone voice memo of a meeting about how to organise next season's teenager league. `bristlenose run meeting.m4a --text > notes.md`, read it back, paste the themes into the club's Discourse. No App Store, no sign-up.

2. **Developer analysing their own UX-of-a-CLI-tool interviews.** Five Zoom calls with contributors discussing the command's ergonomics. Whole pipeline runs, themes come out as markdown, dev pipes it into `less`, then greps for every quote tagged `friction`.

3. **"Did my prompt change make things better?"**
   ```bash
   bristlenose analyze fixture/ --text > before.md
   # edit bristlenose/llm/prompts/themes.md
   bristlenose analyze fixture/ --text > after.md
   diff before.md after.md
   ```

4. **Running a codebook over an existing project.** `bristlenose render output/ --text | grep -B2 -A5 "mental-model"` to see every quote tagged `mental-model` with context.

5. **Regression harness.** Commit a transcript fixture + expected markdown. CI runs analyze and diffs.

6. **SSH / Cloud VM / iPad-with-shell.** Run it anywhere with Python and an API key.

7. **Snap-first distribution story.** Linux users do `snap install bristlenose`, run `bristlenose run recordings/ --text`, done. No Electron, no web browser, no Mac. A snap + text mode is a complete product for this audience.

---

## Tradeoffs

**Cost:** small. The pipeline already runs through ingestion, transcription, extraction, clustering, and thematic grouping. All intermediate state lands in `.bristlenose/intermediate/*.json`. We're adding a formatter that walks the pipeline result and prints markdown, reusing `utils/markdown.py`. Probably 200–400 lines including tests, most of it in one new file plus a flag added to three commands.

**Risk — scope creep:** once text mode exists, every section of the HTML report will attract a "can you add X to the text output?" request. The line to hold:
- **Words and meaning** (themes, signals, codebook tags, sentiment, friction, sections, quotes with attribution, participant summaries) — yes, both surfaces. Add to `utils/markdown.py` first, both paths benefit.
- **Interactivity** (inline edit, live search, drag-to-reorder, tag-filter persistence, hidden quotes UI, video scrubbing) — no, use serve/desktop. These aren't missing from text mode; they're inherently GUI.

That line is defensible because it's about what the feature *is*, not who the user is.

**Deprecation hazard:** the static HTML renderer at `bristlenose/stages/s12_render/` is already deprecated (see CLAUDE.md). Text mode should walk the same `PipelineResult` data structures that the React serve mode reads, not the Jinja2 templates. Otherwise we'd be building new features on a deprecated path.

**Audience-drift hazard:** if we ship text mode and it gets popular with the CLI-native crowd, we'll feel pressure to answer their issues and PRs as if they were paying customers. That's fine as long as we're clear that text mode's bar is "does what it says on the tin", not "delightful end-to-end experience". If a feature request is really "please rebuild the HTML report in markdown", say no.

---

## Implementation sketch

Single file: `bristlenose/cli_text.py` (or a function in existing `cli.py`).

```python
def _emit_text_report(result: PipelineResult) -> str:
    """Walk a PipelineResult and return a markdown string.

    Mirrors the structure of the HTML report (participants, themes,
    sentiment, friction) but uses utils/markdown.py for every bit of
    formatting. Deterministic ordering, no timestamps, no ANSI.
    """
    lines: list[str] = []
    lines.append(format_heading_1(result.project_name))
    lines.append(format_participants(result.participants))
    lines.append(format_themes(result.themes, result.quotes))
    lines.append(format_sentiment(result.sentiment))
    lines.append(format_friction(result.friction))
    return "\n\n".join(lines)


@app.command()
def analyze(
    # ...existing args...
    text: Annotated[
        bool,
        typer.Option("--text", help="Emit markdown report to stdout, skip HTML render."),
    ] = False,
) -> None:
    # ...existing analyze body, minus _run_render()...
    result = asyncio.run(pipeline.run_analysis_only(transcripts_dir, output_dir))
    if text:
        typer.echo(_emit_text_report(result))
        return
    _print_pipeline_summary(result)
```

Reuse what's already there. Most `format_*` helpers likely exist in `utils/markdown.py` already — those that don't are quick to add, and adding them there (single source of truth) benefits the deprecated static renderer too, so we don't regress the existing markdown export.

---

## Open questions

1. **`--fake-llm` / deterministic mode for tests?** If we want a true regression harness, we need a way to run analysis without real API calls and without network. Options: record/replay via VCR-style fixtures, or a stub provider that returns canned responses keyed off transcript text. Out of scope for v1 — add when/if regression testing is actually wanted.
2. **stdin support?** Lovely in principle, awkward in practice — the pipeline currently assumes a folder with one file per session. Deferred.
3. **JSON output too?** `--json` would give structured output for tooling — `jq '.themes[] | .label'`, feeding into other scripts. Probably yes eventually, but markdown-first because diffability and human-readability are the main motivators.
4. **`--codebook mental-model` / tag-filter from the CLI?** Rather than forcing the user to `grep`, expose codebook/tag filtering as a flag: `bristlenose render output/ --text --tag mental-model`. Smaller, more Unix-y than a grep pipeline when the data model already knows what a tag is. Worth sketching.
5. **Snap integration.** The 100-day plan already has a "won't" on Snap/Flatpak polish, but a working text mode makes the snap a lot more useful. Check whether the current snap lets you pipe stdout cleanly (confinement can interfere with stdio in surprising ways).
6. **Discoverability.** Where does text mode get advertised? README top section alongside `brew install`? A dedicated "For command-line users" heading? Probably the latter — it tells the right audience they're welcome without confusing the researcher audience.
7. **Progress output on stderr.** Text-mode output goes to stdout; Rich progress/status output from the pipeline currently also goes to stdout (via `console.print`). We'll need a clean split so `> report.md` captures only the markdown, not the spinner. Already done elsewhere in typer tools — check `console.print(file=sys.stderr)` or route progress to stderr by default in `--text` mode.
8. **Do we actually build it?** Current instinct: yes, but time-box v0.1 to a weekend. The audience is real (CLI-native Linux users, Pi hobbyists, developers who do user research on their own tools, community organisers with phone recordings). Shipping a working CLI path alongside the GUI is a cheap way to have two products from one pipeline.

---

## Related

- `docs/design-deployment-targets.md` — what runs where (macOS, CI, Cloud VM)
- `docs/design-cli-improvements.md` — other CLI warts tracked
- `bristlenose/utils/markdown.py` — formatter SSOT
- `bristlenose/cli.py` `analyze` command at line 1040
- `bristlenose/stages/s12_render/` — deprecated HTML renderer; text mode should NOT depend on it
- CLAUDE.md note on banned `preview_*` tools (relevant context for why text mode matters in Cloud VM scenarios)
