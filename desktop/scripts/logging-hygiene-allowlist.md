# logging-hygiene allowlist

`check-logging-hygiene.sh` scans Swift host-app code for logger calls that
interpolate credential-shaped identifiers (`key`, `secret`, `token`,
`credential`, `password`) without an explicit `privacy: .private` or
`privacy: .sensitive` marker, and for any `print()` that dumps an env dict.

This file records legitimate exceptions. Each entry:

1. A short justification describing why the line doesn't leak credentials.
2. A line with the exact allowlist marker and an extended-regex (ERE)
   pattern that matches the offending grep output line.

Format:

```
<!-- ci-allowlist: HYG-<N> --> <regex-pattern>
```

The script runs each candidate line through these patterns and skips any
that match.

Current entries: none.

<!-- Add new entries below this line. Renumber contiguously. -->
