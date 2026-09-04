# Mockups

Standalone HTML mockups for features in progress. Open in a browser to see the design intent — these are not part of the application and are never linked from the report or CLI.

Each file is self-contained (inline CSS/JS) so it works without a build step.


## Lifecycle

A mockup is a snapshot of intent at a date. Some are the design of record; some
show a flow that was replaced; some show an idea that was drawn, argued about,
and deliberately not built. Without a marker there is no way to tell them apart
except by reading the code — which defeats having them, and means the same
rejected idea gets proposed again a year later by someone who found the picture.

So a mockup carries a **dated timeline**, not a single state. The states:

| State | Means |
|---|---|
| `PROPOSED` | Drawn as an idea. Not built. |
| `IMPLEMENTED` | Built and shipped. |
| `SUPERSEDED by X` | A later design of the same thing replaced it. |
| `PARKED` | Built, tested, and deliberately withheld behind a feature flag. The code is live; the researcher cannot see it. Neither delete it nor re-propose it — check the flag's own doc for the revisit conditions. |
| `SANDPIT` | Not a design at all — an instrument. A tuner, playground, gallery, catalogue or stress test you open to *adjust* something or to see a range at once. It has no lifecycle: it is useful or it is not, and it goes stale only when the thing it tunes disappears. The design docs already use this word (&ldquo;Sandpit: `focus-mode-lab.html`&rdquo;). |
| `ABANDONED` | Decided against. **After `IMPLEMENTED` it means built, shipped, then removed** — the strongest do-not-relitigate signal there is, because someone already paid to find out. |

A file whose last entry is `IMPLEMENTED` with nothing after it **is the current
truth** — that is the one to point at, and the one to copy from.

Timelines read left to right and each entry carries its date:

```
PROPOSED 19 Feb 2026 · IMPLEMENTED 4 Mar 2026 · SUPERSEDED 31 Aug 2026 by codebook-v2-autocode-button.html
PROPOSED 7 Feb 2026 · IMPLEMENTED 4 Mar 2026 · ABANDONED 29 Aug 2026 — the v1 lens, deleted in baa1aa0e
PROPOSED 23 Feb 2026 · IMPLEMENTED 5 Aug 2026 · PARKED 5 Aug 2026 — not intuitive enough; flag moderatorQuestionPill
```

An `ABANDONED` or `SUPERSEDED` entry **must say why in a clause**. That clause is
the whole value of keeping the file: the picture shows what was tried, the
clause stops it being tried again.

**Nothing is deleted.** A superseded mockup is the record of why the current
thing looks the way it does, and that argument is usually the expensive part.

### Where the timeline lives

- **[STATUS.md](STATUS.md)** is the register — every mockup, its date, its
  timeline. Look here first for "what is the current design for X".
- A **banner** goes at the top of any file whose last entry is not
  `IMPLEMENTED`, so opening it warns you before you read it. Self-styled inline
  so it cannot clash with the file's own CSS.
- No banner and no register entry means **unreviewed** — nobody has checked.
  That is the absence of a claim, not a claim of currency.

**A new mockup must be added to the register**, and CI enforces it:
`scripts/check-mockup-register.py`, wired to `.github/workflows/mockup-register.yml`
on any change under `docs/mockups/`. It checks that every file has a row, that
every row names a real file, and that every row names a state — not that the
state is *right*, which is a judgement against the code that no script can make.
`*unreviewed*` is a valid entry: say nothing rather than guess.

## A mockup that links live theme CSS will rot silently

Twelve mockups `<link>` the real theme instead of inlining it, which sounds like
the honest thing to do — the picture then shows the *actual* design system. It is
a trap. The theme gets restructured; the link still resolves, the classes still
exist, and the **tokens move out from under it**. An undefined custom property is
invalid at computed-value time, so `background: var(--bn-colour-bg)` silently
falls back to nothing and the page renders bare.

Found 3 Sep 2026: `tokens.css` held colour and type tokens in March; they now live
in `colors/palette-default.css` and `tokens-typography.css`. Four mockups linked
only the old file and had **37 undefined variables** each, including
`--bn-colour-bg`, `--bn-colour-text` and `--bn-font-body`. They rendered as
unstyled HTML. Repaired by linking what `index.css` names, in its order.

If you link the theme, link the four token files first —
`tokens.css`, `tokens-typography.css`, `tokens-desktop.css`,
`colors/palette-default.css` — and expect to re-check after any theme
reorganisation. Inlining is safer for anything meant to survive as a record.
