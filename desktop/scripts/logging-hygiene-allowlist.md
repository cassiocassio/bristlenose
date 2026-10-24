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

Current entries: HYG-1, HYG-2, HYG-3, HYG-4, HYG-5.

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

## HYG-3 — a Keychain service name, not a credential

`KeychainHelper.swift` (`SharedKeychainItem.store`, the guard that refuses to
overwrite the login copy when the synced copy holds a different key) logs
`service`, the Keychain *service name* — `Bristlenose OpenAI API Key` and its
siblings from `KeychainHelper.serviceNames` — at `privacy: .public`. That is the
label the item is filed under, the same string `security find-generic-password
-s` takes, and never the key itself (`value` is not interpolated). The two
sibling lines just above it log the same `service` the same way and pass only
because their message text happens not to say "key" after the interpolation;
this one trips on the words "kept another key".

The pattern pins the whole call through its closing parenthesis, so the entry
stops matching if anything else is interpolated into the line.

<!-- ci-allowlist: HYG-3 --> log\.error\("synced copy of \\\(service, privacy: \.public\) kept another key — login copy left as it was"\)[[:space:]]*$

## HYG-4 — a report preference name, not a credential

`BridgeHandler.swift` (`storeReportPref`, the `report-pref` bridge message, R89)
logs `key`, the name of a report preference the SPA asked to save (a
localStorage key such as the zoom level or `bristlenose-quote-grouping-1`), at
`privacy: .public` when it refuses one. The variable is named for the
localStorage API, not because it holds a secret: what is saved under it is a
number or a word like `sections`, capped at 32 characters, and the refused
*value* is never logged (the over-long branch logs only its length,
`s.count`). The unlisted-key branch is the useful diagnostic, so `.public` is
right.

One entry covers the three refusal lines; each alternative pins the full call,
so logging the value, or anything else, in any of them stops the match.

<!-- ci-allowlist: HYG-4 --> log\.error\("report-pref refused: (key \\\(key, privacy: \.public\) is not listed|\\\(key, privacy: \.public\) value of \\\(s\.count\) characters|\\\(key, privacy: \.public\) value is not a string)"\)[[:space:]]*$

## HYG-5 — `fingerprint(`, not `print(`

The env-dump pattern (`print[[:space:]]*\(.*env\b`) has no word boundary, so
it matches the tail of `fingerprint(`. `ServeEnvStaleness.fingerprint(_:)` (R35)
takes the sidecar env and returns its SHA-256 digest, with the `_`-prefixed
per-spawn variables left out, precisely so that no API key is kept in the
clear; `ServeManager` stores that digest. Neither line prints or logs anything.

The pattern pins the declaration and the one call site exactly.

<!-- ci-allowlist: HYG-5 --> (static func fingerprint\(_ env: \[String: String\]\) -> String \{|instance\.spawnedEnvFingerprint = ServeEnvStaleness\.fingerprint\(env\))[[:space:]]*$
