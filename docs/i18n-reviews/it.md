# Bristlenose — Italian wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment, friction points. I've drafted the Italian UI and it's mostly settled, but a handful of terms aren't locked yet and I'd value your steer before they are. Should take five minutes — the contested ones are first, the obvious ones are a quick scan at the bottom.

## Where I'd really value your steer

### PII masking (the Presidio feature)  ·  genuine toss-up
- **What we use now:** «rimozione dei dati personali» (web + CLI)
- **Also in play:** «oscuramento dei dati personali» (already used on desktop + settings)
- **The nuance:** the feature *masks* text with placeholders rather than deleting it, so «oscuramento» is the technically truer GDPR/Garante register; «rimozione» overstates it as removal — and right now the same feature carries both lemmas across surfaces.
- **My hunch:** converge on «oscuramento dei dati personali» everywhere — more accurate, and it's already what the two largest desktop surfaces say, so it's the smaller edit.
- **You:** «oscuramento» or «rimozione» as the single term — and do you agree the export action «Anonimizza / in forma anonima» stays separate, since stripping names from labels is a different operation from PII masking?

### Star (the per-quote flag action)  ·  genuine toss-up
- **What we use now:** «contrassegnare» / «contrassegnata» (web) vs «stella» / «con stella» (desktop menus)
- **Also in play:** «in evidenza» surfaces once in the clips copy
- **The nuance:** «stella» as a verb is a star-glyph calque that reads slightly awkwardly; «contrassegnare» is more natural Italian but drops the star metaphor — and Apple has no single canonical term here (Mail uses «Bandiera», Photos «Preferiti»).
- **My hunch:** «contrassegnare» everywhere — it's the more natural verb and the glyph carries the metaphor visually without needing the word.
- **You:** keep the star word («con stella») for the metaphor, or go fully verbal with «contrassegnare»?

### Speaker (who's talking in a transcript)  ·  close call
- **What we use now:** «interlocutore»
- **Also in play:** «parlante» (the standard in diarisation/ASR tooling)
- **The nuance:** «interlocutore» leans into the interview/dialogue register; «parlante» is the technical ASR term — both correctly dodge the «altoparlante» (loudspeaker) false friend.
- **My hunch:** keep «interlocutore» — these are research interviews, not raw audio jobs, so the dialogic register fits the product better.
- **You:** does «interlocutore» read right for an interview, or would a researcher expect «parlante»?

### Friction (UX sense — effort/resistance)  ·  close call
- **What we use now:** «attrito»
- **Also in play:** «frizione»
- **The nuance:** «attrito» is the more common resistance metaphor in Italian UX writing; «frizione» appears but feels more mechanical — and I couldn't find a settled NN/g Italian rendering to defer to. (Separate from «punti critici» = pain points, which is a distinct concept I'm keeping apart.)
- **My hunch:** «attrito» — it's already in place for the frustration sentiment and reads as the resistance metaphor.
- **You:** «attrito», or is there a consolidated term you'd reach for first?

## Quick confirms (I think these are settled — just shout if not)
- **Participant → «partecipante»** — standard in Italian UR practice; not «soggetto»/«intervistato»
- **Theme → «tema» / «temi»** — the Braun & Clarke «analisi tematica» term, kept distinct from «argomento» (topic)
- **Tag (the UI noun) → «tag»** — matches Apple's Finder, which keeps «Tag» for UI controls (one open question below)
- **Quote → «citazione»**, **Session → «sessione»**, **Code → «codice»**, **Codebook → «libro dei codici»**, **Signal → «segnale»** — all already consistent

One small Tag follow-up: the noun «tag» is solid, but sentiment tags currently read «etichette di sentiment». Align to «tag di sentiment» for consistency, or keep «etichetta» as a deliberate distinction?

## Anything I've got wrong?
If any term reads stiffly, off-register, or just isn't what a working Italian researcher would say, flag it — including ones I've parked as "settled". Your call wins over mine on all of these.
