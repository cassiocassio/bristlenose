# swiftui-pro — vendored third-party skill

**Not ours.** This is Paul Hudson's `swiftui-pro` skill, vendored verbatim.

- **Source:** https://github.com/twostraws/swiftui-agent-skill (`swiftui-pro/`)
- **Author / licence:** Paul Hudson (@twostraws) / MIT (see `LICENSE`)
- **Version vendored:** 1.1 (see `metadata.version` in `SKILL.md`)
- **Vendored:** 2026-06-07

## What it is

A **knowledge source**, not a reviewer persona. `SKILL.md` is a SwiftUI
code-review checklist; the real content is in `references/*.md` (deprecated API,
view composition, data flow, navigation, design/HIG, accessibility, performance,
modern Swift, hygiene). Load only the relevant reference for a partial review.

It auto-triggers in the **main** conversation when you read/write/review
SwiftUI. Review **subagents** (gruber, code-review, james-bach) can't invoke
skills — they `Read` the reference files directly. See the wiring note in
`.claude/skills/usual-suspects/SKILL.md` and `what-would-gruber-say.md`.

## macOS caveat (read before trusting it blindly)

The skill is **iOS-first** (iOS 26 / Swift 6.2 default target). Bristlenose's
desktop app is macOS. Where it conflicts with our reality:

- "tap" vocabulary and the 44×44 minimum touch target are iOS — on Mac the verb
  is *click* (MEMORY.md hard rule) and hit-target sizing differs.
- iOS deployment-target assumptions don't apply to the AppKit/SwiftUI Mac shell.

**Precedence on conflict:** project hard rules (`MEMORY.md`, `CLAUDE.md`) win,
then macOS idiom (gruber / app-store-police), then swiftui-pro for generic
SwiftUI craft. swiftui-pro beats an agent's *untrained hunch* on pure SwiftUI
facts (deprecated API, property-wrapper choice) — but never beats a documented
project decision or a Mac-platform correction.

## Updating

Re-vendor from upstream (it's actively maintained — check the repo's last
commit before bumping):

```sh
cd /tmp && rm -rf swiftui-pro-install
gh repo clone twostraws/swiftui-agent-skill swiftui-pro-install -- --depth 1
DST=.claude/skills/swiftui-pro
cp swiftui-pro-install/swiftui-pro/SKILL.md "$DST/SKILL.md"
rm -rf "$DST/references" && cp -R swiftui-pro-install/swiftui-pro/references "$DST/references"
cp swiftui-pro-install/LICENSE "$DST/LICENSE"
# then bump "Version vendored" + "Vendored" date above
```

Siblings exist if we want them later: SwiftData Pro, Swift Concurrency Pro,
Swift Testing Pro (same author, same format).
