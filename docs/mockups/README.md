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
| `ABANDONED` | Decided against. **After `IMPLEMENTED` it means built, shipped, then removed** — the strongest do-not-relitigate signal there is, because someone already paid to find out. |

A file whose last entry is `IMPLEMENTED` with nothing after it **is the current
truth** — that is the one to point at, and the one to copy from.

Timelines read left to right and each entry carries its date:

```
PROPOSED 19 Feb 2026 · IMPLEMENTED 4 Mar 2026 · SUPERSEDED 31 Aug 2026 by codebook-v2-autocode-button.html
PROPOSED 9 Jul 2026 · ABANDONED 25 Jul 2026 — three widgets tested worse than the list
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
