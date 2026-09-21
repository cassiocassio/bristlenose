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
Načítání signálů…
Zatím žádné signály. Spusťte zpracování nebo použijte štítky z knihy kódů, abyste signály vygenerovali.
Chyba signálů štítků: {{error}}
Signály jsou statisticky významné koncentrace nálady v rámci sekcí zprávy. Silné a střední signály zvýrazňují, kde se zkušenosti účastníků shlukují.
Signály jsou statisticky významné koncentrace nálady nebo štítků z knihy kódů v rámci sekcí zprávy. Dva typy karet signálu.
```

## Where I'd value your steer

### «Signály jsou …»  ·  the copula is mine
- **What we use now:** «Signály jsou statisticky významné koncentrace nálady…»
- **The nuance:** I kept the plural so your existing clause could be reused word
  for word; the singular («Signál je statisticky významná koncentrace…») would
  have meant re-inflecting the whole predicate. A definition sometimes wants the
  singular.
- **You:** plural, or singular for a defined term?

### «Chyba signálů štítků»  ·  I think this is clumsy
- Three nouns in a genitive chain. The previous wording had the same shape with
  *analýzy* in place of *signálů*, so it is **not new** — but it was already
  awkward. Alternatives: «Chyba při zpracování signálů štítků», «Chyba výpočtu
  signálů štítků». English is singular (*Tag signal error*); I went plural, as
  fourteen locales did.
- **You:** break the chain, and is plural right?

### «Spusťte zpracování»  ·  pre-existing, worth your view
- The empty state says *zpracování* for the pipeline, while the rest of the file
  says **analýza** (*Spustit analýzu*, *Analýza dokončena*). That predates this
  round and I deliberately did not "fix" it — but now that the lens is no longer
  called Analysis, the two words sit less comfortably together.
- **You:** should the pipeline be *analýza* here too, or is *zpracování* right
  in an empty state?

## Quick confirms — all first-draft

- **Intensity tooltip** — «Průměrná emocionální intenzita (1–3)». The range said 0–3 in every language
  including English, and the scale has always been 1–3; one digit, corrected
  everywhere.
- **The lens name is unchanged** and glossary-anchored. This round is about the
  sentences around it.
- **A *Signals view* phrasing existed for a few hours and is gone.** Before the
  definition-first rewrite these sentences named the lens with your language's
  own word for a *view*. No string does now. If a future one needs it, the
  glossary says: use the platform's **View** noun, never the optical word —
  Apple ships *Lens* as the camera part in all 21 of our languages.
