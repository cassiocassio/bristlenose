# Bristlenose — German wording check

Bristlenose turns user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. I'm locking the German interface terms and would value your steer on a handful before they're fixed. Should take five minutes — most of it is just confirming the obvious calls.

## Where I'd really value your steer

### „Code" vs „Kode"  ·  genuine toss-up
- **What we use now:** „Code / Codes" on the web, „Kode / Kodes" in the Mac app — a real split between our two surfaces.
- **Also in play:** standardising on either spelling product-wide.
- **The nuance:** both are attested — MAXQDA uses „Code / Codierung", ATLAS.ti uses „Kode / Kodierung" — so neither is wrong, but one product shouldn't disagree with itself across its own screens.
- **My hunch:** „Code / Codes" everywhere — it pairs cleanly with „Codebuch" (already our codebook term) and „Codegruppe", and matches MAXQDA. Then fix the Mac menus to match.
- **You:** „Code" or „Kode" for the whole product?

### PII redaction — false friend to fix  ·  one clear-cut, one toss-up
- **What we use now:** „Schwärzung / schwärzen" dominates (good), but one string says „PII-Redaktion ist deaktiviert" and the pipeline backend is labelled „Integrierte Anonymisierung".
- **Also in play:** „Anonymisierung", and the stray „Redaktion".
- **The nuance:** „Redaktion" is a false friend — in German it's the editorial department, not redaction; that one's just a bug. Separately, „Schwärzung" (blacking-out spans) and „Anonymisierung" (irreversible de-identification) are arguably distinct GDPR concepts, so the mix may be deliberate.
- **My hunch:** anchor „PII-Schwärzung / schwärzen", and fix „Redaktion" → „Schwärzung" regardless. I'd keep „Anonymisierung" only for the built-in backend (which is literally named the anonymiser), not as a synonym for the redaction step.
- **You:** kill „Redaktion" — agreed? And do you want „Schwärzung" and „Anonymisierung" kept distinct, or unified?

### „Teilnehmer" — which gender form?  ·  genuine toss-up
- **What we use now:** „Teilnehmer" in the main UI, but „Teilnehmer:in" (colon form) in our role labels — and „Nutzende" / „Forschungsperson" turn up elsewhere too.
- **Also in play:** „Teilnehmende" (neutral participle), „Befragte" (the QDA/interview register), bare „Teilnehmer".
- **The nuance:** the word is fine; it's the inclusive-language convention that's applied unevenly across the locale.
- **My hunch:** pick „Teilnehmende" and apply it consistently — it's gender-neutral and sits well with the „Nutzende" forms already in the locale. If you'd rather keep it simple, bare „Teilnehmer" everywhere is the fallback. Either way, one convention product-wide.
- **You:** „Teilnehmende", „Teilnehmer:in", or bare „Teilnehmer" — and same call for „Sprecher"?

### „Friction"  ·  clear-cut, just confirm
- **What we use now:** no dedicated label yet — only bare „Reibung" inside some prose.
- **Also in play:** „Reibungspunkte", „Pain Point", English „Friction".
- **The nuance:** established German UX uses the compound „Reibungspunkte" (Nielsen/Norman lineage) for friction-as-obstacle, not bare „Reibung".
- **My hunch:** „Reibungspunkte" for any future label, and normalise the countable prose uses to match (leaving „Reibung" only where it reads as the abstract quality).
- **You:** „Reibungspunkte" — or do you keep the English „Friction" / „Pain Point" in practice?

## Quick confirms (I think these are settled — just shout if not)

- **Tags → „Tags"** — Apple keeps the English word in the German Finder and Reminders, and we already use it consistently.
- **Theme → „Thema / Themen"** — the German Braun & Clarke rendering; deliberately not „Kategorie" (which signals the Mayring/Kuckartz content-analysis tradition).
- **Speaker → „Sprecher"** — the standard term in German transcription/diarisation, kept distinct from „Teilnehmer".
- **Codebook → „Codebuch"** and **Session → „Interview"** — already consistent.

## Anything I've got wrong?

If any of these reads stiffly, or there's a concept we render awkwardly that you'd phrase differently, please flag it — and if your instinct differs from my hunch anywhere above, your call wins over mine.
