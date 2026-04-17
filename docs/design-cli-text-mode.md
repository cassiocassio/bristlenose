# CLI text-only mode

A pipe-friendly way to run Bristlenose's LLM analysis against a transcript and get themes, sentiment, quotes, and sections back as plain markdown — no HTML, no React, no browser, no Mac app required.

**Status (Apr 2026):** design stage, parked. Not scheduled. Revisit when the first external contributor asks how to iterate on prompts without spinning up the full desktop app, or when we want a regression harness for prompt changes.

---

## Who this is for (and who it isn't)

**For:**
- Open-source contributors hacking on prompts, stages, or analysis logic who don't want to install Node, Vite, Xcode, or run a browser
- Anyone doing a quick sanity check on a prompt change over SSH or in a Claude Code Cloud VM (see `docs/design-deployment-targets.md`)
- CI / regression harness for prompt and analysis changes — diff markdown before vs after a prompt tweak
- Researchers on an iPad or a stripped-down environment who just want to see the raw output of the pipeline

**Not for:**
- The 99% of user researchers who bought Bristlenose for the desktop app or the browser-based serve mode. Text-only mode is a **contributor affordance**, not a product surface. It should never be promoted as the main way to use Bristlenose, and the researcher docs should not mention it in the main flow.

This distinction matters because it shapes the scope: we're building a Unix-ish tool for engineers, not a second product. The bar is "works well enough that an OSS contributor can iterate", not "works well enough to ship to paying customers".

---

## Motivation

1. **Contribution barrier.** Right now, evaluating a prompt change means: run the full pipeline, wait, open the HTML report in a browser, eyeball it. For small prompt tweaks that's heavyweight. A text dump would let contributors see the effect in seconds.
2. **Reviewability.** An OSS project that can only be evaluated through a Mac app is effectively closed to reviewers who don't want to grant an unsigned binary access to their machine. `transcripts in → markdown out` is a surface you can read.
3. **Regression harness for prompts.** If text output is stable (deterministic ordering, no timestamps), you can commit a golden-output fixture and `git diff` catches unexpected regressions from prompt or model changes. Free test infrastructure.
4. **Cloud VM viability.** The Claude Code Cloud VM audit (Apr 2026) showed the full pipeline runs there. A text-mode flag makes that realistically usable for pipeline work, not just document work.

---

## Proposed surface

Two candidates, pick one.

### Option A — flag on `analyze`

```
bristlenose analyze transcripts-raw/ --text
```

Reuses the existing command. Writes markdown to stdout (or a user-given file via `-o`). Skips the HTML renderer entirely — no Jinja2, no React. Intermediate JSON still written so you can re-render later.

**Pros:** smallest change, no new command to document, composable (`--text > out.md`).
**Cons:** `analyze` already has many flags. One more.

### Option B — dedicated `tweak` command

```
bristlenose tweak sample-transcript.txt
bristlenose tweak transcripts-raw/
```

A new sibling to `analyze`. Accepts either a folder or a single file. Always emits markdown. No HTML ever. A dedicated "play with text" surface.

**Pros:** discoverable as "the text-mode command", less flag clutter on `analyze`, easier to advertise in the README for contributors.
**Cons:** new command surface to maintain, near-duplicate of `analyze`.

**Recommendation:** **Option A**, initially. If OSS contributors actually use it and ask for a dedicated command, promote to B later. Don't design for a hypothetical audience.

---

## Input

### v1 (minimum useful)

A folder of `.txt` transcripts, exactly as `bristlenose analyze` takes today. The file format is whatever the existing transcript stages produce — plain text with speaker labels and timecodes.

### v2 (nice later, iPad-friendly)

A single `.txt` file via stdin or as a positional arg:

```
cat interview-1.txt | bristlenose analyze --text -
bristlenose analyze --text interview-1.txt
```

Single-file input needs a minimal fixture format — probably just a wrapper that fakes the "sessions" shape the pipeline expects. Design that when someone actually asks for it.

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

1. **"Did my prompt change make things better?"**
   ```bash
   bristlenose analyze fixture/ --text > before.md
   # edit bristlenose/llm/prompts/themes.md
   bristlenose analyze fixture/ --text > after.md
   diff before.md after.md
   ```

2. **Regression harness.** Commit a transcript fixture + expected markdown. CI runs analyze and diffs.

3. **Contributor onboarding.** README snippet: `pip install bristlenose && bristlenose analyze examples/ikea-tiny/ --text` — one command, no Node, no Xcode, no API key (if we also add a `--fake-llm` for a deterministic stub; see Open questions).

4. **SSH / Cloud / iPad.** Run it from anywhere that has Python and an API key.

---

## Tradeoffs

**Cost:** small. `analyze` already runs the full pipeline through quote extraction, clustering, and thematic grouping. All intermediate state is already in `.bristlenose/intermediate/*.json`. We're just adding a formatter that walks the pipeline result and prints markdown, reusing `utils/markdown.py`. Probably 200–400 lines including tests.

**Risk:** scope creep. Once text mode exists, every section of the HTML report will attract a "can you add X to the text output?" request. Two responses ready:
- For researcher-facing features (inline edit, search, CSV export, etc.): "no, use the browser". Text mode is a contributor tool.
- For analysis features (new theme taxonomy, new sentiment dimension): "yes, but add it to `utils/markdown.py` first so both paths benefit".

**Deprecation hazard:** the static HTML renderer at `bristlenose/stages/s12_render/` is already deprecated (see CLAUDE.md). Text mode should not be built on top of it — it should walk the same pipeline result data structures that the React serve mode reads. Otherwise we'd be building new features on a deprecated path.

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
3. **JSON output too?** `--json` would give structured output for tooling. Probably yes eventually, but markdown-first because diffability is the main motivator.
4. **Cross-reference with `bristlenose render`?** `render` already re-emits HTML + markdown from existing intermediate JSON. Text-only could be `render --text-only` instead of `analyze --text`. Worth considering — it'd mean you can re-emit text for an old run without re-running the LLM. Possibly both paths should exist.
5. **Do we need this at all?** Honest check: if no OSS contributors materialise or ask for this, it's dead weight. Hence parking it. Build when someone's waiting for it.

---

## Related

- `docs/design-deployment-targets.md` — what runs where (macOS, CI, Cloud VM)
- `docs/design-cli-improvements.md` — other CLI warts tracked
- `bristlenose/utils/markdown.py` — formatter SSOT
- `bristlenose/cli.py` `analyze` command at line 1040
- `bristlenose/stages/s12_render/` — deprecated HTML renderer; text mode should NOT depend on it
- CLAUDE.md note on banned `preview_*` tools (relevant context for why text mode matters in Cloud VM scenarios)
