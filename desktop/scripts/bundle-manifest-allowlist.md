# bundle-manifest allowlist

`check-bundle-manifest.sh` scans `bristlenose/` for directories that contain
runtime data files (`.yaml`, `.md`, `.json`, `.html`, `.css`, `.js`, etc. —
see the script's `EXT_RE` for the full list) and asserts every such directory
is covered by a `datas` entry in `desktop/bristlenose-sidecar.spec`.

This file records legitimate exceptions — dirs that contain matching files
but are genuinely not runtime, e.g. archives, test fixtures, or documentation
that happens to share an extension.

Format:

```
<!-- ci-allowlist: BMAN-<N> --> <regex-pattern-matching-dir-path>
```

The script runs each candidate dir path through these patterns and skips any
that match.

Current entries: BMAN-1.

<!-- Add new entries below this line. Renumber contiguously. -->

## BMAN-1 — a package's `gotchas.md` is contributor prose, not runtime data

Each `bristlenose/<pkg>/CLAUDE.md` keeps a one-line gotchas index and points at
a `gotchas.md` beside it for the full entries (the root `CLAUDE.md`, "Sibling
CLAUDE.md files"). The scanner skips `CLAUDE.md` by name but not its sibling, so
`llm/`, `server/` and `stages/` trip it. Nothing under `bristlenose/` opens a
`gotchas.md` (`grep -rn gotchas bristlenose --include='*.py'` is empty): the
sidecar is whole without them. `theme/gotchas.md` is not listed here only
because the whole `theme/` directory is a `datas` entry, so it rides along.

The pattern pins the filename directly under one package directory, so a
`gotchas.md` nested deeper, or any other `.md`, is still reported.

<!-- ci-allowlist: BMAN-1 --> ^bristlenose/[^/]+/gotchas\.md$
