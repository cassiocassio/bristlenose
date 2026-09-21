# Bristlenose — Brazilian Portuguese wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. I've drafted the Brazilian Portuguese wording and want your steer on a handful of terms before they're locked. Should take five minutes — most of it is just confirming I haven't gone wrong.

## Where I'd really value your steer

### Friction (the "friction point" concept)  ·  genuine toss-up
- **What we use now:** atrito (in the frustration definition and the "gap" pattern)
- **Also in play:** fricção / ponto de fricção
- **The nuance:** Brazilian UX writing uses both, often in the same article — *fricção* leans to the Nielsen-Norman term-of-art, *atrito* reads more naturally Brazilian.
- **My hunch:** I'd keep **atrito** as the default — it reads less like a calque and our audience is researchers, not the dev-UX crowd — but make both definition sentences agree on it.
- **You:** For a researcher audience, is *atrito* the natural default, or does *fricção* carry more weight as the recognised UX term?

### Star (marking a quote)  ·  clear-cut, just confirm the direction
- **What we use now:** the action says marcar com estrela / estrela; the resulting state is announced as citação destacada and the column header is Destacada
- **Also in play:** unifying on the estrela family throughout
- **The nuance:** English uses one root the whole way (Star / Starred); we've split it into *estrela* (the literal star) versus *destaque* (highlight), which collides with a separate "featured" concept we also call em destaque.
- **My hunch:** Normalise to the **estrela** family everywhere the star control is meant; keep *destaque* only where we genuinely mean "highlight/featured".
- **You:** Does *citação com estrela* read cleanly as the state label, or is *destacada* actually the more natural Brazilian phrasing — in which case I'd flip the action to match instead?

### Framework (codebook framework)  ·  genuine toss-up
- **What we use now:** the loanword framework in prose and the tag sidebar; Estrutura in the codebook chrome
- **Also in play:** picking one — framework or estrutura — for both
- **The nuance:** *framework* is the everyday loanword in Brazilian UX/dev register; *estrutura* is cleaner Portuguese but collides with a layer we already call *Estrutura* (= Structure) elsewhere in the report.
- **My hunch:** Standardise on the loanword **framework** — it's the live register and it dodges the *Estrutura*-means-two-things clash.
- **You:** In a research tool's UI, does *framework* read as normal, or would you expect the translated *estrutura* despite the collision?

### PII redaction  ·  clear-cut, just confirm
- **What we use now:** Remoção de PII on web/CLI/settings; the desktop app forks to ocultação de PII; the audit prose uses redação/redigida
- **Also in play:** ocultação, censura de PII
- **The nuance:** Strictly, redaction = blacking-out, so *remoção* (removal) is a slight stretch — but it's our established dominant and matches our CLI wording.
- **My hunch:** Align everything to the dominant **remoção de PII** and drop the desktop *ocultação* — one word across all surfaces.
- **You:** Is *remoção* fine here, or does the blacking-out sense make *ocultação* (or *censura*) the more accurate term worth standardising on instead?

## Quick confirms (I think these are settled — just shout if not)

- **Participant → Participante** — the modern Brazilian research-ethics standard (over the dated *sujeito* / narrower *entrevistado*); stays distinct from *Falante*.
- **Theme → Tema** — the Braun & Clarke *análise temática* term; *temática* stays as adjective only.
- **Tags → Etiquetas** — matches Apple's own macOS Finder translation; distinct from *rótulos* (anonymisation labels) and *marcação de tempo* (timecode).
- **Speaker → Falante** — natural for transcription; avoids *alto-falante* (loudspeaker) and the radio-announcer reading of *locutor*. (One small flag: if anything, this is the one I'd most welcome a sanity-check on — *locutor* is the formal diarization term, but I think *Falante* is right for a non-technical audience.)

## Anything I've got wrong?

If any term feels off, or there's a concept we render awkwardly that I haven't flagged, please say — your ear wins over my drafting every time.


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
Carregando sinais…
Ainda não há sinais. Execute o pipeline ou aplique etiquetas do livro de códigos para gerá-los.
Erro nos sinais de etiqueta: {{error}}
Sinais são concentrações estatisticamente notáveis de sentimento dentro das seções do relatório. Sinais fortes e moderados destacam onde a experiência do participante se concentra.
Sinais são concentrações estatisticamente notáveis de sentimento ou etiquetas do livro de códigos dentro das seções do relatório. Dois tipos de cartão de sinal.
```

## Where I'd value your steer

### «Sinais são …» without an article  ·  I think this may be wrong
- **What we use now:** «Sinais são concentrações estatisticamente notáveis de
  sentimento…»
- **The nuance:** I left the subject bare to match the English's bareness. Every
  other Romance locale in the product uses the definite article — Italian «**I**
  segnali sono», Spanish «**Las** señales son», French «**Les** signaux sont»,
  Catalan «**Els** senyals són» — and Portuguese normally takes one for a
  generic plural.
- **My hunch:** it should be «**Os** sinais são…», and the two Portuguese
  locales are the odd ones out because I transferred an English habit.
- **You:** article or no article?

### «para gerá-los»  ·  no change needed, but here is why
- Portuguese was one of only three locales that needed **no** fix to the pronoun
  described at the top: *-los* is masculine and *etiquetas* is feminine, so the
  gender alone rules out the wrong reading. Left exactly as it was.
- **You:** confirm it reads naturally.

### «Erro nos sinais de etiqueta»  ·  quick check
- English is singular (*Tag signal error*); the noun is plural here, as in
  fourteen locales. The *em*-phrase avoids stacking *de* twice.
- **You:** confirm — and is *etiqueta* right singular, or *etiquetas*?

## Quick confirms — all first-draft

- **Intensity tooltip** — «Intensidade emocional média (1–3)». The range said 0–3 in every language
  including English; the scale has always been 1–3.
- **The lens name is unchanged** and glossary-anchored.
- **A *Signals view* phrasing existed for a few hours and is gone.** If a future
  string has to name a lens, the glossary says: the platform's **View** noun,
  never the optical word — Apple ships *Lens* as the camera part in all 21 of
  our languages.
