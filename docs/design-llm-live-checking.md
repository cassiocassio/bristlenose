# Live checking of LLM providers — what we learned, what's done, what isn't

_Written 5 Sep 2026, from the Aug-2026 dependency review and the live provider
testing that followed it. Every claim below was measured with real keys on
4 Sep 2026 unless it says otherwise. Companion: the pre-mortem ledger,
`dependency-premortem-log.md`, Entry 7 § "Live evidence"._

## Why this document exists

On 4 Sep 2026 the macOS Settings ▸ LLM Provider pane showed Claude, ChatGPT and
Gemini all **Online**, green, "last verified 6 seconds ago". At that moment:

- both models the Gemini picker offered returned `404 — no longer available to
  new users`;
- the Claude default that had been moved that morning returned malformed tool
  input on every realistic transcript;
- the ChatGPT default was a May-2024 model, six generations behind, and the
  parameters we sent it would have been rejected by anything newer.

None of this was visible to 4,375 passing tests, to `pip list --outdated`, to
the quarterly dependency review, or to the green lights. It was visible only to
a real call. This doc records what that afternoon taught, what was fixed, what
was deliberately left, and where the work goes next.

## What we learned

### The green light answers one question, and it is the least useful one

`design-desktop-settings.md` § "the ladder" already describes three rungs:

| rung | what it proves | what it cannot see |
|---|---|---|
| 1 | a key is present | anything |
| 2 **(shipped)** | the endpoint is reachable and the key authenticates | credit, whether the model exists, whether our request works |
| 3 (designed, not built) | a structured `analyze()` against a fixture succeeds — *"this **is** ground truth"* | — |

Rung 2 validates with a **fixed cheap model** (`LLMValidator.swift:134` uses
`claude-haiku-4-5-20251001` for Anthropic regardless of what the user selected).
So "Online" means *this key is accepted*, never *your next run will work*. The
doc was honest about this — "copy must not over-claim" — and it made no
difference to the person reading a green dot. An honest caption does not change
what green means to a human.

### Three questions, not one

The live check asks, per shipped (provider, model):

- **i. alive** — is the key accepted at all
- **ii. exists** — does the model id still resolve
- **iii. shape** — does our exact request go through and validate as
  `QuoteExtractionResult`

Each failed independently on 4 Sep, for a different provider, and only a real
call through the real client could distinguish them.

### Vendors drift in three ways, and docs record at most one

**Soft retirement.** Google returned `404 — no longer available to new users.
Please update your code to use models/gemini-3.6-flash` for both
`gemini-2.5-flash` and `gemini-2.5-pro`. Google's deprecations page showed **no
shutdown date** for either, the day before, and still does. "No retirement
date" is a statement about existing customers; it says nothing about whether a
new account can obtain the model. A hold-on-cost decision had been made on the
strength of that page. **A vendor's "no retirement date" is not evidence a
model is obtainable; only a call from a fresh account is.**

**Parameter renames at generation boundaries.** Anthropic removed `temperature`
from `messages.create` in SDK 1.x, with no `**kwargs`, so the named argument is
a `TypeError` before any HTTP call. OpenAI's GPT-5 line rejects **both**
`max_tokens` (renamed `max_completion_tokens`) and any non-default
`temperature`. Neither shows up as a dependency bump; both are invisible to a
mocked SDK, because a mock accepts any keyword.

**Output-shape regressions within a family.** `claude-sonnet-5` returns
malformed tool input — a `str` or `dict` where a list was expected, carrying
the expected container inside it — on **two of the six real stage prompts**:
quote-clustering (2 of 2 passes) and thematic-grouping (1 of 2), while
quote-extraction and the three earlier stages pass. Sonnet 4.6 passes all six.
So with the real prompts a run dies at stage 10 or 11, *after* transcription
and every per-session quote call. The live-check script's own prompt
reproduces it on quote-extraction 5/5 — a property of that prompt, not the
pipeline's (corrected 5 Sep from the six-template run in the Online-light
session). Two consequences: **the right fixture is the six real stage
templates**, about 4¢ per model per pass, not one hand-written transcript; and
grouping flipping between passes means **no single probe can promise a run**
— the durable fix is a repair step where decode-time enforcement is not
available. Root cause still not established.

**Both are now done (5 Sep 2026).** The fixture is
`scripts/live_check_fixture.py`, carrying all six calls through the pipeline's
own `get_prompt_template`, fields, `wrap_untrusted` envelope and models. The
repair is `_validate_repairing` in `client.py`, on the Anthropic and Gemini
paths only.

**Building it found a THIRD shape this section had not named**, and the first
version of the repair could not touch it. Sonnet 5 returned
`{"parameters": {"clusters": [...]}}` — the JSON-Schema keyword for a tool's
argument object, leaking into the argument object itself. The repair iterates the
response model's *own* declared fields, deliberately, so that it cannot become a
make-it-parse pass; `parameters` is not one of them. The envelope case is now
handled structurally (exactly one key, not a model field, inner keys within the
model's), which also covers `arguments` / `input` / `properties`.

**Measured after the fix, four passes:** sonnet-5 completes both stages every
time. `s10:clusters` repaired on every pass, `s11:themes` on some — consistent
with the flipping already recorded. The repair logs at WARNING, so a provider
degrading its shape stays visible rather than being absorbed; a silent repair
would have turned this finding into a thing nobody could ever notice again.

**This does not re-open Sonnet 5 as a default.** The repair buys a run that
would otherwise die at stage 10; it is not evidence the model's output is sound,
and the root cause is still unknown.

### Mocks cannot see any of this, and signature checks see only some

Every provider test mocks the SDK's `create`. A mock accepts any keyword and
returns whatever it is told, so it cannot report a removed parameter, a retired
model, or a malformed response. The suite passed 4,246 tests against an
`anthropic` major that would have raised on every Claude call (ledger Entry 6),
and 4,375 against the Sonnet 5 regression.

Two mitigations now exist, and they are different in kind:

- **Installed-signature tests** (`test_every_kwarg_we_send_exists_on_the_installed_sdk`,
  for Anthropic and OpenAI) introspect the *real* SDK and assert every keyword we
  send is accepted. They catch parameter renames the moment the SDK is
  installed. They cannot catch a retired model or a bad response.
- **The live check** (`scripts/check-providers-live.py`) catches all three, at
  the cost of needing keys and network, so it cannot run in CI.

### The list under test has to be derived

Three hand-maintained model tables rotted in one week: the pricing table (a
row wrong in both directions; two offered models with no row at all, so their
users silently saw no cost estimate), `_MODEL_MAX_OUTPUT_TOKENS` (knows only
`gpt-4o`), and the default itself (declared in four places, two tests pinning
the literal). The live check therefore **derives** its list — the registry
default plus `LLMProvider.availableModels`, read from the Swift source — so it
tests what ships and cannot drift from it. Parity tests pin Swift↔Python
defaults and pin that every picker model has a pricing row. Do not add a
fourth table.

### "Current version of the class" is a rule, and rules need re-applying

The Claude default was `claude-sonnet-4-6` not because anyone chose that model
but because "Sonnet class, current version" was evaluated once and left. Every
provider default had the same history. Re-applying the rule is honouring the
decision, not reopening it — but it has to be re-applied against a live
account, because the current version may be broken (Sonnet 5) or the old one
gone (Gemini 2.5).

## What is done

| change | commit | evidence |
|---|---|---|
| Claude temperature via `extra_body` — same wire, survives SDK 1.x | `09bb5e82` | live pass on `claude-sonnet-4-6` |
| OpenAI/Azure: Structured Outputs (`json_schema`, strict) replacing JSON mode | `7fbec0c2` | live pass on `gpt-5.6-terra` and `gpt-4o` |
| OpenAI parameter gate (`_OPENAI_LEGACY_PARAMS`, fails closed to modern) | `208b4b57` | live pass, both shapes |
| ChatGPT default `gpt-4o` → `gpt-5.6-terra`; picker terra + luna | `208b4b57` | live pass through `analyze()` — **but it broke preflight**: `preflight/api_key.py` validated keys with `max_tokens=1`, which GPT-5-class rejects with a 400 the copy blamed on credit, so every ChatGPT run aborted at preflight for a night. Fixed the same night in a separate session (reads `_OPENAI_LEGACY_PARAMS`, sends `max_completion_tokens=256` — a cap of 1 cannot finish a token on a reasoning model). The live check could not see it: it calls `analyze()` directly and skips preflight. |
| Claude default declared once per language; `config.py` and `LLMSettingsView` derive it; parity test | `a9d8f443` | Swift suite green |
| Sonnet 5 tried and **reverted** to 4.6, receipt beside the value | `c3a34866` | 5/5 live failures |
| Gemini default → `gemini-3.8-flash`; picker flash + `3.5-flash-lite`; Pro dropped | `8efcf2dc` | live pass; 2.5 pair 404 |
| Pricing corrected and covered; test asserts arithmetic not rates | `52fccede` | — |
| `mcp` refusals keep their reason on 2.1 (base class, not a refactor) | `e6a161c3` | 73/73 on a scratch venv at 2.1.1 |
| `scripts/check-providers-live.py` + release gate + quarterly item 8 | `b04ac9d2` | 7/7 baseline |
| Keychain: a key saved in the app or the CLI is seen by both | `bcdc03b9` (other session) | read-back |

The live check is wired into `check-release-ready.sh` as a "providers live"
row in the standard ok/warn/bad idiom, with a missing key reported as WARN
(unverified), never OK. Releases happen most weeks; that is the cadence, and
nothing has to be remembered.

## What is not done, and could be

**Rung 3 in the app — paused, by the maintainer's call ("no decisions
yet").** The direction as of 5 Sep is a **weekly cloud-matrix run from the
maintainer's Mac** with candidate models added, plus the cheap change of
pointing the existing one-token ping at the *selected* model. Replicating each
provider's request shape in Swift — proposed in the first handoff — is
withdrawn: a second request builder drifts by construction, and the preflight
regression above is exactly that failure. Running the sidecar's real
`LLMClient.analyze()` has zero drift. Cost policy stands either way: *a tiny
fraction of £1 for a reassuring green light is fine if it's the only way to
confirm a call would succeed* — a handful of probes a day, a handful of cents
a year.

**The live check skips preflight.** `check-providers-live.py` calls
`analyze()`; `bristlenose run` goes through `preflight/api_key.py` first, which
has its own request builder — and that is where the ChatGPT regression lived.
The check should exercise preflight too, or preflight should stop building
requests of its own.

**The acceptance matrix has been silently green since 7 July.**
`scripts/acceptance/run_matrix.py` writes each cell to a fixed directory and
never cleans it, so cloud cells *resumed* old manifests, made zero calls, and
reported PASS; and `is_green` counts `FAIL_EXPECTED` as green, so a configured
provider that cannot start a run still prints GREEN. Fresh directories plus
"configured-and-failed = red" are the two fixes (found 5 Sep, other session;
old cell dirs moved aside, nothing deleted).

**Why Sonnet 5 double-encodes at clustering and grouping.** Unknown. The
`verbatim_excerpt` hypothesis is weakened — extraction, the stage that carries
that instruction, passes. The repair step above is the durable answer; a root
cause is what would let Sonnet 5 back in without one.

**The quote-stability corpus has been rebuilt and run** (5 Sep 2026,
`experiments/quote-stability/`). It had to be rebuilt rather than re-run: the
Jul harness was kept out of the public tree because its corpus was
participants'. The replacement runs on FOSSDA, which is open-source and already
transcribed, so a pass is one `extract_quotes` call per session and nothing
else. Numbers in that directory's `FINDINGS.md`; the design decision that
removed the temperature slider cites the Jul figures, so it is the doc to true
if they have moved.

**Azure is on legacy parameters and a 2024 API version.** It addresses a
deployment, not a model, so no name-based gate can work. A GPT-5 deployment
needs `max_completion_tokens` and a newer `azure_api_version`. The Swift
default and picker still list model names in a field that wants a deployment
name; the parity test excludes Azure for that reason.

**Ollama is still on `json_object`.** An assertion caught that `_analyze_local`
shares the OpenAI shape; it was left alone because Ollama's schema support is
its own implementation. Untested.

**The OpenAI schema is sent twice** — once enforced in `response_format`, once
pasted into the system prompt as text. The prompt copy is now redundant and
costs input tokens on every call. Removing it is a prompt change and wants the
corpus.

**`_MODEL_MAX_OUTPUT_TOKENS` knows only gpt-4o.** `max_completion_tokens` on
GPT-5-class models *includes* reasoning tokens; our 64000 was sized for output
alone. Under the 128K cap, so not refused, but a long transcript's reasoning
could surface as truncation.

**`drop_nulls` rests on an unguarded assumption** — that no response model has
a required-nullable field. True today; a ten-line test would keep it true.

**CLI `configure` validation and the app's probe should ask the same
question**, so "valid" means one thing on both surfaces.

## Challenges

- **Ground truth costs money and needs keys**, so the only test that sees
  everything cannot run in CI. The release gate is the compromise: human at the
  keyboard, keys present, pence per run.
- **Every provider has a different request shape** — tool-use, `json_schema`,
  `response_schema`, deployment names, local — so "one probe" is five probes,
  and a probe that does not replicate the real shape is rung 2 in disguise.
- **Azure's deployment names are opaque**; nothing about `prod-eastus` says
  which model is behind it.
- **Vendor documentation lags vendor behaviour**, and in the case of soft
  retirement is structurally unable to carry the relevant fact.
- **Model tables are hand-maintained by nature** — pricing, output caps,
  sunset lists. Each is a small correctness risk with no gate. Deriving the
  *list* is possible; the *values* still need eyes.
- **The green light is a UX promise the mechanism cannot keep** until rung 3
  exists. Until then the honest caption and the human reading are at odds.
- **Model-choice work is planned** and this should not pre-empt its shape. Two
  declarations per language plus a parity test was chosen over a registry for
  that reason.

## The future

- **A live gate at release cadence** is the floor. A weekly launchd run would
  add inter-release coverage, with the known hazard that an unanswered keychain
  prompt wedges a launchd job silently — it would need a non-interactive key
  source.
- **One request builder, not two.** Whatever probes a provider — the CLI check,
  preflight, a Settings light — should run the sidecar's real `analyze()` on the
  real stage templates. Every second builder has drifted: `api_key.py` did on
  the night the default moved.
- **The quarterly review gains a model-currency pass** (policy item 8): not
  "do the defaults still answer" — the gate covers that — but "are they still
  the right models against each vendor's current lineup", which is a judgement
  a gate cannot make.
- **Per-provider cost research has a second customer.** Beyond the CLI's
  bill-shock estimate, a subscription or relay model would have to provide
  tokens profitably; the same live-and-priced inventory feeds both.
- **When model choice is built**, the derived-list discipline and the parity
  tests are what it should absorb — one source, both languages, pinned.

## Receipts

Ledger: `dependency-premortem-log.md`, Entry 7 § "Live evidence — 4 Sep 2026"
and the Gemini addendum; Held register rows for anthropic, mcp, snapcore.
Policy: `design-platform-policy.md` § Quarterly tooling review, item 8.
Ladder: `design-desktop-settings.md` § the three rungs. The live check:
`scripts/check-providers-live.py`, indexed in `scripts/README.md`.
