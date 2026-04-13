# Design: Hardware-Aware Gemma 4 Local Model Recommendations

_13 Apr 2026 — research & plan, not yet implemented._

## Problem

Bristlenose recommends `llama3.2:3b` as the default local model regardless of hardware. A researcher with a 48 GB M4 Max gets the same 3B model as someone on an 8 GB M3. Gemma 4 (released 2 Apr 2026) offers dramatically better models at every tier, with native structured JSON support and Apache 2.0 licensing.

## Gemma 4 model family

Four models, all Apache 2.0:

| Ollama tag | Params | Context | Weights (Q4) | Min RAM | Comfortable RAM |
|---|---|---|---|---|---|
| `gemma4:e2b` | 2.3B effective | 128K | ~2 GB | 8 GB | 8 GB |
| `gemma4:e4b` | 4.5B effective | 128K | ~3 GB | 8 GB | 16 GB |
| `gemma4:26b` | 26B MoE (4B active) | 256K | ~16 GB | 24 GB | 36 GB |
| `gemma4:31b` | 31B dense | 256K | ~20 GB | 32 GB | 48 GB |

**There is no 12B model.** The gap between E4B and 26B MoE is intentional — E4B targets edge, 26B targets quality.

### Benchmarks (vs Gemma 3 27B)

| Benchmark | Gemma 3 | Gemma 4 31B |
|---|---|---|
| AIME 2026 (math) | 20.8% | 89.2% |
| LiveCodeBench (code) | 29.1% | 80.0% |
| GPQA (science) | 42.4% | 84.3% |
| Agentic tool use (tau2-bench) | 6.6% | 86.4% |

Still below Claude and GPT-4o on reasoning, but dramatically better than any prior open model at these sizes.

### Structured JSON support

Gemma 4 has **native structured JSON output** — not bolted on via system prompt hacks. The 26B MoE scores 85.5% on agentic tool-use benchmarks, the 31B hits 86.4%. This is a significant improvement over llama3.2:3b (~85% JSON schema compliance in Bristlenose testing).

Bristlenose uses `response_format={"type": "json_object"}` via Ollama's OpenAI-compatible API — **not** tool/function calling. This matters because:

### Known Ollama issues (as of Apr 2026)

- **Tool calling is broken in Ollama v0.20.0** — streaming drops tool calls entirely, data goes into the reasoning field. **Does not affect Bristlenose** — we use JSON mode, not tool calling.
- **26B MoE memory pressure** — on 24 GB Mac mini, consumes nearly all unified memory and causes heavy swapping under concurrent requests. With `llm_concurrency=3` (Bristlenose default), this would be amplified. Only recommend 26B for 36 GB+ machines.
- **CUDA 13.2 runtime causes garbage output** with GGUF quantisations. Must be avoided on Linux/NVIDIA.

## Proposed memory tiers

| System RAM | Recommended model | Download | Notes |
|---|---|---|---|
| >= 48 GB | `gemma4:31b` | ~20 GB | Near cloud quality, flagship |
| >= 36 GB | `gemma4:26b` | ~16 GB | MoE, good quality/RAM trade-off |
| >= 16 GB | `gemma4:e4b` | ~3 GB | Solid default, leaves room for OS |
| >= 8 GB | `gemma4:e4b` | ~3 GB | Tight but workable |
| < 8 GB | `llama3.2:3b` | ~2 GB | Gemma E2B untested for JSON |

**Gap at 24 GB:** No good Gemma 4 fit — E4B is capable but small, 26B causes swapping. Options: (a) recommend E4B at this tier too, (b) keep `qwen2.5:7b` or `llama3.1:8b` as the 24 GB recommendation, (c) test whether 26B works at `llm_concurrency=1`. Decision deferred to implementation.

## Implementation plan

### Step 1: hardware.py — Model RAM mapping + recommendation

File: `bristlenose/utils/hardware.py`

Add a named tuple (not bare tuple — review feedback) and module-level constant:

```python
class ModelRAM(NamedTuple):
    weights_gb: float
    min_ram_gb: float
    comfortable_ram_gb: float

LOCAL_MODEL_RAM: dict[str, ModelRAM] = {
    "gemma4:e2b":   ModelRAM(2.0,  8.0,  8.0),
    "gemma4:e4b":   ModelRAM(3.0,  8.0,  16.0),
    "gemma4:26b":   ModelRAM(16.0, 24.0, 36.0),
    "gemma4:31b":   ModelRAM(20.0, 32.0, 48.0),
    "llama3.2:3b":  ModelRAM(2.0,  4.0,  8.0),
    "llama3.2:1b":  ModelRAM(1.0,  4.0,  4.0),
    "llama3.1:8b":  ModelRAM(5.0,  8.0,  16.0),
    "mistral:7b":   ModelRAM(4.0,  8.0,  16.0),
    "qwen2.5:7b":   ModelRAM(4.0,  8.0,  16.0),
}
```

Add `recommended_local_model` property to `HardwareInfo` (mirrors existing `recommended_whisper_model` pattern):

```python
@property
def recommended_local_model(self) -> str:
    if self.memory_gb is not None:
        if self.memory_gb >= 48:
            return "gemma4:31b"
        if self.memory_gb >= 36:
            return "gemma4:26b"
        if self.memory_gb >= 8:
            return "gemma4:e4b"
    return "llama3.2:3b"  # safe floor for < 8 GB or unknown
```

Add standalone `local_model_fits(model: str, memory_gb: float | None) -> bool | None`.

Update module docstring (currently says "transcription backend" — now also covers LLM model selection).

### Step 2: ollama.py — PREFERRED_MODELS, prefix list

File: `bristlenose/ollama.py`

Update `PREFERRED_MODELS`:

```python
PREFERRED_MODELS = [
    "gemma4:e4b",     # Gemma 4 E4B — good default, 3 GB download
    "gemma4:31b",     # Gemma 4 31B Dense — near cloud quality
    "gemma4:26b",     # Gemma 4 26B MoE — quality/RAM trade-off
    "gemma4:e2b",     # Gemma 4 E2B — minimal
    "llama3.2:3b",    # Previous default — fallback
    "llama3.2",
    "llama3.2:1b",
    "llama3.1:8b",
    "mistral:7b",
    "qwen2.5:7b",
]
```

Add `"gemma"` to suitable-model prefix check (line 79).

**Do NOT change `DEFAULT_MODEL`** — keep `llama3.2:3b` so existing users who never set `BRISTLENOSE_LOCAL_MODEL` are unaffected. The hardware-aware CLI flow recommends Gemma 4 for new users; the default is the safe fallback.

### Step 3: config.py — NO CHANGE

**Keep `local_model: str = "llama3.2:3b"`.** Changing the Pydantic default would silently break existing local users on their next run (model not found). The interactive first-run flow and doctor tips handle the Gemma 4 recommendation for new and existing users respectively.

### Step 4: providers.py — Minimal update

Update `ProviderSpec` `default_model` to `"gemma4:e4b"` (this is registry metadata for display/documentation, not the runtime default — that comes from config.py).

### Step 5: cli.py — Hardware-aware _setup_local_provider()

The biggest change. Restructure `_setup_local_provider()`:

1. **Return type** changes from `str | None` to `tuple[str, str] | None` — returns `("local", model_name)` so the model flows through to `load_settings(local_model=...)`.

2. **Detect hardware** at the top — call `detect_hardware()` for `memory_gb` and `chip_name`.

3. **Show hardware info + recommendation:**
   ```
     Apple M4 Max · 48 GB memory

     Recommended: gemma4:31b (20 GB download, ~30 min on broadband)
     Near cloud quality, runs entirely on your Mac.

     [Y] Download gemma4:31b
     [s] Smaller model instead (gemma4:e4b, 3 GB)
     [n] Cancel
   ```

4. **If user already has a suitable model pulled**, show it and offer upgrade:
   ```
     You already have llama3.2:3b installed.

     Recommended upgrade: gemma4:e4b (3 GB download)
     Better quality for research analysis.

     [Y] Download gemma4:e4b
     [k] Keep using llama3.2:3b
     [n] Cancel
   ```

5. **Disk space check** before large downloads — `shutil.disk_usage()`.

6. **Retry on download failure** — offer `[r] Retry / [n] Cancel` instead of exiting the entire flow. Mention Ollama supports resume.

7. **Update `_maybe_prompt_for_provider()`** to unpack the tuple and pass `local_model=model` to `load_settings()`.

8. **Use "memory" not "unified memory"** on all platforms — chip name already signals Apple Silicon.

9. **Provider menu text** — soften from `"Local AI (free, private, slower)"` to `"Local AI (free, private)"`. Move speed qualifier to the hardware-specific recommendation.

10. Update all hardcoded `"ollama pull llama3.2"` messages.

### Step 6: doctor.py — RAM warning + upgrade tip

In `check_local_provider()`, after validation succeeds:

1. **RAM warning** (WARN, not FAIL) if model's `comfortable_ram_gb > memory_gb`:
   ```
   Model gemma4:31b needs more memory than available (48 GB needed, 16 GB available).
   It may run extremely slowly. Recommended for your hardware: gemma4:e4b
   ```

2. **Upgrade tip** (SKIP/note) for existing local users on older models:
   ```
   Tip: gemma4:e4b works well on your hardware (you're using llama3.2:3b)
   ```

### Step 7: doctor_fixes.py — Dynamic model name

Use `DEFAULT_MODEL` from `ollama.py` instead of hardcoded `"llama3.2"`.

### Step 8: llm/client.py — Update stale error message

Line 596 hardcodes `"--model llama3.1:8b"` in a suggestion message. Update to reference `gemma4:e4b` or make it dynamic.

### Step 9: Tests

All mocked — CI has no Ollama.

- `test_hardware.py` — `TestRecommendedLocalModel` at tiers (8, 16, 36, 48 GB), `TestLocalModelFits`, test `ModelRAM` named tuple
- `test_providers.py` — update `test_local_spec` for new default_model
- `test_provider_horror_scenarios.py` — add `test_ollama_model_oversized_for_ram`
- `test_ollama.py` (new) — test `check_ollama()` finds gemma4 variants via mocked API

### Step 10: Documentation

- This file (`docs/design-gemma4-local-models.md`) — the plan
- `bristlenose/llm/CLAUDE.md` — update local provider section
- `SECURITY.md` — document hardware cache file, local model provenance
- `CHANGELOG.md` — prominent entry noting new Gemma 4 recommendations

## Review findings — outstanding issues

The plan was reviewed by code-review, security-review, and ux-critique agents. Below are findings that were incorporated into the revised plan above, and issues that remain open.

### Incorporated into revised plan

| # | Finding | Resolution |
|---|---|---|
| 1 | Changing config.py default breaks existing users | **Keep `llama3.2:3b` as config default.** Only the interactive flow recommends Gemma 4 |
| 3 | Fallback for <8 GB recommends model needing 8 GB | **Fall back to `llama3.2:3b`** for <8 GB |
| 5 | Ollama tag names wrong (gemma4:4b vs gemma4:e4b) | **Corrected all tags** from web research — e2b, e4b, 26b, 31b. No 12B model exists |
| 6 | Bare tuple not self-documenting | **Use `NamedTuple`** (`ModelRAM`) |
| 7 | hardware.py docstring scope | **Update docstring** |
| 8 | Hardware cache not in SECURITY.md | **Add to Step 10** |
| 9 | Model provenance undocumented | **Add to Step 10** |
| 15 | No smaller-model escape hatch | **Added `[s] Smaller model` option** to download prompt |
| 16 | Menu still says "slower" | **Softened to "free, private"** |
| 17 | No download time estimate or disk check | **Added both** to Step 5 |
| 18 | No retry on download failure | **Added retry prompt** to Step 5 |
| 19 | No upgrade tip for existing users | **Added to Step 6** (doctor note) |
| 21 | "Unified memory" is jargon | **Use plain "memory"** everywhere |
| 22 | "MoE" and "runs fast" in user text | **Removed jargon**, use factual descriptions |

### Open issues — deferred to implementation

| # | Issue | Status |
|---|---|---|
| 2 | **Gemma 4 structured JSON reliability unvalidated.** Must run the 5 pipeline prompts against each Gemma 4 variant before shipping. If JSON compliance is below llama3.2 baseline (~85%), keep llama3.2 as default and offer Gemma 4 only as experimental | **MUST DO before merge** |
| 4 | Stale `"--model llama3.1:8b"` in llm/client.py error message | Added as Step 8 |
| 10 | `recommended_local_model` as property vs standalone function. Property mirrors `recommended_whisper_model` (consistency) but couples hardware.py to LLM knowledge | **Decision: use property** for consistency with existing pattern. The coupling is acceptable — hardware.py already recommends whisper models |
| 11 | Already-pulled model: prefer existing or suggest upgrade? | **Decision: show both options** (download new / keep existing / cancel) |
| 12 | Should recommendation use `comfortable_ram_gb` from the dict? | **Decision: yes** — derive thresholds from `comfortable_ram_gb` in `LOCAL_MODEL_RAM` rather than duplicating magic numbers |
| 13 | Google-branded model for "local privacy" path | **Decision: acceptable** — Gemma 4 via Ollama is genuinely local (no data egress). The framing "runs entirely on your Mac" is sufficient. Monitor for user feedback |
| 14 | CUDA/Linux: system RAM vs GPU VRAM | **Parked** — Ollama handles GPU offloading automatically. Ship Apple Silicon first, address CUDA VRAM detection later |
| 20 | Validate model tag format with regex | **Nice to have** — `subprocess.run` uses list form so not exploitable, but cheap defence-in-depth |
| 23 | Non-interactive (no TTY) environments | **Should add** — detect `sys.stdin.isatty()` and skip interactive prompts |
| 24 | Prominent CHANGELOG entry | Added to Step 10 |
| — | **24 GB RAM gap** — no good Gemma 4 fit between E4B and 26B. Test whether 26B works at `llm_concurrency=1` before deciding | **Deferred to testing** |
| — | **26B + concurrency=3 memory pressure** — may need to auto-reduce `llm_concurrency` for 26B on tight RAM | **Deferred to testing** |

## Sources

- [Ollama Gemma 4 library — all tags](https://ollama.com/library/gemma4/tags)
- [Google Blog — Gemma 4 announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
- [Gemma 4 — Google DeepMind](https://deepmind.google/models/gemma/gemma-4/)
- [Gemma 4 Benchmarks — Medium](https://medium.com/@moksh.9/heres-a-tighter-benchmark-focused-blog-post-501c5ea829f4)
- [Gemma 4 Review 2026 — DEV Community](https://dev.to/techsifted/google-gemma-4-review-2026-apache-20-license-benchmarks-commercial-use-3iea)
- [Mac mini Ollama + Gemma 4 12B setup — GitHub Gist](https://gist.github.com/greenstevester/fc49b4e60a4fef9effc79066c1033ae5)
- [Gemma 4 tool calling broken — GitHub Issue](https://github.com/anomalyco/opencode/issues/20995)
- [Unsloth — CUDA 13.2 warning, run locally](https://unsloth.ai/docs/models/gemma-4)
- [Gemma 4 VRAM requirements guide](https://gemma4guide.com/guides/gemma4-vram-requirements)
- [Gemma 4 on Apple Silicon — CloudInsight](https://cloudinsight.cc/en/blog/gemma-4-apple-silicon)
- [Antigravity Lab — local code review with Gemma 4](https://antigravitylab.net/en/articles/editor/antigravity-gemma4-private-code-review-local-setup)
- [HuggingFace — Welcome Gemma 4](https://huggingface.co/blog/gemma4)
- [Artificial Analysis — Gemma 4 31B](https://artificialanalysis.ai/models/gemma-4-31b)
