# Bristlenose — Turkish wording check

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
  tags*. Most locales now name the noun outright.

Where your language's own earlier wording already carried the definition, I
reused it verbatim rather than re-translating — so the clause in the middle of
those sentences is the one you (or a predecessor) already saw. The copula and
the subject at the front are mine, and they are what I would most like checked.

**Context you should have: nobody has ever reviewed the Turkish.** It was
machine-seeded and is one of nine locales shipping that way, so this is not
"confirm my hunches" — it is the first time a native speaker will look at it.
Two things were changed on measurement rather than on judgement, and both want
your eye.

## The five new strings

```
Sinyaller yükleniyor…
Henüz sinyal yok. Sinyal oluşturmak için işlem hattını çalıştırın veya kod kitabı etiketleri uygulayın.
Etiket sinyali hatası: {{error}}
Sinyaller, rapor bölümleri içinde istatistiksel olarak dikkat çekici duygu durumu yoğunlaşmalarıdır. Güçlü ve orta sinyaller, katılımcı deneyiminin nerede kümelendiğini vurgular.
Sinyaller, rapor bölümleri içinde istatistiksel olarak dikkat çekici duygu durumu veya kod kitabı etiketi yoğunlaşmalarıdır. İki tür sinyal kartı.
```

## The one I'd fix first

### «kod kitabı» replaced «kod defteri» across the whole locale  ·  measured, never reviewed
- **What happened:** on 20 Sep 2026 all 26 occurrences of *kod defteri*
  (Codebook) were swept to **kod kitabı**, and every inflected form was mapped
  by hand — *defteri* is front-harmony and *kitabı* back-harmony, so the suffixes
  all had to change with it.
- **Why:** MAXQDA's own Turkish interface names its Codebook report **Kod
  kitabı** (two university training decks list the Raporlar menu verbatim), its
  official Turkish webinar says *Kod Kitabı*, DergiPark returns qualitative-research
  papers for *kod kitabı* and **Ottoman cryptography** for *kod defteri* — and
  *Elektronik Kod Defteri* is the name of a cipher mode.
- **What I am not sure about:** the sweep produced **«Kod kitabı kitaplığı»**
  for *Codebook Library*, which repeats *kitab-* and *kitapl-* in one label.
- **You:** is *kod kitabı* the term a Turkish researcher expects — and what
  would you call the Library without that repetition?

## Where I'd value your steer

### «…yoğunlaşmalarıdır»  ·  I suspect this is heavy
- **What we use now:** «Sinyaller, … duygu durumu yoğunlaşmalarıdır.»
- **The nuance:** that predicate stacks a noun compound (*duygu durumu
  yoğunlaşmaları*) on a plural, then the copula *-dır*, after a long adverbial.
  It is grammatical; I cannot hear whether it is comfortable.
- **Also in play:** breaking it in two, or «Sinyaller, … yoğunlaşmalardır» without
  the compound possessive.
- **You:** does it read as a definition, or would you restructure it?

### The comma after a one-word subject  ·  small but everywhere
- **What we use now:** «Sinyaller, rapor bölümleri içinde…» — and the same in
  the second sentence, «Güçlü ve orta sinyaller, katılımcı…»
- **The nuance:** Turkish uses that comma to stop a subject being misread, and
  with a single word it is often unnecessary. I copied the pattern from the
  file's existing sentences rather than deciding it.
- **You:** keep, drop, or keep only in the longer of the two?

### «Etiket sinyali hatası»  ·  number question
- **The nuance:** English is singular (*Tag signal error*) and I kept the
  singular here, while **fourteen** other locales went plural by reusing their
  section name (*Tag signals*). Turkish compounds singular naturally, so this
  may be right and the others may all be the odd ones.
- **You:** singular as it stands?

## Quick confirms — all first-draft, none reviewed

- **«Sinyaller»** as the lens name — our own coinage, not a QDA term in any
  language; glossary row says *Sinyaller*.
- **«işlem hattı»** for *pipeline* — already in the file, unchanged.
- **«Henüz sinyal yok.»** — the empty state. Note the instruction now names the
  noun (*Sinyal oluşturmak için…*) rather than using a pronoun, which is the
  fix described at the top.
- **Intensity tooltip** — «Ortalama duygusal yoğunluk (1–3)»; the range said
  0–3 in every language and the scale has always been 1–3.
- **«Sinyaller görünümü»** — a *Signals view* phrasing existed for a few hours
  and is **gone**; no Turkish string now contains the word *view/görünüm* for a
  lens. If a future string needs it, the glossary says to use Apple's own
  noun — *Görünüm* — and never *objektif*, which is the camera lens.

## Also worth your time, beyond this round

The Codes menu has a real problem: **«Kod Defterlerine»** was one of four
strings the sweep above touched, and more generally the Turkish *Uninstall*
verb and the *Delete* verb may collide the way they do in Finnish, Dutch,
Russian and Ukrainian — English distinguishes *Uninstall* (reversible) from
*Delete* (permanent) **in the verb**, and if Turkish uses one word for both,
nothing signals which is which. Worth a look at the Codes menu as a whole.
