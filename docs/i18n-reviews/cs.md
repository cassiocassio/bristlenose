# Bristlenose — Czech wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. I've translated the Czech UI and want your steer on a handful of terms before I lock them in. Should take you five minutes — most of it is just nodding along.

## Where I'd really value your steer

### Quote (citát vs citace)  ·  clear-cut, just confirm
- **What we use now:** **citát** everywhere it matters — nav, dashboard, export columns, help text (~88 places)
- **Also in play:** **citace** has crept into about 17 strings (the Miro panel, the desktop quotes menu, Settings, and oddly two stray actions sitting right next to *citát* — "Skrýt tuto citaci", "Označit tuto citaci hvězdičkou")
- **The nuance:** to my ear *citát* is a quoted utterance (what we want — a participant's words), whereas *citace* drifts toward a bibliographic reference.
- **My hunch:** normalise everything to **citát** and kill the *citace* strays. The English source is a single word ("Quote") throughout, so the split is just my inconsistency, not a real distinction.
- **You:** any context where *citace* is actually the better word, or is *citát* right across the board?

### Tags (štítky vs značky)  ·  genuine toss-up
- **What we use now:** **štítky** (consistently)
- **Also in play:** **značky** (Apple's primary term) and the loanword **tagy**
- **The nuance:** Apple's macOS Czech uses **značky** as the primary Finder/Mail Tags term, with *štítky* only noted as a synonym — but *značky* can also read as colour-marks/flags, where *štítky* is unambiguously labels.
- **My hunch:** lean to keeping **štítky** for clarity, but this is your Mac-idiom call — if a Czech Mac user expects *značky*, HIG alignment wins.
- **You:** for a native Mac app, does *štítky* read fine, or does the Finder convention pull you to *značky*?

### Friction (tření)  ·  genuine toss-up
- **What we use now:** **tření**, only in two sentiment descriptions (never as a label)
- **Also in play:** **obtíže** / **překážky** (difficulties/obstacles), or the loan **frikce**
- **The nuance:** *tření* is literally physical friction; the Norman/Nielsen UX metaphor doesn't seem conventionalised in Czech UX writing, so it may land oddly on a practitioner's ear.
- **My hunch:** I'd probably swap to **obtíže** for the everyday sense — but I have low confidence here and would rather defer to you.
- **You:** does *tření* carry the interaction-difficulty metaphor naturally, or would *obtíže*/*překážky* read better?

### Participant (účastník vs respondent)  ·  clear-cut, just confirm
- **What we use now:** **účastník** everywhere
- **Also in play:** **respondent** (common in industry UX writing)
- **The nuance:** *účastník* is the ethics-aware academic-UR term; *respondent* is what a lot of Czech practitioners actually say day-to-day.
- **My hunch:** stay with **účastník** — respectful, modern, and a clean match to the source.
- **You:** does your audience expect *respondent*, or is *účastník* safe? And do the plurals read right in counts (*účastníci* / gen. pl. *účastníků*)?

## Quick confirms (I think these are settled — just shout if not)

- **Speaker → mluvčí** — matches Azure Speech and the Czech transcription-tool convention; *řečník* would be wrong register.
- **Theme → téma** — the canonical Czech Braun & Clarke rendering (*tematická analýza* → *téma*).
- **Tag (singular) → štítek** — same lemma as above, pending the *štítky/značky* call.
- **Codebook → kniha kódů**, **Code → kód** — consistent throughout.
- **Star → hvězdička**, **Signal → signál**, **Framework → rámec** — single, consistent terms.

## Anything I've got wrong?

If any term feels off, or a concept reads awkwardly in Czech that I haven't even flagged, please call it out — your ear beats my glossary every time, so your call wins.
