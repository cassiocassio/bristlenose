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

Current entries: HYG-1, HYG-2.

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

## HYG-2 — a two-literal ternary, not a credential

`ServeManager.swift` (`postAgentScope`'s no-token guard) logs which *direction*
an agent-scope call would have gone — the interpolation is
`readable ? "open" : "CLOSE"`, two string literals — at `privacy: .public`,
which is correct: a direction is safe and useful to log, and the message exists
to be loud about a revocation that could not be sent.

Same shape as HYG-1: the checker trips on the literal words "auth token" in the
*message text*, not on what is interpolated. Note the marker regex accepts only
`.private` / `.sensitive`, so a correctly-`.public` call cannot satisfy it —
widening that to accept `.public` would be the wrong fix, because `.public` on a
genuinely secret value is precisely the bug this gate exists to catch.

**The pattern anchors on the interpolation, not the message.** A first draft
matched `agent-scope .*skipped.*no auth token` — message text only — and an
adversarial check showed it would also allowlist
`log.info("agent-scope \\(authToken) skipped — no auth token")`, i.e. an actual
leak in the same sentence. Any allowlist entry here must pin the thing that makes
the line safe; if the interpolation changes, the entry must stop matching.

<!-- ci-allowlist: HYG-2 --> agent-scope .*readable \? "open" : "CLOSE", privacy: \.public.*no auth token
