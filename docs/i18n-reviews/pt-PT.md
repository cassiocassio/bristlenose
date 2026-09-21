# Bristlenose — European Portuguese wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. Before I lock the European Portuguese terms, I'd value your steer on a handful where I'm genuinely unsure (and a quick sanity check on the rest). Should take five minutes.

## Where I'd really value your steer

### "Star" the quote  ·  genuine toss-up
- **What we use now:** the buttons, menus, shortcuts and desktop all say **estrela** — *Marcar com estrela* / *Com estrela*.
- **Also in play:** the screen-reader announcements, the CSV column header and the clips text say **destacar / destaque / destacada** (e.g. column *Destacada*).
- **The nuance:** it's one feature wearing two metaphors — press a button labelled *Marcar com estrela*, the screen reader says *Citação destacada*, and the exported CSV column is *Destacada*. Three names for one action.
- **My hunch:** standardise on the literal star everywhere — verb *Marcar com estrela*, state *Com estrela*, CSV column *Com estrela* — and keep *destacar* only as free prose ("destacar descobertas"). The star metaphor is the one users actually see on the control; *destaque* also risks colliding with "featured".
- **You:** happy to fix the whole feature on **estrela / Com estrela**, or would you rather *destacada* won as the single term?

### "Tags"  ·  genuine toss-up
- **What we use now:** **Etiqueta(s)**, consistently.
- **Also in play:** **Identificadores** (what Apple's pt-PT Finder calls Tags), or the loanword **Tag**.
- **The nuance:** this is the register clash — Apple PT-PT uses *Identificadores* (and *Etiquetas* is the Brazilian Finder term), but the QDA/UX register in Portugal genuinely says *etiqueta / etiquetagem*. So *Etiqueta* looks like a Brazilian borrow on the Apple axis but is the right word on the research axis.
- **My hunch:** keep **Etiqueta** — researchers are the audience and it's the QDA-register term; *Identificador* would read oddly to them. (One knock-on: we already use *rótulos* for "labels" in the anonymise export, so I'd tidy that to avoid two near-synonyms.)
- **You:** for a researcher coding quotes, does *Etiqueta* read native — or does the macOS *Identificador* pull strongly enough that we should match the platform?

### PII redaction  ·  clear-cut, just confirm
- **What we use now:** **remoção de PII / remover** (headings, the pipeline stage, settings).
- **Also in play:** **redação / redigido** (slips into the web privacy prose) and **ocultação / ocultar** (desktop-only fork).
- **The nuance:** *redação* is arguably the most technically-correct term but clashes with the everyday "essay" sense; *ocultar* already means "hide a quote" elsewhere in the app, so reusing it for PII risks overload.
- **My hunch:** standardise on **remoção / remover** for the feature name and sweep the stray *redação* / *ocultação* out of the prose.
- **You:** any objection to *remoção* as the single term — or is *redação* the one a Portuguese researcher would expect?

## Quick confirms (I think these are settled — just shout if not)

- **Participant → Participante** — the UXPM Portugal / qualitative-research term; *utilizador* stays reserved for the product's end-user sense.
- **Speaker → Interveniente** — the scielo.pt transcription norm for voices in an interview (we rejected *orador* and *falante*).
- **Theme → Tema** — the Braun & Clarke noun; *temática* stays as the adjective only ("análise temática").
- **Friction → Atrito** — the lead term in PT UX writing; *fricção* is an acceptable but secondary synonym.
- **Framework → Framework** (loanword) — kept untranslated in the prose and desktop menus, as is common in PT tech writing; two codebook labels still say *Estrutura*, which I'll align unless you'd rather the codebook keep *Estrutura*.

## Anything I've got wrong?

If any of the "settled" terms feels off, or if there's a concept we render awkwardly in European Portuguese, flag it — your call wins over mine on all of these.


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
A carregar sinais…
Ainda não há sinais. Execute o pipeline ou aplique etiquetas do livro de códigos para os gerar.
Erro nos sinais de etiqueta: {{error}}
Sinais são concentrações estatisticamente notáveis de sentimento dentro das secções do relatório. Sinais fortes e moderados destacam onde a experiência do participante se concentra.
Sinais são concentrações estatisticamente notáveis de sentimento ou etiquetas do livro de códigos dentro das secções do relatório. Dois tipos de cartão de sinal.
```

## Where I'd value your steer

### «Sinais são …» without an article  ·  I think this may be wrong
- **What we use now:** «Sinais são concentrações estatisticamente notáveis de
  sentimento…»
- **The nuance:** I left the subject bare to match the English. Every other
  Romance locale uses the definite article — Italian «**I** segnali sono»,
  Spanish «**Las** señales son», French «**Les** signaux sont», Catalan «**Els**
  senyals són».
- **My hunch:** it should be «**Os** sinais são…».
- **You:** article or no article?

### «para os gerar»  ·  no change needed, but here is why
- European Portuguese was one of only three locales needing **no** fix to the
  pronoun described at the top — *os* is masculine, *etiquetas* feminine. The
  pre-verbal clitic placement is yours, not mine, and I kept it rather than
  importing the Brazilian *gerá-los*.
- **You:** confirm.

### The no-cross-borrow rule held  ·  for information
- Everything here is European: *A carregar* (not *Carregando*), *secções* (not
  *seções*), *para os gerar* (not *gerá-los*), *vista*. Nothing was copied from
  pt-BR, which is the standing rule for this pair.
- **You:** shout if any of it reads as Brazilian anyway.

## Quick confirms — all first-draft

- **Intensity tooltip** — «Intensidade emocional média (1–3)». The range said 0–3 in every language
  including English; the scale has always been 1–3.
- **The lens name is unchanged** and glossary-anchored.
- **A *Signals view* phrasing existed for a few hours and is gone.** If a future
  string has to name a lens, the glossary says: the platform's **View** noun,
  never the optical word — Apple ships *Lens* as the camera part in all 21 of
  our languages.
