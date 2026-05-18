---
status: partial
last-trued: 2026-04-21
trued-against: HEAD@sidecar-signing on 2026-04-21
---

> **Truing status:** Partial — individual item analyses remain useful; status line and the "Provider Registry Abstraction" section are stale; command name throughout was the aspirational `config set-key` (now corrected to shipped `configure`). See banner at Provider Registry Abstraction section for the aspirational-not-shipped call-out. Cost tables are Feb-2026 snapshots; `llm_max_tokens` default doubled Apr 2026. Preserved: all open-item analyses (still correct, still open).

## Changelog

- _2026-04-21_ — trued up: fixed `bristlenose configure` → `bristlenose configure` throughout (11+ occurrences) — this was the highest-impact fix, users copy these snippets. Compacted Item #1 (render argument) with shipped anchor; updated Item #6 `--llm` naming to reflect shipped `claude/chatgpt/azure/gemini/local`; marked Provider Registry Abstraction section as "Aspirational — not shipped"; date-stamped cost tables; updated top-of-file status line. Anchors: `bristlenose/cli.py:1115-1140`, `bristlenose/cli.py:818,1061`, `bristlenose/cli.py:1613`, `bristlenose/cli.py:845`, commit "raise default llm_max_tokens from 32768 to 64000". Preserved: item-level analysis and rationale even for shipped items (useful context for future CLI design).
- _Gemini provider shipment_: `config.py:66` has `google_api_key` field; runtime dispatch in `bristlenose/llm/` unverified by this pass — flagged for human.

# CLI improvements

Catalogue of CLI warts, inconsistencies, and potential improvements. Prioritised by user friction, not implementation difficulty.

**Status (Apr 2026):** many items completed since Feb 2026 snapshot below — including Ollama, Azure, Keychain, Gemini (config field present; runtime dispatch unverified in last truing pass — flag for confirm), `render --input` auto-detect, LLM product-name aliases (`claude`/`chatgpt`). The "Done" section at the bottom is the authoritative running list; top-inline ✅ markers are consolidated there. **Stale from Feb 2026:** "7 items completed, 9 items open, 4 won't fix" — out of date; do not trust the count.

Detailed LLM provider implementation records (Ollama, Azure, Keychain — all shipped) archived to `archive/design-llm-providers-implementation.md`.

---

## High friction (users complain or get confused)

### 1. ~~`render` argument is `INPUT_DIR` but should be `OUTPUT_DIR`~~ — OBSOLETE (A3, 12 May 2026)

**The `render` command was removed in A3.** Invoking `bristlenose render` now hits a hidden catch-and-interpret stub that redirects to `bristlenose run` (analyse) or `bristlenose serve` (open existing). The argument-naming problem this section describes no longer applies. The historical analysis is preserved below as context for the §Future direction repurpose.

---

_Historical (Apr 2026):_

Real session:
```
╰─➤  bristlenose render
╭─ Error ────────────────────────────────────────────────────────────────────────╮
│ Missing argument 'INPUT_DIR'.                                                  │
╰────────────────────────────────────────────────────────────────────────────────╯
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

### 5. ✅ File-level progress during transcription — DONE

The spinner now shows file-level progress: "Transcribing audio... (2/5 files)" during the transcription stage. Implemented via callback from `transcribe_sessions()` to `pipeline.py`.

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

### 8. ~~`render` argument semantics are wrong (see #1)~~ — OBSOLETE (A3, 12 May 2026)

Moot — the `render` command was removed in A3. See §1 above.

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

### 10. ✅ Config file support is underdocumented — DONE

Configuration is now well documented:
- `.env.example` in repo with all env vars documented
- `bristlenose help config` shows all settings with descriptions
- Man page has full CONFIGURATION section
- TOML keys map 1:1 from env vars (lowercase, without `BRISTLENOSE_` prefix)

---

## Low friction (polish)

### 11. Typer's default help box is too wide

The default `--help` output spans the full terminal width:
```
╭─ Error ────────────────────────────────────────────────────────────────────────╮
│ Missing argument 'INPUT_DIR'.                                                  │
╰────────────────────────────────────────────────────────────────────────────────╯
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

**Post-A3 status (12 May 2026):** `render` was removed from the command list (now a hidden catch-all stub redirecting to `run` / `serve`); the rest of the order remains a Typer-definition-order quirk. Current top-level help shows `run, transcribe, analyze, serve, status, configure, doctor, help`.

**Options:**
- (a) Reorder by workflow: `run`, `transcribe`, `analyze`, `serve`, `status`, `doctor`, `configure`, `help`
- (b) Reorder alphabetically
- (c) Do nothing — users scan the list anyway

**Recommendation:** (a) — `run` first as primary; pipeline commands grouped; utilities (`doctor`, `configure`, `help`) last.

**Implementation:**

Typer orders commands by definition order in the source file. Move function definitions in `cli.py` to the desired order. Verb-sharp top-level help descriptions for `run` ("Analyse a folder of interviews and open the report in your browser.") and `serve` ("Open a previous report in your browser (no analysis).") shipped in A3.

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

## Future direction

### Markdown report as the CLI deliverable (post-100-days)

The static HTML report is on the deletion path as a *user-facing surface* — `--static` and `bristlenose render` are being removed in A3 (the file still gets written as a sealed byproduct of stage 12, just nowhere referenced). The interactive React SPA via `bristlenose serve` is the product.

But the CLI population (engineers, devrel, OSS-research folk) has a separate, legitimate need: a deliverable that plays to terminal strengths — emailable, greppable, diffable, pipeable through `pandoc`, checkable-into-git, attachable-to-Slack, pasteable-into-a-paper. The static HTML doesn't serve that; a well-designed **markdown report** would.

Reframes `--static` from "the old thing, deprecated" (sad, vestigial) to "the markdown deliverable for terminal users" (confident, differentiated). Different output target than the SPA, smaller scope (markdown is far easier to keep design-coherent than HTML), might even simplify `s12_render/` rather than carrying it as appendix-of-the-digestive-system code.

**Not for now.** This needs a real design pass — what does a *good* markdown research report look like? — and that pass shouldn't happen pre-alpha. Capture, park, revisit.

**Revisit trigger:** post-first-cohort signal. If 2+ cohort members say "I just wanted a text file I could grep / share / paste", that's the unlock. Until then, the HTML byproduct sits silently and nobody types `--static`.

**Not blocked by:** anything. The current vestigial HTML write doesn't get in the way; A3 just stops surfacing it. When this revives, the design work is the gate, not the code.

## Captured design — preferences UX, pipeline view, per-stage routing (May 2026)

A design conversation in May 2026 (out of the foundation-models-corpus reading) explored what the CLI surface for preferences, multi-stage model choice, and key management *could* eventually look like. None of it is committed beyond a single v1 read-only Pipeline view (the spike for which lives in the local-only branch handoff for this work). Captured here so the design space isn't re-derived from scratch when each piece earns its place.

**The shipping reality** (so the contrast is honest):
- `bristlenose configure <provider>` already ships — interactive key entry, validates via test call, stores in Keychain (macOS) / Secret Service (Linux). See `bristlenose/cli.py:1843`. This is what the conversation rediscovered as a desirable `auth login`-style verb; it's already there.
- `bristlenose doctor` already nudges users to run `configure` when keys are missing (`bristlenose/doctor.py`).
- Provider switching today is done by editing `.env` or setting `BRISTLENOSE_LLM_PROVIDER` env var.
- No per-stage routing exists in dispatch — `bristlenose/llm/client.py` reads one provider, applies it to every LLM-using stage.
- No TOML preferences file. Pydantic-settings reads from env vars + `.env` only.

What follows is parked ideas, each with the question they answer + when they'd earn their place. None are commitments.

### Future verb: `bristlenose use <provider>` — fast-path provider switch

**The case:** switching active provider when keys for multiple are present (e.g. "Claude credit ran out, swap to ChatGPT"). Today you edit `.env` or pass an env var inline. Aspirationally:

```
bristlenose use claude       # sugar for: config set llm_provider anthropic
bristlenose use chatgpt
bristlenose use local
bristlenose use claude-opus  # product + tier shorthand
bristlenose use              # print currently active
```

**Pros:**
- Verb-name reflects user intent ("use claude"), not mechanism ("set the llm_provider key to anthropic").
- One word, zero subcommands — the slickest CLI for the most common write.
- Sugar over the eventual `config set` path; no duplicate logic.

**Cons:**
- Provider switching isn't actually the dominant write — the conversation eventually established that the dominant write is *initial key entry*, which `configure` already handles.
- Adds a new top-level verb for an operation that today is two-line edit of `.env`.
- Speculative until a cohort member says "I keep editing `.env` to flip providers."

**Earns its place when:** a cohort member volunteers that provider-flipping is a friction point. One-line Typer alias when the time comes; not before. *(William's call.)*

### Future verb: `bristlenose config [show|set|get|edit|path]` — long-tail prefs read/write

**The case:** a `git config` / `npm config`-style noun-namespace for the non-key, non-provider settings that today live as env vars (temperature, concurrency, future per-stage overrides):

```
bristlenose config                       # show effective config (sparse)
bristlenose config set llm_temperature 0.2
bristlenose config get llm_concurrency
bristlenose config edit                  # open prefs file in $EDITOR
bristlenose config path                  # print where the file lives
bristlenose config --per-stage           # the pipeline-view lens
```

**Pros:**
- Standard CLI idiom (git, npm, gh, kubectl, helm, docker).
- One namespace for everything that isn't keys (`configure`) or provider-switch (`use`).
- The `--per-stage` flag is a natural home for the pipeline view — same data, lens applied.

**Cons:**
- Pre-commits a namespace to features that don't exist (per-stage overrides, `optimise_for` axis).
- William's verdict: "easy because `config` is the obvious bucket; not simple because it braids 'show me what's running' with 'let me change it.'"
- First-run + a text editor cover the long tail today (no v2/v3 settings exist that need this).

**Earns its place when:** there are 2+ writeable settings that don't fit cleanly under `use` or `configure`. Probably alongside the `optimise_for` axis (v2) or per-stage overrides (v3) — not before.

### Future expansion: interactive `doctor` (diagnose + prompt-to-fix)

**The case:** `doctor` today is read-only diagnostic. The conversation wondered whether it should expand to "diagnose + walk through fixing what it found":

```
$ bristlenose doctor
  ⚠ Anthropic API key missing.
    Paste it now (hidden input), or press Enter to skip: _
```

**Pros:**
- Single command does diagnosis + first-fix; matches `brew doctor` / `pyenv doctor` patterns where suggestions are inline.
- One conversation = one user keystroke flow.
- The hooks already exist (`_maybe_auto_doctor` at `bristlenose/cli.py:300` runs implicitly at startup).

**Cons:**
- Mission expansion on a tool that does one thing today. William: "may be a fine idea; not this spike's idea."
- `bristlenose configure <provider>` already exists for the specific key-entry case; doctor pointing at it is honest pointer-following, not a missing surface.
- Interactive prompts in a diagnostic command complicate scripting / CI use.

**Earns its place when:** a cohort member fails first-run and the watch-them-do-it tape shows that "run `bristlenose configure claude`" was a step too many. Today the doctor → configure pointer is one extra command, not a dealbreaker.

### Future storage: TOML preferences file

**The case:** Pydantic-settings reads env vars + `.env` today. A future preferences file at:

```
~/.config/bristlenose/preferences.toml          # user-scoped
<project>/.bristlenose/preferences.toml         # project-scoped (per study)
```

Precedence: env vars > project TOML > user TOML > defaults.

```toml
# Example future shape — not implemented
optimise_for = "privacy"

[stage_overrides]
s10_quote_extraction = "claude-sonnet"
sentiment = "apple-fm"

[stage_forbids]
s07_pii_removal = ["cloud"]
```

**Pros:**
- Per-user *and* per-project scopes — research projects carry their own preferences when handed off to collaborators (researchers think in projects).
- Diffable, syncable, debuggable in a way env vars aren't (env vars don't survive shells; `.env` is often reserved for API keys only).
- Pydantic-settings supports TOML source natively — one-line `SettingsConfigDict` change.
- Storage location `~/.config/bristlenose/` already exists (`bristlenose.db` lives there).
- Per-project location `.bristlenose/` already exists (PII summary, manifest, LLM call log).
- The desktop UserDefaults → env var translation in `BristlenoseShared.swift:105` already provides the bridge mechanism; TOML becomes the durable middle-ground.

**Cons:**
- A file format with no writeable settings (today) is YAGNI — what would you put in it?
- Existing `.env` + env vars cover the current configuration surface.
- `~/.gitconfig` / `npm config` precedent: file format exposed because *something* writes to it. Without writes, there's nothing to format.

**Earns its place when:** any of: (a) `optimise_for` axis ships and needs persistence, (b) per-stage overrides ship and need persistence, (c) the desktop UI wants to write user-mutable settings that the CLI should also see. Not before.

### Future round-trip: CLI ↔ Desktop preferences via TOML

**The case:** Desktop today writes to `@AppStorage` (UserDefaults); CLI reads env vars + `.env`. They don't share state. Desktop's sidecar-spawn translates UserDefaults → env vars for the child process (`BristlenoseShared.swift:105`, `ServeManager.swift:431`), so the wire format is already env vars on both sides.

The aspirational addition: Desktop writes through to `~/.config/bristlenose/preferences.toml` on every UserDefaults change; CLI reads the same file. Same file, two surfaces.

**Pros:**
- A Mac user who edits Settings on the desktop app can run `bristlenose run` from the terminal and get the same routing.
- A Linux/CLI user can edit TOML; if they later install the desktop app it reads the file.
- The bridge mechanism (env-var translation) already exists; this is the durable persistence layer behind it.

**Cons:**
- Today there are no user-mutable settings that need round-trip; both surfaces converge on the same env vars at runtime.
- Writing TOML from a sandboxed desktop app needs explicit container-path → user-home mapping. Solvable but real work.
- "Schema lives Python-side, written by Swift" needs careful contract testing.

**Earns its place when:** there is more than one preferences-writeable setting AND a real user reports cross-surface drift. Sequencing: comes after TOML itself ships (above).

### Future write surface: per-stage backend overrides

**The case:** the design conversation that motivated all of this — [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) and [design-stage-backends.md](design-stage-backends.md) propose a resolver that picks per-stage backends. The user-facing edit surface in some future v3 would be:

```toml
[stage_overrides]
s10_quote_extraction = "claude-sonnet"   # too many guardrail refusals on Apple FM
sentiment = "apple-fm"                    # enum classification, no need to spend tokens
```

Or via CLI: `bristlenose config set stages.s10_quote_extraction claude-sonnet`.

**Pros:**
- The mixture-of-models story (Whisper + Pyannote + LLM-per-stage) becomes user-controllable.
- Linux/eGPU users get fine-grained routing for offload (s10 to a local 4090, s11/s12 to cloud).
- The pipeline view becomes interactive — the same data, click-to-edit.

**Cons:**
- Requires the resolver to exist (catalogue, requirements, selection — see [design-stage-backends.md](design-stage-backends.md)).
- Requires the TOML format to exist.
- Requires the cohort to have validated that the mental model lands (the v1 read-only Pipeline view is the experiment that gates this).

**Earns its place when:** v1 pipeline view ships AND cohort feedback indicates per-stage choice is desired. Probably 2027.

### Future preference: `optimise_for` axis

**The case:** before per-stage overrides, a simpler intermediate — one global preference axis that re-ranks the resolver's eligible-backend list:

```
optimise_for = "privacy" | "speed" | "cost" | "best-available"
```

`privacy` ranks on-device backends first. `speed` prefers low-latency cloud (Claude Haiku, GPT-4o-mini). `cost` prefers free local / cheap cloud. `best-available` is the current default.

**Pros:**
- Single knob that's understandable to non-engineers ("I want privacy" / "I want speed").
- Survives backend churn — when a new backend appears in the catalogue, it slots into the existing ranking automatically.
- Doesn't require users to know what backends exist.

**Cons:**
- Requires the resolver + catalogue to exist.
- May not be necessary if `use <provider>` is enough for the common case.

**Earns its place when:** the resolver exists AND cohort feedback shows a "preference dial" is more legible than a stage-by-stage table.

### Naming notes (won't relitigate)

- **`config` vs `configure`**: settled in shipped code. `configure <provider>` is the interactive wizard for key entry (matches `aws configure` / `gcloud auth login` idiom). If a `config` namespace ever ships, it's read/write of non-secret settings (matches `git config` / `npm config`). The two coexist without overlap.
- **Why `bristlenose config claude` (positional shortcut) is bad**: `config` as a noun-namespace expects subcommands. A bare positional would be ambiguous (key? value? provider?). `git config foo` means *get* the value of `foo` — readers would be unable to tell write-by-positional from read-by-positional.
- **`use` reads as intent, `config set` reads as mechanism**: subtle but real distinction. If both ever ship, they're not aliases — they're different surfaces over the same underlying writer.

### JSON wire-format design questions (parked)

If/when the Pipeline view's JSON becomes a multi-consumer contract (today: CLI table + React tab):

- **Pydantic vs dataclass for boundary types**: project rule says Pydantic for things crossing JSON boundaries. Internal frozen records can stay dataclass.
- **Codegen vs hand-mirrored TS + fixture round-trip**: precedent in the codebase is hand-mirror + contract fixture (`tests/fixtures/pipeline-summary-contract.json`). Don't introduce codegen for one boundary — Rule of Three applies.
- **`schema_version` field from day one**: no external consumers exist; Rule of Three argues against. Add when the second consumer appears.

### Things explicitly decided NOT to do (in v1 or near-term)

- **Apple FM availability probe on CLI**: returns `unknown` for v1 with honest "see desktop app" copy. The probe needs Swift-side access to `SystemLanguageModel.Availability`; a bundled `bristlenose-fm-probe` Swift binary in the Homebrew formula is the eventual answer (~50 lines, single function, returns enum). Not v1 spike scope. *(Five-agent convergence in the v1 plan review.)*
- **Network connectivity probe via HEAD to Apple endpoint**: replace with OS route-table check (no outbound packets). Preserves "Bristlenose never phones home" promise.
- **Schema versioning, codegen, per-stage overrides, optimise_for axis, TOML file, `use` verb, `config` namespace, interactive doctor expansion**: all deferred per William's parsimony pass. Each earns its place from real cohort signal, not from design-doc speculation.

### Cross-references

- Design rationale: [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md), [design-stage-backends.md](design-stage-backends.md), [design-modularity.md](design-modularity.md) §Modularisation matrix
- Existing `configure` command: `bristlenose/cli.py:1843`
- Existing UserDefaults→env-var translation: `desktop/Bristlenose/Bristlenose/BristlenoseShared.swift:105`
- The v1 spike plan + review log live in the local-only branch handoff for this work.

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

4. **Time estimate warning** (#9) — warn before jobs >30min, based on audio duration

### Roadmap (enterprise enablement)

6. ✅ **Azure OpenAI support** — DONE (v0.7.0)
7. **Gemini support** — for Google Cloud shops (Phase 4, see LLM Provider Roadmap below)
8. ✅ **Local model support (Ollama)** — DONE (v0.7.0)

---

## LLM Provider Roadmap

The goal is to support whatever LLM your organisation has access to. Many enterprises have Microsoft contracts that include Azure OpenAI, others are Google Cloud shops with Gemini access, and some need air-gapped local models.

---

### Documentation-First: What We're Offering Users

Before implementing, let's write the README section. This reveals what abstraction we actually need.

#### Proposed README Section: "Choosing an LLM Provider"

```markdown
## Choosing an LLM provider

Bristlenose works with several AI providers. You only need **one**.

| Provider | Best for | Cost (typical study) |
|----------|----------|---------------------|
| **Claude** | Default. Excellent structured output | ~$1.50 |
| **ChatGPT** | Widely used, familiar | ~$1.00 |
| **Azure OpenAI** | Enterprise/corporate | ~$1.00 |
| **Gemini** | Budget-conscious | ~$0.20 |
| **Local (Ollama)** | Air-gapped, free | $0 |

### Quick setup

**Claude** (default)
```bash
bristlenose configure claude
# Prompts for your API key, stores securely in Keychain
```

**ChatGPT**
```bash
bristlenose configure chatgpt
bristlenose run ./interviews --llm chatgpt
```

**Azure OpenAI** (enterprise)
```bash
bristlenose configure azure
# Prompts for: endpoint, deployment name, API key
bristlenose run ./interviews --llm azure
```

**Gemini** (budget)
```bash
bristlenose configure gemini
bristlenose run ./interviews --llm gemini
```

**Local** (Ollama)
```bash
# Start Ollama first: ollama serve
bristlenose run ./interviews --llm local --model llama3.2
```

### Which provider is configured?

```bash
bristlenose doctor
```

Shows:
```
  LLM provider   ok   Claude (Keychain)
```

### Switching providers

The `--llm` flag overrides for a single run:

```bash
bristlenose run ./interviews --llm gemini   # use Gemini this time
```

To change the default, set a different key:

```bash
bristlenose configure chatgpt
```

### Environment variables (alternative to Keychain)

If you prefer `.env` files or CI environments:

```bash
# Claude
BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...

# ChatGPT
BRISTLENOSE_OPENAI_API_KEY=sk-...

# Azure OpenAI
BRISTLENOSE_AZURE_ENDPOINT=https://my-resource.openai.azure.com/
BRISTLENOSE_AZURE_KEY=abc123...
BRISTLENOSE_AZURE_DEPLOYMENT=gpt-4o-research

# Gemini
BRISTLENOSE_GOOGLE_API_KEY=AIza...

# Local
BRISTLENOSE_LOCAL_URL=http://localhost:11434/v1
BRISTLENOSE_LOCAL_MODEL=llama3.2
```

### Model selection

Each provider has a sensible default. Override with `--model`:

```bash
bristlenose run ./interviews --llm gemini --model gemini-2.5-pro
bristlenose run ./interviews --llm chatgpt --model gpt-4o-mini
bristlenose run ./interviews --llm local --model mistral
```

### Getting API keys

- **Claude**: [console.anthropic.com](https://console.anthropic.com/settings/keys)
- **ChatGPT**: [platform.openai.com](https://platform.openai.com/api-keys)
- **Azure OpenAI**: Azure portal → your OpenAI resource → Keys
- **Gemini**: [aistudio.google.com](https://aistudio.google.com/apikey)
- **Local**: No key needed, just run `ollama serve`
```

---

#### What This Reveals About the Abstraction

The user-facing documentation reveals several design requirements:

1. **Unified `configure` command** — one command handles all providers, prompts for the right fields
2. **Provider aliases** — users type `claude`/`chatgpt`/`azure`/`gemini`/`local`, not `anthropic`/`openai`
3. **Keychain-first** — secure by default, env vars as fallback
4. **Doctor shows provider status** — single line showing which provider is active and how it's configured
5. **`--llm` flag is the main switch** — consistent across all commands
6. **`--model` is optional** — sensible defaults, power users can override
7. **Environment variable naming** — `BRISTLENOSE_AZURE_*` not `BRISTLENOSE_AZURE_OPENAI_*` (shorter, user types "azure")

#### Provider Registry Abstraction

> **Aspirational — not shipped as of 2026-04-21.** The `ProviderSpec` / `ConfigField` / `resolve_provider()` abstraction sketched below was never built. Shipped providers (Ollama, Azure, Gemini, Claude, ChatGPT, Miro) use direct dispatch in `bristlenose/llm/client.py`. Body retained as design rationale — the abstraction may still be worth doing if provider count grows further. See the "What this enables" list below for the case.

From the docs, we need a provider registry that knows:

```python
@dataclass
class ProviderSpec:
    """Specification for an LLM provider."""
    name: str                          # Internal name: "anthropic", "openai", "azure", "gemini", "local"
    display_name: str                  # User-facing: "Claude", "ChatGPT", "Azure OpenAI", "Gemini", "Local"
    aliases: list[str]                 # CLI aliases: ["claude"], ["chatgpt", "gpt"], ["azure"], etc.
    config_fields: list[ConfigField]   # What to prompt for in `configure`
    default_model: str                 # e.g. "claude-sonnet-4-20250514", "gpt-4o", "gemini-2.5-flash"
    sdk_module: str                    # e.g. "anthropic", "openai", "google.genai"
    pricing_url: str                   # For doctor output and cost estimates

@dataclass
class ConfigField:
    """A configuration field for a provider."""
    name: str                          # e.g. "api_key", "endpoint", "deployment"
    env_var: str                       # e.g. "BRISTLENOSE_AZURE_KEY"
    prompt: str                        # e.g. "Azure OpenAI API key"
    secret: bool = True                # Mask input, store in Keychain
    required: bool = True
    default: str = ""

# Registry
PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        name="anthropic",
        display_name="Claude",
        aliases=["claude"],
        config_fields=[
            ConfigField("api_key", "BRISTLENOSE_ANTHROPIC_API_KEY", "Claude API key"),
        ],
        default_model="claude-sonnet-4-20250514",
        sdk_module="anthropic",
        pricing_url="https://docs.anthropic.com/en/docs/about-claude/models",
    ),
    "openai": ProviderSpec(
        name="openai",
        display_name="ChatGPT",
        aliases=["chatgpt", "gpt"],
        config_fields=[
            ConfigField("api_key", "BRISTLENOSE_OPENAI_API_KEY", "ChatGPT API key"),
        ],
        default_model="gpt-4o",
        sdk_module="openai",
        pricing_url="https://platform.openai.com/docs/pricing",
    ),
    "azure": ProviderSpec(
        name="azure",
        display_name="Azure OpenAI",
        aliases=["azure", "azure-openai"],
        config_fields=[
            ConfigField("endpoint", "BRISTLENOSE_AZURE_ENDPOINT", "Azure endpoint URL", secret=False),
            ConfigField("deployment", "BRISTLENOSE_AZURE_DEPLOYMENT", "Deployment name", secret=False),
            ConfigField("api_key", "BRISTLENOSE_AZURE_KEY", "Azure API key"),
        ],
        default_model="",  # Deployment name IS the model reference
        sdk_module="openai",  # Same SDK!
        pricing_url="https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/",
    ),
    "gemini": ProviderSpec(
        name="gemini",
        display_name="Gemini",
        aliases=["gemini", "google"],
        config_fields=[
            ConfigField("api_key", "BRISTLENOSE_GOOGLE_API_KEY", "Google API key"),
        ],
        default_model="gemini-2.5-flash",
        sdk_module="google.genai",
        pricing_url="https://ai.google.dev/gemini-api/docs/pricing",
    ),
    "local": ProviderSpec(
        name="local",
        display_name="Local (Ollama)",
        aliases=["local", "ollama"],
        config_fields=[
            ConfigField("url", "BRISTLENOSE_LOCAL_URL", "Ollama URL", secret=False, default="http://localhost:11434/v1"),
            ConfigField("model", "BRISTLENOSE_LOCAL_MODEL", "Model name", secret=False, default="llama3.2"),
        ],
        default_model="llama3.2",
        sdk_module="openai",  # Ollama is OpenAI-compatible
        pricing_url="",  # Free
    ),
}

# Alias lookup
def resolve_provider(name: str) -> str:
    """Resolve alias to canonical provider name."""
    name = name.lower()
    if name in PROVIDERS:
        return name
    for provider_name, spec in PROVIDERS.items():
        if name in spec.aliases:
            return provider_name
    raise ValueError(f"Unknown provider: {name}")
```

#### LLMClient Refactor

With the registry, `LLMClient` becomes cleaner:

```python
class LLMClient:
    def __init__(self, settings: BristlenoseSettings) -> None:
        self.settings = settings
        self.provider = resolve_provider(settings.llm_provider)
        self.spec = PROVIDERS[self.provider]
        self._client: object | None = None
        self.tracker = LLMUsageTracker()
        self._validate_config()

    def _validate_config(self) -> None:
        """Check required config fields are present."""
        for field in self.spec.config_fields:
            if field.required:
                value = self._get_config_value(field)
                if not value:
                    raise ValueError(
                        f"{self.spec.display_name} {field.prompt.lower()} not set. "
                        f"Run: bristlenose configure {self.spec.aliases[0]}"
                    )

    def _get_config_value(self, field: ConfigField) -> str:
        """Get config value from Keychain, env, or settings."""
        # 1. Keychain
        from bristlenose.keychain import get_key
        key = get_key(f"{self.provider}_{field.name}")
        if key:
            return key
        # 2. Environment
        value = os.environ.get(field.env_var, "")
        if value:
            return value
        # 3. Settings object
        return getattr(self.settings, field.env_var.lower().replace("bristlenose_", ""), field.default)

    async def analyze(self, system_prompt: str, user_prompt: str, response_model: type[T], max_tokens: int | None = None) -> T:
        """Dispatch to provider-specific implementation."""
        max_tokens = max_tokens or self.settings.llm_max_tokens

        # Dispatch based on SDK module
        if self.spec.sdk_module == "anthropic":
            return await self._analyze_anthropic(system_prompt, user_prompt, response_model, max_tokens)
        elif self.spec.sdk_module == "openai":
            # OpenAI SDK handles: openai, azure, local (Ollama)
            return await self._analyze_openai_compatible(system_prompt, user_prompt, response_model, max_tokens)
        elif self.spec.sdk_module == "google.genai":
            return await self._analyze_gemini(system_prompt, user_prompt, response_model, max_tokens)
        else:
            raise ValueError(f"No implementation for SDK: {self.spec.sdk_module}")

    async def _analyze_openai_compatible(self, ...) -> T:
        """Handle OpenAI, Azure, and Local (Ollama) — all use the OpenAI SDK."""
        import openai

        if self._client is None:
            if self.provider == "azure":
                self._client = openai.AsyncAzureOpenAI(
                    api_key=self._get_config_value(self.spec.config_fields[2]),  # api_key is third field
                    azure_endpoint=self._get_config_value(self.spec.config_fields[0]),
                    api_version="2024-10-21",
                )
            elif self.provider == "local":
                self._client = openai.AsyncOpenAI(
                    base_url=self._get_config_value(self.spec.config_fields[0]),
                    api_key="ollama",  # Ignored but required
                )
            else:  # openai
                self._client = openai.AsyncOpenAI(
                    api_key=self._get_config_value(self.spec.config_fields[0]),
                )

        # Rest is identical for all three...
        model = self.settings.llm_model or self._get_model_for_provider()
        # ...
```

#### Benefits of This Abstraction

1. **Adding a new provider** = add one entry to `PROVIDERS` dict + one dispatch branch if new SDK
2. **`configure` is generic** — loops over `spec.config_fields`, prompts for each, stores in Keychain
3. **Doctor is generic** — loops over providers, checks which have valid config
4. **Error messages are consistent** — "Run: bristlenose configure {alias}" for all providers
5. **Pricing is centralised** — `spec.pricing_url` used in doctor and cost estimates
6. **Future-proof** — Mistral, Cohere, AWS Bedrock all fit the same pattern

---

### Provider Comparison Matrix

| Aspect | Claude (current) | ChatGPT (current) | Azure OpenAI | Gemini |
|--------|------------------|-------------------|--------------|--------|
| **SDK** | `anthropic` | `openai` | `openai` (same SDK) | `google-genai` (new dep) |
| **Structured output** | Tool use | JSON mode | JSON mode (same as OpenAI) | Native JSON schema |
| **Async support** | ✅ Full | ✅ Full | ✅ Full (same SDK) | ✅ Full (`client.aio`) |
| **Implementation effort** | — | — | ~30 lines (copy OpenAI) | ~50 lines (new pattern) |
| **New dependency** | No | No | No | Yes (`google-genai`) |
| **Auth complexity** | API key | API key | Endpoint + key + deployment | API key |
| **Config fields** | 1 | 1 | 4 | 2 |

### Model Quality for User Research Tasks

Bristlenose's LLM stages require:
1. **Structured JSON output** — speaker role identification, quote extraction, topic segmentation
2. **Long context** — full transcripts (10K–50K tokens typical)
3. **Instruction following** — strict schema adherence, no hallucinated quotes
4. **Reasoning** — identifying themes, clustering quotes semantically

**Current defaults:**
- Claude Sonnet 4 — excellent at structured output via tool use, strong instruction following
- GPT-4o — good JSON mode compliance, solid reasoning

**Azure OpenAI:**
- Same models as OpenAI (GPT-4o, GPT-4o-mini) — identical quality
- Structured outputs supported since API version 2024-08-01-preview
- 100% schema compliance with `strict: true` mode
- **Verdict:** Equivalent quality to current OpenAI support

**Gemini:**
- Gemini 2.5 Pro/Flash have native JSON schema support — no JSON mode workaround needed
- Strong multilingual performance (useful for non-English interviews)
- Gemini 2.5 Flash is exceptionally cheap ($0.30/M input vs $2.50/M for GPT-4o)
- Some SDK limitations: dictionaries in schemas can be problematic ([issue #460](https://github.com/googleapis/python-genai/issues/460))
- **Verdict:** Comparable quality, better price, slight SDK immaturity

### Pricing Comparison (per million tokens, Jan 2026)

| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| **Claude Sonnet 4** | $3.00 | $15.00 | Current default |
| **GPT-4o** | $2.50 | $10.00 | Current alternative |
| **GPT-4o-mini** | $0.15 | $0.60 | Cheaper, less capable |
| **Azure GPT-4o** | ~$2.50 | ~$10.00 | Same as OpenAI (varies by region) |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | Long context 2× price >200K |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | Best value, very capable |
| **Gemini 2.5 Flash-Lite** | $0.10 | $0.40 | Ultra-cheap, simpler tasks |

**Cost for typical bristlenose run (5 interviews, ~50K input + ~10K output per interview):**
- Claude Sonnet 4: ~$1.50
- GPT-4o: ~$1.00
- Gemini 2.5 Flash: ~$0.20

Gemini Flash could reduce costs by 5–7× for price-sensitive users.

### User Demand Assessment

**Azure OpenAI:**
- **High demand** for enterprise users
- Many large organisations have Microsoft 365 E5 contracts that include Azure OpenAI
- Compliance/data residency requirements force Azure routing
- IT departments often block direct OpenAI API access
- "I'd use this at work if it supported Azure" is a common pattern

**Gemini:**
- **Medium demand** — Google Cloud shops, cost-conscious users
- Fewer enterprises are Google-first than Microsoft-first
- Strong appeal for budget users (5–7× cheaper than Claude/GPT-4o)
- Good multilingual support is a differentiator

### Implementation Priority Recommendation

**Do Azure OpenAI first:** ✅ DONE (v0.7.0)
1. Zero new dependencies (reuses `openai` SDK)
2. Minimal code (~30 lines, copy-paste from OpenAI implementation)
3. High enterprise demand (unblocks paying customers)
4. Identical quality to existing OpenAI support
5. ~2 hours implementation + testing

**Do Gemini second:** (Phase 4, next up)
1. Requires new dependency (`google-genai`)
2. Different structured output pattern (native JSON schema, not tool use)
3. SDK has some rough edges (dict handling issues)
4. Lower enterprise demand, but good for cost-conscious users
5. ~4 hours implementation + testing (includes SDK learning curve)

### Shipped implementation details

Detailed implementation plans for Ollama, Azure OpenAI, and Keychain integration — including code sketches, doctor validation patterns, testing checklists, and the zero-friction first-run UX design — are archived in `archive/design-llm-providers-implementation.md`. That file also contains the LLM-specific "Won't do" decisions and the revised implementation order that was followed.
