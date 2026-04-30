# Security

## Local-first architecture

Bristlenose runs on your laptop. There is no Bristlenose server, no account, and no telemetry.

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
3. **Whisper downloads its transcription model**, once per model, on first transcription. Model files are downloaded from huggingface.co to `~/Library/Application Support/Bristlenose/models/`. This is data, not code — the download is consumed by the transcription library that already ships signed inside the app.

Bristlenose itself has zero sub-processors. There is no cloud database, no analytics service, no error-tracking vendor, no auth provider, and no telemetry endpoint.

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

Bristlenose uses two layers of identity: **speaker codes** (p1, p2) and optional **display names** (first names, set by the researcher). Full names and surnames are never shown in the report UI.

**What's protected by default:**

- Quote attributions in the report show speaker codes only (p1, p2) — not names
- CSV export and clipboard copy include codes only — quotes can be pasted into Miro, PowerPoint, or shared with stakeholders without exposing participant identity
- This prevents stakeholders from looking up participants, forming biases based on names or perceived demographics, or dismissing feedback based on who said it rather than what was said

**What contains names:**

- The HTML report file embeds display names (first names) in the page source and session table — these help the research team recall who's who ("p3 — Mary — remember, she didn't like the pricing"). If you share the `.html` file with someone outside the research team, they will see these names
- The Markdown summary includes display names when available
- `people.yaml` in the output directory stores both display names and full names

**Design intent:** Display names are a working tool for the research team (researchers, moderators, observers who were on the call). When findings are presented to a wider audience — product teams, stakeholders, executives — the speaker codes provide the anonymisation boundary. The HTML export (Export Report) strips display names by default, making this the safe path for external distribution. Anonymisation is controlled by a checkbox in the export dialog.

Moderator and observer names (m1, m2, o1) are not stripped — they are part of the research team, not research subjects.

## Serve mode API access control

`bristlenose serve` runs a local HTTP server on `127.0.0.1` (loopback only — traffic never leaves the machine). API endpoints serve research data: participant names, interview quotes, themes, sentiment analysis, and media files.

**Request validation token:** Each server instance generates a random 32-byte token (`secrets.token_urlsafe`, 256 bits of entropy) at startup. If `_BRISTLENOSE_AUTH_TOKEN` is set in the process environment, it overrides the random token — this path exists so CI test fixtures can pin a known token and so `uvicorn --reload` can preserve session continuity across code saves. A future hardening task will gate this override behind an explicit `BRISTLENOSE_DEV_MODE=test` flag so production serve runs ignore environment tokens inherited from the parent shell; tracked in project planning. The token is:

- Kept in process memory (and exported to the process environment for reload recovery) — never written to disk
- Injected into the SPA HTML served to the browser
- Printed to stdout for the desktop app to capture
- Required as `Authorization: Bearer <token>` on all `/api/*` and `/media/*` requests
- Exempt for `/api/health` (version/status only, no project data) and `/report/*` (static assets)

**What this protects against:** Opportunistic API scraping by unrelated local processes. A process that doesn't know the token cannot call `curl http://127.0.0.1:8150/api/projects/1/quotes` — the request returns 401.

**What this does not protect against:** A determined attacker with same-user privileges who fetches the HTML first, extracts the token, and then calls the API. The token is a defence-in-depth speed bump, not an authentication boundary. The real security boundary is OS-level process isolation. This is the standard approach for localhost development servers (VS Code, JupyterLab, Electron apps).

**No TLS:** Serve mode uses HTTP on the loopback interface. Traffic on `127.0.0.1` never hits a network interface, NIC, switch, or router. It cannot be intercepted by network-based attackers. TLS is not used because the loopback interface is not routable — adding TLS would add certificate management complexity without security benefit for same-machine communication.

**Additional protections:**

- **CORS:** `allow_origins=[]` blocks all cross-origin browser requests
- **Media allowlist:** `/media/` route only serves known media file extensions (`.mp4`, `.mov`, `.wav`, `.mp3`, etc.) with path-traversal guard
- **Desktop environment scrubbing:** The macOS app passes only essential environment variables (`PATH`, `HOME`, `LANG`, etc.) to the Python subprocess — no cloud tokens, database passwords, or Xcode debug variables
- **Auditable CI suppressions:** every suppression in the Playwright e2e gate is source-controlled, justified inline with a register ID, and indexed in `e2e/ALLOWLIST.md` with a category and tracker — so the distinction between "CI lubricant we learned to live with" and "real product debt" stays visible over time

## Output files

Bristlenose creates output inside the input folder (`<folder>/bristlenose-output/` by default). Output includes:

- Raw and optionally PII-redacted transcripts
- Intermediate JSON (used by `bristlenose render` to re-render without LLM calls)
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
