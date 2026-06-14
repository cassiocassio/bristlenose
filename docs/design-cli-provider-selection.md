# CLI Provider & Model Selection — design + implementation plan

**Status: PROPOSAL — under review (not implemented).** Drafted 10 Jun 2026.

This doc specifies how the **CLI** chooses which LLM provider and model to use,
replacing the current hardcoded `anthropic` / `claude-sonnet-4` defaults with a
derive-or-diagnose model. Desktop selection is unchanged (the Swift host injects
provider+model explicitly); see §Desktop interplay for the toes this must not
tread on.

---

## 1. Principles

1. **A key is a secret; "which provider/model" is a preference.** Different
   stores, different verbs. Adding a key must never silently change the active
   provider.
2. **No hardcoded vendor default in the CLI happy path.** A fresh install with
   no keys should *diagnose* (help you set one up), not silently try Claude.
3. **First/only key just works — by derivation, not stored state.** When exactly
   one cloud provider has a key and nothing explicit is chosen, use it. No
   persisted "first-ever" marker to drift.
4. **Beyond one key, you're explicit.** Two-plus keys with no selection →
   actionable error/diagnostic, never an arbitrary pick.
5. **Interactive may offer; scripted never surprises.** Prompts only on a TTY;
   non-interactive contexts fail with an actionable message + the exact env
   var/flag to set. `configure` is always idempotent.
6. **The flat "default model per provider" is transitional.** It survives only
   until per-stage model selection (`bristlenose pipeline`) drives execution. v1
   reframes it (provider-derived, not a Claude string); it is not deleted.

---

## 2. Provider resolution (the ladder)

On every CLI run, provider is resolved in this order (first match wins):

| # | Source | Scope |
|---|--------|-------|
| 1 | `--llm <provider>` | per run |
| 2 | `BRISTLENOSE_LLM_PROVIDER` env var (incl. `.env`, `bristlenose.toml`) | per shell / project |
| 3 | **the sole cloud provider that has a key** (derived) | per machine |
| 4a | **0 keys** → diagnostic (TTY) / error (non-TTY) | — |
| 4b | **2+ keys, none selected** → ambiguity error listing configured providers | — |

`local` (Ollama) is **never derived** — it is used only when explicitly chosen
(`--llm local` / env), because "I have no cloud key" must surface the choice
between *get a key* and *go local*, not silently pick local.

### What changes vs today

- Today: `BristlenoseSettings.llm_provider` field defaults to `"anthropic"`
  (`config.py:106`), so step 3/4 don't exist — a keyless run silently resolves
  to Claude, then `_needs_provider_prompt` (`cli.py:381`) only rescues the
  narrow "provider==anthropic AND no anthropic key" case.
- After: steps 3/4 are added **for the CLI only** (gated on
  `not hosted_by_desktop()`). The field default is retained as an internal
  backstop the desktop relies on (see §Desktop interplay) — but the CLI no
  longer *reaches* it on the happy path.

---

## 3. `configure` behaviour (secrets only)

`bristlenose configure <provider>` continues to **only validate + store a key**
(`cli.py:1892`). It never writes a provider preference. Two refinements:

- **First key (0→1 transition):** print "you can now run: `bristlenose run …`"
  (unchanged). No selection is written — derivation (step 3) makes it active.
- **Subsequent key (now 2+):** print a one-line, TTY-and-script-safe hint:
  > `ChatGPT key stored. You now have 2 providers (Claude, ChatGPT). Pick one`
  > `per run with --llm chatgpt, or set BRISTLENOSE_LLM_PROVIDER=chatgpt.`

No interactive "make this active?" prompt in v1 (keeps `configure`
deterministic; the offer is deferred — see §Open decisions).

---

## 4. Diagnostics

- **0 keys, TTY:** existing `_prompt_for_provider` menu (`cli.py:405`) — Claude /
  ChatGPT / Azure / Gemini / Local, with where-to-get-a-key links.
- **0 keys, non-TTY:** exit 2 with "No AI provider configured. Run
  `bristlenose configure <claude|chatgpt|gemini|azure>` or set
  `BRISTLENOSE_LLM_PROVIDER` + the matching key." **Never prompt** (a prompt in
  CI hangs the job).
- **2+ keys, none selected, any context:** exit 2 (non-TTY) / short diagnostic +
  re-prompt (TTY) listing the configured providers and the two ways to choose.
- **Selected provider has no key** (e.g. `BRISTLENOSE_LLM_PROVIDER=gemini`, no
  Gemini key): preflight error "provider Gemini selected but no Gemini key found
  — run `bristlenose configure gemini`." (This is the cross-store reconciliation;
  it already half-exists in the api-key preflight, `preflight/api_key.py`.)

TTY detection: `sys.stdin.isatty() and sys.stdout.isatty()`; honour the existing
`BRISTLENOSE_SKIP_PREFLIGHT` / non-interactive conventions.

---

## 5. Model selection (reframe, don't delete)

- The flat `llm_model` field default (`config.py:109`,
  `"claude-sonnet-4-20250514"`) is **provider-coupled today** only because
  `_fill_provider_default_model` (`config.py:369`) snaps a never-chosen model to
  the *resolved provider's* `default_model` (from `PROVIDERS`, `providers.py`).
  With the new derive logic this already produces gpt-4o for a sole-ChatGPT
  setup, etc.
- **v1 change:** stop documenting a single model default. Man page + README +
  `.env.example` say "defaults to the selected provider's recommended model,"
  not a fixed Claude string. Optionally set the field default to `""` and let
  `_fill_provider_default_model` always fill from the provider spec (removes the
  Claude hardcode from the field) — *flagged as a sub-decision* because empty
  default has a blast radius on any code reading `llm_model` directly.
- **Future home:** the per-(stage, provider) matrix that `bristlenose pipeline`
  already renders. When per-stage selection drives execution, the flat
  `llm_model` retires. Not in scope here.

---

## 6. Example sessions (the playback)

### S1 — Fresh install, no keys, interactive
```
$ bristlenose interviews/
Bristlenose v0.16.0 · Apple M2 · 32 GB

No AI provider configured. Choose one:
  [1] Claude API   (recommended, ~$1.50/study)   console.anthropic.com
  [2] ChatGPT API  (~$1.00/study)                platform.openai.com
  [3] Azure OpenAI (enterprise)
  [4] Gemini API   (budget, ~$0.20/study)        aistudio.google.com
  [5] Local AI     (free, private, slower)       ollama.ai
Choice [1]: 2

Get your key from: platform.openai.com/api-keys
Then run:  bristlenose configure chatgpt
```

### S2 — Configure the first key, then run (just works, no flag)
```
$ bristlenose configure chatgpt
Enter your ChatGPT API key: ****************
Validating... ✓ Valid
✓ Stored in Keychain as "Bristlenose ChatGPT API Key"
You can now run: bristlenose run interviews

$ bristlenose interviews/
Bristlenose v0.16.0 · ChatGPT · Apple M2 · 32 GB
✓ Ingest …                 (ChatGPT is the only configured provider — used automatically)
```

### S3 — Add a second key (no auto-switch)  ·  **derive-only (recommended v1)**
```
$ bristlenose configure claude
Enter your Claude API key: ****************
Validating... ✓ Valid
✓ Stored in Keychain as "Bristlenose Claude API Key"
Note: you now have 2 providers (ChatGPT, Claude). Bristlenose won't guess —
pick one per run with --llm claude, or set BRISTLENOSE_LLM_PROVIDER=claude.

$ bristlenose interviews/
Error: 2 AI providers are configured (ChatGPT, Claude) but none is selected.
  Choose one:   bristlenose run interviews --llm chatgpt
  Or persist:   export BRISTLENOSE_LLM_PROVIDER=chatgpt    (add to ~/.zshrc or .env)
(exit 2)
```

### S3′ — Same step under **persist-first (Variant B)** — for comparison
```
$ bristlenose configure claude
… ✓ Stored.
(The first provider you configured — ChatGPT — remains active. Switch with
 `bristlenose use claude`.)

$ bristlenose interviews/
Bristlenose v0.16.0 · ChatGPT · …       ← keeps using the first-configured provider
```

### S4 — Scripted / CI (non-TTY) with ambiguity → clean failure
```
$ bristlenose run interviews/ < /dev/null
Error: multiple AI providers configured (ChatGPT, Claude) and no selection.
  Set BRISTLENOSE_LLM_PROVIDER or pass --llm. (exit 2)
```

### S5 — Editor: persist a default without touching secrets
```toml
# bristlenose.toml  (or .env: BRISTLENOSE_LLM_PROVIDER=chatgpt)
[llm]
provider = "chatgpt"        # preference — plaintext, committable
# key stays in the Keychain; never written here
```
```
$ bristlenose interviews/
Bristlenose v0.16.0 · ChatGPT · …       ← bare run now uses the persisted preference
```

### S6 — Selected provider missing its key
```
$ BRISTLENOSE_LLM_PROVIDER=gemini bristlenose interviews/
Error: provider "Gemini" selected but no Gemini key found.
  Run: bristlenose configure gemini   (exit 2)
```

---

## 7. Implementation plan

**Python — `bristlenose/credentials.py`**
- Add `configured_cloud_providers() -> list[str]`: iterate the cloud entries in
  `PROVIDERS` (anthropic/openai/azure/google), return those with a non-empty key
  via `get_credential`. (Azure counts as configured on key presence; endpoint/
  deployment validated later in preflight.)

**Python — `bristlenose/config.py` (`load_settings`)**
- After pydantic build + alias normalisation, insert a CLI-only resolution step
  (gated `not hosted_by_desktop()`): if `llm_provider` was *not* explicitly set
  (not in `overrides`, no `BRISTLENOSE_LLM_PROVIDER`), replace the field-default
  value using `configured_cloud_providers()`:
  - exactly 1 → that provider (record ledger `step=derive-sole-provider`)
  - 0 or 2+ → leave a sentinel/flag so the CLI layer raises the right
    diagnostic (don't raise inside `load_settings` — keep it pure/UI-free).
- Keep the `llm_provider` field default `"anthropic"` (desktop backstop). Keep
  `_fill_provider_default_model` and `_guard_orphan_desktop_model` exactly as-is.

**Python — `bristlenose/cli.py`**
- Replace `_needs_provider_prompt` (`:381`) with a richer
  `_resolve_or_prompt_provider(settings)` that consumes the derive result:
  0 keys → menu (TTY) / exit 2 (non-TTY); 2+ unselected → diagnostic (TTY) /
  exit 2 (non-TTY); 1 or explicit → pass through.
- Wire it where `_maybe_prompt_for_provider` is called (`:1116` run, `:1395`
  analyze). Add TTY guards.
- `configure` (`:1892`): after a successful store, compute
  `configured_cloud_providers()`; if count ≥ 2 print the one-line "pick one" hint.

**Docs**
- Man page `bristlenose/data/bristlenose.1`: rewrite the `BRISTLENOSE_LLM_MODEL`
  line ("selected provider's recommended model"); add a "Choosing a provider"
  paragraph describing the ladder.
- README "Getting an API key": replace "Option A (Claude) is the default" with
  the derive/diagnose explanation + how to persist via `BRISTLENOSE_LLM_PROVIDER`.
- `.env.example`: annotate the precedence.

---

## 8. Desktop interplay — toes NOT to tread on

The desktop selects provider+model in Swift and injects them as env vars; the
Python resolution must stay backward-compatible with that contract.

1. **`tests/test_swift_python_contract.py`** asserts the Swift constant
   `BristlenoseShared.pythonDefaultProvider` equals Python's `config.py` default
   provider. **→ Keep the `llm_provider` field default `"anthropic"`.** Removing
   it breaks the contract and the desktop's no-active-provider backstop.
2. **`BristlenoseShared.overlayPreferences` / `resolvedProviderModel`**
   (`BristlenoseShared.swift:170-201`): when `activeProvider` is **unset**, the
   desktop injects **no `BRISTLENOSE_LLM_PROVIDER`** and scopes the API-key
   overlay to `pythonDefaultProvider`. So a defaulted desktop run reaches Python
   with *exactly one* injected key and no provider env var. Under the new derive
   logic this resolves to that one provider — same outcome — **but only because
   the new step is gated `not hosted_by_desktop()`; under hosting we must NOT run
   derive/diagnose and must fall through to the field default.** Verified by
   `ServeManagerEnvTests.swift:65` (no_active_provider_falls_back_to_python_default_key).
3. **`_fill_provider_default_model` / `_guard_orphan_desktop_model`** are already
   `hosted_by_desktop()`-partitioned. Leave both untouched; mirror the same gate
   for the new provider-derive step.
4. **`tests/test_desktop_config_resolution.py::TestRunCommandDefaultDoesNotOverrideEnv`**
   pins `--llm` default `None`. Unchanged here.
5. **No Swift changes required.** The desktop's "first validated key becomes
   active" already lives in `ConsentActivation.resolve`; this plan does not touch
   it. CLI and desktop deliberately use *different* mechanisms for the same
   intent (derive-on-CLI vs persisted-activeProvider-on-desktop) — documented,
   not unified.

**Net:** every new behaviour is behind `not hosted_by_desktop()`. The field
default + Swift contract is the seam; we keep both green.

---

## 9. Testing plan

- `configured_cloud_providers`: unit tests over a fake credential store (0/1/2/3
  keys, azure-key-only).
- `load_settings` derive step: 1 key → that provider; 0/2+ → sentinel; explicit
  `--llm`/env always wins; **`hosted_by_desktop()` → derive is a no-op** (pins
  toe #2).
- CLI: TTY vs non-TTY matrix for 0-key and 2-key cases (exit codes + no-hang).
  Reuse the subprocess pattern from `tests/test_run_lifecycle.py` (poll, don't
  block) for the non-TTY exit-2 cases.
- `configure` 2nd-key hint present/absent at the 1→2 boundary.
- Keep `test_swift_python_contract.py` green (proves toe #1).
- Man-page lint (`mandoc -Tlint`).

---

## 10. Open decisions (for review)

1. **Derive-only (v1) vs persist-first (Variant B).** Derive-only = no stored
   state, but a 2nd key forces an explicit pick on the next run (S3). Persist-
   first = first-configured provider stays active (S3′), needs a plaintext
   `active_provider` in `~/.config/bristlenose/config.toml` + a `bristlenose use`
   verb + drift validation. **Lean: derive-only.**
2. **`llm_model` field default `""` vs keep `"claude-sonnet-4"`.** Empty is
   cleaner (no vendor hardcode) but wider blast radius. **Lean: keep for v1,
   fix docs only.**
3. **Interactive "make this active?" offer in `configure`** when adding a 2nd
   key on a TTY. Convenience, but only meaningful under persist-first. **Defer.**
4. **Should the 0-key non-TTY case exit 2 or fall through** to a clearer
   first-stage preflight failure? **Lean: exit 2 early with the configure hint.**
