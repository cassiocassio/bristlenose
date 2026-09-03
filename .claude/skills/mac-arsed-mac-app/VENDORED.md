# mac-arsed-mac-app — vendored third-party skill

**Not ours.** Bart Reardon's `mac-arsed-mac-app` skill, vendored verbatim.

- **Source:** https://github.com/bartreardon/skills (`mac-arsed-mac-app/`)
- **Author / licence:** Bart Reardon (author of swiftDialog) / MIT (see `LICENSE.txt`)
- **Vendored:** 2026-09-03 (upstream pushed 12 Jul 2026)

Third of the vendored Swift/Mac skills, and the only one that is about
**taste and judgement** rather than API facts. Siblings: `swiftui-pro`
(generic SwiftUI craft, iOS-first), `swift-concurrency-pro` (language-level
concurrency). Read all three `VENDORED.md` files; precedence is shared.

## What it is

44 KB across five files. `SKILL.md` is a 9-step workflow (classify app shape →
choose substrate → affordance map → **build the command model first** →
windows/documents → pasteboard and drag/drop → state preservation →
progressive disclosure → Mac behaviour test plan). References:

| File | What it carries |
|---|---|
| `reference/detailed-rules.md` (15 KB) | 18 sections — native controls, menus, keyboard/focus, text editing, selection, drag and drop, pasteboard, windows/panels/tabs/sheets, documents, state preservation, interop, accessibility, undo, performance, visual design |
| `reference/swiftui-appkit.md` (8 KB) | **The reason to have this skill.** Names the specific places pure SwiftUI still cannot be Mac-native, each with current status |
| `reference/review-and-qa.md` (6 KB) | Review rubric, "I wonder if this works" tests, anti-patterns |
| `reference/design-outputs.md` (2 KB) | Affordance-map template |

It is explicitly sourced (Gruber's 2020 Daring Fireball post, Collin Donnell,
Brent Simmons, the ATP Dev "Mac-Assed Mac Apps" episode, Paulo Andrade) and
**disagrees with its own sources where warranted** — an editorial position,
not scraped prose.

## Why it earns its place here — the selection problem

`swiftui-appkit.md` is the only document found in a wide survey (3 Sep 2026,
~40 repos measured) that separates macOS's **three distinct layers of
"highlighted"**:

1. `\.appearsActive` — window key state
2. emphasized selection — `\.backgroundProminence` + the `.selection` shape
   style, **`List`/`Table` only**
3. the context-menu focus ring — reported still unsolved, with only `List`
   getting it right *because `List` is backed by `NSTableView`*

That is precisely the wall the project sidebar hit. See
`docs/design-desktop-sidebar-appkit.md` and the two-axis section in
`desktop/CLAUDE.md`.

## Where it stops short of our decision

It keeps **SwiftUI as the default and AppKit as a targeted fallback** — it
would bridge an `NSViewRepresentable` to read window-key state rather than
move the whole control. The project went further: AppKit `NSOutlineView` is
the *confirmed destination* for the sidebar, and the SwiftUI `List` path is
being deleted.

**On the sidebar specifically, the project decision wins.** Elsewhere, its
default-to-SwiftUI posture is a reasonable starting point — the skill is a
judgement aid, not a mandate.

## Relationship to the local HIG corpus (they are different layers)

The project already mirrors part of Apple's HIG to `~/.local/share/hig-corpus/`
(built by `scripts/scrape-apple-corpus.py`, deliberately outside any git repo —
Apple's content is copyrighted and must never be committed). Four review agents
carry a hard citation rule against it.

Keep the layers straight:

- **HIG corpus = what Apple says.** The citable authority. Cite as
  `[HIG: <path>#<anchor>]`.
- **mac-arsed = what experienced Mac developers do about it**, including where
  the platform does not deliver what the HIG implies. Not a substitute for a
  HIG citation, and it does not satisfy the agents' citation rule.

When the two disagree on a factual point about Apple's guidance, the corpus
wins. When the corpus is silent on *how to actually build it*, this skill is
the better source.

## Precedence on conflict

Project hard rules (`MEMORY.md`, `CLAUDE.md`, `desktop/CLAUDE.md`) → the HIG
corpus for cited Apple guidance → mac-arsed for Mac craft and judgement →
swiftui-pro for generic SwiftUI mechanics. `swift-concurrency-pro` owns
concurrency and does not overlap this skill at all.

## Updating

```sh
cd "$(mktemp -d)" && gh repo clone bartreardon/skills . -- --depth 1
DST=/Users/cassio/Code/bristlenose/.claude/skills/mac-arsed-mac-app
cp mac-arsed-mac-app/SKILL.md "$DST/SKILL.md"
rm -rf "$DST/reference" && cp -R mac-arsed-mac-app/reference "$DST/reference"
cp mac-arsed-mac-app/LICENSE.txt "$DST/LICENSE.txt"
# then bump the "Vendored" date above
```

## Why this one — already evaluated, do not re-research

Chosen from a surveyed field, not picked at random. The full register, with
what was declined and why, is at:

  https://claude.ai/code/artifact/7165ebdc-e1a4-43a2-b96c-9626d54e2405   (maintainer's record; private)

**Alternatives already surveyed** (~40 repos, 3 Sep 2026): `CharlesWiltgen/Axiom`
is 15% macOS repo-wide and worth only two files; `openai/plugins`,
`fayazara/macos-app-skills`, `petekp/agent-skills` and
`LaughingJackalope/macos-skills` all carry **no licence** and cannot be vendored
however good they are; HIG mirrors like `markmals/mac-dev-skills` bundle Apple's
copyrighted docs, which an MIT wrapper does not license. **Open:**
`yigitkonur/plugin-swiftui`'s two decision references (~10 KB) are the only other
artefact found that encodes 'SwiftUI isn't ready for this Mac control'.

A future research round should start from that register. Re-proposing something
it declined needs a reason the decline did not already consider.
