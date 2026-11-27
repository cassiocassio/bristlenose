---
status: current
last-trued: 19 Nov 2026
trued-against: HEAD@main (8f685f7be) on 19 Nov 2026
---

# Azure: what every surface says in every state

The acceptance test for the Azure work in [`design-azure-connection.md`](design-azure-connection.md):
every state a researcher can reach, against every surface that reports it, **as the code behaves today**,
then the places where two surfaces give different answers, then what the design proposes. If a row here is
wrong, the design is wrong. Mockups: [`azure-connection-states.html`](mockups/azure-connection-states.html)
(what the proposal looks like), [`azure-decision-consequences.html`](mockups/azure-decision-consequences.html)
(what each open decision changes).

## How it was built, and how far to trust it

- **Read from code at `main` on 14 Nov 2026** by two read-only surveys (Python, Swift), each cell with a file and line.
- **The Python paths were also run** against a local fake Azure server (preflight, doctor, classifier, a run).
  The fake's 400 body is the one Azure really sent (observed 12 Nov); **the 401 body is observed; the 403, 5xx, 3xx and
  portal-URL bodies are plausible shapes, not captured.** Where a verdict depends on Azure's real `error.code`, the
  cell says UNKNOWN.
- The labels in the Mac column are English; the Mac strings are locale keys. The provider is named "Azure OpenAI"
  today in every sentence (D10 renames it "Azure"; the rename is on a branch).

## 1. Who reaches the user first

| Where | Order |
|---|---|
| CLI `run` | provider guidance, then **doctor** (a paid call plus a reachability check; any FAIL exits 1), then **preflight** (a second paid call, cached 24 hours; failure exits 2), then the run. Doctor sees most states first. |
| CLI `analyze` | doctor only; never preflight. |
| Mac Settings | the Swift check (a one-token POST, `max_tokens: 1`), cached on the key alone. Never meets the run's output cap, and keeps no Azure body. |
| Mac run | the app spawns `bristlenose run … --no-serve`, and `run` has **no hosted guard** around the doctor checks or the preflight (`cli.py`), so **both run before a Mac analysis too** (read from code; not yet confirmed on a hosted run). A refusal there reaches the Mac only as stdout text, which the Mac classifies by regex (no structured cause, so no toolbar pill). A failure after that reaches the Mac as a classified cause: the **events log carries only the exception class and HTTP status, never Azure's words** (a privacy contract). The sidecar's `serve` (the assistants) runs neither. |
| Serve-mode assistants (autocode, chat lens, elaboration, codebook builder) | none of the checks; the first Azure failure is a live call. |

## 2. The matrix (today)

Mac pane = Settings ▸ LLM Provider detail (dot, label, sentence). Mac run = a failed analysis (sidebar popover and cover pane).
Doctor, Preflight, Run = the CLI. Proposed = the design's answer (§6, §9 of the design doc). "Raw" = does the surface keep Azure's own words.

| # | State | Mac pane | Mac run | CLI doctor | CLI preflight | CLI run | Proposed |
|---|---|---|---|---|---|---|---|
| 1 | No key | grey "Not set up", no sentence; toggle off | refused before it starts: "Azure OpenAI isn't set up yet." + Set Up Provider | FAIL "No Azure OpenAI API key" + fix | silent (the guide stops first, exit 2) | n/a | unchanged; nothing can be said until a key is pasted |
| 2 | Key, no endpoint | **orange** "Unavailable" + "Add the Azure endpoint URL…"; **toggle on** | "isn't set up yet" | FAIL "No Azure OpenAI endpoint" | silent | `ValueError` text | S5 help line |
| 3 | Key + endpoint, no deployment | **grey** "Not set up", no sentence; **toggle off** | "isn't set up yet" | FAIL "No … deployment name" | silent | `ValueError` text | S5 help line |
| 4 | Online | green "Online" + "Last verified …" | n/a | OK | silent, cached 24 h | normal | "Last verified" only when Online |
| 5 | 401 | red **"Invalid key"** + "rejected this key (401)… generate a new key in your provider dashboard" | "Your Azure OpenAI key was rejected." Popover: Show Log; cover pane: Set Up Provider; pill only if the cause is structured | FAIL "rejected (401 Unauthorized)" + fix | "key was rejected (HTTP 401). Check the key at portal.azure.com" | "rejected your API key. Run `bristlenose configure`" | **S1**: "Azure didn't accept this key (401). Check it and the endpoint in Keys and Endpoint." Label "Not connected" |
| 6 | 403 (firewall, private endpoint, key auth off) | same as 401 with "(403)" | classified as a bad key | "403 Forbidden" + the key-rejected fix, **body dropped** | **raw body** + "if this looks like a credit-balance issue…" | "rejected your API key. Run `bristlenose configure`" | shipped HTTP-status sentence + Details; S4 held (U3) |
| 7 | 404 DeploymentNotFound | red **"Invalid key"** + "**The key is fine**… check the endpoint URL and deployment name" | "doesn't offer the chosen model. Choose another in Settings" (the Model picker is inert for Azure) | "Deployment 'X' not found" + a fix that blames key, endpoint and deployment equally | "deployment name, not a model id" (the best one) | "doesn't offer the model X. Set BRISTLENOSE_AZURE_DEPLOYMENT" | **S2**: "No deployment named “X” on this resource. Key and endpoint are fine; check the name." |
| 8 | 400, output cap too large | the check sends `max_tokens: 1`, so **never meets it**; a low-cap deployment passes green, then the run fails | retried once at the ceiling Azure names (after a sidecar rebuild) | retried once, then OK | retried once, then OK | retried once, logs `azure_output_cap_learned` | invisible |
| 9 | 400, other refusal (parameter, schema, temperature) | orange "returned HTTP 400"; **body discarded** | "rejected the request"; retryable | "HTTP 400: Azure's message" (key scrubbed) | **raw** + "credit-balance" advice | "rejected the request… unsupported model or malformed input" | S3 held (U11); Details carries the record |
| 10 | 429 | orange "rate-limited… try again in a minute" | "rate limit reached"; Retry | OK with a dim "could not validate: HTTP 429" (was silent; fixed 14 Nov) | "rate-limiting this account… lower BRISTLENOSE_LLM_CONCURRENCY" | "Rate-limited by Azure OpenAI" | unchanged |
| 11 | 5xx | orange "returned HTTP 503" | "is unavailable. Try again shortly" | OK with a dim "could not validate: HTTP <code>" (was silent for 500 and 503; fixed 14 Nov) | **raw** + "credit-balance" advice | "had a server error" | unchanged |
| 12 | Offline / timeout | orange; "No network connection. Your key was fine" over a cached verdict, "No network connection, so this key hasn’t been checked yet." with none (fixed 27 Nov); 5 s timeout | "Couldn't reach Azure OpenAI. Check your connection" | key row green tick "could not validate"; network row red | "Network connect failed: check DNS / VPN / offline status" (was "Provider says: Connection error… credit-balance"; fixed 14 Nov) | "Couldn't reach Azure OpenAI" | unchanged |
| 13 | Host not found (DNS) | orange "Couldn't reach Azure OpenAI. Check your connection" (more likely a mistyped resource name) | same as 12; no network pill for Azure | network row red "Can't reach <host>" | as 12 | as 12 | **S6**: "Couldn't find that endpoint. Check the address." |
| 14 | Not https / malformed | red "Invalid key" + "must start with https://"; **`http://` accepted** | n/a | network row FAIL "must start with https://", yet accepts `http://`; key row green | no check | `http://` works, key sent in clear | https only; no userinfo (D14) |
| 15 | Portal long URL or full classic URL | not normalised; expect a 404, so red "Invalid key" + "The key is fine" | `apiRequest` "rejected the request" | "Deployment 'X' not found" (**wrong diagnosis**) | generic 404 + "credit-balance" | same as 9 | finder step 0 keeps the host and lifts the name and version |
| 16 | 3xx redirect | verdict from the final response; UNKNOWN | crashes (`AttributeError`), "Something went wrong" | no longer followed: OK with "could not validate: HTTP 3xx" (fixed 14 Nov) | a reply that is not a chat completion is not a pass and is not cached (fixed 14 Nov) | `AttributeError` | refuse redirects (D14) |
| 17 | Truncated, content filter, empty reply mid-run | n/a | "too dense for Azure OpenAI's output limit. Try a model with a larger output" (inert picker) | OK | n/a | truncation prints "All quote extraction calls failed."; a content filter prints "unsupported model or malformed input" | unchanged; wording out of scope |

Rows 6, 10, 11 and 16 in the Mac-run column show the run classifier's answer. Because a Mac-launched run goes through doctor and preflight first, the researcher may meet the preflight's refusal text (classified by regex) before the classifier speaks.

## 3. Where two surfaces disagree (ranked)

Severity: **A** = a researcher is told something false or sent the wrong way; **B** = inconsistent but not false; **C** = a gap.

1. **A, a 404 says "Invalid key" and "the key is fine" on one line.** Shipped in 0.46.0 (Mac pane, red). D4 fixes the label.
2. **A, 403 gets three diagnoses.** The Mac, doctor and run call it a bad key and send the researcher to `configure`; preflight shows Azure's own body (the only one that can tell a firewall from a key) under "credit-balance" advice.
3. **A, "credit-balance" advice for non-credit failures.** Preflight's generic text is shown for 403, 5xx and 400 (offline and DNS were fixed on 14 Nov and now say network).
4. **Fixed 14 Nov: doctor reported 429 and 5xx as a good key, silently.** It still shows green (it cannot prove the key is bad) but now adds the dim "could not validate: HTTP <code>" detail, as it already did for a 502.
5. **A, 404 is "deployment not found" in doctor for every 404.** A pasted portal URL (state 15) is misreported as a missing deployment. Measured live 19 Nov: a portal URL, a full classic URL, an `http://` endpoint and any wrong path all answer a generic 404 `{"error":{"code":"404","message":"Resource not found"}}`; only a missing deployment answers `DeploymentNotFound`. Doctor runs first on every `run`, so its misreading pre-empts the preflight, which already tells the two apart.
6. **Fixed (`3b117f875`, 27 Nov): the offline sentence claimed "Your key was fine"** when no key was ever validated (Mac). With no cached verdict it now says "No network connection, so this key hasn’t been checked yet." (`LLMValidator.explanation`, the owner's choice in c-offline). Still open: under a cached out-of-credit verdict the shipped "was fine" sentence shows beneath the amber status.
7. **A, the 'choose another model' remedies point at an inert picker.** The run's model-unavailable and truncation sentences tell the researcher to choose a model; Azure takes a deployment name and the Model row does nothing.
8. **Fixed 14 Nov for doctor and preflight: redirects passed silently.** Doctor no longer follows a redirect and preflight no longer takes a non-completion reply for a pass or caches it. A redirect during the run itself still ends as "unknown" (not changed).
9. **B, the Mac check and the run disagree about what Azure accepts.** The check sends `max_tokens: 1`; a deployment with a low cap passes green and fails the run, and a reasoning deployment that rejects `max_tokens` could fail the check while the run is fine (UNKNOWN). The commit that added it says "as Python's doctor does"; the doctor stopped sending that shape on 20 Oct.
10. **Fixed (merged, `21ee1d213`): the Mac validation cache was keyed on the key alone.** It is now keyed on key + endpoint (trimmed) + deployment + API version (`LLMValidator.swift` `identity`), so editing any of them invalidates a cached verdict. One hole remains, §5 below (S1): a run's refusal is written against the config saved when the run *ends*, not the one it ran with.
11. **B, missing endpoint and missing deployment behave oppositely** in the Mac pane (orange and activatable, versus grey and blocked).
12. **B, the popover and the cover pane offer different remedies** for the same failure (Show Log versus Set Up Provider).
13. **B, `http://` is accepted** while every message says https is required.
14. **C, nothing handles the portal URL, the classic URL, a redirect, a hostless endpoint, DNS versus mistyped name, or a 403 that is not a key.**

## 4. What the matrix changes in the design

1. **The raw record has no source for a failed run.** Run events keep the exception class and status only, by design, so the Details popover can show Azure's words for a **Settings check** and for the **CLI**, but not for a failed **analysis**, unless a response hook is added. The run log file does hold Azure's message: the first 200 characters of a JSON message, up to 500 of a non-JSON body, with no key redaction. This is open questions Q14 and Q15 in the decision mockup; the matrix makes it concrete. Until they are answered, "Details" on a run failure shows our category, not Azure's text.
2. **One verdict per state.** Items 1 to 8 above are one problem: five surfaces, three code paths, no shared table. The finder (design §5) and one client builder (D13) are the fix; the matrix is the test that it worked.
3. **Doctor and preflight must agree** on 429, 5xx, offline, DNS and 3xx before the finder lands, or the finder's step 1 inherits the same split.
4. **Launch-sized fixes hidden in here** (each small, none a feature). **Done on 14 Nov:** preflight classifies network failures as network; doctor no longer reports 429 and 5xx silently as a good key; redirects are no longer a pass (and no longer cached). **Still open:** the "Invalid key" label on a 404 (D4, a UX string) and the Mac cache key (built on a branch, not merged). All are reliability, not UX.
5. **Real Azure bodies, recorded 19 Nov:** portal URL, classic URL, wrong path and `http://` all give the generic 404 above (Azure does **not** redirect http to https, so the redirect refusal never fires against Azure itself); a bad key with a bad deployment is **401** (Azure checks the key first, so "invalid key" is right for that pair); the 64000 cap refusal wording is as recorded on 12 Nov. **Still needed:** the 403 bodies (key-based auth off, private endpoint), which need a change on the resource.

## 5. Transition model (19 Nov 2026)

States alone miss the bugs that live between them, so each surface was also modelled as states x events, read from the code at `9be56fe6f` (three read-only passes: Python checks, the run, the Mac). Regions, not a flat product: **configuration** (key, endpoint, deployment, API version: present, absent, malformed), **credential** (absent, present, unreadable), **verdict + cache**, **run**, **learned output ceiling**, **network**. Events: an edit while a check runs; a result arriving after the settings changed; a run started while checking; a key revoked mid-run; 401, 403, 404 (two kinds), 429, 5xx, 3xx, timeout and DNS failure at each stage; the cap refusal and its retry; quit and relaunch with a cached verdict; a sidecar older than the app; provider switched away and back; the CLI and Mac sharing one Keychain item.

**Holds** (each checked against the code): the cap retry happens at most once per call and never applies one deployment's ceiling to another; the preflight cache fingerprint covers key, endpoint, deployment, API version and request parameters; a Mac check whose config changed mid-flight is cancelled and its result dropped; every Mac check has a 5 s timeout; provider text reaching the UI goes through the redactor.

**Odd transitions found** (bug candidates, ranked by harm; *string* = needs new wording, an owner call):

| # | Sequence | What happens | Fix |
|---|---|---|---|
| S1 | Run on endpoint A, fix it to B (B checks green), run A ends with 401 | The refusal is recorded against B: correct config shows "Invalid key", radio disabled, no re-check for 60 s (`ProviderProblemModel.swift` `recordRefusal` passes no config) | capture the run's config at spawn |
| P1 | Any non-DeploymentNotFound 404 (§3 item 5) | doctor says "Deployment not found" and stops the run | read the body |
| P2 | Endpoint or proxy accepts the connection and never answers | preflight waits 600 s x 3 attempts with nothing on screen | explicit timeout, fewer retries |
| R1 | Chat lens: the model's reply fails validation | `ValidationError` is a `ValueError`, so it is answered 400 "bad question" with fragments of the reply in the detail | route parse failures to the 502 path |
| R2 | AutoCode re-apply fails | the raw provider text (`str(exc)`) is stored in the job's `error_message` and served by `/status` | `failure_summary` as its siblings do |
| R3 | Terminal warnings from speaker, quote and theme stages | printed through `_short_reason` without key redaction | redact there |
| S3 | Relaunch with a cached rejection, or offline | "re-checking…" is shown though no check is started | paint it only when a check starts |
| S4 | New key or config entered offline | was: "Your key was fine" for a key never checked | fixed 27 Nov (`3b117f875`): its own sentence when nothing was cached, "…so this key hasn’t been checked yet." |
| S8 | Azure key pasted before the endpoint | "Unavailable" can be activated and auto-adopted | treat a missing endpoint as not set up |
| P4 | Locked or unreadable Keychain (CLI) | reads as "no key" and the Keychain read has no timeout | timeout; naming it is a *string* |
| P5 | Azure 403 (firewall, private endpoint, RBAC) | doctor, run and Mac all call it a bad key | *string* |
| R4 | `llm-calls.jsonl` | a reply that later fails to parse is recorded `ok` | record after parsing |
| — | Codebook builder with an unready provider | bare 500 | fixed 19 Nov: refuses like AutoCode |

**Totality gaps** (a catch-all that hides a cell): `LLMValidator.swift` URLError `default:` hides ATS (http), unsupported URL, TLS interception and proxy failures as one "Network error"; its HTTP `default:` puts every 400 (cap, parameter, API version) and 3xx in one bucket that a cached green can mask; doctor's broad `except` turns a scheme-less endpoint into a green "could not validate"; the Keychain read's broad `except` makes unreadable look like absent.

**Live, 19 Nov (CLI on the dev venv):** a run on a deployment with a 32768 ceiling succeeded; the preflight learned the ceiling first, so the run's own `azure_output_cap_learned` line never appeared, and the preflight's second attempt failed with `SSL: UNEXPECTED_EOF_WHILE_READING` while still printing a tick. Seen once; cause not known.

## 6. Not covered here

The CLI `configure azure` asks for the key only and validates nothing (design §7); the website docs; non-OpenAI Foundry models (100-days item); Microsoft Entra ID sign-in. The chat-lens route is behind a dev flag, so it is listed but not judged.
