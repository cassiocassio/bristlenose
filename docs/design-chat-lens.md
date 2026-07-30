---
status: draft
---

# Chat lens — a cited question box inside Bristlenose

_Design note. Nothing built. July 2026._

> **Status: Draft.** Split out of [`design-mcp-server.md`](design-mcp-server.md)
> (§6b/§6c there, 30 Jul 2026) so the two workstreams can run as separate
> sessions: that doc owns connecting **external** assistants (Claude Desktop,
> Claude Code, peers) to a local Bristlenose server; this one owns the **in-app**
> conversational surface. Read that doc's §Positioning first — this feature is
> the deliberate, scoped exception to it.

## Changelog

- _30 Jul 2026_ — added §5a (prior art, partial read — verification still running). Three corrections to §5: prompt-level grounding is empirically insufficient and models do not spontaneously abstain (15–40% hallucination on insufficient context, 13% even on sufficient); id-existence validation catches fabrication only, not unsupported claims, so a support check is needed; and native Claude citations are mutually exclusive with structured outputs (HTTP 400), which blocks §6 as written. Vindicates skip-retrieval. Adds better mechanisms: per-claim citation exemption for connective text, three-way abstention reasons, sentence-granularity support checking with a prompted judge over NLI. Contests inline citation layout.
- _30 Jul 2026_ — §7: named the shared seam (`bristlenose/server/grounding.py`) and the shared response vocabulary, so parallel sessions collide at one file path instead of silently duplicating.
- _30 Jul 2026_ — split from `design-mcp-server.md`. Added §2 (the in-app
  benefits, incl. citations that resolve to the report's own quote → transcript
  → video apparatus), §6 (prototype route via the `elaboration.py` template),
  and §7 (the coordination contract with the MCP workstream for parallel
  sessions).

---

## 1. Which proposal this is — and which it is not

Two different "chat in Bristlenose" ideas came up during the MCP design, and only
one of them survived:

- **Refused:** a "Claude lens" — a window inside Bristlenose onto an MCP
  conversation happening in an external assistant. An empty room with a signpost;
  the data and the chat both live elsewhere.
- **This doc:** a real question-answering surface, in-app, powered by the
  provider Bristlenose is *already* configured with — Claude, ChatGPT, Azure
  OpenAI, Gemini, or Ollama via `bristlenose/llm/`. No new credentials, no new
  vendor relationship, no connect step.

The positioning tension is real and stated, not papered over: the MCP doc's
§Positioning rejected "a chat lens inside Bristlenose" as the Dovetail/Marvin
shape. This feature re-enters that door **knowingly and narrowly** — see §4 for
the scope that keeps the line intact ("specific jobs with a review affordance
happen in-app; open-ended conversation happens in the assistant" — here the
citation *is* the review affordance).

## 2. Why in-app at all — benefits only the app can deliver

- **Citations that resolve to the real objects.** This is the strategic reason to
  exist. An assistant in someone else's chat window cannot deep-link `q-p1-123`.
  A Bristlenose-native answer can footnote every claim to a clickable quote —
  and the click has somewhere to go, because the apparatus already exists:
  - quote id → quote card in the report (existing `q-{participant}-{seconds}`
    DOM ids);
  - quote → per-participant transcript page at the timecode (`#t-<seconds>`
    anchors, resolved by `resolveSegmentForSeconds` in `TranscriptPage.tsx` —
    the same tolerance chain the journey deep-links use);
  - transcript position → **the video at that moment**, via the video-map API
    (`GET /api/projects/{id}/video-map`) and `PlayerContext.tsx`.

  So a cited answer is not a bibliography — it is a set of playable moments.
  "Participants struggled with onboarding [▶ 3 quotes]" where ▶ means *watch the
  person say it*. No external assistant can do this, and no screenshot of a chat
  window can either. It is also the feature's demo.
- **No connect problem.** Everything in the MCP doc's §6a — config files, the
  sandbox constraint, token rotation, client detection, install-the-app
  fallbacks — is absent. The surface ships inside the product.
- **It reaches the researchers the glue position misses.** The MCP doc admits its
  funnel honestly: needs an assistant, needs a setup step. This surface has no
  funnel — it is a lens in the report they already have open.
- **Ollama makes it genuinely local-first.** A conversational analysis surface
  where nothing leaves the machine is something no MCP path can offer, and it is
  on-brand in a way the MCP story is not.
- **Context assembly is ours.** The server picks the right objects — codebook,
  signals, starred quotes, section structure — deterministically, rather than
  hoping a remote model calls the right tools in the right order.
- **Cost model:** questions are metered on the researcher's own API key (~20k
  input tokens per question on the context-stuffing route, §6), where MCP spends
  their assistant subscription. This cuts both ways — flat-rate assistant users
  get MCP "free"; Ollama users get this lens free. Say which is which in any
  comparison.

## 3. The two objections, stated at full strength

1. **This is literally the alternative §Positioning rejected** — "a chat lens
   inside Bristlenose". Reversing that is allowed, but it should be done knowingly
   and the doc should not pretend the tension away.
2. **You will build a worse chat UI.** Streaming, markdown, history, retry, edit,
   branch, attachments, model switching — that is a product, and every hour of it
   is an hour not spent on the object model that is actually defensible (MCP doc,
   §Positioning "what this position has to defend").

## 4. The resolution: scope

**The version that survives objection 2 is not a chat.** It is a **question box
with cited answers** — ask, get an answer footnoted to clickable quotes, no
conversation history, no branching, no attachments, no model picker. Perhaps a
tenth of the build of a chat product. The citation is the review affordance, so
the positioning line holds; and the inline evidence is the reason the feature is
worth having rather than being a worse copy of a chat app.

If history/threading ever earns its way in, it does so *after* the cited answers
prove trustworthy — not as part of v1.

## 5. Guard rails — the citation requirement is the *spine* of the guard rail

> **Revised 30 Jul 2026.** This section originally argued the citation requirement
> was *sufficient* on its own. Prior art says otherwise — see §5a. It remains the
> right spine; it needs a support check beside it.

The obvious worry is off-topic use: a researcher asks the interview chat for a
spaghetti recipe. That is the **least** of it, and it does not need a filter.

**The dangerous case is a confident, plausible, uncited research claim.** Ask a
raw model "what do participants think about pricing?" against a corpus containing
nothing about pricing, and it will produce fluent UXR-shaped findings from its
training data. In a research tool, presented next to real findings, that is the
actual harm — not a recipe.

Both are handled by the same mechanism, which is why it should not be a separate
subsystem:

1. **The response schema requires citations.** Every claim carries `quote_ids`;
   the prompt says answer only from the supplied quotes. A recipe has no
   supporting quotes, so it cannot be expressed in the response format at all. It
   falls out as an empty result, not a refusal.
2. **Cited ids are validated server-side against the corpus.** This is
   load-bearing and easy to skip: **a model can invent `q-p1-999`.** Resolve every
   returned id against the project's actual quotes, and drop or flag any claim
   whose citations do not resolve — and check scope, not just syntax, so a claim
   cannot cite a quote from a project the question did not cover. **Without this
   check the citations are theatre**, and the feature is worse than no feature
   because it looks verified.
   > **Corrected by §5a.** Existence-checking catches fabricated ids and *nothing
   > else* — not unsupported claims, not irrelevant-but-real citations. Prior art
   > goes further: construct the id space server-side so fabrication is not
   > expressible, and add a separate support check. See §5a Corrections 1–2.
3. **Render the cited quote inline, under its claim.** A wrong citation becomes
   obvious without a click. This is simultaneously the guard rail, the review
   affordance, and the reason the feature is worth having in-app at all (§2).
   > **Contested by §5a.** A controlled study (N=372) found a *persistent parallel
   > sidebar* — not inline — was the only layout preserving critical engagement as
   > citation density rose. Provisional evidence; test both.

### What not to build

**Do not build a topic classifier or a refusal layer.** It is a subsystem, it will
false-positive on legitimate adjacent questions — *"how should I phrase this
finding for execs?"* is off-corpus and entirely reasonable in a research tool —
and it guards the wrong risk.

A short scoping line in the system prompt is worth having as *framing*, not
enforcement, and it should be plain rather than a lecture. The empty-result case
is **not a refusal**: "nothing in this study's quotes answers that" is a finding
about the corpus, not a rejection of the researcher. That message needs to fit the
existing `MessageKind` vocabulary — see `docs/design-pipeline-diagnostic-popover.md`
before inventing a new tone for it.

### The separate one: cost

Stuffing the corpus (§6) means every question costs roughly 20k input tokens on
the researcher's own key. That is a real guard rail with nothing to do with
topic: cap tokens per question and questions per session, and look at prompt
caching early — the corpus prefix is identical across every question in a
session, which is close to the ideal caching shape.

Out of scope for the prototype: answering questions *about Bristlenose itself*
("how do I export?"). Legitimate, but a different corpus and a different feature.

## 5a. Prior art — and three corrections to §5

Deep-research pass, 30 Jul 2026. **Read status honestly:** 120 claims extracted
from primary sources; adversarial verification was still running when this was
written, ~15 claims fully voted. The refutations that had landed targeted
extractors' *interpretive framing*, not the underlying facts ("descriptive half
checks out, interpretive half overreaches" was the recurring verdict). So what
follows leans on **structural facts** — documented API shapes, published
parameters, benchmark numbers — and flags interpretation as interpretation.

### Correction 1 — "the citation requirement is sufficient" is wrong

§5's central claim does not survive. Two independent lines of evidence:

- **Prompt-level grounding is empirically insufficient.** The Trust-Score /
  Trust-Align work (ICLR 2025) reports as its headline *negative* result that
  prompting techniques, including few-shot in-context learning, fail to constrain
  models to answer only from supplied documents. Closing the gap required
  preference-based alignment, worth ~10–30 Trust-Score points.
- **Models do not spontaneously abstain.** Google's sufficient-context work
  measures 15–40% hallucination when the supplied context cannot answer the
  question — and, more damning, **13% hallucination for GPT-4o even when the
  context is sufficient**. Microsoft documents the same admission for Azure
  OpenAI On Your Data: `inScope=true` is explicitly *not* a hard constraint, and
  the model still answers out-of-domain questions with it enabled.

**And ID-existence validation catches the wrong half of the problem.** A citation
that resolves correctly but points at a passage that does not support the claim
is *worse than no citation*, because its apparent validity buys unearned trust.
Citation quality is two-sided — recall (is every statement supported by what it
cites?) and precision (is each attached citation actually relevant?) — and an
ID-resolution check catches neither. It catches fabricated identifiers only.

**So §5 needs a third leg: a support check, not just an existence check.**

### Correction 2 — don't let the model emit IDs at all

§5 assumed the model returns `quote_ids` and the server validates them. Every
serious implementation surveyed does the opposite: **construct the ID space
server-side so a fabricated ID is not expressible.**

- **Google's Check Grounding API** returns integer indices into the caller's own
  fact array — the indices are emitted by the *validator*, not the generator, so
  validation is a bounds check rather than a fuzzy match.
- **LlamaIndex** mechanically prepends numbered markers to each context chunk
  before generation, so the only citation tokens available are ones that
  provably exist.
- **Anthropic's Citations API** extracts the cited span server-side and defines
  `cited_text` as exactly the caller's content at `[start_block_index:end_block_index]`
   — the calling server can re-derive the span from its own corpus and reject any
  mismatch.

**The Anthropic path fits Bristlenose almost exactly.** `search_result` content
blocks accept **arbitrary caller-defined stable identifiers** as the citation key
(not just URLs), and *custom content* blocks are used **as-is with no further
chunking**. So: **one quote per block, `source="q-p1-123"`, citations enabled.**
A 1:1 citation-to-quote mapping becomes *structural* rather than prompt-enforced,
and the docs name transcripts as a motivating case.

### Correction 3 — the prototype's schema and native citations are mutually exclusive

**This is a hard blocker on §6 as written.** On the Claude API, enabling citations
on any document or `search_result` block *while also passing* `output_config.format`
returns **HTTP 400**. Anthropic's stated reason: citations interleave metadata with
prose text blocks, which cannot coexist with strict JSON schema constraints.

§6 specifies both — a `claims[]/quote_ids[]` response model *and* citation
behaviour. **Pick one:**

| | A — schema + validation | B — native citations |
|---|---|---|
| Mechanism | model emits `quote_ids`; server resolves them | platform returns cited blocks with caller IDs |
| Fabricated IDs | possible; must be caught | **not expressible** |
| Provider-agnostic | **yes** (works on Ollama, ChatGPT, Gemini) | Claude-only |
| Cost | quote text regenerated as output tokens | `cited_text` is **billing-free** both directions |

**Recommendation: build A, but shape it like B.** Bristlenose must work on Ollama
and the other providers (§1), so a Claude-only primitive cannot be the only path.
But adopt B's discipline inside A: supply one quote per block with an explicit
stable ID, and — per LlamaIndex — hand the model a **server-constructed index
space** (`[1]`, `[2]`, … mapped to quote ids server-side) rather than asking it to
recall `q-p1-123` strings. Fabrication then degrades to an out-of-range integer,
caught by arithmetic. Worth a spike on B for the Claude path if the cost
asymmetry proves material.

### What §5 got right

- **Skip retrieval on a small corpus** — strongly supported. Anthropic states
  retrieval is unnecessary below ~200k tokens and prescribes stuffing the corpus;
  its long-context guidance triggers at 20k+ and prescribes *prompt structuring*,
  not retrieval. Chunk retrieval carries a measured 1.9–5.7% miss rate that
  full-context removes entirely. And Microsoft documents the failure this avoids:
  the canonical abstention string fires as a **false refusal** when the evidence
  exists but the retriever dropped it — conflating "your data doesn't answer
  this" with "my retriever lost it".
- **Put the corpus before the question** — vendor-prescribed layout (the "up to
  30%" figure attached to it is an unsourced vendor claim; treat as weak).
- **Prompt caching** is the named mechanism that makes whole-corpus prompting
  economic — §5's cost note is on the right track.
- **No topic classifier** — supported, but the *mechanism* is better than §5's:
  see below.

### Better mechanisms than §5 proposed

**Not every claim must cite.** Google ships a per-claim `grounding_check_required`
boolean; when false, no citation indices are returned and the claim still renders.
Framing, transitions and meta-sentences are *exempted* rather than forced to cite
or suppressed. **This is the actual anti-brittleness mechanism** — better than
§5's "one plain scoping line", and it directly addresses the punitive-feel worry.

**Abstention is not one message.** Google's answer API returns a machine-readable
`AnswerSkippedReason` enum separating *out of scope* (no high-relevance results),
*in scope but no evidence*, and *evidence existed but the answer could not be
grounded* — plus adversarial/chit-chat/policy reasons. §5 has one empty-result
message; it should have at least those first three. Apple's HIG independently
prescribes that refusal states **coach toward a better request** rather than
denying, and that open-ended prompt boxes ship **curated example inputs** to set
scope up front.

**Over-citation is a measurable defect, not free.** ALCE penalises "overcite":
for a jointly-entailed multi-citation sentence, each citation is re-tested
individually and counted against precision if the sentence entails without it.
Recall-only citation metrics are gameable by footnoting everything reachable.

### The support check — how to build it cheaply

- **Sentence granularity, no decomposition.** Splitting claims into atomic facts
  before verification actively *hurts* (MiniCheck −1.4, QAFactEval −1.9) and adds
  cost. The primitive is `check(document, sentence) → [0,1]`, binary
  supported/not-supported, threshold at the midpoint.
- **A prompted LLM judge beats a fine-tuned NLI model** for the sufficiency gate:
  93.0% accuracy / 0.935 F1 versus TRUE-NLI T5-11B at 0.826 / 0.818. Notably NLI
  has the highest *precision* but much lower recall — it under-detects. So don't
  reach for an NLI dependency; use the provider already configured.
- **It is cheap.** A 770M specialised checker (MiniCheck-FT5) reaches GPT-4-level
  grounding accuracy at >400× lower cost ($0.24 vs $107 across 13K checks).
- **But it is noisy — do not make it a hard gate.** On the 11-dataset
  LLM-AggreFact benchmark the best judge scores ~75% balanced accuracy: roughly
  one in four supported/unsupported judgements is wrong. Use it to *flag*, not to
  suppress.
- **Correct abstention deserves its own metric.** Trust-Score treats "refusal
  groundedness" as a first-class dimension alongside correctness and attribution;
  answer correctness is *not* a proxy for groundedness, since models answer
  correctly up to ~35% of the time from parametric memory when context is
  insufficient.

### Layout — inline may be the wrong default

§5.3 prescribes rendering the cited quote inline beneath its claim. A controlled
experiment (N=372) comparing Collapsible / Hover Card / Footer / **Aligned
Sidebar** found the persistent parallel sidebar was the *only* condition that
preserved critical engagement as citation density rose, and that high citation
density measurably degrades critical evaluation in the other presentations — the
mitigation being **layout, not fewer citations**. Hover Card won on frictionless
in-flow verification but did not protect critical engagement; the paper frames
fluency and reflective verification as not co-optimisable.

**Caveat, and it is substantial:** non-peer-reviewed preprint, and the headline
critical-thinking outcome rests on an *automated* assessment rather than a
validated human-scored instrument. Treat as provisional. But it is enough to stop
inline-under-claim being adopted as obviously-correct — worth testing both in the
lab surface, and it converges with Bristlenose's existing sidebar vocabulary.

**And a genuine challenge to the whole premise:** Microsoft's HAX Guideline 11
warns that explanation surfaces are double-edged and can *increase over-reliance*
and inflate expectations. A citation footnote is a local explanation. §2's claim
that citations make the feature trustworthy is therefore not self-evidently true —
citations plus an unverified support relation may buy *more* unearned confidence
than no citations at all. This is the strongest argument in the corpus for
Correction 1.

### Tone

- **Explicit prompting is the only reliable lever on length.** Anthropic states
  Opus 5 runs longer by default than prior models and that the effort parameter
  does *not* reliably shorten visible output. Two transferable rules: state the
  positive instruction rather than the prohibition ("compose smoothly flowing
  prose paragraphs" beats "do not use markdown"), and **match prompt style to
  desired output style** — markdown in the prompt produces markdown in the output.
- **Hedging is a calibration problem, not a tone problem.** HAX Guideline 2
  requires the *linguistic* precision of the interface to track measured system
  performance: confident phrasing is a defect when accuracy doesn't support it,
  and hedged phrasing is *equally* a defect when it does. This is a better frame
  than "be terse".
- **Explain only what moves the decision.** Google PAIR's guidance is deliberately
  anti-comprehensive — explain the aspects that affect user trust and
  decision-making, not the whole system. Supports evidence-first layout over
  narrated model rationale. PAIR also warns that **displaying model confidence is
  an unreliable trust device**, often not actionable — so a per-claim confidence
  number is not automatically an improvement. *(PAIR pages were proxy-blocked;
  wording recovered via exact-phrase search and third-party quotation — treat as
  high-confidence-but-unverified.)*
- **Apple HIG favours specificity over brevity per se** — failures should state
  what happened in plain language plus a next step.

### Instruction placement

Microsoft documents that system/role instructions are **silently truncated** past
an implicit per-model token limit, and recommends repeating the critical
instruction at the *end* of the prompt. With a stuffed corpus in the same prompt,
a long corpus-only/tone system prompt can degrade **without error**. Restate the
citation and scope rules after the corpus, not only before it.

## 6. Prototype route — fastest honest path

**Template: `bristlenose/server/elaboration.py`.** It is already the exact shape
needed — an LLM call from serve mode, provider-agnostic via `LLMClient(settings)`,
structured output through `analyze(..., response_model=…)`, results content-hash
cached in SQLite (`ElaborationCache`), project-scoped. Copy the skeleton.

**Skip retrieval entirely.** No embeddings, no vector store, no chunking. A real
project is a few hundred curated quotes (~20k tokens) — the whole corpus fits in
context. That is the MCP doc's compression argument turned inward, and it removes
the single biggest source of prototype timeline blowout. Folder scope does not
fit this route; the prototype is one project.

**Citations are structural, not prose.** Do not ask for footnotes in the answer
text and hope. The response model is roughly:

> **Read §5a Correction 3 before writing this call.** On the Claude API, native
> citations and `output_config.format` are **mutually exclusive (HTTP 400)** —
> this schema and Anthropic's citation primitive cannot be combined. The
> recommendation is to keep the schema (provider-agnostic, works on Ollama) but
> hand the model a **server-constructed integer index space** rather than raw
> `q-p1-123` strings, so a fabricated citation degrades to an out-of-range int.

```
claims:      [{ text: str, quote_ids: [str] }]
unsupported: str   # what the corpus could not answer, plainly
```

Rendering the chip is then mechanical, and a claim with an empty `quote_ids` is
*visibly* uncited rather than silently confident. `analyze()` already takes
`prompt_template` for telemetry — register the prompt in
`bristlenose/llm/prompts/` and it inherits the existing `llm_request` logging.

**Ship it the way the codebook lab shipped** — flag-gated
(`experimental_codebook_lab` is the precedent), ugly, one route plus one lab
page. No streaming, no history, no model picker.

**What the prototype is testing is not "can it answer" — it is "are the
citations honest".** Render each cited quote inline beneath its claim rather than
behind a click, so a wrong citation is obvious instantly. The video deep-link
(§2) is the second iteration, once the citations are trustworthy — the ids it
needs are already in the response.

## 7. Coordination with the MCP workstream (parallel sessions)

These two features are being pursued in **separate sessions**, possibly
concurrently. The original sequencing argument (MCP first, as a forcing function
on the object model) still holds as a *preference*; if the work runs in parallel
instead, the risk to manage is **two divergent implementations of the same
core**. Both features need:

- **corpus/context assembly** for a project (which objects, in what order, with
  what caps);
- **quote-id resolution and validation** (the §5 server-side check and the MCP
  doc's tool responses resolve ids the same way);
- **the same invariants** stated to the model (quote exclusivity, tag
  double-counting, no cross-study person joins — MCP doc §3/§3a);
- **the same anonymisation boundary** on the way out.

**Contract: whichever session lands first establishes the shared core as
ordinary importable server code (not route-handler-private logic); the other
consumes it.** Neither session should duplicate it. If the MCP session lands
first, the chat lens is a thin client over the same functions the MCP tools
call; if the chat lens lands first, the MCP tools wrap its core. Either order
works; two cores do not.

**Named seam — so parallel work collides mechanically instead of diverging
silently:** the shared core lives at **`bristlenose/server/grounding.py`**. Both
sessions create *that path* if it does not exist yet; if both do, git surfaces a
merge conflict at one file — visible and resolvable — rather than two
similar modules under different names that nobody reconciles. Design-level
contents: `assemble_corpus_context(…)` (which objects, in what order, with what
caps), `resolve_quote_ids(…)` (resolved + rejected split, scope-checked against
the project), the model-facing `INVARIANTS` statements (from
`design-mcp-server.md` §3/§3a), and the anonymisation application. Shared
response vocabulary across both surfaces: `claims[].text`, `claims[].quote_ids`,
`unsupported` — do not invent synonyms per surface.

## Related docs

- [`design-mcp-server.md`](design-mcp-server.md) — the external-assistant
  workstream: positioning (read §Positioning before touching scope here),
  object surface, invariants, scope model, spike definition (§9a).
- [`design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md)
  — `MessageKind` vocabulary for the empty-result message (§5).
- `bristlenose/server/elaboration.py` — the prototype template (§6).
- [`design-llm-call-telemetry.md`](design-llm-call-telemetry.md) — the telemetry
  the prototype inherits via `prompt_template`.
- `frontend/CLAUDE.md`, `bristlenose/server/CLAUDE.md` — player/transcript
  deep-link apparatus reused by §2.
