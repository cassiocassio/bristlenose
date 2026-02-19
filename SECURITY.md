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

## Output files

Bristlenose creates output inside the input folder (`<folder>/bristlenose-output/` by default). Output includes:

- Raw and optionally PII-redacted transcripts
- Intermediate JSON (used by `bristlenose render` to re-render without LLM calls)
- HTML report, Markdown summary, CSV of quotes
- `people.yaml` with participant display names

These files persist until you delete them. Bristlenose does not automatically clean up output directories. If your research data is sensitive, manage these files according to your organisation's data-handling policy.

## Reporting a vulnerability

If you find a security issue, please email **security@cassiocassio.co.uk** with a description of the vulnerability and steps to reproduce. You should receive a response within 7 days.

Please do not open a public GitHub issue for security vulnerabilities.
