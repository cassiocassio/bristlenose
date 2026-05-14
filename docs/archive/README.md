# Archive — historical interest only

**Do not consult these documents as current specification.** Every doc in this folder is superseded. The body is preserved so that, when debugging "why did we pivot?" or "did we try X already?", the original reasoning is traceable — not so that anyone designs against it today.

If a doc here describes a path you're about to take, that's a signal you need to find the *successor* doc (named in the archived doc's `superseded-by` front-matter, or in its prepended "superseded" banner) — not that the archived content is the spec.

## Boundary

This folder is **public**. Only docs that were already public belong here. Anything originally gitignored archives within its own gitignored tree — archival does not downgrade sensitivity. A superseded sensitive doc is still sensitive. See the `/true-the-docs` skill (Archetype D) for the source-aware rule.

## How docs get here

`/true-the-docs` classifies a doc as Archetype D when its body is wholly historical (a successor exists, or the design path was abandoned). The skill:

1. Prepends a "superseded" report at the top.
2. Sets front-matter `status: archived-historical` or `archived-reference`.
3. Moves the file here.
4. Records `supersedes:` / `superseded-by:` cross-refs.

Files in this folder should always carry that front-matter. If they don't, they were moved by hand and need a closer look.
