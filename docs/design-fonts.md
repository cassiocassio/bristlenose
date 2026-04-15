# Font Strategy

## Vision

Two typefaces, two jobs:

- **SF Pro** — all UI chrome: navigation, labels, buttons, headings, badges, toolbar, sidebar, stats. The tool's voice
- **Sentinel** (Hoefler&Co) — all verbatim content: quotes, transcripts, participant speech. The participants' voice

This split is the soul of Bristlenose. The sans-serif says "this is the tool talking." The serif says "this is what someone actually said." A researcher scanning the report can feel the boundary before reading a word.

## Why Sentinel

Sentinel is a Clarendon slab serif designed by Jonathan Hoefler (2009, expanded 2020). It was built to fix what classical slab serifs lacked: proper italics, a full weight range, and real text-setting quality. It reads well at small sizes in dense layouts — exactly what quote cards demand.

Bristlenose pays for the font. Typography has been gutted by free font libraries that pay designers a one-time fee ($10k–$30k for a family that took 2,000–4,000+ hours to make) and then distribute perpetually for free, pulling the entire market expectation toward zero. We don't participate in that.

## Why SF Pro

SF Pro is Apple's system font — neo-grotesque sans-serif, nine weights, variable optical sizes, four widths. On macOS it's free and already installed. On other platforms we fall back to the system sans-serif stack (Segoe UI Variable on Windows, system-ui on Linux).

SF Pro is not bundled or loaded from a CDN. It's referenced by name and degrades gracefully to the platform's native sans-serif. The UI chrome should feel native to the OS.

## Current state (pre-implementation)

- **Font:** Inter Variable loaded from Google Fonts CDN
- **Font stack:** `"Inter", "Segoe UI Variable", "Segoe UI", system-ui, -apple-system, sans-serif`
- **No serif font** — everything is sans-serif
- **No font files bundled** — all fonts are CDN or system

## Metrics comparison

All values normalised as ratio of UPM (units per em).

| Metric | Inter (current) | SF Pro (UI target) | Sentinel (verbatim target) |
|---|---|---|---|
| UPM | 2048 | 2048 | 1000 (OTF) |
| x-height ratio | **0.546** | **~0.526** | **~0.48–0.50** |
| Cap-height ratio | 0.728 | ~0.705 | ~0.68–0.70 |
| Design model | Humanist sans, screen-first | Neo-grotesque sans | Clarendon slab serif |

Sources: [Inter font family](https://rsms.me/inter/) (x-height 1118/2048 at opsz=14, cap-height 1490/2048). SF Pro approximate values from OS/2 table (~1078 sxHeight, ~1443 sCapHeight on 2048 UPM). Sentinel values are estimates pending license — confirm with [Wakamai Fondue](https://wakamaifondue.com/) once font files are in hand.

### What the metrics mean

Sentinel sets **~8–12% visually smaller** than Inter or SF Pro at the same `font-size`. Its x-height is lower, so lowercase letters have more air above and below — which is actually desirable for dense quote cards (more breathing room, more authority, easier scanning).

## Implementation plan

### CSS custom properties

```css
/* Two font stacks — tool voice and participant voice */
--bn-font-ui: "SF Pro", "SF Pro Text", "SF Pro Display",
    "Segoe UI Variable", "Segoe UI", system-ui, -apple-system,
    sans-serif;

--bn-font-verbatim: "Sentinel", "Sentinel Book",
    Charter, "Bitstream Charter",    /* free fallback with similar DNA */
    Georgia,                          /* universal safe serif */
    serif;
```

### Where each font applies

| Context | Font token | Examples |
|---|---|---|
| UI chrome | `--bn-font-ui` | Tab bar, toolbar, sidebar, badges, buttons, stat cards, headings, labels, nav, footer |
| Verbatim content | `--bn-font-verbatim` | Quote card body text, transcript segments, featured quotes, coverage excerpts |
| Monospace | `--bn-font-mono` | Timecodes, code references (unchanged) |

### Size adjustments for Sentinel

Because Sentinel's x-height is lower than SF Pro, verbatim text needs a size bump to feel visually equivalent:

```css
/* Verbatim text sizes — bumped to compensate for lower x-height */
--bn-text-verbatim:       0.9375rem;   /* 15px vs 14px body */
--bn-text-verbatim-lh:    1.55;        /* slightly more leading for serif */

/* CSS font-size-adjust normalises apparent size during fallback loading */
font-size-adjust: 0.49;
```

### Weight mapping

Sentinel's weight names map differently than Inter's numeric values:

| Sentinel weight | Numeric | Usage |
|---|---|---|
| Light | 300 | — (not used initially) |
| Book | 400 | Quote body text (`--bn-weight-normal`) |
| Medium | 500 | Starred quotes (`--bn-weight-starred`) |
| Bold | 700 | — (not used initially) |

### Fallback chain

The `--bn-font-verbatim` stack degrades gracefully:

1. **Sentinel** — the intended experience (users who have the license)
2. **Charter / Bitstream Charter** — free, similar warmth, Matthew Carter. Available on many Linux distros
3. **Georgia** — universal web-safe serif, slightly wider but tonally close
4. **`serif`** — platform default (Times New Roman on Windows, Times on macOS)

For users without Sentinel, the report still reads well. The serif/sans split still communicates the tool-vs-participant distinction.

## Licensing

Hoefler&Co licensing model:

| License type | Model | Fits Bristlenose? |
|---|---|---|
| Desktop | Per-seat, perpetual | No — we need web rendering |
| Cloud.typography | Subscription, per-pageview | No — local-first tool, no cloud |
| Self-hosted webfont | Annual, single-domain | Partial — local server is `localhost` |
| App / redistribution | Custom negotiation | **Yes — this is what we need** |

### What to negotiate

Bristlenose is AGPL open-source and ships via pip, Homebrew, and Snap. The font files (`.woff2`) would be bundled in the package and served locally from `localhost`. No cloud, no CDN, no external traffic.

Ask Hoefler&Co for:
- **Perpetual redistribution license** for bundling Sentinel `.woff2` files in an open-source package
- **Weights needed:** Book, Book Italic, Medium (3 files minimum). Possibly Light for a future de-emphasis use
- **Credit:** Sentinel credited in About/colophon, README, and this document

Contact: [typography.com](https://www.typography.com/) → custom licensing inquiry.

If they decline redistribution at any price, the fallback plan is:
1. Ship with Charter as the default verbatim font (free, high quality)
2. Document Sentinel as the "intended" font in this file and the design system docs
3. Users who own Sentinel can drop the `.woff2` files into a config directory

## File changes required

| File | Change |
|---|---|
| `bristlenose/theme/tokens.css` | Add `--bn-font-ui`, `--bn-font-verbatim` tokens. Rename `--bn-font-body` to `--bn-font-ui`, keep alias |
| `bristlenose/theme/tokens.css` | Add verbatim size/line-height tokens |
| `bristlenose/theme/atoms/*.css` | Apply `--bn-font-verbatim` to quote content, transcript segments |
| `bristlenose/theme/organisms/blockquote.css` | `font-family: var(--bn-font-verbatim)` on `.quote-card` body text |
| `bristlenose/theme/templates/transcript.css` | `font-family: var(--bn-font-verbatim)` on `.segment` text |
| `bristlenose/theme/templates/document_shell_open.html` | Remove Google Fonts CDN link for Inter. Add `@font-face` for Sentinel if bundled |
| `frontend/index.html` | Same CDN removal + `@font-face` |
| `bristlenose/theme/CLAUDE.md` | Update typography section |
| Font files | Add `.woff2` files to `bristlenose/theme/fonts/` (after license secured) |

## Open questions

1. **Sentinel license outcome** — will Hoefler&Co grant a redistribution license for an open-source tool? Price?
2. **Exact Sentinel metrics** — confirm x-height, cap-height, weight mapping from actual font files once licensed
3. **CJK verbatim text** — Sentinel doesn't cover CJK. Quotes in Japanese/Korean/Chinese need a serif CJK fallback (Noto Serif CJK?)
4. **Inter removal** — currently loaded from Google Fonts CDN. SF Pro is system-only (no CDN). Do we need a CDN-loaded sans-serif fallback for Linux users, or is `system-ui` sufficient?
5. **Italic usage** — Sentinel has true italics. Do we use them for anything? (Moderator questions, emphasis within quotes, stage directions?)
