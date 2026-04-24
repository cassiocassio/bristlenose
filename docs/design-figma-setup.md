# Figma Setup — Bristlenose Scratch File

How to set up the Figma file for low-fidelity, component-accurate, spacing-loose wireframing. Goal: sketch "these components in this order," let the OS and CSS handle pixels. Not a design system file — a sketchpad. Name it `bristlenose-scratch`, not `bristlenose-design-system`.

Pairs with [design-type-colour-parity.md](design-type-colour-parity.md) — the type/colour tokens below are mirrors of the CSS tokens, not a parallel system.

## Before you open Figma

- Install **SF Pro** and **SF Mono** (developer.apple.com/fonts). Without these, every spacing decision is lies — Figma falls back to Inter metrics.
- Install **Inter** (rsms.me/inter) too — needed for CLI/browser fidelity checks.
- Turn on Dark Mode in Figma preferences if you'll spend time there (dark mode is where mismatches live; see parity doc).

## File bootstrap

Duplicate **Apple Design Resources — macOS** from developer.apple.com/design/resources into your drafts. This is the source of native components. Don't edit it — copy instances into the scratch file.

## File structure

```
Page: 🎨 Tokens       — colours, spacing as variables
Page: 🔤 Type         — the HIG type ramp + specimen
Page: 🧱 Native kit   — copied-in Apple components (toolbar, sidebar, list)
Page: 🧱 Web kit      — your atoms/molecules (badges, quote cards, tags)
Page: 📐 Guides       — window templates w/ margins
Page: 🪞 Parity       — native vs web controls at same styles, side-by-side
Page: 🖼 Screens      — the actual scratch work
Page: 📝 Notes        — annotations, open questions
```

First seven pages are scaffolding — built once, rarely touched. Screens is where "like this" happens.

## Page-by-page setup

### 🎨 Tokens

**Spacing variables** (deliberately small — 4 buckets, not 7):

| Variable | Value |
|---|---|
| `space/xs` | 4 |
| `space/sm` | 8 |
| `space/md` | 16 |
| `space/lg` | 24 |
| `space/xl` | 32 |

**Radius variables**:

| Variable | Value |
|---|---|
| `radius/sm` | 4 |
| `radius/md` | 6 |
| `radius/lg` | 10 |

**Colour variables** — light/dark modes on every colour. Semantic names only, mirroring CSS tokens:

| Variable | Binds to |
|---|---|
| `text/primary` | `labelColor` / `--bn-text-primary` |
| `text/secondary` | `secondaryLabelColor` |
| `text/tertiary` | `tertiaryLabelColor` |
| `surface/window` | `windowBackgroundColor` |
| `surface/content` | `textBackgroundColor` |
| `border/separator` | `separatorColor` |
| `accent/control` | `controlAccentColor` |

Use Apple's actual HIG values for light and dark. If/when you change the CSS tokens, update here too. If the mapping ever drifts, the scratch file lies.

### 🔤 Type

Build the HIG ramp as Figma Text Styles. Single namespace (no `macos/` vs `web/` split — point of the parity work is one scale).

| Style | Size / Line | Weight |
|---|---|---|
| `type/large-title` | 26 / 32 | Regular |
| `type/title-1` | 22 / 26 | Regular |
| `type/title-2` | 17 / 22 | Regular |
| `type/title-3` | 15 / 20 | Regular |
| `type/headline` | 13 / 16 | Semibold |
| `type/body` | 13 / 16 | Regular |
| `type/callout` | 12 / 15 | Regular |
| `type/subheadline` | 11 / 14 | Regular |
| `type/footnote` | 10 / 13 | Regular |
| `type/caption-1` | 10 / 13 | Regular |
| `type/caption-2` | 10 / 13 | Medium |

Font family: **SF Pro Text** below 20, **SF Pro Display** 20 and up. Figma doesn't auto-switch — set explicitly per style.

Add two annotation-only styles:
- `note/red` (10/13, #d00, Inter) — margin notes on screens.
- `note/grey` (10/13, #888, Inter) — secondary annotations.

Specimen sheet: one frame showing every style at a sample string ("The quick brown fox…"). Makes it obvious when a style is wrong.

### 🧱 Native kit

Copy from Apple's file, don't redraw:

- Window chrome (traffic lights, title bar, toolbar — unified + compact variants).
- NavigationSplitView sidebar (source list rows, section headers, disclosure).
- List styles (plain, inset, sidebar).
- Segmented controls, buttons (push, pill), popovers, sheets.
- Menus and menu bar items.

Use as **component instances** — don't detach. When macOS 27 ships an updated kit, re-import and instances refresh.

### 🧱 Web kit

Your atoms/molecules from `bristlenose/theme/` — the ones you actually use in wireframes:

- Quote card (avatar + name + body + tag strip).
- Tag badge (with group colour).
- Finding flag.
- Toolbar (search, filters, sort).
- Sidebar TOC row.
- Modal shell (title + body + footer).

Draw once, use everywhere. Auto-layout from the start — never fixed widths.

### 📐 Guides

Window templates at three sizes:

| Template | Inner dims | Use |
|---|---|---|
| Window / compact | 900 × 600 | Minimum viable Bristlenose |
| Window / standard | 1280 × 800 | Typical target |
| Window / wide | 1600 × 1000 | Reviewer's big monitor |

Each template pre-fills:
- Toolbar at 52pt unified (or 38pt compact).
- Sidebar at 220pt source list.
- Content margin 20pt standard / 16pt compact.
- An annotation strip along the side listing these numbers.

Drop these as the starting frame for every new screen. Don't start from a blank rectangle.

### 🪞 Parity

Side-by-side comparisons, screenshots from real builds:

- Native button / web button at `type/body`.
- Native list row / web list row.
- Native text field / web text field.
- Native popover / web modal.
- Body text at every type style: native vs WKWebView vs Safari vs Chrome (4 columns).

This is the page that tells you whether the type+colour alignment work has landed. If a row is visibly off at arm's length, the token is wrong. (See parity doc — fix there, not here.)

Update when tokens change.

### 🖼 Screens

The scratchpad. Rules:

- Start from a Guides template, never blank.
- Use Native kit for chrome, Web kit for content.
- Type styles only — no custom sizes.
- Spacing variables only — no loose numbers.
- Auto-layout everything. If you're nudging by 1–3px, stop.
- 30 min per screen, then move on. Timer. Seriously.

Cover frame banner: *"Wireframes — components and order are the spec. Spacing and type sizes are illustrative. OS defaults win."*

### 📝 Notes

Open questions, decisions, things to check with implementation. Not designs. Kept here so Screens stays clean.

## Working practices

**Two sources of truth is the worst outcome.** Figma mirrors `bristlenose/theme/tokens/`. When tokens change in code, update Figma same session. When Figma reveals a needed token, add it to code before committing the mock.

**Mode discipline.** Colour variables have light + dark from day one. Every frame can be toggled. Retrofitting modes later is miserable.

**Greyscale first.** Draft screens in greyscale. Add colour only when moving from "what" to "how it looks." Stops reviewers arguing about blue when the question is structure.

**Annotations are first-class.** `note/red` on everything ambiguous. The mock carries shape; the notes carry intent.

**Native vs web labelling.** Every frame titled with the target: `Mac app / Quotes tab` vs `CLI / Quotes tab`. Same screen, different targets, different acceptable fidelity.

## What this setup is not

- Not a design system. The system is `bristlenose/theme/`.
- Not a handoff spec. Implementation reads tokens from code, not from Figma numbers.
- Not a marketing asset. Polish comes from higher-fi passes on the two or three screens that ship to users.
- Not canonical for colour or type values. If Figma and CSS disagree, CSS wins — then update Figma.

## Estimated setup time

- Apple kit import + page scaffold: 30 min.
- Tokens (spacing, radius, colour light+dark): 45 min.
- Type styles (11 HIG + 2 annotation): 30 min.
- Web kit (6 components): 1–2 hrs (reusable forever).
- Guides (3 templates): 30 min.
- Parity page (4 real screenshot comparisons): 1 hr.

**~4 hrs to first screen.** Resist shortcuts — skipping the guides page is the one that bites most.

## Gotchas

- **Font fallback.** If SF Pro isn't installed, Figma silently uses Inter. Proportions drift 1–2pt everywhere. Check the Fonts panel before trusting anything.
- **pt vs px.** macOS is pt, web is px. 1:1 at 1× Retina. Don't mix in one frame — label the frame.
- **Variables vs styles.** Figma has both. Use variables for colour and spacing (mode-aware, aliasable). Use styles for type (no variable support for compound properties).
- **Apple's kit uses their own variables.** Alias yours to theirs where they overlap, or you'll have two systems fighting. Most important: colour.
- **Community kits drift.** If you supplement Apple's kit with a community macOS UI file, date-stamp what you pulled in — they rot.
- **Don't trace screenshots.** If you find yourself redrawing a toolbar, stop — go find it in the kit.

## When to leave scratch mode

If a screen becomes load-bearing (shipping soon, stakeholder review, implementation reference), duplicate it to a `hi-fi/` page and polish *that copy*. Scratch stays scratch. The moment you start polishing in place, the file stops being a sketchpad and becomes an obligation.
