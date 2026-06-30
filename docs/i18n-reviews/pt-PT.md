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
