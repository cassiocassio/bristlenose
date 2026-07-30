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

## 5. Guard rails — the citation requirement *is* the guard rail

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
3. **Render the cited quote inline, under its claim.** A wrong citation becomes
   obvious without a click. This is simultaneously the guard rail, the review
   affordance, and the reason the feature is worth having in-app at all (§2).

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

> A deep-research pass on prior art (grounded in-product agents, citation
> validation, abstention UX, tone) is in flight as of 30 Jul 2026; fold its
> findings into this section when it lands — especially anything that contradicts
> "the citation requirement is sufficient".

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
