# Bristlenose — Norwegian Bokmål wording check

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

**Context you should have: nobody has ever reviewed the Norwegian Bokmål.** It was machine-seeded and is one of nine locales shipping that way, so this is the first native read rather than a confirmation pass.

## The five new strings

```
Laster inn signaler …
Ingen signaler ennå. Kjør pipelinen eller bruk kodebok-tagger for å generere signaler.
Feil i tagg-signaler: {{error}}
Signaler er statistisk bemerkelsesverdige konsentrasjoner av sentiment innenfor rapportseksjonene. Sterke og moderate signaler viser hvor deltakeropplevelsen klumper seg sammen.
Signaler er statistisk bemerkelsesverdige konsentrasjoner av sentiment eller kodebok-tagger innenfor rapportseksjonene. To typer signalkort.
```

## Where I'd value your steer

### The copula sentence is mine  ·  low risk, but unread
- The definition sentence puts **er** in front of your existing clause, which
  survived from the earlier wording word for word. The construction is the only
  new thing.
- **You:** does it read as a definition, or would the singular be better?

### The compound nouns  ·  the thing I would check first
- **kodebok-tagger / tagg-signaler** — these compound freely in your language, which is why this locale
  avoided the three-noun genitive chain that Czech, Polish, Russian and
  Ukrainian all ended up with. But a long compound can still read badly.
- **You:** are these the compounds you would write?

### Number, where English is singular  ·  quick check
- English says *Tag signal error*, singular; this locale went plural, as
  fourteen did.
- **You:** confirm?

### The empty state now names the noun  ·  context
- It used to end with a pronoun (*dem* / *ze*) whose nearest candidate was the
  tags, as described at the top. It now names signals outright, which is a
  little more repetitive and a lot less ambiguous.
- **You:** confirm, or would you restructure?

## Quick confirms — all first-draft

- **Intensity tooltip** — «Gjennomsnittlig følelsesmessig intensitet (1–3)». The range said 0–3 in every language
  including English; the scale has always been 1–3.
- **The lens name is unchanged** and glossary-anchored.
- **A *Signals view* phrasing existed for a few hours and is gone.** If a future
  string has to name a lens, the glossary says: the platform's **View** noun,
  never the optical word — Apple ships *Lens* as the camera part in all 21 of
  our languages.
