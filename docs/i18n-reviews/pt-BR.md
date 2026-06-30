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
