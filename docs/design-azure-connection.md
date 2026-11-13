---
status: proposal
updated: 12 Nov 2026
last-trued: 12 Nov 2026
trued-against: HEAD@main on 12 Nov 2026
---

# Connecting an Azure deployment

> **Status: a proposal. Everything here is unbuilt except one fix:** the output-cap retry (C7, O17, R11)
> shipped on 12 Nov 2026 in `9dc0a4578`, with its review follow-up in `f932b75e2`. The rest needs a mockup review and the owner's
> approval before any UI change (the 28 Oct UX gate), and it follows the owner's 12 Nov brief:
> **invent as little as possible, go with the grain of the UX we already have, serve both the
> small team with portal access and the large organisation that hands you a key, and say
> everything in the words Microsoft uses.** The mockup is
> [`docs/mockups/azure-connection-states.html`](mockups/azure-connection-states.html).
>
> Every finding below was gathered on 12 Nov 2026 against a real, throwaway Foundry resource
> and is marked **Observed**, **Read in code** or **Unverified**. No key, subscription id or
> account name appears in this file.

## 1. The problem

The provider is called "Azure OpenAI" in Settings and the CLI today (D10 renames it "Azure"), and it takes three things: an
endpoint, a deployment name and a key. Microsoft has since folded Azure OpenAI into **Foundry**.
The portal's create menu now offers "Foundry (Recommended)" and "Azure OpenAI" side by side,
resources answer on more than one host, and a researcher in a larger organisation never sees
the portal at all: someone in IT sends them values. Whatever they paste has to work, and when
it cannot, the message has to say what to ask for, in words that person will recognise from
the Microsoft side.

## 2. Findings

### 2.1 Observed (12 Nov 2026, real Foundry resource, East US, key authentication on)

| # | Finding |
|---|---|
| O1 | One key is accepted on both `<resource>.openai.azure.com` and `<resource>.services.ai.azure.com`. |
| O2 | `GET /openai/v1/models` with the key is a **free** authentication check: 200 for a good key, 401 for a bad one, on both hosts. It carries no tokens and no deployment name. |
| O3 | A deployment name that does not exist returns **404 `DeploymentNotFound`**, on both hosts and on both the classic and `/openai/v1` routes. It is distinguishable from a bad key (401) and from a wrong host. |
| O4 | For a non-reasoning deployment (`gpt-4.1-mini`, Global Standard), all three of: the classic route (`/openai/deployments/<name>/chat/completions?api-version=…`) with `max_tokens`, the same with `max_completion_tokens`, and `/openai/v1/chat/completions`, return **200 on both hosts**. The classic route works on the `services.ai.azure.com` host too. |
| O5 | The reply names the real model (`model: gpt-4.1-mini-2025-04-14`), so a check can learn what is behind a deployment name at no extra cost. |
| O6 | **A key cannot list deployments.** The classic list is a bare 404. `/openai/v1/models` returns a ~500-entry catalogue of base models, not the resource's deployments. The researcher has to supply the deployment name. |
| O7 | The Foundry portal shows an **Endpoint** and a **Key** (with copy buttons) on each deployment's Details page. The endpoint it shows is on the `services.ai.azure.com` host and ends in `/openai/v1/…`. The Foundry home shows "API key", "Project endpoint" and "Azure OpenAI endpoint". The Azure portal's "Keys and Endpoint" page has Foundry / OpenAI / AI Services tabs over **one key**. A researcher can be given any of these. |
| O8 | A wrong or damaged key returns **401** on every route with the body `{"error":{"code":"401","message":"Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid key for an active subscription and use a correct regional API endpoint for your resource."}}` (response header `apim-request-id`). **Azure's own 401 covers a wrong endpoint as well as a wrong key**, so a 401 sentence must name both. |
| O9 | A fresh subscription had **no quota** for the newest model: the deploy dialog says "Insufficient quota" and offers "Manage quota" and "Request quota". The Quota page reads used/allowed per region and deployment type (`0/0` is none). Quota is a different thing from a budget alert. |
| O10 | Deployment types offered: Global Standard, Data Zone Standard, Standard, Developer, Global Batch, Data Zone Batch, Global Provisioned Throughput (hourly billing). The dialog says Global Standard "might be processed globally, outside of the resource's Azure geography". |
| O11 | The catalogue also lists Anthropic Claude as a **"Messages"** API **hosted on Anthropic infrastructure** (not Azure), plus Kimi, DeepSeek and Mistral as "Chat completion". |
| O12 | A signed-in owner still sees "You don't have permission to create agents… ask your administrator to assign you the Foundry User role". A key does not go through that permission; an Entra-only user would. |
| O13 | **A small real-shape request works** for a non-reasoning deployment: temperature 0.1 plus strict structured output (`json_schema`, `strict: true`) on the classic route with `api-version` 2024-10-21 returned 200 on both hosts, and so did the `/openai/v1` route. **The probe sent `max_tokens` 50, not the run's 64000** (see C7, U10), so this settles the shape, not the output cap. |
| O14 | **Response headers.** A good call carries `x-request-id`, `apim-request-id`, `x-ms-region` (for example "East US"), `x-ms-served-model` and `x-ratelimit-*` (limit and remaining, requests and tokens). A **404 carries only `apim-request-id` and `x-ms-region`**: the request id an administrator can search for is `apim-request-id`, and the region comes with every answer. |
| O15 | **Azure's own words.** Missing deployment: `DeploymentNotFound`: "The API deployment for this resource does not exist. If you created the deployment within the last 5 minutes, please wait a moment and try again." A bad parameter: `decimal_above_max_value`: "Invalid 'temperature': decimal above maximum value. Expected a value <= 2, but got 9 instead." Errors carry a structured **code** and name the parameter, so a classifier can key on the code, not on message text. |
| O16 | A deployment's name does **not** appear in the `/openai/v1/models` list (checked against a real deployment), so name discovery is confirmed impossible with a key. |
| O17 | **The run's output cap is rejected.** `max_tokens` 64000 (the run's default) with temperature 0.1 and strict schema returned **400 `invalid_value`**, on both hosts: "max_tokens is too large: 64000. This model supports at most 32768 completion tokens, whereas you provided 64000." The message **names the ceiling**. The rejected request cost about 30 of the 100,000 tokens-per-minute quota (no 64000 reservation). |

### 2.2 Read in code

| # | Finding |
|---|---|
| C1 | The real call (`llm/client.py` `_analyze_azure`) always sends the **legacy shape** (`max_tokens` + temperature 0.1), pins `api-version` 2024-10-21 (the code says it "predates" GPT-5-class models), and always demands **strict structured output** (`json_schema`, `strict: true`) with no repair step. A deployment of a newer model family, or an older one without strict schemas, can fail a *run*. |
| C2 | The run-time preflight (`preflight/api_key.py` `_validate_azure`) and `doctor` (`_validate_azure_key`) share `request_params`, but **neither sends `response_format`**: they do not send the run's real request, so a strict-schema failure goes uncaught today. `doctor` also has its own urllib URL builder, and the Mac check its own body: **four copies**, not three. Step 2 is a behaviour change, and must say which response model's schema it sends (the run uses several). |
| C3 | `bristlenose configure azure` validates nothing ("needs endpoint and deployment to validate"), stores the key, and prints how to **hand-edit `.env`** for the endpoint and deployment. |
| C4 | The SDK builds the URL by appending to whatever is pasted. Checked offline against openai 3.26: a pasted `…/openai/v1/responses` becomes `…/responses/openai/deployments/<name>/chat/completions?api-version=…`, and a pasted full classic URL becomes a malformed one. **Both pasted shapes fail today.** |
| C5 | The Mac status vocabulary is `online`, `notSetUp`, `invalid`, `unavailable`, `outOfCredit`, `checking`. A 404 on Azure is already routed to `invalid` so the provider cannot be chosen until it is fixed. `azureNotFound` is the existing sentence. |
| C6 | Existing Azure strings (`desktop.llmSettings.validation.*`): `azureEndpointMissing` (status **unavailable**, `LLMValidator.swift:61`), `azureEndpointScheme`, `azureNotFound`, `keyRejected`, `rateLimited`, `httpStatus`, `buildFailed`, `noResponse`, `networkError`, `unreachable`, `offline`, `timedOut`. `keyRejected` says "generate a new key in your provider dashboard", which a researcher who is not allowed to generate keys cannot do. The Swift scheme check accepts `http` as well as `https` (`:71-72`); `doctor` also accepts both schemes (`doctor.py:839` allows `https://` and `http://`; only its message says https). |
| C7 | The real run sends `max_tokens` = `llm_max_tokens` (**64000**, `config.py:140`). `_clamp_max_tokens` (`client.py`) is keyed on the model **name** and knows only `gpt-4o` and `gpt-4o-mini`, so an Azure deployment (an arbitrary name) is **never clamped**; the preflight and `doctor` send the same 64000 through `request_params`. **Confirmed live (O17): a `gpt-4.1-mini` deployment answered 400, so Azure runs, the preflight and `doctor` failed for it.** **Fixed in `9dc0a4578` (follow-up `f932b75e2`):** `azure_output_ceiling` reads the ceiling out of that one wording, the run, `_validate_azure` and `doctor` retry once at it, and `remember_azure_ceiling` keeps it per (endpoint, deployment) for the process. Until the sidecar is rebuilt the Mac app still has the old client, and has no override (the CLI has `BRISTLENOSE_LLM_MAX_TOKENS`). |

### 2.3 Unverified, and how each gets settled

| # | Unverified | How |
|---|---|---|
| U1 | ~~The real-run shape on both routes and hosts.~~ **Settled for a non-reasoning model (O13).** Still open for a reasoning deployment (U2). | — |
| U2 | A **reasoning deployment** (newest family) refusing `max_tokens` and temperature, and the Mac check's 400 reading (N162). | Needs quota for the newest model (requested). |
| U3 | What a resource with **key access turned off** returns (status, code, wording). | Switch local authentication off on the test resource and re-probe. |
| U4 | Gateway hosts (for example an API Management front door): the route, and whether the key header differs. | No test target. Out of scope for v1 beyond "use the host as given". |
| U5 | Whether newer models are offered only on the Responses route. | Watch the catalogue; later and larger. |
| U6 | What the **Model** row in the Azure pane drives (the request model is the deployment name, C1). | Read before any mockup draws it. |
| U7 | Whether a pasted Foundry **project endpoint** (`…/api/projects/<project>`) reduces to the same host cleanly. | Offline test of the parser. |
| U8 | ~~Which response headers an administrator can look up.~~ **Settled (O14).** | — |
| U9 | ~~The message text of the 401.~~ **Settled (O8).** | — |
| U10 | ~~Does Azure reject `max_tokens` 64000 for the `gpt-4.1-mini` deployment?~~ **Yes (O17).** | — |
| U11 | The error **code and wording** for a schema (`response_format`) refusal, which decides S3 (our own schema may be the cause, so S3 is held). | Needs a model that refuses strict schemas. |

## 3. Who is connecting, and what they hold

| | A. Solo or small team, **has the portal** | B. Organisation, **is given** values | C. Organisation, **key access off** |
|---|---|---|---|
| Who made the resource | The researcher, or a colleague with the Owner role | IT or a cloud team, under policy (region, networking) | Same as B |
| What they see | Azure portal "Keys and Endpoint"; Foundry portal "Models ▸ Deployments" and each deployment's Details page | Nothing. A ticket, an email or a secure message | Nothing |
| What they hold | Endpoint, Key 1, a deployment name they chose (often an arbitrary one) | Usually an endpoint, a key and a name; sometimes only two of the three, sometimes a "model name" that is really the deployment name | **No key.** Access is by sign-in (Microsoft Entra ID) and a role |
| What they paste | A clean host from "Keys and Endpoint", or the long Endpoint from the deployment page | Whatever the message says, in whatever shape | Nothing they have fits the pane |
| What goes wrong | Quota wall before the app is involved (O9); a damaged key (O8); a wrong deployment name (O3) | The long URL (C4); the deployment name missing or wrong (O3, O6); a region or data-zone rule they did not choose (O10) | A key-shaped hole: nothing to paste |
| v1 | Works | Works | **Recognise and say so plainly; no sign-in** |

A gateway in front of Azure (U4) is a fourth shape that this table leaves open.

## 4. What the researcher might paste

| They paste into **Endpoint URL** | Example (resource name changed) | What we do (visible in the fields, never silent) |
|---|---|---|
| A clean host | `https://contoso.openai.azure.com/` | Use as is. |
| The portal's long **Endpoint** | `https://contoso.services.ai.azure.com/openai/v1/responses` | Reduce to the host. Note that the Responses route is not the one we call. |
| A full classic URL | `https://contoso.openai.azure.com/openai/deployments/research-mini/chat/completions?api-version=2024-10-21` | Reduce to the host, **lift the deployment name** and the API version into their fields. |
| A project endpoint | `https://contoso.services.ai.azure.com/api/projects/proj-default` | Reduce to the host (U7). |
| Something that is not https | `contoso.openai.azure.com` | The existing `azureEndpointScheme` sentence. |
| A host on another domain | `https://llm.example.org/` | Use as given; a gateway (U4). |

What we can **only** know if the researcher gives it: the deployment name (O6) and the key.

**Migration.** An endpoint already saved in `@AppStorage` (possibly a long portal URL) and one taken from an environment variable (`AZURE_OPENAI_ENDPOINT`, `BRISTLENOSE_AZURE_ENDPOINT`) go through the same step-0 parse on first use, so existing setups are tidied, not broken; a lifted deployment name or API version fills a field only when that field is empty.

## 5. The connection finder (the state engine)

Python is the source of truth (`bristlenose/llm/azure_connect.py`, a new module). The run,
the run's preflight, `doctor`, `configure azure` and the Mac's Settings check all use it, so
there is **one** builder for the route and the request shape (the point of C2). The Mac's check
runs before any sidecar exists, so it mirrors steps 0 to 2 natively, held to the Python by a
shared fixture (`tests/fixtures/azure-connect-contract.json`), as the fresh-run probe is.

| Step | What | Cost | Ends in |
|---|---|---|---|
| **0. Read what was pasted** | Scheme check; reduce to the host; lift a deployment name and API version if the URL carried them. No network. | none | the existing `azureEndpointMissing` or `azureEndpointScheme`, or on to 1 |
| **1. Key and endpoint** | `GET <host>/openai/v1/models` with the key, redirects off, one attempt. | **free** (O2) | **200** → key and endpoint are right; on to 2. **401** → key not accepted (S1). **403** → the shipped `httpStatus` sentence plus the raw record, **never S1**, until U3 shows the code that identifies key-based authentication being off (then S4). **404** → **not a verdict**: on to step 2 (the route was observed on one Foundry resource only, so a 404 here must not break a working setup). Network → `offline` / `timedOut`, or **S6** for a host that cannot be found. 429 → `rateLimited`. 5xx → `httpStatus` |
| **2. Deployment** | Only if a deployment name is present. `POST` the run's real request (the legacy shape, strict structured output, **and the run's real output cap, C7: the finder adopts the retry already in `client.py`, it does not add one**) to the classic route, redirects off, one attempt; read `model` from the reply. If the shape is refused: a 400 whose structured `code`/`param` (O15) names `max_tokens` or temperature → retry **once** with `max_completion_tokens` and no temperature; a route or `api-version` refusal → retry **once** on `/openai/v1`; a 400 saying the output cap is too large → clamp to the ceiling Azure names, if it names one (R11). | one small billed call, as today | 200 → connected. 404 `DeploymentNotFound` → no such deployment (S2, "key and endpoint are fine" only if step 1 returned 200). A 404 with any other code, when step 1 also 404'd → endpoint not found (`azureNotFound`). 400 on the schema → S3 (held, U11). Any other 400 → `httpStatus` |
| **3. Hold the profile** | In memory for the process: host, route, token parameter, whether temperature is sent, the model reported. The run's client reads it. **Open (R1, R2 below): the preflight is cached for 24 hours and the serve-mode assistants never run it, so "nothing is persisted, every run re-probes" is not yet true.** | none | |

Step 1 is why this is cheaper and clearer than today: when step 2 returns 404 we **already know
the key and endpoint are right**, so the message can say so (it cannot today, because one 404
covers the endpoint, the deployment and the API version).

## 6. The states the pane and the CLI end in

The Mac keeps its existing vocabulary (C5); nothing is added to `ProviderStatus`.

| Cause | Status | Sentence | Source |
|---|---|---|---|
| Nothing entered, or no deployment name yet | not set up | none (as today) | existing |
| Endpoint missing | **unavailable** (orange, as shipped) | `azureEndpointMissing` | existing |
| Endpoint not https | invalid | `azureEndpointScheme` | existing |
| Running steps 1–2 | checking | — | existing |
| Connected | online | "Last verified …" (as today) | existing |
| Key or endpoint rejected (**401**; Azure's own message covers both, O8) | invalid | **S1** below: what was refused and what to check | **new** (replaces `keyRejected` for Azure only, C6) |
| **403** (firewall, private endpoint, key access off) | invalid | the shipped `httpStatus` sentence ("Azure OpenAI returned HTTP 403." today; "Azure returned HTTP 403." after the rename, D10) plus the raw record; **never the key-rejected sentence**, because the key may be fine. S4 only once U3 gives the code that identifies key-based authentication being off | open (U3) |
| Endpoint not found | invalid | `azureNotFound` | existing |
| No such deployment (404 `DeploymentNotFound`, after step 1 passed) | invalid | **S2** below: "Key and endpoint are fine" is only said when step 1 really passed | **new** |
| Model cannot do structured outputs | invalid | **S3** below | **new** |
| Key-based authentication off (wording **unverified**, **held until U3**) | invalid | **S4** below | **new** |
| Offline, timed out, cannot connect | unavailable (orange; the provider can still be chosen) | `offline` / `timedOut` / `unreachable` | existing |
| Host cannot be found (DNS) | invalid | **S6** below | **new** |
| Rate limited, 5xx | unavailable | `rateLimited` / `httpStatus` | existing |

**The label.** Today's `.invalid` label is "Invalid key" (`llmSettings.status.invalid`), chosen from the status alone (`LLMProvider.swift:109-114` is the precedent: it shows "Local" instead of "Online" for Ollama). Over "Key and endpoint are fine" it contradicts the sentence, and a screenshot sent to IT then prompts a key regeneration for a key that is fine. Proposal (D4): Azure shows **"Not connected"** (one new key) on **every** Azure failure, the 401 and 403 included (amended 13 Nov, Mac review): Azure's own 401 reads "invalid subscription key or wrong API endpoint", so the key is never certain, and S1 itself says "check it and the endpoint". That covers no such deployment, structured outputs, key-based authentication off, host not found, the shipped `azureNotFound` and `azureEndpointScheme`, and the 401 and 403. One rule, no per-code choice. The spoken VoiceOver label must come from the same function as the drawn one (`ValidationAnnouncement.swift:33` builds it from the status alone today). The label is chosen from the failure's key, so **`ProviderStatus` gains no case**.

### 6.1 Two layers: our reading, and Azure's raw answer (owner, 12 Nov)

A researcher in an organisation they do not administer will send **a screenshot or a pasted
block** back to whoever runs the resource, and that person works in Azure's vocabulary, not ours.
So every Azure failure has two layers, and they are **different in kind**, not short and long
versions of one text:

1. **Our interpretation** (the sentence): what we think happened, in about 20 words and two lines,
   in the researcher's language. It is ours, so it can be wrong; it is the summary a researcher
   reads, and for many the red light is enough.
2. **The raw record** (behind a Details button): what Azure actually said, **verbatim, unedited and in
   English**: the request line, the HTTP status, the response body (Azure's JSON error, code and
   message), and the identifying response headers. It is the standard output of the failure, the
   thing a researcher does not want to deal with and a helpdesk does. We do not rephrase it, and we
   add nothing but a UTC time and our version, labelled as ours.

   Example (real, from the 12 Nov probe, with the resource name changed):
   ```
   POST https://contoso.openai.azure.com/openai/deployments/research-mni/chat/completions?api-version=2024-10-21
   HTTP 404
   apim-request-id: 3d1fae88-0000-4000-8000-000000000000
   x-ms-region: East US
   {"error":{"code":"DeploymentNotFound","message":"The API deployment for this resource does not exist. If you created the deployment within the last 5 minutes, please wait a moment and try again."}}
   Bristlenose: 12 Nov 2026 14:32 UTC · 0.46.0
   ```

   What is in it, and why:

   | Part | Why the administrator wants it |
   |---|---|
   | **Request line** (method, URL with host, path, `api-version`) | Which resource and endpoint, which route, which deployment name as typed. **No request headers, never the key.** |
   | **HTTP status** | The first thing they match. |
   | **Response body, verbatim** (Azure's `code` and `message`) | Azure's own words, which is what their documentation and support use (O15). |
   | **`apim-request-id`, `x-request-id` when present, `x-ms-region`, `date`** (an allowlist of response headers, O14) | The id they can search in their own logs, and where it was served. No other headers are shown. |
   | A network failure, when there was no HTTP answer | The system's own error (for example `NSURLErrorDomain -1003`, host not found). |
   | Azure's `Date` header, and our own line (UTC time, version), labelled `Bristlenose:` | Rules out a recent change; ours is marked as ours. |

   **Rules.**
   - **Raw means captured, not composed.** The record is a faithful transcription of the request that was made (method, URL, `api-version`), the status, the response body exactly as received, and an allowlist of response headers. Anything of ours is labelled: our line reads `Bristlenose: 12 Nov 2026 14:32 UTC · 0.46.0`. The time is Azure's `Date` header when present.
   - **The key never appears.** No request headers are shown. A key-shaped string in the body (32 hex characters, or the 84-character shape) is replaced by a **visible** `[redacted]`; the patterns must not match the GUID-shaped request ids. Key-shaped input in the Endpoint, Deployment or API-version field is refused before any request is made (§12), so it cannot come back here.
   - **Bounded.** A body is capped (about 2 KB) and shown as received even when it is not JSON (an HTML page from a proxy or a captive portal).
   - **Which response.** The finder makes one attempt with redirects off, so the record is that attempt. The SDK path the run uses retries six times and follows redirects by default, so a mid-run failure has a record only if the run's client is built from the finder with a response hook (R10); until then the record belongs to the check, not to a failure deep in a run.
   - **The record is English and unedited by design**, like the log.

What each pattern lets an administrator check (our understanding of Azure, to be confirmed
against U3):

| They read | They check |
|---|---|
| `401`, or `403` | Keys and Endpoint: was Key 1 regenerated? Is key access (local authentication) turned off for the resource? Is a network rule blocking the caller? |
| `404 DeploymentNotFound` | Foundry ▸ Models ▸ Deployments: does that exact name exist, and was it created in the last few minutes? |
| `400`, with a parameter or `response_format` named | The deployment's model family: a newer model refuses `max_tokens` and temperature; an older one cannot return structured outputs. |
| `429` | Quota: the tokens-per-minute and requests-per-minute limits on that deployment, and the Quota page for the region. |
| no answer, timed out, or the host not found | Inbound networking on the resource (firewall, private endpoint) and whether the host name is right. |

**On the Mac the raw record is a reveal, not part of the message** (owner, 12 Nov: "for many the red
light is enough; the human explanation helps first; the raw stuff is there but not in your face").
In order: the red light, the sentence, and on the status line a small **Details** button (owner,
13 Nov: only the extended, CLI-level detail goes behind it). It opens **the app's existing diagnostic
popover** (`ProjectDiagnosticPopover`: 360pt wide, 16pt inset, height following its content up to a
320pt ceiling and then scrolling inside, the header never scrolling) holding the raw record in
monospaced Caption 1, with the **copy button in the popover's header** (`.bordered`, `.controlSize(.small)`,
`doc.on.doc`, tooltip `desktop.pipeline.diagnostic.action.copy`). The button appears **only on Azure
failures**, only when there is a record, and is a plain push button like the shipped "Show Details"
(`RunCoverPane`, `BootView`): it opens something, so it has no state to name. One fixed noun, **"Details"**
(one new string, 21 locales); the popover headline is drawn as "Details" and is the one wording still to choose.

**Why a popover and not a disclosure in the pane (D11, superseded).** The Settings window never
scrolls and nothing limits it to the screen (`SettingsWindow.refitToContent`), so anything that grows
the pane is a height budget against the smallest Mac we support (§13: the M1 Air at default scaling).
An inline box has to be capped, scrolled or both; the popover already solves exactly that (the 320pt
ceiling, "nothing is clamped, the text is the payload; it scrolls", `docs/design-pipeline-popover-sizing.md`),
so the edge case of a long record (a proxy's HTML page can be 2 KB) cannot break the 90% case, which is a
red light and one sentence. The two disclosure options the mockup first drew (A, the shipped `DisclosureGroup`;
B, a Claude Code style trailing chevron) were both rejected by the HIG and accessibility reviews on
13 Nov or made unnecessary by this; neither is drawn now.

**Open:** a failed *run* already shows its cause in the sidebar status-line popover; a failed
Settings *check* is a different event, so the Details button reaches the same popover content from the pane.
Whether the Settings verdict's raw record reaches `ProviderProblemModel` for the toolbar pill is not checked.

**The CLI is a separate decision (D12).** A terminal has no disclosure to collapse into, and what
is on screen is what gets pasted into a ticket. Proposed: the sentence first, then the raw record
as a dim block, by default. The alternative is to print them only with `-v`.

## 7. Mac and CLI behaviour

**Mac, Settings ▸ LLM Provider ▸ Azure** (today "Azure OpenAI", D10). One new control: the Details button. The Endpoint URL field becomes
tolerant (§4) and shows what it kept, in the same fields. The status dot, its label and the
message under it carry the states (§6); the administrator's raw record sits behind the
**Details** button and its popover (§6.1). The help line (S5) shows only while the deployment name is empty. The label becomes **"Azure"** (D10): it is what IT says and where the key lives, and it promises no model. One **new line of help** under the Azure fields (Endpoint URL and Deployment name stack their label above a full-width field, as shipped; API version stays label-left), in
Microsoft's words (§9).

**CLI.**
- `bristlenose configure azure` **asks** for the endpoint and the deployment name (C3 says it
  prints how to hand-edit `.env` today), runs steps 0 to 2, and stores all three: the key where
  keys go, the endpoint and deployment in the user config `.env` that `FileCredentialStore`
  already uses.
- `bristlenose doctor` and the run's preflight print the same steps in the house style
  (`✓`, `⚠`, `✗`). A failure prints the sentence, then the raw record as a dim block
  (D12).
- The CLI's terminal text stays English by design.

## 8. v1 and later

**v1:** the tolerant endpoint; step 1 (free key check); step 2 with the one-retry parameter and
route fallback; plain Azure-specific messages; the same builder in the run, preflight, `doctor`
and `configure azure`; the Mac's check mirrored by the contract fixture; one paragraph of
"what to ask your IT department" in the website docs.

**Later:** a way to sign in with Microsoft Entra ID (the key-off organisation, C scenario);
gateway hosts (U4); the Responses route if newer models need it (U5); Claude and other
non-OpenAI models through Foundry (O11; a different wire format, and hosted outside Azure, which
matters for data residency); choosing or advising a model once we can read it (O5).

## 9. Words: say it the way Microsoft does

Observed in the portals on 12 Nov 2026. Use these; do not coin ours.

| Say | Not |
|---|---|
| **Endpoint**; **Keys and Endpoint** (Azure portal ▸ Resource Management); **Key 1** | "Target URI" (a third-party word), "API base", "URL" on its own |
| **Deployment name**; **Models ▸ Deployments** (Foundry portal) | "model name" for the deployment name: Microsoft keeps them apart and so must we |
| **Azure** (our provider label, D10); **Microsoft Foundry** in help text and portal pointers | "Azure OpenAI" as our label (it reads as OpenAI-only); "Azure Foundry" (not a Microsoft name); "Azure AI Studio", "AI Services" |
| **Deployment type**: Global Standard, Data Zone Standard, Standard | "tier", "plan" |
| **Quota**, **Insufficient quota**, **Request quota** | "limit", "credit" (Azure has no credit pool here) |
| **Microsoft Entra ID** | "Azure AD", "SSO" |

**Length rule (owner, 12 Nov): the sentence is our interpretation, in about 20 words and two lines** in the pane (the shipped key-rejected sentence, rendered for Gemini, is 23 words, and is the benchmark). It is a *different kind* of text from the raw record behind the disclosure, which is Azure's own answer and is never shortened or rephrased (§6.1).

**Proposed new strings** (English, for the owner to approve; each is 21 locales; placeholders in braces as `keyRejected` uses them; word counts are as rendered):

- **S1** · Key (or endpoint) not accepted (Azure only; 401 only) · 15 words: "{{provider}} didn’t accept this key ({{status}}). Check it and the endpoint in Keys and Endpoint."
- **S2** · No such deployment · 15 words: "No deployment named “{{name}}” on this resource. Key and endpoint are fine; check the name."
- **S3** · Model can’t do structured outputs (**held until U11**: our own schema may be the cause) · 16 words: "This deployment’s model can’t do structured outputs, which Bristlenose needs. Use a chat model that can."
- **S4** · Key-based authentication off (**held until U3**) · 13 words: "Key-based authentication is turned off for this resource, so Bristlenose can’t use it."
- **S5** · Help line under the Azure fields (shown only while the deployment name is empty) · 14 words: "Find the endpoint, key and deployment name under Models ▸ Deployments in Microsoft Foundry."
- **S6** · Host cannot be found · 7 words: "Couldn’t find that endpoint. Check the address."
- **L1** · the Azure status label on any failure · "Not connected" (replaces "Invalid key" for Azure; D4).

Each names what is wrong and what to check, in Microsoft's own terms (*structured outputs*, *key-based authentication*, *Models ▸ Deployments*, *Microsoft Foundry*), and stops there: a researcher who was given these values knows to ask whoever gave them (owner, 13 Nov: no "ask whoever…" touches). They are shorter than the ~20-word benchmark, which is a ceiling, not a target. **S2 interpolates a typed name into a markdown-rendered `Text`; the name must be escaped.**

**What to ask your IT department** (draft for the website docs, not for the app; it states only what we have observed):
> Ask for four things: the **endpoint** of the Azure resource (in Microsoft Foundry); the **name of a
> deployment** of a chat model that supports structured outputs; a **key** for the resource (say so if
> your organisation turns key-based authentication off); and enough **quota** for several interviews at
> once. Where your data is processed is set by the deployment type (Global Standard, Data Zone Standard
> or Standard); that is your administrator's setting, and Bristlenose cannot see it.

## 10. Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | The free key-and-endpoint check first (`GET /openai/v1/models`)? | Yes. Observed to split 401 from 404 at no cost. |
| D2 | A tolerant Endpoint field that reduces to the host and lifts the deployment name and API version, shown in the fields? | Yes, always visible and editable, never silent. |
| D3 | The new strings in §9 in Microsoft's words: S1, S2, S5, S6 and the label L1 (S3 and S4 are held, D15)? | Approve wording; then 21 locales. |
| D4 | The Azure status label on any failure (§6, L1): **"Not connected"** instead of "Invalid key" (the 401 and 403 included, and the shipped `azureNotFound` and `azureEndpointScheme`), chosen from the failure's key, so `ProviderStatus` gains no case? One new string, 21 locales. | **Yes.** Mockup frames 6-11 show it. Amended 13 Nov (was: only when the key is not the problem). |
| D5 | `configure azure` asks for the endpoint and deployment and saves them in the user config `.env`? | Yes. |
| D6 | Key-off organisations: recognise and say so, no sign-in in v1? | Yes. |
| D7 | Persist nothing and re-probe in every run's preflight? | **Not yet answerable as written (R1, R2).** The preflight result is cached 24 hours, and serve-mode assistants skip it. Either Azure bypasses the cache and the profile is derived where each client is built, or the profile is persisted and fingerprinted. Decide with D13. |
| D8 | Leave the Model row as it is; check first what it drives (U6)? | Yes. |
| D9 | Show the real model name on success (O5)? | Not in the Mac pane for v1; in `doctor` and the CLI only. |
| D10 | The provider label: **"Azure"** instead of "Azure OpenAI"? | **Decided 13 Nov (owner): yes.** A Foundry deployment can be any model, IT and the key both say Azure, and "Azure OpenAI" reads as OpenAI-only. v1 is proven for OpenAI-model deployments on the chat route; a deployment whose model Bristlenose cannot use fails the check with a reason rather than mid-run. Testing other Foundry models is a 100-days item. **Code rename owed** (not done): `LLMProvider.swift:22`, the 21 locales (one occurrence each), 13 Python files, README, the man page, the website docs and the provider-naming rule in `CLAUDE.md`. |
| D11 | **Superseded 13 Nov (owner).** Was: the pane's collapsed details as **A**, the shipped `DisclosureGroup`, or **B**, a trailing chevron. Now: a **Details** button opening the existing diagnostic popover, copy button in its header (§6.1). | **Yes.** Frames 5b and 5c in the mockup. Open: the popover's headline wording. |
| D12 | The CLI: print the same raw record as a dim block after the failure sentence, by default? (Alternative: only with `-v`.) | By default: a terminal cannot collapse, and the output is what gets pasted into a ticket. |
| D13 | Where the connection result lives (R1, R2): the 24-hour preflight cache and the serve-mode assistants (autocode, chat lens, elaboration, codebook builder), none of which run the preflight. | Build the client from the finder in one place so every caller gets the right route and parameters; make the cache key include them. |
| D14 | Security requirements from the security review (§12): https only; no redirects ever; rebuild the URL from scheme, host and port; reject userinfo; **validate the API-version field (`YYYY-MM-DD` or `-preview`) as well as the Endpoint and Deployment fields**, and refuse key-shaped input in all three; confirm before a key goes to a host outside Microsoft's Azure domains. | Yes, as requirements, not options. |
| D15 | The held strings: S3 (until U11) and S4 (until U3) do not ship until the real error bodies have been read. | Yes. |

## 11. Test plan

- **Fake server**, one per shape and failure in §5 and §6, with a mutation pass (each fix
  mutated alone to prove the test can fail). **Its response bodies are copied from real Azure answers (O15), never guessed**; the parameter and route retries (not the output-cap retry, already shipped) wait for the reasoning-model probe (U2) before they ship.
- **Contract fixture** read by pytest and the Swift suite: pasted URL → host, deployment,
  version, route hint; status and body → outcome.
- **The real resource:** `azure-probe.sh` (a private scratch script, not in the repo; U1 and U8 are settled, O13 and O14); the newest model for U2 once its quota is
  approved; the key-off probe for U3.
- **One cheap real pipeline run** per deployment family (an older-style and a newer-style one).
- **Human check on the Mac:** the pane states in the mockup (the shipped Settings window at 660pt; the failures with Details closed, and the popover open, including the 2 KB worst case), in light and dark.

## Related

[`design-cli-provider-selection.md`](design-cli-provider-selection.md),
[`design-cli-just-works.md`](design-cli-just-works.md) (the API-key preflight),
[`design-pluggable-llm-routing.md`](design-pluggable-llm-routing.md),
[`design-shared-formats.md`](design-shared-formats.md) (the contract-fixture pattern),
`bristlenose/llm/CLAUDE.md` ("Claude, ChatGPT and Azure requests").

## 12. Review (12 Nov 2026): what six reviewers found

Six read-only reviews of this doc and the mockup (Mac native UX, UX critique, i18n, user-facing
text, design and state machine, security). Factual errors in the doc are fixed above; the rest is
here. Raw outputs stay out of the repo.

**Requirements added (security; D14).**
- **Redirects.** The Python client follows redirects (the openai SDK default, `follow_redirects=True`; not our code) and httpx drops only
  `Authorization` on a cross-host hop, so the `api-key` header (and a POST body that is transcript text
  in a run) can follow a redirect. Pass a client with redirects off; treat any 3xx as a failure naming
  the `Location` host. The Mac's `URLSession` has no redirect delegate; add one that refuses.
- **https only**, enforced in Swift, Python and the contract fixture (the Mac accepts `http` today).
- **Rebuild the URL from scheme, host and port only**; reject userinfo (`https://contoso.openai.azure.com@evil/`);
  accept `api-version` only as `YYYY-MM-DD` or `YYYY-MM-DD-preview`; add parser-disagreement cases
  (`https://evil\@contoso.openai.azure.com`) to the contract fixture.
- **A host outside the Azure domains** (`*.azure.com`, `*.azure-api.net`, `*.azure.us`, `*.azure.cn`)
  needs an explicit confirmation before the key is sent.
- **Key-shaped input in the wrong field.** The portal shows Endpoint and Key side by side; a key pasted as the deployment name would come back in the sentence, the raw record, the clipboard and the log. Detect key-shaped input in the Endpoint, Deployment and API-version fields and refuse it; add the Azure key shapes (32 hex; 84-character) to the log redactor and `check-logging-hygiene.sh`. **The raw record is shown verbatim (§6.1)**: the only change is a visible `[redacted]` on a key-shaped string in the body, with patterns that do not match GUID request ids; never log the raw pasted text.
- **Environment shadowing.** `AZURE_OPENAI_ENDPOINT` and `.env` files found up the tree beat the user
  config, so a check can pass against one endpoint while a later run sends the key to another. Give
  the endpoint and deployment the key's read-back and shadowing check, and name the endpoint's source
  in the run header.
- **Residency wording.** Data Zone means processing anywhere in the EU or US zone, not "in a
  region"; abuse monitoring can retain prompts; a key cannot read the deployment type. The IT draft
  now says only that this is the administrator's setting. `SECURITY.md`'s "the provider you selected"
  is no longer guaranteed behind a gateway.
- The raw record names the organisation (host, deployment); the copy action is "for your
  administrator", not for public posting; mask the key field while details are open; Mac logs use
  `privacy: .private`.

**Design gaps to close before building (design review).**
- **R1.** The preflight result is **cached 24 hours** (`_is_recently_validated` in `api_key.py`), keyed on the legacy
  request fingerprint: a deployment that passed only on a retry is cached, and the next run skips the
  check, has no profile, and fails on the legacy shape.
- **R2.** **Serve mode never runs the preflight**: autocode, chat lens, elaboration and the codebook
  builder each build an `LLMClient` directly. The `/openai/v1` route also needs a plain `AsyncOpenAI`
  with a `base_url`, while the cached client is an `AsyncAzureOpenAI`.
- **R3.** Retry triggers must key on Azure's structured `code` and `param` (O15), with new
  sub-kinds in `failure_classifier.py`, not on message text, or a content-filter 400 reads as "this
  model can't".
- **R4.** Specify the retries: can the parameter and the route retry both fire (three billed calls)?
  Which failure is reported if the retry also fails? The SDK's six retries on 429/5xx could mean
  minutes in a preflight, and the Mac's 5-second session can time out on a first strict-schema call
  (which reads as `unavailable` and is masked by a cached green).
- **R5.** The gateway fall-through must be defined by an explicit host allowlist: `*.azure-api.net` is
  an Azure domain that may not serve `/openai/v1/models`; its 404 must not read as "endpoint not found".
- **R6.** Split **403** out of 401: a firewall, a private endpoint or key access off must not get
  the key-rejected sentence (S1 uses `{{status}}`, not a hard-coded 401).
- **R7.** The fixture must pin a **sequence** (1, 2, retry) and the exact request bodies, generated from
  Python, and the Swift session must be injectable (`urlSession` is `private static let` today). A
  structural test must show the doctor and Mac builders are derived from it, or the parity fixture
  leaves a fourth copy standing.
- **R8.** "Only if a deployment name is present" plus "another domain falls through to 2" can reach `online` without step 2; Swift returns not-set-up before any network call when there is no deployment name, so step 1 never runs there. State the outcome per case.
- **R9.** The Mac's validation cache is keyed on the provider and the key alone (`LLMValidator.cachedEntry(provider:key:)`), so a mistyped host after one good check can show a masked green. Include the endpoint, deployment and API version in the key. (D13 covers the Python cache; this is the Mac's.)
- **R10.** Capture: the SDK the run uses retries six times and follows redirects by default (that is the openai SDK's default, not our code), and `doctor` uses urllib, which also follows them. The raw record exists for the finder's own one-attempt requests; for a failure deep in a run, the run's client must be built from the finder with a response hook, or the record belongs to the check only.
- **R11. Done** (`9dc0a4578`, `f932b75e2`): the ceiling is parsed from Azure's own message (`invalid_value`, "supports at most N completion tokens") and the request retried once at N, in the run, the preflight and `doctor`; the learned value is process-local (a separate `doctor` process does not reach a run) and never expires (the limits are in `bristlenose/llm/gotchas.md`). The Mac check sends `max_tokens: 1` (`LLMValidator.swift`) and never meets the cap, so it is not part of this; it would be only if §5 step 2 makes it send the real cap.

**UX and text (Mac and UX reviews; open as marked).**
- The **status label** (D4) and where the raw record lives (D11, now a popover) are decisions above.
- Mockup fidelity (fixed in this version): only a not-set-up row dims (an invalid row is full opacity
  with a true red dot); the "Use this provider" toggle is disabled for an invalid provider; the
  endpoint is a single-line field; caption-sized text; the copy button sits beside the text.
- **Persona C** (no key at all) gets no message on the Mac: the pane stays at grey "Not set up". A probe without a key cannot tell "key access off" from "no key" (both answer 401), so nothing can be said until a key is pasted; the website paragraph is their path.
- The **Model row** says `gpt-4o` whatever is deployed; the connected frame and an administrator's
  screenshot both show it (D8; read what it drives first, U6).
- **`configure azure` saves nothing when the deployment check fails**, throwing away an endpoint and
  key that passed; save what passed and re-ask only for the deployment name.
- A deployment name or `api-version` lifted from a pasted URL fills its field **only when it is
  empty**, never over what the researcher typed.
- "Last verified in 0 seconds" under a red dot reads as success: **hide the line unless the status is Online** (no new string; drawn so in the mockup since 13 Nov).
- The IT paragraph no longer states a token figure, "current" models, or residency advice (S1-S6,
  §9). Naming: first mention "Microsoft Foundry"; the CLI prompts say "endpoint" while the pane says
  "Endpoint URL".
- **i18n.** Add glossary rows for the Microsoft terms (Azure, Foundry, Microsoft Entra ID, Endpoint,
  Deployment, Keys and Endpoint, Models ▸ Deployments) and align the shipped `azureNotFound`'s word
  for "deployment" in every locale; measure Microsoft's own per-locale labels (including `zh-Hant-HK`);
  tag the English details with `languageIdentifier = "en"`
  for VoiceOver; the `boot.*` keys are shared with the boot screen, so a reword there changes Settings.
- **Surfaces if this ships:** README (the `configure azure` section, and its claim that it
  "validates the key"), the man page (lines ~162, 259, 640), `cli.py` help text and the hint at ~1277,
  the website's `docs-src/cli.md`, and `desktop.json` in 21 locales.

## 13. Second review (13 Nov 2026): Mac-native (HIG) and accessibility

Two read-only reviews of the mockup and §6, §9, §10, against the shipped pane (the owner's screenshot
of the rebuilt app shows Endpoint URL and Deployment name already stacked, API version label-left).
Applied to the mockup and this doc on 13 Nov unless marked open.

**Applied.**
- **D11 = A, one fixed label "Details"** (both reviews). **Superseded the same day by the popover (owner); the inline box, its cap and its stand-in are dropped.**
- **D4 amended:** "Not connected" on every Azure failure, 401 and 403 included. The 403 row would
  otherwise have kept "Invalid key" beside "the key may be fine".
- **"Last verified" only when Online;** its grey is the secondary tone (the tertiary tone fails contrast, 2.34:1 light).
- **Raw record** at the caption size (10pt monospaced, a system text style, never `.system(size:)`),
  one selectable `Text`, English-tagged for VoiceOver, **in the popover** (360pt wide, 320pt ceiling, scrolls
  inside): the pane never holds it, so it cannot move the window. (Superseded the first answer, full height with a window refit.)
- **Stacked Endpoint and Deployment rows** drawn in every frame, as shipped.
- **Spoken label = drawn label** (requirement, §6).

**Open: for the build, not the mockup.**
- The copy button posts a VoiceOver announcement; the announcement for S2 reads the plain sentence, never the markdown-escaped one.
- (Superseded: no inline disclosure to animate; the popover is the system's.)
- Move **Azure Settings directly under API Key** (Tab order otherwise runs Key, Model, Endpoint); the doc's "three fields" is four in the pane (Endpoint URL, Key, Deployment name, API version).
- Trim whitespace and newlines from a pasted key on commit; the paste-to-host rewrite registers with the window's `undoManager` so Cmd-Z returns the pasted URL; a URL pasted into the key field gets a sentence (mirror of D14).
- Cancel an in-flight check when a newer commit lands (`validationTasks` exists).
- Group the dot, label and sentence into one VoiceOver element; hide the dot.
- A Help link to the website's IT paragraph is optional (`HelpLink`, macOS 14+).
- **Screen floor (owner, 13 Nov): the M1 MacBook Air at default scaling**, 1440×900 points, roughly 800-820pt visible below the menu bar and above the Dock. It is the earliest Apple silicon, which is the app's own floor (arm64 only). Large-text scaling on a small screen is not a target. The Settings window grows to fit and never scrolls, and `refitToContent()` has no screen clamp (read 13 Nov), so the pane's height is a budget: the owner's screenshot measures the Azure window at 792pt, a failure adds an estimated 50pt (the sentence; the Details button sits on the status line and adds none), and the open record is a popover, which adds none. Measure the collapsed failures with Diagnostics ▸ Azure Settings (below) rather than trust the estimates.
- (Moot with the popover: the HIG review would have capped an inline box at 140pt, the accessibility review would not.)
- The HIG corpus has no disclosure-control page; the disclosure verdicts are Mac convention and inference, not HIG quotes.
- **Diagnostics ▸ Azure Settings** (built 13 Nov, uncommitted; `AzureSettingsFixture.swift`): four fixtures (key not accepted, no such deployment, host not found, the longest sentence) that open the real pane in a failure state with fake data, so the window height can be read on a real screen. It overlays at read time and never writes the real verdict. Known limits: it draws the shipped label "Invalid key", hides "Last verified" as the design does, and has no Details button (not built), so its height is the sentence's alone; the window refits exactly while a fixture is active so heights do not depend on the order picked; with a stored Azure key, choosing a fixture still triggers the normal check, and a VoiceOver announcement can read the real verdict. The sentences are draft copy that compiles into every build but is reachable only where `exposesDebugTools` is true.
- **Provider name (owner, 13 Nov): "Azure"** (D10), not "Azure OpenAI". Verified for OpenAI-model deployments only; the other Foundry models are untested (100-days item).
