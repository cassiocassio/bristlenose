# Bristlenose — Catalan wording check

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

**Context: the Catalan is glossary-first but unreviewed.** The term table was
built from Apple's shipped Catalan, the Microsoft style guide and
Softcatalà/TERMCAT, and you are the first native reader of either the glossary
or the strings.

## The five new strings

```
S'estan carregant els senyals…
Encara no hi ha senyals. Executa el processament o aplica etiquetes del llibre de codis per generar-ne.
Error dels senyals d'etiquetes: {{error}}
Els senyals són concentracions de sentiment estadísticament notables dins de les seccions de l'informe. Els senyals forts i moderats indiquen on s'agrupa l'experiència dels participants.
Els senyals són concentracions estadísticament notables de sentiment o d'etiquetes del llibre de codis dins de les seccions de l'informe. Hi ha dos tipus de targeta de senyal.
```

## Where I'd value your steer

### «Els senyals són …»  ·  the copula is mine
- Plural with the article, so your existing clause survived verbatim. A
  definition might prefer «Un senyal és una concentració…».
- **You:** plural, or singular?

### «Executa el processament»  ·  I think this may be wrong
- The empty state says *el processament* for the pipeline. Everywhere else the
  Catalan calls it **l'anàlisi** (*emptyState.prePipeline*,
  *emptyState.postZeroQuotes*, *announce.pipelineCompleted*) — and
  *processament* appears in this same file only inside *processament del
  llenguatge natural* (NLP), which is a different sense of the word.
- **The nuance:** it predates this round, so I left it rather than sweeping. But
  it is a one-off against thirty siblings.
- **You:** should this be *l'anàlisi*?

### «Error dels senyals d'etiquetes»  ·  heavier than Catalan UI usually goes
- **Also in play:** «Error del senyal d'etiquetes» (singular), «Error en els
  senyals d'etiquetes»
- **The nuance:** the definite plural article in an error label is weighty.
  English is singular; I went plural as fourteen locales did.
- **You:** which of the three?

### «per generar-ne»  ·  confirm
- The partitive was already here and it is the reason Catalan needed **no** fix
  where thirteen other locales did: *-ne* refers to the established topic and
  cannot reach *etiquetes*. Spanish, which has no partitive, had to name the
  noun and now repeats it.
- **You:** confirm *-ne* reads naturally here.

## Quick confirms — all first-draft

- **Intensity tooltip** — «Intensitat emocional mitjana (1–3)». The range said 0–3 in every language
  including English, and the scale has always been 1–3; one digit, corrected
  everywhere.
- **The lens name is unchanged** and glossary-anchored. This round is about the
  sentences around it.
- **A *Signals view* phrasing existed for a few hours and is gone.** Before the
  definition-first rewrite these sentences named the lens with your language's
  own word for a *view*. No string does now. If a future one needs it, the
  glossary says: use the platform's **View** noun, never the optical word —
  Apple ships *Lens* as the camera part in all 21 of our languages.
