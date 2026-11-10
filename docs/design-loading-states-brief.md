# Loading-state vocabulary — design brief

_**Status 10 Nov 2026: partly built, not approved.** The tapestry strip's working sweep and the skeleton tokens were implemented on 9 Nov as the first trial; the owner has not yet judged them in the real app, the ghosts and every other surface are not built, and there is no backlog yet. The "don't touch the theme or frontend" line below applied to the mockup stage and was lifted for that one trial. The reversal of "never a skeleton" is written into `design-progressive-lenses.md` §2 (decided, not built)._

_Brief for the mockup work, 9 Nov 2026. Not a design doc yet: it becomes one after the owner approves the mockup._

Design the loading-state vocabulary for Bristlenose as a system, in pixel-accurate CSS mockups, before any implementation. Don't touch `tokens.css`, the theme, the frontend or the desktop app, and don't commit.

## Context

In user testing, progressive display read as broken. People didn't realise analysis was still running. They also never discovered that the tapestry bars are a scrubbable video timeline, because the bars and thumbnails only appeared once frames existed. Today the only loading cue is the text shimmer (`docs/design-motion.md` §4.7.1, `bristlenose/theme/atoms/shimmer.css`). Skeleton and ghost placeholders aren't defined anywhere.

`docs/design-progressive-lenses.md` §2 currently says "never a skeleton" and "no placeholder for a waiting row". This brief proposes reversing those two decisions; the mockup says so explicitly.

## The three states

Each needs a name, a visual, a motion rule and a token set.

| State | Visual |
|---|---|
| Done | the real thing |
| Working on it now | shimmer, on at most a few elements |
| Will exist, not started | static ghost (dim outline, no motion); reads as "coming", never as "disabled" |

## The mockup page

One page in `docs/mockups/`, in the style of `analysis-lifecycle-states.html`, in bn-accurate mode with real `--bn-*` tokens and component classes.

- **A.** The same three states side by side across at least five areas: tapestry bars plus thumbnail on a video session; session-row cells (speakers, sparkline); the tail of the Quotes list; Themes or Signals arriving at the barrier; a waiting row. Plus one area outside the pipeline (dashboard or a cloud-import sidebar).
- **B.** The unhappy paths for each area: Stop, failure, cancelled run, audio-only (no placeholder), and the resolve moment when the real content arrives.
- **C.** Light and dark, and the reduced-motion / animation-off fallback beside the animated version.
- **D.** A proposed token block, namespaced `--bn-ghost-*` and `--bn-skeleton-*`, defined inside the mockup. It reuses the shimmer timing tokens (sweep, gap, period, easing) so block shimmer has the same character as text shimmer. It says where it follows §4.7.1 and where it can't, because the text clip doesn't apply to a box.
- **E.** Written principles: when each state applies; the motion budget (one shimmer per region, independent phase); every ghost has a defined exit; a ghost only appears for something we know will arrive (for example probe-confirmed video).

## Ground it in fact

Before drawing the tapestry, read how scene colours, strips and thumbnails are scheduled, and state how long each placeholder would actually be on screen. If a wait is a couple of seconds, say so and say whether it needs shimmer at all.

## Check against the system

Run `is-this-bristlenosey` on the proposal, then `ux-critique` and `what-would-gruber-say` on the mockup. List the decisions wanted from the owner. Stop there: no implementation until the owner approves the mockup.

## Parked after the 9 Nov reviews (owner: save for later, move forward)

Not yet in the mockup. Pick up before the design doc is written.

1. **A plain progress line** ("3 of 8 sessions read" style) where the eye already is. All three reviewers said "still working" is a status problem, not a per-cell one. Open question: is today's subtitle/sidebar progress text too quiet, or in the wrong place?
2. **A stronger ghost line in Edo dark.** The outline collides with the border colour there and reads too faint; it was also lowered in contrast on 9 Nov, so re-check all four scheme/palette combinations together.
3. **An explicit failure and stopped rule.** Today the page says failure resolves to the shipped fallback and Stop removes every placeholder. Spell out per area what a failed, cancelled and stopped run leaves behind, and that the status line says "Analysis stopped".

Also still open: strip decode time per hour of video is unmeasured, and the 12 Oct "never a skeleton" ruling is not yet reversed.
