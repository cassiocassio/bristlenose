---
status: partial
last-trued: 2026-10-23
---

# any-llm: one way in to the other providers

> **Status: v1 built (23 Oct 2026), not yet released.** The CLI, the server's
> three key checks and the web edits are on `main`; Homebrew carries the extra
> from the release that ships it. v1 is the CLI (with Homebrew). v2 (the Mac app) is sketched so v1
> doesn't paint it into a corner, and is not scheduled before the 24 Nov App
> Store submission. Review findings: the maintainer's private review log for
> this doc. CLI sessions: [mockups/any-llm-cli-session.html](mockups/any-llm-cli-session.html).

## Changelog

- _2026-10-23_ — thinking switched off (§5.3d), after the OpenRouter walk:
  Qwen 3.8 Flash, Nemotron and DeepSeek V4 Flash thought by default, every s09
  pass on Qwen and Nemotron ran past its 570 s deadline, and the halves were
  nearly as slow. Every call now sends `reasoning_effort="none"`; a model that
  always thinks refuses it and is asked again with its own default, as a
  refused `json_schema` is. A pass that outruns the deadline through any-llm is
  no longer called a network failure, and an unexplained give-up names the
  model and `bristlenose use provider:model`.

- _2026-10-23_ — review of the build (Fable plus five reviewers), folded in:
  the preflight falls back to `json_object` as the run does (DeepSeek could
  never start); a rejected stored key is asked for again and a rejected
  environment key is named, never a loop; a key given to `configure` is the one
  checked, and a variable that will shadow it is named; readiness never raises
  (Vertex-style construction errors become `broken`); the destination line and
  the preflight cache follow `*_API_BASE` overrides, with a warning for plain
  HTTP off the machine; our own retry on 429/5xx honouring `Retry-After`;
  Mistral's `model_length` reaches split-and-retry; a key pasted as the model is
  caught before it is echoed or stored; install hints keep the extras already
  installed and pin injected SDKs; `doctor`'s any-llm row shows only where it is
  installed or chosen; a contract test against the real library (skipped where
  it isn't installed). Still open: the free CI job that installs the extra.

- _2026-10-23_ — built v1, and trued the plan to it: default set Mistral and
  OpenRouter (owner; DeepSeek reachable directly at no cost, since it rides on
  the OpenAI SDK; Groq and Grok through OpenRouter, the name confusion being a
  cost of its own); `use provider:model` switches between stored models; no
  Python 3.10 structural reason (the install fails loudly instead); the Groq
  413 reading dropped with Groq; the live check gains an opt-in `--anyllm`.

- _2026-10-23_ — revised after Fable's review: build on an exact pin of
  1.27.0 now, with #1370 as a parallel gesture, not a gate; the run preflight
  covers `anyllm`; no unknown-finish-reason guard (it can't be written on
  1.27); SDK default retries; a provider-agnostic 402 rule; host from the
  provider class; one key-spec helper; gated model copy; cuts listed in §12.
- _2026-10-23_ — revised after a seven-reviewer pass and a survey of other
  any-llm integrations. Changed: structured output goes as a JSON-schema dict
  and we parse; typed errors are switched on and classified on the inner
  provider; one offline readiness probe; the model is copied into `llm_model`
  (fixing Azure's same bug); `temperature` and `max_tokens` not sent; keys
  stored per inner provider; a version window, not a floor; disclosure
  surfaces; ~5 locale keys, not 1; Homebrew carries it; the default inner
  set. New: §3's version decision, which puts the upstream Anthropic 1.x
  migration on the critical path for a good v1.
- _2026-10-23_ — first draft.

## 1. What and why

[mozilla-ai/any-llm](https://github.com/mozilla-ai/any-llm) (`any-llm-sdk`,
Apache-2.0) is one async call over the official SDKs of about fifty-five
providers. Supporting it gives a Bristlenose user Mistral, Groq, OpenRouter,
DeepSeek and the rest through one door.

**It is a community play, not provider strategy.** Nearly every researcher
uses the key of a provider they already pay, or picks the logo they've heard
of. The five native providers (Claude, ChatGPT, Gemini, Azure OpenAI, Ollama)
stay exactly as they are, on their own code paths. any-llm is for the long
tail and for the people who build it, and it is credited where they'll see it.

This supersedes the "not adopted" verdict in
[design-pluggable-llm-routing.md](design-pluggable-llm-routing.md) §"Prior art".
Neither of that section's reopen triggers fired (the §1 resolver; a provider
beyond five, parked until after launch): the owner overrode it on 23 Oct 2026,
for the community reason above, inside the reliability phase.

**Owner-approved exception (23 Oct 2026).** The README's any-llm section and
the website's CLI page may say "Coming to the Mac app." It is the one named
exception to the no-promises rule for user-facing docs: no date, no version,
nowhere else.

## 2. Minimum new surfaces

| New | Kind | Why it can't reuse something |
|---|---|---|
| Provider `anyllm` in `PROVIDERS` (aliases `any-llm`, `any_llm`) | registry row | It's a provider. Canonical ids are hyphen-free because preflight derives names from them |
| `anyllm_model` setting (`BRISTLENOSE_ANYLLM_MODEL`) | settings field | Azure's precedent (`azure_deployment`): a provider with no default model gets its own field |
| `bristlenose[any-llm]` extra | packaging | `mcp`/`voice` precedent |
| `_analyze_anyllm` in `llm/client.py` | call path | One per provider |
| `any_llm_ready(settings)` | one helper | The single readiness probe (§5.3), shared by configure, doctor, the server and the client |
| ~5 locale keys × 21 | pipeline reasons/actions | The Azure sibling's shape: not installed, no model, no key (§7) |
| doctor row `any-llm` + fix keys | doctor (English) | `ollama_*` precedent |

**No new** CLI command, CLI flag, message kind, failure kind, cause category,
SPA component or export field. **One small web edit**: the config-reference
grid in `SettingsModal.tsx` (data, one key).

## 3. Versions — the one decision that shapes v1

**Facts (measured 23 Oct 2026):**

- any-llm makes `anthropic` and `openai` **core** dependencies. From **1.27.1**
  (4 Sep) it caps `anthropic<1`; we require `anthropic>=1.0`. So with our
  constraints pip resolves **1.27.0**, the last uncapped release, whatever
  extras we ask for. It imports and works next to our SDKs (tested end to end
  on Ollama).
- 1.27.0 lacks fixes we want: per-instance `unified_exceptions` (1.29), Mistral
  response-validation errors misread as caller errors (1.37, #1491), and
  finish reasons outside OpenAI's five raising `ValidationError` and losing the
  response on OpenRouter (1.38, #1471). Its Anthropic route is probably broken
  against our SDK; we never use it (§5.2 refuses native prefixes).
- any-llm ships about three releases a week and has shipped breaking changes
  as minors (1.9, 1.16). Integrators split between exact pins and `<2`; the
  LiteLLM supply-chain incident of 24 Mar 2026 is why careful ones pin.
- The cap lifts when upstream's Anthropic 1.x migration lands
  ([#1370](https://github.com/mozilla-ai/any-llm/issues/1370), open,
  unassigned, with a written plan).

**Decision proposed (Fable's review): build now on an exact pin,
`any-llm-sdk[mistral,groq]==1.27.0`, and decouple from #1370.** 1.27.0 is
viable: its Anthropic SDK import is confined to the Anthropic provider we never
use, and typed errors are one in-process environment switch that 1.40 still
honours. The code is written to the 1.40 shape (the switch, our own
`finish_reason` check, no `max_retries` argument), so moving up is a pin change,
made on the normal dependency cadence and proved with
`scripts/check-providers-live.py`. An exact pin, not a window: a window grammar
would need widening every few days against three releases a week.

Helping land #1370 stays the community gesture, in parallel. It needs the
owner's go (it publishes under the owner's name), and making it a gate would
put the release in someone else's review queue during the reliability phase.

**Known exposure on 1.27.0, stated rather than guarded.** A finish reason
outside OpenAI's five (Mistral's `model_length`/`error`, OpenRouter's `error`,
DeepSeek's `insufficient_system_resource`) fails pydantic validation inside
any-llm before we see the response, and no guard can be written around it. A
raw `pydantic.ValidationError` escaping any-llm is mapped to "the provider
returned something any-llm couldn't read", never a pydantic dump. Fixed
upstream in 1.38; it goes when the pin moves.

## 4. Sibling map (is this Bristlenosey?)

Kind: a sixth LLM provider with a free-form model string. Siblings:
**`local`** for selection (never derived, explicit only) and **`azure`** for
the model (no default, its own field, no pricing, a synthesised pipeline row).

| Part | Proposal | Sibling | Verdict |
|---|---|---|---|
| Selection | Explicit only: `--llm any-llm`, `use`, `configure`, `BRISTLENOSE_LLM_PROVIDER` (aliases normalised from env and `.env` too) | `local`: «never derived — used only when explicitly chosen» | follows |
| Model | `anyllm_model`, must be set. For `anyllm` it wins over `BRISTLENOSE_LLM_MODEL`, and `load_settings` copies it into `llm_model` so cost lines, logs, the manifest and AutoCode see the real model. The copy carries the sibling's gates: the value gate (only when `llm_model` is still the code default) and no change when hosted by the desktop | `azure_deployment` (same leak today: `BRISTLENOSE_LLM_PROVIDER=azure` leaves `llm_model=claude-sonnet-4-6` and prints a Claude price); `_fill_provider_default_model` (the gates) | follows. Azure's fix is its own small change, CLI only, so desktop Azure runs don't move in the reliability phase |
| `configure any-llm` | No `--model` flag; asks for the model, probes readiness, uses the shell key or asks for one and stores it, validates free where it can, makes it current | `configure local` (uniform verb) + `configure claude` (validate, store, read back) | follows |
| Keys | Shell variable first, then the platform store (Keychain / Secret Service / file), one entry per inner provider, named "Bristlenose Mistral API Key (any-llm)"; passed as `api_key=` | The four cloud providers' order: env → `.env` → store | follows |
| Call path | `AnyLLM.create(provider, api_key=…)` once per client, reused; `acompletion(response_format=<json_schema dict>)`; we check `finish_reason`, refusal and empty content, then `_validate_repairing` | `_ensure_*_client` (one client), `_validate_repairing` («ONLY FOR PROVIDERS THAT MAKE NO SHAPE GUARANTEE») | follows. A Pydantic type would make any-llm parse, raising on truncation and bad JSON and discarding the content and usage |
| Sampling | Neither `temperature` nor `max_tokens` sent unless the user set them (detected by the same value gate: still the field default means unset); gated in `request_params`, which the preflight shares. Truncation reports the cap actually sent and names `BRISTLENOSE_LLM_MAX_TOKENS` | `request_params` («Gate a parameter there, never at a call site») | departs (why: our 64000/0.1 are rejected by small-output and reasoning models; a per-model table is a new picker the interim rule forbids) |
| Retries | The inner SDK's defaults (2) on 1.27, whose `create` can't pass `max_retries` to every SDK (`Mistral(...)` rejects it). On 1.40, pass `max_retries` and catch `UnsupportedParameterError` | `_CLOUD_MAX_RETRIES=6` set on each native SDK client | departs (why: 1.27 has no uniform way to set it) |
| Errors | Typed errors on. Classify `original_exception` first, the any-llm class second, the generic status rules last. One new provider-agnostic rule: **402 → OUT_OF_CREDIT** (OpenRouter and DeepSeek use it; the classifier had none) | `classify_exception`; «Never classify billing on the HTTP status alone» (402 *is* the billing status) | follows |
| Copy | Name the inner provider ("Mistral rejected the API key"); no `billing_hints` entry, so out-of-credit falls through to the provider's own words | Product names, never the library's, for an account | follows |
| Telemetry | `cohort_normalise` knows `anyllm`, model kept opaque; no cost computed for `anyllm` rows | azure | follows. Without it every row is lost silently |
| Pricing | None. No pre-run estimate, no cost in the summary, tokens still shown | azure (once fixed) | follows |
| Server | The three existing `_has_api_key` sites each call `any_llm_ready` for `anyllm`; they are not restructured | — | follows (smallest change that stops AutoCode refusing and elaboration skipping silently) |
| Pipeline view | A backend "any-llm", requirements in the Azure shape (package / model / key), model synthesised from settings, `? untested` | azure + `python_package` | follows |
| doctor | `any-llm` row: the version and the inner providers this install carries. The API key row keeps today's shape (`Mistral (…ab1) (environment)`). No version-window warnings: the pin and the pipx advice are the fix | `check_local_provider` | follows |
| Install hint | Per channel; a missing inner SDK names `pipx inject bristlenose "any-llm-sdk[cohere]"` and the like | `voice_install_hint` | follows (one shared channel helper) |
| Credit | The row names, doctor, README, man page, `ACKNOWLEDGEMENTS.md` § AI Providers | `ACKNOWLEDGEMENTS.md` | follows; no credit field invented |

**Verdict: Bristlenosey**, with two named departures (sampling not sent, the
server helper) and one sibling fix (Azure's model leak).

## 5. v1: the CLI

### 5.1 The user's path

The [CLI mockup](mockups/any-llm-cli-session.html) draws every command,
flag and response. In short:

```bash
pipx install "bristlenose[any-llm]"      # Homebrew carries it already
bristlenose configure any-llm            # asks: model, as provider:model
bristlenose run interviews/
```

### 5.2 `configure any-llm`, in order

1. Not installed → the install hint for this channel, exit 1.
2. Model: from `BRISTLENOSE_ANYLLM_MODEL`, else a prompt
   (`Model: provider:model`).
3. Readiness probe (§5.3). Malformed → the form; unknown provider → "did you
   mean"; one of the five built-in providers → "Claude is built in. Use:
   bristlenose configure claude"; inner SDK missing → the inject command.
   Exit 1, nothing stored, the string never echoed whole.
4. Key: the shell variable if set ("Using MISTRAL_API_KEY from your
   environment"); else `--key`, else a hidden prompt.
5. Validate with the run preflight's own inert request (§5.3a): a fraction of
   a cent, the same request shape the run sends, so a green check means the
   run will start. A model list is not used: OpenRouter's is public, so a
   wrong key would pass. "Couldn't reach" only for connection and timeout
   errors; anything else is reported, not stored.
6. Store (when the key didn't come from the shell) with `set_verified`, read
   back, and say where: `Stored in Keychain as "Bristlenose Groq API Key
   (any-llm)"`.
7. Name the destination host, and for gateways (OpenRouter and the like) that
   it passes transcripts on.
8. Write `BRISTLENOSE_ANYLLM_MODEL` to the user config, then
   `_set_current_provider("anyllm")`, word for word as today.

`use any-llm` takes the Ollama-style branch. `use mistral:mistral-large-latest`
switches to a model whose key is already stored or exported: no network, nothing
asked, like `use claude`; a missing key changes nothing and names the fix.
`run --llm any-llm` with no model refuses (exit 2) and never prompts.

### 5.3 The readiness probe

One offline function, no network: `split_model_provider` (form and provider),
refusal of the five native prefixes, `AnyLLM.create(provider, api_key=…)`
catching `ImportError` (inner SDK missing; `ModuleNotFoundError.name` tells
"not installed" from a broken install, whose error is shown verbatim) and
`MissingApiKeyError` (whose `env_var_name` is the only source of a variable
name we print). It returns a small result: ready, or which of
{not installed, no model, bad model, native prefix, SDK missing, no key}.
`ENV_API_KEY_NAME` is never read directly: it is `"None"` for Ollama, empty
for Vertex and a sentence for SageMaker.

### 5.3a The run preflight

`preflight/api_key.py` returns early for providers it doesn't know, so today
`configure` could go green and the run die at stage 8 (the R104 class). v1
adds `_validate_anyllm`: one inert request built by the same code path as
`_analyze_anyllm`, used by both `configure` and `run`.

### 5.3b Structured-output request

Every inner provider gets the JSON schema in the system prompt as well as in
`response_format` (the OpenAI path does the same), since `_validate_repairing`
can't repair a 400. If a provider rejects `json_schema` (DeepSeek may accept
only `json_object`), fall back to `json_object` plus the prompt, as
`_analyze_local` does.

### 5.3c Destination host and key specs

The host printed by `configure` and `run` is `urlparse(cls.API_BASE).hostname`
when the provider class carries one, else the provider's name; never a
hand-kept table (`MistralProvider` has no `API_BASE` in 1.27). Key storage goes
through one helper, `anyllm_credential(inner) -> CredentialSpec`, in
`providers.py`, giving the service name "Bristlenose Groq API Key (any-llm)";
`configure` and `_analyze_anyllm` both use it, and the static `CREDENTIALS`
table (mirrored in Swift) is untouched.

### 5.3d Thinking

Every call sends `reasoning_effort="none"`, any-llm's own word for "answer
without thinking first", which it maps per provider: OpenRouter forwards it and
reads it as thinking off; DeepSeek, Mistral and Claude already default to it
(Mistral turns any other level into `"high"`, so "low" would switch thinking
*on* there). This is how the built-in route asks Claude, and our prompts were
tuned on a model that doesn't think first.

Measured 23 Oct 2026 on OpenRouter, one short extraction prompt, default vs
`"none"`: Qwen 3.8 Flash 41.6 s / 1,839 output tokens → 2.1 s / 91; DeepSeek V4
Flash 891 → 107; Grok 4.3 858 → 70; Nemotron 3.5 746 → 87; Sonnet 4.6, Llama
3.3 70B and GPT-5.4 mini unchanged. `"low"` barely helped Qwen (1,553). On the
whole FOSSDA run Qwen's s09 halves had written 20–37k tokens each from ~5k in,
and every full pass was cancelled at the deadline; the provider still bills the
tokens a cancelled call generated, and no row records them.

A model that always thinks refuses `"none"` with a 400 ("Reasoning is mandatory
for this endpoint and cannot be disabled": Gemini 2.5 Pro, GPT-5 mini). The
call is sent again without it and the client remembers, as with a refused
`json_schema`; the preflight does the same, or `configure` would turn away a
model that runs. No setting: if a researcher needs thinking on, that is a
question for the owner, not a flag.

Two consequences in the failure path. A pass still writing at s09's deadline
through any-llm is categorised `unknown`, not `network` (the provider
answered; "check your connection" was wrong); the built-in providers keep
`network`. And an abandoned run whose cause is `unknown` names the model that
ran and `bristlenose use provider:model` beneath the banner, because the
abandonment message ("All quote extraction calls failed.") overwrites the
per-session cause. No new failure category: that is a five-site change across
the Swift mirrors and 21 locales, and any-llm is not on the Mac in v1.

### 5.4 Rich

Every line that prints a model string or an install command turns Rich's
highlighter off and escapes brackets: the highlighter reads
`anthropic:claude` as an IPv6 address, and `[any-llm]` as a style tag.

### 5.5 Files

Core: `providers.py`, `config.py` (field, alias normalisation, model copy),
`preflight/api_key.py`,
`cli.py`, `doctor.py`, `doctor_fixes.py`, `pipeline.py`, `credentials*.py`
only if a derived service name needs registering. LLM: `client.py`,
`failure_classifier.py`, `pricing.py`, `cohort_normalise.py`, `telemetry.py`,
`llm/CLAUDE.md` (and true its stale "Azure cost returns None" line). Pipeline
view: `catalogue.py`, `host.py`, `render.py`, `cli.py`. Server: the helper and
its three callers, `run_inspector.py`. Web: `SettingsModal.tsx`
`CONFIG_DATA`. Locales: ~5 keys × 21. Packaging: `pyproject.toml`, the
Homebrew formula (`bristlenose[voice,any-llm]`, at release, in the tap repo).
Docs: README, man page, `ACKNOWLEDGEMENTS.md`, `SECURITY.md`,
`design-cli-provider-selection.md`, the routing doc's prior-art section,
`docs/glossary.md` (the name's forbidden forms: AnyLLM, Any-LLM, any_llm,
anyllm in prose). Website (separate repo, drafted for the owner): `cli.md`, the
two privacy pages, terms.

### 5.6 Packaging policy

| Channel | v1 | Why |
|---|---|---|
| pip / pipx / uv | `[any-llm]` extra | The user adds it. Docs recommend pipx or uv, so Bristlenose's any-llm never shares an environment with the user's own |
| Homebrew | carried | Owner, 23 Oct. Mac CLI users are the likeliest audience; the formula's `post_install` already pip-installs us |
| Snap, Fedora Copr | not carried | Snap's confinement leaves only the file store; Copr would add wheels to track for CVEs. Revisit on request |
| Mac app bundle | not carried | v2 |

Default inner set (owner, 23 Oct, revised the same day): **Mistral and
OpenRouter**. Mistral is the European provider a researcher's client is likeliest
to approve; OpenRouter reaches Grok, Llama, Qwen, DeepSeek and Groq-hosted models
with one key. The extra adds `mistralai` only: OpenRouter rides on the `openai`
SDK we ship, and so does DeepSeek, which therefore works directly at no extra
cost. Its current models are `deepseek-flash` and `deepseek-v4-pro`
(`deepseek-chat` and `deepseek-reasoner` are gone, per the DeepSeek walk on 23
Oct 2026); their documented response format is `json_object`, met by the
fallback. The 4096-token default output this plan once cited belonged to the old
model; the current ones list far larger caps, so truncation is unlikely there. Groq and Grok directly
are one `pipx inject` away. Both default providers are in upstream's "Verified" tier.
`mistralai` 3.x depends on `opentelemetry-api`, which does nothing unless an
SDK and exporter are installed; CI asserts they aren't. Never `[all]`, which
pulls the `platform` extra's telemetry client.

No-fork holds (`design-modularity.md`: differences live in «`pyproject.toml`
extras» and the «PyInstaller spec»). The Python never asks which channel it is
on.

## 6. Disclosure

`SECURITY.md` says its list of where data goes is complete. Through any-llm the
destination is the user's choice, and gateways (OpenRouter and others) forward
to further processors. So, in the same release: `SECURITY.md` gains the any-llm
case; the website's two privacy pages and terms are drafted for the owner; and
`configure` and the run header name the destination host (§5.2, mockup frames
3–7). The research-ethics rule stands: free tiers may train on inputs, so the
docs say to check the provider's terms before sending participant data.

## 7. Web

The SPA renders no provider name from a fixed map; failure copy is
provider-neutral; unpriced cost hides; exports carry no provider. So: the
pipeline row (server), the config-reference grid (`CONFIG_DATA`, one key), and
AutoCode's missing-model refusal left as it is (no v1 surface can set the
model from the browser, and neither existing refusal fits). Locale keys, all 21 locales:
`pipeline.reasons.anyllm_not_installed`, `pipeline.reasons.no_anyllm_model`,
`pipeline.reasons.no_anyllm_key`, `pipeline.actions.install_anyllm`,
`pipeline.actions.configure_anyllm`, `configReference.settings.llm.anyllmModel`.
A reverse test pins
that every catalogue reason and action key resolves in `en` and in
`_REASON_TEXT`.

## 8. v2: the Mac app (sketch, not scheduled)

The Python is v1's, unchanged; everything Mac-only is Swift. Settled by the
review:

- **Bundle.** any-llm in `SIDECAR_EXTRAS` (the `mcp` precedent),
  `collect_submodules("any_llm")` in the spec (it imports provider modules by
  name), a bundle-integrity check that imports it. The import costs about 0.6 s,
  paid lazily on first use.
- **Row.** One row below Ollama, with a section break: name **"Other
  provider"**, empty 28 pt logo slot, credit in the links slot ("any-llm").
  Detail pane: Model above API Key (the key depends on the model's prefix); a
  plain text field with an example placeholder; key placeholder "Key for
  mistral", never an environment variable name; status "Not checked" from
  presence alone, no new route, works with no project open.
- **Keys.** Inject `BRISTLENOSE_ANYLLM_API_KEY`, which `_analyze_anyllm`
  passes as `api_key=`. That keeps the env allowlist, the redactor, the tests
  and the CLI contract, and never collides with `OPENAI_API_KEY` and friends.
  The redactor also matches injected secrets by exact value. The model goes on
  `BRISTLENOSE_ANYLLM_MODEL` (a third case in `overlayPreferences`).
- **Scope.** Single-key HTTPS providers only, from an allowlist Python reports.
- **Enum.** Keep the case in `LLMProvider` (commit-on-close and quit-save walk
  `allCases`); exclude it explicitly at the two consent sites.
- **Gate.** Diagnostics-gated first, but the gate only offers the row; it
  never hides a configured one.
- **Strings.** About 7–10 keys plus consent; failure slots get the inner
  provider's name or the existing `…Generic` variants, never "Other provider".

**Open calls, the owner's:**

1. **Consent.** (a) join `AIConsentView`'s list and bump the version, re-asking
   everyone; or (b) a stock alert on first activation naming the actual
   destination, again whenever the prefix changes, logged to `consentLog`. The
   policy text says to bump on a new class of recipient, so (b) means amending
   it in the same change.
2. **Key slots.** One slot for the row (re-paste when switching providers;
   nothing invisible syncing through iCloud) or one per inner provider (as the
   CLI stores them). The CLI's per-provider entries are in the login keychain
   either way.

## 9. Test plan

Against [design-test-philosophy.md](design-test-philosophy.md). CI never makes
a paid call. Fakes raise the way the real library does.

**Silent if broken, so tested (pytest, fake `any_llm`):**

1. **Dispatch composes.** Provider and model through `load_settings` →
   `LLMClient.analyze` → the fake gets `model="mistral:x"`, a schema dict, and
   neither `temperature` nor `max_tokens`.
2. **The Claude default is never sent or shown.** Model unset → refused before
   any call; with a model set, the cost line is absent, the summary and
   `llm_request` name the any-llm model (and Azure's, for the sibling fix).
3. **Error classification, table-driven, on the shapes the four providers
   really send**: OpenRouter 402 and DeepSeek 402 "Insufficient Balance" →
   OUT_OF_CREDIT; Groq 429 → RATE_LIMITED; Groq 413 "Request too large" read as
   a size limit; Mistral `SDKError` with a string body (status only); 401 →
   INVALID_KEY; a raw `pydantic.ValidationError` from any-llm → the readable
   message. Shapes confirmed in the manual walk.
4. **Truncation.** `finish_reason="length"` → `TruncatedResponseError` with the
   cap actually sent; any-llm's own `LengthFinishReasonError` (fallback route)
   maps the same.
5. **Refusal and empty content** fail loudly, not as a schema failure.
6. **Telemetry rows survive** for `anyllm`, with no cost.
7. **The readiness probe**, one table: not installed, broken install shown
   verbatim, bad form, native prefix, SDK missing, no key (variable from the
   error), ready.
8. **The server sites**: each of the three accepts `anyllm` when ready and
   refuses when not (one parametrised test; they keep their own refusal
   shapes).
9. **Explicit only**: `MISTRAL_API_KEY` alone never derives `anyllm`; an
   `any-llm` alias in the environment resolves.
10. **Install hint** forms per channel, and the 3.10 refusal.
11. **Locale keys**: the reverse test (§7).

**Against the real library:** `scripts/check-providers-live.py --anyllm
provider:model` (repeatable; `--provider anyllm` for those alone) runs the
preflight and the real stage templates through the real `LLMClient`. Opt-in,
because any-llm ships no model of its own and each needs its provider's key.
Run before release and whenever the pin moves. Pence per run, nothing through
Ollama: on 23 Oct 2026 `--anyllm llamacpp:llama3.2:3b` with
`LLAMACPP_API_BASE=http://localhost:11434/v1` passed preflight, clusters and
themes.

**CI job (free):** installs `.[any-llm]` at the pin, imports `any_llm` and the
four providers' modules with sockets patched to fail (no import-time network),
and asserts no OpenTelemetry SDK or exporter and no `any_llm_platform_client`.

**Already covered:** the ladder's precedence, `_set_current_provider`,
`_validate_repairing`, the pipeline view's round-trip.

**Manual walk before release (about £0.05; public FOSSDA fixture only):**
Ollama through any-llm (free; structured output on a weak model); Groq free
tier; a new OpenRouter account with no credit (the out-of-credit path); about
$5 of Mistral for the headline example; a small-output model to see
truncation split and recover; `doctor`, `pipeline` and `serve`'s Settings ▸
Pipeline with and without the extra; a Homebrew install.

**v2 (Mac):** Swift units for the env dict (the any-llm key injected only for
the active row, under the Bristlenose name) and `anyLLMOffered`; the pytest
contract test extended; a sidecar smoke that imports `any_llm` from the bundle.
The UI rides the cohort.

## 10. Sequencing

| Step | Share | When |
|---|---|---|
| v1 CLI + web + Homebrew on `==1.27.0` | ~40% | Next minor (0.43.0) |
| Upstream: help land #1370 (Anthropic 1.x), then move the pin | — | In parallel; the PR needs the owner's go |
| v2 Mac | ~55% | After the 24 Nov submission |

## 11. Open questions

- **`ollama:` through any-llm.** It bypasses the local-model refusals in
  AutoCode and elaboration and the Whisper/GPU overlap guard. Refuse
  `ollama:` too (Ollama is built in), which is the simplest answer.
- **Inner provider as a field.** Classifier, copy and telemetry all derive it
  from the model prefix; one helper, `inner_provider(settings)`, keeps that to
  one rule.

## 12. Cut after Fable's review

- Restructuring the three server key checks into one helper (they call the
  probe instead).
- doctor's version-window and anthropic-floor warnings.
- AutoCode's refusal-text change.
- The `httpx.MockTransport` contract suite (replaced by the live check).
- Importing every provider module in CI (the four and `any_llm` only).
- "Upstream first" as a sequencing gate.
- Python 3.10: no environment marker. `pip install "bristlenose[any-llm]"` on
  3.10 fails loudly (any-llm needs 3.11), which beats a silent no-op extra.

