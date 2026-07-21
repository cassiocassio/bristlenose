# Design: CLI session fusion — terminal capture + think-aloud video

**Status: exploration — parked.** Not on the roadmap and not a scheduled feature. Documented so the prior-art survey and licence clearances below aren't repeated. Positioned (see §Positioning) as a possible optional open-source capture adapter, not a core or paid capability.

## The idea

Record a participant doing a task in a terminal while also recording think-aloud video/audio (e.g. a moderated call). Capture the terminal at high fidelity (asciicast + OSC 133 semantic marks), synchronise all streams on one timeline, and feed the fused artifact into Bristlenose's existing analysis so the codebook can code **"what they said" alongside "what they typed/did."**

The payoff that a transcript-only tool can't reach is **silent friction**: a participant runs several failing commands, hesitates, opens docs, and says nothing. Audio-only records a gap; the terminal track records the failed commands and exit codes. In CLI studies the non-verbal track is often the primary signal.

## Prior art — the specific combination is a genuine gap

The combination of (terminal-semantic capture) + (time-synced think-aloud video) + (automated/LLM qualitative coding) appears in **no** surveyed system. The closest work each has two of the three legs and explicitly lacks the third:

- **ChronoViz** (Fouse/Weibel et al., CHI 2011) — central video pane over stacked per-source timelines with one playhead + user-defined coding. Ingests *generic* "computer logs" but has zero terminal/shell awareness and no auto-coding. https://adamfouse.com/pdfs/fouse-chi-2011.pdf
- **ANVIL / ELAN** — multi-track annotation on a user-defined coding scheme; no terminal semantics, manual coding. https://www.anvil-software.de/ , https://en.wikipedia.org/wiki/ELAN_software
- **IDE++** (Onward! 2014) — fine-grained structured developer-interaction capture, but IDE-scoped (not terminal), no video/think-aloud, and *explicitly* leaves interpretation "to future work." https://earlbarr.com/publications/ideplus.pdf
- **CodeWatcher** (ICSME 2025) — VS Code editor-event logging; not terminal, no think-aloud, no coding. https://arxiv.org/abs/2510.11536
- **Greenberg csh corpus** (1988) — large-N naturalistic terminal traces, but logs only. https://saul.cpsc.ucalgary.ca/pmwiki.php/HCIResources/UnixDataReadme
- Field context: Google CHI 2021 documents "CLIs are unstructured text interfaces" with no semantic anchors (https://research.google/pubs/accessibility-of-command-line-interfaces/); Schröder & Cito 2022 apply qualitative coding to shell aliases — but static artifacts, not time-synced sessions (https://arxiv.org/pdf/2012.10206).

Absence-of-prior-art can't be proven exhaustively, but the closest systems each disclaim exactly the missing leg.

## Building blocks — all licence-clear for an AGPL-3.0 product

Verified against primary sources (21 Jul 2026). No non-commercial/research-only blockers anywhere.

| Building block | Licence | Reuse mode | Verdict |
|---|---|---|---|
| asciicast v2 format | open spec | write own reader/writer | free |
| OSC 133 / FinalTerm marks | escape-sequence standard | implement yourself | free |
| asciinema recorder | GPL-3.0+ | subprocess | safe (no infection) |
| asciinema-player (JS) | Apache-2.0 | embed in report | safe (Apache→AGPL compatible) |
| pyte (screen replay) | LGPL-3.0 | linked library | safe |
| OmniParser caption model | MIT | weights | safe |
| OmniParser detector (default) | AGPL-3.0 (Ultralytics YOLOv8) | weights | ok for an AGPL product |
| OmniParser `icon_detect_v3` | MIT (YOLOv9 rewrite) | weights | permissive escape hatch |
| ELAN EAF format | open XML schema | reusable | free |
| ANVIL | proprietary, research-only | **do not embed** | blocked |

OmniParser was the one that could have dead-ended a paid product; it did not — the only copyleft is AGPL on the detector weights, which is consistent with Bristlenose's AGPL posture, and an MIT detector path exists. (`icon_detect_v3` MIT status is Microsoft-asserted; confirm the per-folder LICENSE before relying on it.)

## Synchronisation — no Java

Audio-fingerprint tools SyncSink/Panako are AGPL **+ JVM** — rejected (no JRE in a Mac sidecar). Workaround ladder, all no-Java, permissive, reusing the already-bundled ffmpeg:

1. **Default — FFT cross-correlation** on the shared voice signal (numpy/scipy or librosa, ~20 lines). Correlate a start-window and an end-window → affine offset+drift, derived automatically. This subsumes the manual "3-2-1-go" spoken-slate idea.
2. **If codec/SNR brittle** — `audalign` (MIT, pip, purpose-built to align recordings) or `audfprint` (Dan Ellis, MIT). Pure-Python on numpy; ffmpeg for decode.
3. **Zero-dep** — roll landmark fingerprinting (~150 lines numpy). Patent-clear: the core Shazam landmark patent (US 6,990,453) expired ~2021.

Simplification: capture the mic on the **same machine** as the terminal cast → they share a clock for free → only *local-mic ↔ call-audio* needs aligning, one correlation.

## Reconstruction & highlighting

- **Replay** the asciicast through pyte to reconstruct screen state at time T; render as a **styled HTML frame** (cells → themed spans), not a PNG — fits the HTML report, stays selectable/searchable.
- **OSC 133** (`A` prompt-start / `B` input-start / `C` output-start / `D;<exit>` finished) segments the stream into command episodes with exit codes, no program instrumentation. Caveat: `B` and the exit code are *optional* in the spec, so capture must **inject a known-good shell integration** (spawn the recording shell with an rcfile) rather than trust the participant's terminal.
- **Exit codes are a free, deterministic friction signal** — a run of non-zero exits with no co-timed utterance is silent friction, detectable without an LLM.
- **Highlighting is mode-aware.** Line mode: the OSC 133 episode *is* the highlight (box last command + output; auto-flag non-zero exits). Alt-screen (vim/htop/fzf/tmux, detectable via `\033[?1049h`/`l`): drop to full-frame, lean on the utterance. tmux is known-degraded (full-redraw + OSC passthrough) — document, don't chase.

## Multi-surface reality

Real sessions span a full desktop (multiple terminals, browser, file manager, perf tools). The **screen video is the master timeline** (complete but lossy); the terminal cast, browser URLs, and a **focus/window log** (`[t, app, title]`) are *indexes* that make the video queryable. The keystone cheap add is the focus timeline — it answers "which terminal" and "when did they leave for the browser." For un-instrumented surfaces, run a vision model (OmniParser) on the frame at each *already-flagged* timestamp (quote, exit-cluster, silent stall) rather than the whole recording. The codebook then codes a multi-surface evidence timeline: `utterance ∥ action-on-surface-X`.

## Positioning

Addressable audience is small: the overwhelming majority of salaried UX-research work targets web/GUI surfaces, and CLI-as-a-research-surface is culturally uncommon among the developers and engineering leaders who own CLIs (even large orgs staff usability/design on web consoles and billing UX but not on CLI *structure*). The cohort's native feedback channel is asynchronous/text/public (issues, RFCs, PRs), not recorded observed sessions.

Conclusion: if built, position as an **optional open-source capture adapter that feeds the existing pipeline** — a thin `bristlenose record` (spawned OSC-133 shell → asciicast + mic audio → a folder the current pipeline already ingests), reusing the analysis/report/codebook wholesale with no new product surface. Value is developer-community reach and product identity, not direct revenue. It must not compete for time with the core roadmap.

If it ever lands with users at all, the framing that fits the culture is to lead with the **trace** (exit codes are receipts engineers trust over interviews) and frame sessions as "find where the tool is confusing," not "test the user."

## Open questions

- **The load-bearing unknown is not technical.** Will competent CLI practitioners agree to be recorded struggling, and does the "blame the tool, here's the trace" framing get a yes? A half-day recruiting probe answers this before any build.
- Confirm `icon_detect_v3`'s per-folder MIT LICENSE before relying on the permissive OmniParser path.
- Fallback capture when a participant's shell lacks OSC 133 integration (the spawned-shell injection is the intended answer).
