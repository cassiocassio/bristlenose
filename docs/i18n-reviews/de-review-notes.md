# Bristlenose — German review notes (everything still open)

_Compiled 26 Sep 2026 from three earlier sets of notes — the March review
questions (`docs/locales/review-german-locale.md`), the per-locale brief
([de.md](de.md), rounds one and three) and the glossary research
([../i18n-glossary-proposals.md](../i18n-glossary-proposals.md)) — and **each
question re-checked against the German locale files as they stand today**.
Questions that have since been settled are left out; counts are of the German
strings on 26 Sep 2026._

---

Bristlenose turns a folder of user-research recordings into a report the
researcher edits, shares and keeps — extracted quotes, themes, sentiment,
friction points. It runs as a Mac app and in the browser. The German interface
was translated by us, not by a native speaker, and nobody who does qualitative
research in German has read it yet.

**How to answer:** a word per question is plenty — „Code", „Teilnehmende",
„ja". Where I've written a hunch, it is only a hunch; your call wins. Part 1 is
the part that matters: each answer there changes many strings at once. Parts 2–4
are quicker.

We use formal **Sie** throughout, and standard macOS chrome (Sichern,
Abbrechen, Widerrufen …) comes straight from Apple's German glossary — no need
to review those.

## Part 1 — decisions that change many strings

### 1. „Code" or „Kode"?
- **Now:** the Mac app's menus say „Kode / Kodes / Kode-Gruppe" (12 strings); the
  web report says „Code". Our own glossary says „Kodes". So the product disagrees
  with itself.
- **Both are real:** MAXQDA writes „Code / Codierung", ATLAS.ti „Kode / Kodierung".
- **Hunch:** „Code" everywhere — it pairs with „Codebuch", „Codegruppe" and „AutoCode".
- **Complication:** „Code" also appears in the *other* sense — a participant's
  anonymous speaker code like „p1" („Behält Codes (p1, p2) bei"), which elsewhere
  we call „Sprecherkennung". Should the speaker code be „Sprecherkennung"
  everywhere, so that „Code" means only the research code?
- **You:** Code or Kode? And speaker code: „Sprecherkennung", „Sprechercode", or
  something else?

### 2. Redaction, anonymisation — how many words?
Three different operations, currently sharing vocabulary:

| Operation | What it does | German now |
|---|---|---|
| PII redaction | blacks out names, phone numbers etc. in the transcript text | „Schwärzung / schwärzen / geschwärzt" (4) — **and one „PII-Redaktion ist deaktiviert"** |
| The redaction engine | the built-in software that does the above | „Integrierte Anonymisierung / Anonymisierer" (3) |
| Anonymise on export | removes participant names from an exported report | „Anonymisieren" (menu), „Anonymisierung gilt nur für den Text" |

- „Redaktion" is a false friend (editorial department) — I'll fix that one
  regardless (Part 3).
- **Hunch:** „Schwärzung" for the first; the engine could be „Integrierte
  Schwärzung" to match; keep „Anonymisieren" for the export, where names really are
  removed.
- **You:** agree, or should they be named differently? Is „Anonymisierung" wrong
  for the export, given its GDPR meaning (irreversible)?

### 3. Gender-inclusive forms
- **Now:** role badges use the colon form — „Forscher:in", „Teilnehmer:in",
  „Beobachter:in" (3 strings). The rest of the interface uses bare „Teilnehmer",
  „Sprecher", „Moderator" (and „Teilnehmernamen", „Moderatorfrage" in compounds).
  Three newer strings use „Teilnehmende".
- **Options:** colon („Teilnehmer:in"), star („Teilnehmer\*in"), participle
  („Teilnehmende / Forschende / Beobachtende"), or generic masculine.
- **Hunch:** participles — no marker to argue about, and they read well in UI.
  „Sprecher" has no clean participle („Sprechende" is odd), which may be a reason
  against.
- **You:** which convention do German-speaking researchers expect right now?
  One convention product-wide, including „Sprecher" and „Moderator"?

### 4. Sessions → „Interviews"?
- **Now:** „Interviews" for sessions (56 strings, including the tab name). But three
  strings say „Sitzung" (the AutoCode refusal and two error messages about a
  session being too long for the model).
- **The doubt:** Bristlenose also takes usability tests, focus groups and diary
  studies. Does „Interviews" still work as the label for a mixed set? We avoided
  „Sitzungen" as sounding clinical.
- **You:** keep „Interviews" (and fix the three „Sitzung"), or a broader word?

### 5. Starring a quote — „markieren"?
- **Now:** „Dieses Zitat markieren", „Markierte Zitate", „Nur markierte Zitate",
  CSV column „Markiert" (21 strings). But the Welcome screen says „Stern &
  Ausblenden".
- **The doubt:** in German macOS, „markieren" usually means *select* or
  (in Mail) *flag*, so „markiert" may read as „selected" rather than „starred".
  Alternatives: „mit Stern versehen / Mit Stern", „als Favorit".
- **You:** keep „markieren", or does the star need its own word?

### 6. Timecode — three words for one thing
„Zeitmarke" (CSV column, Welcome tip), „Zeitcode" (copy format hint),
„Zeitstempel" (the AI-consent list). **You:** which one? My hunch is „Zeitmarke".

### 7. Sentiment labels
These are badges on quotes. Seven values: Frustration, Verwirrung, Zweifel,
Überraschung, Zufriedenheit, **Begeisterung**, **Zuversicht**.
- **Delight → „Begeisterung":** we mean the small positive surprise — *„oh, that's
  nice!"*. Is „Begeisterung" too strong (enthusiasm)? Rejected: „Entzücken"
  (literary), „Freude" (too general).
- **Confidence → „Zuversicht":** we mean feeling in control, knowing what to do
  next. „Zuversicht" leans hopeful/optimistic. Rejected: „Vertrauen" (trust),
  „Selbstvertrauen" (long for a badge). Would „Sicherheit" be better?
- **Singular or plural „Stimmung"?** The column and filter say „Stimmung"; the
  Signals description says „wo sich Stimmungen … konzentrieren"; the Welcome screen says
  „Sieben Stimmungen". Fine as is, or pick one?

### 8. Friction
- **Now:** the Welcome example says „der deutlichste Reibungspunkt"; the Nielsen
  line says „an denen das Fach Reibung … erkennt".
- **Hunch:** „Reibungspunkt(e)" for the countable obstacle, „Reibung" only for
  the abstract quality — which is what we have.
- **You:** right — or do German UX researchers just say „Pain Point" / „Friction"?

## Part 2 — the Signals lens (new since your last look, all my first drafts)

The lens formerly called *Analysis* is now **Signale**. Five new sentences:

```
Signale werden geladen…
Noch keine Signale. Führen Sie die Pipeline aus oder wenden Sie Codebuch-Tags an, um Signale zu generieren.
Fehler bei Tag-Signalen: {{error}}
Signale sind statistisch auffällige Konzentrationen von Stimmungen innerhalb der Berichtsabschnitte. Starke und moderate Signale heben hervor, wo sich die Erfahrungen der Teilnehmer bündeln.
Signale sind statistisch auffällige Konzentrationen von Stimmung oder Codebuch-Tags innerhalb der Berichtsabschnitte. Zwei Arten von Signalkarten.
```

- **„Signale sind …"** — would a German definition rather say „Ein Signal ist eine
  statistisch auffällige Konzentration …"?
- **„von Stimmungen" vs „von Stimmung"** — the two sentences disagree (same
  question as 7c).
- **„Fehler bei Tag-Signalen"** — or the compound „Tag-Signal-Fehler"?
- **„Pipeline"** — is the English word acceptable to a researcher, or is it
  developer jargon here? („Analyse ausführen"?)

## Part 3 — things I'll fix unless you object

- **„du" has crept into 18 strings** — the Accounts settings pane (disconnecting
  Miro / cloud accounts), the cloud-recording import screens („Melde dich an …",
  „Keine davon gehört dir"), the restart-after-language-change prompt
  („Möchtest du die App jetzt neu starten?"), the export save panel („Wähle, wo
  der Bericht gespeichert werden soll."), the duplicate-codebook-name message and
  the empty MCP Agents list. Everything else is „Sie". I'll move these to „Sie".
  *Is there any place where „du" would actually be right?*
- **„PII-Redaktion ist deaktiviert" → „PII-Schwärzung ist deaktiviert".**
- **„Wähle ein Projekt aus und dann „Project" ▸ …"** names the menu in English;
  the German menu is „Projekt".

## Part 4 — smaller doubts, quick yes/no

1. **„Codebuch"** for codebook, and **„Codebücher"** as the tab name — natural in a
   tool UI? Or „Kategoriensystem" (Mayring) / „Codierleitfaden"?
2. **„Framework"** stays English (7 strings: „Forschungs-Frameworks", „mit einem
   fertigen Framework starten"). OK, or „Bezugsrahmen" / „Modell"?
3. **„Taggen" / „taggen"** as a verb (8 strings), and **„AutoCode"** as a product
   name — acceptable?
4. **Book titles** on the Welcome screen are in English (*The Design of Everyday
   Things*, *Usability Engineering*, *Thematic Analysis*, *Emotion & Adaptation*).
   Should they be the German editions' titles where one exists?
5. **„Ansicht"** is our word for one of the report's five views (Quotes, Sessions,
   Signals …) — we avoid „Linse", which on a Mac means the camera part. Right?
6. **„Redebeitrag"** is reserved for a *turn* (one stretch of speech by one
   person) — for a future menu item that moves words from one speaker to another,
   so it must never be confused with „Zitat". Is „Redebeitrag" the right word, or
   „Wortbeitrag" / „Äußerung"?
7. **„Schlank — Zitat, Code, Name, Zeitcode"** describes a compact copy format
   (English: *Lean*). Does „Schlank" work, or „Kompakt"?
8. These were judgement calls — does any read strangely?
   „Erneut analysieren" (Re-analyse) · „Erstellt mit Bristlenose" (Built with) ·
   „Feedback geben" · „Problem melden" (Report an issue) · „Bild-in-Bild"
   (Picture in Picture) · „Agentenzugriff aktivieren / deaktivieren"
   (Turn On / Off Agent Access).

## Anything I haven't asked about

If anything reads stiffly or like a translation, please flag it — even without a
suggested fix.
