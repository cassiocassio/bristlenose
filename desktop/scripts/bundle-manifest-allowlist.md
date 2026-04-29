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

Current entries: none.

<!-- Add new entries below this line. Renumber contiguously. -->
