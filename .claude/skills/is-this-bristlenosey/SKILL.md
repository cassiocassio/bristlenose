---
name: is-this-bristlenosey
description: "Does this fit how Bristlenose already does it? Before designing or reviewing a feature, find its nearest live, sanctioned sibling in Bristlenose and check the proposal follows that sibling's mechanism (surface, precedence, data path, store, strings, tests), naming every departure and every invention. Use when planning or reviewing a feature, or when asked 'is this bristlenosey?', 'does this fit?', 'how does BN already do this?'. For a genuinely new kind of thing with no sibling, it says so and hands it to the platform-taste reviewers."
---

# Is this Bristlenosey?

Most features are not new design problems. They are one more instance of something Bristlenose
already does: one more activity on a project's status line, one more lens, one more background job,
one more string, one more format. The Bristlenose answer is usually the one its nearest live sibling
already gives. Reviewing such a feature from first principles ("how would Photos do it?") produces
confident, well-argued, wrong advice: it re-litigates decisions the codebase has already taken.

Learned 14 Oct 2026, when a new feature was reviewed as a new UX by three reviewers who argued it
away from the surface its shipped siblings use; the owner's correction was to fit it into the
standard Bristlenose frameworks. (The case itself is kept out of this skill so it can serve as a
test.)

## The method

1. **Name the kind, in Bristlenose's terms.** Answer the domain file's classification questions
   *before* reading how the proposal describes itself, so the kind is not chosen to fit the
   proposal. If two kinds fit, map against both and list the choice as an open call.
   **Gates:** set *removable* gating aside (a feature flag, "rough, on main", a temporary
   Diagnostics gate) and review the feature as it will ship. Keep a gate that is the surface's
   permanent home: App-Store-hidden diagnostics chrome (English by decision), export mode,
   DEBUG/`--dev`-only tools, the distribution channel. Those decide strings, privacy and placement.
2. **Find the nearest live, sanctioned sibling**, from the domain file or the ruling doc below, then
   **read its code**: the file points, the code is the evidence. Exclude sealed, frozen, archived or
   retired-by-doc surfaces (the static renderer `s12_render/`, the vanilla `theme/js/`,
   `docs/archive/`). Where the code and its ruling doc disagree, that is an open call, not a
   precedent. If a governing design doc is named, read it: the decision may already be open or taken.
3. **Map each part of the proposal onto the sibling**: surface, placement/precedence, data path and
   transport, store, wording and length, strings and locale enrolment, tests, export/privacy
   classification. Mark each part:
   - **follows**: the same mechanism;
   - **departs**: "the sibling does X; we depart because Z". If you cannot write Z, mark it
     **departs, unjustified**: that is a finding, never a quiet "follows";
   - **invents**: a new surface, vocabulary, transport or type where a sibling exists. A finding;
   - **new kind**: no sibling exists at all. Not a defect: it is reviewed on its merits.
4. **Carry the sibling's rules over** (the domain file lists them): what a glyph, ring or colour
   means there, what may never be shown, budgets, precedence, privacy. A rule that looks wrong in
   the sibling is a finding *against the sibling*, not a requirement on the proposal.
5. **Where siblings disagree, do not choose.** Name both, say which the proposal follows, and list it
   as an open call for the owner.
6. **Verdict**: *Bristlenosey* / *mostly* / *not yet* / *new kind*, with the part-by-part table.
   Parts marked **invents** or **new kind** go to platform-taste review (what-would-gruber-say,
   ux-critique, mac-arsed-mac-app).

**Using the table in other reviews.** If this skill's table is handed to other reviewers, give it
only to lanes that check claims against the repo, labelled *claims to verify*, never to a
fresh-eyes lane: a sibling's own defects must still be catchable. (It is not wired into
/usual-suspects yet.)

## Output

```
Kind: <one line, in BN terms>   (two kinds fit? say so)
Sibling(s): <feature — code symbol — governing doc>
| Part | Proposal | Sibling | follows / departs (why) / departs, unjustified / invents / new kind |
Open calls: <only if siblings disagree or the kind is ambiguous>
Verdict: …
```

## Domains

Read only what the question touches.

**Domain files** (the knowledge was scattered, so it was inventoried):

- `domains/progress.md`: work in flight, activity, waiting. *Drafted*, smoke-tested only (below).

**Ruling docs** (one doc already rules; treat it as the sibling register). Paths under `docs/`:

- Formats → `design-shared-formats.md`
- Gates → `design-feature-flags.md`
- Strings and i18n → `design-i18n.md` §"Which surfaces are targets", `platform-text-map.md`, `glossary.md`
- Messages and errors → `design-pipeline-diagnostic-popover.md`
- Credentials → `design-keychain.md`
- Providers and model switching → `design-cli-provider-selection.md`, `bristlenose/llm/CLAUDE.md`
- Lenses → `design-lens-template.md` and the shipped lenses
- Sidebar and project rows → `design-desktop-project-status.md`, `design-desktop-sidebar-appkit.md`
- Menus and commands → `design-desktop-menu-actions.md`
- Keyboard → `design-keyboard-shortcuts.md`, `design-keyboard-navigation.md`
- Edits to researcher data → `design-undo-catalog.md`, `design-undo-debt.md`
- Exports and privacy → `design-export-html.md`, `design-localhost-auth.md`, `methodology/consent-gradient.md`
- Cross-platform → `design-modularity.md`, `design-platform-policy.md`
- Tests and gates → `design-test-philosophy.md`, `testing/`
- Analysis lifecycle → `design-analysis-lifecycle.md`, `design-pipeline-resilience.md`
- Identity → `design-project-identity.md`, `design-people.md`
- Settings → `design-desktop-settings.md`
- Terminal output → `design-cli-formatting.md`, `design-cli-just-works.md`
- Motion and visual tokens → `design-motion.md`, `bristlenose/theme/CLAUDE.md`

**Next domain file, when a case calls for it:** background jobs in serve. No ruling doc, but robust
code (`server/scene_strips.py` `SceneStripJob`, `server/screen_text_job.py`, AutoCode's task set) and
rules that each new job re-derives from gotchas: defer during a run, the rerun flag, failures recorded
so polls do not loop, strong task refs, never cache a short read.

## How a domain file earns trust

A domain file is *drafted* until it has been tested properly, and the evidence is stated in the file.

- **Smoke test (what progress has had):** a few questions whose answers are left out of the file,
  answered by fresh agents with only the skill and the code. Weak: the rules may name the answer,
  the sample is tiny, and there is no control.
- **To call it *built*:** a control arm (the same questions without the skill, several runs each,
  report the difference); time-travel questions (past decisions, especially reversed ones, asked in
  a worktree at the commit before the decision, so the answer is physically absent); questions
  where the obvious sibling is wrong or the call is open; adversarial proposals that look
  Bristlenosey but break a rule. Grade the cited evidence (do the symbols exist, are the claims true),
  not only the conclusion.

## Maintaining a domain file

- Anchor to symbols and docs, never line numbers; say which surface a symbol belongs to when there
  are two (the AppKit and SwiftUI sidebars differ).
- Every rule cites where it is ruled (doc, code comment) or the incident that made it.
- Record disagreements between siblings as open calls in that domain's file; resolve them only when
  the owner does.
- Keep some known answers out, to test with.
