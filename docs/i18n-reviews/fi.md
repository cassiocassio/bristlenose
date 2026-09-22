# Bristlenose — Finnish wording check

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

**Context you should have: nobody has ever reviewed the Finnish.** It was machine-seeded and is one of nine locales shipping that way, so this is the first native read rather than a confirmation pass.

## The five new strings

```
Ladataan signaaleja…
Ei vielä signaaleja. Suorita analyysi tai lisää koodikirjatunnisteita tuottaaksesi signaaleja.
Tunnistesignaalien virhe: {{error}}
Signaalit ovat tilastollisesti merkittäviä tunnesävyjen keskittymiä raportin osioissa. Vahvat ja kohtalaiset signaalit korostavat, missä osallistujakokemus keskittyy.
Signaalit ovat tilastollisesti merkittäviä tunnesävyjen tai koodikirjatunnisteiden keskittymiä raportin osioissa. Kahdenlaisia signaalikortteja.
```

## Where I'd value your steer

### Uninstall and Delete are the same word  ·  fi `Poista` ×3

Three rows sit in one open menu: uninstalling a codebook, deleting a code, and
deleting a code group. English distinguishes them **in the verb** — Uninstall is
reversible, Delete is not, and the Library can reinstall what you uninstalled.
In your language all three currently read fi `Poista` ×3, so nothing signals that one
of them is recoverable and two are permanent.

The objects differ, so the rows are tellable apart. The question is whether that
is enough, or whether the uninstall row should carry a longer, unambiguous form.

**Please don't feel you have to reach for a dictionary word.** We measured the
obvious candidates against Apple's own system strings and they appear **zero
times** — `Afinstaller`, `Deïnstalleer`, `Poista asennus`, `Деинсталлировать`, `설치 제거` — while the verb you
already have is exactly what Apple ships for Uninstall. So the seeded word is
right *and* the collision is real, at the same time. Danish and Korean happen to
avoid it because their delete verb differs.

One candidate, to accept or reject: `Poista koodikirjan asennus`.

### «Signaalit ovat … keskittymiä»  ·  the copula is mine
- **What we use now:** «Signaalit ovat tilastollisesti merkittäviä tunnesävyjen
  keskittymiä raportin osioissa.»
- **The nuance:** I kept your existing clause exactly, including its partitive
  plural, and put *ovat* in front. I believe a plural indefinite predicate after
  *olla* takes the partitive, which is what this is — but the whole sentence is
  mine as a construction.
- **You:** does it read as a definition? Would the singular («Signaali on…») be
  better?

### «Suorita analyysi» in the empty state  ·  the awkward one
- The empty state tells you to *Suorita analyysi* — run the analysis — in order
  to get **signals**. That is consistent with the rest of the file, which calls
  the pipeline *analyysi* (*Aloita analyysi*, *Analyysi valmistui*), and I
  deliberately left it. But the lens used to be **called** Analysis and is now
  called Signals, so the sentence now reads a little oddly in a way it did not
  before.
- **You:** leave it (the pipeline genuinely is *analyysi*), or reword?

### «Tunnistesignaalien virhe»  ·  quick check
- Finnish compounding lets this avoid the genitive chain that Czech, Polish,
  Russian and Ukrainian all ended up with, which is why I like it. English is
  singular (*Tag signal error*); the compound is plural.
- **You:** confirm?

## Quick confirms — all first-draft

- **Intensity tooltip** — «Keskimääräinen tunnevoimakkuus (1–3)». The range said 0–3 in every language
  including English, and the scale has always been 1–3; one digit, corrected
  everywhere.
- **The lens name is unchanged** and glossary-anchored. This round is about the
  sentences around it.
- **A *Signals view* phrasing existed for a few hours and is gone.** Before the
  definition-first rewrite these sentences named the lens with your language's
  own word for a *view*. No string does now. If a future one needs it, the
  glossary says: use the platform's **View** noun, never the optical word —
  Apple ships *Lens* as the camera part in all 21 of our languages.
