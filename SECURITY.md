# Security

## Where Bristlenose runs, and what it sends

Bristlenose runs on your laptop. There is no Bristlenose server, no account, and no telemetry — nothing is sent to us, ever.

It is **not** a tool where nothing leaves your machine, and you should not choose it believing that. The analysis is an outbound call to a cloud LLM provider, and that is the normal, recommended path. Every case where data does leave is listed below under [Data leaves your machine only when](#data-leaves-your-machine-only-when) — five of them, in full. Ollama closes the largest one, at the cost of speed and analysis quality.

**Transcription** happens locally using Whisper (faster-whisper or MLX Whisper). Audio never leaves your machine.

**LLM analysis** requires API calls to your configured provider (Claude, ChatGPT, Azure OpenAI, or Gemini). Transcript text is sent to those APIs and is subject to each provider's data-handling policy. If you need fully offline analysis, use Ollama with a local model — no data leaves your machine.

## Credential storage

API keys are stored in your operating system's secure credential store:

- **macOS (CLI)** — Keychain (via `security` CLI). The library that ships through PyPI / Homebrew / Snap is signed by the package channel.
- **macOS (desktop app, Apr 2026 onwards)** — Keychain via Security.framework (`SecItemAdd`/`SecItemCopyMatching`). The SwiftUI host reads your key from Keychain at the moment it starts the local analysis process, passes it to that process as an environment variable, and the process holds it in memory for the lifetime of the local serve process. Keys are read from Keychain only at launch and never persisted to disk.
- **Linux** — Secret Service (GNOME Keyring / KDE Wallet, via `secret-tool`)
- **Fallback** — environment variables or `.env` file

Keys are never written to disk in plaintext by Bristlenose. The `.env` fallback is read-only — Bristlenose reads it if present but does not create or modify it.

## Code signing and runtime hardening (macOS desktop app)

The desktop app is distributed through the Mac App Store. Every Mach-O in the bundle — the SwiftUI host, the bundled Python runtime, FFmpeg, every `.dylib` and Python C-extension `.so` — is signed under our Apple Distribution identity (Team ID `Z56GZVA2QB`) with Hardened Runtime enabled. App Store Connect validates the upload server-side before distribution; users only ever receive bundles that have passed Apple's automated security review.

The Hardened Runtime entitlement table requests **one** entitlement: `com.apple.security.cs.disable-library-validation`. This is empirically required, not defensive. Apple's bundled `Python.framework` carries an internal code signature that AMFI's library-validation check reads at `dlopen` time, distinct from the per-binary signatures we apply during build. The framework's nested signature does not match our Team ID, so dyld would refuse to load it without the entitlement. Disabling library validation is the standard pattern for embedded-Python apps on macOS — Apple Developer Support documents it explicitly. The mitigation: every binary in the bundle is signed by us under one identity, the rest of Hardened Runtime remains enabled (no `allow-jit`, no `allow-unsigned-executable-memory`, no `allow-dyld-environment-variables`), and the App Sandbox (when enabled) constrains the process. The specific framework path that triggers the requirement is documented in `desktop/bristlenose-sidecar.entitlements`.

The build pipeline lives in `desktop/scripts/build-all.sh`. Pre-archive gates scan every Mach-O for the `BRISTLENOSE_DEV_*` developer-only environment variable references and reject any binary carrying the `get-task-allow` debugger entitlement. SHA256-pinned downloads (FFmpeg/ffprobe from evermeet.cx) and a sign-manifest emitted on every build give per-binary supply-chain provenance.

Privacy manifests cover the entire bundle: `Contents/Resources/PrivacyInfo.xcprivacy` for the SwiftUI host and FFmpeg, and `Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy` for the embedded Python runtime and its native extensions. Both declare `NSPrivacyTracking = false`, an empty `NSPrivacyCollectedDataTypes`, and the specific required-reason API categories triggered by bundled code. The build pipeline rejects any release archive that's missing either manifest or fails `plutil -lint`.

A complete inventory of every third-party binary and Python wheel that ships in the desktop app — origin URL, version, SHA256 (where applicable), licence — is maintained at [`THIRD-PARTY-BINARIES.md`](THIRD-PARTY-BINARIES.md). The Python-wheel section is auto-regenerated from the venv install via `scripts/generate-third-party-binaries.py`. CVE monitoring runs through GitHub Dependabot for Python dependencies + a quarterly manual review for native binaries; the cadence is documented in the same file.

## Data leaves your machine only when:

1. **You use a cloud LLM provider.** Transcript text is sent to the provider you selected in Settings (Claude, ChatGPT, Azure OpenAI, or Gemini), using your own API key, at the moment you trigger an analysis. Using Ollama with a local model eliminates even this.
2. **You open the LLM settings tab.** Bristlenose pings each configured cloud provider with a minimal auth-check request to confirm your key still works. No transcript data is sent — just an empty or minimal request that the provider answers with a 200 or 401. Capped at once per minute per provider (verdict cache). Ollama is never contacted off-machine — the URL is hardwired to localhost in the desktop GUI.
3. **Whisper downloads its transcription model**, once per model, on first transcription. Model files are downloaded from huggingface.co to `~/Library/Application Support/Bristlenose/models/`. This is data, not code — the download is consumed by the transcription library that already ships signed inside the app. Integrity relies on Hugging Face Hub's own LFS hash verification against `huggingface.co`'s manifest endpoint; Bristlenose does not pin model SHAs. If you set `HF_ENDPOINT` to a third-party mirror, that mirror's integrity story is the one that applies.
4. **You start a CLI pipeline run.** Before transcription begins, Bristlenose makes a one-token request to your configured cloud provider to verify the key works and has billing balance, so the run aborts up-front instead of failing six minutes in. The request body is the literal character `.` — no transcript content. Capped at one call per 24h per provider (validation cache). Skipped when the provider is Ollama, or when `BRISTLENOSE_SKIP_PREFLIGHT=1` is set.
5. **(Desktop app only) iCloud Keychain syncs your stored credentials.** If you have iCloud Keychain enabled, macOS replicates Bristlenose's stored credentials to your other Macs as synchronizable Keychain items. This is iCloud **Keychain**, not iCloud Drive: it is end-to-end encrypted, so the contents are not readable by Apple. No transcript or research data is involved. Two kinds of credential are covered, and the second is worth reading separately if you work with client organisations.

    **Your provider API key** — your own credential, under your own account, revocable at the provider.

    **Your cloud meeting sign-ins**, if you use `File ▸ Import` to bring recordings in from Microsoft Teams or Google Meet. These are OAuth grants, one Keychain item per signed-in account, and they are scoped to reading your own files and calendar (`Files.Read` and `Calendars.Read` on Microsoft; the equivalent read-only scopes on Google) — not to acting as you. **Where this differs from an API key: the account may belong to a client's organisation rather than to you**, so a client's IT policy may have a view on that grant being replicated to your other Macs, even end-to-end encrypted. It is the same grant you would hold by signing in to Teams or Drive on those Macs directly, but it is worth knowing it is there rather than discovering it during a supplier assessment.

    To prevent replication: disable iCloud Keychain, or use the CLI (file-based, non-synchronizing) — cloud import is a macOS-app feature and does not exist on the CLI. To revoke a meeting sign-in outright rather than merely removing Bristlenose's copy of it: **Settings ▸ Accounts ▸ Disconnect** removes the stored grant from this Mac, and revocation at the provider is Microsoft Entra ▸ Enterprise Applications, or your Google Account ▸ Security ▸ Third-party apps. Bristlenose's own disconnect confirmation says the same thing, because removing our copy is not revocation.
6. **You send a board to Miro.** If you use Export → Send to Miro, the quotes in your project are uploaded to your own Miro account, authorised by a Miro access token you provide. The board carries quote text, speaker codes (p1, p2), sentiment, and — only if you opt in — links to clips you host; **participant display names are never sent**, and hidden quotes are excluded. This is the only export that crosses to a third-party service, and only when you trigger it.

7. **You turn on Agent Access for a project.** `bristlenose serve` can expose a read-only MCP endpoint (`/mcp/`, loopback only, bearer-token-gated). On the CLI it exists only when the separate `bristlenose[mcp]` extra is installed; the macOS app ships it, inert until you act. Exposure is an explicit, per-project act: **Turn On Agent Access** (right-click a project, or the list in Settings ▸ MCP Agents). While an exposed project is open, the app writes a small runtime handshake file (`mcp-handshake.json`, `0600`, inside Bristlenose's own container) carrying the serve's port and an **MCP-scoped** credential; the Claude Desktop extension — and any client running the same proxy — reads it at connect time, so no token is pasted into another vendor's config, and none of it survives the app closing. A project with access off has no handshake and cannot be reached, no matter what is open. When a connected agent (Claude Desktop via the extension; Claude Code, Codex, or any MCP client via the Settings ▸ MCP Agents tabs) asks questions, the tools return quote text (**verbatim**), speaker codes, section/theme labels, signals, and codebook definitions to that agent — which sends them to its own model vendor under that vendor's terms. Whether participant names accompany the speaker codes is the **Anonymise** switch in Settings ▸ MCP Agents — one global switch for everything agents read, off by default (the same word and default as the export surfaces; the command line does not yet expose it). Quotes always cite speaker codes; names appear only in the overview's speaker map. No tool accepts a filesystem path, and the connection is read-only in data and in cost (no writes, no LLM calls from Bristlenose's side). The scoped credential opens the four read-only `/mcp` tools and nothing else — it cannot reach `/api/*` (participant names, curation writes). **To revoke: Turn Off Agent Access** — the handshake is deleted on the spot and the project is unreachable again (a raw URL+token copied from the Generic MCP tab dies with the serve's port; the durable Keychain token can additionally be removed by deleting the "Bristlenose MCP Token" Keychain item). The extension's proxy runs under the agent client's own Node runtime, which is outside Bristlenose's signing boundary. Corollary: what the agent reads becomes part of that agent's conversation history — deleting the project later does not delete the agent's history. Bristlenose's own record of what it served — and the three things it deliberately does not record, including which agent asked — is under **Agent access record** below.

Bristlenose itself has no sub-processors for its core operation — no cloud database, no analytics service, no error-tracking vendor, no auth provider, and no telemetry endpoint. Two exceptions, both opt-in: using **Export → Send to Miro** makes **Miro Inc. a sub-processor** for the quote content you choose to upload, held under your own Miro account and access token and governed by Miro's terms rather than Bristlenose's; and connecting an **MCP agent** (item 7) makes that agent's model vendor a recipient of the quote content the agent reads, governed by the agent vendor's terms.

### What Bristlenose writes to your machine

Per-user state lives outside your project directories and persists across runs:

- **API keys** — macOS Keychain (`security`) or Linux Secret Service (`secret-tool`). Service names listed in `bristlenose/llm/CLAUDE.md`.
- **Whisper model cache** — `~/.cache/huggingface/hub/` (CLI) or `~/Library/Application Support/Bristlenose/models/` (desktop). Several GB depending on chosen model.
- **Validation state** — `~/Library/Application Support/Bristlenose/state.json` on macOS, `$XDG_DATA_HOME/Bristlenose/state.json` (default `~/.local/share/Bristlenose/state.json`) on Linux. Contains last-validated timestamps per provider — no keys, no transcript data. Mode `0o600`.

Project artefacts (transcripts, reports, intermediates) live exclusively under your input folder's `bristlenose-output/` and never leave it.

**One exception, and it is short-lived.** `bristlenose run --clean` no longer deletes the previous report before starting — a run that crashed used to leave you with neither the old report nor a new one. It now *moves* it to a hidden sibling, `.bristlenose-output-previous/`, and deletes that only once the run has produced a replacement. If the run fails, the report is put back and the failed attempt is kept at `.bristlenose-output-failed/` so a retry can resume from it. Both are removed by the next successful run.

While either exists it holds a full copy of the output directory, **including `pii_summary.txt` and `llm-calls.jsonl`** — so during that window `rm -rf bristlenose-output` alone does not remove every byte. To be certain, and this is the form to use in a deletion procedure:

```sh
rm -rf bristlenose-output .bristlenose-output-previous .bristlenose-output-failed
```

`bristlenose status` reports either directory when it finds one. They are dot-prefixed so Bristlenose can never re-ingest a stashed report as interview material — which also means Finder will not show them to you.

#### Event log (`pipeline-events.jsonl`)

`<output_dir>/.bristlenose/pipeline-events.jsonl` is an append-only schema-versioned log of run lifecycle events (started / completed / cancelled / failed). The desktop app reads its tail to render the diagnostic pill and popover.

**Privacy contract:** `cause.message` strings are bristlenose-constructed from structured fields only — exception class name, stage slug, provider slug, and HTTP status. They never carry `str(exc)`, raw provider response bodies, LLM output text, transcript substrings, or participant-derived tokens. This matters because provider error bodies (Anthropic on rate-limit / content-policy; OpenAI BadRequest; Azure content filters) sometimes echo prompt fragments — without the contract, an abandoned run could persist participant names or transcript text into the event log. Implementation: `_build_cause()` in [`bristlenose/run_lifecycle.py`](bristlenose/run_lifecycle.py); contract test in [`tests/test_run_lifecycle.py`](tests/test_run_lifecycle.py) (`test_build_cause_redacts_pii_from_exception_body`).

Each message is capped at 4 KB; each stage's `failed` list is capped at 10 entries (with a synthetic "+ N more" overflow placeholder). These caps protect the desktop's 64 KB log-tail read window from a 50-session failure producing a 200 KB terminus line.

**This file is a re-identification key** when combined with the transcript files in the same project (session ordinals correlate to participant codes). Never include in any export, support bundle, or shareable archive. Mode `0o600` + `O_NOFOLLOW` enforced. To purge: `rm <project>/.bristlenose/pipeline-events.jsonl` (deleting the project folder removes it automatically). The file is local-only and never transmitted.

#### Agent access record (`bristlenose.log`)

When a project has Agent Access on (item 7 above), every MCP tool call an agent makes is recorded in that project's log at `<output_dir>/.bristlenose/bristlenose.log` — one timestamped line per call, at the default INFO level, rotating at 5 MB with two backups:

```
2026-07-30 17:14:33 | INFO | bristlenose.server.mcp_server | mcp_tool | tool=search_quotes | project=1 | elapsed_ms=65 | result_bytes=7975
```

Refusals (a call arriving for a project whose window has been closed), malformed inputs, and tool failures are logged alongside. This is Bristlenose's durable answer to *what was an agent served, and when*.

**Three things it deliberately does not record, and one of them is not a gap.**

- **Which agent.** The MCP protocol's client identification is self-asserted and unauthenticated — any client can claim any name — so recording it would put an unverifiable identity claim into a security record. Bristlenose knows the protocol and never the client: it can offer an endpoint, it cannot observe who connected. **If you need to know which assistant read a study, that record exists in the assistant's own conversation history, under your account** — not here.
- **What was returned.** `result_bytes` is a payload size. Quote text, participant codes and names are never written to the log.
- **Whether you or the assistant initiated the call.** That distinction lives entirely inside the assistant.

**No separate MCP audit file is written, by decision rather than omission.** A second per-project artefact listing which studies were read and when would duplicate the record above, and would itself become a re-identification key subject to the same never-export discipline as `pii_summary.txt` and `llm-calls.jsonl` — additional sensitive material to protect, answering nothing the log does not already answer.

**The grant itself is durable and is the fact that matters most.** Which projects you have opened to agents is stored state, survives a restart, and is listed in Settings ▸ MCP Agents. What is deliberately *not* stored is the "Last asked" time shown in that list: it is held in memory while a project is open and is gone when it closes, and the pane says so.

**Data-controller note.** The log lives in the same hidden `.bristlenose/` directory as the other re-identification keys and is excluded from every export and support bundle. It is readable by you, on your machine; there is no export of it and no way to send it anywhere from inside Bristlenose. If a data-protection assessment requires an access record for agent reads, this file is it — and the "which agent" column it cannot supply is a limit of the protocol, not a setting.


## Prompt injection via transcripts

Bristlenose feeds participant speech into a third-party LLM (Claude, ChatGPT, Azure OpenAI, Gemini, or local Ollama) for quote extraction, theme clustering, and elaboration. A participant who knows their words will be analysed by an LLM — or a third party who hands the researcher a doctored `.docx` / `.srt` transcript — could craft text designed to override the system prompt and produce off-topic, misleading, or embarrassing content in the rendered report. This is a known property of any system that places untrusted text into LLM context.

**Mitigation shipped (alpha):** every prompt template that interpolates transcript text or quote data wraps the untrusted content in a per-call random-nonce sentinel envelope (`<untrusted_transcript_a8f3>…</untrusted_transcript_a8f3>`), with a system-prompt directive to treat content inside the envelope as data rather than instructions. Closing-tag-shaped substrings inside the content are escaped as defence-in-depth. Implementation: [`bristlenose/llm/boundary.py`](bristlenose/llm/boundary.py); enforcement test: [`tests/test_prompt_boundary.py`](tests/test_prompt_boundary.py).

**Residual risk (alpha — explicitly accepted):** sentinel-tagging reduces but does not eliminate the surface. The highest-impact failure mode — a fabricated quote attributed to a real participant — is bounded by structured output schemas but not eliminated. Bristlenose does not currently apply allowlist validation to free-form theme or cluster labels in the rendered report; an attack that survives the sentinel could produce off-topic headings that the researcher must scrub manually before sharing.

**Local LLM (Ollama) caveat:** users selecting `--llm local` get materially weaker protection. Local models adhere less consistently to role separation, and there is no provider-side safety filter. Picking Local in the picker is an informed trade-off.

**What to do if you see suspicious output in your report:** re-run the affected stage (`bristlenose run --resume`), and if the issue recurs raise an issue on GitHub with the offending transcript (redacted as needed). Do not share the report until the affected sections are reviewed.

Threat model and roadmap for stronger mitigations (label allowlist, red-team fixture corpus, span-grounded quotes): [`docs/design-prompt-injection-defence.md`](docs/design-prompt-injection-defence.md).

## PII redaction

PII redaction is **opt-in** — enable it with `--redact-pii` from the command line. **In the desktop app,** PII redaction settings will be available in a future Settings update. When enabled, Bristlenose uses Microsoft Presidio (spaCy NLP) to detect and replace personally identifiable information in transcripts before LLM analysis. It is off by default because false positives (redacting research-relevant text) damage data accuracy.

**Configurable threshold:** `BRISTLENOSE_PII_SCORE_THRESHOLD` (default 0.7, range 0.0–1.0). Lower values catch more PII at the cost of more false positives. See [Presidio analyzer docs](https://microsoft.github.io/presidio/analyzer/).

### What PII redaction catches reliably

Person names in clear context (~90% recall), email addresses, phone numbers in standard formats, credit card numbers, US Social Security numbers, UK NHS numbers, IBAN codes, and IP addresses.

**Deliberately excluded:** location names — redacting these destroys research data (e.g. "Oxford Street IKEA" becomes "[ADDRESS] IKEA").

### What PII redaction misses

- **Non-Western names** — the spaCy English model has significantly lower recall for names from South Asian, East Asian, African, and Arabic naming traditions
- **Nicknames and diminutives** — informal names like "Bazza", "Deano" are invisible to NER
- **Names that are common words** — "Grace", "Will", "Hope" in ambiguous context
- **Misspelled names** — NER relies on lexical match
- **Dictated contact details** — "john dot smith at company dot co dot uk" is not recognised as an email
- **Phone numbers spoken in words** — "oh seven seven double-oh three six nine"
- **Social media handles, usernames** — not in default entity types
- **UK National Insurance numbers** — no Presidio recogniser
- **Vehicle registrations** — no recogniser

### What PII redaction cannot detect

**GDPR special category data (Article 9):** health conditions, racial or ethnic origin, political opinions, religious beliefs, trade union membership, sexual orientation. No automated tool reliably detects these in conversational speech. They require human review before sharing transcripts externally.

**Indirect identification (GDPR Recital 26):** individually harmless facts that together identify someone — for example, "38-year-old accessibility tester at [employer] in [town] with ADHD" may narrow to one person. Job title combined with employer, rare conditions combined with location, or school names combined with children's ages can all enable re-identification. Automated tools cannot detect these; they require researcher judgement.

### Speaker identification and PII timing

Speaker identification (Stage 5b) sends a small portion of raw transcript to the LLM **before** PII redaction runs (Stage 7), because it needs names and roles to work correctly. This is typically the most PII-dense portion of an interview (introductions, name confirmations). With Ollama (local models), this stays on your machine. With cloud LLM providers, this portion is sent unredacted.

### Audit trail

`pii_summary.txt` is written to the `.bristlenose/` hidden directory inside the output folder. It contains every original PII value with replacement labels, confidence scores, and timecodes — **this file is a re-identification key and must not be shared outside the research team.** Review it to catch false positives or missed items.

`llm-calls.jsonl` is written to the same `.bristlenose/` directory. Each row records one LLM call's cost, timing, model, and participant code (`p1`, `p2` …) for the cost-forecasting feature. The file does **not** contain transcript text, quotes, or LLM prompt/response bodies. **It is a re-identification key when combined with the transcript files in the same project — must not be shared outside the research team, never include in any export or support bundle.** Mode `0o600` and `O_NOFOLLOW` are enforced. The file is local-only and never transmitted; there is no Bristlenose backend that sees this data. To purge: `rm <project>/.bristlenose/llm-calls.jsonl` (deletion of the project folder removes it automatically). Kill switch: `BRISTLENOSE_LLM_TELEMETRY=0` stops new appends. Retention is bounded by `BRISTLENOSE_LLM_CALLS_RETAIN` (default 1000 rows).

### Testing

The test suite includes an adversarial transcript (`tests/fixtures/pii_horror_transcript.txt`) with PII planted across 8 categories designed to stress-test every known weakness in NER-based detection. Expected results are documented in `tests/fixtures/pii_horror_expected.yaml`.

PII redaction is heuristic-based and not guaranteed to catch every instance. Always review the audit summary before sharing transcripts externally.

## Anonymisation boundary

Bristlenose uses two layers of identity: **speaker codes** (p1, p2) and optional **display names** (short names, either set by the researcher or derived from a name found in the recording).

**Always present, never stripped:**

- Speaker codes appear on every quote and in every export. Anonymisation never removes them — they are what lets you trace a quote back to a person using your own records
- The **Send to Miro** export sends codes only; display names are never part of the board payload

**Governed by anonymisation, which is OFF by default:**

- Quote attributions in the report show the display name beside the code, wherever one is set
- The offline HTML export, CSV export, clipboard copy, and video-clip filenames all carry display names
- Turning on **Remove participant names from labels** in the export dialog drops *participant* display names from all of these, leaving codes. Moderator and observer names are kept — they are the research team, not its subjects

So an export shared outside the research team carries participant names unless you turn anonymisation on. Turning it on is what makes quotes safe to paste into a deck or hand to stakeholders without exposing participant identity — and what prevents stakeholders looking participants up, forming biases from names or perceived demographics, or dismissing feedback based on who said it rather than what was said.

**Also contains names:**

- The HTML report file embeds display names in the page source and session table — these help the research team recall who's who ("p3 — Mary — remember, she didn't like the pricing"). Share the `.html` file outside the team and they will see these names
- The sessions grid reveals the **full name**, surname included, as a hover tooltip wherever it differs from the display name
- The Markdown summary includes display names when available
- `people.yaml` in the output directory stores both display names and full names

**Design intent:** Display names are a working tool for the research team (researchers, moderators, observers who were on the call). When findings are presented to a wider audience — product teams, stakeholders, executives — the speaker codes provide the anonymisation boundary. Anonymisation is controlled by a checkbox in the export dialog — **it is off by default**, so an export carries display names unless the researcher ticks it. (An earlier version of this paragraph said the export strips names by default. It does not, and never did: both the query parameter and the dialog checkbox default off. Corrected 25 Aug 2026.)

Moderator and observer names (m1, m2, o1) are not stripped. The boundary is **participant / not-participant**, not team membership: the ethics of anonymisation apply to research subjects, not to colleagues and collaborators. A client-side observer is not on the research team and is still named, because they are not a subject — you may see their clarifying questions attributed in an exported transcript and see them in the people list. They never appear in the Quotes lens, because quotes are participant evidence. See `docs/design-people.md` §E decision 2.

## Serve mode API access control

`bristlenose serve` runs a local HTTP server on `127.0.0.1` (loopback only — traffic never leaves the machine). API endpoints serve research data: participant names, interview quotes, themes, sentiment analysis, and media files.

**Request validation token:** Each server instance generates a random 32-byte token (`secrets.token_urlsafe`, 256 bits of entropy) at startup. If `_BRISTLENOSE_AUTH_TOKEN` is set in the process environment, it overrides the random token — this path exists so CI test fixtures can pin a known token and so `uvicorn --reload` can preserve session continuity across code saves. A future hardening task will gate this override behind an explicit `BRISTLENOSE_DEV_MODE=test` flag so production serve runs ignore environment tokens inherited from the parent shell; tracked in project planning. The token is:

- Kept in process memory (and exported to the process environment for reload recovery) — never written to disk
- Injected into the SPA HTML served to the browser
- Printed to stdout for the desktop app to capture
- Required as `Authorization: Bearer <token>` on all `/api/*` and `/mcp/*` requests (media routes are protected by a path-traversal guard and extension allowlist instead — `<video>` elements cannot send headers)
- Exempt for `/api/health` (version/status only, no project data), `/report/*` (static assets), and a browser-shaped `GET /mcp/` (a static explainer page carrying directions only — no project data, no token)

**MCP endpoint (`/mcp/`):** present when the `bristlenose[mcp]` extra is installed (always, in the macOS app's bundled sidecar); the auth prefix is enforced even when it isn't (fail closed). When the desktop injects a scoped MCP token, `/mcp` validates against that token alone and it opens nothing else; without one (the CLI), `/mcp` accepts the single server token. Bearer-only — the browser auth cookie deliberately does not authenticate it. The MCP SDK's DNS-rebinding protection is active (loopback-only allowed hosts and origins). Tools are read-only and take no filesystem paths (pinned by an input-schema test); participant names follow the project's Anonymise switch (codes-only when it is on), and the only path to the persons table is grounding's gated resolver.

**What this protects against:** Opportunistic API scraping by unrelated local processes. A process that doesn't know the token cannot call `curl http://127.0.0.1:8150/api/projects/1/quotes` — the request returns 401.

**What this does not protect against:** A determined attacker with same-user privileges who fetches the HTML first, extracts the token, and then calls the API. The token is a defence-in-depth speed bump, not an authentication boundary. The real security boundary is OS-level process isolation. This is the standard approach for localhost development servers (VS Code, JupyterLab, Electron apps).

**No TLS:** Serve mode uses HTTP on the loopback interface. Traffic on `127.0.0.1` never hits a network interface, NIC, switch, or router. It cannot be intercepted by network-based attackers. TLS is not used because the loopback interface is not routable — adding TLS would add certificate management complexity without security benefit for same-machine communication.

**Additional protections:**

- **CORS:** `allow_origins=[]` blocks all cross-origin browser requests
- **Media allowlist:** `/media/` route only serves known media file extensions (`.mp4`, `.mov`, `.wav`, `.mp3`, etc.) with path-traversal guard
- **Desktop environment scrubbing:** The macOS app passes only essential environment variables (`PATH`, `HOME`, `LANG`, etc.) to the Python subprocess — no cloud tokens, database passwords, or Xcode debug variables
- **Auditable CI suppressions:** every suppression in the Playwright e2e gate is source-controlled, justified inline with a register ID, and indexed in `e2e/ALLOWLIST.md` with a category and tracker — so the distinction between "CI lubricant we learned to live with" and "real product debt" stays visible over time
- **Debug verbosity is opt-in and double-gated:** unhandled server exceptions always log a traceback to `bristlenose.log`, but the response body returns the generic `Internal Server Error` message by default. Setting `BRISTLENOSE_DEBUG_500=1` returns the traceback in the response body only when the server is also started with `dev=True` (i.e. `bristlenose serve --dev` or a development sidecar build). A shipped sidecar bound to a researcher's laptop ignores the env var. Useful for diagnosing sandbox / packaging issues; not intended to be set in production. See `docs/design-desktop-asset-serving.md`.

## Output files

Bristlenose creates output inside the input folder (`<folder>/bristlenose-output/` by default). Output includes:

- Raw and optionally PII-redacted transcripts
- Intermediate JSON (consumed by `bristlenose serve` to re-open the project without re-running the pipeline)
- HTML report, Markdown summary, CSV of quotes
- `people.yaml` with participant display names

These files persist until you delete them. Bristlenose does not automatically clean up output directories. If your research data is sensitive, manage these files according to your organisation's data-handling policy.

## Vulnerability management

Bristlenose uses automated scanning to detect known vulnerabilities in dependencies:

- **Python** — `pip-audit` runs on every CI build
- **JavaScript** — `npm audit` runs on every CI build
- **Static analysis** — CodeQL (`security-extended` suite) runs on every push and weekly
- **Dependency updates** — Dependabot opens PRs weekly for both Python and JavaScript dependencies
- **Secret scanning** — gitleaks pre-commit hook locally; GitHub server-side scanning on the remote

**Remediation targets:**

| Severity | Direct dependencies | Transitive dependencies |
|----------|-------------------|------------------------|
| Critical | Patch within 7 days | Patch within 7 days if fix available; track in pinned issue if not |
| High | Patch within 30 days | Patch within 30 days if fix available; track in pinned issue if not |
| Medium/Low | Next scheduled release | Review quarterly |

Transitive dependencies with no upstream fix (e.g. advisories in torch or protobuf that only affect training workloads, not Bristlenose's inference-only usage) are documented with justification in CI configuration via `--ignore-vuln` comments.

**SBOM:** CycloneDX Software Bills of Materials for both Python and JavaScript are generated on every CI build and available as build artifacts.

## Reporting a vulnerability

If you find a security issue, please email **security@bristlenose.app** with a description of the vulnerability and steps to reproduce. You should receive a response within 7 days.

Please do not open a public GitHub issue for security vulnerabilities.
