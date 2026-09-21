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


---

# Round three — the Signals lens (21 Sep 2026)

Bristlenose turns a folder of user-interview recordings into a browsable report
— quotes, themes, sentiment. One of its five lenses was called **Analysis** and
is now called **Signals**, and that rename left five sentences describing the
old name in every language but English. They are fixed, and **everything below
is a first draft I wrote, not a translation anyone has checked.**

Two of the five are worth knowing the history of, because the English moved
twice in one day:

- **The definition came back.** Before the rename the sentence read *"the
  analysis page surfaces signals — statistically notable concentrations of
  sentiment within report sections"*, and that dash was the only place the
  product said **what a signal is**. The rename dropped it, so the next
  sentence talked about *strong and moderate signals* without the term ever
  being introduced. The English is now definition-first: *"Signals are
  statistically notable concentrations of sentiment within report sections."*
- **A pronoun was pointing at the wrong noun.** The empty state said *"apply
  codebook tags to generate **them**"* — and in thirteen languages the nearest
  candidate for *them* was **the tags**, which invites *apply tags to generate
  tags*. Your language was one of the five where the pronoun form matched the
  tags noun *exactly*, so the wrong reading was the easier one. It now names
  the noun.

Where your language's own earlier wording already carried the definition, I
reused it verbatim rather than re-translating — so the clause in the middle of
those sentences is the one a predecessor already wrote. The copula and the
subject at the front are mine, and they are what I would most like checked.

## The five new strings

```
Signale werden geladen…
Noch keine Signale. Führen Sie die Pipeline aus oder wenden Sie Codebuch-Tags an, um Signale zu generieren.
Fehler bei Tag-Signalen: {{error}}
Signale sind statistisch auffällige Konzentrationen von Stimmungen innerhalb der Berichtsabschnitte. Starke und moderate Signale heben hervor, wo sich die Erfahrungen der Teilnehmer bündeln.
Signale sind statistisch auffällige Konzentrationen von Stimmung oder Codebuch-Tags innerhalb der Berichtsabschnitte. Zwei Arten von Signalkarten.
```

## Where I'd value your steer

### «Signale sind …»  ·  the copula is mine
- **What we use now:** «Signale sind statistisch auffällige Konzentrationen von
  Stimmungen innerhalb der Berichtsabschnitte.»
- **The nuance:** plural, so your existing clause survived verbatim. A German
  definition might prefer «Ein Signal ist eine statistisch auffällige
  Konzentration…».
- **You:** plural, or singular for the definition?

### «von Stimmungen» vs «von Stimmung»  ·  pre-existing inconsistency
- The two help sentences disagree: the guide says **Stimmungen** (plural), the
  Signals section says **Stimmung** (singular). Both predate this round — I left
  each as it was rather than picking — but they are two renderings of one English
  word (*sentiment*) sitting on the same lens.
- **You:** which one, for both?

### «Fehler bei Tag-Signalen»  ·  sanity-check me
- **Also in play:** «Tag-Signal-Fehler» (compound), «Fehler bei der Berechnung
  der Tag-Signale»
- **The nuance:** English is singular (*Tag signal error*); I went plural, as
  fourteen locales did. *bei* + dative avoids a genitive stack, which is why I
  chose it over the compound.
- **You:** *bei*-phrase, or the compound?

## Quick confirms — all first-draft

- **Intensity tooltip** — «Mittlere emotionale Intensität (1–3)». The range said 0–3 in every language
  including English, and the scale has always been 1–3; one digit, corrected
  everywhere.
- **The lens name is unchanged** and glossary-anchored. This round is about the
  sentences around it.
- **A *Signals view* phrasing existed for a few hours and is gone.** Before the
  definition-first rewrite these sentences named the lens with your language's
  own word for a *view*. No string does now. If a future one needs it, the
  glossary says: use the platform's **View** noun, never the optical word —
  Apple ships *Lens* as the camera part in all 21 of our languages.
