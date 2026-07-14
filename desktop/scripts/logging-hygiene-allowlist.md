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

Current entries: HYG-1.

<!-- Add new entries below this line. Renumber contiguously. -->

## HYG-1 — provider name, not a credential

`BristlenoseShared.swift` (`overlayAPIKeys` keyless-provider guard) logs the
*active provider name* — `anthropic` / `openai` / `azure` / `google` / `local`
— at `privacy: .public` when the provider is keyless (Ollama). The interpolated
value is `active`, a provider identifier, **not** a credential. The checker
trips on the literal words "API key" in the *message text*, not on what's
interpolated; `.public` is correct, since provider names are safe (and useful)
to log.

<!-- ci-allowlist: HYG-1 --> active provider=.*is keyless.*no API key injection
