---
status: pending
last-trued: 2026-04-28
trued-against: HEAD@main (23d56af) on 2026-04-28
---

# Keeping LLM price estimates current

> **Pending / aspirational.** Followup to Phase 1 cost forecast. Slice C of Phase 1 has now shipped (`4401e41`); implementation can begin as a separate small PR. Forecast logic (now data-driven) and pricing freshness are independent concerns. Last confirmed aspirational 2026-04-28.
> **Parent design:** [design-llm-call-telemetry.md](design-llm-call-telemetry.md). Sibling: [design-cost-forecast-phase1.md](design-cost-forecast-phase1.md).

## Changelog

- _2026-04-28_ — confirmed still aspirational; Phase 1 Slice C shipped (`4401e41`) so the "after slice C" precondition is now met. Branch `cost-and-time-forecasts` closed (`23d56af`); `trued-against` re-anchored to main.
- _2026-04-27_ — initial draft.

## Problem

Today [`bristlenose/llm/pricing.py`](../bristlenose/llm/pricing.py) is a hard-coded `PRICING` dict and a `PRICE_TABLE_VERSION = "2026-04-25"` constant baked into the released wheel. The dict ships with whatever rates were correct on the day a Bristlenose version was cut, and never updates again on the user's machine.

Anthropic, OpenAI, and Google change frontier-model pricing roughly four to ten times a year between them. New models appear, old models drop in price, and tier boundaries shift. The slice B telemetry log captures `price_table_version` per row so a maintainer can recompute historical actuals against any future rate sheet — that part is fine. The user-facing forecast is not.

**Concrete failure:** Anthropic halves Sonnet 4 input pricing tomorrow morning. A user on Bristlenose v0.15.x runs `bristlenose run` against a 12-session project. The pre-run forecast prints `~$3.20` when the real cost is `~$1.90`. The user either over-budgets (mild) or, worse, picks a smaller / cheaper model than they actually needed. Slice C makes the forecast *self-correcting from local history* but does nothing about the rate sheet itself — local medians × stale rates still gives the wrong dollar figure.

We need a way to refresh the price table between releases without forcing users onto a release cadence and without compromising the local-first promise.

## Approach

Three-tier fallback, ship-with-bundled-prices:

1. **Bundled `pricing.json` in the wheel/snap/dmg.** Same dict that's in `pricing.py` today, lifted into a JSON file co-located with the module. Always present, always loadable. Airgapped users, Ollama-only users, and anyone who opts out of the fetch see *some* number — the number that was current the day their build was cut. Worst case is the status quo.
2. **Optional fetch from `https://bristlenose.app/pricing.json`** on a 24-hour-ish TTL. Stdlib `urllib.request` GET, 5 second timeout, no auth, no headers beyond default `User-Agent`. Cached locally on success.
3. **Local cache file** read on every cost calculation. If the cache is fresh (< 24h), skip the fetch. If the cache exists but is stale, serve it *and* kick off a refresh. If the cache is missing or unreadable, fall back to bundled.

The fetch is **never blocking on the hot path**. The first call into pricing reads cache + bundled synchronously; the network refresh runs in a background thread (or is simply deferred to the next cost calculation if the previous attempt was less than e.g. 60 seconds ago). A failed fetch never bubbles an exception — it logs at INFO and returns the existing cache.

## Data shape

The endpoint payload mirrors the in-code dict, plus a version stamp and per-provider URLs:

```json
{
  "schema_version": 1,
  "price_table_version": "2026-05-12",
  "currency": "USD",
  "pricing": {
    "claude-sonnet-4-20250514":  [3.0, 15.0],
    "claude-haiku-3-5-20241022": [0.80, 4.0],
    "gpt-4o":                    [2.50, 10.0],
    "gpt-4o-mini":               [0.15, 0.60],
    "gemini-2.5-flash":          [0.15, 3.50],
    "gemini-2.5-pro":            [1.25, 10.0]
  },
  "pricing_urls": {
    "anthropic": "https://docs.anthropic.com/en/docs/about-claude/models",
    "openai":    "https://platform.openai.com/docs/pricing",
    "azure":     "https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/",
    "google":    "https://ai.google.dev/gemini-api/docs/pricing"
  }
}
```

**Field semantics:**

- `schema_version` — `1` for now. Bumped only if the *shape* changes (e.g. tiered pricing, cache-token rates as separate columns). The client refuses to load any payload whose `schema_version` it doesn't know, falls back to bundled.
- `price_table_version` — ISO date of the most recent rate change. Stamped onto every telemetry row at call time (already done, slice B). Lexical comparison is enough: "newer string wins."
- Tuples `[input_rate_usd, output_rate_usd]` per million tokens. Same as today's dict.

**Backward compat for new providers:** adding a new model is just a new key in `pricing`. Old clients ignore unknown keys (the lookup is `model in PRICING`, returns `None` on miss — same as today). Adding a new *column* (e.g. cache-read pricing) requires a `schema_version` bump and a client-side change; until then those rates stay hard-coded inside the provider methods.

## Cache location

**Decision: global, not per-project.** `~/.config/bristlenose/pricing-cache.json` on Linux, `~/Library/Application Support/Bristlenose/pricing-cache.json` on macOS. Use `platformdirs.user_config_dir("bristlenose")` (already a transitive dep via `pydantic-settings`) — no new dependency.

Per-project would mean re-fetching for every fresh project directory and would put the cache in places users sync to Dropbox / iCloud / git, which is the wrong category of artefact (it's machine-global, not project-data). Global cache means one fetch per laptop per 24 hours regardless of how many studies the user runs.

The cache file shape is the endpoint payload plus a fetched-at timestamp:

```json
{
  "fetched_at": "2026-05-12T09:14:33Z",
  "payload": { …endpoint JSON verbatim… }
}
```

Mode `0o644` is fine — there's nothing sensitive here, and it's not in the project directory so it doesn't conflate with the `0o600` PII / telemetry artefacts.

## Kill switch and offline path

**`BRISTLENOSE_PRICE_FETCH=0`** — short-circuits any network attempt. Cache is still *read* if present (a previously-fetched cache stays useful), but never refreshed. Set this in CI, in corporate environments where outbound HTTPS to non-allowlisted hosts is blocked, or by users who are paranoid about any phone-home behaviour and would rather see a slightly-stale number forever.

**Endpoint unreachable** (DNS failure, 5xx, timeout, certificate error, malformed JSON, `schema_version` mismatch): logged once per process at INFO (`pricing_fetch | status=skipped | reason=<...>`), the existing cache or bundled value is used, and no error surfaces to the user. The forecast prints with no asterisk — there is no "estimate may be stale" UI noise. Stale prices are still useful prices; the user already sees a "verify rates at <provider URL>" line in the existing cost output.

**No cache, no network:** bundled JSON. Identical to today's behaviour.

**Decision tree at cost-calculation time:**

```
read cache file
  ├─ exists and fresh (< 24h) → use cache.payload
  ├─ exists and stale         → use cache.payload, schedule background refresh
  └─ missing / unreadable     → use bundled pricing.json,
                                 schedule background refresh (if BRISTLENOSE_PRICE_FETCH != 0)
```

Background refresh is a single-shot `threading.Thread(daemon=True)`. No retry loop, no exponential backoff, no scheduling library. If it fails, the next cost calculation that finds a stale cache schedules another one — which already gives natural rate-limiting (one attempt per cost calculation, capped by the 24h TTL on success).

## Implementation specifics

These are pinned now because they are easy to get wrong and the design hinges on them. Pulled out of the prose so reviewers don't have to hunt:

**Bundled JSON load:** lazy, not at module import. Module-level `_BUNDLED: dict | None = None` sentinel populated on first call to `estimate_cost()`. Loaded via `importlib.resources.files("bristlenose.llm").joinpath("pricing.json").read_text()` so it survives PyInstaller frozen builds, snap, and the wheel uniformly. Plain `Path(__file__).parent / "pricing.json"` breaks under PyInstaller and is forbidden.

**In-process resolved table:** module-level `_resolved: dict | None = None` populated on first cost calculation, never invalidated within a process lifetime. One file read per process, not one per LLM call. Pricing does not change mid-run; refreshes apply on next process start.

**Cache write:** atomic. Write to `pricing-cache.json.tmp` opened with `os.open(path, O_CREAT | O_TRUNC | O_WRONLY | O_NOFOLLOW, 0o644)`, then `os.replace()` to the final name. `O_NOFOLLOW` matches the discipline already in `bristlenose/llm/telemetry.py` — kills the symlink-redirect class of attack even though the file isn't sensitive. `os.replace()` is atomic on POSIX, so a daemon thread killed mid-rename leaves the previous good file intact.

**Cache read:** wrap `json.loads()` in `try/except (json.JSONDecodeError, OSError, ValueError)` and treat any failure identically to "cache missing" — fall back to bundled, schedule a refresh. Corrupt cache (from a daemon thread killed mid-write before `os.replace`) recovers automatically on next call.

**Fetch:** `urllib.request` imported inside the fetch function body, not at module top. Single `urlopen(req, timeout=5, context=ssl.create_default_context())`. Read with `resp.read(65536)` cap — anything larger is malformed, fall back. TLS verification uses the system trust store; never disabled, even for debugging. Set `BRISTLENOSE_PRICE_FETCH=0` instead.

**Concurrency guard:** module-level `threading.Lock` plus a `_fetch_in_progress: bool` flag. Multiple cost-calculation paths in one `bristlenose run` (pre-flight, mid-run elaboration, end-of-run) must not spawn parallel fetches against the same cache file.

**Payload validation:** Pydantic `PricingPayload` model (consistent with the rest of the codebase). Rejects:
- `schema_version != 1`
- `pricing` with `> 1000` keys, or any key whose value isn't `[float, float]`
- Any rate `< 0` or `> 10_000` USD/Mtok (sanity ceiling — frontier rates today are <$20)
- `price_table_version` not matching `^\d{4}-\d{2}-\d{2}$` (lexical date — used in telemetry stamps, must not be a hostile string)

Any `ValidationError` → log at INFO, fall back to bundled, never to a partially-valid payload. The validation runs before `os.replace()` so a malformed payload never overwrites a good cache.

**Logging:** `logger.info("pricing_fetch | status=%s | reason=%s", status, reason)` — matches the `llm_request | provider=…` shape already in the codebase. Pricing fetch can happen outside a project context (`bristlenose doctor`, `serve` boot); when no run dir is bound, the log line goes to stderr only, not to a project log file.

**`PRICE_TABLE_VERSION` source after refactor:** today this is a module-level `str` constant in `pricing.py` consumed by the slice B telemetry writer. After the refactor, the writer must read it via `pricing.get_active_version()` (a function that returns the version of whichever payload — cache or bundled — was used to satisfy the most recent cost calculation). Module-level constant goes away. Coordinate with whoever lands slice B so the import path migrates in lockstep.

## Hosting

Static JSON file served from `https://bristlenose.app/pricing.json`. Same DreamHost shared hosting as the marketing site. No CDN — the file is ~1 KB and updates are infrequent enough that origin load is negligible. The existing TLS cert covers it.

**Update workflow:**

1. Maintainer notices a price change (vendor email, blog post, monthly check).
2. Edit `bristlenose/llm/pricing.json` in the public repo (canonical home), bump `price_table_version` to today's date.
3. `deploy-website` rsyncs to DreamHost. The deploy script copies `bristlenose/llm/pricing.json` from the public repo into the deploy staging dir at deploy time, so the live `bristlenose.app/pricing.json` is always the public-repo version (no second source of truth).
4. The same edit ships in the next release as the bundled fallback.

Single source of truth: `bristlenose/llm/pricing.json` in the public repo. The deploy step is a copy, not a separate file. No CI sync gate needed (was an open question — closed by collapsing to one canonical file).

## Update cadence

Rough budget: **one maintainer hour per month** to check the four vendor pricing pages and update the JSON. Estimated 4–10 changes per year combined across Anthropic, OpenAI, Azure (passthrough), Google. New-model launches dominate; rate cuts on existing models are second.

A future improvement is a scheduled GitHub Action that diffs the three pricing pages and opens an issue when something moves. Out of scope here — the human-driven monthly check is sufficient at current cadence.

## Trust posture

This feature must not undermine the local-first claims in [SECURITY.md](../SECURITY.md). Specifically:

- **Read-only HTTP GET.** No POST, no PUT, no headers beyond `User-Agent: bristlenose/<version>`. The server log on DreamHost sees an IP and a timestamp — same as someone visiting `bristlenose.app` in a browser. No PII, no project data, no key fingerprints, no opaque identifiers.
- **No cookies, no fingerprinting, no analytics.** DreamHost's default access log is the only record. We don't add JS, beacons, or any second-leg request.
- **The JSONL telemetry stays local.** This design touches *only* the inbound rate sheet. The outbound `llm-calls.jsonl` artefact described in slice B / SECURITY.md continues to never leave the user's machine.
- **One-line opt-out.** `BRISTLENOSE_PRICE_FETCH=0` in the environment, `.env`, or shell profile. Documented in SECURITY.md and `bristlenose --help` epilogue alongside the existing `BRISTLENOSE_LLM_TELEMETRY` switch.
- **Airgap is supported.** Bundled JSON means the app is fully functional without ever touching `bristlenose.app`. A user can `iptables -A OUTPUT -d bristlenose.app -j DROP`, set `BRISTLENOSE_PRICE_FETCH=0`, and lose nothing except slowly-decaying price accuracy.

The talking point in SECURITY.md becomes: *"Bristlenose makes one optional, anonymous HTTPS GET per day to fetch up-to-date LLM pricing. The request carries no identifiers and can be disabled with `BRISTLENOSE_PRICE_FETCH=0`. No other network calls are made."*

**App Store review:** the mechanic is bog-standard (static JSON fetch on a TTL — same pattern as every weather, currency, or config-driven app). Reviewer-facing disclosure goes in App Review Notes: *"App fetches a static JSON price sheet from bristlenose.app once per day. No user data is transmitted. Disable with `BRISTLENOSE_PRICE_FETCH=0`."* Privacy nutrition label stays "Data Not Collected" — server-side IP logs not linked to identity, no tracking. Sandbox needs `com.apple.security.network.client`, already required for the LLM sidecar so no new entitlement. Add this line to the App Review Notes draft when it's written in Track C / C3 closeout.

## Phasing against the road to alpha

Not all of this is on the TestFlight critical path. Split:

**Ship for TestFlight alpha (small London UXR cohort, weeks not months on a build):**

- Lift the in-code `PRICING` dict into a bundled `bristlenose/llm/pricing.json` and load it at module import. Pure refactor, no behaviour change, no network. This is what makes the network-fetch followup *possible* without a code change in users' builds.
- That's it. Alpha users are reachable, the cohort turns over fast, and frontier prices are unlikely to move enough in the alpha window to mislead anyone meaningfully.

**Ship for public-beta GM (wider audience, App Store distribution, builds in the wild for months):**

- The DreamHost endpoint, the cache file, the 24h TTL, the `BRISTLENOSE_PRICE_FETCH` kill switch, the SECURITY.md and App Review Notes lines. Deploy step copies `bristlenose/llm/pricing.json` from the public repo to the deploy staging dir — single source of truth, no sync gate needed.
- This is where the feature actually earns its keep. A beta user on a six-month-old build is exactly who stale prices hurt.

This phasing also defers the only piece that touches App Review (the network-disclosure line) until the submission that actually needs it — alpha TestFlight builds don't ship the fetch, so there's nothing to disclose yet.

## Out of scope (v2 candidates)

- **Vendor-pushed updates.** Webhooks, websockets, push notifications. The 24h TTL is good enough for prices that change quarterly.
- **Signed payloads.** Today's hard-coded dict is unsigned too; if the threat model ever needs supply-chain integrity for the price table, it needs it for the wheel itself first. Sign the wheel via PyPI's attestations work, then revisit.
- **Multi-currency.** All rates in USD. Per-locale conversion belongs in display logic, not the rate sheet.
- **Per-region pricing.** Azure pricing varies by region; we currently don't model this and the bundled fallback returns `None` for Azure cost. Same behaviour after this change.
- **Tiered / batch / cache-token pricing.** Anthropic's batch API is half price; cached input tokens are 10% of input rate. The forecast under-counts these savings today. Captured separately under [design-llm-call-telemetry.md](design-llm-call-telemetry.md) Phase 4.
- **Historical rate archive.** A user might want "what did this cost on the day I ran it." That information is already in the per-row telemetry (`price_table_version` stamp). Recomputing against an archive of old rate sheets is a maintainer-side analysis tool, not a user feature.

## Open questions parked for decision

1. **Sign the payload?** A half-day HMAC pass (public key in wheel, sign on deploy, verify on fetch, fall back to bundled on mismatch) kills the "DreamHost compromise → garbage prices stamped into telemetry forever" concern dead. Without it, payload validation (above) caps the blast radius at "rates within sane bounds" but a hostile maintainer-impersonator could still nudge every install's forecasts ±20%. Worth the half day or accept the risk?
2. **24h TTL or longer?** Underlying signal changes every 5–13 weeks. 24h is ~30–90× more frequent than necessary. 7 days would cut DreamHost requests 7× with essentially zero accuracy loss. 24h chosen for reach-users-fast on a price cut; longer chosen for politeness to the host. Pick.
3. **`model_aliases` field at v1?** Anthropic ships `claude-sonnet-4-5` then renames to date-pinned `claude-sonnet-4-20250514`-style. Adding `aliases: {alias: canonical}` at v1 is free now and avoids a `schema_version` bump later. Or YAGNI.
4. ~~CI sync gate between `website/pricing.json` and `bristlenose/llm/pricing.json`~~ — **closed 2 May 2026.** Resolved by collapsing to a single source of truth: `bristlenose/llm/pricing.json` is canonical, the deploy step in the website repo copies it into the deploy staging dir. No second file to drift from.
5. **Background thread vs `asyncio` task.** Pipeline is asyncio. Thread works from sync callers (CLI `doctor`, `status`) and avoids event-loop coupling. Asyncio stays inside the prevailing concurrency model. Defensible either way; pick one and stop relitigating.
6. **First-fetch trigger for desktop app.** Background-on-cost-calc means a user who only ever runs `transcribe-only` never refreshes. Hooking into `doctor` or app launch widens the trigger but adds latency to commands that have nothing to do with pricing. Status quo (cost-calc only) is the path of least surprise; raise if alpha feedback suggests otherwise.
7. **Doctor check for old `schema_version`.** When v2 ships, users on v1 clients silently keep using stale-but-valid v1 cache forever. A doctor warning ("pricing schema older than your client supports — upgrade Bristlenose for new pricing fields") is the obvious mitigation but adds a doctor surface. Future problem; flag now so it's not forgotten.

## SECURITY.md updates needed (separate PR, not part of this design)

When the network-fetch slice ships for public-beta GM:

- Reword `SECURITY.md:5` from "no telemetry" to "no usage telemetry" with a forward-pointer to a new "Network calls" section.
- Add a "Network calls" section listing both the LLM API calls (already covered) and the once-daily pricing fetch with `BRISTLENOSE_PRICE_FETCH=0` opt-out.
- Name DreamHost as the hosting sub-processor for the pricing endpoint. State that no user data is sent and that DreamHost retains access logs (IP + UA) per their default policy.
- App Review Notes: consider "Diagnostics → Performance Data, not linked to identity" instead of "Data Not Collected" — defensible against the most pedantic reviewer, only one tier "worse" on the privacy nutrition label.

## Reference files

- Current pricing module: [bristlenose/llm/pricing.py](../bristlenose/llm/pricing.py)
- Slice B telemetry stamping: [design-cost-forecast-phase1.md §schema](design-cost-forecast-phase1.md)
- Local-first promises this must not undermine: [SECURITY.md](../SECURITY.md)
- Static-site deploy mechanism: deploy script in the separate `bristlenose-website` private repo (reads `bristlenose/llm/pricing.json` from this public repo at deploy time)
- Deploy target: `bristlenose.app` (DreamHost shared hosting)
