# Test Philosophy & the James Bach Reviewer

_May 2026. Companion to `design-test-strategy.md` (which is the per-layer audit). This doc is the **decision framework** — how to choose the right level of testing for a given change, and the agent role that should be applied at planning time._

## TL;DR

- **A test earns its place by encoding an invariant the team cares about, in a venue where regressions would otherwise be silent.** Everything else is ceremony.
- **The TestFlight cohort is the integration test** — name it, don't hide it. Don't write XCUITest to re-cover what the cohort already sees.
- **Parsimonious testing**: write the test that answers a specific risk question at the cheapest layer that can answer it.
- **The Python and TS test surfaces stay as they are.** This framework applies *prospectively* to new changes and especially to **Swift / desktop** + **cross-surface flows**, where conventions haven't settled.
- **A planned reviewer agent, `what-would-james-bach-say`** (not yet implemented), runs alongside the other `/usual-suspects` reviewers. Specialist in test placement, scope, and proportion — anti-maximalist, anti-piecemeal.

## Why this doc exists

Bristlenose has accumulated four test surfaces:

- **Python** (~2,300 pytest tests) — pipeline, server, analysis, LLM
- **TypeScript / React** (~1,300 Vitest tests) — frontend components, stores
- **Playwright** (`e2e/`) — browser-level integration
- **Swift** (~150 `@Test` declarations, not all yet wired — the `BristlenoseTests` target isn't connected to the Xcode project as of May 2026; see [desktop/CLAUDE.md](../desktop/CLAUDE.md#testing))

The Python and TS layers grew with sensible defaults baked in from the start — the tooling pulled their philosophy along with them (pytest, Vitest, RTL ship opinions). The Swift layer is growing **piecemeal, per code surface, per dev environment**: tests appear next to the file the author was thinking about, not as the output of a deliberate "where does this behaviour belong on the pyramid?" decision.

There is no analogue for the moment in planning when someone asks **"what's the right amount of test for this thing, and at which layer?"** That question is the test-tzar role. This doc:

1. States the philosophy (the synthesis of James Bach + indie-Mac practice)
2. Scopes the framework (prospective, not retrospective)
3. Lays out the options at each layer
4. Gives a decision framework for routing test work
5. Specifies the `what-would-james-bach-say` review agent

## Philosophy: tests encode invariants worth defending

The doc's namesake is **James Bach** ([Satisfice](https://www.satisfice.com/), [_Lessons Learned in Software Testing_](https://www.amazon.com/Lessons-Learned-Software-Testing-Context-Driven/dp/0471081124) with Kaner & Pettichord) — context-driven testing founder, Rapid Software Testing methodology. Anti-dogma, pro-thinking-about-test-value. The voice the agent borrows.

Bach's school and the indie Mac tradition (Simmons, Arment, Shipley) look like opposites — one methodology-rich (Heuristic Test Strategy Model, Rapid Software Testing), the other methodology-silent. The deeper agreement: **a test earns its place by encoding an invariant the team cares about, in a venue where regressions would otherwise be silent.** Everything else is ceremony. Bach attacks scripted procedure; indies attack scripted procedure by not writing about it. Same target, different prose styles.

The synthesis is **parsimonious testing**: write the test that answers a specific risk question at the cheapest layer that can answer it, and let the TestFlight cohort be the integration harness for everything else.

### Principles the reviewer quotes

1. **Test where the regression would be silent.** Parsers, persistence, state machines, schema round-trips, money/time/PII handling. If a human eyeballing the UI would catch the break in one session, a unit test is *speculative generality* (Fowler) — the cohort sees it Tuesday. If nobody would notice for a month, the test pays for itself.

2. **Match the test to the smallest layer that proves the invariant.** A pure-function bug gets a pure-function test, not an XCUITest. *Simple vs. easy* (Hickey): XCUITest is easy because it mimics the user; it is not simple because it braids rendering, timing, and animation into one assertion. Indie consensus on XCUITest fragility ([swiftyplace](https://www.swiftyplace.com/blog/testing-in-ios-development), [Bitrise](https://bitrise.io/blog/post/snapshot-testing-in-ios-testing-the-ui-and-beyond)) is the empirical version of this.

3. **Snapshot tests are a consolation prize, not a strategy.** Point-Free's own issue tracker ([#237](https://github.com/pointfreeco/swift-snapshot-testing/issues/237), [#732](https://github.com/pointfreeco/swift-snapshot-testing/issues/732), [#921](https://github.com/pointfreeco/swift-snapshot-testing/issues/921)) documents the SwiftUI-rendering tail. Use them where layout *is* the invariant (export HTML, server-rendered status page). Don't use them as a substitute for thinking about what the test is for. *Hoare's test*: a snapshot that passes because the diff is small isn't evidence of correctness, it's evidence of unchanged pixels.

4. **The cohort is the integration test — name it, don't hide it.** Internal TestFlight + five-act cohort calls are the harness for UX, perf-feel, copy, and cross-stack timing. This is Bach's "skilled tester > scripted procedure" delivered by the people who'll actually use the thing. Document what the cohort covers so nobody writes an XCUITest to re-cover it. Marco Arment and Underscore have been operating this way for years ([Under the Radar](https://www.relay.fm/radar)).

5. **Add the third caller before you add the abstraction.** *Rule of Three* (Fowler / Roberts) applies to test helpers as hard as to production code. Two similar specs are duplication; three are a fixture. Premature test-harness work is *tests added for the test framework* — a tell, not a feature.

### What this rejects

- **Maximalist coverage targets.** Knuth's 97% applies: most code is not where the risk lives. A coverage number is a *Parkinson bikeshed* — easy to have opinions about, orthogonal to whether the dangerous invariants are defended. Cursor's auto-generated coverage failure mode ([Salesforce case study](https://engineering.salesforce.com/how-cursor-ai-cut-legacy-code-coverage-time-by-85/), [Cursor forum thread](https://forum.cursor.com/t/test-coverage-doesnt-work-on-cursor/51565)) is the modern empirical version.
- **Anarchic "tests are pointless" posturing.** Indie silence is not indie nihilism; [Brent Simmons tests his parsers](https://github.com/brentsimmons) where regression would be silent. Skipping tests on parsers, persistence, or PII handling because "the cohort will catch it" is an *ETTO violation* (Hollnagel, Efficiency-Thoroughness Trade-Off) at a boundary — irreversible consequences (data loss, leaked PII) bow to thoroughness, not parsimony.
- **Rip-and-replace test-framework migrations.** Swift Testing for new code, XCTest where it works. Migration is not a feature. Indie consensus ([viesure](https://viesure.io/modern-swift-unit-testing/developer/), [Mobile Dev Diary](https://www.mobiledevdiary.com/posts/series/swift-testing-vs-xctest/6-parametrized-tests/)).

The test that earns its keep answers a specific question about a specific risk at the cheapest layer that can answer it. Everything else is the cohort's job.

## Scope of this framework — prospective, not retrospective

**The mature Python and TS layers stay as they are.** They already satisfy the philosophy. The tool-bound conventions (pytest, Vitest, RTL) are doing the philosophical work without ceremony. Re-deriving those opinions buys nothing, and disturbing settled layers risks introducing the very brittleness the Juju scar warns against.

This framework — and the Bach reviewer — applies **prospectively, per change**. The deliberate effort is reserved for:

- **Swift / desktop** — where conventions haven't settled and tests are accreting piecemeal
- **Cross-surface flows** — which no layer currently owns
- **New changes on any layer** — including Python and TS, because piecemeal drift can happen anywhere

**Scope rule for the reviewer (resolves the cross-layer ambiguity):** the Bach reviewer comments on *the placement of new tests* on every layer (Python, TS, Swift), but does not re-audit existing tests on the mature layers. The lens is "is this new test at the right level?" not "should those 2,300 existing pytest tests be reorganised?" If a Python or TS test surface starts misbehaving (slow suites, flaky runs, refactor-blocking brittleness), revisit then — driven by a real symptom, not by this doc.

## Layer options

Each test type has a sweet spot. Pick the *highest* layer that gives you confidence cheaply, and the *lowest* layer for things that need exhaustive enumeration.

### Python

- **pytest unit** — pure functions, stage logic, model validation. Default for everything backend.
- **pytest + FastAPI TestClient** — HTTP integration. Hits real SQLite, real handlers, mocked LLM.
- **pytest subprocess** — CLI smoke (`bristlenose run /tmp/fixture`). Slow, rare, high signal.

### TypeScript / React

- **Vitest pure-function** — stores, utilities, reducers, format helpers.
- **Vitest + React Testing Library** — component behaviour from user perspective (role/text/label queries). Default for components.
- **Vitest + router** — `createMemoryRouter` for navigation behaviour without browsing.

### Browser (Playwright)

- **Smoke E2E** — full stack, real Chromium/WebKit, 5–15 tests max. Real bugs only; not a unit-test replacement.
- **Allowlist discipline** — every suppression registered in `e2e/ALLOWLIST.md` with a category. Drift dies in CI.
- **Don't measure DOM with `networkidle`** — see the SPA-readiness gotcha in CLAUDE.md.

### Swift (desktop)

**The indie-Mac default pattern (Simmons, Arment, Hansmeyer):** model-layer unit tests where regressions are silent (parsers, persistence, state machines) + snapshot tests for layout-sensitive views + TestFlight beta cohort as the integration test. XCUITest is the option teams regret — slow, flaky on CI, simulator-bound. Our cohort approach (internal TF) maps to this directly. Default to the indie pattern; reach for XCUITest only when a *named regression* recurs.

- **Swift Testing unit** — pure types, `ProjectIndex` mutations, `UndoableRemovalStore`, redactors, env builders. Default. Currently the dominant layer.
- **Swift Testing + factored helpers** — pull SwiftUI decision logic into pure functions (e.g. `DropDecision.evaluate(items:target:) -> Outcome`) so it's testable without `XCUIApplication`. Underused; high leverage. Encoded as a convention in [`desktop/CLAUDE.md`](../desktop/CLAUDE.md#testing): *if a SwiftUI view is making a decision, the decision belongs in a testable helper, not in the view*. **Prerequisite:** `SidebarDropDelegate` (and similar types nested in `ContentView.swift`) are currently unreachable from any test target — the factoring isn't optional, it's the prerequisite for any unit test of view decisions. Also see the unwired-target caveat in [desktop/CLAUDE.md](../desktop/CLAUDE.md#testing).
- **Snapshot tests** ([pointfreeco/swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing)) — warranted only for layout-sensitive components where pixel/structure breakage would otherwise go unnoticed. Maintenance tax is real (SwiftUI rendering long tail — see Principle 3). Adopt selectively, not by default. Narrow lane in Bristlenose: maybe `NavBar`, `RemoveToast`, server-rendered status page.
- **XCUITest (`BristlenoseUITests` target — not yet created)** — drives the real `.app` via accessibility tree. The only thing that can verify menu-item enable state, toast auto-dismiss timing, `NSUndoManager` Edit-menu labels, drop affordance visual state, and Cmd+Z fall-through. Real cost: a target, CI runner time, a flake budget. Earn it through a named regression.
- **Manual one-offs** — true Finder→app drags, "Reveal in Finder" effect, real iCloud eviction. Synthesising these from XCUITest needs `osascript`/`CGEvent` and isn't worth it for 2–3 cases.

### Cross-surface (the experience layer)

No layer currently asserts: *user drops a folder of recordings, project appears in sidebar, run starts, completes, dashboard renders, user renames, user closes app, reopens, project still there, locate-when-moved works.* End-to-end-as-the-user is owned by nothing because it crosses Swift + Python + React. Options:

- **Playwright + scripted Swift harness** — Swift side exposes an XCUITest entry that does the desktop bits; Playwright takes over once the WKWebView is up. Real but fragile.
- **Manual scripted walks** (current state) — checklist in handoff, human runs it. Cheap, doesn't catch regressions between runs.
- **Cohort dogfooding** as the actual signal (Principle 4) — this is what we're doing for TF.

For an alpha-stage single-maintainer project, **scripted manual walks + the TestFlight cohort are the right level** for cross-surface — but the absence of automated coverage should be a deliberate choice, not an accident. Revisit if cohort feedback surfaces recurring cross-stack regressions, or post-TF when a contributor lands.

## Decision framework

Given a change, ask in order:

1. **What's the user-visible invariant this protects?** If you can't state one, you don't need a test.
2. **Would the regression be silent?** (Principle 1) If a human eyeballing the UI catches it in one session, the cohort is enough. If nobody notices for a month, the test pays for itself.
3. **What's the cheapest layer that proves it?** (Principle 2) Pure function > component > integration > browser/UI automation.
4. **Will this test survive a reasonable refactor?** If a rename or restructure breaks it without changing user behaviour, it's testing the wrong thing.
5. **Is there exhaustive enumeration to do (matrix of inputs)?** That's unit territory — push it as low as possible.
6. **Is this a cross-surface flow?** Default to manual + documented walk + cohort, unless this flow is regression-prone enough to justify the wiring (Principle 4).
7. **Is the change Swift?** Default has historically been "add to nearest `*Tests.swift`." Pause and check if the logic should be factored out for unit testability instead, and whether anything in this change is only reachable via XCUITest (and if so, whether a named regression earns that target).

## The `what-would-james-bach-say` reviewer

**Role:** a reviewer agent that runs alongside `code-review`, `perf-review`, `security-review`, `a11y-review`, etc. in `/usual-suspects`. Specialist in **test placement, scope, and proportion**. Sibling to `what-would-william-of-ockham-say` for the test pyramid.

**Inputs:** a plan, diff, or branch.

**Outputs (under 400 words):**

- **Exemplar audit (first):** Are the existing tests near the change still showing the patterns we want future agents to imitate? If a recent test drifted into anti-patterns (testing implementation, mocking what shouldn't be mocked, brittle selectors), flag it — the next agent will copy whatever it finds. This is the leverage point Simon Willison names in [Agentic Engineering Patterns](https://simonwillison.net/2026/Feb/23/agentic-engineering-patterns/): well-organised test code is the prompt for future agents.
- **Coverage gaps:** behaviour the change introduces that no test layer asserts. File:line refs.
- **Wrong-layer findings:** tests that exist but at the wrong level (unit test that should be component; component test that's really pure-function logic).
- **Over-testing findings:** tests that lock implementation rather than invariants. Brittleness predictions.
- **Cross-surface gaps:** flows the user can trigger that cross Python/TS/Swift boundaries with nothing asserting end-to-end. Default recommendation: cohort + manual walk, not new automation.
- **Proposed routing:** for each gap, the cheapest layer that closes it. Concrete: "factor `SidebarDropDelegate.dropEntered` into a pure helper, test in `SidebarDropDelegateTests.swift`."
- **Explicit non-recommendations:** things that look testable but shouldn't be tested at this stage (cost > value). The reviewer earns its keep by blessing under-testing where proportionate.

**What the reviewer is NOT:**

- **Not a gatekeeper the main agent must invoke during the work.** That pattern causes the main coding agent to stop reasoning about tests — it knows there's another agent to do the thinking ([Shrivu Shankar — How I Use Every Claude Code Feature](https://blog.sshh.io/p/how-i-use-every-claude-code-feature)). The reviewer fires on PR / diff / plan, not as a step in the main agent's flow.
- **Not a coverage maximiser.** Meta's TestGen-LLM produces 1 useful test for every 20 generated ([Qodo writeup](https://www.qodo.ai/blog/we-created-the-first-open-source-implementation-of-metas-testgen-llm/)). Cursor's auto-test community confirms the same failure mode. The reviewer's bias is *fewer, better* tests.
- **Not the main coding agent's helper.** Following codecentric's [isolated specification testing pattern](https://www.codecentric.de/en/knowledge-hub/blog/dont-let-your-ai-cheat-isolated-specification-testing-with-claude-code), the reviewer reviews behaviour against spec without seeing the implementation diff verbatim — guards against agents optimising for tests rather than spec.

**Tone:** Bach-shaped (context-driven, heuristic, anti-dogma). Pessimistic about new infrastructure (UITests target, visual regression baselines) until justified by a named recurring bug. Sceptical of "while we're here, let's also test X" scope creep.

**When invoked:**

- Manually against a plan before implementation starts.
- Automatically as part of `/usual-suspects` once a diff exists.
- Manually against a Swift file if the user senses piecemeal drift.

**Acceptance criteria for the agent file** (when implemented): under-400-word output budget, tone anchored to `what-would-william-of-ockham-say.md` (sibling parsimony-style reviewer), no calibration set pre-built — wait for the Rule of Three of miscalibrations before formalising.

**Not yet implemented** — when ready, file at `.claude/agents/what-would-james-bach-say.md` modelled on `perf-review.md` / `what-would-william-of-ockham-say.md`. Wiring into `/usual-suspects` is a one-line addition to the skill's step 4.

## Open questions deferred

- **`BristlenoseUITests` target — when, what scope.** Probably one TF-cohort-blocking branch covering ~6 specific behaviours (toast timing, menu dimming, Cmd+Z fall-through, drop affordance, locate-flow error messages, reveal dim state). Earned by recurring regression reports, not scheduled.
- **Cross-surface E2E harness.** Whether to wire Swift + Playwright together at all, or keep it as documented manual walks + cohort. Decide post-TF when there's cohort feedback on what actually breaks across boundaries.
- **Visual regression for the SPA.** Audit doc has this planned post-React; React migration is done; question is open.

## Cross-refs

- [`docs/design-test-strategy.md`](design-test-strategy.md) — per-layer audit, tool choices, timeline (counts as of Feb 2026 — superseded by the TL;DR figures here)
- [`docs/design-playwright-testing.md`](design-playwright-testing.md) — Playwright specifics
- [`docs/design-test-data-generation.md`](design-test-data-generation.md) — fixtures
- [`e2e/ALLOWLIST.md`](../e2e/ALLOWLIST.md) — suppression discipline
- [`desktop/CLAUDE.md`](../desktop/CLAUDE.md#testing) — Swift Testing conventions (the testable-helper convention)

## References

### James Bach + context-driven testing

- [James Bach — Satisfice](https://www.satisfice.com/) — Rapid Software Testing methodology, Heuristic Test Strategy Model
- [_Lessons Learned in Software Testing_](https://www.amazon.com/Lessons-Learned-Software-Testing-Context-Driven/dp/0471081124) — Kaner, Bach, Pettichord

### Indie Mac practice

- [Brent Simmons — inessential.com](https://inessential.com/) and [NetNewsWire on GitHub](https://github.com/brentsimmons)
- [Marco Arment / David Smith — Under the Radar (Relay)](https://www.relay.fm/radar) — TestFlight-cohort-as-integration-test pattern
- [swiftyplace — Why We Keep Avoiding Tests in iOS](https://www.swiftyplace.com/blog/testing-in-ios-development) — the 27-second simulator story
- [Bitrise — Snapshot Testing in iOS](https://bitrise.io/blog/post/snapshot-testing-in-ios-testing-the-ui-and-beyond)
- [WillowTree — How to Use Swift Snapshot Testing for XCUITest](https://willowtree.engineering/2023/02/14/how-to-use-swift-snapshot-testing-for-xcuitest/)
- [pointfreeco/swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing) — and its [SwiftUI long tail](https://github.com/pointfreeco/swift-snapshot-testing/issues/921)
- [Point-Free — Swift Testing support for SnapshotTesting](https://www.pointfree.co/blog/posts/146-swift-testing-support-for-snapshottesting)
- [viesure — Modern Swift Unit Testing](https://viesure.io/modern-swift-unit-testing/developer/) — Swift Testing vs XCTest migration policy
- [Mobile Dev Diary — Swift Testing vs XCTest series](https://www.mobiledevdiary.com/posts/series/swift-testing-vs-xctest/6-parametrized-tests/)
- [Indie Stack — Daniel Jalkut](https://indiestack.com/), [Becky Hansmeyer](https://www.beckyhansmeyer.com/) — silence on test strategy is itself signal

### Agentic-coding community on testing

- [Simon Willison — Agentic Engineering Patterns](https://simonwillison.net/2026/Feb/23/agentic-engineering-patterns/) — well-organised existing tests as agent prompt
- [Shrivu Shankar — How I Use Every Claude Code Feature](https://blog.sshh.io/p/how-i-use-every-claude-code-feature) — the `PythonTests` subagent anti-pattern
- [Anthropic — Claude Code Sub-Agents docs](https://code.claude.com/docs/en/sub-agents)
- [codecentric — Isolated Specification Testing with Claude Code](https://www.codecentric.de/en/knowledge-hub/blog/dont-let-your-ai-cheat-isolated-specification-testing-with-claude-code) — implement-agent / verify-agent separation
- [Qodo — Open-source implementation of Meta's TestGen-LLM](https://www.qodo.ai/blog/we-created-the-first-open-source-implementation-of-metas-testgen-llm/) — 1:20 useful-to-noise ratio
- [Salesforce — How Cursor cut legacy coverage time by 85%](https://engineering.salesforce.com/how-cursor-ai-cut-legacy-code-coverage-time-by-85/) — speedup real, autonomy isn't
- [Cursor forum — Test Coverage doesn't work on Cursor](https://forum.cursor.com/t/test-coverage-doesnt-work-on-cursor/51565)
- [dev.to — TDD with Claude](https://dev.to/spyrae/tdd-with-ai-claude-writes-tests-first-then-the-implementation-27hm) — "test behaviour, not implementation"

### Heuristics cited

- **Knuth's 97%** — Donald Knuth, "premature optimization is the root of all evil" (1974). Applies to coverage: most code is not where the risk lives.
- **Rule of Three** — Martin Fowler / Don Roberts: extract a helper on the third caller, not the second.
- **Simple vs. Easy** — Rich Hickey, "[Simple Made Easy](https://www.infoq.com/presentations/Simple-Made-Easy/)" (Strange Loop 2011).
- **Hoare's test** — C.A.R. Hoare on so-obvious-no-bugs vs so-complex-no-obvious-bugs.
- **Speculative Generality** — Martin Fowler / Kent Beck, _Refactoring_ — abstractions for needs that haven't materialised.
- **ETTO** — Erik Hollnagel, _The ETTO Principle: Efficiency-Thoroughness Trade-Off_ — at irreversible boundaries, thoroughness wins.
- **Parkinson's Law of Triviality** (bikeshed) — Cyril Northcote Parkinson, 1957 — disproportionate weight to trivial decisions.
