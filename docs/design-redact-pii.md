# PII Redaction — exploration, decisions & forward plan

> **Status: DELIVERY UN-PARKED 12 Sep 2026; ENGINE CHOICE STILL OPEN.**
> The §2.5.2 blocker below was a blocker on shipping *code* through Background
> Assets. Splitting code from data removes it — see §"Un-parking the Mac path
> (12 Sep 2026)". What has *not* changed is the second, independent argument for
> rolling our own: the Presidio stack is still more machinery than the job needs.
> So there are now two live routes where this doc had one. The original parked
> status is preserved verbatim below because its reasoning is still load-bearing.
>
> **Superseded status (26 Jul 2026):** PARKED for a post-100days "roll our own PII" project.
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

## Roll our own PII — **REJECTED 12 Sep 2026**

> **Decision: we are not building a PII engine. Presidio + spaCy + `en_core_web_lg`
> is the engine, and the remaining problems are treated as packaging and
> configuration.** The analysis below is kept because it is sound and because it
> names the real weaknesses — but the conclusion it reaches is not the one taken.
>
> **What flipped it is that the weaknesses turned out to be configuration, not
> limitations.** Every gap the hour-scale corpus measured sits inside Presidio's
> own extension surface:
>
> | measured gap | what it actually is | cost |
> |---|---|---|
> | phones 2/8, both models | `PhoneRecognizer.SCORE = 0.4`, lifted to 0.75 only by an adjacent context word. `__init__` takes `context=`. Widening the list took the sample from **1/4 to 3/4**, measured. | 0 MB |
> | `Fedora`/`Bash`/`Kotlin` → `[NAME]`, both models | `analyze(allow_list=[...], allow_list_match="exact")`. Suppressed **8/8** product names while `Ada Okonkwo` and `Marcus Swift` stayed caught — exact matching is on the whole span, so an allow-listed token inside a full name does not suppress the name. | 0 MB |
> | employee ID · postcode · DOB, 0/n | No recogniser exists for them. `PatternRecognizer` is Presidio's own registration point. | 0 MB |
> | hardcoded `language="en"` | Presidio takes a per-language NLP engine. | model-sized |
>
> So "the off-the-shelf detector is not good enough" was substantially "the
> off-the-shelf detector is unconfigured". Tuning it is ordinary work against a
> library we already ship; replacing it is a new detection engine for a privacy
> control, needing its own validation and blocked on a methodology call.
> **Don't reopen this without new evidence** — the eval rig
> (`experiments/pii_corpus_hour.py` + `pii_measure_hour.py`, 68 planted spans and
> 32 negative probes) is what new evidence would have to come from.
>
> The delivery of the 425 MB model stays an open packaging question — see
> §"Un-parking the Mac path".

## Post-beta: a per-project allow-list the researcher builds by review

**Decision 12 Sep 2026: Presidio configuration work is post-beta**, and when it
comes the allow-list should be **per project or per folder, curated by the
researcher**, not a global brand-name list we maintain.

**Why per-project beats a shipped list.** The measured false positives were
`Jenkins` · `Ada` · `Swift` · `Bash` · `Kotlin` · `Vala` · `Fedora` · `Grafana` —
technical vocabulary, redacted identically by both spaCy models. A global list
fixes those eight and then becomes a treadmill: every new product name is an
entry we add, forever, against a vocabulary that moves faster than our release
cadence. And the ambiguous entries carry a permanent cost we would be choosing on
the researcher's behalf — allow-listing `Ada` means a participant referred to as
"Ada", with no surname, stops being redacted in *every* study. A medical study and
a developer-tools study want opposite answers, and only the researcher knows which
they are running.

**The shape.** Review what was redacted, toggle the wrong ones back, and the
toggle adds that term to the project's allow-list for the next analysis. It is a
review queue over redactions, not a settings form — the researcher is already the
person who knows `Fedora` is an operating system.

**It front-loads, which changes what kind of feature it is.** The first one or two
interviews of a study expose ~90% of the vocabulary that matters, and it is
overwhelmingly **brand and product names that are also human names** — the
measured false positives were exactly this shape (`Jenkins`, `Ada`, `Swift`,
`Julia`), not arbitrary nouns. A statistical NER cannot separate those two senses
and never will; the researcher separates them in seconds because they know which
study they are in. So this is a **setup pass, not a chore**: heavy on interview
one, near-silent by interview three. Design it as something that gets out of the
way — the queue should visibly shorten — rather than a permanent review surface.

**Borrow, don't invent.** This is the accept/deny review idiom the codebook
surface already ships (badge accept/deny, the AutoCode review queue). Same
gesture, different queue. Do not design a new one.

**Parked until Presidio runs reliably from the TF app (12 Sep 2026):** structured
recognisers can also fire on numbers that are *not* identifiers. A participant
count, a dosage, a version string or a reference number can shape-match
`CREDIT_CARD` (Luhn) or `UK_NHS` (modulus-11) — both are checksum recognisers, so
a coincidence passes the checksum and the number is destroyed in the transcript.
Unmeasured; the hour corpus planted valid identifiers and did not probe innocent
numbers that happen to validate. Falls to the same review-queue affordance as the
name case, and the same 0-MB configuration surface. **Sequenced after delivery,
deliberately** — there is no point tuning a detector that cannot yet reach the
Mac.

**Two things it must respect.**

1. **The data source is a re-identification key.** `pii_summary.txt` already lists
   every original value with timecodes, and lives in `.bristlenose/` precisely so
   it is not shareable. A review UI is the affordance the security review predicted
   would be proposed here, and its constraint stands: never render it into an
   export, a feedback bundle, or anything a researcher can hand on. Revealing in
   Finder (where the file's own CONFIDENTIAL header is visible) is safer than
   rendering the values in-app.
2. **Allow-listing is a privacy control operated in reverse.** Every entry is a
   deliberate decision to stop redacting something. The list wants provenance —
   what was added, when — for the same reason the redaction itself does.

**What parking this means for beta, stated once.** The measured gaps ship as they
are: six of eight phone numbers survive redaction, and technical vocabulary is
over-redacted. The blast radius is small because PII is **off by default** and,
until the delivery question is settled, **CLI-only** — so this affects opt-in CLI
users, not the default path. That is what makes parking it reasonable rather than
risky, and it is also why the delivery question and this one are independent.

### The rejected design, preserved (post-100days, was the forward direction)

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

## Un-parking the Mac path (12 Sep 2026)

**What changed.** Nothing about §2.5.2 — the rule, and this doc's reading of it,
both stand. What changed is realising the delivery was mis-shaped: we costed
"presidio + spaCy + weights, all of it, through Background Assets", which is
downloading importable code and is correctly refused. **Split the payload and the
blocker disappears**, because §2.5.2's clean side is *data*, which is exactly what
Apple's own on-demand dictation and translation language packs are.

### The split, measured (12 Sep 2026)

| Payload | Size | Native Mach-O objects | Ships how |
|---|---|---|---|
| `en_core_web_lg` — the weights | **425 MB** | **0** (one `.py`, a thin `load()`) | On demand, Background Assets |
| spaCy · thinc · blis · presidio (+ srsly, preshed, cymem, murmurhash) | ~46 MB on disk, ~39 MB est. post-freeze | **63** | **Bundled in the reviewed binary** |

_The earlier "73" counted numpy's 19, which the bundle already carries — a marginal-vs-total mix-up. Re-measure post-freeze rather than carrying the estimate._

The thing we want on demand is verifiably pure data; the thing that must be
reviewed is small. That is the sanctioned shape rather than a workaround for it.

### Why not roll our own download (asked, and answered against)

> **Correction, 12 Sep 2026.** This section first argued that library validation
> would refuse a self-downloaded `.so` and nothing would run. **That was wrong,
> and wrong in an instructive way:** it read the *host's* entitlements and drew a
> conclusion about the *sidecar*, which is the process that would actually
> `dlopen` the code — and `desktop/bristlenose-sidecar.entitlements` has carried
> `com.apple.security.cs.disable-library-validation` since 28 Apr 2026, for the
> `Python.framework` nested-seal reason its own header records. There is no OS
> backstop under a downloaded pack. Same family as the "ask the build system, name
> the scheme" gotcha: naming the wrong target returns a real answer to the wrong
> question.

The conclusion survives, on four reasons that are actually true. Background Assets
gives us resume across quit and reboot, background scheduling, storage accounting
the system can reclaim under pressure, and a **declared, reviewable** delivery
mechanism. Rolling our own gives a worse version of all four and one extra
liability: with library validation disabled on the loading process, a compromised
CDN can serve anything and nothing in the OS objects. **So the pack owes its own
integrity check** — pin a SHA-256 in the app and verify before the first
`spacy.load`, exactly as the security review already required for the CLI model
wheel and as we do for FFmpeg. **Go native, and verify the bytes ourselves.**

### Which BA API — and the floor that decides it

| API | Floor | Verdict |
|---|---|---|
| `BAAssetPackManager.ensureLocalAvailabilityOfAssetPack:` | `macos(26)` (some methods 26.4) | Exactly this feature, written by Apple. **Off our floor.** |
| `BADownloadManager` + `BAURLDownload` | **`macos(13.0)`** | What we build against. Self-hosted `NSURLRequest`, `essential:NO`. |

Deployment floor is held at 15.0 (`project_deployment_floor_held`, 3 Sep 2026), so
the managed API is unavailable. Revisit when the floor moves to 26 — it would
delete most of this section's code.

**No `BADownloaderExtension` appears to be required for our case**, on three
header readings: `BAErrorCodeCallFromExtensionNotAllowed = 50` exists (some
methods are app-only — the app is a first-class caller); `fetchCurrentDownloads`
documents downloads "queued by your application or extension"; and
`performWithExclusiveControl:` exists precisely so app and extension do not
collide. The extension serves pre-launch and app-not-running downloads; ours is a
user in Settings with the app in front of them. **`applicationGroupIdentifier` is
a required init parameter**, so `com.apple.security.application-groups` plus a
registered App Group is mandatory — an entitlement, not a nested Mach-O. On macOS
the group string is Team-ID-prefixed (`<TeamID>.app.bristlenose`), not iOS's
`group.` form. **Sequence the portal work before the spike, not during it:**
signing is `Manual` with `PROVISIONING_PROFILE_SPECIFIER = Bristlenose Mac App
Store`, so the App ID must gain the capability and that named profile must be
regenerated or the archive will not sign — the identical hazard to the standing
`associated-domains` rule. _(An earlier draft named a `BAAppGroupID` Info.plist
key; it does not exist. The SDK's keys are `BAEssentialMaxInstallSize`,
`BAHasManagedAssetPacks`, `BAManifestURL`, `BAMaxInstallSize`,
`BAUsesAppleHosting`. Note `BAURLDownload` also takes `fileSize:` as a required
parameter — an exact byte count to publish with the pack and keep in sync.)_

> ⚠️ **This is the one unproven claim in the plan, and Phase 1 exists to prove it.**
> The headers establish the API surface and the floors; they do not establish that
> a BA-using app functions with *no extension target present*. Apple's templates
> pair them. Prove it before scoping anything downstream of it.

### Build order

Phases 0–2 are independent of Background Assets and can land immediately; the
UX for phases 3–4 is specced in `docs/mockups/mockup-privacy-settings.html` §1b.

- **Phase 0 — reconcile the model. ✅ DONE 12 Sep 2026.** `_SPACY_MODEL` was
  `en_core_web_sm` and vestigial: a bare `AnalyzerEngine()` took Presidio's
  default, so we fetched 12 MB and silently pulled 400. It is now `en_core_web_lg`
  and `_build_engines` binds the analyzer to it via `NlpEngineProvider`, so
  fetched == used. The `preflight.pii.downloading` string said "~12 MB" and now
  states the real size. **Owed:** 15 non-en locales still carry the 12 MB claim,
  and `doctor.py` / `doctor_fixes.py` still probe for and recommend `sm` at eight
  sites — so `doctor` can call the stack healthy on a machine that will then
  download 400 MB. The model name wants one shared constant.
- **Phase 1 — the BA spike.** A throwaway target with the App Group entitlement,
  **no extension**, one `scheduleDownload:` of a small self-hosted file. Does it
  transfer, or return `BAErrorCodeCallerConnectionNotAccepted` (55) /
  `…ConnectionInvalid` (56)? Everything below is contingent on this. Half a day.
- **Phase 2 — the failure apparatus.** *Verified still open 12 Sep.* Stage 7 has
  **no try/except and no failure recording**, so a `remove_pii()` raise is an
  unclassified crash that cannot reach the project-row status line;
  `categorise_exception` handles neither `FrozenSidecarError` nor
  `PackageInstallError`. Add both `isinstance` arms → `MISSING_DEP`, and wrap the
  stage. **Semantics are already decided and are privacy-critical: fail-stop.**
  If redaction was asked for and could not run, the run must abandon — never
  analyse unredacted transcripts behind a warning. Keep `cause.message` to class
  name + stage per the privacy contract; audit what Presidio raises before letting
  any `str(exc)` through. This is the largest slice and the mockup is right that
  it, not the toggle, is the real work.
- **Phase 3 — bundle the code.** Drop `presidio_analyzer`, `presidio_anonymizer`,
  `spacy` from `excludes` in `desktop/bristlenose-sidecar.spec`; keep
  `en_core_web_lg` out. Re-run `check-bundle-manifest.sh` and
  `check-bundle-integrity.py`, and re-verify Privacy Manifest required-reason
  coverage against the *actual* bundle `.so`, not the dev venv.
- **Phase 4 — BA delivery + Privacy tab.** `BAURLDownload` against a self-hosted
  425 MB pack; `PrivacySettingsView` with the five states from the mockup;
  `piiEnabled` UserDefaults + one `env["BRISTLENOSE_PII_ENABLED"]` line in
  `BristlenoseShared.swift`; `BRISTLENOSE_PII_LIB_DIR`-style path handoff so
  `spacy.load(<path>)` reads the pack without importing it as a package.
- **Phase 5 — copy, i18n, docs.** ~8 new strings × 21 locales (English settles
  first). App-Store-facing: Privacy Manifest (expected answer: **no
  change** — the only required-reason symbol in the 63 new objects is blis's
  `_mach_absolute_time`, already declared under `35F9.1`) and the App Review note
  making the code/data split checkable. True `design-modularity.md`'s PII row, this
  doc's Appendix A, and both mockups.

### Open decisions, named rather than assumed

1. **A run that starts before the download finishes** — wait, or fail cleanly with
   the existing `MISSING_DEP` row? Failing is nearly free once Phase 2 lands;
   waiting is kinder and matches "the appliance copes". Decide before the Swift.
2. **Engine choice is still open.** This plan makes Presidio *deliverable*; it does
   not make it *right*. Roll-our-own still deletes 425 MB, the native code, the
   App Store question and the hardcoded `language="en"` — and is better on exactly
   the non-Western names `lg` is bought for. A cheap hedge exists: bundle `sm`
   (+15 MB) so the toggle works instantly at 15/15 on the must-catch set, with the
   `lg` pack as an optional upgrade for the hard tail.


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
