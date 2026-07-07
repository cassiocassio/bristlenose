# Curation persistence across incremental re-runs

**Status:** _Shipped this branch (Jul 2026):_ Freeze (Phase 1), section identity (Phase 2), theme star-anchor + "New" flag (Phase 3b/3c), and the named-group retire-exemption + read-only Uncategorised floor. _Still design-only:_ the §9 surfaced-suggestion / dissent flow and §13 manual re-assignment (Phase 0 — [`design-manual-reassignment.md`](design-manual-reassignment.md)).
**Parent:** [`design-incremental-analysis.md`](design-incremental-analysis.md) — the problem of adding interviews to an already-analysed project without destroying researcher work. That doc frames the problem and the two-layer stance; **this doc specifies the persistence layer**: exactly which human signals survive a re-run, the identity machinery that carries them, and the rules and tie-breakers for when structure shifts underneath them.
**Implementation plan:** [`design-curation-persistence-plan.md`](design-curation-persistence-plan.md) — the code-grounded phasing (Freeze → Section identity → Themes + "New!" flag), migration steps against the live importer/models, and the build/review process.
**Grounding:** the quote-stability experiment (Jul 2026 — statistical summary in the parent doc). Numbers used throughout: re-extracting the same interview recovers **~81%** of quotes by single-best-overlap-match and **~95%** by union/split-crediting at ≥70% overlap, with a **~9% genuinely-fragile tail** no matcher recovers; **section** membership is stable run-to-run (**ARI ~0.96**); **theme** membership churns (**ARI ~0.43**, theme counts swinging ~2× on *identical* quotes). Examples below (a "Checkout" section, an "Onboarding friction" theme) are generic UX illustrations, not from any project's data.

---

## 1. The challenge

Interviews arrive over weeks. Each re-run re-derives everything from scratch — and LLM extraction and grouping are non-deterministic, so quote boundaries drift, sections shift, themes reshuffle and re-label even on identical input. But the researcher's curation on top of that output — the stars, edits, tags, hides, and custom names — *is the deliverable*. Naively re-running risks two failures: their work **vanishes** (a starred quote isn't re-extracted; a hide comes back unhidden) or it's **silently reshuffled** (the theme they named and cited is gone, their quotes re-bucketed).

The bind is a trilemma. Computer science wants **stable identity** (small input change → small, predictable output change). LLMs supply **drift**. Qualitative methodology wants the analysis to **legitimately evolve** — more data *should* change the thesis. So we can neither freeze everything (that kills the evolving analysis the researcher needs) nor let everything re-form (that destroys the curation). The resolution is a seam: freeze what the human committed, let the rest evolve, and be honest at the join.

## 2. What the data says (the constraints we design against)

These are empirical inputs, not opinions:

- **Quotes drift, and freezing beats matching for anything valuable.** Re-extraction recovers ~95% by union-matching, but a **~9% tail is genuinely fragile** — the model sometimes doesn't extract those quotes at all, so *no* matching rule can recover a mark pinned to them. Anything the researcher touched must therefore be **frozen**, not re-derived-and-rematched.
- **Sections are stable; membership carries their identity.** ARI ~0.96. Majority-membership matching resolves "this section is that section" cleanly almost always.
- **Themes churn; membership does *not* carry their identity.** ARI ~0.43, with theme counts swinging ~2× on identical quotes. Theme labels drift heavily. Membership-based theme matching frequently has no clean answer.
- **The theme layer generates its own instability.** Even at *fixed* quotes, sections stay near-deterministic but themes reshuffle — so theme churn is not merely inherited from quote drift; the grouping stage manufactures it.
- **Corpus type decides how hard this is.** Product / usability studies are **section-heavy** (most quotes live in stable sections) → persistence is easy. Exploratory / oral-history studies are **theme-heavy** (most quotes live in churny themes) → persistence is hard, and the reliable floor becomes the quotes page, not the theme structure.

## 3. The design stance

1. **Human-declared meaning is authoritative, not provisional.** The researcher arrives with months of product context the system lacks; a session-1 star is an *informed* judgement, not a premature guess awaiting statistical validation. Their marks outrank the machine's later re-derivation, always.
2. **Presence vs prominence.** *Presence* — does this quote/grouping still exist for the researcher — is human-owned and absolute. *Prominence* — is it the featured hero, the signal-card exemplar — is machine-suggested and legitimately fluid.
3. **Preservation scales with the cost of being wrong.** Freeze where a miss loses curated work (catastrophic); use best-effort matching where a miss is cheap to fix.
4. **Membership is identity; labels and names are presentation bound to identity.** A section/theme *is* its quotes; its label (machine) and its custom name (human) ride on top of that identity.
5. **Never silently reshuffle a human commitment — surface it.** The machine may *suggest* moves, splits, renames; the human commits.
6. **The machine's confidence is weakest on the layer that churns.** A confident theme placement is high-confidence-per-run but low-stability-across-runs (ARI 0.43). Don't let noisy machine judgement override stable human intent.
7. **Object permanence beats theoretical accuracy.** A researcher builds a spatial memory of their own report — *this quote lives in that theme*. A slightly-imperfect grouping they can find beats a theoretically-better one the machine silently moved: "that's where I left it" wins over "the computer moved my cheese." Continuity isn't a concession to laziness; it's a property of human cognition, and honouring it is the whole point of pinning. When accuracy and permanence conflict, permanence is the default and accuracy is a *suggestion*.

## 4. The UX we're aiming for

From the researcher's chair:

- A **starred or edited** quote **never vanishes** — it's always at least on the quotes page, in the exact form they left it. If they exported it to a board or linked a clip, that reference stays valid.
- A **hidden** quote **stays hidden** (best-effort ~95%) — it doesn't magically reappear next run.
- A section or theme they **renamed** keeps *their* name on the surface, even as the machine's auto-generated name drifts underneath.
- The report's **structure evolves** as data grows — new themes appear, groupings sharpen — but their committed work rides through it untouched.
- Nothing they did disappears **silently**. When the machine wants to move, split, or re-name something they committed to, it **asks**.

## 5. Vocabulary

| Term | Meaning |
|---|---|
| **Fluid** | A quote/grouping with no human marks — fully re-derived each run; may re-cluster, demote, or drop. This is where churn belongs. |
| **Pinned** | A quote the researcher starred or edited — given a durable ID and **frozen**; never re-derived. |
| **Frozen** | Stored verbatim as of the moment it was pinned; carried forward as an artefact, not regenerated. |
| **Human state** | Any deliberate mark: starred, edited, tagged (→ pin); hidden (→ suppress). |
| **Presence / prominence** | Whether it exists (human-owned) vs whether it's featured (machine-suggested). |
| **Membership-identity** | A section/theme identified by the set of quotes in it, not by its label. |
| **Anchor** | For a human-committed (custom-named) theme, its identity is anchored to its **frozen starred quotes** — the stable part — while fluid membership churns around them. |
| **Suppression** | A hide: excluded from the report and best-effort re-suppressed, without freezing or elevating the quote. |
| **Carry** | Re-applying a mark/name to the right target on the next run. |

## 6. What each human signal commits to

The key subtlety: signals differ in *what* they commit the researcher to — a quote, a form, or a structure.

| Signal | Researcher's intent | Commitment | Treatment |
|---|---|---|---|
| **Star** | "Keep it, I might use it" | the **quote survives** — *not* its grouping | pin: durable ID + freeze form + guaranteed on quotes page |
| **Edit / trim** | "*This* wording is the one" | the **edited form survives** (strongest care signal — ~1 in 50, report-bound) | pin: durable ID + freeze the *edited* form |
| **Tag** | "This means X" | the **tag survives on the quote** (most common human work — protect it *most*, not least) | pin: same durable-ID + freeze as star |
| **Hide** | "Not worthy" | it **stays gone** | suppress: best-effort re-match, no freeze, no elevation |
| **Custom section name** | "I care about this grouping *and* its name" | the **name displays** on this grouping's identity | bind name to the section's membership-identity |
| **Custom theme name** | same, on a churny layer | the name displays on this theme's identity, held by its star-anchors | bind name to theme-identity, **anchored to its frozen starred quotes** |

**Pin trigger = `starred ∨ edited ∨ tagged`.** Hide is *not* a pin (see §10 for why the asymmetry is principled).

**Naming also commits the container's *existence*, not just its label.** A renamed section/theme is human-owned: the pipeline may never auto-retire it, even when re-analysis drains all its quotes — a **0-member named group is a valid resting state**, deleted only by the researcher (a future gesture). An *un-named* (machine-labelled) group still retires when it drains; a pinned quote it leaves behind lands in the **Uncategorised floor** (§12), never silently hidden. The star is a claim about the *quote*; the name is a claim about the *container* — they survive independently. *(Shipped, this branch: the importer exempts named groups from the retire sweep; `GET /quotes` returns a read-only `uncategorised` bucket of pinned, un-homed quotes.)*

## 7. The state engine

Three marks (`Starred`, `Edited`, `Hidden`) collapse to three observable states plus one rare overlap. **Preservation** (Fluid ↔ Pinned, driven by star/edit/tag) and **visibility** (Visible ↔ Hidden, driven by hide) are orthogonal.

```
                 ┌───────────────────────────────────────┐
                 │  PINNED                                │
                 │  • durable ID minted, form frozen      │
   star/edit/tag │  • guaranteed on quotes page           │
 ┌──────────────▶│  • placement carried (section reliable,│
 │               │    theme best-effort / anchored)       │
 │               └───────┬───────────────────▲────────────┘
 │  unstar AND revert    │ hide         unhide│ (or star,
 │  AND untag            │ (rare)             │  which un-hides)
 │  (no marks remain)    │                    │
 │               ┌───────▼─────────┐          │
┌┴──────────────┐│ PINNED+HIDDEN   │          │
│  FLUID (auto) ││ (edit kept, but │          │
│ • re-derived  ││  suppressed)    │          │
│   every run   │└─────────────────┘          │
│ • matchable   │                             │
│ • demotable / │        hide            ┌─────┴─────────┐
│   droppable   │───────────────────────▶│  HIDDEN       │
│               │◀───────────────────────│ • excluded    │
└───────────────┘        unhide          │ • re-suppress │
                                         │   best-effort │
                                         │   (~95%)      │
                                         └───────────────┘
```

A quote returns to **Fluid** only when its *last* preserving mark is removed. **Hidden** is an independent display flag; "edited-then-hidden" is a legal but rare corner (the frozen edit is retained in case they unhide).

## 8. Identity across runs

Two identity problems, solved differently because the failure costs differ.

**Quote identity.**
- **Pinned quotes:** identity is the **durable ID minted at pin-time**, and the quote is **frozen**. It is never re-derived, so it can never fall into the fragile tail. Matching is used only to *dedup* a re-extracted near-duplicate against the frozen copy (worst case: a brief duplicate, trivially resolved — the failure mode is benign, not catastrophic).
- **Fluid quotes:** identity is **best-effort matching** — position-overlap (≥70% of character span) primary, text-similarity as tiebreaker. ~95% carry with a ~9% fragile tail — acceptable *because these quotes carry no human state* (low stakes).

**Group identity.**
- **Sections:** the **membership signature** (which quotes are in it). Reliable — ARI ~0.96 — so "this section is that section" resolves by majority-membership almost always.
- **Themes:** membership is *unreliable* as an identity carrier (ARI ~0.43). For a **human-committed** (custom-named) theme, identity is instead **anchored to its frozen starred quotes** plus the custom name — the parts that don't churn. The theme is found across runs by its star-anchors even as its fluid membership reshuffles around them.

## 9. Rules and tie-breakers

> **Build status.** The **continuity defaults** in this section ship today (majority keeps the name, star-anchor decides near-ties, named containers persist, a dropped pin lands in Uncategorised). The **surfaced-suggestion** mechanism they defer to — the dismissible *"move this starred quote?"* / *"the anchors are scattering — you decide"* prompts — is **design, not built** (there is no surfacing code today; see §15). Rules below that say *surface* / *suggest* / *ask* describe intended behaviour, not shipped behaviour; until they're built the silent continuity default is what runs.

- **Quote carry.** Pinned → carried by frozen ID (+ dedup match). Fluid → best-effort match; misses drop to unmarked, which is fine.
- **Section-name carry.** Majority-membership map A→B: if most of A's quotes land in B (and not scattered), B *is* A under a new auto-label; the custom name displays on B. Splits and merges (below) are the only wrinkles, and they're rare at 0.96.
- **Theme-name carry.** Majority-membership for a *clear* split; **star-anchor breaks near-ties** (see split rule); **bind-then-stick** — once a custom name is inherited by a lineage, it stays bound to that lineage and does *not* re-compete for majority every run (or the noisy split ratio would make the name flicker between children run to run).
- **Split inheritance.** A custom-named theme A (say 50 quotes) splits into P (30) and Q (20): **P, the majority, inherits the custom display name** (its own machine label is suppressed); **Q, the offshoot, shows a fresh machine label.** This is silent and fine for a clear split — the earlier "always surface a split" instinct was over-cautious.
  - *Near-tie tiebreaker:* when the split is close (26/24 — noise at ARI 0.43, not a real majority), the side holding the **star-anchor** keeps the name. The star is the one signal in the theme that isn't noisy.
- **Starred quote in a split.** Default to **continuity**: the starred quote stays with the majority / custom-name child (P). If the machine is confident it belongs in the offshoot (Q), **surface that as a dismissible suggestion** ("this starred quote looks like a better fit for Q — move it?") — never move it silently. Rationale: the machine's theme-placement confidence lives on the churny layer (may reverse next run), and the worst failure is a starred quote *silently leaving the theme the researcher named*. Surfacing dominates both silent defaults — it captures the machine's occasional-correct insight without ever imposing it. Set a **high bar to surface** (robust, repeated dissent, not a one-run wobble) so the theme layer's noise doesn't spam suggestions.
- **Anchored theme, committed content.** A custom-named theme doesn't silently split its *committed* content; new quotes may be *suggested into* it (growth, researcher can reject). The one moment the machine must **ask rather than decide** is when a custom-named theme's **multiple star-anchors scatter** across different new themes — the anchor itself is fracturing, and no automatic rule should choose.

## 10. Failure modes and their costs

The differential treatment (freeze some, best-effort others) is justified by *what a miss costs*:

| Mechanism | If it fails | Cost | Design response |
|---|---|---|---|
| Pinned quote (frozen) | — can't miss; it's not re-derived | — | freeze |
| Fluid quote match | mark lost | low (no human state on it) | best-effort, accept |
| **Hidden** quote match | quote **reappears** unhidden | **low** (re-hide is one click) | best-effort, **accept the ~5% risk** |
| Section-name carry | — near-never (0.96) | trivial | majority map |
| Theme-name carry | name flickers / lands on wrong child | medium | star-anchor tiebreaker + bind-then-stick |
| Starred quote placement | wrong theme home | low, and *surfaced* not silent | continuity default + suggestion |

This is why **hide is not a pin**: a hide-miss costs a re-hide; a star-miss costs lost curated work. Spend the expensive mechanism (freeze) only where getting it wrong is expensive. (Optional: a lightweight *suppression marker* — position + text fingerprint — makes hide reliable without freezing/elevating it, if the ~5% reappearance is ever judged too high.)

## 11. How often each edge fires (frequency by research type)

Because of the exclusivity rule (a quote lives in exactly one place — a section *or* a theme), a starred quote's fate is set by which layer it's on, which maps to research type:

- **Section-heavy (product / usability).** Most starred quotes are section-homed → stable (0.96). Edges are **rare**; the "uncategorised starred quote" fallback almost never fires. Persistence is easy.
- **Theme-heavy (exploratory / oral-history).** Most starred quotes are theme-homed → churny (0.43). Theme-home edges are **common**; the fallback fires regularly — but "uncategorised" isn't "lost": the star guarantees the **quotes page**, so it means "pinned, not currently under a theme."

The genuinely fraught corner — a **custom-named theme with multiple starred quotes, where re-theming scatters them** — is **rare² / rare³** (custom names are rare; multiple stars in one; scatter possible). Low frequency, *maximal* stakes (most human investment) → worth a dedicated surfaced flow, not a silent heuristic, but not a common code path.

## 12. Edge-case catalogue

_Rows whose resolution says **surface** / **ask** / **dissent** describe the design-only suggestion flow (see the §9 build-status note) — not shipped behaviour. The Uncategorised-floor and named-survival rows are shipped._

| Case | Resolution |
|---|---|
| Fluid quote not re-extracted (fragile tail) | acceptable — it carried no human state |
| Pinned quote's re-extracted near-duplicate appears | dedup against the frozen copy |
| Hidden quote not re-matched | reappears; researcher re-hides (accepted) |
| Section splits | custom name → majority child; surface only if no majority |
| Section merges (two custom names → one) | genuine conflict → **surface** |
| Custom-named theme splits (clear majority) | majority child keeps name; offshoot gets fresh label (silent) |
| Custom-named theme splits (near-tie) | star-anchor decides which child keeps the name |
| Starred quote lands in the offshoot child | stays with majority by default; machine dissent **surfaced** |
| Custom-named theme's multiple star-anchors scatter | **ask** — the anchor is fracturing |
| **Named** theme drains to empty | **does not dissolve** — the human-owned container survives (to zero members), keeping its starred quotes; deleted only by the researcher |
| **Un-named** theme dissolves entirely | its pinned quotes surface in the read-only **Uncategorised floor** — never silently hidden |
| Edited-then-hidden | frozen edit retained; visibility hidden |
| Star a currently-hidden quote | un-hides + pins |

## 13. Data model — what implementers need

**Per quote:** `durable_id` (minted on first human touch, **run-independent** — so external references like board exports / clip links stay valid), `source` (`human` | `autocode`), `is_starred`, `is_edited` + `frozen_text`, `frozen_form` (verbatim span at pin-time), `is_hidden`, `tags[]`. A quote is **pinned** iff `is_starred ∨ is_edited ∨ tags` present. **`frozen_form` and `durable_id` are re-identification keys — never serialised to the `/quotes` payload or any export** (enforced + regression-pinned: `TestFrozenFormStaysOffTheExportBoundary`).

**Per section/theme:** a **durable identity** (`section#ID` / `theme#ID`) keyed to a **membership signature** (sections) or **star-anchor set + custom name** (human-committed themes) — *not* to the label; `auto_label` (machine, regenerated); `custom_name` (human, bound to the durable ID, `source=human`, sticky).

**The load-bearing fix — shipped (Phase 2).** The original rename (`HeadingEdit`) keyed on `heading_key = "section-{slug}:title"` where the slug derived from the *label*, and sections/themes upserted by *label* — so when "Checkout" drifted to "Checkout page" the system saw a **different** group, orphaning the custom name. Identity is now **re-based from the label onto membership signature (sections) / star-anchors (themes)**: sections upsert by membership (`importer.py` `_import_quotes_from_clusters`), themes by star-anchor + membership (`_match_by_anchor`), and migration `004_curation_section_identity` re-keys the reconstructable `HeadingEdit`s. This is what makes every "carry the name / carry the placement" rule above reliable.

**Matching primitive:** transcript position-overlap (≥70% char span) primary; text-similarity tiebreaker; embeddings optional — but note embedding endpoints share the same batch-invariance non-determinism as generation, so validate stability before relying on cosine.

**Hard dependency — manual re-assignment must exist first** (designed in [`design-manual-reassignment.md`](design-manual-reassignment.md)). Every "continuity by default, move on the researcher's gesture" rule in this doc assumes the researcher *can* move things by hand: **drag-and-drop a quote between sections/themes**, and **multi-select → send-to-section / send-to-theme**. This is the landing place for every surfaced suggestion — dismiss keeps it, accept drops it where the researcher chooses. Without direct manual re-assignment, "the machine suggests, the human commits" has no *commit* gesture. **(Scope correction — see the Update below.** This was originally framed as a hard prerequisite for the *whole* model; the read-only floor + named-exemption have since decoupled the **no-silent-loss** guarantee from it. Manual re-assignment is still required for *acting on* surfaced orphans/suggestions, and still earns its keep by making a *fresh* analysis's mis-groupings fixable — but it no longer blocks correctness.)

> **Update (this branch) — correctness no longer blocks on Phase 0.** The read-only **Uncategorised floor** plus the **named-group retire-exemption** now guarantee *no silent loss* without any manual-reassignment UI: a dropped pinned quote is always either kept in its (named) container or surfaced in Uncategorised. Phase 0 is still required to *re-file* an orphan out of Uncategorised and to *commit* a surfaced suggestion — but it is no longer load-bearing for the "nothing vanishes" guarantee, only for "the researcher can act on what's surfaced." Empirically demonstrated by a forced-orphan repro against the real importer + `/quotes`.

## 14. Worked example

Researcher analyses **3 interviews**. Stars 5 quotes, edits 2, adds 8 tags, hides 3, renames a section "Basket" → "Checkout", renames a theme "Early experience" → "Onboarding friction". Exports two starred quotes to a board.

Adds **3 more interviews**, re-runs:

- The 5 starred + 2 edited quotes are **frozen** — they re-appear verbatim, in place; the board links still resolve. The 8 tags ride on their (pinned) quotes.
- The 3 hidden quotes are **re-matched and stay hidden** (say 3/3 this run; on a larger add, ~1 in 20 might resurface → re-hide).
- "Checkout" section: new quotes flow in, machine wants to call it "Checkout page" — **suppressed**; the researcher's "Checkout" still shows.
- "Onboarding friction" theme: the theme layer churns; but the theme is found by its **star-anchors**, keeps the custom name, and its starred quotes stay in it.
- Edge: the machine splits "Onboarding friction" 30/20. Majority child keeps "Onboarding friction"; offshoot shows a fresh label. One starred quote landed in the offshoot → surfaced: *"move to the new theme?"* — researcher dismisses; it stays. *(The surfacing step is design-only — see §9; today the quote silently stays with the majority.)*

Nothing the researcher did vanished or moved without a prompt. New structure appeared around their committed work.

## 15. Acceptance / round-trip test

The executable contract (extends the round-trip test in the parent doc):

1. Boot a fixture project. Apply: star N, edit M, tag K, hide J, rename one section, rename one theme.
2. Add sessions; re-run.
3. Assert: **every** starred/edited quote present, in frozen form, with tags intact; renamed section shows the custom name; renamed theme shows the custom name and still contains its starred quotes; hidden quotes still hidden (allow the documented best-effort miss rate, asserted separately). Then exercise a forced theme split and assert the **inheritance** behaviour of §9 — majority child keeps the name; a near-tie is decided by the star-anchor (*asserted today:* `test_majority_child_keeps_id_on_split`, `test_anchor_matcher_follows_plurality`). The **surfaced-suggestion / dissent** behaviour of §9 is design only — **not built and not asserted yet**; this step does not cover it.

If this fails, the persistence contract is broken — there is no "passes most of the time" version of not losing a researcher's work.

## 16. Open questions

- **Transcript edit vs. freeze.** If the researcher later corrects the transcript under a pinned quote, does the frozen form update? (Lean: freeze holds; correction offers a per-quote re-sync.)
- **Hide: best-effort vs. suppression-marker.** Ship the accepted-~5%-reappearance best-effort, or the lightweight reliable marker? (Lean: best-effort first; marker if reappearance annoys.)
- **Surfacing bar.** How confident/stable must a machine "move your starred quote" dissent be before it interrupts?
- **Durable ID after unpin.** _Resolved (Design-Q1):_ un-pin **scrubs** `durable_id` + `frozen_form` (a `frozen_form` is a re-identification key — don't keep a frozen copy on a deliberately un-pinned quote); re-pin mints fresh. Tested (`test_unpin_scrubs_frozen_form_then_repin_remints`).
- **Embedding tiebreaker stability** under batch-invariance — un-probed.
- **Saturation-proxy governor** for lock/unlock lives at the quote layer, not the theme layer (per the parent doc) — how it interacts with pins is unspecified.
