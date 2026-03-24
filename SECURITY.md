# Security

## Local-first architecture

Bristlenose runs on your laptop. There is no Bristlenose server, no account, and no telemetry.

**Transcription** happens locally using Whisper (faster-whisper or MLX Whisper). Audio never leaves your machine.

**LLM analysis** requires API calls to your configured provider (Claude, ChatGPT, Azure OpenAI, or Gemini). Transcript text is sent to those APIs and is subject to each provider's data-handling policy. If you need fully offline analysis, use Ollama with a local model — no data leaves your machine.

## Credential storage

API keys are stored in your operating system's secure credential store:

- **macOS** — Keychain (via `security` CLI)
- **Linux** — Secret Service (GNOME Keyring / KDE Wallet, via `secret-tool`)
- **Fallback** — environment variables or `.env` file

Keys are never written to disk in plaintext by Bristlenose. The `.env` fallback is read-only — Bristlenose reads it if present but does not create or modify it.

## PII redaction

PII redaction is **opt-in** via `--redact-pii`. When enabled, Bristlenose uses Microsoft Presidio (spaCy NLP) to detect and replace personally identifiable information in transcripts before LLM analysis.

**Redacted entity types:** person names, phone numbers, email addresses, credit card numbers, national ID numbers (US SSN, UK NHS), driver's licence numbers, passport numbers, bank account numbers, IBAN codes, IP addresses, URLs, dates/times.

**Deliberately excluded:** location names — redacting these would destroy research data (e.g. "Oxford Street IKEA" becomes "[ADDRESS] IKEA").

**Audit trail:** `pii_summary.txt` in the output directory lists every redaction with the original text, replacement label, confidence score, and timecode. Review this file to catch false positives or missed items.

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

**Design intent:** Display names are a working tool for the research team (researchers, moderators, observers who were on the call). When findings are presented to a wider audience — product teams, stakeholders, executives — the speaker codes provide the anonymisation boundary. The planned export/share feature will strip names by default, making this the safe path for external distribution.

Moderator and observer names (m1, m2, o1) are not stripped — they are part of the research team, not research subjects.

## Serve mode API access control

`bristlenose serve` runs a local HTTP server on `127.0.0.1` (loopback only — traffic never leaves the machine). API endpoints serve research data: participant names, interview quotes, themes, sentiment analysis, and media files.

**Request validation token:** Each server instance generates a random 32-byte token (`secrets.token_urlsafe`, 256 bits of entropy) at startup. The token is:

- Stored in memory only — never written to disk
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

If you find a security issue, please email **security@cassiocassio.co.uk** with a description of the vulnerability and steps to reproduce. You should receive a response within 7 days.

Please do not open a public GitHub issue for security vulnerabilities.
