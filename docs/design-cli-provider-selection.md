# CLI Provider Selection — the current-provider model

**Status: IMPLEMENTED — 31 Jul 2026.** Originally drafted 10 Jun 2026 as a
derive-only proposal; revised at implementation to the **current-provider**
model after review (the .app already works this way: the provider stays
whatever you last set, and nothing asks mid-run). This doc describes what
shipped and why. _Trued 4 Sep 2026: the §4 transcripts show the real Keychain
item names, the read-back failure branch is recorded, and §6 gains the
two-keychain sharing._

Desktop selection is unchanged (the Swift host injects provider+model
explicitly); see §6 for the toes this deliberately does not tread on.

---

## 1. Principles

1. **A key is a secret; "which provider" is a preference.** Different stores,
   different verbs. Keys live in the Keychain / Secret Service / protected
   file; the provider preference is a plaintext line in the user-level config.
2. **No vendor default in the CLI happy path.** The `llm_provider` field
   default (`"anthropic"`, `config.py`) survives *only* as the desktop-contract
   backstop — a CLI run never reaches it. A fresh install with no keys
   diagnoses; it does not silently try Claude. (The old behaviour dated from
   February, when Claude was the only provider built.)
3. **Configuring a provider is choosing it.** `bristlenose configure gemini`
   validates + stores the key **and makes Gemini current, loudly** — the
   printed line names the switch and the way back. Nobody pastes a Gemini key
   expecting to keep running Claude; when they do want that, `use` is one
   command. (The June draft's "adding a key must never change the provider"
   survives on the word *silently*: the switch happens in the same breath as
   the user's own action, announced, reversible.)
4. **`run`/`analyze` never prompt. Full stop.** The only interactive step in
   the entire CLI is the key paste inside `configure`. Scripted, CI, agent-
   driven, and walked-away-for-tea runs all behave identically: resolve or
   exit 2 with the exact command to run.
5. **Sole key just works — by derivation, not stored state.** One configured
   cloud key with no recorded choice → that provider, whoever's it is. Claude
   wins by the same rule as everyone else, never by favouritism.
6. **Ambiguity is never resolved by a vendor default.** Two-plus keys and no
   choice → name the providers and the two ways to choose; exit 2.

## 2. The ladder

Resolved on every `load_settings()` (first match wins):

| # | Source | Mechanism |
|---|--------|-----------|
| 1 | `--llm <provider>` | cli-override into `load_settings(**overrides)` |
| 2 | `BRISTLENOSE_LLM_PROVIDER` env var | pydantic-settings env |
| 3 | project-local `.env` | pydantic-settings env_file (later file wins) |
| 4 | **current provider** — `BRISTLENOSE_LLM_PROVIDER=` in the user-level config `.env` (`~/.config/bristlenose/.env`), written by `configure` / `use` | same env_file list, lowest priority |
| 5 | sole configured cloud key (derived, no stored state) | `_derive_provider` |
| 6 | 0 keys → status `none`; 2+ keys → status `ambiguous` | CLI exits before running |

`local` (Ollama) is **never derived** — it is used only when explicitly chosen
(`--llm local`, env, `use local`, `configure local`), because "no cloud key"
must surface the choice between *get a key* and *go local*.

**Storage.** The current provider is a plain `BRISTLENOSE_LLM_PROVIDER=` line
upserted into the same user-level `.env` that `configure` already uses as its
no-keyring key fallback (`bristlenose/credentials.py`:
`read_user_config_var` / `write_user_config_var`, mode `0o600`).
pydantic-settings already loads that file lowest-priority via
`config._find_env_files()`, so rungs 2–4 are one mechanism, not three code
paths — and the desktop carve-out (hosted processes read no `.env` files at
all) means the CLI preference can never leak into a desktop-hosted run.

## 3. Implementation map

- **`config.py`** — `configured_cloud_providers(settings)` (string-typed,
  non-empty keys only; Azure counts on key presence, endpoint validated by
  preflight); `ProviderResolution` (status `hosted | explicit | derived |
  none | ambiguous`); `_derive_provider(...)` runs inside `load_settings`
  *after* `_populate_keys_from_keychain` (derivation needs the full key
  picture) and *before* `_fill_provider_default_model` (so a derived provider
  gets its coherent default model); result recorded in the `llm_resolve`
  ledger (`step=2b-derive`) and exposed via `get_provider_resolution()`.
  `provider_resolution_for(settings)` is the stateless recompute for
  long-lived processes.
- **`cli.py`** — `_maybe_guide_provider_setup` (called by `run`/`analyze`
  after `load_settings`): `none` → setup guidance (TTY, exit 0) or terse
  error (non-TTY, exit 2); `ambiguous` → exit 2 naming the providers +
  `bristlenose use …` / `--llm`; `explicit` with a missing key → exit 2
  naming the exact gap ("Gemini is selected but no Gemini key is
  configured"), replacing the old misleading "No LLM provider configured";
  `derived`/`hosted` → pass. `bristlenose use <provider>` — validates a key
  exists (cloud), writes the preference, confirms; warns when a real env var
  masks the choice. `configure` calls `_set_current_provider` on success
  (cloud and local; never for `miro`).
- **`server/routes/autocode.py`** — a server can't prompt: the start-job
  route recomputes `provider_resolution_for(settings)` and returns 409 on
  `ambiguous` instead of letting the field default silently pick a vendor.
  (Chat lens / codebook builder inherit whatever the serve process resolved;
  tightening them is deferred to the per-stage backend work.)
- **`doctor_fixes.py`** — the no-keys suggestion offers all four providers
  (`bristlenose configure <claude|chatgpt|gemini|azure>`), naming no
  favourite.

## 4. The sequences (as shipped)

Fresh machine, zero keys — guidance, no menu, no prices, exit:

```
$ bristlenose interviews

No LLM provider configured.

Set one up once — bristlenose configure <provider> validates your
key and stores it securely (Keychain):

  Claude    https://console.anthropic.com/settings/keys
  ChatGPT   https://platform.openai.com/api-keys
  Gemini    https://aistudio.google.com/apikey
  Azure     https://portal.azure.com

For local models via Ollama:  bristlenose configure local
```

First key — configure = choose; bare runs work forever after:

```
$ bristlenose configure chatgpt
Enter your ChatGPT API key: ················
✓ Valid
✓ Stored in Keychain as "Bristlenose OpenAI API Key"
ChatGPT is now your provider for analysis.
You can now run: bristlenose run interviews
```

Second key — switches loudly, names the way back:

```
$ bristlenose configure claude
✓ Valid
✓ Stored in Keychain as "Bristlenose Anthropic API Key"
Claude is now your provider for analysis (was ChatGPT).
Switch back any time:  bristlenose use chatgpt
You can now run: bristlenose run interviews
```

_The two transcripts above printed "Bristlenose ChatGPT API Key" and "Bristlenose
Claude API Key" until 4 Sep 2026 — faithful transcripts of a CLI line that named the
item after the product rather than the stored service. The names shown now are what
Keychain Access lists (`providers.py` `CREDENTIALS`)._

When the key does not read back — a refused write, or an environment variable
shadowing the stored key — `configure` refuses to claim it, exits 1, and the
provider is **not** made current (`credentials.set_verified`, 4 Sep 2026):

```
$ bristlenose configure claude
✓ Valid
✗ Not saved — the key did not read back from Keychain.
Either the write was refused, or an environment variable (BRISTLENOSE_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY) is shadowing the stored key.
```

Switching without re-pasting a key:

```
$ bristlenose use chatgpt
ChatGPT is now your provider for analysis (was Claude).
Switch back any time:  bristlenose use claude
```

Explicit choice missing its key — the precise error:

```
$ bristlenose run interviews --llm gemini
✗ Gemini is selected but no Gemini key is configured.
  Run:  bristlenose configure gemini
(exit 2)
```

Migration edge — 2+ keys already present but no recorded choice (configured
under a pre-`use` version, or keys arriving via `.env`/env only). One-time,
TTY or not:

```
$ bristlenose run interviews
✗ 2 AI providers are configured (Claude, ChatGPT) and none is selected.
  Pick one to stay current:  bristlenose use claude|chatgpt
  Or just for this run:      --llm claude
(exit 2)
```

This is the only hard stop the model retains, and the population it hits is
precisely the old silent-Claude beneficiaries — who now make one explicit
choice.

## 5. Model selection

Unchanged mechanism: `_fill_provider_default_model` snaps a never-chosen
model to the *resolved* provider's `default_model`, which now composes with
derivation (sole Gemini key → `gemini-2.5-flash` with no flags anywhere).
Docs no longer state a fixed Claude model string as "the default" — the
documented behaviour is "the selected provider's recommended model". The flat
`llm_model` field default remains until the per-stage matrix drives
execution (see `docs/design-stage-backends.md`).

## 6. Desktop interplay — toes NOT trodden on

1. `tests/test_swift_python_contract.py` pins the Swift constant
   `BristlenoseShared.pythonDefaultProvider == "anthropic"` against the
   `config.py` field default. **Kept.** Derivation is gated
   `not hosted_by_desktop()`; under hosting the resolution status is
   `hosted` and the field default remains the no-active-provider backstop
   (`ServeManagerEnvTests.swift`).
2. `_find_env_files()` returns `[]` under hosting (the consent-integrity
   carve-out), so the CLI's stored current provider is invisible to
   desktop-hosted processes by construction.
3. `_fill_provider_default_model` / `_guard_orphan_desktop_model` untouched.
4. The desktop's own "first validated key becomes active"
   (`ConsentActivation.resolve`) and Settings picker are unchanged. CLI and
   desktop now share the same *semantics* (provider stays as last set;
   switching is explicit) through different mechanisms — deliberate.
   Remaining desktop-side language ("Claude is the recommended default" in
   `WelcomeHomeView.swift`; the Settings picker preselecting Claude before
   first activation) is queued for the desktop UX pass.
5. **The keys themselves are shared, not just the semantics (4 Sep 2026).**
   The app keeps a login-keychain copy of every CLI-read key
   (`KeychainHelper.sharedWithCLI`, pinned by
   `tests/test_swift_python_contract.py`) and adopts what `configure` writes
   when Settings ▸ LLM Provider is opened, so a key set up in either place is
   seen by both — `docs/design-keychain.md` §"One keyspace, two keychains".
   The *current-provider* choice stays per channel: item 2 keeps the CLI's
   `BRISTLENOSE_LLM_PROVIDER` invisible to the app.

## 7. Testing

`tests/test_provider_resolution.py` — the ladder matrix (sole-key derive per
provider incl. anthropic-by-same-rule, zero/two-key statuses, cli-override /
env / dotenv explicitness, local-never-derived, hosted no-op, stateless
recompute incl. MagicMock tolerance), the user-config store (round-trip,
upsert, 0600), `use` (persist canonical name, missing-key teach, unknown
provider, env-var masking warning), `configure`-sets-current (first key,
second key names the previous). `tests/test_provider_horror_scenarios.py` —
the user-visible gate flows (guidance TTY/non-TTY, ambiguous teach-`use`,
precise missing-key error, hosted/derived pass-through, never-prompts).
Ledger coverage in `tests/test_desktop_config_resolution.py` unchanged.
