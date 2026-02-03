# CLI improvements

Catalogue of CLI warts, inconsistencies, and potential improvements. Prioritised by user friction, not implementation difficulty.

---

## High friction (users complain or get confused)

### 1. `render` argument is `INPUT_DIR` but should be `OUTPUT_DIR`

Real session:
```
╰─➤  bristlenose render
╭─ Error ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Missing argument 'INPUT_DIR'.                                                                          │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

The argument is called `INPUT_DIR` but `render` reads from `output/intermediate/`. The user is in `project-ikea/` which contains `interviews/` (input) and `output/` (output). They have to guess that `.` works because the project name gets derived from the current dir.

The actual data flow is:
- `render` reads from `$OUTPUT_DIR/intermediate/*.json`
- `render` writes to `$OUTPUT_DIR/research_report.html`
- The `INPUT_DIR` argument is only used to derive the project name fallback

This is backwards. The positional argument should be the output directory (where the data lives), not the input directory (which isn't read at all).

**Options:**
- (a) Change the positional argument to `OUTPUT_DIR` — breaking change but correct
- (b) Make both optional: `bristlenose render` in a project dir auto-detects `./output/`
- (c) Rename to clarify: `PROJECT_DIR` (the parent containing both input and output)

**Recommendation:** (a) or (b). The current signature is misleading. Users shouldn't have to pass `.` to mean "use the output dir that's right here".

**Implementation sketch for (b) — auto-detect:**

```python
@app.command()
def render(
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Output directory containing intermediate/ from a previous run. "
                 "Defaults to ./output/ if it exists.",
        ),
    ] = None,
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Project name (defaults to output dir name)."),
    ] = None,
    ...
) -> None:
    # Auto-detect output directory
    if output_dir is None:
        if (Path.cwd() / "output" / "intermediate").exists():
            output_dir = Path("output")
        elif (Path.cwd() / "intermediate").exists():
            output_dir = Path.cwd()
        else:
            console.print("[red]No intermediate/ found.[/red]")
            console.print("Run from a project directory or specify the output path.")
            raise typer.Exit(1)

    # Derive project name from output dir, not input dir
    if project_name is None:
        project_name = output_dir.resolve().parent.name
```

This would let users just type `bristlenose render` when in a project directory. The intermediate JSON already contains metadata that could provide the project name.

### 2. ✅ `analyze` vs `analyse` spelling — DONE

American spelling (`analyze`) is inconsistent with the codebase's British English (e.g. "favourites", "colour"). Users in the UK/AU may type `bristlenose analyse` and get "No such command".

**Fix applied:** Added `analyse` as a hidden alias. Users can type either; help shows only `analyze` to avoid clutter.

```python
analyse = app.command(name="analyse", hidden=True)(analyze)
```

### 3. ✅ `transcribe-only` has a hyphen, other commands don't — DONE

Command naming is inconsistent:
- `run` (no hyphen)
- `transcribe-only` (hyphen)
- `analyze` (no hyphen)
- `render` (no hyphen)
- `doctor` (no hyphen)

Users might try `transcribeonly` or `transcribe_only`. The hyphen is surprising.

**Fix applied:** Added `transcribe` as a hidden alias. Users can type either; help shows only `transcribe-only` for backward compat.

```python
transcribe = app.command(name="transcribe", hidden=True)(transcribe_only)
```

### 3. Output directory exists → error (no merge, no prompt)

Running `bristlenose run ./input/ -o ./output/` fails if `./output/` exists and isn't empty:

```
Output directory already exists: output
Use --clean to delete it and re-run.
```

This is safe but annoying. Users often want to re-run with tweaks.

**Current workarounds:**
- `--clean` deletes everything and re-runs
- `bristlenose analyze` takes a transcripts dir and writes to a new output

**Pain points:**
- `--clean` is nuclear — wipes `people.yaml` edits, transcripts, everything
- No "resume from stage X" option
- No merge/update mode for HTML output while preserving other files

**Options:**
- (a) `--force` flag that overwrites HTML/markdown but preserves `people.yaml` and transcripts — like `render` does
- (b) Prompt user: "Output exists. [c]lean all / [o]verwrite reports / [a]bort?"
- (c) Auto-detect what changed and only re-run those stages (complex)
- (d) Do nothing — force users to use `render` for report-only updates

**Recommendation:** (a) — add `--force` as a gentler alternative to `--clean`. Currently render is the escape hatch but it requires a separate command.

**Implementation sketch:**

```python
# In run() command:
if output_dir.exists() and any(output_dir.iterdir()):
    if clean:
        shutil.rmtree(output_dir)
        console.print(f"[dim]Cleaned {output_dir}[/dim]")
    elif force:
        # Preserve: people.yaml, raw_transcripts/, cooked_transcripts/, intermediate/
        # Delete: research_report.html, research_report.md, transcript_*.html
        for f in output_dir.glob("*.html"):
            f.unlink()
        for f in output_dir.glob("*.md"):
            f.unlink()
        console.print(f"[dim]Cleared reports in {output_dir} (preserving data)[/dim]")
    else:
        console.print(
            f"[red]Output directory already exists: {output_dir}[/red]\n"
            f"Use [bold]--force[/bold] to overwrite reports (preserves transcripts + people.yaml).\n"
            f"Use [bold]--clean[/bold] to delete everything and re-run."
        )
        raise typer.Exit(1)
```

The tricky part: if transcripts changed, the user probably wants to re-run analysis, not just re-render. `--force` should probably re-run from analysis (stage 8) onward, not just render. Need to think about what "force" really means:
- `--force` = "I edited people.yaml, re-render please" → same as `render`
- `--force` = "I want to re-run LLM stages with different prompts" → needs analysis re-run
- `--force` = "Just let me overwrite, I know what I'm doing" → unclear semantics

Maybe `--force` should just be an alias for "run render instead of erroring". Keep it simple.

### 4. Error messages don't suggest the fix command

**Status:** Won't fix — current messages are fine. Focus effort on multi-provider support instead.

### 5. No progress during long stages

The spinner shows "Transcribing audio..." but for a 1-hour video, that sits there for 10+ minutes with no feedback. Users don't know if it's stuck.

Whisper's tqdm progress bar was intentionally suppressed (it doesn't work well with Rich's spinner — see CLAUDE.md gotchas). But some progress indication would help.

**Options:**
- (a) Show file-level progress: "Transcribing audio... (2/5 files)"
- (b) Show elapsed time updating live: "Transcribing audio... 3m 42s"
- (c) Show percentage for single-file runs via Whisper's internal progress callback
- (d) Do nothing — the per-stage timing at completion is sufficient

**Recommendation:** (a) — file count is low-friction to implement and gives useful feedback for multi-file runs. Could combine with (b) for single-file runs.

**Implementation sketch:**

The pipeline already knows the file count after ingest. The challenge is threading that info back to the spinner.

Option 1: Callback-based progress
```python
# In pipeline.py
async def run(...):
    ...
    def on_file_progress(current: int, total: int):
        status.update(f" [dim]Transcribing audio... ({current}/{total} files)[/dim]")

    segments = await transcribe_sessions(sessions, ..., progress_callback=on_file_progress)
```

Option 2: Return progress from transcribe step
```python
# transcribe.py yields progress tuples
async for file_idx, total, segments in transcribe_sessions_with_progress(...):
    status.update(f" [dim]Transcribing... ({file_idx}/{total})[/dim]")
```

Option 3: Simpler — just show "Transcribing N files..." upfront
```python
status.update(f" [dim]Transcribing {len(sessions)} files...[/dim]")
# No per-file updates, but at least user knows the scale
```

Option 3 is easiest. Options 1-2 require refactoring the transcribe module to support callbacks or async iteration, which is more invasive.

For elapsed time display (option b), Rich's `Status` doesn't natively support timers, but we could:
```python
import time
start = time.perf_counter()
while transcribing:
    elapsed = time.perf_counter() - start
    status.update(f" [dim]Transcribing... {_format_duration(elapsed)}[/dim]")
    await asyncio.sleep(1)
```
This needs the transcription to be truly async (yielding control), which mlx-whisper isn't. Would need `asyncio.to_thread()` wrapping.

---

## Medium friction (users notice but work around it)

### 6. `--llm` provider naming and multi-provider roadmap

The flag value is `anthropic` (company name) but the help text says "Claude". Users might try `--llm claude`. More importantly, we need to support more providers for enterprise users.

**Current state:**
- `--llm anthropic` (Claude)
- `--llm openai` (ChatGPT)

**Provider roadmap (priority order):**

1. **GitHub Copilot / Azure OpenAI** — enterprise users with Microsoft contracts can't use consumer APIs. Copilot uses Azure OpenAI under the hood. Need to support:
   - `--llm copilot` or `--llm azure`
   - `BRISTLENOSE_AZURE_OPENAI_ENDPOINT` + `BRISTLENOSE_AZURE_OPENAI_KEY`
   - Or GitHub Copilot token auth if available

2. **Google Gemini** — for Google Cloud shops
   - `--llm gemini`
   - `BRISTLENOSE_GOOGLE_API_KEY`

3. **Local models (Ollama/llama.cpp)** — for air-gapped or privacy-sensitive environments
   - `--llm local` with `BRISTLENOSE_LOCAL_MODEL_URL`

**Implementation approach:**

```python
# In config.py:
_LLM_PROVIDER_ALIASES = {
    "claude": "anthropic",
    "chatgpt": "openai",
    "gpt": "openai",
    "copilot": "azure",
    "github": "azure",
}

# In llm/client.py — provider registry pattern:
_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "azure": AzureOpenAIProvider,  # future
    "gemini": GeminiProvider,      # future
    "local": LocalProvider,        # future
}
```

**Help text update:**
```python
typer.Option("--llm", "-l", help="LLM provider: claude, chatgpt, copilot, gemini.")
```

**For now:** Accept `claude`/`chatgpt` as aliases for `anthropic`/`openai`. Design the provider abstraction to make adding Copilot straightforward.

### 7. `-w` is overloaded

`-w` means `--whisper-model` on `run` and `transcribe-only`. But flags should be memorable. `-w small` is fine; `-w large-v3-turbo` is awkward.

The model names themselves are Whisper's (`tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`). These are technical and unfamiliar to users who just want "fast" or "accurate".

**Options:**
- (a) Add friendly aliases: `--whisper-model fast` → `small`, `--whisper-model accurate` → `large-v3-turbo`
- (b) Show model comparison in `help config` or `help workflows`
- (c) Do nothing — power users know the model names, and defaults are sensible

**Recommendation:** (b) for now — document the tradeoffs. (a) is nice but adds magic.

### 8. `render` argument semantics are wrong (see #1)

Moved to #1 as high-friction. The positional argument is named `INPUT_DIR` but render doesn't read the input directory — it reads from `output/intermediate/`. Users have to pass `.` or the project parent directory, which is confusing.

### 9. No `--dry-run` — but time estimate warning would be valuable

Full `--dry-run` is overkill, but a **time estimate warning** before long jobs would be helpful.

**Idea:** After ingest, if estimated processing time exceeds 30 minutes, show a warning:

```
⚠ This will take a while — 4 sessions, ~2h 15m of audio
  Based on previous runs: ~45 minutes to process
  Press Ctrl+C to cancel, or wait to continue...
```

**Implementation sketch:**

```python
# In pipeline.py, after ingest:
total_audio_seconds = sum(f.duration_seconds or 0 for s in sessions for f in s.files)

# Rough heuristic: transcription ~0.3x realtime on Apple Silicon, LLM ~30s per participant
estimated_minutes = (total_audio_seconds * 0.3 / 60) + (len(sessions) * 0.5)

if estimated_minutes > 30:
    console.print(f"\n[yellow]⚠ This will take a while[/yellow]")
    console.print(f"  {len(sessions)} sessions, ~{_format_duration(total_audio_seconds)} of audio")
    console.print(f"  Estimated: ~{int(estimated_minutes)} minutes")
    console.print(f"  [dim]Press Ctrl+C to cancel[/dim]\n")
    time.sleep(3)  # Give user a moment to read and cancel
```

Could also store actual timing from previous runs in `~/.config/bristlenose/timing-history.json` to improve estimates over time.

### 10. Config file support is underdocumented

`-c / --config` accepts a path to `bristlenose.toml` but:
- There's no example `bristlenose.toml` in the repo
- `help config` doesn't mention it
- The TOML schema isn't documented

Users discover it in `--help` output but don't know what keys are valid.

**Options:**
- (a) Add `bristlenose.toml.example` to the repo with all keys documented
- (b) Add `help config-file` topic explaining the TOML format
- (c) Add `bristlenose init` command that creates a starter config file
- (d) Do nothing — env vars are the primary config method

**Recommendation:** (a) + (b) — document what exists.

---

## Low friction (polish)

### 11. Typer's default help box is too wide

The default `--help` output spans the full terminal width:
```
╭─ Error ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Missing argument 'INPUT_DIR'.                                                                          │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

This is 108 characters wide. The pipeline output is capped at 80 columns (`Console(width=min(80, Console().width))`), but Typer's help/error boxes ignore this and use the full terminal.

Inconsistent: the checkmark output is narrow and clean, but errors and help are sprawling.

**Options:**
- (a) Configure Typer to use the same 80-column cap
- (b) Accept the inconsistency — Typer's boxes are readable
- (c) Override Typer's console with a width-capped one

**Recommendation:** (a) if Typer supports it, otherwise (b). Not a big deal but noticeable.

**Implementation notes:**

Typer uses Rich internally. The width can be controlled via `rich_markup_mode` and a custom `Console`, but Typer doesn't expose this cleanly. Options:

1. Set `COLUMNS=80` environment variable before Typer runs — hacky but works
2. Subclass `typer.Typer` and override the console — invasive
3. Use `typer.main.get_command()` to get the Click command and configure Rich there — complex
4. Accept the inconsistency — it's really not that bad

Looking at the Typer source, the console is created internally in `rich_utils.py`. There's no clean hook.

**Verdict:** Accept inconsistency (option b). The 80-column cap is for our output; Typer's chrome is Typer's business. Users don't notice the mismatch because they see help OR pipeline output, not both together.

### 12. Version flag is uppercase `-V`

Standard convention is `-v` for version, `-V` for verbose (or vice versa). We have:
- `-V` / `--version` for version
- `-v` / `--verbose` for verbose logging

This is fine but some users expect `-v` to show version (like `git -v`, `python -V`). The uppercase `-V` matches Python's convention but not Git's.

**Options:**
- (a) Swap them: `-v` for version, `-V` for verbose
- (b) Accept both `-v` and `-V` for version (conflict with verbose)
- (c) Do nothing — current behavior matches Python's CLI

**Recommendation:** (c) — keep current. Python's convention is reasonable.

### 12. No shell completion

Tab completion would help discoverability. Typer supports generating completion scripts for bash/zsh/fish.

**Options:**
- (a) Add `bristlenose --install-completion` (built into Typer)
- (b) Ship completion scripts in the package
- (c) Document how to generate completions manually

**Recommendation:** (a) — Typer makes this trivial. Just needs enabling.

### 13. Help output is manual, not auto-generated

The `_help_commands()`, `_help_config()`, `_help_workflows()` functions are hand-written prose. When options change, the help can drift from reality.

**Options:**
- (a) Generate help from command definitions + docstrings
- (b) Add tests that verify help text matches actual options
- (c) Do nothing — manual help allows better prose

**Recommendation:** (c) for now — the manual help is intentionally better than auto-generated. But (b) would catch drift.

### 14. No coloured diff on `--clean`

When `--clean` wipes the output directory, it just says:

```
Cleaned output
```

It could show what was deleted (like `git clean -n`).

**Options:**
- (a) List deleted files/dirs before deleting (confirm prompt)
- (b) List deleted items after deletion (informational)
- (c) Do nothing — `--clean` is explicit, users know what it does

**Recommendation:** (c) — `--clean` is an explicit flag. If users are worried, they can check manually first.

### 15. Command order in `--help` is arbitrary

The commands list shows:
```
│ help             Show detailed help...                  │
│ doctor           Check dependencies...                  │
│ run              Process a folder...                    │
│ transcribe-only  Only run transcription...              │
│ analyze          Run LLM analysis...                    │
│ render           Re-render the HTML...                  │
```

This order is neither alphabetical nor by frequency of use. `run` is the main command but it's third. `help` and `doctor` are utility commands but they're first.

**Options:**
- (a) Reorder by workflow: `run`, `transcribe-only`, `analyze`, `render`, `doctor`, `help`
- (b) Reorder alphabetically
- (c) Do nothing — users scan the list anyway

**Recommendation:** (a) — put `run` first since it's the primary command. Group pipeline commands together, then utilities.

**Implementation:**

Typer orders commands by definition order in the source file. Current order in `cli.py`:
1. `help` (line 45)
2. `doctor` (line 347)
3. `run` (line 495)
4. `transcribe_only` (line 602)
5. `analyze` (line 648)
6. `render` (line 697)

To reorder, just move the function definitions. Desired order:
1. `run` — primary command
2. `transcribe_only` — subset of run
3. `analyze` — works on existing transcripts
4. `render` — works on existing intermediate
5. `doctor` — utility
6. `help` — utility

This is a pure code reorganisation with no functional change. Could do it as a separate commit: "reorder CLI commands for better discoverability".

### 16. `doctor` output alignment

The doctor table uses fixed-width formatting:

```
  FFmpeg          ok   7.1
  Backend         ok   mlx (Apple M2 Max)
```

Works but could be prettier with proper column alignment or Rich tables.

**Options:**
- (a) Use Rich `Table` for proper alignment
- (b) Keep current — it's clean and minimal
- (c) Add colour coding for different check types

**Recommendation:** (b) — current output matches the Cargo/uv aesthetic. Don't over-style.

---

## Won't fix (documented for completeness)

### `run` is too short / ambiguous

Some users expect `bristlenose` alone to do something (it shows help). `run` is the main command but "run what?" isn't self-evident.

This is fine. `run` is conventional (`npm run`, `cargo run`). The help explains it.

### No interactive mode

A TUI with menus, file pickers, and live previews would be nice but is out of scope for a CLI tool. The web UI (future `bristlenose serve`) is the answer for rich interactivity.

### Windows path handling

Windows paths with backslashes work but aren't tested extensively. Typer/pathlib handle this, but edge cases may exist.

Not a priority until Windows users report issues.

---

## Implementation order (suggested)

### Backward compatibility policy

**Don't worry about backward compat until v1.0.0.** We're pre-release; breaking changes are fine. After v1.0.0 and beta user feedback, we'll stabilise the CLI surface and maintain backward compat properly.

For now: make the CLI good, don't carry cruft forward.

### Language policy: British English preferred

Prefer British spellings throughout — `analyse`, `colour`, `favourite`, `organisation`. The Americans can cope; offer hidden aliases for them if needed (`analyze` → `analyse`).

Think of it as ethnographically quirky. The tool is opinionated about language the same way it's opinionated about user research methodology.

**TODO: Britannification pass** — go through codebase and CLI to standardise on British spellings:
- `analyze` → `analyse` (command name, help text, comments)
- `color` → `colour` (already done in CSS tokens)
- `favorite` → `favourite` (already done)
- Variable names, docstrings, error messages
- Keep American aliases where they exist (hidden, for convenience)

### Done

- ✅ **`analyse` alias** (#2) — hidden alias for `analyze` (British English convenience, not backward compat)
- ✅ **`transcribe` is now primary** (#3) — renamed from `transcribe-only` (no backward compat alias needed pre-v1.0)
- ✅ **Fix `render` argument** (#1) — now auto-detects `./output/` or `./intermediate/`. Positional arg renamed from `INPUT_DIR` to `OUTPUT_DIR`. Added `-i/--input` option for original input directory (auto-detected from sibling directories with media files)
- ✅ **Reorder commands in help** (#15) — now shows `run`, `transcribe-only`, `analyze`, `render`, `doctor`, `help`
- ✅ **`--llm claude/chatgpt` aliases** (#6) — normalised in `load_settings()`. Users can now use `--llm claude` or `--llm chatgpt`

### Do now (quick wins)

### Do soon (valuable UX)

4. **File-level progress** (#5) — "Transcribing... (2/5 files)" gives sense of movement
5. **Time estimate warning** (#9) — warn before jobs >30min, based on audio duration

### Roadmap (enterprise enablement)

6. **Copilot/Azure OpenAI support** — priority for corporate environments
7. **Gemini support** — for Google Cloud shops
8. **Local model support** — air-gapped environments

### Won't do

- **Context-aware API key errors** (#4) — current messages are fine
- **`--force` flag** (#3) — `render` command already handles this use case
- **Cap Typer help width** (#11) — no clean hook, accept inconsistency
- **Full `--dry-run`** (#9) — time estimate warning is more useful
