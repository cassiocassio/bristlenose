# Real-Data Testing Strategy

## Why synthetic data isn't enough

The fishkeeping, rockclimbing, and Socrates datasets exercise pipeline mechanics — stage transitions, JSON schemas, quote extraction logic. They don't test:

- **Transcription fidelity** — real accents, mumbling, crosstalk, background noise, varied recording quality
- **Thematic analysis depth** — whether clustering and theming produce coherent, meaningful findings on a real corpus with genuine themes (not planted ones)
- **Scale rendering** — 100+ sessions, 500+ quotes, minimap performance, scroll feel, sidebar responsiveness
- **Multi-language analysis** — whether quote extraction, sentiment tagging, and thematic grouping work in Spanish, French, Korean (not just English)
- **Public-domain screenshots** — marketing site, App Store listing, and blog posts need real interview content that we can show publicly

---

## English sources

### Tier 1 — Bulk-downloadable, public domain or Creative Commons

These can be freely downloaded, redistributed, and used in screenshots.

| Source | Volume | Format | Licence | What it tests |
|--------|--------|--------|---------|---------------|
| **[StoryCorps Archive](https://archive.storycorps.org/)** | Tens of thousands of interviews | Audio (MP3) | Public archive, individually downloadable (share icon > Download) | Speaker diarisation (2 speakers per recording), sentiment variety, real speech patterns, varied audio quality |
| **[Internet Archive — Oral History](https://archive.org/details/OralHistory)** | Hundreds of recordings | Audio + video, some with .srt subtitles | Varies per item, many public domain | Mixed-format ingestion (video + existing subtitles), subtitle parsing path |
| **[FOSSDA — Free and Open Source Stories](https://fossda.org/)** | ~50 interviews with open-source pioneers | Video | Public domain (via Permanent.org) | Thematic clustering on a focused, coherent topic (tech history) |
| **[IWM Sound Archive](https://www.iwm.org.uk/collections/sound)** | 33,000+ recordings, 60,000+ hours | Audio (streamable, downloadable for non-commercial use) | Non-commercial personal use permitted | British English accents, long-form interviews, historical themes. Downloadable for non-commercial offline listening |

### Tier 2 — Large scale, public domain, transcripts only (no audio/video download)

Useful for exercising the analysis pipeline (post-transcription) at scale.

| Source | Volume | Format | Licence | What it tests |
|--------|--------|--------|---------|---------------|
| **[NASA JSC Oral History Project](https://www.nasa.gov/history/history-publications-and-resources/oral-histories/johnson-space-center/)** | 100+ astronaut and engineer interviews | Text transcripts (downloadable) | US government, public domain | .txt ingestion path, thematic analysis on a coherent corpus at scale, quote extraction from pre-existing transcripts |
| **[Veterans History Project](https://www.loc.gov/collections/veterans-history-project-collection/)** | 121,000+ collections | Mixed (some digitised audio/video, mostly on-site) | US government, public domain | Public-domain screenshots for marketing. Video thumbnail extraction |

### Tier 3 — Access-restricted (evaluated, not usable)

Documented here so we don't re-research them.

| Source | Why not |
|--------|---------|
| **[USC Shoah Foundation](https://sfi.usc.edu/vha/access)** | 55,000 video testimonies but strictly copyright-restricted. No bulk download. Institutional access only |
| **[Fortunoff Archive (Yale)](https://fortunoff.library.yale.edu/)** | 4,400 testimonies. Viewing at access sites only, no download |

---

## Non-English sources

Matching Bristlenose's 5 non-English locales (es, fr, de, ko, ja). Tests whether quote extraction, sentiment tagging, and thematic grouping work outside English.

### Spanish

| Source | Volume | Format | Licence | Notes |
|--------|--------|--------|---------|-------|
| **[SpinTX Video Archive](https://spintx.org/)** (UT Austin) | Hundreds of short captioned video clips | Video + synchronised transcripts | Creative Commons (non-commercial) | Native and heritage Spanish speakers in Texas. Captioned, annotated. Ideal for testing Spanish transcription + analysis |
| **[Spanish in Texas Corpus](https://coerll.utexas.edu/coerll/project/spanishtx/)** | Interviews and conversations | Video + audio + full transcripts + POS annotations | Academic open access | Downloadable, richly annotated |
| **[Library of Congress — Hispanic collections](https://www.loc.gov/audio/?fa=language:spanish)** | Varied | Audio | US government, public domain | Includes the Juan B. Rael Collection (ethnographic field recordings) |

### French

| Source | Volume | Format | Licence | Notes |
|--------|--------|--------|---------|-------|
| **[INA — Institut National de l'Audiovisuel](https://www.ina.fr/)** | 100,000 indexed archives, 20,000h free online | Video + audio (streamable) | Free online consultation; licensing for reuse | Includes interview programmes like *Radioscopie* and *Les Pieds sur terre*. Streaming, not bulk download — would need individual capture |
| **[Service historique de la Defense](https://www.servicehistorique.sga.defense.gouv.fr/en/resources/oral-archives)** | ~2,500 testimonies, ~6,000 hours | Audio | French government archive | Military and conflict oral histories |

### Korean

| Source | Volume | Format | Licence | Notes |
|--------|--------|--------|---------|-------|
| **[Korean War Legacy Foundation](https://koreanwarlegacy.org/interactive-library/)** | 1,100+ video interviews | Video (streamable, searchable) | Free educational use | Interviews with veterans from dozens of countries. Includes Korean-language interviews alongside English. Tagged with metadata and short clips |
| **[Korean National Archives (국가기록원)](https://www.archives.go.kr/)** | 2.7 million archival sources | Mixed | Korean government | Interface in Korean. Includes oral histories, audio-visual materials |

### German and Japanese — gaps

Not yet researched. Candidates to investigate:

- **German**: Deutsches Historisches Museum oral history, Bayerische Staatsbibliothek audio archives, Zeitzeugen (contemporary witness) projects
- **Japanese**: NHK Archives, National Diet Library digital collections, Hiroshima/Nagasaki testimony archives

---

## UXR usability test recordings (record your own)

No public source exists for raw, unedited usability test recordings. Published UXR videos are always NDA'd session material or curated highlight reels — never the full moderator + participant + screen + tasks session that Bristlenose is designed to analyse.

**This is the most important gap.** The oral history sources test scale, transcription, and thematic depth. But they don't have the task-based structure that the UXR codebook is built for: moderator sets task, participant attempts, friction or success, moderator probes. That structure is what drives sentiment tags (frustration, confusion, delight, trust), quote categories (friction points, workarounds, feature requests), and moderator question detection.

### Plan: record 5-6 sessions with friends

- **Target site**: a public website with clear tasks. gov.uk is ideal (well-known, tasks are obvious, no NDA issues). Alternatives: NHS.uk, a charity site, a council website
- **Participants**: friends or family, not UX professionals. Varied ages and tech confidence
- **Format**: Zoom or Meet recording with screen share + face camera. 30-45 minutes each
- **Structure**: classic moderated usability test
  - 4-5 tasks ("find out how to renew your passport", "check if you need a visa for Thailand", "find your local recycling centre")
  - Think-aloud protocol
  - Moderator probes after each task ("what were you expecting?", "what was confusing?")
- **Output**: ~4 hours of .mp4 video
- **What it tests**:
  - Moderator question detection (the pill feature)
  - Task-centric friction tagging
  - The full UXR codebook sentiment taxonomy
  - Quote extraction boundaries around task sequences
  - Speaker diarisation (moderator vs participant)
- **Double duty**: this is also the demo dataset for the marketing site and the "folder in, report out in 5 minutes" speed demo video (100days Section 1 + Section 7)

### Why this matters more than the oral histories

The oral history sources prove the pipeline works at scale. The usability test recordings prove the **analysis is good** — that the UXR codebook produces findings a researcher would actually agree with. This is the out-of-box value proposition. If the codebook tags a moment of confusion correctly, if it spots the friction point, if it groups related findings into a coherent theme — that's the product working.

---

## Recommended test matrix

The minimum viable real-data corpus that exercises all pipeline paths and all target languages:

| Corpus | Sessions | Format | Language | Pipeline path exercised |
|--------|----------|--------|----------|------------------------|
| NASA JSC transcripts | ~50 | .txt | English | Ingest > parse > topic segmentation > quote extraction > clustering > theming > render |
| StoryCorps audio | ~30 | .mp3 | English | Ingest > extract audio > transcribe > diarise > merge > full analysis pipeline |
| Veterans History Project video | ~5 | .mp4 | English | Video ingestion > thumbnail extraction > transcription > full pipeline. Screenshot candidates |
| SpinTX clips | ~20 | .mp4 + .srt | Spanish | Subtitle parsing > Spanish-language analysis > i18n rendering |
| IWM Sound Archive | ~10 | .mp3 | British English | British accent transcription quality, historical themes |
| Korean War Legacy | ~10 | .mp4 | Korean + English | Korean-language analysis, mixed-language handling |
| **Own UXR usability tests** | **~6** | **.mp4** | **English** | **UXR codebook validation, moderator question detection, task-centric analysis, demo dataset, marketing screenshots** |

**Total: ~130 sessions, ~100+ hours, 3 formats, 3 languages + the critical UXR usability format**

---

## Method

### Acquisition

1. **NASA transcripts** — download directly from [nasa.gov oral histories](https://www.nasa.gov/history/history-publications-and-resources/oral-histories/johnson-space-center/). Save as `.txt` files. No scraper needed, individual page downloads
2. **StoryCorps** — use archive.storycorps.org, click share > download on each interview. Select interviews across topics for thematic variety. ~30 interviews, ~20 hours
3. **VHP video** — download a handful of digitised video interviews from loc.gov. Focus on ones with clear audio for transcription quality testing
4. **SpinTX** — download clips from spintx.org. Creative Commons, freely redistributable
5. **IWM** — download from iwm.org.uk/collections/sound. Non-commercial use permitted
6. **Korean War Legacy** — contact for download access or capture individual interviews from koreanwarlegacy.org
7. **Own UXR usability tests** — recruit 5-6 friends, record Zoom sessions testing a public website (gov.uk). ~4 hours total. This is the only way to get task-based usability test recordings

### Folder structure

```
trial-runs/
  nasa-astronauts/           # ~50 .txt transcripts
  storycorps-diverse/        # ~30 .mp3 audio interviews
  veterans-video/            # ~5 .mp4 video interviews
  spintx-spanish/            # ~20 .mp4 + .srt (Spanish)
  iwm-british/               # ~10 .mp3 (British English)
  korean-war-legacy/         # ~10 .mp4 (Korean + English)
```

Each folder is a separate Bristlenose project. Run independently, then compare analysis quality across corpora.

---

## Objectives

### Transcription quality
- [ ] StoryCorps: spot-check 10 transcripts against audio. Note diarisation accuracy (2 speakers per recording)
- [ ] IWM: check British accent handling (place names, military terminology)
- [ ] SpinTX: compare Whisper transcription against provided ground-truth transcripts
- [ ] Korean War Legacy: check Korean-language transcription accuracy

### Thematic analysis quality
- [ ] NASA: do themes make sense for a space programme oral history? Are findings coherent?
- [ ] StoryCorps (diverse topics): does the pipeline handle topic diversity without producing meaningless "miscellaneous" clusters?
- [ ] SpinTX: does Spanish-language thematic grouping produce sensible categories?

### Scale and performance
- [ ] NASA (50 sessions): measure wall-clock time per stage, memory high-water mark
- [ ] Combined corpus (125 sessions): render time, minimap performance, scroll feel at 500+ quotes
- [ ] Identify any O(n^2) bottlenecks in clustering or rendering

### Screenshot candidates
- [ ] Veterans History Project: capture 3-5 report screenshots showing real interview content for marketing
- [ ] NASA: capture analysis view showing thematic breakdown of astronaut interviews
- [ ] Ensure all screenshot content is unambiguously public domain (US government work)

### i18n analysis quality
- [ ] Spanish (SpinTX): are sentiment tags, quote boundaries, and codebook categories correct?
- [ ] Korean: does quote extraction respect Korean sentence boundaries?
- [ ] Document any language-specific pipeline failures for future fixing

---

## Golden-file regression (future)

Once the real-data corpus is stable:

1. Freeze pipeline output (JSON) for one representative project as a reference
2. After code changes, re-run and diff against reference
3. Catches both quality regressions (different quotes extracted) and performance regressions (slower stages)
4. Automate as a CI step or cron job on the development machine
