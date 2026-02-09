# CLI improvements

Catalogue of CLI warts, inconsistencies, and potential improvements. Prioritised by user friction, not implementation difficulty.

**Status (Feb 2026):** 7 items completed, 9 items open, 4 won't fix. Detailed LLM provider implementation records (Ollama, Azure, Keychain — all shipped) archived to `archive/design-llm-providers-implementation.md`.

---

## High friction (users complain or get confused)

### 1. `render` argument is `INPUT_DIR` but should be `OUTPUT_DIR`

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
bristlenose config set-key claude
# Prompts for your API key, stores securely in Keychain
```

**ChatGPT**
```bash
bristlenose config set-key chatgpt
bristlenose run ./interviews --llm chatgpt
```

**Azure OpenAI** (enterprise)
```bash
bristlenose config set-key azure
# Prompts for: endpoint, deployment name, API key
bristlenose run ./interviews --llm azure
```

**Gemini** (budget)
```bash
bristlenose config set-key gemini
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
bristlenose config set-key chatgpt
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

1. **Unified `config set-key` command** — one command handles all providers, prompts for the right fields
2. **Provider aliases** — users type `claude`/`chatgpt`/`azure`/`gemini`/`local`, not `anthropic`/`openai`
3. **Keychain-first** — secure by default, env vars as fallback
4. **Doctor shows provider status** — single line showing which provider is active and how it's configured
5. **`--llm` flag is the main switch** — consistent across all commands
6. **`--model` is optional** — sensible defaults, power users can override
7. **Environment variable naming** — `BRISTLENOSE_AZURE_*` not `BRISTLENOSE_AZURE_OPENAI_*` (shorter, user types "azure")

#### Provider Registry Abstraction

From the docs, we need a provider registry that knows:

```python
@dataclass
class ProviderSpec:
    """Specification for an LLM provider."""
    name: str                          # Internal name: "anthropic", "openai", "azure", "gemini", "local"
    display_name: str                  # User-facing: "Claude", "ChatGPT", "Azure OpenAI", "Gemini", "Local"
    aliases: list[str]                 # CLI aliases: ["claude"], ["chatgpt", "gpt"], ["azure"], etc.
    config_fields: list[ConfigField]   # What to prompt for in `config set-key`
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
                        f"Run: bristlenose config set-key {self.spec.aliases[0]}"
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
2. **`config set-key` is generic** — loops over `spec.config_fields`, prompts for each, stores in Keychain
3. **Doctor is generic** — loops over providers, checks which have valid config
4. **Error messages are consistent** — "Run: bristlenose config set-key {alias}" for all providers
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
