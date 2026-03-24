# French (fr) — Native Review Notes

**Reviewer:** Anne-Sophie (Metz)
**Date sent:** _______
**Status:** awaiting review

## What this is

Bristlenose is a local-first user-research analysis tool — transcription, coding, quote extraction. We've machine-translated the UI into French and need a native-speaking UXR practitioner to sanity-check the terminology before we ship it.

The translation covers ~210 strings across 8 files: navigation tabs, buttons, settings, sentiment labels, speaker roles, CLI output, macOS menu bar items, and toolbar labels.

## What we need from you

Read through the term choices below and tell us if anything feels off — wrong word, stilted phrasing, something no French researcher would actually say. We're after natural, professional French that feels like the tool was built for francophone researchers, not translated from English.

Don't worry about typos or formatting — we'll fix those. Focus on whether the **vocabulary feels right**.

## Key terminology decisions

These came from researching ATLAS.ti, MAXQDA, and NVivo localised UIs, plus academic QDA literature (Paillé, Mucchielli). We're fairly confident but want your gut check.

| English | Our French | Why | Your verdict? |
|---------|-----------|-----|---------------|
| Quotes | **Verbatim** | French researchers use "verbatim" as an everyday noun for participant quotes. "Citations" felt too cold/academic | |
| Codebook | **Grille de codage** | Academic preference. "Livre de codes" is a literal calque | |
| Codes | **Codes** | Same word in French | |
| Tags | **Tags** | English loanword, no native QDA equivalent | |
| Sessions | **Entretiens** | "Séance" felt uncommon in research contexts | |
| Signals | **Signaux** | Our own concept (pattern detection), direct translation | |

## Open questions — we'd love your opinion

### 1. "Delight" → Enchantement or Enthousiasme?

This is a sentiment label for moments where a participant expresses genuine positive surprise — exceeding expectations, not just "happy". We went with **"Enchantement"** but considered **"Enthousiasme"**. Which feels more natural as a one-word label on a quote card?

### 2. "Verbatim" as a count noun

We use it as: "les verbatim", "un verbatim", "Verbatim suivant" (next quote). Does that read naturally, or would you expect "le verbatim" or some other form?

### 3. Gender-inclusive forms

We used the **point médian** (interpunct):
- Chercheur·euse
- Participant·e
- Observateur·rice

Is this the convention you'd expect in a professional research tool? Some teams prefer the slash form (chercheur/euse) or parenthetical (chercheur(euse)). What feels right to you?

### 4. "Réglages" vs "Préférences"

Apple switched from "Préférences" to "Réglages" in macOS Ventura (2022). We followed Apple. Does "Réglages" feel normal to you now, or do you still mentally say "Préférences"?

### 5. "Favori" for Star

We translated the star/bookmark action as "Favori". In context: you click a star icon on a quote to mark it as important. Does "Favori" work, or would "Étoile" / "Marquer" / something else be more natural?

## Where to find the files

If you want to read the full translations in context:

```
bristlenose/locales/fr/common.json      — nav, buttons, labels
bristlenose/locales/fr/settings.json    — settings panel
bristlenose/locales/fr/enums.json       — sentiments, speaker roles
bristlenose/locales/fr/cli.json         — command-line output
bristlenose/locales/fr/pipeline.json    — progress messages
bristlenose/locales/fr/server.json      — error messages
bristlenose/locales/fr/doctor.json      — health checks
bristlenose/locales/fr/desktop.json     — macOS menus & toolbar
```

## How to send feedback

However works for you — reply to the email, annotate this doc, voice note, whatever. Even just "looks fine" or "change X to Y" is perfect. No need to be formal.

Merci !
