# Translating Bristlenose

Bristlenose uses [Weblate](https://hosted.weblate.org/projects/bristlenose/) for community translation. You don't need to know Git or JSON — just sign up and start translating in your browser.

## Getting started

1. Go to [hosted.weblate.org/projects/bristlenose/](https://hosted.weblate.org/projects/bristlenose/)
2. Pick a language and component
3. Translate strings — Weblate shows the English source, context, and glossary suggestions
4. Your translations are submitted as pull requests for review

## Components

Each component maps to a namespace file in `bristlenose/locales/`:

| Component | What it covers | Priority |
|-----------|---------------|----------|
| **common** | UI chrome — nav, buttons, labels, quotes, sessions, analysis, codebook | Highest |
| **settings** | Settings panel labels | High |
| **enums** | Sentiment tags (frustration, confidence, etc.) and speaker roles | High |
| **desktop** | macOS menu bar, toolbar, native chrome (macOS app only) | Medium |
| **cli** | Command-line output messages | Low |
| **pipeline** | Pipeline stage progress labels | Low |
| **server** | API error messages | Low |
| **doctor** | Health check messages | Low |

Start with **common**, **settings**, and **enums** — these are what users see most.

## Glossary

Weblate includes a project glossary with two kinds of terms:

- **Apple standard terminology** — Save, Cancel, Delete, Settings, etc. must match the platform conventions for your language (sourced from [Apple's localisation resources](https://applelocalization.com/))
- **QDA domain terms** — Codebook, Quotes, Sessions, Signals, Codes. These follow established conventions from ATLAS.ti, MAXQDA, and NVivo in each language

The glossary prevents inconsistent translations of these standard terms.

## Guidelines

- **Use formal register** — Bristlenose is a professional research tool. Use formal "you" where applicable (usted, vous, Sie, 합쇼체)
- **Don't translate interpolation variables** — `{{count}}`, `{{name}}`, `{{error}}` must stay as-is
- **Preserve pluralisation keys** — i18next uses `_one` / `_other` suffixes. Translate both forms
- **Check Apple conventions** — for standard UI verbs (Save, Cancel, Delete, Open, Close), use whatever Apple uses in your language's macOS localisation
- **Context is provided** — each string has a note explaining where it appears. If context is missing, ask in the Weblate discussion

## Current languages

| Language | Status |
|----------|--------|
| English (en) | Source language |
| Spanish (es) | Machine-translated, awaiting native review |
| French (fr) | Machine-translated, awaiting native review |
| German (de) | Machine-translated, awaiting native review |
| Korean (ko) | Machine-translated, awaiting native review |
| Japanese (ja) | Stubs only — needs translators |

## Adding a new language

1. Open an issue or start translating on Weblate — new languages are welcome
2. Weblate creates the locale files automatically
3. Before release, translations are cross-checked against [Apple's localisation glossary](https://applelocalization.com/) for standard UI terms

## Technical details

- Format: i18next JSON v4 (nested keys)
- Source files: `bristlenose/locales/{lang}/{namespace}.json`
- Single source of truth — Python, React, and macOS desktop all read from the same locale files
- English strings that change in the codebase are automatically flagged as "needs editing" in Weblate
