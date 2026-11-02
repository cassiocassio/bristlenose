# Provider-problem diagnosis: technical brief

Status: proposal and measurement record, 2 Nov 2026. Nothing here is built. It backs the
title-bar pill in `docs/mockups/provider-problem-surface.html` (sections E and F) and the
DEBUG prototype `ProviderProblemPrototype.swift`.

**Evidence marks used throughout**

- **[M-unsb]** measured 2 Nov 2026 on macOS 27.0 (26A428) by `experiments/provider-reachability`, unsandboxed command-line binary.
- **[M-sb]** measured the same day, same Mac, in the App Sandbox (`app-sandbox` + `network.client`, bare Mach-O with an embedded Info.plist, ad-hoc signed). Not the shipped app, and not macOS 15.
- **[M-prior]** measured earlier on 2 Nov by the owner's probe and recorded in the mockup; not re-run here.
- **[C file:line]** read from code, not run.
- **[E]** expected, not measured. Treat as a hypothesis.

Every measurement is of a **healthy network**. The unhealthy states (Wi-Fi off, WAN down, portal,
VPN, sinkhole, interception, wrong clock) need the owner's hands; § 7 lists them and
`experiments/provider-reachability/README.md` has the steps.

## 0. What this changes in the mockup's premises

Three things the measurements say that the mockup did not know:

1. **Plain HTTP to Apple's hosts needs no ATS exception [M-sb].** A sandboxed binary with an Info.plist and no `NSAppTransportSecurity` key fetched `http://captive.apple.com/hotspot-detect.html` (200, "Success"), `http://www.apple.com/…`, `http://developer.apple.com/` and `http://support.apple.com/` without error. The same binary got `-1022 appTransportSecurityRequiresSecureConnection` in 10 ms for `http://api.anthropic.com/v1/models`, so ATS was on. Apple's own domains are evidently allowed cleartext. The mockup's "needs a narrow transport-rules exception for Apple's host … the project has no exception" is **probably unnecessary**. Caveats: one OS (27.0), a bare executable and not a bundled `.app`, and nothing on macOS 15. Confirm in the real app before dropping the plan (§ 7).
2. **A proxy's 403 page already reads as "key rejected" [C failure_classifier.py:148-149, LLMValidator.swift:251-256; M by running the classifier on the stub replies].** The classifier's last-resort rules are bare `401 → INVALID_KEY` and `403 → INVALID_KEY`. A stub corporate block page (403, HTML, no `request-id`) classifies as `invalid_key`, a 502 page as `server_error`. Row 7 ("a proxy answers instead of the provider") would light the *key rejected* pill with "Add a new key in Settings". The provider-signature check (§ 3.3) is a correctness fix, not decoration.
3. **`NETWORK` is almost never produced, and carries nothing.** § 2.

## 1. Audit of every LLM call site

Produced by reading `bristlenose/`, `bristlenose/server/`, `frontend/src/` and `desktop/Bristlenose/Bristlenose/`; every cell is **[C]**. The headline claims were re-checked by grep (the single `postLLMFailure` caller, the swallowed `except` in `elaboration.py:660`, the untracked re-apply `except` at `autocode.py:1270`, no caller passes `http_status`). Rows the audit could not confirm are marked *unverified*.

All real provider calls go through `LLMClient.analyze` (`llm/client.py`; SDK sites at `:916`, `:1058`, `:1201`, `:1343`, `:1500`, any-llm `:1798`). Per-call outcomes are written to `llm-calls.jsonl`, which the host must not read (re-identification surface, root `CLAUDE.md`).

Channels by which the Mac host can learn of a refusal today: **(A)** the run terminus in `pipeline-events.jsonl` (`run_failed.cause`), read by `deriveFailureFromEvents` (`PipelineRunner.swift:3339`); **(B)** the stderr regex `categoriseFailure` (`PipelineRunner.swift:~3178`, patterns at `:3230`); **(C)** the `llm-failure` bridge post, `BridgeHandler.swift:1533`, which Swift acts on for `out_of_credit` and `invalid_key` only (`ProviderProblem.swift:35-41`). No other path feeds `ProviderProblemModel`.

| # | Site | file:line | Process | Failure classified how | Host learns? | Silent? |
|---|---|---|---|---|---|---|
| 1 | s05b speaker splitting | `stages/s05b_identify_speakers.py:343` (except `:354`) | `run` subprocess | none: bare `except`, message to an `errors` list, unsplit segments returned (`:359-369`) | no cause; CLI warning only (`pipeline.py:3138`) | **yes** |
| 2 | s05b speaker-role refinement | `s05b…py:455` (except `:486`) | `run` | none: logged at debug, heuristic roles stand | no | **yes** |
| 3 | s08 topic segmentation | `stages/s08_topic_segmentation.py:162` | `run` | `_build_cause` → `categorise_exception` | A when every session fails (`PipelineAbandonedError`, `pipeline.py:3558`); a partial failure is `run_completed` + summary → "completed with problems" row, **no pill** | weak when partial |
| 4 | s09 quote extraction | `stages/s09_quote_extraction.py:361` | `run` | `_build_cause`; any-llm deadline downgraded NETWORK→UNKNOWN (`run_lifecycle.py:806-816`) | as 3 (abandon `pipeline.py:3828`) | weak when partial |
| 5 | s10 clustering, s11 theming | `stages/s10…py:69`, `s11…py:70` | `run` | `_build_cause` | A (attempted = 1, so one failure abandons: `pipeline.py:3945`) | no |
| 6 | Discussion lens | `discussion/stage.py:96,119,139,157` | `run` | `_build_cause` into `outcome.failed`; stage "never abandons" (`pipeline.py:2105-2124`) | writes a `failed` record and prints "Discussion lens not built"; whether it reaches the summary is *unverified* | yes, as far as shown |
| 7 | readable chain (s05b/s08/s09 early) | `readable_chain.py:114,123` | `run` | as rows 1-4 | as rows 1-4 | as rows 1-4 |
| 8 | `analyze` command | `pipeline.py:4607` | `run` kind analyze | `_build_cause`; **no key preflight on this path** (only call is `cli.py:1706`) | A | no |
| 9 | **key preflight** (paid, inert call) | `preflight/api_key.py:292` (Claude), `:379`/`:449` (ChatGPT/Azure), `:520` (Gemini), `:604` (local), `:656` (any-llm) | `run`, before the lifecycle opens (`cli.py:1706`) | `_classify_network_error` (`:228`) then `classify_exception` | **exit 2, no terminus** → host falls back to B (stderr regex) | no for credit; key rejection deliberately not used for the pill when unstructured (`ProviderProblem.swift:50-60`) |
| 10 | AutoCode first apply | `server/autocode.py:403` | serve sidecar (`routes/autocode.py:374`) | `classify_exception` → `AutoCodeJob.failure_kind` (`:551`, `:599`) | **C** via the chip: `GET …/autocode/{fw}/status` → `ActivityChipStack.tsx:165-168` → `postLLMFailure` (`:317-318`) | no for credit/key; **rate-limit, server error, network, model-unavailable are shown on the chip and dropped by the host** |
| 11 | AutoCode catch-up (tracked) | `autocode.py:1081` via `routes/data.py:1819`, `track_status=True`; `except` `:1274-1281` | sidecar | `classify_exception` → `failure_kind` | C, as 10 | weak: needs a report window polling; background-window behaviour *unverified* |
| 12 | **AutoCode re-apply after `run_completed` (untracked)** | `autocode.py:1375` `reapply_active_frameworks`, launched `app.py:1431-1465` | sidecar | **none**: `logger.exception("Re-apply failed …")` (`:1271`); `track_status` False, so no `failure_kind` | **not at all** | **yes: a paid multi-batch call on every finished run** |
| 13 | **Signal elaboration** (`generate_elaborations`) | `server/elaboration.py:625`; swallowed at `:660-661` | sidecar | **none**: `logger.exception("Signal elaboration LLM call failed, returning cached only")` | **not at all** | **yes**. Callers: startup repair `app.py:136`, after-run snapshot `app.py:1453`, after AutoCode `routes/autocode.py:393`, `GET /signals/codebooks?elaborate=true` |
| 14 | **Signals snapshot / card refresh** | `routes/signals.py:1214-1250` | sidecar | elaboration already swallowed; `_signal_snapshot_has_complete_narratives` false → warning, no snapshot written | **not at all**; last good snapshot keeps serving, "Picking up Signals…" may linger until `end_signals_preparing` (`app.py:1458`) | **yes** |
| 15 | Signals SSE stream | `routes/signals.py:1012-1075`, `event: error\ndata: {}` at `:1070` | sidecar | bare `except`, empty payload | `streamElaborations` (`utils/api.ts:748`) has no non-test caller | dead path |
| 16 | Chat lens answer | `server/chat_lens.py:274`; route 502 at `routes/chat_lens.py:~95-100` | sidecar, lab page only (`experimental_chat_lens`, default True `config.py:262`; mounted `app.py:429-440`) | none; HTTP 502 with `f"{type(exc).__name__}: {exc}"` (raw exception text) | HTTP to the lab page; SPA has no caller | host: not at all |
| 17 | Chat lens support judge | `chat_lens.py:193` | sidecar | bare `except`; claims stay "unchecked" (flag-not-gate, by design) | no | yes (by design) |
| 18 | Codebook builder synthesize / refine / decisions | `server/codebook_builder.py:286` | sidecar, routes mounted unconditionally (`app.py:381`) | none; no try/except, FastAPI 500 | HTTP 500; no SPA caller found (the lab page is the likely one, *unverified*) | host: not at all |
| 19 | Codebook builder candidate scan | `codebook_builder.py:362` | sidecar | `gather(return_exceptions=True)`, `scan.errors += 1` | in the response body; consumer *unverified* | yes for the host |
| 20 | MCP grounding | `server/mcp_server.py`, `server/grounding.py` | sidecar | **no LLM call**: retrieval only (`load_cached_elaborations`); no `LLMClient` import | n/a | n/a |
| 21 | Transcript edits | `routes/transcript.py`, `routes/data.py` | sidecar | **no LLM call itself**; `note_quotes_counting` may schedule an AutoCode catch-up (row 11) | via row 11 | via row 11 |
| 22 | Tag suggestion | none found | n/a | no LLM tag suggestion in `bristlenose/` | n/a | n/a |
| 23 | `doctor` key checks | `doctor.py:447` `check_api_key`; Claude `/v1/models` `:1978-2020`, ChatGPT `:2022`, Azure POST `:2055`, Gemini `:2141` | CLI | ad hoc `(ok, err)` tuples, not `LLMFailureKind`; 429/5xx counts as "valid" | only if the Swift Health window runs the CLI (*unverified*); not wired to the pill | credit state is invisible on `/models` by design |
| 24 | **Swift key validator** | `LLMValidator.swift:36` `validate`, `:132` `buildRequest`, `:206` `classify` | Swift host | own status classifier; Claude is a billed `POST /v1/messages` `max_tokens=1`, the rest are free GETs | direct (`recordVerdict` `:533`, `LLMSettingsView.swift:1073`) | no |
| 25 | Ollama pull / probe | `LLMValidator.swift:359`, `:607` | Swift host | URLError mapped | direct | no |

**The silent ones, ranked by the owner's worry (a few cents, nobody told):**

1. **Row 12, post-run AutoCode re-apply.** Fires on every finished run. A dead key or empty account leaves quotes untagged with only a log line. Also the one most likely to run *immediately after* a run that itself failed for the same reason.
2. **Rows 13-14, signal elaboration and the card refresh.** Refreshed after every run, every AutoCode completion and every startup repair. `except Exception: logger.exception(…)` and nothing else: no kind, no event, no HTTP status. This is exactly the "signal card refresh" case in the mockup's C′ (the in-place note has nothing to read from).
3. **Rows 1-2, s05b.** A refusal is a CLI warning; the run can "succeed" with degraded roles if later stages are served from cache.
4. **Rows 16-19, chat lens and codebook builder.** Raw exception text or an uncaught 500 to a lab page; no host path. Lower stakes (lab surfaces) but the chat lens is the product's other assistant surface.
5. **Rows 3-4, partial s08/s09.** `run_completed` + summary never reaches `ProviderProblemModel`; a run that is mostly refused but not abandoned leaves no pill. `noteCreditIfTheRunUsedAnLLM` (`PipelineRunner.swift:1563-1584`) may even *clear* a recorded refusal after such a run (depends on `runUsedAnLLM`, *unverified*).
6. **Row 10-11, host drops four of six kinds.** Rate limit, server error, network and model-unavailable reach the chip but `fromLLMFailureKind` returns nil for them.
7. **Transcript edits (21)** are not themselves a call. The mockup's phrase "a transcript edit that needs a few cents" is true only through the catch-up chain (row 11), and only for tracked passes.

**Consequence for the design.** The pill "appears only after a refused call" (owner decision). Today a refused call reaches the host from exactly two producers: a run (A/B) and an AutoCode chip (C). Rows 12-14 are the incidental calls and they reach nobody. A single serve-side seam is needed (§ 2.3), not a per-surface patch. There is no `OutOfCreditModel` symbol any more; `ProviderProblemModel` replaced it (`ProviderProblemModel.swift:227` `recordRefusal`, `:278` `noteRunSucceeded`), though `BridgeHandler`'s comment still uses the old name.

## 2. What `NETWORK` carries today, and the wire-contract change

### 2.1 Today

- `LLMFailureKind.NETWORK` exists (`failure_classifier.py:53`) but **`_RULES` has no rule that returns it** (checked by reading all 200 lines of the table). `classify_exception` / `classify_fields` cannot return it for Claude, ChatGPT, Azure, Gemini or Ollama.
- The only producer is `anyllm.classify` → `is_network_error` (`anyllm.py:417-418`, `:555-572`): a **boolean** from exception class names (`_NETWORK_NAMES`: `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `ReadError`, `WriteError`, `APIConnectionError`, `APITimeoutError`, `RemoteProtocolError`), walking `original_exception`, `__cause__`, `__context__`.
- For built-in providers the run path detects network separately: `run_lifecycle.categorise_exception` (`:743-748`) calls `is_network_error`, then a text regex `_NETWORK_RE`, yielding `CauseCategoryEnum.NETWORK` on a `Cause`.
- `Cause` (`events.py:258-294`) has `category, code, message, reason, provider, model_host, stage, session_id, exit_code, signal, signal_name`. `code` is meant to hold the HTTP status (`run_lifecycle.py:869`) but **no caller passes `http_status=`** (grep: definition and docstring only), so it is always `None`. `message` is `"<stage> failed: <ClassName> on <provider>"`, built from structured fields only, never `str(exc)` (a rule: provider bodies can echo transcript, `stages/CLAUDE.md:315`). Keep that rule.
- Swift: the terminus-level decoder reads only `category, message, signal_name, exit_code` (`EventLogReader.swift:101-115`); the summary-level one adds `code, reason, provider, stage, session_id` and ignores `model_host` (`PipelineSummary.swift:190`). `PipelineFailureCategory.network` exists (`PipelineRunner.swift:19`) and shows as a failed-row category. `ProviderProblemCondition` has only `keyRejected` and `outOfCredit` (`ProviderProblem.swift:11-12`), so **network never lights the pill**.
- The preflight has its own `error_class="network"` (`api_key.py:228-262`: TLS, proxy, connect) but aborts with exit 2 and no terminus, so the host sees only the stderr tail and the regex `connection refused|timed out|dns|could not resolve` (`PipelineRunner.swift:3230`).

### 2.2 What the Mac host needs

Diagnosis needs to know *which phase died* and *whether the provider itself spoke*. The existing fields cannot say either. Proposed additive fields, all optional, all derived from the exception chain and response headers (never bodies):

| Field | Values | Source | Why the host needs it |
|---|---|---|---|
| `http_status` (fill the existing `code`) | int | `exc.status_code`, `_extract_status` (`failure_classifier.py:255`) | splits 401/402/429/5xx from a transport failure; today always null |
| `error_class` | exception class name, e.g. `APIConnectionError`, `ConnectTimeout`, `SSLCertVerificationError` | `type(cur).__name__` along the chain | the only transport detail the Python side has |
| `phase` | `dns` / `connect` / `tls` / `request` / `response` / `unknown` | map the chain: `socket.gaierror` → dns; `ConnectError`/`ConnectTimeout` → connect; `ssl.SSLError`/`SSLCertVerificationError` → tls; `ReadTimeout`/`RemoteProtocolError` → response | separates rows 5, 6, 10 without a probe; a TLS failure is the wrong-clock / inspection signal |
| `host` | provider API host only (`api.anthropic.com`, the Azure resource host, `127.0.0.1:11434`) | the SDK's base URL, **never** the full URL (Gemini puts the key in the query, `LLMValidator.swift:96-98`) | which host to resolve and probe; Azure's is user-supplied |
| `provider_signature` | bool | response carried the provider's own error JSON shape and/or `request-id` header | distinguishes "Claude said no" from "a proxy said no" (§ 0.2); absent on transport errors |
| `request_id` | string | `request-id` / `x-request-id` header | lets a bug report be matched to the provider's logs; not a secret |
| `kind` | `LLMFailureKind` value | the classifier | one vocabulary on the wire |
| `call_site` | enum: `run_stage`, `autocode`, `autocode_reapply`, `signal_elaboration`, `chat_lens`, `codebook_builder`, `preflight` | caller | lets the host apply the owner's persistence rule ("an incidental refusal on an acknowledged condition gets an in-place note and nothing in the title bar") |
| `explicit` | bool | caller | whether the researcher asked for it (Analyse, Autocode) |

Add a **`NETWORK` rule path** in `failure_classifier.py` that actually fires from `classify_fields` (transport exception classes, no status), so `kind=network` is produced for built-in providers too, and the SDK-specific class names stay in one place (`anyllm._NETWORK_NAMES` is the seed). Add `phase`/`error_class` extraction beside `_extract_status`.

Swift side: decode the new keys in both `Cause` structs (they already tolerate unknown keys per `events.py` comments); extend `ProviderProblemCondition.fromLLMFailureKind` (`ProviderProblem.swift:35`) to carry `network` plus the evidence, not only credit and key.

### 2.3 One seam for serve-side calls

Today a serve call that dies has no way to tell the host except by being an AutoCode chip. Proposal (design only):

- A tiny `report_llm_refusal(kind, provider, call_site, evidence…)` in the sidecar, called from the `except` of rows 11-14 and 16-19 (and from `LLMClient` itself on any raised provider error, if the process is hosted: `_BRISTLENOSE_HOSTED_BY_DESKTOP`).
- It writes **one line to the sidecar's stdout** in a stable prefix (`[bristlenose] llm-refusal: {json}`), which `ServeManager.handleLine` (`ServeManager.swift:1623`) already reads for `auth-token:` and `Report:` lines. No new port, no new SPA code, no dependence on a report window being open (which is what weakens row 11), no events-log write (serve calls don't use `run_lifecycle`). The JSON carries the § 2.2 fields and is redacted by the same `BristlenoseShared.redactKeys` used on run output.
- The SPA's `postLLMFailure` stays for the chip's own message; the host de-duplicates on `request_id` + time.

Alternatives considered: a new SPA bridge post per surface (rejected: N surfaces, each can forget; and needs a window); polling `/api/…/llm-health` from Swift (rejected: a poll for a condition that only exists after a refusal); reading `bristlenose.log` (rejected: log text is not a contract).

## 3. What a sandboxed macOS app can know

All of § 3 was measured by `probe.swift`, run as an App-Sandboxed binary on a healthy Wi-Fi network [M-sb] unless marked.

### 3.1 Network path: `NWPathMonitor`

- **Works inside the App Sandbox [M-sb].** First update within the 2 s the probe allows: `status satisfied`, `supportsDNS true`, `supportsIPv4 true`, `supportsIPv6 false`, interfaces `[en0 wifi]`, `isExpensive/isConstrained false`, `unsatisfiedReason notAvailable` (the field is present and meaningless when satisfied), and **`gateways: [192.168.4.1]`**. Identical in the unsandboxed run [M-unsb]. No entitlement beyond `network.client`.
- **The unsatisfied shape [M-sb, emulated].** A monitor restricted to `requiredInterfaceType: .cellular` (a Mac has none) reports `unsatisfied`, `unsatisfiedReason notAvailable`, `interfaces []`, `gateways []`, `supportsDNS false`. This shows the fields' shape, **not a real offline state**; Wi-Fi off was not tried (§ 7).
- `satisfied` means a route exists, not that the internet answers (a router with WAN down reads satisfied [E, and the premise of the whole ladder]).
- VPN: `usesInterfaceType(.other)` is the tunnel flag, field recorded as `uses_other`; no VPN available here, so false and untested [E].
- Cost: no traffic. It can run always-on at no cost; the design below samples it once at diagnosis time.

### 3.2 Control probe

- `https://captive.apple.com/hotspot-detect.html`: 200, `content-type: text/html`, body `<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>`, no `request-id`, a `via: …ts.apple.com` header; 41-120 ms across runs [M-unsb, M-sb]. (The mockup's 38-48 ms [M-prior] agrees.)
- **Plain HTTP: the same URL over `http://` also returns 200 "Success" in 30-86 ms [M-unsb, M-sb], sandboxed, with and without an ATS exception** (§ 0.1).
- **The HTTPS-only limit stands for TLS reasoning [E].** A captive portal cannot present a valid certificate for `captive.apple.com`, so over HTTPS it surfaces as a TLS error indistinguishable from a wrong clock or an inspecting proxy. Positive portal evidence needs the plain-HTTP probe: a 3xx or a 200 whose body is not "Success". The probe returns the 3xx itself (redirects are not followed) so a `Location:` is captured. Untested against a real portal. The stub's `portal/redirect` and `portal/hotspot` routes show the probe *records* both shapes [M-unsb] (`302` + `location`; `200` HTML), which says nothing about how real portals behave.
- Apple's check is a courtesy endpoint, not a documented API [E]: its contract (body text, host) could change. Treat anything but an exact "Success" as "not clean", never as "portal".

### 3.3 Keyless provider probe: signatures

Measured 2 Nov 2026, GET with no credential [M-unsb and M-sb agree]:

| Provider | URL | Result | Signature |
|---|---|---|---|
| Claude | `api.anthropic.com/v1/models` | 401 `application/json`, 183-222 ms | `{"type":"error","error":{"type":"authentication_error","message":"x-api-key header is required"},"request_id":"req_…"}`; headers `request-id`, `cf-ray`, `server: cloudflare` |
| ChatGPT | `api.openai.com/v1/models` | 401 `application/json`, 245-265 ms | `{"error":{"message":"Missing bearer authentication in header","type":"invalid_request_error","param":null,"code":null}}`; headers `x-request-id`, `cf-ray`, `server: cloudflare` |
| Gemini | `generativelanguage.googleapis.com/v1beta/models` | **403** `application/json; charset=UTF-8`, 85 ms | `{"error":{"code":403,"message":"Method doesn't allow unregistered callers (callers without established identity)…`, status `PERMISSION_DENIED`; **no `request-id`**, `server: scaffolding on HTTPServer2` |
| Azure OpenAI | `<resource>.openai.azure.com/openai/deployments` | host is user-supplied; a made-up resource name gave **`-1003 cannotFindHost`** in 34 ms (Azure resource hosts resolve only if the resource exists) | real-resource signature **unmeasured**; the stub assumes `apim-request-id` [E] |
| Ollama | `http://127.0.0.1:11434/api/tags` | 200 JSON `{"models":[…]}`, 54-167 ms (running on this Mac); with nothing listening: `-1004 cannotConnectToHost` (the `refused-port` case) | local; "reachable" means loopback, the network ladder does not apply |

Reading:

- **Claude and ChatGPT** have a strong signature: JSON error shape + a request-id header. Either present means "the provider's own server answered".
- **Gemini's is weaker**: a Google JSON error with `status: PERMISSION_DENIED`, no request-id header. And the keyless 403 classifies as `invalid_key` through the `PERMISSION_DENIED` rule (`failure_classifier.py:145-146`), which is the same string a leaked or restricted *real* key produces; the keyless probe proves reach and nothing about the key, as for Claude.
- **A 401 means the same thing for everyone: reached and refused. It says nothing about the user's key** (no key was sent).
- The probe **never sees 402, 429, 5xx or 529** from the real providers (those need a billed or rate-limited call). The refused call's own status supplies the "Claude responding" and "Your account" rungs; the probe only supplies "reachable".

### 3.4 DNS comparison

`getaddrinfo` for the provider host and the control host, with each address classed public / private / loopback / link-local / cgnat / unspecified.

- Healthy [M-sb, M-unsb]: captive.apple.com → 2 public (17.253.x), api.anthropic.com → 1 public (160.79.104.10), api.openai.com → 2 public (Cloudflare), Gemini → 8 public (172.217.x); 9-18 ms each.
- NXDOMAIN → `-1003` with `_kCFStreamErrorDomainKey 12, _kCFStreamErrorCodeKey 8` (`EAI_NONAME`) [M-unsb, M-sb]: a distinguishable DNS failure.
- A sinkhole (`0.0.0.0`, `127.0.0.1`, a private address) is **not yet measured**; the probe classifies the answer so the comparison is one line [E that filtering DNS answers with an unspecified or private address, per the mockup].
- `getaddrinfo` cannot be cancelled and can block for several seconds on a dead resolver [E, normal libc behaviour]. The probe runs it on a global queue and abandons after 8 s; the service should abandon at its own budget (§ 5).

### 3.5 System proxy settings

`CFNetworkCopySystemProxySettings` works sandboxed [M-sb]. Healthy output here is only `ExceptionsList: ["*.local","169.254/16"]` and `FTPPassive: 1`, both unscoped and under `__SCOPED__.en0`: no proxy enabled. Presence of `HTTPEnable/HTTPSEnable/ProxyAutoConfigEnable` is a hint that the network is managed [E]. It says what is configured, not what happened.

### 3.6 Gateway TCP probe

`NWConnection` to the gateway reported by the path, ports 53/80/443, 1.5 s each [M-sb and M-unsb identical]:

- port 53: `ready` in 6 ms (this router runs DNS);
- ports 80, 443: state `waiting` with `POSIXErrorCode 61 ECONNREFUSED`. `NWConnection` reports a refusal as `waiting` and keeps retrying, so the probe always spends its 1.5 s window; a design would read the first `waiting` error and cancel at once.

So **feasible in the sandbox with only `network.client`**, and *a refusal is evidence the router is alive* (it answered with a RST). What is *not* known: behaviour with the router down (expect `waiting` with `EHOSTUNREACH`/timeout [E]), and with a VPN that hides the LAN gateway. It splits "router down" from "WAN down" only if the router answers some port, and routers differ in which they answer, so **do not promise a router rung** (matches the mockup's stance). Use it, if at all, as an extra line of evidence for "No internet connection" (row 2): "your router answered but nothing beyond did".

### 3.7 `URLSessionTaskMetrics`

Not re-measured; the owner found it **empty for all four failed requests** [M-prior]. Dropped; the probe does not record it.

### 3.8 URLError codes (what the failed call itself says)

Measured [M-unsb and M-sb identical unless noted]:

| Case | URLError | Stream error domain/code | Time |
|---|---|---|---|
| Host does not exist (`.invalid`) | -1003 cannotFindHost | NetDB(12) / 8 | 22-48 ms |
| Nothing listening (127.0.0.1:1) | -1004 cannotConnectToHost | POSIX(1) / 61 | 44-95 ms |
| Black-holed address 10.255.255.1, 4 s timeout | -1001 timedOut | domain 4 / -2103 | 4018-4070 ms (the timeout is accurate to ±70 ms) |
| Self-signed cert on a TLS listener | -1202 serverCertificateUntrusted, `has_peer_trust true` | SSL(3) / -9807 | 49-127 ms |
| https URL to a plain-HTTP server | -1200 secureConnectionFailed | SSL(3) / -9836 | 49-127 ms |
| Server closes cleanly with no reply | -1005 networkConnectionLost | domain 4 / -4 | 57-137 ms |
| Server RSTs | -1005 networkConnectionLost (unsandboxed: -1001 at first, before the stub was fixed; after the fix, -1005 in both) | | 56 ms |
| Server sends non-HTTP bytes | **no error: HTTP 200 with the garbage as the body** [M-unsb, M-sb] | | 56 ms |
| Plain HTTP to a non-Apple host (sandboxed, ATS on) | -1022 appTransportSecurityRequiresSecureConnection | | 10-17 ms |
| `-1009` notConnectedToInternet | **not measured** (needs Wi-Fi off) | | |
| `-1201` bad date / `-1204` not yet valid | **not measured** (needs a wrong clock; a local cert cannot be made "trusted but expired" without installing a root, which changes the system trust store) | | |

Two things the mockup should take from this:

1. The `-9807` / `-9836` stream codes split "cannot verify the chain" from "the far end isn't speaking TLS", which `-1202` / `-1200` already do. `-1201` (bad date) is the candidate separator between **wrong clock (row 4)** and **inspection (row 6)** [E]; if wrong-clock reports `-1201` and a MITM with an untrusted CA reports `-1202`, row 4 no longer depends on "control and provider both fail TLS". Worth the owner's 5 minutes (§ 7, step 7).
2. A garbage reply produced HTTP 200 with the junk as body, so a status-only check is not a signature check.

### 3.9 Local network and sandbox entitlements

`network.client` alone sufficed for everything above, including loopback and the gateway TCP probe [M-sb]. The gateway connection (a 192.168.x address) completed on 27.0 without the probe handling any prompt, but the run was from a terminal and nobody watched for a dialog. Whether a local-network privacy prompt (`NSLocalNetworkUsageDescription`) appears for an app, and on macOS 15, is **unmeasured** [E that it can].

## 4. Per-provider keyless signatures: summary and gaps

See § 3.3. Gaps to fill with the owner's hands: Azure with a real resource (keyless signature, and what a wrong `api-version` or an AAD-only resource says), Ollama from a non-running state through the validator path, and the real 402/429/5xx/529 shapes, which only a billed or rate-limited call produces. For those the stub's bodies follow the shapes the classifier already reads (`failure_classifier.py` rules), so what is established is **how our classifiers treat those bodies**, not that the providers send them:

| Stub reply | Python `classify_llm_failure` | Notes |
|---|---|---|
| Claude 400 "credit balance is too low" | `out_of_credit` | the real wire, per `failure_classifier.py:20-24` |
| Claude 402 `billing_error` | `out_of_credit` | |
| Claude 429 / 500 / 529 `overloaded_error` | `rate_limited` / `server_error` / `server_error` | 529 is not separated from a plain outage |
| ChatGPT 429 `insufficient_quota` | `out_of_credit` | same status as ordinary 429 → `rate_limited` |
| Gemini 400 `API_KEY_INVALID` | `invalid_key` | Swift `classify` also maps this (`LLMValidator.swift:257`) |
| Gemini 403 (any, incl. keyless) | `invalid_key` | |
| Gemini 429 / 503 | `rate_limited` / `server_error` | credit and rate fold together by design |
| Azure 401 / 404 DeploymentNotFound / 429 / 500 | `invalid_key` / `model_unavailable` / `rate_limited` / `server_error` | |
| **Proxy 403 HTML, no request-id** | **`invalid_key`** | wrong: not the provider |
| Proxy 407 | `bad_request` | |
| **Proxy 502 HTML** | **`server_error`** | wrong: not the provider |
| Portal 302 / 200 HTML | `unknown` | |

(Run by feeding the stub bodies, parsed as `bristlenose/llm/failure_classifier.py` does, to `classify_llm_failure`; the Swift `LLMValidator.classify` reads the same way for 401/403/402/429 by code reading, `:248-285`.)

## 5. Proposed design: the diagnosis service in the Swift host

Design only. Names are suggestions.

### 5.1 Shape

```
ProviderDiagnosis (service, @MainActor-free; async)
  func diagnose(refusal: Refusal, budget: Duration = .seconds(3)) async -> Diagnosis

Refusal      { kind: LLMFailureKind?, provider, httpStatus?, errorClass?, phase?,
               host?, providerSignature: Bool?, requestId?, callSite, explicit, at: Date }

Evidence     { path: PathSample?            // NWPathMonitor, one snapshot
               control: ControlResult?       // https (and http only on TLS failure)
               dns: [HostResolution]         // provider host + control host
               providerProbe: ProbeResult?   // keyless GET, signature check
               gatewayTCP: [PortResult]?     // optional, evidence only
               proxyConfigured: Bool, vpnUp: Bool }

Diagnosis    { rungs: [Rung]                 // the ladder, in order
               version: FailureVersion       // one of the 13 rows
               pill: PillDecision            // .pill(kind) | .inPlaceOnly
               line1/line2 keys              // locale keys, never sentences
               details: forensic record (for Copy details) }

Rung         { id: connected | signedIn | internet | reachable | responding | account
               state: pass | warn | fail | notChecked }
```

`ProviderDiagnosisClassifier.classify(refusal:evidence:) -> Diagnosis` is a **pure function** (no URLSession, no clock): everything that decides is testable by value. The service only gathers `Evidence`, then calls it. `notChecked` is set for every rung above the first failure.

### 5.2 Inputs, in cost order

1. **The refusal itself** (free): kind/status/phase/signature from § 2.2. If `kind ∈ {out_of_credit, invalid_key, rate_limited}` **and** `providerSignature == true`, the provider spoke: rungs up to *responding* pass, *account* fails. **No probe is needed.** This is the common case and costs nothing.
2. **Path snapshot** (free, no traffic).
3. **DNS of provider and control host** (one `getaddrinfo` each, abandoned at budget).
4. **Control probe** (HTTPS first; HTTP only if HTTPS fails with TLS, so cleartext is rare).
5. **Keyless provider probe** (only when there was no provider-signature reply and the control host answered).
6. **Gateway TCP** (only to add a line to "No internet connection"; optional, off by default in v1).

Probes 3-5 run **concurrently** (a task group), all under one deadline; each request sets `timeoutIntervalForRequest = timeoutIntervalForResource = remaining budget`, `waitsForConnectivity = false`, no cookies, `ephemeral`, no redirects followed. Measured: healthy network, all concurrently, ≈ 250 ms [M-sb: DNS 9-18, control 41-120, provider 183-265 ms]. Worst case = budget (**3 s**), because the timeout is accurate to ±70 ms [M-sb]; the `getaddrinfo` thread is abandoned, not awaited.

### 5.3 When it runs

- **Only after a refused call**, never on a timer, never at launch, never from a stored verdict (owner decision). One diagnosis per refusal, **coalesced**: refusals within ~10 s share one `Evidence`.
- **Skipped entirely** when `Refusal.providerSignature == true` with a classified kind (case 1 above): the refusal already is the evidence.
- Offline (`path.status != satisfied`): short-circuits to row 1, no probes, no pill.
- Never from the verdict cache (`LLMValidator` sticky verdict), never from Settings revalidation (that path keeps its own mapping; the two should agree on the pure classifier but have different triggers).
- Result cached ~60 s per `(provider, host)` for the popover's "Connection details" disclosure; re-run on explicit "Try again".

### 5.4 Mapping to the mockup's 13 failure versions

`E`/`M` marks what the rule needs and whether we have seen its input.

| # | Version | Rule (pure classifier) | Pill? | Input measured? |
|---|---|---|---|---|
| 1 | Offline | `path.status == unsatisfied` (or refusal `-1009`) | no | field shape only [M-sb emulated]; real state **[E]** |
| 2 | Internet down | path satisfied; control fails with `-1003/-1001/-1009`; provider DNS fails or times out | no | **[E]** |
| 3 | Captive portal | HTTP control returns 3xx or 200 ≠ "Success" | no (owner: positive evidence only) | stub only; **real portal [E]** |
| 4 | Wrong date/time | control **and** provider both fail TLS (`-1201`/`-1204`, or `-1202` when also untrusted) | no | `-1201` **[E]**; cannot be produced without changing the clock |
| 5 | Network blocks the provider | control OK; provider DNS fails / resolves to `unspecified`/`private`/`loopback` / refused / reset / timeout | **warn** | refused `-1004`, reset `-1005`, timeout `-1001` [M]; sinkhole DNS **[E]** |
| 6 | Network inspects TLS | control OK; provider fails `-1202`/`-1200`; ideally control also OK | **warn** | `-1202`/`-1200` [M locally]; real MITM **[E]** |
| 7 | Proxy answers for provider | control OK; HTTP reply with **no provider signature** (HTML, 403/407/502, no request-id) | **warn** | stub only [M]; **today's classifier misreads it as key/outage (§ 0.2)** |
| 8 | Provider outage | provider signature present, 5xx/529 | in place; pill if it persists | classifier on stubs [M]; real 5xx/529 **[E]** |
| 9 | Rate limited | signature, 429 | no | stubs [M] |
| 10 | No answer | control OK, provider times out `-1001`, nothing else | no (until repeats → 5) | `-1001` accuracy [M]; cannot tell from black hole by design |
| 11 | Key rejected | signature + 401/403 `authentication_error` **on a call that sent a key** | **error** | stubs [M]; keyless 401 proves nothing |
| 12 | Out of credit | signature + 402 / credit-balance body | **warn** | stubs [M]; the real wire per classifier comments |
| 13 | Can't tell | otherwise | no | |

Two rules worth stating: **(a)** a 401/403 counts as *key rejected* only when `providerSignature` is true or the status came from a structured provider error; a bare 401/403 without a signature goes to row 7, never row 11. **(b)** Rows 5-7 share one pill and one sentence; the classifier keeps them distinct only for the forensic record.

### 5.5 Privacy

- The probes send **no key, no project data, no participant data**. Hosts contacted: `captive.apple.com`, the provider's own API host, the user's Azure host, loopback for Ollama. An IP address and a timestamp reach Apple and the provider, as every LLM call already exposes to the provider.
- This is **a new outbound request to Apple** the user did not trigger directly. It must be in the privacy surfaces: the three website pages and the AI disclosure (`AIConsentView`; root `CLAUDE.md` says a change to what leaves the machine edits all three pages) and probably a consent-version look. Run only after a failure, once per refusal.
- Never put the key, a URL with a key (Gemini), or `str(exc)` into the evidence record; keep `Cause.message` rules (§ 2.1). "Copy details" prints codes and kinds, not bodies.
- No history storage beyond the last refusal and the last diagnosis. (The mockup's "when the provider last answered" would use `llm-calls.jsonl`, which the host must not read; if wanted, the sidecar can report a last-success timestamp over the § 2.3 seam.)

### 5.6 Test strategy

- **Pure classifier + shared fixture**, in the style of `tests/fixtures/shared-format-contract.json`: `tests/fixtures/provider-diagnosis-contract.json`, a list of cases `{name, refusal, evidence, expect: {version, rungs, pill, line1_key, line2_key}}`, asserted from pytest (a Python reference classifier, or at minimum a schema + exhaustiveness check that every one of the 13 versions has a case and every `LLMFailureKind` has a mapping) **and** from Swift Testing (the real classifier). A drift in one side fails its suite. The Python `classify_llm_failure` rules and the Swift `LLMValidator.classify` already duplicate each other with no fixture; the same fixture can carry their agreement for the status+body cases of § 4.
- **The cases are the stub replies and the measured URLError table**, so the fixture is seeded from `results/*.json` (keep a sanitised extract in the fixture, not the raw files).
- Mutation: each case proven red against a classifier that ignores its distinguishing field.
- **Service tests** with an injected `Evidence` provider (no network): budget expiry returns whatever finished, `notChecked` below a failed rung, coalescing, "skipped when the refusal carries a signature".
- A test that every rung/version has all locale keys (the pill copy is 21 locales, `check-locales.py`).
- Do not unit-test NWPathMonitor itself; keep it behind a one-method protocol.
- Live behaviour: `experiments/provider-reachability` runs against real states; its output feeds the fixture.

## 6. Implementation order (suggested, not binding)

1. Python: fill `http_status`, add `phase` / `error_class` / `host` / `provider_signature` to `Cause`, give `classify_fields` a real NETWORK path; require `provider_signature` before a bare 401/403 is `invalid_key`.
2. Python: the § 2.3 seam, called from rows 12-14 first.
3. Swift: decode, extend `ProviderProblemCondition`, handle the stdout line in `ServeManager.handleLine`.
4. Swift: pure classifier + fixture, then the gathering service.
5. Wire the pill's popover disclosure ("Connection details").

## 7. Open questions for the owner

1. **Is "no pill for incidental refusals" firm for rate-limit and outage?** The audit shows the host drops them today; the mockup keeps them in place. Fine, but then rows 13-14 need an in-place note that something reads, which requires the § 2.3 seam to also feed the SPA.
2. **Which surface owns the in-place note for signal-card refresh (row 14)?** The refresh happens in the background after a run; there is no card being looked at when it fails. Is the note shown on the next visit to Signals, or never?
3. **Should the post-run AutoCode re-apply (row 12) become tracked (`track_status=True`)?** It is a one-line change that makes it reach the chip and the bridge; it also makes a chip appear after every run that failed to tag. Needs a product call.
4. **Partial-failure runs (rows 3-4): should a run that was mostly refused light the pill?** Today it cannot.
5. **Gemini 403 means `invalid_key` for both a leaked key and a restricted one (and a keyless probe).** Is "rejected" the right word for a restricted key?
6. **Azure:** the host is user-supplied and its keyless signature is unmeasured. Is "Claude reachable"-style reach reported for Azure at all, or only `-1003`/`-1004`-class evidence?
7. **The new Apple request.** OK to add `captive.apple.com` to the AI disclosure and the three privacy pages? It would be the first non-provider host the app contacts on its own.
8. **If plain HTTP to Apple needs no ATS exception, do you still want the cleartext probe**, given that cleartext is rare (only after a TLS failure) but unusual in a sandboxed Mac app and a reviewer may ask?
9. **Gateway TCP:** worth shipping as evidence for row 2, or cut? It is measured to work but cannot name the router honestly.
10. **Persistence rule** from the mockup: "a refusal re-expands the pill only when the condition changed or the call was an explicit AI action". `call_site` and `explicit` in § 2.2 exist to support it; confirm that is the rule.

## 8. Needs the owner's hands

All commands and steps are in `experiments/provider-reachability/README.md`; each result file lands in `results/` and `./summarise.py results/*.json` compares states.

- Wi-Fi off; Wi-Fi joined to nothing (real `unsatisfied`, `-1009`, `-1005`).
- Router up with WAN unplugged / phone hotspot with no data (the row 2 state; the only way to see whether the control probe fails fast).
- A captive portal (the real 3xx or body; the HTTP-vs-HTTPS asymmetry; confirm "Success" is exact).
- VPN up, dropped, dropped with kill switch (`uses_other`; what the failed call says).
- DNS sinkhole via `/etc/hosts` (needs `sudo`; **revert** and flush DNS).
- TLS interception via mitmproxy without installing its CA (`-1202` against the control host too?), and a 403 block page (row 7 in the wild). **Turn the system proxy off afterwards.**
- A wrong system clock, future and past (is it `-1201`/`-1204`, and does the control host fail the same way?). **Turn "Set automatically" back on.**
- macOS 15 versus 26 on VM guests: where `.status` lands, whether the title-bar controls collide at minimum width, and whether (a) `NWPathMonitor` + gateway probe prompt for local-network access and (b) plain HTTP to apple.com hosts still needs no ATS exception.
- A real Azure resource host (`--azure-host`), and Ollama stopped.
- A real 402/429/5xx/529 from each provider is not obtainable without spending or breaking an account; the stubs stand in. If the owner has a spent-out test key, one billed call per provider would replace the stub assumptions in § 4 (a decision for the owner; this brief spent nothing).

## 9. What was run for this brief

- `experiments/provider-reachability/run.sh baseline --with-stub` unsandboxed, `--sandboxed`, `--sandboxed-ats`: 4 s timeout; keyless GETs to Apple's captive host, the three providers' public model-list endpoints, a made-up Azure resource host, loopback Ollama; 28 stub routes; the local failure cases. About 7 s each (the hang/black-hole cases hold the 4 s timeout).
- A separate sandboxed run for plain-HTTP behaviour: `http://api.anthropic.com/v1/models`, `http://www.apple.com/…`, `http://developer.apple.com/`, `http://support.apple.com/`.
- No API key, no paid call, no change to Wi-Fi, DNS, proxies, the clock or the hosts file. Side effect: two sandbox containers exist under `~/Library/Containers/app.bristlenose.reachprobe` and `…reachprobe.ats` (delete the folders to clean up).
