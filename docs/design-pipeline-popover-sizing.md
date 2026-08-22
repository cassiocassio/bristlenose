---
status: built (unreleased)
last-trued: 2026-08-22 — written as a spec, agreed, built the same day; §7 and §8 rewritten from the as-built
trued-against: working tree on 2026-08-22
---

# The diagnostic popover's height — content, capped

_Scoped 22 Aug 2026, from the observation that the popover's height is arbitrary:
four refusals and fifty-five failures are served the same box. Companion mockup:
[`docs/mockups/pipeline-popover-sizing.html`](mockups/pipeline-popover-sizing.html) —
every case below is drawn there, twice, at native size. This doc is the build
spec; the mockup is the acceptance target. Parent doc:
[`design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md),
whose two fixed-size claims this supersedes — **done, both rewritten** (see §8)._

> **As built, 22 Aug 2026.** All three §7 questions were answered as
> recommended: ceiling stays 320, no pinned overflow row, no artificial floor.
> The mechanism is `ViewThatFits` and it works — see §7 for the one thing that
> was genuinely uncertain going in and how it resolved.

---

## 1. What it was, and why the number was a fossil

Both presenters hard-coded the same pair:

| Presenter | Was | Path |
|---|---|---|
| SwiftUI sidebar (**shipping**) | `ProjectRow.swift:423` | `.padding(16).frame(width: 360, height: 320)` |
| AppKit sidebar (flag, default off) | `ProjectSidebarOutline.swift:1829` | identical |

`ProjectDiagnosticPopover`'s own docstring said *"the presenter supplies the
size"* — which is why the magic pair lived in two files with nothing keeping
them equal.

**320 was never chosen for the content.** It was a mitigation for an
NSPopover/SwiftUI **ProgressView** constraint-pass livelock that required a
force-quit (QA, 20 Apr 2026). The instruction attached to it was emphatic: the
frame must stay fixed, *no `idealHeight`, no `.fixedSize`*.

That ProgressView belonged to the live activity pill. The pill was deleted
(`git log --diff-filter=D -- desktop/Bristlenose/Bristlenose/PipelineActivityItem.swift`
→ *"desktop: remove the per-project pipeline toolbar pill"*). What remains
renders only terminal states — `.failed`, `.completedPartial`,
`.failedWithDiagnostic` — and contains **no ProgressView at all**: one `Spacer()`
in the header, one `ScrollView` around the body.

**The content is also static for the popover's whole lifetime.** `liveData` is
read in exactly one place, `ProjectDiagnosticPopover.swift:218`, inside
`copyDiagnosticForCurrentState()`. Nothing in the rendered body observes it. The
body is a pure function of a terminal `PipelineState`.

Those two facts together are the safety argument: sizing here is a **present-time
decision, computed once and never animated**, which is a different thing from the
*resize animation* the fixed frame was defending against. The mitigation outlived
its trigger, and that is precisely why it now reads as arbitrary.

## 2. The rule

Three lines, and the whole spec is downstream of them:

1. **Width stays nailed at 360.** It is the column the copy is written to. Only
   the height moves.
2. **Height is the content's height.** No floor beyond the header chrome.
3. **320 becomes a ceiling, not a height** — and the scroller appears *only* when
   that ceiling is actually reached.

This is the posture the Settings window already takes, not its machinery. We are
not importing `SettingsWindowController`, `refitToContent()`, or ceiling
arithmetic. Those exist because Settings panes change shape while on screen; this
popover cannot.

## 3. Mechanism

`ViewThatFits` — already a house idiom (`WelcomeHomeView.swift:579`,
`WelcomeIllustrations.swift:228`, `WelcomeDegradationLab.swift`), so this is
reuse, not novelty.

```swift
// Inside ProjectDiagnosticPopover — NOT in the presenters.
ViewThatFits(in: .vertical) {
    body                    // unscrolled: chosen when it fits → height = content
    ScrollView { body }     // fallback: chosen when it doesn't → height = ceiling
}
.frame(width: Self.width)          // 360 − the 16pt padding the presenter adds
.frame(maxHeight: Self.ceiling)    // 320
```

No measurement, no `@State`, no round-trip, no feedback edge. The fit test runs
in the same layout pass that positions the view, so there is no first-frame jump
to animate — which is what keeps §1's livelock class out of reach.

Both presenters then drop `.frame(width:height:)` and keep `.padding(16)`. The
sizing constants move into the view as `private static let`, so there is one of
each.

## 4. Behaviour — the ladder

Heights are **mockup measurements**, not native truth; they establish the shape
and the fits/scrolls verdict, and get confirmed against the real app in §7. Case
letters match the mockup.

| # | Scenario | Source | Today | Target | Scroller |
|---|---|---|---|---|---|
| A | Degraded — no summary on the wire | `.failed(message, category)` | 320 (**221 empty**) | 99 | no |
| B | One refusal | 1 bucket, 1 row | 320 (**221 empty**) | 99 | no |
| C | Four refusals | the *New Project 2* screenshot | 320 (**147 empty**) | 173 | no |
| D | Typical partial | `showcase_typical_partial` | 320 (**105 empty**) | 215 | no |
| E | Seven refusals | the *folder-of-horrors* screenshot | 320 (34 empty) | 286 | no |
| F | Three buckets, mixed categories | `showcase_failed_multi_category` | 320, scrolls | 320 | yes |
| G | Truncated at the wire cap | `showcase_truncated_varied` | 320, scrolls | 320 | yes |
| H | Worst case the wire permits | 5 buckets × 10 + overflow | 320, scrolls | 320 | yes |

Case E is the tell: 320 was tuned around roughly *seven wrapping rows*, which is
why the folder-of-horrors popover sits almost exactly flush while the four-row
one leaves nearly half the box empty. **320 is a good ceiling and a bad floor.**

The worst case is bounded and knowable: five buckets (`PipelineSummary.allBuckets`
— ingest, transcripts, topics, quotes, themes) × `STAGE_FAILED_MAX = 10`
(`bristlenose/events.py:47`) plus one overflow row each. Scrolling genuinely has
to exist; it just has to stop being the only mode.

## 5. Edge cases

- **E1 · At the ceiling — the sliver is the affordance.** The cut lands *inside*
  a row, not on a boundary. We deliberately do **not** snap to whole rows: a
  half-visible row is the thing that says "there's more". The MCP Agents register
  can snap because its pitch is a fixed 32pt; ours cannot, because reasons wrap.
- **E2 · One block taller than the ceiling.** `CAUSE_MESSAGE_MAX` is 4096 bytes
  (`events.py:37`), so a raw provider error in the degraded body can exceed the
  ceiling on its own. Nothing is clamped — the text is the payload; it scrolls.
- **E3 · German chrome, and now German rows.** The header sits *above* the
  scroll region, so if "Teilweise abgeschlossen" + "Protokoll anzeigen" + the
  copy button wrap, they take room from the body rather than from the ceiling.
  **The reason column now moves too — this changed on 22 Aug 2026, after this
  section was first written.** It used to be pinned English: `Cause.message` is
  English on the wire by design and carried no discriminator, so the popover
  had nothing to key a translation on and rendered it raw. `Cause.reason` now
  carries `UnusableReason` and the pane resolves
  `desktop.pipeline.diagnostic.reason.*` in all 21 locales
  (`design-pipeline-diagnostic-popover.md`, 22 Aug entry). This section
  predicted the consequence and it has arrived: **rows are taller in some
  languages than in English, and the ceiling must absorb it.** Measured 22 Aug
  2026 — the longest English reason is **55** characters (`no_audio`),
  against **70** in German and **74** in Catalan, so budget about
  **1.35×** the English column: a reason that sits on one line in English
  wraps to two elsewhere, and a bucket of ten does it ten times. Measure the
  ladder against a non-English locale, not the 125% text toggle alone. Re-derive
  rather than trusting these numbers once more reasons land — they come from
  `pipeline.diagnostic.reason` in `bristlenose/locales/*/desktop.json`.
- **E4 · The overflow row below the fold.** "… and 4 more failures truncated" is
  the one row that says the list is *incomplete*, and it is the row most likely
  never to be read. Open question — §7.
- **Larger accessibility text.** Rows grow, the ceiling holds, the scroller
  appears. Nothing is clamped. The mockup has a 125% toggle.
- **Bucket count line.** `bucketCountLabel` only renders above two failures
  (`ProjectDiagnosticPopover.swift:149`), so per-bucket header height is not
  constant — one more reason the height cannot be arithmetic.
- **DEBUG swatch modes.** `showcase_all_glyphs` and `showcase_all_states` are the
  tallest content in the app. They must scroll, not clip.

## 6. Failure modes this build must not walk into

1. **The greedy ScrollView.** `ScrollView { body }.frame(maxHeight: 320)` reads
   like the fix and reproduces today's bug exactly — SwiftUI's `ScrollView` is
   greedy along its scroll axis and claims the whole ceiling for four rows. This
   is written down one floor up already, at
   `MCPAgentsSettingsView.swift:458`. Drawn as an anti-pattern in the mockup.
2. **A greedy first candidate.** If the unscrolled candidate contains anything
   vertically flexible, it always "fits" and `ViewThatFits` never engages — the
   fallback becomes dead code. `WelcomeDegradationLab.swift:484` records this
   failure by name. `bucketsBody` is a `VStack` of `Grid`s and `Text` today, which
   is safe; adding a `Spacer()` or `maxHeight: .infinity` to it would silently
   disable the whole mechanism.
3. **`.fixedSize` inside a candidate.** It forces the text to demand its full
   height and ignore the bounds, breaking the fit test —
   `WelcomeHomeView.swift:629`.
4. **A measure-then-resize round trip.** A `@State` height starting at 0 gives a
   visible jump on open, and feeding a measured height back into the measured
   subtree is the shape that produced the 20 Apr 2026 livelock. `ViewThatFits`
   avoids both by deciding in-pass. If it turns out not to work, the fallback is
   `onGeometryChange` on a width-pinned, height-unbounded copy of the body — but
   the measured view must never be the one the resulting frame is applied to.
5. **Two presenters drifting.** Solved by moving the constants into the view. A
   presenter that still passes a height must fail review.
6. **The scroller gutter — unverified.** With *Always show scroll bars* set in
   System Settings, a legacy scroller claims about 15pt. Which way that lands
   was asserted here before it was checked, and the assertion was probably
   wrong: SwiftUI's `ScrollView` insets its content for a legacy scroller
   rather than overlaying it, so the likely effect is not text sitting under a
   scrollbar but the reason column **narrowing by ~15pt**, re-wrapping, and
   getting taller — which can push a case that fitted over the ceiling. Benign
   either way (it scrolls), but it means the fit decision is not scroller-
   independent. Nobody has run the app with that setting on. The mockup has a
   toggle for the overlap question; the re-wrap question needs the real app.

## 7. Decisions taken, and the one real unknown

All three questions answered as recommended, 22 Aug 2026:

1. **Ceiling stays 320**, now as a maximum rather than a height.
2. **No pinned overflow row.** A real question, but not a sizing question.
3. **No artificial floor.** The header chrome is the floor; the thinnest states
   land around 100pt and read fine.

**The unknown was whether `ViewThatFits` would receive a definite height
proposal at all.** With a `nil` proposal in the measured axis, the first
candidate trivially "fits" and the ladder is dead — tall content would render
un-scrolled and clip at the ceiling with no scroller and no error. Reasoning
about SwiftUI's proposal semantics could not settle it, so it was measured
instead: `theCeilingHolds()` builds a ten-failure summary with wrapping messages
and asserts the popover measures *exactly* the ceiling. It does. The
`.frame(maxHeight:)` bound reaches `ViewThatFits` as a definite proposal, the
scrolled candidate is chosen, and nothing clips.

That test is the reason the mechanism is trustworthy, and it is why the suite
is worth having at all here — see §8.

## 8. As built

**Changed:**

| File | What |
|---|---|
| `ProjectDiagnosticPopover.swift` | Owns `width` / `ceiling` / `inset`. `body` is `ViewThatFits` over a shared `shell`; header and body extracted so the header never scrolls. |
| `ProjectRow.swift` | Presents the view bare — no padding, no frame. |
| `ProjectSidebarOutline.swift` | Same, plus `host.sizingOptions = .preferredContentSize` so the hosting controller publishes the size NSPopover reads. |
| `DiagnosticPopoverSizingTests.swift` | New. Six cases. |

**The tests pin the decision, not the pixels.** They measure through
`NSHostingController.view.fittingSize` — deliberately, because that is the same
number `NSPopover` sizes from, so a green suite is evidence about the shipped
mechanism rather than about a parallel calculation. Every assertion is
relational: *short is shorter than the ceiling*, *three failures are taller than
one*, *ten wrapping failures measure exactly the ceiling*, *one failure and five
do not measure the same*. No point value is asserted anywhere; those are
snapshots of a font metric and pinning them would lock the implementation and
break on the next system font revision.

Between them they catch both silent failures: `ViewThatFits` choosing the greedy
`ScrollView` for everything (every case measures exactly the ceiling — the fixed
box, back again) and choosing the un-scrolled candidate for everything (tall
content overshoots and clips, no scroller). Both render without error, which is
why a test that only checks "it renders" would pass through either.

**Verified:** the six sizing tests pass; the full Swift suite is 1287 cases
green; `TEST BUILD SUCCEEDED` for both targets.

**Still owed — the look:** the tests exercise the AppKit hosting path. The
*shipping* sidebar is the SwiftUI `.popover`, which sizes from the same layout
but has not been seen by eye. Per the house rule that a test suite hides the
rendered surface, run the fixtures through the real `.app` and look — at minimum
`showcase_typical_partial` (thin), `showcase_failed_multi_category` (the
ceiling), `showcase_truncated_varied` (the overflow row), and the
`folder-of-horrors` corpus that produced the screenshots this started from.

## 9. References

| Thing | Where |
|---|---|
| The view | `desktop/Bristlenose/Bristlenose/ProjectDiagnosticPopover.swift` |
| Presenters | `ProjectRow.swift:423`, `ProjectSidebarOutline.swift:1829` |
| Fixture scenarios | `desktop/Bristlenose/Bristlenose/DiagnosticFixture.swift` |
| Wire cap | `bristlenose/events.py:47` (`STAGE_FAILED_MAX`), `:37` (`CAUSE_MESSAGE_MAX`) |
| Refusal copy | `bristlenose/refusals.py` |
| Scroller-presence precedent | `MCPAgentsSettingsView.swift:458` |
| `fittingSize` precedent | `SettingsView.swift:176` (`refitToContent`) |
| `ViewThatFits` traps | `WelcomeHomeView.swift:629`, `WelcomeDegradationLab.swift:484` |
| Sizing tests | `desktop/Bristlenose/BristlenoseTests/DiagnosticPopoverSizingTests.swift` |
| Mockup | `docs/mockups/pipeline-popover-sizing.html` |
