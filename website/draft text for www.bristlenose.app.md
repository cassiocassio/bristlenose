# Draft text for www.bristlenose.app

---

## Hero

Eight interviews. You have eight interviews in a folder on your desktop.

You can point the program at the folder and it will do the work. Transcribe them, find the quotes, group them by what the person was looking at and what kept coming up. It marks what was good and what was bad. Five minutes for a study.

Free and open source. macOS, Windows, Linux.

---

## Features

### Find the quotes that matter

It finds the good quotes. The filler is gone but the feeling is still there. The meaning is there. Click a timecode and you hear the exact moment.

### Never lose context

The full transcript is there. Every word, every speaker. The words are highlighted as the recording plays. If someone wants to know what was really said you can show them. You do not have to explain.

### Watch the moment, not the hour

Each quote has a link to the video. Click it. Watch ten seconds. Close it. You don't have to scrub through an hour of recording to find one thing.

### Organise your way

You can tag things however you want. Your codes, your system. Or use someone else's — Nielsen, Garrett, Morville. Drag them. Drop them. Give them colours. It doesn't care.

### See where the pain is

Three people confused by the same form. That's not a coincidence. That's your finding, right there. Frustration and confusion and delight — it surfaces all of it across every interview.

### Share without the setup

When you're done you hand someone a file. One file. They open it in a browser. No names — just speaker codes. They don't know who said what. That's the point.

---

## The pitch

You've run eight interviews. The recordings are in a folder and stakeholders want findings.

The tools that do this kind of thing cost money. Real money. More than the project, sometimes. And you still end up doing the work yourself, dragging quotes onto sticky notes, hoping you caught the pattern. The other way is to sit and listen and write things down and listen again and after two days you have notes and you hope they are right.

Point the program at your recordings — audio, video, or transcripts from Zoom, Teams, or Google Meet — and it handles the mechanical part. Transcription runs on your machine. The analysis finds the speakers and pulls the quotes and puts them where they belong. A typical study takes two to five minutes.

What you get is a report. It is a good report. You can star the quotes you want. You can hide the ones you don't. You can tag them with your own codebook and search for them and export them. The keyboard shortcuts are fast. J and K to move. S to star. T to tag. R to repeat the last tag. You can do this all day and your hands do not leave the keyboard.

A researcher built it. Not a company. Just a researcher who got tired of the same thing you're tired of. Free, open source, no accounts, no telemetry.

---

## How it works

1. **Drop in your recordings.** Any mix of audio, video, or existing transcripts.
2. **Wait a few minutes.** Transcription, speaker identification, quote extraction, thematic grouping.
3. **Curate and share.** Star, tag, filter. Export the findings that matter.

---

## Privacy

Nothing leaves your laptop. There is no server. There is no account. There is no telemetry. Transcription is local. The analysis can be local too if you use Ollama. Your data stays with you and that is the end of it.

---

## Providers

Pick one. Switch any time.

- **Claude** — best quality, ~$1.50 per study
- **ChatGPT** — similar quality, ~$1.00 per study
- **Gemini** — budget option, ~$0.20 per study
- **Azure OpenAI** — enterprise compliance
- **Ollama** — free, fully local, no account

---

## Pricing

Free and open source. A typical study costs about $1.50 in API fees. You bring your own key. Use Ollama for $0. The core tool stays free.

---

## Manual intro

A folder of recordings goes in. Findings come out. Quotes grouped by screen and theme with sentiment marked and friction surfaced. That is what the program does.

## Sessions and participants

Each recording is a session. The program knows who is talking. There is the researcher who asks the questions. The researcher is never quoted. There is the participant. The participant is the data. Sometimes there is someone else in the room who does not talk. They are not in the report.

Everyone gets a code. P1. P2. You can add names for yourself, but the names don't leave the project. What goes out is the code.

## Quotes

It pulls out the good parts. The things worth quoting. It cleans them up a little — the filler words, the false starts — but it keeps the corrections, the hesitations that mean something. If someone changed their mind mid-sentence, that stays because it is true. Context is added only when the meaning would be lost without it. Each quote shows up once. Just once.

## Sections and themes

Sections group quotes by screen or task — what the participant was looking at. Themes group quotes by what kept coming up across participants. Screen-specific quotes go to sections. General-context quotes go to themes.

## Sentiment and signals

Every quote gets sentiment. Positive, negative, neutral, mixed. Specific emotions — confusion, delight, frustration, trust, skepticism. Signal cards surface the patterns. Wins and problems and niggles and surprises.

## Serve mode

    bristlenose serve ./interviews/

It opens in the browser. Everything you do is saved — star quotes, tag, hide noise, edit names, reorganise your codebook. Changes persist between sessions. This is the primary way to work with it.

What you can do:

- **Star quotes** — the ones that belong in your presentation
- **Hide quotes** — dismiss noise without deleting it
- **Tag quotes** — your own codes, with autocomplete from your codebook
- **Edit names** — display names for participants and moderators
- **Edit codebook** — drag-and-drop tags between groups, rename, recolour
- **AutoCode** — let the AI propose tags, then set a confidence threshold
- **Search** — any quote across all interviews
- **Filter by tag** — one code at a time
- **Export** — CSV for Miro or FigJam, or self-contained HTML for stakeholders

## Codebooks

A codebook is a set of tags. Each tag belongs to a group. Each group has a colour. You can import a standard framework — Nielsen's heuristics, Garrett's Elements of UX, Norman's Emotional Design, Morville's honeycomb, Yablonski's Laws of UX — or make your own.

AutoCode: press the button and the AI proposes tags. You set a threshold. Above it, accepted. Below it, rejected. The borderline cases you review one by one.

## Privacy and security

No server. No account. No telemetry. Audio is transcribed on your machine. The analysis pass sends transcript text to your chosen AI provider — or stays entirely offline with Ollama. API keys are stored in your OS keychain. Never in plaintext.

Two layers of identity. Speaker codes are the anonymisation boundary. Display names help your team. Exports use codes only.

PII redaction is there if you need it. Names, phone numbers, email addresses, ID numbers. An audit trail lists every redaction. Location names are excluded — they carry research context.
