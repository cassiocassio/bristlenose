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

4. **Time estimate warning** (#9) — warn before jobs >30min, based on audio duration

### Roadmap (enterprise enablement)

6. **Azure OpenAI support** — priority for corporate environments (see detailed roadmap below)
7. **Gemini support** — for Google Cloud shops
8. **Local model support** — air-gapped environments

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

**Do Azure OpenAI first:**
1. Zero new dependencies (reuses `openai` SDK)
2. Minimal code (~30 lines, copy-paste from OpenAI implementation)
3. High enterprise demand (unblocks paying customers)
4. Identical quality to existing OpenAI support
5. ~2 hours implementation + testing

**Do Gemini second:**
1. Requires new dependency (`google-genai`)
2. Different structured output pattern (native JSON schema, not tool use)
3. SDK has some rough edges (dict handling issues)
4. Lower enterprise demand, but good for cost-conscious users
5. ~4 hours implementation + testing (includes SDK learning curve)

### Current Architecture

The `LLMClient` in `bristlenose/llm/client.py` uses a dispatch pattern:

```python
async def analyze(self, system_prompt, user_prompt, response_model, max_tokens):
    if self.provider == "anthropic":
        return await self._analyze_anthropic(...)
    elif self.provider == "openai":
        return await self._analyze_openai(...)
    else:
        raise ValueError(f"Unsupported LLM provider: {self.provider}")
```

Each provider has:
1. **Lazy client initialisation** — SDK client created on first use
2. **Structured output mechanism** — tool use (Anthropic) or JSON mode (OpenAI)
3. **Token tracking** — normalised to `input_tokens`/`output_tokens`

Adding a new provider requires changes in 5 locations:
1. `config.py` — add API key field, add alias
2. `llm/client.py` — add dispatch branch, add implementation method
3. `llm/pricing.py` — add model pricing
4. `doctor.py` — add API key validation
5. Tests

### Priority 1: Azure OpenAI

**Why:** Many enterprises have Microsoft 365 E5 or Azure contracts that include Azure OpenAI. They can't use consumer OpenAI API keys; they must route through their Azure subscription for compliance, billing, and data residency reasons.

**Key insight:** Azure OpenAI uses the same models (GPT-4o, GPT-4o-mini) but with a different authentication and endpoint scheme. The OpenAI Python SDK supports Azure natively via `AsyncAzureOpenAI` — we don't need a separate SDK.

**Implementation complexity: LOW** — copy-paste from `_analyze_openai()` with 4 line changes.

#### Configuration

```python
# In config.py
class BristlenoseSettings(BaseSettings):
    # Existing
    llm_provider: str = "anthropic"
    openai_api_key: str = ""

    # New for Azure (4 fields)
    azure_openai_endpoint: str = ""      # https://my-resource.openai.azure.com/
    azure_openai_key: str = ""           # API key from Azure portal
    azure_openai_deployment: str = ""    # Deployment name (NOT model name!)
    azure_openai_api_version: str = "2024-10-21"  # Use latest stable

# Add aliases
_LLM_PROVIDER_ALIASES = {
    "claude": "anthropic",
    "chatgpt": "openai",
    "gpt": "openai",
    "azure": "azure",           # NEW
    "azure-openai": "azure",    # NEW
}
```

#### Implementation

The implementation is nearly identical to `_analyze_openai()` — just swap the client class and add Azure-specific params:

```python
# In llm/client.py — add to __init__
self._azure_client: object | None = None

# In _validate_api_key() — add branch
if self.provider == "azure":
    if not self.settings.azure_openai_endpoint:
        raise ValueError(
            "Azure OpenAI endpoint not set. "
            "Set BRISTLENOSE_AZURE_OPENAI_ENDPOINT to your resource URL."
        )
    if not self.settings.azure_openai_key:
        raise ValueError(
            "Azure OpenAI API key not set. "
            "Set BRISTLENOSE_AZURE_OPENAI_KEY from your Azure portal."
        )
    if not self.settings.azure_openai_deployment:
        raise ValueError(
            "Azure OpenAI deployment not set. "
            "Set BRISTLENOSE_AZURE_OPENAI_DEPLOYMENT to your model deployment name."
        )

# In analyze() — add dispatch branch
elif self.provider == "azure":
    return await self._analyze_azure(
        system_prompt, user_prompt, response_model, max_tokens
    )

# New method (copy of _analyze_openai with 4 changes highlighted)
async def _analyze_azure(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
) -> T:
    """Call Azure OpenAI API with JSON mode for structured output."""
    import openai

    if self._azure_client is None:
        # CHANGE 1: AsyncAzureOpenAI instead of AsyncOpenAI
        # CHANGE 2: azure_endpoint and api_version params
        self._azure_client = openai.AsyncAzureOpenAI(
            api_key=self.settings.azure_openai_key,
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_version=self.settings.azure_openai_api_version,
        )

    client: openai.AsyncAzureOpenAI = self._azure_client  # type: ignore[assignment]

    schema = response_model.model_json_schema()
    schema_instruction = (
        f"\n\nYou must respond with valid JSON matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    logger.debug("Calling Azure OpenAI API: deployment=%s", self.settings.azure_openai_deployment)

    response = await client.chat.completions.create(
        # CHANGE 3: deployment name instead of model name
        model=self.settings.azure_openai_deployment,
        max_tokens=max_tokens,
        temperature=self.settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + schema_instruction},
            {"role": "user", "content": user_prompt},
        ],
    )

    if hasattr(response, "usage") and response.usage:
        self.tracker.record(response.usage.prompt_tokens, response.usage.completion_tokens)

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Empty response from Azure OpenAI")

    data = json.loads(content)
    return response_model.model_validate(data)
```

**Total new code: ~35 lines** (method is 90% identical to OpenAI).

#### Key Differences from Regular OpenAI

| Aspect | OpenAI | Azure OpenAI |
|--------|--------|--------------|
| Client class | `AsyncOpenAI` | `AsyncAzureOpenAI` |
| Auth | `api_key` only | `api_key` + `azure_endpoint` + `api_version` |
| Model param | Model name (`gpt-4o`) | Deployment name (`my-gpt4o-deployment`) |
| API versions | Implicit | Explicit (`2024-10-21`, `2025-03-01-preview`) |

**Gotcha:** Azure uses deployment names, not model names. A user might deploy GPT-4o as `"research-model"` or `"gpt4o-eastus"`. The deployment name is set in Azure portal when they create the deployment.

#### Doctor Validation

```python
def _validate_azure_key(endpoint: str, key: str, deployment: str, api_version: str) -> tuple[bool | None, str]:
    """Validate Azure OpenAI credentials.

    Azure doesn't have a simple /models endpoint, so we make a minimal
    completion request with max_tokens=1 to verify credentials work.
    """
    import httpx

    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"
    headers = {"api-key": key, "Content-Type": "application/json"}
    params = {"api-version": api_version}
    body = {
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 1,
    }

    try:
        response = httpx.post(url, headers=headers, params=params, json=body, timeout=10)
        if response.status_code == 200:
            return True, ""
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 404:
            return False, f"Deployment '{deployment}' not found"
        else:
            return False, f"Azure returned {response.status_code}: {response.text[:100]}"
    except httpx.ConnectError:
        return None, f"Cannot connect to {endpoint}"
```

#### Pricing

Azure OpenAI pricing is roughly equivalent to OpenAI consumer pricing but varies by:
- Region (East US cheaper than West Europe)
- Commitment tier (pay-as-you-go vs provisioned throughput)

For cost estimation, we'll use OpenAI rates as a baseline. Add to `pricing.py`:

```python
# Azure uses deployment names, not model names, so we can't look up directly.
# Cost estimation for Azure will return None (unknown) unless user configures
# BRISTLENOSE_AZURE_MODEL_EQUIVALENT to map their deployment to a model name.
```

Alternatively, add a config field `azure_openai_model_equivalent` so users can specify which model their deployment uses for cost estimation.

#### User Experience

```bash
# Environment variables
export BRISTLENOSE_LLM_PROVIDER=azure
export BRISTLENOSE_AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
export BRISTLENOSE_AZURE_OPENAI_KEY=abc123...
export BRISTLENOSE_AZURE_OPENAI_DEPLOYMENT=gpt-4o-research

# CLI usage
bristlenose run ./interviews --llm azure

# Or in .env file:
BRISTLENOSE_LLM_PROVIDER=azure
BRISTLENOSE_AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
BRISTLENOSE_AZURE_OPENAI_KEY=abc123...
BRISTLENOSE_AZURE_OPENAI_DEPLOYMENT=gpt-4o-research
```

#### GitHub Copilot Clarification

GitHub Copilot ≠ Azure OpenAI. They're different products:

- **Copilot** is IDE-integrated code completion. No public inference API. The [copilot-api](https://github.com/ericc-ch/copilot-api) reverse-engineering project exists but violates ToS and risks account suspension.
- **Azure OpenAI** is the API service for GPT models. Available to Azure subscribers.
- **GitHub Enterprise + Copilot** customers can usually get Azure OpenAI access through their Microsoft relationship.

**Recommendation:** Don't support Copilot directly. Point enterprise users to Azure OpenAI instead.

#### Testing Checklist

1. Unit tests:
   - [ ] `_validate_api_key()` raises for missing endpoint/key/deployment
   - [ ] `_analyze_azure()` dispatches correctly
   - [ ] Response parsing and token tracking work

2. Integration test (requires Azure credentials):
   - [ ] Real API call with a simple prompt
   - [ ] Structured output matches Pydantic schema

3. Doctor tests:
   - [ ] `check_api_key()` handles azure provider
   - [ ] Validation function handles 401/404/network errors

### Priority 2: Google Gemini

**Why:** Google Cloud Platform customers often have Gemini access through their GCP billing. Some organisations are Google-first and don't have Azure or Anthropic relationships. Additionally, Gemini 2.5 Flash is 5–7× cheaper than Claude/GPT-4o, appealing to cost-conscious users.

**Implementation complexity: MEDIUM** — new SDK, different async pattern, some known limitations.

#### Configuration

```python
# In config.py
class BristlenoseSettings(BaseSettings):
    # New for Gemini (2 fields)
    google_api_key: str = ""                   # From Google AI Studio or GCP
    gemini_model: str = "gemini-2.5-flash"     # Default to Flash (cheap + capable)

# Add aliases
_LLM_PROVIDER_ALIASES = {
    ...
    "gemini": "gemini",    # NEW
    "google": "gemini",    # NEW
}
```

#### New Dependency

Gemini requires a new package:

```toml
# In pyproject.toml
dependencies = [
    ...
    "google-genai>=1.0.0",  # NEW — Google Gen AI SDK
]
```

**Size impact:** ~15 MB (includes protobuf, grpcio, google-auth). Not trivial, but acceptable.

#### Implementation

```python
# In llm/client.py — add to __init__
self._gemini_client: object | None = None

# In _validate_api_key() — add branch
if self.provider == "gemini" and not self.settings.google_api_key:
    raise ValueError(
        "Google API key not set. "
        "Set BRISTLENOSE_GOOGLE_API_KEY from Google AI Studio or GCP console."
    )

# In analyze() — add dispatch branch
elif self.provider == "gemini":
    return await self._analyze_gemini(
        system_prompt, user_prompt, response_model, max_tokens
    )

# New method
async def _analyze_gemini(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
) -> T:
    """Call Google Gemini API with native JSON schema support.

    Unlike Anthropic (tool use) and OpenAI (JSON mode), Gemini supports
    Pydantic-derived JSON schemas natively via response_schema config.
    """
    from google import genai

    if self._gemini_client is None:
        self._gemini_client = genai.Client(api_key=self.settings.google_api_key)

    # Gemini SDK uses .aio property for async client access
    client = self._gemini_client.aio

    # Gemini accepts JSON schema directly — cleaner than tool use workaround
    schema = response_model.model_json_schema()

    logger.debug("Calling Gemini API: model=%s", self.settings.gemini_model)

    # Gemini combines system + user prompts differently
    # The official pattern is to include system instructions in contents
    response = await client.models.generate_content(
        model=self.settings.gemini_model,
        contents=f"{system_prompt}\n\n{user_prompt}",
        config={
            "response_mime_type": "application/json",
            "response_schema": schema,
            "max_output_tokens": max_tokens,
            "temperature": self.settings.llm_temperature,
        },
    )

    # Token tracking — Gemini uses different field names
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        self.tracker.record(
            response.usage_metadata.prompt_token_count or 0,
            response.usage_metadata.candidates_token_count or 0,
        )

    # Parse response
    if not response.text:
        raise RuntimeError("Empty response from Gemini")

    data = json.loads(response.text)
    return response_model.model_validate(data)
```

#### Key Differences from Claude/OpenAI

| Aspect | Claude | OpenAI | Gemini |
|--------|--------|--------|--------|
| Structured output | Tool use (force tool call) | JSON mode + schema in prompt | Native `response_schema` |
| Async client | `AsyncAnthropic()` | `AsyncOpenAI()` | `Client().aio` |
| System prompt | Separate `system=` param | First message role=system | Combined with user content |
| Token fields | `input_tokens`, `output_tokens` | `prompt_tokens`, `completion_tokens` | `prompt_token_count`, `candidates_token_count` |

#### Known SDK Limitations

The `google-genai` SDK has some rough edges as of v1.5.0:

1. **Dict handling in schemas** — `dict[str, T]` types can cause issues ([googleapis/python-genai#460](https://github.com/googleapis/python-genai/issues/460)). Our Pydantic models use `list` not `dict` for collections, so should be fine.

2. **Async context management** — Must call `await client.aclose()` or use `async with` context manager. We'll use lazy init + no explicit close (like our other providers), which may leak connections. Consider adding cleanup in future.

3. **Error messages** — Less descriptive than Anthropic/OpenAI. May need extra logging for debugging.

**Mitigation:** Test thoroughly with our actual Pydantic models (`SpeakerRoleAssignment`, `TopicSegmentationResult`, `QuoteExtractionResult`, etc.) before shipping.

#### Pricing

Add to `pricing.py`:

```python
PRICING: dict[str, tuple[float, float]] = {
    # ... existing ...
    # Gemini
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),      # Best value
    "gemini-2.5-flash-lite": (0.10, 0.40),  # Ultra cheap
}

PRICING_URLS: dict[str, str] = {
    # ... existing ...
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
}
```

#### Doctor Validation

```python
def _validate_google_key(key: str) -> tuple[bool | None, str]:
    """Validate Google API key by listing available models."""
    import httpx

    url = "https://generativelanguage.googleapis.com/v1/models"
    params = {"key": key}

    try:
        response = httpx.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return True, ""
        elif response.status_code == 400:
            return False, "Invalid API key format"
        elif response.status_code == 403:
            return False, "API key rejected — check it's enabled for Gemini API"
        else:
            return False, f"Google returned {response.status_code}"
    except httpx.ConnectError:
        return None, "Cannot connect to Google API"
```

#### User Experience

```bash
# Environment variable
export BRISTLENOSE_LLM_PROVIDER=gemini
export BRISTLENOSE_GOOGLE_API_KEY=AIza...

# CLI usage
bristlenose run ./interviews --llm gemini

# Use cheaper Flash model (default)
bristlenose run ./interviews --llm gemini

# Use Pro for higher quality
bristlenose run ./interviews --llm gemini --model gemini-2.5-pro
```

**Cost comparison for 5 interviews:**
- Claude Sonnet: ~$1.50
- GPT-4o: ~$1.00
- **Gemini Flash: ~$0.20** (5–7× cheaper)

#### Testing Checklist

1. Unit tests:
   - [ ] `_validate_api_key()` raises for missing key
   - [ ] `_analyze_gemini()` dispatches correctly
   - [ ] Token tracking handles Gemini's field names
   - [ ] Response parsing works with our Pydantic models

2. Integration test (requires Google API key):
   - [ ] Real API call with `QuoteExtractionResult` schema
   - [ ] Verify all 5 stage schemas work

3. Edge cases:
   - [ ] Empty response handling
   - [ ] Schema with nested objects
   - [ ] Long context (>100K tokens)

### Priority 3: Local Models (Ollama)

**Why:** Air-gapped environments, data sovereignty requirements, or users who want to avoid API costs entirely.

**Approach:** Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1/`. We can use the standard OpenAI SDK pointed at a local endpoint.

**Configuration:**

```python
# In config.py
class BristlenoseSettings(BaseSettings):
    # New for local
    local_model_url: str = "http://localhost:11434/v1"  # Default to Ollama
    local_model_name: str = "llama3.2"  # Model name in Ollama

# Add alias
_LLM_PROVIDER_ALIASES = {
    ...
    "local": "local",
    "ollama": "local",
}
```

**Implementation:**

```python
# In llm/client.py
async def _analyze_local(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
) -> T:
    """Call local Ollama-compatible API with JSON mode.

    Uses the OpenAI SDK pointed at a local endpoint.
    """
    import openai

    if self._local_client is None:
        self._local_client = openai.AsyncOpenAI(
            base_url=self.settings.local_model_url,
            api_key="ollama",  # Required but ignored by Ollama
        )

    client: openai.AsyncOpenAI = self._local_client

    # Same JSON mode approach as OpenAI
    schema = response_model.model_json_schema()
    schema_instruction = (
        f"\n\nYou must respond with valid JSON matching this schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```"
    )

    response = await client.chat.completions.create(
        model=self.settings.local_model_name,
        max_tokens=max_tokens,
        temperature=self.settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + schema_instruction},
            {"role": "user", "content": user_prompt},
        ],
    )

    # Token tracking (Ollama provides this)
    if hasattr(response, "usage") and response.usage:
        self.tracker.record(response.usage.prompt_tokens, response.usage.completion_tokens)

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Empty response from local model")

    data = json.loads(content)
    return response_model.model_validate(data)
```

**Key considerations:**
- Ollama runs on `localhost:11434` by default
- The API key is required by the SDK but ignored by Ollama (set to `"ollama"`)
- JSON mode support depends on the model — function-calling models (Llama 3.1+, Mistral, Qwen 2.5) work best
- Smaller models may struggle with complex schemas; may need prompt engineering
- No API cost, but local inference is slower and less capable

**Doctor check:** Validate that the local endpoint is reachable:

```python
def _validate_local_model(url: str, model: str) -> tuple[bool | None, str]:
    """Check that Ollama is running and the model is available."""
    try:
        response = httpx.get(f"{url}/models", timeout=5)
        if response.status_code != 200:
            return False, f"Local model server returned {response.status_code}"
        models = response.json().get("data", [])
        if not any(m.get("id") == model for m in models):
            return False, f"Model '{model}' not found. Run: ollama pull {model}"
        return True, ""
    except httpx.ConnectError:
        return False, "Cannot connect to local model server. Is Ollama running?"
```

**Pricing:** Local models are free (no API cost). `estimate_cost()` returns `None` for local provider.

---

### Ollama as Zero-Friction Entry Point

**The problem:** API keys are a barrier to trying the tool. Users must:
1. Create an account with Anthropic or OpenAI
2. Add payment details
3. Generate and copy an API key
4. Figure out where to put it

Many potential users bounce at step 1-2. This is a significant adoption barrier.

**The solution:** Make Ollama the "just try it" path — no signup, no payment, no keys.

#### First-Run Experience (Proposed)

```
bristlenose run ./interviews

Bristlenose v0.7.0

No LLM provider configured. Choose one:

  [1] Local AI (free, private, slower)
      Requires Ollama — install from https://ollama.ai

  [2] Claude API (best quality, ~$1.50/study)
      Get a key from console.anthropic.com

  [3] ChatGPT API (good quality, ~$1.00/study)
      Get a key from platform.openai.com

Choice [1]:
```

If they choose [1] and Ollama isn't installed:

```
Ollama not found.

Install it from: https://ollama.ai
(It's a single download, no account needed)

After installing, run:
  ollama pull llama3.2

Then try again:
  bristlenose run ./interviews

Press Enter to open the download page...
```

If Ollama is installed but no suitable model:

```
Ollama is running, but no suitable model found.

Downloading llama3.2 (2.0 GB)...
████████████████████████████████████████ 100%

Ready! Starting with local AI.
```

If everything is ready:

```
Running with local AI (llama3.2)
This is slower than cloud APIs but completely free and private.
For best quality, run: bristlenose config set-key claude

  ✓ Ingested 5 sessions                          0.1s
  ✓ Extracted audio                              12.3s
  ...
```

#### Why This Works

1. **Zero signup** — no account creation, no email, no payment
2. **Privacy reinforcement** — "completely free and private" echoes our core pitch
3. **Low commitment** — try before deciding if it's worth $1.50/study
4. **Graceful upgrade path** — once they see value, "bristlenose config set-key claude" is easy
5. **Works offline** — useful for researchers in the field or on planes

#### Model Recommendations

Based on [Ollama's structured output documentation](https://ollama.com/blog/structured-outputs), these models work well with JSON schemas:

| Model | Download | RAM | Quality | Speed | Notes |
|-------|----------|-----|---------|-------|-------|
| **llama3.2:3b** | 2.0 GB | ~4 GB | Good | Fast | **Default** — fits most laptops |
| **llama3.2:1b** | 1.3 GB | ~2 GB | OK | Very fast | For older machines, Chromebooks |
| **mistral:7b** | 4.1 GB | ~8 GB | Better | Medium | Better reasoning |
| **qwen2.5:7b** | 4.4 GB | ~8 GB | Better | Medium | Good multilingual (CJK) |
| **llama3.1:8b** | 4.7 GB | ~8 GB | Best | Slower | Closest to cloud quality |

**Default: `llama3.2:3b`**

Rationale:
- 2 GB download is tolerable for first-time users
- 4 GB RAM requirement fits most modern laptops (8 GB total)
- Good enough for structured output tasks
- Fast enough that users see results quickly

#### Quality Trade-offs (Be Honest in Messaging)

Local models are genuinely worse than Claude/GPT-4o for our tasks:

| Aspect | Claude Sonnet | llama3.2:3b | Notes |
|--------|---------------|-------------|-------|
| JSON schema compliance | ~99% | ~85% | May need retries |
| Quote extraction | Nuanced | Good | Misses subtle insights |
| Speaker identification | Excellent | Good | Occasional confusion |
| Theme grouping | Excellent | OK | Less coherent themes |
| Speed (5 interviews) | ~2 min | ~10 min | On M2 MacBook |

**Key insight:** For a first try, "good enough to see if the tool is useful" is sufficient. Users who see value will upgrade to cloud APIs for production runs.

**Messaging in CLI output:**

```
Running with local AI (llama3.2)
This is slower and less accurate than cloud APIs, but completely free and private.
For production quality, run: bristlenose config set-key claude
```

The message is honest about trade-offs while suggesting the upgrade path.

#### Implementation Details

**Ollama detection:**

```python
def check_ollama() -> tuple[bool, str, str | None]:
    """Check if Ollama is running and has a suitable model.

    Returns:
        (is_available, message, recommended_model)
    """
    import httpx

    try:
        # Check Ollama is running
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return False, "Ollama not responding", None

        models = r.json().get("models", [])

        # Look for suitable models in priority order
        preferred = ["llama3.2:3b", "llama3.2", "llama3.1:8b", "mistral:7b", "qwen2.5:7b"]
        for model in preferred:
            if any(m["name"].startswith(model.split(":")[0]) for m in models):
                return True, f"Found {model}", model

        # Check for any llama/mistral/qwen model
        suitable = [m["name"] for m in models if any(
            m["name"].startswith(p) for p in ["llama", "mistral", "qwen"]
        )]
        if suitable:
            return True, f"Found {suitable[0]}", suitable[0]

        return False, "No suitable model found", None

    except httpx.ConnectError:
        return False, "Ollama not running", None
```

**Auto-pull model with progress:**

```python
import subprocess
import sys

def pull_model(model: str = "llama3.2:3b") -> bool:
    """Pull model from Ollama registry. Shows progress to user."""
    console.print(f"Downloading {model}...")
    console.print("[dim]This may take a few minutes depending on your connection.[/dim]")

    result = subprocess.run(
        ["ollama", "pull", model],
        stdout=sys.stdout,  # Show Ollama's progress bar
        stderr=sys.stderr,
    )

    if result.returncode == 0:
        console.print(f"[green]✓[/green] Downloaded {model}")
        return True
    else:
        console.print(f"[red]Failed to download {model}[/red]")
        return False
```

**Retry logic for structured output failures:**

Local models sometimes produce malformed JSON. Add retry with backoff:

```python
async def _analyze_local_with_retry(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int,
    max_retries: int = 3,
) -> T:
    """Call local model with retry for JSON parsing failures."""
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await self._analyze_openai_compatible(
                system_prompt, user_prompt, response_model, max_tokens
            )
        except json.JSONDecodeError as e:
            last_error = e
            logger.debug(f"JSON parse failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # Backoff

    raise RuntimeError(
        f"Local model failed to produce valid JSON after {max_retries} attempts. "
        f"Last error: {last_error}. "
        f"Try a larger model (--model llama3.1:8b) or use cloud API."
    )
```

**First-run flow integration:**

```python
def _prompt_for_provider() -> str:
    """Interactive prompt when no provider is configured."""
    console.print()
    console.print("[bold]No LLM provider configured.[/bold] Choose one:")
    console.print()
    console.print("  [1] Local AI (free, private, slower)")
    console.print("      [dim]Requires Ollama — https://ollama.ai[/dim]")
    console.print()
    console.print("  [2] Claude API (best quality, ~$1.50/study)")
    console.print("      [dim]Get a key from console.anthropic.com[/dim]")
    console.print()
    console.print("  [3] ChatGPT API (good quality, ~$1.00/study)")
    console.print("      [dim]Get a key from platform.openai.com[/dim]")
    console.print()

    choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="1")

    if choice == "1":
        return _setup_local_provider()
    elif choice == "2":
        console.print()
        console.print("Get your API key from: [link]https://console.anthropic.com/settings/keys[/link]")
        console.print("Then run: [bold]bristlenose config set-key claude[/bold]")
        raise typer.Exit(0)
    else:  # choice == "3"
        console.print()
        console.print("Get your API key from: [link]https://platform.openai.com/api-keys[/link]")
        console.print("Then run: [bold]bristlenose config set-key chatgpt[/bold]")
        raise typer.Exit(0)

def _setup_local_provider() -> str:
    """Set up local provider, pulling model if needed."""
    is_available, message, model = check_ollama()

    if not is_available and "not running" in message:
        console.print()
        console.print("[yellow]Ollama not found.[/yellow]")
        console.print()
        console.print("Install it from: [link]https://ollama.ai[/link]")
        console.print("[dim](It's a single download, no account needed)[/dim]")
        console.print()
        console.print("After installing, run:")
        console.print("  [bold]ollama pull llama3.2[/bold]")
        console.print()
        console.print("Then try again:")
        console.print("  [bold]bristlenose run ./interviews[/bold]")
        console.print()

        if Confirm.ask("Open the download page?", default=True):
            import webbrowser
            webbrowser.open("https://ollama.ai")

        raise typer.Exit(0)

    if not is_available and "No suitable model" in message:
        console.print()
        console.print("[yellow]Ollama is running, but no suitable model found.[/yellow]")
        console.print()
        if Confirm.ask("Download llama3.2 (2.0 GB)?", default=True):
            if pull_model("llama3.2:3b"):
                return "local"
            else:
                raise typer.Exit(1)
        raise typer.Exit(0)

    # Ready to go
    console.print()
    console.print(f"[green]✓[/green] Using local AI ({model})")
    console.print("[dim]This is slower than cloud APIs but completely free and private.[/dim]")
    console.print("[dim]For production quality: bristlenose config set-key claude[/dim]")
    console.print()

    return "local"
```

#### Doctor Integration

Update `bristlenose doctor` to show Ollama status:

```
bristlenose doctor

  FFmpeg          ok   7.1
  Whisper         ok   MLX (Apple Silicon)
  LLM provider    ok   Local (llama3.2:3b via Ollama)
                       [dim]For best quality: bristlenose config set-key claude[/dim]
```

Or if no API key and no Ollama:

```
bristlenose doctor

  FFmpeg          ok   7.1
  Whisper         ok   MLX (Apple Silicon)
  LLM provider    !!   No provider configured
                       Quick start (free): install Ollama from https://ollama.ai
                       Best quality: bristlenose config set-key claude
```

#### Requirements Summary

To make Ollama the "just try it" path:

1. **Ollama detection** — check if running, find suitable models
2. **Interactive first-run prompt** — offer choices, guide setup
3. **Model auto-pull** — download default model with consent
4. **Retry logic** — handle JSON parsing failures gracefully
5. **Honest messaging** — be clear about quality trade-offs
6. **Doctor integration** — show local provider status

**Effort estimate:** ~4-5 hours (including testing with different models)

**Priority:** HIGH — this removes the biggest adoption barrier. A user who can try the tool for free in 10 minutes is more likely to eventually become a paying cloud API user.

---

### macOS Keychain Integration

**Why:** macOS is likely the primary platform for our user base (researchers, designers). Storing API keys in `.env` files is:
1. **Insecure** — plain text on disk, easy to accidentally commit to git
2. **Inconvenient** — manual copy-paste, separate file per project
3. **Non-standard** — macOS users expect credentials in Keychain

**Goal:** `bristlenose` should read API keys from macOS Keychain automatically, with `.env`/environment as fallback.

#### Implementation Options

**Option A: Use `keyring` library (recommended)**

The [`keyring`](https://pypi.org/project/keyring/) library provides cross-platform credential storage with native macOS Keychain support.

```python
# In config.py — add fallback chain
def _get_api_key(service: str, env_var: str, settings_field: str) -> str:
    """Get API key from Keychain, then env var, then settings field."""
    # 1. Try Keychain (macOS/Windows/Linux secret service)
    try:
        import keyring
        key = keyring.get_password("bristlenose", service)
        if key:
            return key
    except Exception:
        pass  # keyring not available or failed

    # 2. Try environment variable
    key = os.environ.get(env_var, "")
    if key:
        return key

    # 3. Fall back to settings (from .env file)
    return settings_field

# Usage in BristlenoseSettings or LLMClient:
anthropic_key = _get_api_key("anthropic", "BRISTLENOSE_ANTHROPIC_API_KEY", settings.anthropic_api_key)
```

**CLI for setting keys:**

```bash
# Store key in Keychain
bristlenose config set-key anthropic
# Prompts: Enter your Claude API key: ********
# Stores in Keychain as service="bristlenose", username="anthropic"

# Or one-liner
bristlenose config set-key anthropic --value sk-ant-...

# List configured providers
bristlenose config list-keys
# anthropic  ✓ (Keychain)
# openai     ✓ (env var)
# azure      ✗ (not configured)

# Remove key
bristlenose config delete-key anthropic
```

**Implementation:**

```python
# New file: bristlenose/keychain.py
"""Keychain integration for secure API key storage."""

import sys

def _get_keyring():
    """Get keyring module, or None if unavailable."""
    try:
        import keyring
        # Verify backend is available (not the "fail" backend)
        if keyring.get_keyring().__class__.__name__ == "Keyring":
            return None  # No real backend
        return keyring
    except ImportError:
        return None

def get_key(service: str) -> str | None:
    """Get API key from system keyring."""
    kr = _get_keyring()
    if kr is None:
        return None
    try:
        return kr.get_password("bristlenose", service)
    except Exception:
        return None

def set_key(service: str, key: str) -> bool:
    """Store API key in system keyring. Returns True on success."""
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.set_password("bristlenose", service, key)
        return True
    except Exception:
        return False

def delete_key(service: str) -> bool:
    """Remove API key from system keyring. Returns True on success."""
    kr = _get_keyring()
    if kr is None:
        return False
    try:
        kr.delete_password("bristlenose", service)
        return True
    except Exception:
        return False

def list_keys() -> dict[str, bool]:
    """Return dict of service -> is_configured."""
    services = ["anthropic", "openai", "azure", "google"]
    return {s: get_key(s) is not None for s in services}
```

**Dependency:**

```toml
# In pyproject.toml — optional dependency
[project.optional-dependencies]
keychain = ["keyring>=25.0.0"]

# Or make it a regular dependency (adds ~1 MB)
dependencies = [
    ...
    "keyring>=25.0.0",
]
```

**Security note from keyring docs:**
> Any Python script can access secrets created by keyring from that same Python executable without the OS prompting for a password.

This is acceptable for CLI tools. For higher security, users can configure Keychain Access to require password on each access.

#### Option B: Direct macOS `security` command (no dependency)

Use subprocess to call macOS `security` CLI directly:

```python
import subprocess

def get_key_macos(service: str) -> str | None:
    """Get key from macOS Keychain using security CLI."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "bristlenose", "-a", service, "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None  # Not found

def set_key_macos(service: str, key: str) -> bool:
    """Store key in macOS Keychain using security CLI."""
    try:
        # Delete existing (ignore if not found)
        subprocess.run(
            ["security", "delete-generic-password", "-s", "bristlenose", "-a", service],
            capture_output=True, check=False,
        )
        # Add new
        subprocess.run(
            ["security", "add-generic-password", "-s", "bristlenose", "-a", service, "-w", key],
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
```

**Pros:** No dependency, macOS-native
**Cons:** macOS only, shell escaping risks, less robust

**Recommendation:** Use `keyring` library — it's well-maintained, cross-platform, and handles edge cases properly.

#### Integration with `doctor` Command

Update `bristlenose doctor` to show Keychain status:

```
  API key        ok   Claude (Keychain)
  API key        ok   ChatGPT (env var)
```

Or with warning:

```
  API key        !!   API key in .env file — consider using Keychain
                      Run: bristlenose config set-key anthropic
```

#### Priority

**Do after Azure + Gemini providers.** Keychain is a UX improvement, not a blocker. Users can still use `.env` files. But it should come before v1.0.0 since it's table stakes for a Mac-native tool.

**Effort:** ~3 hours (including CLI commands and doctor integration)

### Implementation Order (Revised — Ollama First)

The zero-friction entry point is the highest value feature for adoption. Build Ollama support first, then layer on enterprise providers.

**Phase 1: Foundation + Ollama (~5 hours)** ← START HERE
1. Create `bristlenose/providers.py` with `ProviderSpec` registry
2. Refactor `LLMClient` to use registry + `_analyze_openai_compatible()`
3. Add Local (Ollama) provider with detection and retry logic
4. Add first-run interactive prompt when no provider configured
5. Add model auto-pull with progress display
6. Update doctor to show Ollama status and guide users

**Why Ollama first:**
- Removes biggest adoption barrier (API key requirement)
- Uses OpenAI SDK — same code path tests the abstraction
- Zero new dependencies (unlike Gemini)
- Users can try the tool for free immediately

**Phase 2: Azure OpenAI (~2 hours)**
1. Add Azure to registry (same SDK as Ollama, different client config)
2. Add doctor validation for Azure credentials
3. Test with enterprise deployment

**Phase 3: ✅ Keychain Integration — DONE**
1. ✅ Created `bristlenose/credentials.py` (abstraction), `credentials_macos.py` (macOS Keychain via `security` CLI), `credentials_linux.py` (Linux Secret Service via `secret-tool`)
2. ✅ Added `bristlenose configure <provider>` CLI command with `--key` option
3. ✅ Updated credential loading to check Keychain first (priority: keychain → env var → .env)
4. ✅ Updated doctor to show "(Keychain)" suffix when key comes from keychain
5. ✅ Validates keys before storing — catches typos/truncation
6. ✅ Tests in `tests/test_credentials.py` (25 tests)

**Phase 4: Gemini (~3 hours)**
1. Add `google-genai` dependency
2. Add Gemini to registry
3. Add `_analyze_gemini()` method (different SDK pattern)
4. Test with all 5 Pydantic schemas

**Phase 5: Documentation + Polish (~2 hours)**
1. Update README with "Choosing an LLM provider" section
2. Update `bristlenose help config` with all providers
3. Update man page
4. Add provider examples to `.env.example`

**Total: ~15 hours**

The order prioritises:
1. ✅ **Adoption** (Ollama removes the biggest barrier) — DONE
2. **Enterprise** (Azure unblocks corporate users)
3. ✅ **UX polish** (Keychain secure credential storage) — DONE
4. **Budget option** (Gemini is cheaper but requires new SDK)

---

### Files to Create/Modify

```
bristlenose/
├── providers.py          # ✅ DONE: ProviderSpec, PROVIDERS registry, resolve_provider()
├── credentials.py        # ✅ DONE: CredentialStore ABC, EnvCredentialStore fallback, get_credential()
├── credentials_macos.py  # ✅ DONE: MacOSCredentialStore using `security` CLI
├── credentials_linux.py  # ✅ DONE: LinuxCredentialStore using `secret-tool`, fallback to env
├── config.py             # ✅ DONE: loads from keychain via _populate_keys_from_keychain()
├── llm/
│   ├── client.py         # MODIFY: use registry, add _analyze_openai_compatible(), _analyze_gemini()
│   └── pricing.py        # MODIFY: add Gemini models, use registry for URLs
├── cli.py                # ✅ DONE: added `configure` command
└── doctor.py             # ✅ DONE: shows key source (Keychain vs env)

tests/
├── test_providers.py     # ✅ DONE: registry tests, alias resolution (47 tests)
├── test_credentials.py   # ✅ DONE: credential store tests (25 tests)
└── test_llm_client.py    # MODIFY: test new providers with mocked SDKs
```

### Testing Strategy

Each provider needs:
1. **Unit tests** — mock the SDK, test dispatch and parsing
2. **Integration tests** (optional, requires credentials) — real API calls
3. **Doctor tests** — validation logic

For local models, add a CI job that runs Ollama in Docker and tests with a small model.

### Documentation

Update:
- `bristlenose doctor` output to show which providers are configured
- `bristlenose help config` to list all provider env vars
- Man page with provider configuration examples
- README with "Enterprise deployment" section

### Won't do

- **Context-aware API key errors** (#4) — current messages are fine
- **`--force` flag** (#3) — `render` command already handles this use case
- **Cap Typer help width** (#11) — no clean hook, accept inconsistency
- **Full `--dry-run`** (#9) — time estimate warning is more useful
