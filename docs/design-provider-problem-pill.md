---
status: partial
last-trued: 2026-11-02
trued-against: db481e43c (slice 1: key rejected and out of credit, after review)
---

# The provider-problem pill

One title-bar pill that tells the researcher the **active cloud provider is
refusing them**. Slice 1 (shipped locally 2 Nov 2026) covers the two refusals the
provider itself answers: **key rejected** and **out of credit**. The design
argument, every alternative weighed, the failure versions and the review
findings are in [`docs/mockups/provider-problem-surface.html`](mockups/provider-problem-surface.html);
this page is the as-built record of what the code does and the calls made.

Not here yet: telling *why a provider can't be reached* (offline, a network that
blocks it, an outage) and the pass/fail ladder of layers. That is slice 2, which
needs measurements and an audit first (`docs/design-provider-problem-diagnosis.md`
once that session has written it). The switch-provider pull-down is a Could in the
100-day list.

## What the researcher sees

- **A capsule in the toolbar's `.status` shelf**, the kind glyph then the words:
  `Claude · key rejected` (red `xmark.circle.fill`, the *error* kind) or
  `Claude · no credit` (amber triangle, the *warning* kind). No glyph of its own:
  the existing five-kind vocabulary only.
- **Loud for 15 minutes** (tinted fill and stroke), **plain** until 24 hours after
  the first refusal, then **the bare glyph** with no capsule. The glyph never
  changes between stages, so a collapsed pill is recognisably yesterday's. Click
  it and the popover has two lines: the state, then what to do.
- **A small bare ✕ on mouseover or keyboard focus** (Safari's tab close), which
  hides the notice entirely. Its room is half reserved so the pill never resizes
  under the pointer, and the end of the text fades beneath it only while it shows.
  The collapsed glyph has no ✕ of its own. VoiceOver has a "Hide" action on the pill.
- **No menu-bar twin and no Hide button** (owner, 2 Nov 2026).

## The rules (`ProviderProblem.swift`, pure and tested)

| Rule | Why |
|---|---|
| A **refused call** raises it; a stored verdict alone does not. | The shipped pill read the sticky verdict, so credit that ran out in January was amber in March for someone who came back for old data. Settings validation still paints the Settings dot. |
| Sources: a finished run (`PipelineRunner.deriveFailureState`, **explicit**) and the sidecar's `llm-failure` bridge post (**incidental**). | A run is something the researcher asked for; a call inside the report is not. |
| A rejected key counts from a run **only when the category came from the structured cause**. | The stderr fallback matches `401` and `authentication` anywhere in the tail, a guess that has mislabelled failures before. |
| The pill is **held to the key's cached verdict**; a new key or a good re-validation clears it and the record, and a run that made an LLM call clears the record whatever the verdict says. | One source of truth with Settings. A run that worked now clears a rejected-key verdict too (it used to clear only out-of-credit): a working call contradicts it. |
| **Except:** a good Settings check does not cure *out of credit* for ChatGPT. | ChatGPT's check is a free model-list request that returns 200 for a bankrupt key. Without this, opening Settings wiped the pill and the hidden state, and the next AutoCode refusal brought it back loud. Only Claude's check (a billed call) can see an empty account. |
| A refusal belongs to **the key the call used**: a run's key is fingerprinted at spawn, and a refusal that arrives after the key was replaced is dropped and logged. | Stamping `.invalid` over a fresh, working key would put a false red on the pill and the Settings dot. |
| A key the Keychain **would not read** hides the pill but keeps the record. | "Could not read" and "gone" both look like nil; a different key later clears the record anyway. |
| A rejected key counts only from a **structured cause that is this attempt's own**: not the stderr guess, and not a reconnected run or one with no spawn time. | `terminusIsCurrentAttempt` answers yes for every unknown, which is right for showing a cause and wrong for lighting an app-wide pill. |
| A new refusal is **announced to VoiceOver once, by the model**, high priority for an error. Not from the view. | The pill is in every window and would announce once per window, and again at every launch for a restored record. |
| Every path that declines to record a refusal **logs why** (`provider-problem` category). | A pill that silently never appears is worse than one that is wrong loudly. |
| ✕ hides it. The same condition again from something **incidental** stays hidden; a refused **run**, or a changed condition or provider, brings it back loud. | Months of edits on an empty account must not bring it back each time. |
| The stage is evaluated at launch, on app activation, on a recorded refusal and on a prefs change. **No timer.** | Nothing may change while someone is looking at the toolbar. |
| Another provider active: hidden, record kept. | Switching back to one that is still refusing says so. |
| A local provider (Ollama) never shows. | No key, no credit. |

## Judgement calls made on the owner's behalf (2 Nov 2026), open to change

- **15 minutes loud, 24 hours to the glyph**, measured from the first refusal and
  never restarted by an incidental repeat, so a month of edits on an empty account
  neither re-tints nor un-collapses it. Evaluated on refresh, so someone who never
  leaves the app sees "loud" for hours.
- **Another provider active: hidden, record kept**, so switching back to one that
  is still refusing says so. Dropping the record on a switch would be quieter.
- **Settings validation raises nothing.** A key just pasted and seen to go red in
  Settings does not light the pill; the Settings dot already says it.
- **A queue of studies on a dead account** re-lights it for each study's refused run
  (each is explicit), so dismissing after the first brings it back for the second.
- **Nothing clears it from a successful incidental call** (an AutoCode job after a
  top-up): only a run that worked, a good Settings check where it can see credit,
  or a new key.
- **A changed verdict between the two refusals** (out of credit, then key rejected)
  clears the record rather than rewording it; the next refusal starts afresh.

## Owed

- **Native review of 20 locales.** The eight new `desktop.providerProblem.*` keys
  (`keyRejected.pill`, `keyRejected.body`, `openSettings`, `hide`, `hideTooltip`,
  `hint`, `kind.error`, `kind.warning`) were drafted by Claude from each locale's
  own terms for key, rejected, Settings and Hide. `zh-Hant-HK` falls back to
  `zh-Hant`.
- **Checked only by building, not by running:** the hover reveal, the fade, the
  centred `.status` placement, the VoiceOver announcement and the behaviour on
  macOS 15. The DEBUG harness (Diagnostics ▸ Provider problem pill) forces any
  look for that.
- **Slice 2** (network diagnosis, the ladder) and **the collapsed glyph's way to be
  dismissed** (it has none beyond fixing the cause).
- **A stale comment in `frontend/src/shims/bridge.ts`** still names the deleted
  `OutOfCreditModel`; not fixed, because a comment edit under `frontend/src` changes
  the sidecar fingerprint and forces everyone's next build to rebuild the sidecar.

## Where the code is

`ProviderProblem.swift` (conditions, stages, rules, presentation),
`ProviderProblemModel.swift` (state, persistence, recording, the DEBUG harness),
`ProviderProblemPill.swift` (the view), `ProviderProblemTests.swift`. Wiring:
`PipelineRunner.deriveFailureState` and its `noteRunSucceeded` default,
`BridgeHandler`'s `llm-failure` case, `ContentView`'s `.status` toolbar item.
