# PII Redaction — exploration, decisions & forward plan

> **Status: SHIPPING PRESIDIO ON ALL THREE CHANNELS. Engine choice CLOSED,
> Mac delivery UN-PARKED — both 12 Sep 2026.**
> Two things changed on the same day and this header claimed neither for half a
> day afterwards. **The engine is Presidio** — "roll our own" is REJECTED, see
> that section. **The Mac path is un-parked** — §2.5.2 was a blocker on shipping
> *code* through Background Assets, and splitting code from data removes it.
>
> The parked-era reasoning is preserved verbatim below because it is still
> load-bearing: it is *why* the split is the right shape, and the §2.5.2
> analysis is the argument a reviewer would have to be answered with.
>
> **Superseded status (26 Jul 2026), kept as history:** PARKED for a post-100days
> "roll our own PII" project. The CLI keeps its working Presidio-based redaction
> **as-is**. Bringing PII to the **Mac desktop** is parked: the Background-Assets
> delivery hits an App Store **§2.5.2** blocker, and the whole Presidio/spaCy
> stack turns out to be more machinery than the job needs. The forward direction
> is **regex + LLM-NER** ("roll our own"), deferred to after the current push.
>
> This doc is the **rehydration brief** — everything learned, decided, tested,
> and sketched, so the next person (probably future-me) can pick it up cold.

## TL;DR (the bow)

- **One engine, three channels.** Presidio + spaCy `en_core_web_lg`, off by
  default. The *code* (33 MB measured, not the ~100 MB this doc long claimed)
  is bundled everywhere; only the **425 MB model** is acquired on demand, and
  a model is data, which is what §2.5.2 turns on and what Background Assets is
  for.
- **One seam, three acquirers.** Every consumer resolves through
  `resolve_spacy_model()` — CLI does `spacy download`, the `.dmg` fetches plain
  HTTPS from `bristlenose.app/models/`, TestFlight/MAS uses managed Background
  Assets. Proven, not assumed: the path route was run with the package made
  unimportable and scored identically.
- **Mac PII is gated at macOS 26**, where the managed BA API lives. Below it the
  toggle renders visible and disabled. The app's own floor stays 15.0.
- **"Roll our own PII" is REJECTED** — the user's call: *"I'd rather deal with
  this as a packaging challenge than a start-again DIY problem."* The §2.5.2
  argument that motivated it dissolved once code and data were separated.
- **Measured, not asserted** (planted-PII hour corpus, through `remove_pii`
  itself): 45/52 targeted PII removed, 9/32 near-miss probes over-redacted —
  every one a product name that is also a person's name, which is what the
  post-beta per-project allow-list is for. Known gaps are listed with the
  measurement, the realest being **spelled-out emails** ("jane dot smith at…"),
  which no pattern can see and spoken interviews are full of.
- **Not a purchase driver.** Good researchers already clean up quotes for
  deliverables — it's taken as part of the job. Compliance departments like to
  pay for it; it is not a differentiator. That is why it stayed cheap: no heavy
  bespoke stack, just careful delivery of an off-the-shelf one.

## Decisions that survive regardless of approach (locked)

These held up across the whole exploration and four review agents, and they are
**engine-independent** — written when "roll our own" was the forward direction,
and unchanged by its rejection. That is the point of the section: they constrain
whatever detector sits underneath, so they would survive a future swap too.

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

> **SUPERSEDED by "The macOS 26 gate (decided 12 Sep 2026)" below.** This
> section concluded classic `BADownloadManager` on a held 15.0 floor. The gate
> decision reverses it: the *feature* is gated at macOS 26 rather than the app's
> floor being raised, which puts the **managed** API back in reach and deletes
> the classic path — and with it the hand-written downloader extension that made
> this section's costing expensive. Kept because the API comparison and the
> header readings below are still the evidence the gate rests on.


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

### Delivery architecture — SETTLED 12 Sep 2026

**One seam, three acquirers, no build fork.** The Python side never learns who
fetched the bytes; it is handed a directory and calls `spacy.load(<dir>)`, which
was verified to load from a path **without importing the package** — that is both
the mechanism and the §2.5.2 argument. Precedent is `BRISTLENOSE_WHISPER_MODEL_DIR`.

**Code ships bundled on every channel** — presidio, presidio-anonymizer, spaCy,
thinc, blis (~39 MB, 63 native Mach-Os, all arm64 *bundles*, none of them
executables, so the nested-signing posture that produced build 2068's rejections
is untouched). Only the 425 MB of weights is acquired, and only that differs:

| channel | acquirer | why this one |
|---|---|---|
| CLI — PyPI · Homebrew · Snap · Fedora | `spacy download` on first use | works today; no store rules exist on these channels |
| `.dmg` — Developer ID | plain HTTPS → Application Support | **App Store guidelines do not apply to this channel.** §2.5.2 is an App Store rule; the payload is data, so library validation is moot |
| TestFlight / App Store | **managed** Background Assets, self-hosted pack | §2.5.2 wants the platform mechanism, and self-hosting is explicitly supported |

**The switch already exists.** `DistributionChannel.current` returns `.debug` /
`.developerID` / `.appStoreOrTestFlight` off the `DEVELOPER_ID_BETA` compilation
condition already wired for the alpha-expiry pill. So this is **one Swift protocol
with two implementations behind an enum that ships today** — not a divergent build
path, and not two spec configurations.

**The consequence worth naming:** the one claim nobody could establish — whether a
Developer-ID BA download completes for a real end user — **never has to be
answered**, because the `.dmg` channel does not use Background Assets. We route
around the unproven thing instead of betting on it.

#### The macOS 26 gate (decided 12 Sep 2026)

**Mac PII requires macOS 26.** Below it the Privacy toggle renders **visible and
disabled**, labelled *"Requires macOS 26 Tahoe or later"*. Accepted tradeoff for
v1, and it buys a great deal:

- The **managed** API (`AssetPackManager.ensureLocalAvailabilityOfAssetPack`,
  `ManagedDownloaderExtension`) is macOS 26+, and it is the one with the
  near-zero-code extension — RawCull's is a single line, Blankie's is three. The
  classic `BADownloadManager` + hand-written-extension path is **deleted from the
  plan**, and with it most of what made the earlier costing expensive.
- One code path on the Mac instead of a 15.0 fallback and a 26 fast path.
- Revisit when the deployment floor moves (`project_deployment_floor_held`); the
  gate then simply disappears.

**The gate is 26.0, and the 26.4 marks in the SDK are renames, not a floor
(read from the macOS 26.5 SDK's swiftinterface, 12 Sep 2026).**
`public actor AssetPackManager` is `@available(macOS 26, *)`; `assetPack(withID:)`,
`url(for:)` and `shared` carry no narrower annotation. Two calls are
*deprecated* at 26.4 in favour of renamed siblings —
`ensureLocalAvailability(of:)` → `ensureLocalAvailability(of:requireLatestVersion:)`
and `status(ofAssetPackWithID:)` → `status(relativeTo:)` — and deprecated is
not removed. So the acquirer forks at 26.4 and calls the renamed form there,
and the product gate stays where it was decided. This is the *progressive
enhancement* row of `desktop/CLAUDE.md`'s "offered, not required" table; a
26.4 warning in Xcode is an argument for `if #available`, never for moving a
gate that costs users 26.0–26.3.

**Open call, small:** whether the `.dmg` also gates at 26. Its plain-HTTPS acquirer
has no OS floor, so it *could* serve 15.0+ — but gating both gives one string, one
support story and one QA matrix, on a channel that is temporary and expiring
anyway. **Default: gate both.** Ungate the `.dmg` only if a tester on 15.x needs it.

#### Prior art

**RawCull** (`github.com/rsyncOSX/RawCull`) is the closest published analogue and
should be read before writing any Swift: macOS-only, **self-hosted** managed BA,
downloading ML models of 283 MB and 1.54 GB, GitHub Releases as the CDN, shipping
TestFlight *and* a Developer-ID DMG. Its manifest is live. **Blankie**
(`github.com/codybrom/Blankie`) is the Apple-hosted counterpart.

Two Apple-side facts that reframe the risk: self-hosting is documented on Apple's
own App Store "what's new" page, and **On-Demand Resources are deprecated in
favour of Background Assets** from OS 27 — this is a framework Apple is investing
in, not one to route around.

#### What needs an outward act (not buildable in this repo)

1. **Register an App Group, Team-ID-prefixed** (`<TeamID>.app.bristlenose`). The
   Team-ID prefix is the escape hatch: it needs **no provisioning profile**, which
   is what makes Developer ID irrelevant to the question. Signing is `Manual` with
   a named MAS profile, so the profile must be regenerated or the archive will not
   sign — the same hazard as the standing `associated-domains` rule.
2. **A new extension target** in the Xcode project.
3. **Hosting the pack** and pinning its SHA-256 in Swift (self-hosted origin, no
   Apple signing of the payload — see the correction above about library validation).

#### Runbook — the four steps only the maintainer can do

Concrete values for this project: team **`Z56GZVA2QB`**, app **`app.bristlenose`**,
`CODE_SIGN_STYLE = Manual`, `PROVISIONING_PROFILE_SPECIFIER = Bristlenose Mac App
Store`. Do these **in order** — 2 fails without 1, and 3 fails without both.

**1 · Register the App Group — and use the Team-ID prefix.**
Developer portal → Certificates, Identifiers & Profiles → Identifiers → **App
Groups** → new, identifier exactly `Z56GZVA2QB.app.bristlenose`.

**Not** the iOS-style `group.` prefix. This is the whole escape hatch: macOS
accepts an app group when *any one* of — Mac App Store distribution, a
Team-ID-prefixed identifier, or a profile authorising it — holds, and Apple
(Quinn, DTS) will not issue a Developer-ID profile authorising an app group. The
Team-ID prefix needs no profile, so it is the route that works on every channel.
Then Identifiers → `app.bristlenose` → enable the **App Groups** capability and
select the group.

> ⚠️ **One capability per Save, and read it back from a fresh page load.**
> Learned the hard way, 12 Sep 2026. The capabilities page submits the *whole*
> form, so a second Save can silently drop what the first one set: App Groups was
> enabled and confirmed showing **(1)**, then a separate Save that only unticked
> Associated Domains reverted it — with no error, and the page still reading as
> though it had worked. Everything downstream then failed confusingly: the
> regenerated profile carried no app group, and the generate page's *Enabled
> Capabilities* quietly listed only In-App Purchase.
>
> So: change one capability, Save, **reload**, and confirm it stuck. The
> post-save UI is not evidence — the same rule as `CredentialStore.set()`
> returning cleanly, which this codebase already learned once.

**We do not already have this — but we have its neighbour, which de-risks it.**
`Bristlenose.entitlements` holds exactly one key today, and the shipping
Developer-ID `.dmg` carries it signed and notarised:

```
keychain-access-groups → $(AppIdentifierPrefix)app.bristlenose → Z56GZVA2QB.app.bristlenose
```

Different entitlement, different portal capability — having it grants nothing —
but it is the **same Team-ID-prefixed shape**, with the same `$(AppIdentifierPrefix)`
expansion, already proven to sign on the Developer-ID channel. That is the
reassurance the BA research could not give: a team-scoped entitlement does ship
on this project's `.dmg` today.

**One wrinkle it exposes.** There are only two build configurations, `Debug` and
`Release`, and *both* channels build `Release` — the `.dmg` distinguishes itself
with command-line overrides in `desktop/scripts/build-dmg.sh:342-353`
(`CODE_SIGN_STYLE=Automatic`, an emptied `PROVISIONING_PROFILE_SPECIFIER`,
`DEVELOPER_ID_BETA`). So they **share `Bristlenose.entitlements`**, and adding the
app group puts it on the `.dmg` too — a build that does not use Background Assets
and where Quinn's "no Developer-ID profile authorises an app group" could bite at
archive time.

Fix it in the same change, and it is one line: add a
`BristlenoseDeveloperID.entitlements` (the current file, without the group) and,
next to the five overrides already at `build-dmg.sh:342-353`, one more setting —
`CODE_SIGN_ENTITLEMENTS="Bristlenose/BristlenoseDeveloperID.entitlements"` with
the usual trailing backslash. **Not deliberately fenced:** it is a build-setting
line for the middle of an `xcodebuild` invocation, and a fenced block in this
repo's tooling renders as a Run button — pasted into a shell the trailing
backslash just hangs it at a continuation prompt.

Do it *with* the group, not before: today the two files would be identical, and a
no-op split is a change whose reason nobody can see in the diff.

**2 · Regenerate the Mac App Store provisioning profile.**
Because signing is `Manual` against a *named* profile, the existing one does not
carry the new entitlement and the archive will refuse to sign with *"Provisioning
profile … doesn't include the com.apple.security.application-groups entitlement."*
Regenerate **Bristlenose Mac App Store**, download, and **verify before
installing** — decode it with `security cms -D -i <file>` and confirm the
`Entitlements` dict actually carries `com.apple.security.application-groups`.
On 12 Sep 2026 the first regeneration came back **without it**: the generate page
had shown *Enabled Capabilities: In-App Purchase* only, because the App-Group
capability had been saved on the App ID moments earlier and had not propagated to
the profile generator. Regenerating a second time is the fix; the tell is on the
generate page before you ever download.

**Do not double-click a distribution profile.** macOS System Settings accepts
*development* profiles only and answers *"Only Development Provisioning Profiles
can be installed in System Settings. Production Provisioning Profiles are
imported within Xcode."* — an alarming-looking dialog for an entirely normal
file. Copy it into Xcode's store instead:
`~/Library/Developer/Xcode/UserData/Provisioning Profiles/`, or let Xcode fetch
it via Settings ▸ Accounts ▸ Download Manual Profiles.
This is the same class as the standing `associated-domains` guard — an entitlement
that obliges a profile regeneration.

**3 · Add the extension target in Xcode.**
File → New → Target → **Background Assets Downloader Extension**. Two things the
template will not get right on its own:

- **Bundle ID must be a child of the app's** — `app.bristlenose.BAExtension`. A
  sibling identifier registers but is never matched to the app.
- **Both** the app and the extension need App Sandbox *and* the app group. The
  **sidecar must not** — `desktop/bristlenose-sidecar.entitlements` is the
  `inherit` target, and host entitlements on it trip `_libsecinit_appsandbox`.
  That rule is standing and this does not change it.

With the managed API the body is one line (`struct …: ManagedDownloaderExtension {}`).
Read `github.com/rsyncOSX/RawCull` first — macOS-only, self-hosted, ML models,
TestFlight plus a Developer-ID DMG, i.e. our exact shape.

**4 · Host the pack and pin its hash.**
Publish the inner `en_core_web_lg-<version>/` directory — the loadable unit, which
contains **no `.py` at all**, and shipping only it is what makes the payload
literally zero-Python rather than merely zero-native-code. RawCull uses GitHub
Releases; `bristlenose.app` is the alternative. Then **pin the SHA-256 in Swift and
verify before unpack**, the same mechanism as `fetch-ffmpeg.sh`'s `FFMPEG_SHA256`.
This is not optional dressing: the origin is ours, Apple signs nothing in the pack,
and the sidecar carries `cs.disable-library-validation`, so there is no OS backstop.
Unpack to a temp directory inside the container, atomic-rename into place, write a
completion sentinel, and have the Python side refuse a pack directory with no
sentinel — a half-unpacked pack still satisfies `Path(...).exists()`, which is
exactly the predicate Presidio's download guard uses.

**Verification, once 1–3 are done:** archive the MAS scheme and confirm it signs;
`pluginkit -mvvv -p com.apple.background-asset-downloader-extension` should list
the extension; then a real download on a clean machine.

#### Folding it into the release machine

Once the pack downloads for real, this has to reach the build and deploy scripts,
their probes, and the docs that describe them. Surveyed 12 Sep 2026 — and the
second list is the useful half.

**Three of the four are done — 12 Sep 2026.** One remains, and it is the one
that cannot be built until the pack is hosted.

| where | what | state |
|---|---|---|
| `desktop/scripts/check-pkg-shippable.sh` | `die`s unless the app group is **present** on the MAS `.pkg` | ✅ **done.** The archive signs without it and BA then fails at runtime — a silent capability loss, so it dies rather than warns |
| `desktop/scripts/check-dmg-shippable.sh` | `fail`s if the app group is **present** on the Developer-ID `.app` | ✅ **done.** It read no entitlements at all before this; both channels share `Release`, so the split lived only in a `build-dmg.sh` override with nothing between a typo and a published image |
| `desktop/scripts/build-dmg.sh` | the `CODE_SIGN_ENTITLEMENTS` override | ✅ **already done** when the split landed — `:353`. This row claimed otherwise for half a day |
| `scripts/check-release-ready.sh` | the hosted pack is reachable **and** its SHA-256 matches the pin | ✅ **done**, and **not** blocked on hosting after all — see below |

**The pack row is tri-state, which is what let it be built before the pack
exists.** `REPORT-STYLE.md` Part 2 already says *no data* is a third state
rather than a failure, so `PII_PACK_URL` / `PII_PACK_SHA256` live empty in
`scripts/project.conf` and the row stays **silent** while they are — a standing
warning on every unrelated release is precisely how a gate teaches people to
scroll past it. It arms itself the moment the URL lands, and then reads:
unreachable → `bad`; reachable but unpinned → `warn` (its own hazard, not a
lesser reachable — without a pin a swapped artefact is undetectable); sha
matches → `ok`; sha differs → `bad`.

`tests/test_pii_pack_probe.py` **extracts the block out of the shell script and
runs it under bash with a stubbed `curl`**, so all five states are exercised as
logic rather than asserted as text — a grep would pass against a probe whose
comparison had been inverted. Both mutations were tried: inverting the sha test
reddens two cases, downgrading `unreachable` to a warning reddens one.

**Both entitlement probes scope to the `<key>` element, not the bare entitlement name** —
and that is load-bearing, not fastidiousness. Each plist carries a comment
*explaining* the split, and those comments contain the entitlement name, so
`grep -q 'com.apple.security.application-groups'` reports the group **present**
in the very file that omits it. Measured while writing the probes: the bare form
would have failed every clean `.dmg` build. `tests/test_entitlements_split.py`
now pins all three facts — each probe exists, each has the right severity
(`die` / `fail`, never `warn`), and neither greps the bare name — with each
assertion proved to bite by loosening the gate it guards.

**Already generic — needs nothing, which is the design working.**

- `check-pkg-shippable.sh`'s nested-executable loop asserts app-sandbox on *every*
  Mach-O of type executable. The `.appex` simply becomes the fifth, and if it is
  mis-entitled the existing gate says so. This is rejection class #1 from build
  2068 and it is already covered.
- `check-bundle-integrity.py` ran clean over the grown bundle — 287 Mach-Os, no
  holes — with no change.
- `check-sidecar-appstore-strings.py` was extended today and passes against the
  built artefact.
- `check-bundle-budget.py` is the **frontend JS** budget, not the sidecar. The
  sidecar's 479 → 512 MB is outside it entirely; do not "fix" that.
- `check-bundle-manifest.sh` is source→spec and stayed clean through the
  un-exclude.

**Docs to true at the same time.** `scripts/README.md` (the index of what to
type), `desktop/scripts/REPORT-STYLE.md` Part 2 (probe rules and exit codes — a
new probe must be tri-state, and *no data* is a third state, not a failure),
`docs/design-release-machine.md`, `docs/release-channels.md` (the pack is a sixth
artefact with its own staleness clock), and `docs/design-modularity.md`, whose PII
row still describes the parked wheel-archive delivery and prices presidio at
"~100 MB" against a measured 33.

#### Known operational risks, carried not solved

macOS is the rough edge: four live macOS-specific BA failures on Apple's forum tag
(mock-server override ignored, a 26.6.1 TLS regression against Apple hosting, an
App Review reviewer unable to fetch a pack, and an app-group fatal on the 27 seed).
Zynga's shipping report adds an exclusive-control lock that can hang, a 6 MB
extension memory ceiling, and scheduled downloads that silently never run. These
are operational rather than architectural, and the plain-HTTPS `.dmg` path is
unaffected by all of them.

### Stage 7 failure is fail-stop, and the Cause is privacy-safe (12 Sep 2026)

Route-independent — it holds whichever acquirer delivers the model — so it
landed before the BA work rather than behind it.

**The predicate is `any failure`, not `every attempt failed`.** Every sibling
stage (s08–s11) records a failure and carries on, because a partial analysis is
still worth something. Redaction is the exception: continuing would hand
unredacted participant speech to the language model and into the report, so a
9-of-10 success is a leak, not a partial success. `Pipeline.run`'s stage-7
block now wraps `remove_pii` and raises `PipelineAbandonedError`.

Before this, the block had **no handler at all**. That was fail-stop *by
accident* — the raise escaped to the run terminus, so nothing ever analysed
unredacted text — but it arrived as an unclassified crash the project row could
not render. The researcher read "the app broke" rather than "your redaction did
not run". What was missing was classification, not safety.

**The Cause is built with `_build_cause`, never `categorise_exception` — and
this is not a style preference.** `categorise_exception` puts `str(exc)`
straight into `cause.message`; `_build_cause` calls it for the *category* and
then composes the message from structured fields only. spaCy raises `E064` /
`E085` from `vocab.pyx` with the **looked-up token interpolated** — a
transcript word — and `cause.message` is persisted to `pipeline-events.jsonl`,
which is a named re-identification key alongside `pii_summary.txt` and
`llm-calls.jsonl`.

This is measured, not theorised. Swapping the handler to the obvious
`categorise_exception` makes
`test_pii_abandon_cause_never_carries_the_exception_text` fail with:

    AssertionError: participant token leaked into cause.message:
    "[E064] Error evaluating vocab for 'Aoife-Nic-Dhonnchadha'"

`categorise_exception` also grew a `PackageInstallError` arm → `MISSING_DEP`.
`FrozenSidecarError` subclasses it, so one arm covers both the sidecar refusing
to install and a CLI download that failed; both mean "the detector is missing",
which the desktop can route to a useful row, and `unknown` it cannot.

Three tests in `tests/test_pipeline_abandon.py`, each proved to bite by
mutating the live code back and confirming precisely the expected red set:
removing the wrap reddens the two pipeline tests; swapping in
`categorise_exception` reddens the privacy test; removing the classifier arm
reddens the classifier test. The assertion with the most teeth is
`segment_topics.call_count == 0` — a warn-and-continue would still leave a
green-looking run.

**No `pii` bucket on `PipelineSummary` — decided against, 12 Sep 2026.** The
buckets are `ingest, transcripts, topics, quotes, themes` on both sides
(verified at HEAD in `events.py` and `PipelineSummary.swift`); adding a sixth
is a wire-contract change — the Swift mirror plus a
`tests/fixtures/pipeline-summary-contract.json` version bump and a scenario
that *uses* the field, or the round-trip proves nothing about it.

It does not earn that, because **stage 7 abandons on any failure**. There is
therefore no partial redaction state for a bucket to describe: it could only
ever be absent, or `attempted=N, succeeded=0` with a single failure — which is
precisely what the `Cause` already carries in `stage="pii_removal"` plus its
category. A field that restates another field is drift waiting to happen.

**What would change the answer:** wanting to *surface* redaction on a
successful run — "47 entities across 12 sessions" on the project row. That is a
feature, not failure apparatus, and the settings mockup deliberately shows no
per-run redaction reporting (state E is a plain setting); the researcher's
record is `pii_summary.txt`. If that UI is ever wanted, the bucket is how to
carry it, and it should be added then with the mirror and fixture in the same
commit.

### Two defects the same seam exposed (12 Sep 2026)

Both fall out of `resolve_spacy_model()` existing: once the model can arrive as
a *directory* rather than a package, code that assumed the package form is
wrong, and code that never asked permission to fetch 425 MB is worse.

**1. The Pipeline view reported "model missing" on a working Mac.**
`pipeline_view/catalogue.py` declares the model as
`Requirement(kind="python_package", value="en_core_web_lg")`, and the probe in
`host.py` answered it with `importlib.util.find_spec`. That is the right
question for the CLI acquirer (`spacy download` installs an importable
package) and the wrong one for the `.dmg` and TestFlight acquirers, which
unpack a model *directory* and install no package at all. The view would have
offered to install something already on disk. The probe now routes through
`_spacy_model_present()`, which asks the same resolver stage 7 asks; a path
override failing its liveness check (`meta.json` + `config.cfg`) reads as
absent, because a model we cannot load is one that is not there.

**2. `--no-fetch` did not reach stage 7.** `_ensure_spacy_model()` took no
argument, so the flag never arrived and the stage downloaded 425 MB anyway —
the largest possible way to disobey "do not reach the network", and the one
heavyweight fetch in the pipeline that ignored a flag Whisper's preflight has
honoured since it was introduced. It now refuses with a `PackageInstallError`.

That type is deliberate rather than a bespoke abort class: a refused install is
what it is, `categorise_exception` already maps it to `MISSING_DEP`, and stage
7's handler turns it into a clean abandon with a privacy-safe Cause — so the
fix above and this one compose without new machinery. Both halves are pinned
separately (`tests/test_pii_spacy_lazy_fetch.py::TestNoFetchIsHonoured`),
because the helper can refuse perfectly and still download if the caller never
passes the flag, which is precisely what the defect was.

The new string `preflight.pii.aborted_no_fetch` is in all 21 full locales,
derived from each locale's own reviewed `whisper.aborted_no_fetch` — the
remedy sentence is identical, so only the subject changed. Machine-derived,
pending native review; `zh-Hant-HK` correctly absent (it inherits `zh-Hant`).

### The first-run fetch gets the terminal to itself (12 Sep 2026)

The CLI acquirer's own UX, and the last thing `_ensure_spacy_model` still owed.
Its docstring had flagged the framed-banner treatment as outstanding since the
size was corrected from 12 MB to ~400 MB — the house rule puts anything over
50 MB behind the framed banner Whisper uses. It turned out to be a correctness
fix as well as a presentational one.

`ensure_spacy_model` runs `subprocess.run([... spacy download ...],
check=True)` with **no capture**, so pip writes 425 MB of progress straight to
our stdout — while `Pipeline.run` holds a `console.status` spinner open across
the whole run. The old call printed with `end=""`, so pip's first line landed
on ours (`…one-off)...Collecting en-core-web-lg`) and the ✓ was orphaned after
pip's last line. Whisper met this first and answered it by stopping the
spinner for the duration — *"step aside, let HF Hub print natively"* — so
stage 7 now does the same: framed banner, `status.stop()`, download,
`status.start()` in a `finally` so one failed fetch does not leave the rest of
the run spinner-less.

`status` threads from `Pipeline.run` → `remove_pii` → `_init_presidio` →
`_ensure_spacy_model` as a keyword-only argument defaulting to `None`, so every
existing caller and test is unaffected. No new locale keys: the banner reuses
`preflight.pii.downloading`, and the done line carries the model name, which is
the register the terminal already uses for this model.

**Not verified in a real terminal.** Rich's `Live` does not render to a
non-TTY, so the spinner contention cannot be observed from a captured shell —
the fix rests on Whisper's identical, deliberate handling and on reading the
uncaptured `subprocess.run`. Three tests pin the mechanics (line terminated,
spinner stopped *during* the download, restarted even on failure) and all three
were proved to bite by restoring the `end=""` form. The thing still worth a
human's eyes is one bare-terminal run of a genuine first fetch.

**Unresolved, small:** `preflight.pii.downloading` says *~400 MB* in all 21
locales while the measured pack is 425 MB and the mockup says so. Correcting
`en` alone would fork it from twenty translations for a string that already
carries a `~`; left alone deliberately rather than overlooked.

### Where the pack is hosted — DECIDED 12 Sep 2026

**`bristlenose.app/models/…`, on the existing DreamHost shared plan**, extending
the apparatus that already serves the `.dmg` rather than standing up anything
new. `deploy.sh` gained `--filter='protect models/'` beside `protect dmg/`:
same shape — too large for git, uploaded out-of-band by `scp`, never present
locally, and wiped by `rsync --delete` without the rule.

**The scale question, answered with the right denominator.** 425 MB × 10,000
installs is 4.25 TB, which sounds alarming as a lump and is ~27 installs a day
— **11.6 GB/day, ~354 GB/month** — spread over a year. That is unremarkable
traffic for a product site, and 10,000 installs is a problem worth having.

**The AUP is about purpose, not volume.** DreamHost's Unlimited Policy restricts
sites whose *essential purpose* is to consume disk or bandwidth, naming file
sharing, archive, mirroring and distribution sites. A product site serving its
own installer and its own model is not one, which is the same basis on which the
`.dmg` has been served all along. Bandwidth is unmetered, so there is no bill to
run up; the exposure is a discretionary call at a scale where upgrading is easy.

**What is genuinely sticky, and the cheap insurance.** The URL is pinned in
`scripts/project.conf` and in Swift, so it ships inside released versions —
moving the bytes later does **not** migrate installed copies. So pin a *stable*
`bristlenose.app` path that can later 302 elsewhere, rather than one naming
where the bytes happen to live today. The SHA-256 pin makes a redirect safe by
construction: integrity is checked against the pin whatever origin serves it.
**Unverified:** whether Background Assets follows a cross-origin redirect. Plain
HTTPS on the `.dmg` route does; the BA route needs checking before the
indirection is relied on for both channels.

**Calibration if it ever must move**, at that same ~354 GB/month: DreamObjects
$0.05/GB ≈ $213/yr; Cloudflare R2 zero egress and 0.425 GB inside its 10 GB free
tier ≈ $0; GitHub Releases free, 2 GB per-file cap, which is what RawCull — the
prior art §"Prior art" tells you to read first — uses.

### Measured end to end on the shipped path — 12 Sep 2026

Everything above tests components. This ran the **planted-PII hour corpus**
through `remove_pii()` itself — the function `Pipeline.run` calls — scoring by
**surface absence from the output text**, which is what a researcher actually
sees. `experiments/pii_e2e_production_path.py`; 67 segments, 4.3 s, real
`en_core_web_lg`.

A note on the metric, because it changed a conclusion: an earlier harness
scored by *span overlap* in the analyzer results and read PHONE as 4/8 where
the end-to-end surface check read **2/8**. Overlap is the generous metric — a
detection that partly covers a planted span still leaves the surface in the
text. Score the output, not the detections.

**It found a real defect, and not in the direction the parked work assumed.**
Presidio's `PhoneRecognizer` scores a bare match **0.4** and only reaches ~0.75
when a context word ("call", "mobile") sits nearby; `pii_score_threshold` is
**0.7**. So a participant who simply reads their number out was **not
redacted** — 2 of 8 planted numbers removed. That is a *false negative* in a
privacy control. The false-positive tuning the user parked post-beta is a
different axis, and the less urgent one: an over-redaction is visible in the
transcript, a missed phone number is not.

**Fix: two bars, not one.** Pattern-matched entities (`PHONE_NUMBER`,
`EMAIL_ADDRESS`, `UK_NHS`, `CREDIT_CARD`, `IBAN_CODE`, `IP_ADDRESS`, the US
identifiers) take a 0.40 floor; PERSON keeps the configured 0.7, because PERSON
is the statistical recogniser and where over-firing destroys research data —
the same reasoning as `_ENTITY_MAP`'s LOCATION exclusion. `DATE_TIME` is
deliberately *not* relaxed: firing on "last Tuesday" is that same data
destruction. The floor may only ever relax a bar (`min()`), so lowering
`pii_score_threshold` still lowers everything rather than inverting below 0.4.

| | before | after |
|---|---|---|
| PERSON | 31/33 | **31/33** (unchanged, by design) |
| EMAIL | 4/6 | 4/6 |
| PHONE | **2/8** | **7/8** |
| ID | 3/5 | 3/5 |
| **total targeted** | 40/52 | **45/52** |
| false positives | 9/32 | **9/32** (unchanged) |

**The "false positives unchanged" row above is true and proves nothing about
this change** (found in the 12 Sep review). Every one of the corpus's 32
negatives is a *word* — product names, month names, sentence starts — and
**none contains a digit**. The bar was lowered only on number-shaped entities.
So the fixture was structurally incapable of showing a phone, NHS or card false
positive, and citing its unchanged count as evidence of safety was the
degenerate-fixture trap `CLAUDE.md` names. The evidence that *can* speak: 16
number-dense non-PII sentences (prices, dates, times, order numbers, version
strings, postcodes, SKUs, extensions, an internal IP) — the floor adds **one**
detection, `10.0.0.1` as `IP_ADDRESS`, which is a genuine IP. The weak sub-0.4
patterns on the US recognisers stay below the floor unless a context word
boosts them, and a boosted "account number" or "passport" match is PII anyway.
So the structural argument held; the corpus never tested it. Sixteen sentences
is a probe, not a corpus — a numeric-negative class belongs in the planted set.

**Known gaps, unchanged and honest:**

- **EMAIL spelled-out ×2** — "jane dot smith at example dot com". Not an email
  pattern, so Presidio cannot see it, and transcripts of *spoken* interviews
  are full of them. The most real of these gaps.
- **PERSON ×2** — a bare first name and one Arabic name. Model limits.
- **PHONE ×1** — an intl number libphonenumber rejects as invalid; Presidio
  returns nothing at all for it, at any threshold.
- **ID/dob ×2** — `DATE_TIME`, excluded above on purpose.
- **False positives: 9 of 32, every one a product name that is also a person
  name.** Exactly the prediction that motivated the post-beta per-project
  allow-list, now measured rather than assumed.

Pinned by `tests/test_pii_score_bar.py` — fast tests on the pure policy
(`score_bar`, `analysis_floor`) so a privacy decision is assertable without the
425 MB model, plus one `@pytest.mark.slow` end-to-end case whose sentence
carries **no** context word. Both go red when the bar is collapsed back to one.

### The path-delivered route is proven, not assumed — 12 Sep 2026

The `.dmg` and TestFlight acquirers unpack a model **directory** and set
`BRISTLENOSE_PII_MODEL_DIR`; `spacy download` never runs, so the importable
package does not exist on those machines. Everything built so far proved only
that `resolve_spacy_model()` *returns* the path. Nothing proved Presidio would
load and behave from one — and the place to discover otherwise is not
TestFlight.

Staged a faithful stand-in: the model directory copied **outside**
site-packages, `BRISTLENOSE_PII_MODEL_DIR` pointed at it, and the
`en_core_web_lg` package made **unimportable** via a `sys.meta_path` blocker,
because without that the installed package could be quietly doing the work.

**Identical results.** 45/52 targeted, 9/32 false positives, 92 redactions,
the same four misses, 4.2 s against 4.3 s. The delivery architecture's central
assumption holds.

Two things measured in passing:

- **The pack is 425 MB and contains zero `.py` files.** The §2.5.2 argument —
  that only *weights* are downloaded and the detection code ships inside the
  reviewed binary — is now measured rather than asserted, which is the form it
  needs to be in if a reviewer ever asks.
- **`SPACY_MODEL_SIZE_HUMAN` and `preflight.pii.downloading` both say ~400 MB
  against a measured 425.** Left alone: correcting `en` alone would fork it
  from twenty translations of a string that already carries a `~`. Noted rather
  than silently diverged.

Pinned by a `@pytest.mark.slow` case in `tests/test_pii_spacy_lazy_fetch.py`.
It bites hard: binding `_build_engines` to `SPACY_MODEL` instead of the
resolved path — the obvious "simplification" — fails it with
`ModuleNotFoundError`, which is exactly the TestFlight failure it exists to
pre-empt.

### `doctor` was misdiagnosing a bad model directory — 12 Sep 2026

Found by asking the third surface the same question the other two now answer.
`resolve_spacy_model()` raises `ValueError` when `BRISTLENOSE_PII_MODEL_DIR`
does not name a loadable model directory — a half-unpacked pack, or a path
aimed one level too high. In `check_pii` that landed in the bare
`except Exception` arm and came back as **"spaCy not compatible (Python
3.14+)"**.

Wrong in the worst possible place: `doctor` is the tool a confused user runs,
and on a `.dmg` or TestFlight machine the path route is the **only** route —
`spacy download` never runs there — so this is the message that whole class of
user would get. The resolver's own text already names the variable, the path
and the two files it wants; it was simply being thrown away.

Now caught before the generic arm, with a dedicated `pii_model_dir_invalid`
fix rather than the install-oriented `spacy_model_missing` one — recommending
`spacy download` here would be actively misleading, since nothing needs
installing and the model may well be present and merely pointed at from the
wrong level.

Fixed in the same pass: `check_pii` called `spacy.load()` **twice**, once to
probe and once for the version string. On `lg` that is 425 MB read twice to
learn "3.8.0".

Pinned in `tests/test_doctor.py` — the detail names the variable, the fix key
routes to the env-var fix, and the fix text does not say `spacy download`. All
three redden when the arm is reverted to the old message.

### Rigorous review — 12 Sep 2026, on switching model

A second pass over everything the day built, asking the running system rather
than the record. Findings in severity order; each names what was done about it.

**1. Re-analysing with redaction on did not replace the served text — FIXED.**
`_import_transcript_segments` skipped any session that already had rows. So:
analyse without redaction → raw text imported → switch it on → re-analyse →
`transcripts-cooked/` lands, `pii_summary.txt` lands, `status` says redaction
ran — and the report, the export and the MCP endpoint keep the original words.
The `words_json` remediation had patched exactly this hole for the timing data
and left the text; its own comment says the skip is why. Pre-existing, but the
day's work made the flow reachable and the chain was called "fully witnessed"
on the strength of a `_find_transcripts_dir` precedence test that never asked
what the rows said afterwards. Now: when the source is `transcripts-cooked/`
and rows exist, they are deleted and reinserted (nothing holds a segment's id;
`quotes` join on `(session_id, segment_index)`, which regenerates identically
because cooked is a one-for-one copy of raw; a fresh row has
`words_json = None`, as a redacted row must). Raw-over-raw keeps the skip. Real
SQLite test, proved red against the skip.

**2. The two-bar threshold's evidence was invalid; the change survives on
better evidence.** See the corrected note under "Measured end to end" — zero
of 32 negatives contain a digit. Re-measured on 16 number-dense sentences: +1
detection, a genuine IP. Recorded rather than reverted.

**3. The pack probe pulled 425 MB per preflight and mistook a slow network for
tampering — FIXED.** `release.sh` runs preflight in `plan` *and* `run`; under
`--max-time` a partial-file hash read as MISMATCH → `bad` → release blocked as
a supply-chain event. Now HEAD + a `.sha256` sidecar beside the pack, never the
body; a served value that is not 64 hex chars (a 404 page through `awk`) is
"no sidecar", never "wrong sha". The stub trips on any body request. **The
sidecar is not the security boundary** — whoever can swap the pack can swap it —
it catches the operational failure (re-uploaded pack, un-updated pin). Byte
integrity is the client's job at acquisition, against the compiled-in pin.
**Operator contract: upload `<pack>` and `<pack>.sha256` together.**

**4. The frozen sidecar announced a download it could not start — FIXED.** The
framed banner printed one call before `FrozenSidecarError`, and that line
reaches "Copy error details". Frozen now skips straight to the refusal.

**5. Managed Background Assets — one alarm, retracted.** An early grep matched
`public var` and missed `public func url(for path:) throws -> URL`
(`AssetPackManager`, macOS 26 SDK line 103). The path-handoff architecture
holds on the API. **Still unverified, and only a real download can verify it:**
whether the `inherit`-sandboxed sidecar can read wherever that URL points.
Named as the one runtime assumption under the TestFlight route.

**6. Test-honesty audit of the day's own claims.** "Every new test proved to
bite" was true of the mutations tried, which is a weaker statement than it
read. `test_pii_score_bar.py`: 16 fast tests; one bit under the collapse-to-one-
bar mutation; three further mutations (raise the floor, relax `DATE_TIME`,
add an unmapped entity) redden 4, 1 and 1 — so the file is a property suite
whose load-bearing members bite, not sixteen independent witnesses. The Swift
handoff had not been mutation-tested at all; gating the flag on pack presence
now reddens exactly `enabledWithoutPackStillFlags()`, which is the asymmetry
the type exists for. The pack probe's silent-when-unset case is also proved.

**7. Pre-existing edge, noted not fixed.** Stage 6 always writes
`transcripts-raw/`. After a stage-7 abandon on a project's *first* run, raw
exists and cooked does not; a serve started on that project imports raw. The
SPA is gated on `run_completed` so the report does not show it, and
`run_failed` triggers no re-import — but MCP and export read the DB. Not new
(the fallback predates today), not a regression (an unwrapped raise reached the
same state), and the files are already on the user's own disk unredacted. Worth
a decision at the Privacy pane: a failed redaction run could delete its raw
output, or the importer could refuse raw when `pii_enabled` is on.

**8. Inert but worth knowing.** `BRISTLENOSE_PII_ENABLED` is now injected into
*serve* spawns as well as `run`; nothing in `server/*.py` reads it. Harmless.

### Stage 7 speaks to the sidebar and the estimator — 12 Sep 2026

Asked directly — *does redaction send messages to the status line, and is its
time in the estimate and the ring?* — the answer was **no** on both, and the
Swift file said why in its own comment: the estimator "folds PII into its
neighbours and never emits it as a progress stage". Reasonable while it ran for
nobody; wrong the day it became a Mac feature. The sidebar showed the previous
stage frozen through the model load and the redaction pass (on the CLI's first
run, through a 425 MB download), and every warm prediction was short by PII's
duration because the six-stage total never contained it.

**The fix is pure reuse — no new mechanism.** Every stage talks through six
channels; stage 7 already used the three CLI-facing ones (`status.update`,
`_print_step`, the manifest) and lacked the two shared with the desktop. It now
makes the *same two calls* every sibling makes — `_emit_stage_entry(STAGE_PII)`
on entry, `_stage_actuals[STAGE_PII]` + `_emit_remaining` on exit — keyed on a
new id in the vocabulary those calls already use: `timing.py STAGE_PII = "pii"`,
in `ALL_STAGES` after `speakers` and in `_SESSION_STAGES` (it is per-transcript);
Swift's `knownStages` mirror; the locale verb `chrome.pipeline.stage.pii` in all
21 locales (en: *Redacting personal information*; the rest machine-seeded in
each locale's own stage-verb register, pending native review).

**It is a conditional stage, and that is the only subtlety.** `initial_estimate`
takes `pii_enabled` on the `skip_transcription` precedent and skips it when off;
`stage_completed` skips it too — without that, a disabled PII would be counted
as *remaining* until the run ended and inflate every ETA. An old `timing.json`
with no `pii` profile degrades gracefully: `_estimate_stage` returns `0, 0` for
a stage without history and `has_history` is `any()`, so a warm estimator stays
warm and simply learns PII's rate over its first four redacted runs.

Pinned three ways: the pipeline-level test drives `Pipeline.run` to stage 7 with
a succeeding redaction and asserts the sink saw `stage == "pii"` and the
estimator was told it completed; `knownStages == ALL_STAGES` is now a
**Python-side** cross-language test, because the Swift copy is ungated by CI and
an id missing on the Swift side is exactly how this shipped invisible; and the
timing suite covers order, session scaling, both conditional skips, and the
old-profile case.

### Build order

Phases 0–2 are independent of Background Assets and can land immediately; the
UX for phases 3–4 is specced in `docs/mockups/mockup-privacy-settings.html` §1b.

- **Phase 0 — reconcile the model. ✅ DONE 12 Sep 2026.** `_SPACY_MODEL` was
  `en_core_web_sm` and vestigial: a bare `AnalyzerEngine()` took Presidio's
  default, so we fetched 12 MB and silently pulled 400. It is now `en_core_web_lg`
  and `_build_engines` binds the analyzer to it via `NlpEngineProvider`, so
  fetched == used. The `preflight.pii.downloading` string said "~12 MB" and now
  states the real size. **The three items this bullet listed as owed are all
  done, verified at HEAD 12 Sep 2026** — and the bullet went on claiming them,
  which is the trap this repo already documents: an owed item is a claim about
  the tree exactly as a resolved one is. Measured: **zero** locales still say
  12 MB (all 21 carry the corrected string), **zero** occurrences of
  `en_core_web_sm` remain in `doctor.py` or `doctor_fixes.py`, and the model
  name does now have one shared constant — `SPACY_MODEL` plus
  `resolve_spacy_model()`, which every consumer routes through. The only
  surviving `en_core_web_sm` strings in the tree are `tests/test_package_install.py`,
  where the name is an arbitrary argument proving `ensure_spacy_model` is
  model-agnostic, and a past-tense comment in `s07_pii_removal.py` explaining
  why the constant is public. Both are correct as they stand.
- **Phase 1 — the BA spike.** A throwaway target with the App Group entitlement,
  **no extension**, one `scheduleDownload:` of a small self-hosted file. Does it
  transfer, or return `BAErrorCodeCallerConnectionNotAccepted` (55) /
  `…ConnectionInvalid` (56)? Everything below is contingent on this. Half a day.
- **Phase 2 — the failure apparatus. ✅ DONE 12 Sep 2026.** Stage 7 wraps
  `remove_pii` and abandons on **any** failure (not `succeeded == 0` — a 9-of-10
  predicate would let one unredacted transcript through), with a Cause built by
  `_build_cause` so no `str(exc)` reaches `pipeline-events.jsonl`.
  `categorise_exception` grew one `PackageInstallError` arm, which covers
  `FrozenSidecarError` too. See §"Stage 7 failure is fail-stop". The plan was
  right that this, not the toggle, was the real work.
- **Phase 3 — bundle the code. ✅ DONE 12 Sep 2026.** `presidio_analyzer`,
  `presidio_anonymizer` and `spacy` are out of `excludes` in
  `desktop/bristlenose-sidecar.spec`; `en_core_web_lg` stays out. Verified on a
  real artefact: 479 → 512 MB, 224 → 287 Mach-Os, integrity clean, the App Store
  string gate clean, presidio importing from the frozen sidecar, model correctly
  absent. Remaining from this phase: Re-run `check-bundle-manifest.sh` and
  `check-bundle-integrity.py`, and re-verify Privacy Manifest required-reason
  coverage against the *actual* bundle `.so`, not the dev venv.
- **Phase 4a — the Swift handoff. ✅ DONE 12 Sep 2026.** `PIIModelPack.swift`
  turns app state into the sidecar's environment, merged in
  `BristlenoseShared.childEnvironment` beside the SSL and ffmpeg blocks. The
  asymmetry between its two variables settles Open Decision 1 below in favour of
  failing cleanly: **`BRISTLENOSE_PII_ENABLED` travels even with no pack**
  (withholding it means the researcher asked for redaction and quietly did not
  get it — stage 7 abandons with `MISSING_DEP` instead), while
  **`BRISTLENOSE_PII_MODEL_DIR` travels only when a loadable pack is present**,
  liveness-checked against the same `meta.json` + `config.cfg` pair Python uses.
  `env_prefix = "BRISTLENOSE_"` is what carries the flag to `pii_enabled`, and
  that is asserted rather than assumed. Cross-language drift is gated from the
  **Python** side (`tests/test_swift_python_contract.py`), because pytest is the
  only suite CI runs — a typo'd variable name is otherwise silent: the pack is
  acquired and never found, and Presidio falls back to `pip install` from
  GitHub.
- **Phase 4b — the acquirers + Privacy tab. ⬜ THE REMAINING WORK.**
  The storage seam under them is built: both acquirers converge on **one
  UserDefaults key, `piiModelPackDirectory`**, holding the loadable inner
  directory's path — managed Background Assets stores `url(for:).path` after
  `ensureLocalAvailability`, the `.dmg` stores its unpack destination — so the
  spawn-time handoff stays synchronous (the BA calls are `async throws`;
  `childEnvironment` is not) and asks one question of one key. Liveness is
  checked at handoff, not at storage, so a pack the system reclaims under
  storage pressure yields the flag alone and the run fails loudly. Until an
  acquirer writes the key, nothing does, and the answer is `nil` everywhere.
  **The managed-route calls, verified against the SDK rather than remembered**
  (`AssetPackManager` is an actor; every call is awaited on it):
    1. `let pack = try await AssetPackManager.shared.assetPack(withID: id)`
    2. `if #available(macOS 26.4, *) { try await manager.ensureLocalAvailability(of: pack, requireLatestVersion: false) } else { try await manager.ensureLocalAvailability(of: pack) }`
    3. Present? `AssetPack.Status` is an `OptionSet` — `status.contains(.downloaded)`
       (26.4: `status(relativeTo: pack)`; before: `status(ofAssetPackWithID:)`).
    4. `let dir = try manager.url(for: FilePath("<model dir inside the pack>"))` —
       **the argument is the pack's internal layout, a hosting decision not yet
       made** (for `en_core_web_lg` the loadable directory is the inner
       `en_core_web_lg-<version>/`, so the pack should carry it at a known
       relative path).
    5. `UserDefaults.standard.set(dir.path, forKey: PIIModelPack.packDirectoryDefaultsKey)`
       — the handoff does the rest, liveness included.
  The `.appex` adopts `ManagedDownloaderExtension` (which refines
  `BADownloaderExtension`); RawCull's is one line. **The one runtime unknown**,
  answerable only by a real download: whether the `inherit`-sandboxed sidecar
  can read the directory `url(for:)` returns.
  Everything downstream is built and proven: set
  `BRISTLENOSE_PII_MODEL_DIR` (that is the real variable — this bullet said
  `BRISTLENOSE_PII_LIB_DIR`, which exists nowhere) and stage 7, `doctor` and the
  Pipeline view all behave, measured identically to the package route with the
  package made unimportable. **Nothing writes that variable and nothing fetches
  the pack.** That is the gap, and it is Swift:
    - the **managed** `AssetPackManager.ensureLocalAvailabilityOfAssetPack` plus
      a `ManagedDownloaderExtension` — *not* `BAURLDownload`, which the macOS 26
      gate deleted from the plan along with the hand-written extension;
    - `PrivacySettingsView` with the mockup's six states (A–E plus F, the
      below-26 disabled row);
    - `piiEnabled` in UserDefaults → `env["BRISTLENOSE_PII_ENABLED"]` and the
      resolved pack path → `env["BRISTLENOSE_PII_MODEL_DIR"]`, both in
      `BristlenoseShared.swift`.
  **Do not build the toggle before the acquirer.** Below macOS 26 it correctly
  reads *"Requires macOS 26 Tahoe or later"*, which promises that upgrading
  delivers the feature — a promise nothing can keep until this phase lands.
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
2. ~~**Engine choice is still open.**~~ **CLOSED 12 Sep 2026 — Presidio.** The
   user's call: *"I'd rather deal with this as a packaging challenge than a
   start-again DIY problem."* See §"Roll our own PII — REJECTED". The original
   argument is preserved there. Kept struck rather than deleted because it was
   a live decision for six weeks and its reasoning is why the split exists:
   roll-our-own would have deleted 425 MB, the native code, the
   App Store question and the hardcoded `language="en"` — and is better on exactly
   the non-Western names `lg` is bought for. The `sm` hedge this bullet used to
   propose (bundle the 15 MB model so the toggle works instantly, `lg` as an
   optional upgrade) is **dead** — *"we need `lg` to offer the feature for real;
   `sm` was only ever a test-the-plumbing job"*. The hour corpus measured the
   difference: PERSON 23/33 on `sm` against 31/33 on `lg`, with `lg` winning on
   exactly the nicknames, South-Asian and hyphenated names the hedge would have
   shipped without.


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

## Appendix A — the RETIRED wheel-archive delivery

> **Historical twice over, and neither reason is the one this line used to
> give.** It said *"preserved so it can be rehydrated if the LLM route doesn't
> pan out"* — but the LLM route (roll-our-own) is **rejected**, so there is
> nothing to fall back from; and the delivery described below was **retired by
> measurement** on 12 Sep 2026, not parked. Shipping presidio + spaCy as
> Python-packages-as-data, unpacked to Application Support with a `sys.path`
> extension at sidecar startup, was designed for a ~100 MB dependency that
> measured **33 MB** in the built sidecar. Bundling the code is simpler and
> costs less than the startup hook it replaces; only the 425 MB *model* is
> acquired, and a model is data.
>
> Kept because the §2.5.2 reasoning below is still the argument an App Store
> reviewer would have to be answered with, and because `BRISTLENOSE_PII_LIB_DIR`
> appears here — a variable that never existed in code, and which the build
> order cited by mistake until today. The real one is
> `BRISTLENOSE_PII_MODEL_DIR`.

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
