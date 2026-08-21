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

---

# Round two — the Codebooks lens (21 Aug 2026)

Since the brief above, a sweep found that a batch of English wording changed in
July and the Italian never followed: the Codebooks lens had been renaming things
for five weeks — *Browse* became *Library*, *Import* became **Install**, *Remove*
became **Uninstall**, and one button that said "AutoCode quotes" now just says
**Apply** — while the Italian kept the July words. One button was labelled
*Applica* in English and *"✦ AutoCode citazioni"* in Italian, which is not a
wording nuance; it's two different actions.

That's fixed, but **everything below is a first draft I wrote, not a
translation anyone has checked** — so this round is less "confirm my hunch" and
more "tell me what's wrong". Where Apple ships a word, I measured it out of the
macOS system files rather than guessing; where I had to invent, I've said so.

## The one I'd fix first

### Three words for one shelf  ·  I think this is genuinely broken
The Codebooks lens now shows all three of these, close together:

| Where | English | Italian |
|---|---|---|
| Sidebar group header | Library | **Libreria** |
| Modal title | Codebook Library | **Libreria dei libri dei codici** |
| Picker section title | Codebook frameworks | **Framework dei libri dei codici** |

- **The nuance:** the English is doing something specific — *Library* is the
  shelf, *frameworks* are the published ones (Braun & Clarke etc.) as against
  ones you built. The Italian renders that as one long compound plus an English
  loanword, and *Libreria dei libri dei codici* is a mouthful nobody would say.
- **My hunch:** none — I don't have one, which is why it's first. The literal
  route produced something clumsy, and picking a freer one is exactly the call
  I shouldn't make alone.
- **You:** what would you actually call this shelf in an Italian research tool?
  And is *framework* the right loanword here, or does Italian UR practice have
  a word for a published, citable coding scheme?

## Where I'd value your steer

### "Default" left in English  ·  measured, but it looks wrong
- **What we use now:** **Default** — the sidebar header over the codebooks that
  ship with Bristlenose (it replaced "Integrati")
- **The nuance:** I nearly wrote *Predefiniti*. Then I counted: across the macOS
  system strings Apple ships **"Default" 239 times in Italian** against 22 for
  *"Di default"*. Italian is the **only** one of our twenty locales where Apple
  keeps the English word — Spanish gets *Por omisión*, French *Par défaut*,
  German *Standard*.
- **My hunch:** follow Apple, because a label that reads differently from every
  other label on the user's own Mac is the defect. But this is a header on a
  *content* shelf, not a system setting, and that may not transfer.
- **You:** does **Default** read as native macOS Italian here, or does a
  research tool want *Predefiniti*?

### Install / Uninstall for a codebook  ·  register question
- **What we use now:** **Installa** / **Disinstalla** / **Applica**, and
  *"reinstallalo quando vuoi dalla Libreria…"*
- **The nuance:** these are Apple's Italian imperatives (measured), so the words
  are right *for software*. The question is whether software-install vocabulary
  is right for **a coding scheme** — the English made this move in July and the
  Italian is now following it faithfully. Faithful to a possibly-odd source.
- **You:** does *installare un libro dei codici* land, or does Italian want
  something closer to *aggiungere* / *importare* even though the English says
  Install?

### The folded-codebook meta line  ·  agreement problem
- **What we use now:** `{{count}} tag · {{coded}} codificate` — e.g.
  **"12 tag · 47 codificate"**
- **The nuance:** *codificate* is feminine plural, agreeing with the implied
  *citazioni* — but the noun actually on screen next to it is *tag*, masculine.
  In English the ellipsis is invisible ("47 coded"); in Italian the reader may
  reach for the wrong antecedent.
- **My hunch:** spell out the noun — *"47 citazioni codificate"* — even though
  it's longer than the English.
- **You:** does the elided form read cleanly, or does it need the noun?

### The File menu is not called Archivio here  ·  a real inconsistency
- **What we use now:** *"Scegli **Archivio ▸ Importa** per iniziare."*
- **The nuance:** *Archivio* is correct — it is what macOS calls the File menu
  in Italian. But Bristlenose's language is **its own preference**, separate from
  the system language, and the File menu is drawn by macOS. So on an
  English-language Mac with Bristlenose set to Italian, this sentence points at
  a menu that says **File**. On an Italian Mac it's right.
- **My hunch:** it's the correct word and a rare mismatch, so leave it — but I
  may be wrong about how often Italian researchers run an English macOS.
- **You:** worth naming the menu at all, or should the sentence describe the
  action without the menu path?

### Quote marks  ·  measured, sanity-check me
- **What we use now:** `Disinstallare “{{label}}”?` — curly double quotes
- **The nuance:** I first wrote «…», then counted: Apple ships **“…” 39,356
  times in Italian** and «…» **nine** times. So the app now uses “…”, against
  what the Italian press register would suggest.
- **You:** is “…” what an Italian macOS dialog should use, or does the caporale
  belong here after all?

## Quick confirms — all first-draft, none reviewed

New wording on existing surfaces:

- **Codebooks (the lens) → «Libri dei codici»** — pluralised; the earlier brief
  had this settled as the singular *libro dei codici*, which is still the term
  for one
- **Manual tags → «Tag manuali»** (was *I tuoi tag*)
- **Needs a home → «Cerca una collocazione»** — the heading over quotes in no
  section or theme, with the paragraph under it: *"{{count}} citazioni che hai
  conservato al momento non sono in nessuna sezione né tema — ma sono al sicuro
  qui, non è andato perso nulla."* Reassurance is the whole job of that sentence
- **New (the badge on new material) → «Nuovo»**, tooltip *«Fai clic per
  ignorare»* — *ignorare* comes from our existing *Ignora* for Dismiss; if
  "ignore" is the wrong verb for making a badge go away, it's wrong in both
  places
- **Picture in Picture → left in English**, because Apple Italian does too
  (measured, unanimous)
- **Settings… → «Impostazioni…»** — the App-menu item, previously hardcoded English

Whole surfaces that were **missing from Italian entirely** and are now first
drafts:

- **The server status page** — 11 strings, absent from `it` while all the other
  locales had them. *"Qui non c'è ancora niente." · "L'ultima esecuzione è stata
  annullata." · "Riesegui quando vuoi." · "L'ultima esecuzione non è riuscita." ·
  "Log recente:" · "La CLI è terminata con codice {code}"*
- **The individual-files state** — *"Bristlenose analizza cartelle"* / *"Questo
  progetto è stato creato da file singoli, quindi non può essere analizzato."*
  (Should the first be *«analizza le cartelle»*? I left the article out to match
  the English's bareness and I'm not sure that transfers.)
- **The analysing animation setting** — *"Mostra l'animazione durante l'analisi"*
  and its longer help line about *parole in stormo*
- **Empty import window** — *"Non c'è ancora nulla da importare"*
- **Name placeholders** — *«Nome della cartella»*, *«Nome del progetto»*

## Still open from round one

The four toss-ups above are unanswered and unchanged: **PII masking**
(*oscuramento* vs *rimozione*), **Star** (*contrassegnare* vs *con stella*),
**Speaker** (*interlocutore* vs *parlante*), **Friction** (*attrito* vs
*frizione*), plus the sentiment-tag question (*tag di sentiment* vs *etichette
di sentiment*). Those are still the highest-value ones — they touch far more
strings than anything in round two.
