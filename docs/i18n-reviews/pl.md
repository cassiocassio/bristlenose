# Bristlenose — Polish wording check

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

**Context you should have: nobody has ever reviewed the Polish.** It was machine-seeded and is one of nine locales shipping that way, so this is the first native read rather than a confirmation pass.

## The five new strings

```
Wczytywanie sygnałów…
Nie ma jeszcze sygnałów. Uruchom potok lub zastosuj tagi z księgi kodów, aby wygenerować sygnały.
Błąd sygnałów tagów: {{error}}
Sygnały to statystycznie znaczące skupiska sentymentu w sekcjach raportu. Silne i umiarkowane sygnały wskazują, gdzie koncentrują się doświadczenia uczestników.
Sygnały to statystycznie znaczące skupiska sentymentu lub tagów z księgi kodów w sekcjach raportu. Dwa typy kart sygnałów.
```

## Where I'd value your steer

### «Sygnały to …»  ·  the definition idiom is mine
- **What we use now:** «Sygnały to statystycznie znaczące skupiska sentymentu w
  sekcjach raportu.»
- **Also in play:** «Sygnały są statystycznie znaczącymi skupiskami…»
  (instrumental), or the singular «Sygnał to…»
- **The nuance:** I chose *to* because it is the ordinary Polish shape for
  defining a term and it keeps the predicate in the nominative, which let me
  reuse the existing clause unchanged. *są* + instrumental is more formal.
- **You:** *to*, *są* + instrumental, or singular?

### «Błąd sygnałów tagów»  ·  I think this is clumsy
- Three nouns in a genitive chain. The previous wording had the same shape with
  *analizy*, so it is not new — but it was already awkward. Alternatives: «Błąd
  podczas przetwarzania sygnałów tagów», «Błąd obliczania sygnałów tagów».
  English is singular; I went plural as fourteen locales did.
- **You:** break the chain, and is plural right?

### A verb I changed and then removed  ·  context only
- For a few hours the sentence read «Widok „Sygnały" **wydobywa** …», which a
  review flagged: *wydobywać* is *to extract / mine out*, and a view does not
  extract clusters — it shows them. I changed it to *pokazuje*, and then the
  definition-first rewrite removed the whole construction. Nothing depends on it
  now; noting it because if a future string describes a lens doing something,
  *wydobywać* is the wrong verb.

### One thing I did **not** change  ·  and would like your view
- The empty state says **«Uruchom potok»** for the pipeline. *potok* is in the
  file already and I left it. If a Polish researcher would expect the English
  loanword *pipeline*, say so — Spanish had exactly this problem in reverse
  (*Tubería* was wrong and became *Pipeline*).

## Quick confirms — all first-draft

- **Intensity tooltip** — «Średnie natężenie emocjonalne (1–3)». The range said 0–3 in every language
  including English, and the scale has always been 1–3; one digit, corrected
  everywhere.
- **The lens name is unchanged** and glossary-anchored. This round is about the
  sentences around it.
- **A *Signals view* phrasing existed for a few hours and is gone.** Before the
  definition-first rewrite these sentences named the lens with your language's
  own word for a *view*. No string does now. If a future one needs it, the
  glossary says: use the platform's **View** noun, never the optical word —
  Apple ships *Lens* as the camera part in all 21 of our languages.
