# Bristlenose — Spanish wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment and friction points pulled out automatically. I've drafted the Spanish wording and want your steer on a handful of terms before they're locked in. Should take five minutes — most of it is just nodding through the obvious ones.

## Where I'd really value your steer

### "PII redaction" (the privacy/anonymisation step)  ·  clear-cut, just confirm
- **What we use now:** mixed — the prose says **"Eliminación de datos personales"** but one settings label says **"Redacción de PII"**.
- **Also in play:** **"Eliminación de PII"**, **"Anonimización"**.
- **The nuance:** false friend — *redactar* means *to write/word a text*, so "Redacción de PII" reads as *writing up the PII*, the opposite of blanking it out.
- **My hunch:** Kill "Redacción de PII". Align that label to **"Eliminación de datos personales"** (or "Eliminación de PII") to match the prose.
- **You:** Happy with "Eliminación de datos personales" as the single term, and dropping *redacción* entirely?

### "Framework" in the codebook (a coding scheme like Garrett or Norman)  ·  genuine toss-up
- **What we use now:** mixed — the loanword **"Framework"** on buttons ("Importar framework"), but **"Marcos teóricos"** as the panel heading.
- **Also in play:** **"Marco"**, **"Marco teórico"**.
- **The nuance:** "framework" is everyday UX/dev speech in Spanish; "marco / marco teórico" is the academic register — and the codebook leans academic.
- **My hunch:** Normalise to **"Marco teórico" / "Marco"** — it fits the codebook's tone, and right now someone clicks a "Framework" button that opens a "Marcos teóricos" panel.
- **You:** Go academic ("Marco teórico"), or keep the loanword because your researchers actually say "framework"?

### "Speaker" vs "Participant" (the sessions table)  ·  clear-cut, just confirm
- **What we use now:** **"Hablante"** everywhere — except the sessions column header "Speakers" is rendered **"Participantes"**.
- **Also in play:** **"Locutor"**, **"Orador"**, **"Interlocutor"** (rejected — broadcast/conversational register).
- **The nuance:** in this product a moderator or observer is a *hablante* but not a *participante*, so collapsing them in that header loses a real distinction.
- **My hunch:** Change that column to **"Hablantes"**; keep "Hablante" as the anchor (matches Azure Speech ES and the diarisation literature).
- **You:** Agree the column should read "Hablantes", and we drop "locutor/orador"?

### "Star" a quote (mark a favourite)  ·  clear-cut, just confirm
- **What we use now:** the action/state is **"Destacar" / "citas destacadas"** everywhere a user acts; the noun **"estrella"** appears only in the Help text that names the icon.
- **Also in play:** **"favoritas"** (used once for "featured").
- **The nuance:** minor verb/noun split — fine pedagogically (the glyph *is* a star), but the stray "favoritas" implies a separate "featured" state we may not have.
- **My hunch:** Keep **"Destacar / destacadas"** (Apple uses it too); collapse the stray "favoritas" into "destacadas" unless there's a real distinct state.
- **You:** Is "destacar/destacada" right to your ear, and is there any "featured" concept distinct from "starred"?

## Quick confirms (I think these are settled — just shout if not)

- **Participant → Participante** — standard in ES UX and qualitative research; *usuario* reserved for "user".
- **Theme → Tema** — the Braun & Clarke "análisis temático" term.
- **Tag → Etiqueta** — matches Apple's Finder ("Etiquetas") and QDA coding usage.
- **Friction → Fricción** ("puntos de fricción") — the established ES UX term; kept separate from *punto de dolor* (pain point).
- **Speaker → Hablante** — the diarisation standard (Azure Speech ES); the only fix is the table column above.

## Anything I've got wrong?

If any term feels off, or there's a concept we've rendered awkwardly that you'd phrase differently, please flag it — I'd rather hear it now. On all of these your call wins over mine.
