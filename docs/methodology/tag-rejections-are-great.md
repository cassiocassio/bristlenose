# Tag rejections are great

*A methodology note for Bristlenose alpha. Pre-beta draft. Expected to evolve.*

> **Implementation status — 26 Apr 2026.** Phase 1 plumbing has shipped (`/api/health` advertises the telemetry endpoint, `/api/dev/telemetry` stub mounted in `--dev`, `telemetry.php` ready in the separate `bristlenose-website` private repo, deployed to bristlenose.app on 2 May 2026 but not yet receiving real events; merge commit `c5a7f61`). The full Level 0 collection described below — Python ingestion + SQLite buffer + batched shipper, React emission hook, Swift opt-in sheet + Keychain UUID + Settings → Privacy — is **deliberately deferred to post-TestFlight**. TestFlight tester feedback comes from video-call UX sessions, not instrumented data; pushing through the remaining work was pushing the TestFlight runway. The doc below remains accurate as the *plan*, with the qualifier that no researcher events have yet been collected. Resume context: [`docs/private/alpha-telemetry-next-session-prompt.md`](../private/alpha-telemetry-next-session-prompt.md). Tracking: [`100days.md`](../private/100days.md) §1 Must, `road-to-alpha.md` §13b.

## Why this doc exists

This captures the thinking behind using tag-rejection signal as Bristlenose's first piece of telemetry and its first mechanism for improving prompt quality. It's written at the pre-alpha stage as a design note, not a spec. It proposes a small set of experiments that can run on testflight alpha builds without new infrastructure — just a bit of event logging and some offline analysis — and sketches what we'd expect to learn from them.

The underlying claim is that tag rejection is the cheapest, highest-quality, most ethically defensible signal we can collect right now about whether our prompts are any good. It's worth instrumenting before anything else.

## The core claim

Every time Bristlenose suggests a tag and a researcher rejects it, that's a small act of human judgement against a machine proposal. Aggregated across enough sessions, those judgements tell us which of our tag prompts are working and which aren't. Not *why* they aren't — that's the next layer of signal — but clearly enough to tell us where to look.

The claim has three parts. Rejection is higher-quality signal than acceptance, because acceptance is often default-behaviour and rejection requires effort. Rejection rate per tag per prompt version is the minimum useful aggregate: it's enough to triage our attention without needing any content from the quote itself. And at alpha scale — a handful of researchers across maybe 20 hours of coded sessions — the signal is already strong enough to drive useful hand-tuning of prompts, without any ML infrastructure.

## Why rejection beats acceptance as signal

Accepting a suggested tag is a weak positive. Researchers working through an afternoon of transcripts will accept things that look roughly right; fatigue biases acceptance upward. Rejection is a stronger negative, because rejecting a suggested tag requires the researcher to notice, form a judgement, and act against the default. The effort threshold for rejection is higher, and that means rejections carry more information per event.

This asymmetry suggests a small design implication even before we start collecting data: we shouldn't make acceptance frictionless if we can help it. A confirm tap for acceptance, rather than a tag that's already ticked, costs the researcher a small effort and raises the quality of every acceptance event we log. Worth doing; not urgent.

## What rejection rate tells you, and what it doesn't

Rejection rate is an attention heuristic, not a diagnosis. A tag with 8% rejection probably doesn't need our attention this week. A tag with 45% rejection does. But 45% doesn't tell us *why* — the tag concept might be genuinely ambiguous, the prompt might be badly operationalised, or researchers might be reaching for it outside its intended scope. All three are interesting findings, and we can't distinguish them from the rate alone. We have to go look.

A few caveats to keep in mind when reading rejection data:

Low rejection rate isn't automatically good. It might mean the prompt is well-calibrated; it might mean the tag is being rubber-stamped. Cross-referencing with application rate helps: a tag that gets applied rarely but accepted every time is different from one that gets applied constantly and accepted every time.

High rejection rate isn't automatically bad either. Some tag concepts are genuinely harder than others. "Usability problem" will always have more edge cases than "participant quote about pricing."

Researcher-level variance matters. One researcher who rejects everything by default will pull up the rejection rate on every tag they touch. Once we have enough data, rates should be controlled for researcher before drawing conclusions.

Study-level variance matters when N is small. A single study with an unusual population can skew a tag's rate noticeably when we only have 20 hours of sessions total. Report ranges, not point estimates, and be patient.

## Minimum data model for alpha

Four fields per event. Nothing else.

| Field | Notes |
|---|---|
| `tag_id` | The tag suggested (codebook entry, not applied-tag instance) |
| `prompt_version` | A string we bump manually when we edit the prompt |
| `event_type` | `suggested`, `accepted`, `rejected`, or `edited` |
| `researcher_id` | Random UUID minted at first launch, stored in the macOS keychain under a Bristlenose-scoped key, rotatable by the tester via a Settings → Reset telemetry ID control. Pseudonymous, not anonymous — the alpha cohort is a handful of people we know personally via TestFlight, so we will often know from context which UUID maps to which tester, and the T&Cs say so rather than pretending otherwise. No server-side table maps UUIDs to Apple ID, email, or StoreKit identity, even once IAP is in the same app. |

No quote content. No participant data. No reason. No transcript excerpt. No timestamp, no study identifier — both carry re-identification risk (timestamp leaks session cadence and working hours; a study identifier combined with a researcher's public posts becomes a pointer to a client). Dropping them costs very little at alpha scale and makes the data genuinely minimal.

This constraint is non-negotiable at alpha. It's what makes the T&Cs clean and the whole exercise ethically straightforward.

The `edited` event type is worth distinguishing from accept and reject. It captures "right tag, wrong boundaries" — the researcher thinks the tag applies but adjusted the selected quote span. That's a subtler signal about prompt quality than flat accept/reject and may turn out to be more informative than either. Important: `edited` is a flag on the event, not a payload — we record *that* the researcher adjusted the span, never the offsets or length of the adjustment. Character offsets plus transcript length would leak where the interesting content sits, which is exactly the kind of re-identification vector the minimal-field discipline exists to prevent.

## Alpha experiments

One experiment at alpha. Everything else we might learn is noticed along the way, not instrumented.

**Experiment 1: Rank tags by success rate.**

`success_rate(tag) = (accepted + edited) / suggested`

Drop tags with `suggested < 10` as below-ranking-threshold. Edited counts as success — the researcher agreed with the concept, disagreed on the span. Ignored = `suggested − (accepted + rejected + edited)`; counts as failure. Report a single table sorted ascending. Bottom of the table is the attention list.

Error bars are wide at alpha scale. Say so in prose rather than imply false precision by reporting rates to two decimal places.

**Follow-on (not an experiment): hand-tune the bottom three.**

Read those prompts. Read textbook definitions of what the tag is meant to capture. Read out-of-band samples of rejected quotes (separately, with explicit researcher permission — not from the telemetry stream). Rewrite inclusion/exclusion criteria. Hash changes naturally because the prompt text changed. Ship v2.

No before/after rejection-rate claim at this cohort size — 10 testers × 1 hour is too small to measure a prompt-rewrite effect cleanly. The next cohort tells us whether we were right.

**Things we'll notice along the way** (not first-class experiments):

- Researcher-level variance — one tester who rejects everything pulls rates up across every tag they touch. We'll see it in the per-researcher breakdown and handle it by conversation, not by statistics.
- Informal "why" — for the bottom three tags, we'll just ask on Slack. No structured reason taxonomy at Level 0.
- Rubber-stamping signal — a tag applied constantly with near-100% acceptance is different from one applied rarely with near-100% acceptance. Cross-reference with application rate when reading the table.

The only engineering required is the event-logging hook, the batched POST endpoint, and a CSV export.

## Consent and T&Cs for alpha

Alpha is TestFlight-only. Every tester is someone we have personally invited and who has agreed to the alpha T&Cs. Telemetry is **opt-in**: at first launch the tester sees a one-click "yes, help improve Bristlenose" explanation with a plain-English summary visible before the toggle. The toggle is never pre-ticked. This matches the consent-gradient doc's Principle 1 (professional norms, not tech norms) and is what makes Level 0 defensible under UK GDPR Article 6 without needing to lean on legitimate-interests-from-a-paid-tool, which would be thin.

Telemetry at alpha is a **time-boxed exception** to Bristlenose's broader "nothing leaves your laptop" posture. The exception is justified by the narrow content (no participant data, no quote text, no study identifier), the narrow audience (a handful of knowing testers), and the narrow purpose (improving code-suggestion prompts — see the consent gradient doc's §Purpose limitation). It has an explicit sunset: at public beta, Level 0 telemetry moves from "opt-in at first launch for TestFlight testers" to "opt-in at first launch for anyone who wants to help improve the tool, with the same one-click control." The exception is not a stalking horse for SaaS-style always-on telemetry; the security and privacy docs (`SECURITY.md`) are updated in the same change that introduces the logging hook, so the public posture stays accurate.

Proposed T&C clause, in plain English:

> When you turn on "help improve Bristlenose," we log when you accept, reject, or edit the codes it suggests, along with a code identifier and a prompt version. We use this to improve the quality of code suggestions — we do not use it to train general-purpose AI models, and we will tell you in plain English if that ever changes (it would require fresh consent under a new purpose). We do not log the content of quotes, any participant data, any study or client identifier, any timestamp, or any reason you might have for your decisions. Events are tied to a random identifier stored on your device that you can reset at any time from Settings. The alpha cohort is small and we know who you are; we don't pretend otherwise. You can turn telemetry off at any time from the same Settings screen, and you can ask us to delete your logged events by contacting us.

What's explicitly *excluded* from alpha data collection, and should remain excluded until beta consent architecture is built:

- Any content from the quote itself
- Any identifying information about the participant
- Any identifying information about the study (client, product, sector)
- Any free-text or structured reason for a decision
- Any data from non-alpha users

These exclusions aren't just legal hygiene; they're a commitment to the data-governance posture we want Bristlenose to be known for. Getting the minimal telemetry working well and transparently is how we earn the right to ask for more later.

## The opt-in flow

The consent UX is where the T&C becomes a real commitment rather than a paragraph nobody reads. Two surfaces: a first-launch sheet, and a persistent Settings control.

### First-launch sheets

Two sheets, shown in sequence at first launch. Sheet 1 is the App-Store-mandatory AI disclosure (not optional, not skippable). Sheet 2 is the telemetry opt-in. Together, under 80 words of body copy.

**Sheet 1 — AI disclosure.** Mandatory acknowledgement.

> **Bristlenose uses AI to analyse your interviews**
>
> Your audio and transcripts are sent to the AI provider you choose — Claude, ChatGPT, Gemini, or Azure — for processing. Everything else stays on this Mac.
>
> [ I understand ]

**Sheet 2 — Telemetry opt-in.** Optional; off if dismissed.

> **Help improve auto-tagging?**
>
> When we suggest a tag and you accept or reject it, we can send back the tag name and your decision. Nothing from the interview itself.
>
> You can change this in Settings any time.
>
> [ Sure ]    [ Not now ]

Design rules:

- **Sheet 1 has one button.** It's an acknowledgement required by the App Store, not a choice.
- **Sheet 2's buttons have equal visual weight.** Neither is primary-highlighted.
- **"Not now," not "No thanks."** It's reversible in Settings, and the copy says so.
- **Sheets are sequential, not combined.** Keeps the mandatory ack and the optional consent legally and cognitively separate — bundling them risks GDPR Recital 43 issues on consent specificity.
- **No scroll-gating, no "learn more."** If it doesn't fit on the sheet, it's not on the sheet.
- **No telemetry emits before sheet 2 is answered.** Dismissing = off.

### Settings control

Under Settings → Privacy:

- Toggle: "Help improve auto-tagging"
- Tester ID (greyed monospace, Reset button)
- "Delete my events" — opens a prefilled email

Email-driven deletion and SAR are fine at alpha scale; in-product versions land for beta when the cohort is strangers.

### Settings control

Live under Settings → Privacy, always visible regardless of first-launch choice. Shows four things:

1. A toggle: "Help improve Bristlenose's code suggestions" (on/off). Off by default until the tester turns it on via the sheet or here.
2. The tester's current random ID, in a greyed-out monospace field, with a "Reset" button. Reset mints a new UUID; past events retain the old ID until the tester asks us to delete them.
3. A "What we send" link that opens the same plain-English explanation as the sheet, so the commitment is reachable at any time, not just on first launch.
4. A "Delete my events" button. Opens a prefilled email to the alpha address with the tester's current ID; we do the deletion on receipt and confirm. (Full in-product deletion is a beta-era feature; email-driven is fine for a cohort of ~10 people.)

Design rules for Settings:

- **The toggle reflects reality, not intent.** Flipping it off stops the next event from logging and stops the next batch from shipping. Events already buffered on disk are flushed on the next ship if opt-in was true at the time they were logged; events logged while opt-in is false never leave the device.
- **Resetting the ID doesn't delete past events.** The copy next to Reset says so. Reset breaks the link going forward; deletion is a separate action.
- **Changing the toggle mid-session is honoured immediately, no restart required.**

### What's deferred to beta

- In-product "download my events" (Article 15 SAR). Alpha handles this via email.
- In-product "delete my events" (Article 17). Alpha handles this via email.
- Per-study opt-in toggles. Alpha is whole-cohort opt-in only; per-study granularity arrives with Level 1 at beta.
- Team/org-level consent. Alpha testers are individuals.
- Consent-renewal UX for prompt-version or purpose changes. Alpha changes the prompts frequently but not the purpose; renewal UX lands when the purpose could plausibly drift (i.e. before Level 1).

## What we can realistically learn from a tiny cohort

A handful of researchers across 20 hours of coded sessions, applied to a codebook of roughly 15 tags, is probably 1,000 to 3,000 tag-application events. That's not much by ML standards, but it's plenty for what we actually need at this stage.

With that volume we should be able to rank tags by rejection rate with meaningful separation between the best and worst. We should be able to identify the two or three prompts that most need attention, hand-tune them, and see whether v2 performs better. We should be able to spot researcher-level outliers and decide whether variance is a first-order concern. And we should be able to collect enough informal "why" data on the worst tags to preview the shape of a structured reason taxonomy for beta.

What we can't do at this scale: statistical inference, subtle prompt-variant comparison, or anything resembling a training pipeline. That's fine. The point at alpha is demonstrating the mechanism, not producing generalisable findings.

Even the demonstration has value beyond Bristlenose itself. "Here are the rejection rates for each code in the UXR codebook as applied across 20 hours of real usability work by professional researchers" is a set of numbers the field does not currently have. It's the kind of empirical observation about qualitative methodology that nobody has been instrumented to collect. That's the seed of a Substack piece, and over time the kind of data that supports an evidence-based refinement of the codebook.

## What success looks like at end of alpha

Alpha is an experiment about whether this signal is worth collecting, not a guarantee it will move prompts. The cohort may be too small and the signal too noisy to meaningfully improve prompts on its own. That's fine — we'll combine the quant signal with qualitative feedback from the testers we know personally, and decide then whether to act on any given tag. It would be silly *not* to collect the basics of tag rejection as we go; the cost is tiny and the optionality is real.

By the end of the alpha window, we should have:

- A success-rate number for every tag in the UXR codebook that cleared the `suggested ≥ 10` threshold, based on real researcher behaviour
- The bottom of that table identified as the attention list, with hand-tuned v2 prompts shipped for (some of) them — hashed, logged, ready for the next cohort to evaluate
- Informal notes from researchers on why they rejected the bottom three tags, gathered over Slack or a call
- A qualitative view on whether researcher-level variance is a first-order concern for data interpretation
- Enough confidence in the mechanism to design and scope the Level 1 capture (structured reasons) for beta
- At least one publishable observation about how the UXR codebook performs operationally

What we explicitly aren't promising: a clean before/after demonstration that v2 prompts reduced rejection. The cohort is too small and the noise floor too high to make that claim honestly at alpha scale. The next cohort tells us whether the hand-tuning worked.

That set is enough to justify the data architecture for beta, to write a first Substack piece that establishes Bristlenose's methodological posture publicly, and to make a concrete case to researchers about why contributing this data benefits them.

## Out of scope for this doc

The following are real questions but belong in other notes:

- The consent architecture for Level 1+ data (quote excerpts, structured reasons) at beta and beyond — see the separate consent-gradient design note.
- PII scrubbing for researcher free-text — needed before any free-text capture; prototype separately.
- Cross-study rejection analysis, which only becomes meaningful with much more data than alpha will generate.
- Exposing rejection rates back to researchers as a product feature. At alpha, keep the data internal; it's for us to act on, not yet for them to see.
- The broader framework emergence question — whether the accumulated corpus eventually supports a novel framework distilled from practice. That's a ten-year arc; this doc is a six-month instrument.

## One thing worth doing before any of this

Before shipping the logging hook, commit to the prompt-version derivation. A manual `{tag_id}-v{n}` string is trivially corruptible: a forgotten bump silently mixes v1 and v2 data and quietly invalidates every rate calculation that reads across the boundary. Instead, derive the version as `{tag_id}-{sha256(prompt_text)[:8]}` — a short content hash of the prompt markdown. Version strings are generated automatically at event-emit time from the current prompt file, so they can't drift from the prompt text they describe. A sidecar file (`prompts/versions.jsonl`) records each hash the first time it's seen along with the prompt text at that point, so the full text of every version that has ever produced events is recoverable after the fact for auditing and for Experiment 2's before/after comparison.

Other prerequisites worth naming so they don't get improvised:

- **Storage.** Alpha events land in a SQLite table in Bristlenose's existing on-device database, then ship batched (not per-event) to `https://bristlenose.app/telemetry.php` — a small PHP endpoint on DreamHost shared hosting, patterned on the existing `feedback.php`, appending one row per event to `data/telemetry.csv`. No third-party analytics service, no hosted LLM in the telemetry path.
- **Offline behaviour.** If the endpoint is unreachable (plane, secure environment), events buffer on disk indefinitely and ship when connectivity returns. They never block analysis and are never dropped silently.
- **Deletion workflow.** Since `researcher_id` is keychain-stored and pseudonymous, deletion-on-request is operationally: the tester tells us their UUID (visible in Settings), we delete matching rows. The `researcher_id` Reset control also breaks the link to future events while leaving past events in place unless explicitly deleted.
- **Debounce.** Accept-then-un-accept within 2 seconds collapses to a single final-state event; later edits emit a new event. The rule is: one event per final state per `(researcher_id, tag_id, prompt_version, session_of_analysis)`, where "session of analysis" is a device-local grouping that never leaves the device.
- **Publication gate.** Any public report of aggregate rejection rates is reviewed against re-identification risk before it ships. Named testers are not credited without their explicit permission. The corpus belongs to the cohort, not to marketing.

## The endgame this is building towards

The alpha instrument is a six-month tool. The mechanism it seeds is a ten-year one, and it's worth naming that mechanism explicitly so the relationship between instrument and endgame stays legible to future maintainers.

What rejection telemetry is ultimately building towards is a prompt-improvement loop where human judgements are the gradient. Every rejection, given enough context, informs a nudge to the prompt — or the exemplar set, or the boundary definition — in a direction that makes the next suggestion marginally better. At scale, if the loop works, the aggregate improvement is continuous and compounding. The codebook isn't *maintained*, it's *cultivated* — cultivated by the collective professional judgement of the users. It's an asset that is difficult to replicate without the same instrument.

**What this is, and isn't.** The loop as described is about improving the prompts that suggest codes, and the codebook's operational boundaries. It is not about training general-purpose AI models, and Bristlenose's consent language commits to that narrower purpose — see the consent gradient doc's §Purpose limitation. If a future Bristlenose-2 ever wants to use this corpus as training data, it requires fresh consent under a new purpose; it is not an extension of what Level 0–3 telemetry authorises.

The 0.01%-per-rejection ratchet is the shorthand: each event, combined with deliberate human review, nudges the system a fraction of a percent in the right direction; over many events and years, the system settles in a place hand-authoring alone would not have found.

The honest caveat is that the mechanism has to be designed carefully or it averages towards mediocrity instead of ratcheting towards excellence. "Most researchers rejected this, so adjust the prompt" is a recipe for regression to the most common judgement, and the most common judgement is not necessarily the best judgement. The interesting design questions — live for year 3 or 4, not for alpha — are things like:

- **Whose rejections count more?** A methodologically rigorous researcher's rejection is worth more than the median's. How do we weight that signal without building a caste system?
- **Binary or Bayesian?** Is accept/reject flat feedback, or is each event evidence updating a posterior about where a tag's boundary actually sits? The latter is much richer but requires a different data architecture.
- **How do we detect averaging-towards-mediocrity before it calcifies?** Some mechanism needs to protect edge-case tags with genuinely hard boundaries from being smoothed into uselessness by the majority vote.
- **What's the ratio of automation to human curation?** At what point does the loop become self-running, and at what point does a human methodologist still need to step in and say "this ratchet is pulling in the wrong direction"?

None of these needs to be resolved to ship alpha. But they're worth writing down now so that when we're designing the Level 2 and Level 3 data architectures, we do it with the endgame in view rather than bolting it on later.

The relationship between this doc and the endgame, stated plainly: the six-month instrument earns us the right to build the ten-year mechanism. If rejection telemetry at alpha doesn't demonstrably improve prompt quality through hand-tuning, the premise of the whole ratchet is in doubt, and we should know that early. If it does, then the next five years of data-governance, consent architecture, and ML infrastructure have a foundation worth building on.
