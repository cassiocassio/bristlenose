# ASR backend strategy — brief notes

**Created**: 2026-05-11
**Status**: Decision log, not a roadmap. Re-read before evaluating any new ASR backend (Apple Speech, etc.) or considering Whisper download UX changes.

## TL;DR

- **Whisper (via mlx-whisper on Apple Silicon, faster-whisper elsewhere) stays the default.** Out-of-the-box transcription is non-negotiable — the default Microsoft 365 tier gives you recordings without transcripts, so we cannot assume the user has one.
- **Platform transcripts (Teams `.docx`, Zoom `.vtt`, Google Meet) are an optimisation, not the core flow.** Already shipped; auto-detected; skips Whisper + audio extraction + the 1.5GB download. See `docs/design-platform-transcripts.md`.
- **Apple `SpeechTranscriber` is not a backend** — not as default, not as draft, not as fallback. Structural mismatch, not a "wait one more year" gap.
- **Desktop app downloads Whisper on first run, inside the app, covered by engaging first-run content.** Not bundled. Not replaced by Apple Speech.

## Why Apple `SpeechTranscriber` isn't a backend

Apple's on-device ASR (macOS 26+) is trained on a narrow distribution: dictation, voice memos, Siri commands. The model is fast, low-power, zero-setup — and structurally wrong for Bristlenose's audio.

Four compounding mismatches, none of which Apple is incentivised to fix:

1. **Noise + accents.** Whisper's training set accidentally contains huge volumes of rough audio (scraped podcasts, YouTube, conferences). Apple trains on cleaner consumer audio. Office/factory/crosstalk degrades Apple's model more than Whisper's.
2. **Conversational speed.** Dictation runs ~100–130 wpm; natural conversation hits 160–250 wpm with disfluencies, false starts, coarticulation ("gonna", "didja"). Apple's models degrade non-linearly above ~180 wpm. Whisper learned conversational rate from web-scraped speech.
3. **Regional accents.** Apple ships per-locale dictation models tuned for *careful speech in that locale*. Whisper picked up Indian, Nigerian, Scottish, Singaporean English at scale from web scrape — robust by accident.
4. **L2 English with substrate accent.** No "Polish-substrate English" model exists in Apple's lineup and never will (50+ first languages × ~10 English varieties = combinatorial explosion). Whisper handles L2 well because the training distribution included it heavily.

**The compounding kills it.** Real UXR audio is often all four at once: a non-native speaker with a regional accent talking fast in a noisy environment about something they care about. Each factor degrades Apple's model more than Whisper's; stacked, the gap is "usable transcript" vs "unusable transcript that mangles the analytically important moments."

**Critically: this gap is biased.** Apple's model works best on default-persona speakers (native-English, careful, quiet room) and worst on under-represented ones. UXR's whole point is reaching users who aren't the default persona. An ASR backend that systematically transcribes default-persona speakers well and everyone else badly would invert the value of doing the research.

## Why "Apple as fast draft, Whisper as quality pass" doesn't work

The two-pass pattern assumes the draft is cheap and disposable. In Bristlenose, neither holds:

- The draft transcript is upstream of diarisation, PII redaction, topic segmentation, quote extraction, clustering. By the time the user sees the draft report, hours of pipeline + user attention have been spent on it.
- The user has formed impressions. The transcript isn't a scratch artifact — it's the substrate everything else is anchored to.
- If the draft mangles Maria's interview, the user's reaction isn't "let me re-run with the quality backend." It's "this tool got Maria's interview wrong, I don't trust the rest." They bounce.
- First impressions of an analysis tool are made on the *hardest* cases, not the easiest. The researcher is judging on the messy interview they were dreading, not the articulate native-English PM.

## The real competitive frame

Bristlenose's competition isn't Dovetail or Marvin. It's **"paste the Teams `.docx` into Copilot and ask for pain points and themes."** Zero new tools, zero IT approval, zero marginal effort.

For Bristlenose to be worth the friction of "install this thing, point it at a folder, wait," out-of-box quality has to beat Copilot's free baseline on the same recording — *with whatever model ships by default*, not "with the quality backend if you tune it."

Teams transcribes well on remote calls because it has per-participant audio streams (structural advantage Bristlenose can't match for single-mic recordings). On in-person / single-mic recordings, Teams is in the same boat as Whisper. So the architectural answer is:

1. **Accept Teams/Zoom/Meet transcripts directly** — neutralises the Copilot advantage by accepting the same input. ✅ Shipped.
2. **Beat Whisper-quality on audio Teams never touched** (in-person interviews, field recordings, archives). ✅ Whisper turbo already clears the bar.
3. **Don't bother trying to beat Teams' diarisation on remote calls** — they have structural advantages we don't. We win on analysis, not on transcript quality for that subset.

## Lazy Whisper download — load-bearing UX gate

The Whisper model is **never instantiated** when all sessions have existing transcripts. Double-gated:

- `pipeline.py:2026-2035` — pipeline skips `transcribe_sessions()` entirely if `needs_transcription` is empty.
- `s05_transcribe.py:58-65` — stage itself short-circuits before any backend init.

This is intentional. The desktop app's first-run UX depends on it: users who happen to bring Teams Premium / Zoom transcripts never see the 1.5GB download. A "warm up the backend on app launch" optimisation would defeat this — **don't add one**.

A regression test pinning this behaviour (mock the model classes, assert never called when all sessions have transcripts) is tracked in the project board.

## Desktop first-run plan

- Whisper download happens **inside the app on first run**, not at install / not bundled.
- ~5 minute wait on typical connection.
- Covered by first-run content (TBD — Track B Branch 2+): explainer, sample report tour, settings walkthrough, maybe a tiny demo dataset.
- Replaces "stare at progress bar" with "explore the product while we fetch the model."

## When to revisit this doc

- **Apple ships a conversational-speech model.** Unlikely on current trajectory (cuts against Siri/dictation priorities), but if it happens, re-test points 1–4 above on real UXR audio before changing anything.
- **App Store bundle-size limits change materially.** If bundling becomes practical, the first-run UX argument weakens — but the "post-install commitment" argument still holds.
- **Real cohort feedback** shows users abandoning at the 1.5GB download step despite first-run content. Then revisit the bundle/streaming/Apple-fallback trade. Cohort first, architecture second.
