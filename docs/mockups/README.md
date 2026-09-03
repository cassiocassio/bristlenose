# Mockups

Standalone HTML mockups for features in progress. Open in a browser to see the design intent — these are not part of the application and are never linked from the report or CLI.

Each file is self-contained (inline CSS/JS) so it works without a build step.

## Status banners

A mockup is a snapshot of intent at a date. Some are still the design of record;
some describe a flow that has since been replaced. Without a marker there is no
way to tell them apart except by reading the code, which defeats the point of
having them.

So a mockup whose standing is not obvious carries a banner at the top, in one of
three states:

| Banner | Means |
|---|---|
| *(none)* | Current. Trust it, or it has never been checked — the absence is not a claim. |
| **IMPLEMENTED** | Its recommendations shipped. Keep for the reasoning; read any "outstanding work" section as a diagnosis of a fixed problem. Commit refs in the banner. |
| **SUPERSEDED** | Describes a flow, vocabulary or decision that no longer exists. Keep as history; the banner names what replaced it. |

Nothing is deleted. A superseded mockup is the record of why the current thing
looks the way it does, and that argument is usually the expensive part.

Banners are self-styled inline so they cannot clash with each file's own CSS.

### Reviewed 3 Sep 2026

- `provider-status-glyph-vocabulary.html` — **SUPERSEDED**. Explored three
  treatments for the provider dot; a fourth shipped (colour + an always-visible
  localised label). Six `ProviderStatus` cases ship, this names five. The a11y
  reasoning stands.
- `mockup-autocode-lifecycle.html` — **SUPERSEDED**. Nine-step storyboard of the
  v1 flow, where importing a codebook and coding with it were separate acts.
  0.29.0 made Install *be* apply.
- `codebook-v2-messages.html` — **IMPLEMENTED**. Its message taxonomy is live and
  its findings drove `ae050e56`, `1d1eb3a0`, `96de7724`.
- `out-of-credit-ux.html` — current, and the **design of record** for the
  out-of-credit pill and popover. Its §3 settled that reaching for AutoCode while
  out of credit gets "nothing new — the pill is enough".
- `codebook-llm-state-matrix.html` — current. The codebook × LLM state audit and
  the decisions taken against it.
