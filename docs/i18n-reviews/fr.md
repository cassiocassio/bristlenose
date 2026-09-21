# Bristlenose — French wording check

Bristlenose turns a folder of user-interview recordings into a browsable report — extracted quotes, themes, sentiment, friction points. We've got a French translation in place and most of it is settled; I'd just like your steer on a handful of terms before we lock them in. Should take five minutes, maybe ten if the Tag one sparks a debate.

## Where I'd really value your steer

### Tag (free-form labels on a quote)  ·  genuine toss-up
- **What we use now:** « étiquettes » on the web report, « tags » in the native Mac menus and toolbar
- **Also in play:** standardising everything one way or the other
- **The nuance:** Apple's own French macOS Finder keeps the loanword (« le champ Tags », « Modifier les tags »), so the desktop is actually the Apple-correct one and the web « étiquettes » is the odd one out — but « étiquettes » is plainer French. These tags are the user's own loose labels, kept deliberately distinct from formal « codes » in the grille de codage.
- **My hunch:** I'd unify on « tags » to match Finder and keep it cleanly separate from « code » — but this is exactly the call where your read on the Mac-French register beats mine.
- **You:** « tags » everywhere to match Apple, or « étiquettes » everywhere even though it drifts from Finder?

### Quote (an extracted participant quotation)  ·  clear-cut, just confirm
- **What we use now:** « verbatim » in the nav and chrome (our anchored term)
- **Also in play:** « citation » still shows up in ~30 spots — export column headers, the quote-card actions, the Miro flow — sometimes next to « verbatim » on the same screen
- **The nuance:** « verbatim » is the QDA-register noun; « citation » is the everyday word — both fine, but mixing them in one view reads as sloppy.
- **My hunch:** Normalise all the chrome to « verbatim » and retire « citation » except where someone is literally citing (e.g. copy-to-clipboard). Also planning to keep « verbatim » invariable in the plural.
- **You:** Happy with « verbatim » as invariable, and any context where you'd actually prefer « citation »?

### Speaker (a voice in the transcript)  ·  clear-cut, just confirm
- **What we use now:** « locuteur » almost everywhere (matches « diarisation des locuteurs »)
- **Also in play:** « intervenant » in the Sessions column header and in one desktop pipeline-stage label — where the CLI says « locuteurs » for the same step
- **The nuance:** « locuteur » is the precise speech-tech term; « intervenant » leans towards a panel/event contributor, though it may feel less jargon-y to a research audience.
- **My hunch:** Normalise to « locuteur(s) » and fix the desktop/CLI split — but I could see « intervenant » as the friendlier column header.
- **You:** All « locuteur », or keep « intervenants » as the Sessions column word?

### Removing personal data (the PII step)  ·  genuine toss-up
- **What we use now:** « suppression des données personnelles » for the step itself; « expurgation / expurger » in the advanced settings labels
- **Also in play:** « anonymisation » — but note that's genuinely a *different* feature for us (stripping name labels), so some of it is correct, not drift
- **The nuance:** « suppression » reads natural to a lay researcher; « expurgation » (and « caviardage ») are the legal-register terms — the question is purely which register fits a researcher-facing tool.
- **My hunch:** Standardise on « suppression » in user-facing copy and drop « expurgation » from the settings labels.
- **You:** « suppression » throughout, or do you want the legal-register « expurgation » kept in the advanced settings?

## Quick confirms (I think these are settled — just shout if not)

- **Participant → « participant »** — the MAXQDA/Dovetail standard; we use the inclusive « participant·e » only in the role-picker — flag if the mid-dot feels wrong for a Mac app
- **Theme → « thème »** — the Braun & Clarke « analyse thématique » term
- **Friction → « friction »** — matches French UX usage (« points de friction »)
- **Star / favourite → « favori »** — consistent everywhere; the one outlier is the spreadsheet column « Marqué », which I'll align to « Favori » unless you'd keep it
- **Quote anchor → « verbatim »** and **Speaker anchor → « locuteur »** — confirmed above; listed here as the agreed base

## Anything I've got wrong?

If any of these feels off in real French research practice — or if there's a concept we render awkwardly that you'd phrase differently — please flag it. On all of these your call wins over ours; I've only made hunches to give you something concrete to push against.


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
Chargement des signaux…
Aucun signal pour l'instant. Exécutez le pipeline ou appliquez des étiquettes de la grille de codage pour en générer.
Erreur lors du calcul des signaux d'étiquettes : {{error}}
Les signaux sont des concentrations statistiquement notables de sentiment au sein des sections du rapport. Les signaux forts et modérés indiquent où les expériences des participants se concentrent.
Les signaux sont des concentrations statistiquement notables de sentiment ou d’étiquettes de grille de codage au sein des sections du rapport. Deux types de carte de signal.
```

## Where I'd value your steer

### «Erreur lors du calcul des signaux d'étiquettes»  ·  I invented this — please check it
- **Was:** «Erreur de signaux d'étiquettes», which I am confident is wrong: *de*
  plus a bare countable plural is not French. *Erreur de lecture / de connexion*
  works because the noun names a process.
- **What I nearly wrote:** «Erreur des signaux d'étiquettes». I measured it
  first, and Apple's French ships **«Erreur des …» zero times** against **87**
  for **«Erreur lors de …»** (*Erreur lors de la lecture du fichier*, *Erreur
  lors de l'enregistrement*), so I followed the platform.
- **The nuance:** *lors du calcul* asserts that the *computation* failed, which
  is true but more specific than the English. It is also longer than an error
  label wants to be.
- **You:** is *Erreur lors du calcul des signaux d'étiquettes* right, or would
  you restructure? This is the string I am least sure of in any language.

### «Les signaux sont des concentrations …»  ·  the copula is mine
- Plural with *des*, so your existing clause survived verbatim. A definition
  might prefer the singular.
- **You:** plural, or singular?

### «pour en générer»  ·  close call
- **Was:** «pour les générer» — changed because nothing plural preceded *les*
  (the sentence opens *Aucun signal pour l'instant*), and after a zero quantity
  French takes the partitive.
- **You:** confirm *en* is right here?

### One typographic thing I left alone
- The two help sentences use **different apostrophes** — the guide has a
  straight `'` in *d'étiquettes*, the Signals intro has a curly `'`. Both
  predate this round; I matched each line rather than normalising, because a
  whole-file apostrophe sweep is a separate job. Flagging so you know it is
  known.

## Quick confirms — all first-draft

- **Intensity tooltip** — «Intensité émotionnelle moyenne (1–3)». The range said 0–3 in every language
  including English, and the scale has always been 1–3; one digit, corrected
  everywhere.
- **The lens name is unchanged** and glossary-anchored. This round is about the
  sentences around it.
- **A *Signals view* phrasing existed for a few hours and is gone.** Before the
  definition-first rewrite these sentences named the lens with your language's
  own word for a *view*. No string does now. If a future one needs it, the
  glossary says: use the platform's **View** noun, never the optical word —
  Apple ships *Lens* as the camera part in all 21 of our languages.
