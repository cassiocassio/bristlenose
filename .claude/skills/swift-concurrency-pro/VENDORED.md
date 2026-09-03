# swift-concurrency-pro — vendored third-party skill

**Not ours.** This is Paul Hudson's `swift-concurrency-pro` skill, vendored verbatim.

- **Source:** https://github.com/twostraws/swift-concurrency-agent-skill (`swift-concurrency-pro/`)
- **Author / licence:** Paul Hudson (@twostraws) / MIT (see `LICENSE`)
- **Version vendored:** 1.0 (see `metadata.version` in `SKILL.md`)
- **Vendored:** 2026-09-03 (upstream HEAD `bee3f69`, 17 May 2026)

Sibling of `.claude/skills/swiftui-pro/` — same author, same format, same
vendoring rules. Read that skill's `VENDORED.md` too; the precedence rules are
shared.

## What it is

A **knowledge source**, not a reviewer persona. `SKILL.md` is a 12-step
concurrency-review checklist; the real content is in `references/*.md`
(hotspots, Swift 6.2 features, actors, structured/unstructured tasks,
cancellation, async streams, bridging, GCD interop, bug patterns, strict-
concurrency diagnostics, async testing). ~1,450 lines — roughly 3× swiftui-pro.
Load only the relevant reference for a partial review.

`references/hotspots.md` is the cheapest entry point: it's a grep-target list,
built for exactly the "where do I even look" pass.

It auto-triggers in the **main** conversation on Swift concurrency work. Review
**subagents** can't invoke skills — they `Read` the reference files directly,
same wiring as swiftui-pro (see `.claude/skills/usual-suspects/SKILL.md` and
`what-would-gruber-say.md`).

## Project reality check (measured 3 Sep 2026 — read before trusting it)

The skill's Core Instructions open with "target Swift 6.2 or later with strict
concurrency checking". **The desktop app does not.** Measured from
`desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj`:

| Setting | Value | Where |
|---|---|---|
| `SWIFT_VERSION` | **5.0** | both targets |
| `SWIFT_DEFAULT_ACTOR_ISOLATION` | **`nonisolated`** | project-level, inherited by both targets |
| `SWIFT_APPROACHABLE_CONCURRENCY` | **NO** | resolved |
| `MACOSX_DEPLOYMENT_TARGET` | **15.0** | resolved — decides which fixes are reachable |

Consequences:

- **Swift 5 language mode, not Swift 6.** Most of `diagnostics.md` maps
  strict-concurrency *errors* to fixes; in Swift 5 mode those largely don't
  fire. Treat that file as a migration aid, not a description of today's build.
  Advice resting on Swift 6 semantics (`sending` parameters, isolated
  conformances) is aspirational here.
- **Default actor isolation is `nonisolated`, NOT MainActor.** Both this skill
  and swiftui-pro tell the reviewer to check this before flagging `@MainActor`
  or calling `MainActor.run()` redundant. The answer is recorded here so nobody
  re-derives it: annotations *are* needed, and `MainActor.run()` is *not*
  automatically redundant.
- **Read these from `xcodebuild -showBuildSettings`, and say which scheme.**
  The dual floor is *deliberate policy*, not drift: production ships **15.0**
  (Sequoia, the n-1 rule) while the Apple-Intelligence schemes require **26.1**
  because Foundation Models is macOS 26+. See `docs/design-platform-policy.md`
  §"Pillar 3 — macOS". An earlier revision of this file reported a single floor
  of 26.1 and approachable concurrency as `YES`; both came from hand-parsing
  the pbxproj, which cannot tell you which config a scheme resolves to. One
  command can:

  ```
  xcodebuild -showBuildSettings -project desktop/Bristlenose/Bristlenose.xcodeproj \
    -target Bristlenose -configuration Release | grep -E 'SWIFT_|DEPLOYMENT'
  ```

- **The deployment floor is the setting that decides whether a "this is fixed
  now" claim applies to us.** At **macOS 15.0**, most of the SwiftUI-on-Mac
  improvements people cite — `List` performance, `TextEditor` rich text, native
  `WebView`, `\.appearsActive` / `\.backgroundProminence` — landed in macOS 26
  and are **not reachable** without a runtime gate. The retreat-to-AppKit
  material is therefore *correct* for this codebase, not over-correction. The
  three `if #available(macOS 26.0, *)` checks in the Swift source are load-
  bearing, not dead code.

**Tests are Swift Testing, not XCTest** (105 files vs 1), so `references/testing.md`
— the largest reference — applies directly. Note the Swift suite is **ungated by
CI**: run `desktop/scripts/test-swift.sh`, never a hand-rolled `xcodebuild`.

## Where it contradicts swiftui-pro (this one wins)

`swiftui-pro/references/swift.md` says **never** use Grand Central Dispatch.
This skill is deliberately softer: GCD stays acceptable in low-level code,
framework interop, and performance-critical synchronous work, and says not to
flag those as errors.

That matters — there are ~16 GCD call sites in the shipping Swift source. An
agent applying swiftui-pro alone would flag all of them. **On concurrency
specifics, prefer this skill:** it is the specialist source and the more recent
judgement. swiftui-pro keeps precedence on general SwiftUI craft.

## Precedence on conflict

Unchanged from swiftui-pro: project hard rules (`MEMORY.md`, `CLAUDE.md`) win,
then macOS idiom (gruber / app-store-police), then the vendored skill for
generic Swift craft. A vendored skill beats an agent's *untrained hunch* on
pure Swift facts — never a documented project decision or a Mac-platform
correction.

Unlike swiftui-pro, this skill is **not** iOS-first: it is platform-neutral, so
the "tap vs click" and 44×44 touch-target caveats do not apply.

## Updating

Upstream moves slowly (4 commits total; HEAD `bee3f69` is 17 May 2026). Check
the last commit before bumping:

```sh
cd "$(mktemp -d)" && gh repo clone twostraws/swift-concurrency-agent-skill . -- --depth 1
DST=/Users/cassio/Code/bristlenose/.claude/skills/swift-concurrency-pro
cp swift-concurrency-pro/SKILL.md "$DST/SKILL.md"
rm -rf "$DST/references" && cp -R swift-concurrency-pro/references "$DST/references"
cp LICENSE "$DST/LICENSE"
# then bump "Version vendored" + "Vendored" date above
```

Upstream also ships plugin-marketplace scaffolding (`.claude-plugin/`,
`agents/openai.yaml`, `assets/`). **Deliberately not vendored** — we install as
a plain project skill, matching swiftui-pro.

Remaining siblings if wanted later: SwiftData Pro, Swift Testing Pro.

## Why this one — already evaluated, do not re-research

Chosen from a surveyed field, not picked at random. The full register — every
candidate, with dates, licences and the reason for each verdict — is in the
maintainer's private notes; in an interactive session, `/artifacts` lists it
under **Swift Corpus Register**. The decisions that matter are summarised below
so this file stands alone without it.

**Known open alternative:** `AvdLee/Swift-Concurrency-Agent-Skill` (MIT, v2.3.0,
1,638★) is reported as materially larger (~250 KB vs ~55 KB) with a diagnostic
routing table that reads your actual build settings before advising. Not
independently verified, no name collision, and its author publishes on
concurrency weekly. Taking it *alongside* this one is the open action — not a
question to re-research.

A future research round should start from that register. Re-proposing something
it declined needs a reason the decline did not already consider.
