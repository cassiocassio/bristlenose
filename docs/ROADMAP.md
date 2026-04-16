# Bristlenose — Roadmap

A rough map of where the project is, what's coming, and what's further out. For shipped work see [CHANGELOG.md](../CHANGELOG.md); for contributor notes see [CLAUDE.md](../CLAUDE.md).

## What Bristlenose is

A local-first analysis tool for user-research interviews. Point it at a folder of recordings, get an interactive HTML report with extracted quotes, themes, sentiment, and user journeys. Everything runs on your laptop — the only network traffic is to your chosen LLM provider for the analysis prompts.

Licensed AGPL-3.0. Distributed via PyPI, Homebrew, and Snap.

## Today — v0.14.x

- 12-stage pipeline: recordings → transcripts → quotes → themes → report
- Five LLM backends: Claude, ChatGPT, Azure OpenAI, Gemini, and Ollama (local, free)
- Serve mode (FastAPI + SQLite + React SPA) with inline editing, tags, stars, search, quote clustering, video clip export, and self-contained HTML export
- macOS desktop app in beta — SwiftUI shell over a bundled Python sidecar
- Six UI languages: English, Spanish, French, German, Korean, Japanese

## Next

Active work, driven by the push from CLI tool to end-user app:

- **Multi-project** — one app, many projects, switch without restart ([design-multi-project.md](design-multi-project.md), [design-project-sidebar.md](design-project-sidebar.md))
- **Drag-and-drop import** — add recordings without the command line
- **Research-package export** — zip of report + transcripts + video clips for handing off ([design-export-html.md](design-export-html.md))
- **First-run experience** — skip the terminal and the API-key ceremony
- **Incremental re-run** — add new interviews to an existing project, preserve your tags and edits ([design-serve-milestone-1.md](design-serve-milestone-1.md))
- **Performance gates** — virtualisation for 1000+ quote reports, bundle-size budget, CI regression tests ([design-performance.md](design-performance.md))
- **Accessibility pass** — WCAG 2.1 AA, VoiceOver, keyboard-complete navigation
- **Visual polish** — typography audit, SVG icon set, colour themes, responsive quote grid ([design-responsive-layout.md](design-responsive-layout.md))

## Later

Shaped with design notes but not the current priority. Open an issue if one of these matters to you.

- **Windows** via winget and a Windows credential store (#44)
- **Transcript editing** — strike sections, correct text, with an audit trail ([design-transcript-editing.md](design-transcript-editing.md))
- **Cross-session speaker linking** — moderator and participant identity across interviews ([design-transcript-speaker-editing-roadmap.md](design-transcript-speaker-editing-roadmap.md))
- **Edit writeback** — propagate edits from the report back into source transcript files (#21)
- **.docx export** — Word output for stakeholder sharing (#20)
- **Multi-page reports** — tabs or linked pages for very large corpora (#51)
- **Custom prompts** — user-defined tag categories and analysis instructions
- **Batch processing** — queue multiple projects (#27)
- **Miro bridge** — CSV export works today; full API integration designed but parked ([design-miro-bridge.md](design-miro-bridge.md))
- **Published reports** — hosted sharing with embedded video clips

## Dependency risk register

Floor-pinned and monitored. Quarterly: `pip list --outdated`, bump for security fixes or needed features. Annual: Python EOL check, major-version review of spaCy and Pydantic, rebuild Snap, scan `pip-audit`.

| Dependency | Risk | Escape hatch |
|---|---|---|
| faster-whisper / ctranslate2 | High | mlx-whisper (macOS), whisper.cpp bindings |
| spaCy + thinc + presidio | Medium | Pin spaCy 3.x; confined to the PII redaction stage |
| anthropic / openai / google-genai SDKs | Low | Floor pins, backward-compatible |
| Pydantic | Low | Stable at 2.x |
| Python | Low | Running 3.12; floor bumps when 3.10 EOLs (Oct 2026) |

---

*Feature requests and bug reports belong on the GitHub issues tracker. To contribute, see [CONTRIBUTING.md](../CONTRIBUTING.md).*
