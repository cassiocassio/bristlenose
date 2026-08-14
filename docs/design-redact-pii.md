# PII Redaction — exploration, decisions & forward plan

> **Status: PARKED for a post-100days "roll our own PII" project — 26 Jul 2026.**
> The CLI keeps its working Presidio-based redaction **as-is**. Bringing PII to
> the **Mac desktop** is parked: the Background-Assets delivery hits an App Store
> **§2.5.2** blocker, and the whole Presidio/spaCy stack turns out to be more
> machinery than the job needs. The forward direction is **regex + LLM-NER**
> ("roll our own"), deferred to after the current 100days push.
>
> This doc is the **rehydration brief** — everything learned, decided, tested,
> and sketched, so the next person (probably future-me) can pick it up cold.

## TL;DR (the bow)

- **CLI PII = kept, working, untouched.** Presidio + spaCy, off by default,
  `--redact-pii`, `spacy download` on first use. No App Store constraints apply
  to pip/brew/snap. **Do not churn it.**
- **Mac PII = parked.** Presidio is excluded from the sidecar today, so PII is
  simply unavailable on desktop. Delivering it via Background Assets is an App
  Store **§2.5.2** rejection risk (downloading importable *code*); bundling it
  means +560 MB (`lg`) or untested quality (`sm`).
- **Forward = "roll our own PII"** (post-100days): **regex for structured PII**
  (emails/phones/cards/IDs — no ML) **+ the LLM for names/context** via the
  user's already-configured provider. Deletes the entire heavy stack *and* the
  App Store problem, and is **better** on the cases that matter (non-Western
  names, context identifiers), multilingually. The `pii_llm_pass` config field
  ([config.py:176](../bristlenose/config.py), "Not yet implemented") is the
  pre-existing stub for exactly this.
- **UX sketches + evidence preserved:** two mockups + a runnable sm-vs-lg test
  (see §Artifacts).
- **Not a purchase driver.** Good researchers already clean up quotes for
  deliverables every day — it's taken as part of the job by professionals.
  Compliance departments like to pay for it, but it's not a differentiator. This
  is *why* it parks comfortably: low priority, don't invest in a heavy stack.

## Decisions that survive regardless of approach (locked)

These held up across the whole exploration and four review agents; they're
approach-independent and carry forward into "roll our own":

| # | Decision | Note |
|---|---|---|
| D1 | **Off by default** | False positives destroy research-relevant text; most researchers don't need it. `pii_enabled=False` ([config.py:175](../bristlenose/config.py)). |
| D2 | **Applies to the next analysis, onward** | PII is a pre-analysis stage; re-analyse to apply. Fine for v1. |
| D3 | **Native Privacy tab is the Mac control** | 4th Settings tab; failure via the normal `.failed` row, no bespoke dialog. |
| D4 | **PII redaction is an onward-flow convenience, NOT on-disk infosec** | The researcher met the participants and already knows the PII. `transcripts-raw/` **stays** in the output folder even when redaction is on; redaction protects *exports/onward artifacts*. GDPR handled via retention lifecycle + redacted archives. (Memory `project_pii_redaction_is_onward_convenience`.) |
| D5 | **Threshold stays a tuned default** | No threshold UI. |
| D6 | **Name-recall caveat** | Reviewer argued it should be **always-visible and about naming tradition** (English UI + non-Western names is the high-risk case), not gated on UI language. **Open** — see §Reviews. |
| D7 | **No `pii_llm_pass` / `pii_custom_names` UI** | Inert today — but `pii_llm_pass` is the *stub for the forward LLM approach*, so it graduates rather than gets deleted. **Amended 14 Aug 2026 — inert, but no longer silent.** Both used to `warnings.warn` and let the run continue, which made an unimplemented *privacy* control indistinguishable from a working one: a researcher who listed the names they most wanted gone got a run reporting redaction succeeded while those exact names sat in `transcripts-cooked/`. `remove_pii` now raises instead. The fields stay unimplemented (this decision is unchanged, and nothing was built against Presidio); the change is only warn → refuse, which is architecture-neutral and survives the roll-our-own migration untouched. The error counts the names but never quotes them — an exception message reaches logs, `pipeline-events.jsonl`, and pasted bug reports, all named re-identification surfaces. Pinned by `tests/test_pii_audit.py::TestPiiConfig` (three tests, each verified to fail against the old warn-and-continue behaviour). |

## What we learned

The exploration walked from "add a toggle" to "reconsider the whole stack":

1. **The failure/reporting apparatus mostly already works** for PII via the
   central `categorise_exception` + `RunFailedEvent` catch-all — only two
   `isinstance` lines were genuinely missing (F2/F3 → `MISSING_DEP`).
2. **Mac delivery was the hard part**, not the toggle. Presidio is excluded from
   the sidecar; delivering it is where the cost and blockers live.
3. **App Store §2.5.2 kills the on-demand-download route** (below).
4. **The sm-vs-lg test** (below) showed Presidio's *only* advantage from its
   heavy model lands on the exact cases an LLM handles trivially — which
   reframed the whole thing as "are we carrying a stack we don't need?"

## Why the Mac Presidio path is parked — costs & blockers

### App Store §2.5.2 (the decisive blocker)

Delivering presidio + spaCy + native `.so` via Background Assets and extending
`sys.path` is **downloading importable code that introduces functionality** —
squarely within §2.5.2's plain text. Aggravating: the code is *excluded from the
shipped binary* (so the download is what makes the feature runnable), and the
wheels contain **downloaded native Mach-O** (`thinc`, `blis`, numpy `.so`) that
gets `dlopen`'d — the least-defensible category. **Un-pre-testable:** internal
TestFlight serves asset packs with no review gate, so it passes silently now and
gets **rejected at App Store submission**, with no citable appeal precedent.
(§2.5.2's clean side is *data* — Whisper model *weights* download fine; code does
not.)

### The Background Assets build/entitlement costs (if ever revived, data-only)

From the app-store-police pass — all required *if* BA is used, and to be scoped
**data-only** (model weights, never code):
- A `BADownloaderExtension` — a new nested Mach-O needing `app-sandbox`+`inherit`,
  one-Team-ID inside-out signing, and inclusion in the nested-executable verify
  gate (re-opens the "app sandbox not enabled" rejection class from build 2068).
- New host entitlement `com.apple.security.application-groups` + `BAAppGroupID`
  Info.plist keys (host + extension only, never the `inherit` sidecar).
- Any downloaded `.so`/`.dylib` must be Team-ID-signed at pack-build time.
- Re-verify the Privacy Manifest required-reason coverage against the *actual
  pack* `.so`, not the dev venv.
- No new JIT entitlement needed (spaCy/thinc/blis are AOT, unlike mlx-whisper).

### The bundling alternative (also unattractive)

Bundle presidio + spaCy + model in the `.app` — §2.5.2-clean (code ships in the
reviewed binary), out-of-box, no BA. But: **`lg` = +~560 MB** to the app;
**`sm` = +12 MB but untested quality** (see below). Either way you're carrying a
whole NER stack to do NER badly.

## Evidence: sm vs lg (the test we ran)

Ran the planted-PII horror fixture through Presidio with each model
(`experiments/pii_sm_vs_lg.py`). Also confirmed **the code today actually runs
`lg`** — `AnalyzerEngine()` uses Presidio's default; the `_SPACY_MODEL="sm"`
constant is vestigial and never configures the analyzer.

| Set | `en_core_web_sm` | `en_core_web_lg` |
|---|---|---|
| **Must-catch baseline** (clear-intro names, emails, phones — 15 items) | **15/15 (100%)** | **15/15 (100%)** |
| **Hard tail** (deliberately-hard, "likely miss" — 54 items) | 15 | 20 |

`sm` == `lg` on everything that *must* be caught. `lg`'s only edge is 6 hard-tail
items — and they're telling:

> `Fatimah bint Khalid` (Arabic) · `Kapoor` (South Asian) · `Bazza` (nickname) ·
> a spelled-out email (`john dot smith at…`) · an employee ID · +1

So `lg`'s 560 MB buys exactly the **non-Western names** (the ethically-important
cases) — *but even `lg` misses 34 of the 54 hard items.* **No NER model closes
this.** That's the crux: the place `lg` beats `sm` is the place an **LLM crushes
both**, multilingually, with nothing to bundle.

## The forward project: "Roll our own PII" (post-100days)

**Insight:** Presidio's entire value is NER (names/places). Structured PII —
emails, phones, cards, IPs, NHS numbers, IBANs — is **regexes**, no ML. And NER
is precisely where Presidio is weakest and the LLM strongest.

**Shape:**
- **Structured PII → a handful of regexes.** Deterministic, language-independent,
  ~zero stack. (Presidio's pattern recognizers do this today; they don't need
  Presidio.)
- **Names / places / context → the LLM**, via the user's configured provider,
  using BN's existing structured-output (Pydantic-schema) infra — the same
  machinery as quote extraction / topic segmentation. `pii_llm_pass`
  ([config.py:176](../bristlenose/config.py)) is the pre-existing stub.

**What it deletes:** presidio-analyzer, presidio-anonymizer, spaCy, the 560 MB
model, the native `.so`, the `[pii]` extra question, `find_pii_stack`, the BA
delivery, **and the entire §2.5.2 App Store problem.**

**What it improves:** name recall on non-Western names + nicknames + obfuscated
forms + context identifiers ("the manager at the GP practice in London"), and
**multilingual for free** (kills the hardcoded `language="en"` and the D6 caveat
problem).

**The one real counter — the trust boundary — and why it's weaker than it looks:**
LLM-detecting PII sends raw PII to the LLM. But (a) the transcript **already**
goes to the LLM for analysis; (b) per D4, redaction is onward-convenience, not
"never touches the cloud"; (c) **Ollama users stay fully local** — the LLM-NER
runs on their machine; (d) the "redact before anything leaves" promise is
*already* porous (speaker-ID sends intro PII pre-redaction —
[SECURITY.md](../SECURITY.md)). What you'd give up is the theoretical
"redact-locally-then-cloud-analyse" ordering — leaky today anyway.

**Open questions to settle first:**
1. Confirm the trust-boundary stance (methodology-adjacent — check
   `docs/methodology/consent-gradient.md` + research-methodology; possibly a
   Boss/founder call). D4 largely answers it.
2. CLI: keep Presidio (per this session's steer) or unify on LLM later? Default:
   **keep Presidio on CLI**, roll-our-own targets the Mac path first, unify only
   if it proves out.
3. Determinism: regex owns structured PII (must be exact); the LLM only does
   names — so an occasional LLM miss never affects emails/phones.
4. Cost/latency of an extra pass (or fold into an existing one).

## Reviews (consolidated — so we don't re-run them)

Four agents reviewed the (parked) Presidio-BA spec:
- **Parsimony:** land-as-specified; Phase 0 is the ship-today slice; fixed a
  `find_whisper_model()` reference that doesn't exist (real precedent:
  `BRISTLENOSE_WHISPER_MODEL_DIR` at [s05_transcribe.py:411](../bristlenose/stages/s05_transcribe.py)).
- **Correctness:** mechanism verified; F5's `str(exc)` can reach the hidden
  events log (audit what Presidio raises, else wrap stage 7 for a structured
  `Cause` per A4 invariant 3); non-`OSError` spaCy load = an unlisted F6; stale
  `transcripts-cooked/` on toggle-off.
- **Security:** *safe to ship* with fixes. Flagged un-redacted `transcripts-raw/`
  in the output root — **reframed by D4** (not a leak in this threat model; raw
  stays). D6 caveat keyed on the wrong variable (see D6). Supply-chain: enforce
  user-only ownership before extending `sys.path`; SHA-pin the CLI model wheel
  like FFmpeg. Importer should **fail loud** when redaction was requested but no
  cooked transcripts exist (the real integrity question).
- **App Store:** the §2.5.2 blocker above; bundle-code-not-download is the clean
  path; reserve BA for data-only model weights.

## Appendix A — the parked Presidio + Background Assets Mac design

Preserved so it can be rehydrated if the LLM route doesn't pan out.

**Delivery (design-modularity.md §"PII removal"):** presidio+spaCy+model as a
wheel-archive Apple-Hosted Background Assets pack, unpacked to Application
Support, `sys.path`-extended at sidecar startup via `BRISTLENOSE_PII_LIB_DIR`
(mirroring the `BRISTLENOSE_WHISPER_MODEL_DIR` pattern). PyInstaller already
excludes presidio/spaCy ([bristlenose-sidecar.spec:209](../desktop/bristlenose-sidecar.spec)).

**Runtime failure modes:** F1 presidio-missing (`ImportError`→`MISSING_DEP` ✓) ·
F2 model-absent (`FrozenSidecarError`→ needs +isinstance) · F3 download-failed
(`PackageInstallError`→ needs +isinstance) · F4 disk-full (`OSError`→`DISK` ✓) ·
F5 Presidio runtime error (`UNKNOWN`; audit for PII in `str(exc)`) · F6
non-`OSError` spaCy load on Py3.14+ (`ConfigError`→ add).

**Delivery failure modes:** BA1 offline · BA2 interrupted (auto-resume) · BA3
unpack disk-full → `DISK` · BA4 pack unavailable (dev/staging).

**Borrow ledger:** almost everything borrows the existing pipeline machinery at
0 change (terminus, CLI banner, `.failed` row, popover, status page, manifest
marks, cache-bust, doctor, capability matrix). Genuinely new was: +2
`isinstance`, `find_pii_stack()`, the Privacy tab, `piiEnabled` UserDefaults +
env line, and the BA delivery itself. No new tokens/journalling/orchestration.

**Every user-facing string** (Privacy tab, download states, CLI, SPA) is
inventoried and rendered in the mockups below.

## Artifacts

- **UX sketches:** [`docs/mockups/mockup-privacy-settings.html`](mockups/mockup-privacy-settings.html)
  (Privacy tab + failure surface) · [`docs/mockups/mockup-pii-wiring-spec.html`](mockups/mockup-pii-wiring-spec.html)
  (data-flow, failure ledger, full string inventory).
- **Evidence:** [`experiments/pii_sm_vs_lg.py`](../experiments/pii_sm_vs_lg.py) —
  runnable sm-vs-lg horror-harness comparison.
- **Existing quality harness:** `tests/test_pii_audit.py` (`-m slow`) +
  `tests/fixtures/pii_horror_*`.
- **Memory:** `project_pii_redaction_is_onward_convenience`.
- **Related:** [`docs/design-modularity.md`](design-modularity.md) (delivery),
  `docs/methodology/consent-gradient.md` (governance),
  [`SECURITY.md`](../SECURITY.md) (PII timing, output files).
