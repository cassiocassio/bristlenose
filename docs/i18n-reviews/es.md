# Bristlenose — Spanish wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — quotes, themes, sentiment and friction points pulled out automatically. I've drafted the Spanish wording and want your steer on a handful of terms before they're locked in. Should take five minutes — most of it is just nodding through the obvious ones.

_Refreshed 3 Aug 2026. The app has gained about 77 new strings since this brief was first written, most of them in the Mac menus and a new "agents" area — those are marked **new** below. Nothing here has been applied yet; it's all still up for your call._

## Where I'd really value your steer

### "PII redaction" (the privacy/anonymisation step)  ·  clear-cut, just confirm
- **What we use now:** mixed — the prose says **"Eliminación de datos personales"** but one settings label says **"Redacción de PII"**.
- **Also in play:** **"Eliminación de PII"**, **"Anonimización"**.
- **The nuance:** false friend — *redactar* means *to write/word a text*, so "Redacción de PII" reads as *writing up the PII*, the opposite of blanking it out.
- **My hunch:** Kill "Redacción de PII". Align that label to **"Eliminación de datos personales"** (or "Eliminación de PII") to match the prose.
- **You:** Happy with "Eliminación de datos personales" as the single term, and dropping *redacción* entirely?

### "Needs a home" — the heading for uncategorised quotes  ·  **new** · genuine toss-up
- **What we use now:** nothing — it's still sitting there in English, along with the sentence under it.
- **The nuance:** it's an idiom, and the whole point of the wording is reassurance. These are quotes you decided to keep that didn't land in any section or theme, and the English deliberately sounds gentle rather than administrative — the body text says *"it's safe here, nothing was lost."* A literal rendering ("Necesita un hogar") sounds odd; a flat one ("Sin clasificar") is accurate but loses the reassurance, which is the entire reason the section exists.
- **My hunch:** none worth the name — this is the one I'd most like you to just *write*, rather than pick from my options.
- **You:** How would you say this to a researcher who's worried they've lost work? Heading plus the sentence under it.

### "Focus Mode" (a quiet reading view — chrome fades, quote text stays)  ·  **new** · genuine toss-up
- **What we use now:** **"Modo enfoque"** — machine-drafted, unreviewed.
- **Also in play:** **"Modo concentración"**, **"Modo de enfoque"**.
- **The nuance:** two traps. Apple's *system* Focus (the notification filter) is **"Concentración"** in Spanish, so "Modo concentración" could read as the OS feature rather than ours. And it must not sound like a *reading mode* that reflows the text into a column — it doesn't; nothing moves, the surrounding clutter just fades.
- **My hunch:** keep **"Modo enfoque"**, precisely because it steers clear of Apple's "Concentración".
- **You:** Does "Modo enfoque" read naturally, or does it sound like a camera setting? And is the clash with Apple's "Concentración" real enough to matter?

### "Star" / "Unstar" a quote  ·  clear-cut, just confirm
- **What we use now:** the action/state is **"Destacar" / "citas destacadas"** everywhere a user acts; the noun **"estrella"** appears only in the Help text that names the icon. **New:** the undo action is **"Quitar destacado"**, and with a count it becomes **"Quitar destacado de 12 citas"**.
- **Also in play:** **"favoritas"** (used once for "featured").
- **The nuance:** "Destacar" itself is settled — but its opposite is four words where English has one, and it sits in a Mac menu where the neighbouring items are one or two words. Long menu items aren't wrong, they're just conspicuous.
- **My hunch:** Keep **"Destacar / destacadas"** (Apple uses it too); collapse the stray "favoritas" into "destacadas" unless there's a real distinct state. Live with the long unstar unless you know a tighter verb.
- **You:** Is there a natural one-word opposite to *destacar* here, or is "Quitar destacado" simply what it is? And is there any "featured" concept distinct from "starred"?

### "Framework" in the codebook (a coding scheme like Garrett or Norman)  ·  genuine toss-up
- **What we use now:** mixed — the loanword **"Framework"** on buttons ("Importar framework"), but **"Marcos teóricos"** as the panel heading.
- **Also in play:** **"Marco"**, **"Marco teórico"**.
- **The nuance:** "framework" is everyday UX/dev speech in Spanish; "marco / marco teórico" is the academic register — and the codebook leans academic.
- **My hunch:** Normalise to **"Marco teórico" / "Marco"** — it fits the codebook's tone, and right now someone clicks a "Framework" button that opens a "Marcos teóricos" panel.
- **You:** Go academic ("Marco teórico"), or keep the loanword because your researchers actually say "framework"?

### "Agent" — the new AI-assistant area  ·  **new** · clear-cut, just confirm
- **What we use now:** **"agente"** throughout — "Activar acceso de agentes", "Agentes MCP", "Compartido con agentes", "Conectar un agente…".
- **The nuance:** this is a whole vocabulary that didn't exist when we last spoke. It's for letting an outside AI assistant read a project's quotes, so the words carry a privacy weight — a researcher needs to understand they're granting access, not installing a feature. There's also a consent paragraph in this area worth reading as prose rather than as terms.
- **My hunch:** "agente" is the standard rendering and I'd keep it; the bit I'm less sure of is whether *"acceso de agentes"* lands as "permission granted to agents" or reads more vaguely.
- **You:** Does "Activar acceso de agentes" clearly say *you are granting outside access*? And does the consent paragraph read like plain Spanish or like a translated legal notice?

### "Speaker" vs "Participant" (the sessions table)  ·  clear-cut, just confirm
- **What we use now:** **"Hablante"** everywhere — except the sessions column header "Speakers" is rendered **"Participantes"**.
- **Also in play:** **"Locutor"**, **"Orador"**, **"Interlocutor"** (rejected — broadcast/conversational register).
- **The nuance:** in this product a moderator or observer is a *hablante* but not a *participante*, so collapsing them in that header loses a real distinction.
- **My hunch:** Change that column to **"Hablantes"**; keep "Hablante" as the anchor (matches Azure Speech ES and the diarisation literature).
- **You:** Agree the column should read "Hablantes", and we drop "locutor/orador"?

## Two small things I spotted while refreshing this

- **Tense drift in the new-project dialog.** English states what happens — *"Your interviews are copied into this folder."* Spanish promises what will happen — *"Tus entrevistas se copiarán en esta carpeta."* Present vs future. Which is right for a Mac save dialog in Spanish?
- **"Add funds…"** for topping up an AI provider's account is **"Añadir fondos…"**. Is *fondos* the word, or would *saldo* (the phone-credit sense) be more natural?

## Quick confirms (I think these are settled — just shout if not)

- **Participant → Participante** — standard in ES UX and qualitative research; *usuario* reserved for "user".
- **Theme → Tema** — the Braun & Clarke "análisis temático" term.
- **Tag → Etiqueta** — matches Apple's Finder ("Etiquetas") and QDA coding usage.
- **Friction → Fricción** ("puntos de fricción") — the established ES UX term; kept separate from *punto de dolor* (pain point).
- **Speaker → Hablante** — the diarisation standard (Azure Speech ES); the only fix is the table column above.
- **Menu verbs** — commands are imperative and article-free: "Analizar", "Añadir archivos…", "Mostrar sesiones", "Ocultar proyectos". One straggler keeps its article — "Mostrar **el** menú Diagnóstico" — which I'll drop for consistency unless you'd keep it.
- **Export scope labels** — "Todas / Seleccionadas / Destacadas", agreeing with *citas*.
- **"Sin crédito"** for a provider that's run out.

## Not translated yet — no decision needed, just flagging

These are showing in English in the Spanish build, or are missing outright. I'll fix them; if any wording jumps out at you while you're in here, all the better.

- The "Needs a home" heading and its sentence (the toss-up above).
- The codebook's folded summary — "3 tags · 40 coded".
- The three speaker-role placeholders — Moderator / Observer / Participant.

## Anything I've got wrong?

If any term feels off, or there's a concept we've rendered awkwardly that you'd phrase differently, please flag it — I'd rather hear it now. On all of these your call wins over mine.
