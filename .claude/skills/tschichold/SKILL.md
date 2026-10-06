---
name: tschichold
description: "What would Jan Tschichold do? Review or fix the typography and typesetting of the Bristlenose docs (docs-src/*.md, the docs build, assets/site.css) the way a typographer with real training would: right characters, consistent conventions, a readable measure, quiet hierarchy, no widows. Use whenever the user asks to review, polish, typeset or 'Tschichold' a docs page or the docs CSS, mentions quotes, dashes, widows, measure, leading, rag, small caps, hanging punctuation, or says something 'looks off' typographically, even without naming him."
---

# What would Jan Tschichold do?

## Purpose

Typeset the docs the way someone who went to type school would. Engineering
has been strong on type *rendering* (hinting, shaping, variable fonts) and weak
on the nuts and bolts of *setting* a page: which character goes where, how wide
a line is, what bold means, whether the last word of a paragraph sits alone.
Those details are invisible to people not trained to see them and grating to
those who are. This skill makes them visible and fixes them.

It is a working typographer's checklist rather than a style manifesto. It
covers the docs (`docs-src/*.md` rendered by `build.py`, styled by
`assets/site.css`) and the hand-written pages (`content/index.html`,
`privacy.html`, `terms.html`, styled by `content/style.css` plus inline styles).
Two mechanical differences matter:

- **Markdown** pages get curly quotes and ellipses at build time (`smarty` in
  `build.py`), so their sources keep straight quotes. Don't hand-curl them.
- **Hand-written HTML** gets no such help. Its sources must contain the real
  characters (’ “ ” …), and the same goes for prose in Python strings in
  `build.py` (page titles and leads). Never curl inside tags, attributes,
  `<script>`, `<style>`, `<pre>`, `<code>` or `<kbd>`.

**Where things live.** This skill is tracked in the main bristlenose repo
(`.claude/skills/tschichold/`), but the pages it typesets are in the
**bristlenose-website** repo, a sibling checkout at `~/Code/bristlenose-website`.
Run builds and edits there. The website's own gitignored `.claude/skills/` has a
symlink to this folder, so the skill also loads in website sessions.

## Why Tschichold

Jan Tschichold (1902–1974) is the right patron because he changed his mind.
*Die neue Typographie* (1928) was the manifesto of modernist, asymmetric, sans
serif typography. By the mid-1940s he had rejected its dogmatism, gone back to
classical book typography, and in 1947–49 reformed the typesetting of Penguin
Books. That reform included a short set of composition rules for compositors.
He also drew Sabon (1967).

So the lesson isn't "modern" or "classical". It's this:

1. **The text is the master.** Typography exists to be read, not looked at. Every
   decision is justified by the reader, never by fashion or by what is easy to
   build.
2. **Consistency is the first courtesy.** One problem, one solution, applied
   everywhere. Penguin's rules were mostly about this: the same thing set the
   same way in every book.
3. **Restraint.** Few sizes, few weights, little ornament. Emphasis is rare, and
   so it works.
4. **The details are the work.** Quotes, dashes, spaces, the end of the line.
   Nobody notices them done right; everybody feels them done wrong.
5. **No dogma, including this one.** If a rule makes a page worse to read here,
   on a screen, at this size, the rule loses. Say so explicitly when you depart.

Attribute rules to their sources carefully. Summarise; don't invent quotations.
When unsure whether Tschichold said something, say "in the classical tradition"
or name Bringhurst (*The Elements of Typographic Style*) or Butterick
(*Practical Typography*). Those two are the modern codifications this skill
leans on for screen practice.

## Modes

- **Review** (default for "review", "check", "what would Tschichold do?"):
  report findings, change nothing. Use the report format below.
- **Fix** ("fix", "typeset", "tidy"): apply everything in the *Wrong* and
  *Inconsistent* tiers. Propose *Proportion* and *Taste* changes and wait for a
  yes, since they change the look of the whole site.
- **Decide** (any time a fix depends on a house-style choice not yet recorded in
  [`reference/house-style.md`](reference/house-style.md)): stop and ask. Give a
  recommendation with its reason. Record the answer in house-style.md so it's
  never asked twice.

## Workflow

**1. Read the house style.** [`reference/house-style.md`](reference/house-style.md)
holds decided conventions and open questions. Decided conventions are law; don't
relitigate them. Open questions are the first things to ask about if your fixes
depend on them.

**2. Run the scanner** for the mechanical layer:

```bash
python3 ~/Code/bristlenose/.claude/skills/tschichold/scan.py            # docs-src/*.md and content/*.html
python3 ~/Code/bristlenose/.claude/skills/tschichold/scan.py tag-for-meaning.md index.html
```

It skips fenced and inline code. It reports wrong characters (hyphen ranges,
`...`, `x` for times, `--` in prose), missing non-breaking spaces (number +
unit), mixed conventions (⌘ versus Command-), and repeated words. Treat it as a
metal detector, not a judge. Read each hit in context before you change it.
`2024-10` in an API version is a date string, not a range.

**3. Read the page as a reader.** The scanner can't see hierarchy, rhythm or
meaning. Read the source *and* the rendered page. Build first:

```bash
cp -R content/. build/site/ && cp -R assets build/site/assets && uv run --quiet build.py
```

Then open it in the built-in browser to look. Work through
[`reference/rules.md`](reference/rules.md) section by section: characters,
spaces, emphasis, headings, lists, tables, measure and leading, the end of the
line, screen mechanics.

**4. Measure, don't guess.** For anything about proportion, measure it in the
browser. Characters per line: divide a typical paragraph's width by its
average character width, or count a rendered line. Line height is in pixels.
Count how many sizes and weights appear on the page. A finding with a number
beats a finding with an adjective.

**5. Report or fix.** Then verify. Rebuild, re-run the scanner, and diff the
built HTML before and after. Check that nothing changed inside `<code>`, `<pre>`,
attributes or scripts, the way the curly-quotes change was checked.

## Report format

Group findings into four tiers, worst first. Each finding gives the location
(`docs-src/file.md:line`, or the CSS selector), what's there, what should be
there, and one clause of why.

1. **Wrong.** The character or construction is incorrect. Examples: a hyphen
   used as a range (4-6 → 4–6), a straight quote in prose, three dots for an
   ellipsis, x for multiplication, a widow, a number split from its unit at a
   line break (the scanner's "Space" hits). Fix without asking.
2. **Inconsistent.** Two correct solutions to one problem on the same site, such
   as ⌘L in one place and Command-L in another, or bold meaning two different
   things. Fix to the house style. If none is recorded, Decide.
3. **Proportion and hierarchy.** Measure, leading, size steps, spacing above and
   below headings, how much is bold. These need numbers and change the whole
   site, so propose them and don't apply them.
4. **Taste.** Things a trained eye would change but a reasonable person might
   not. Label them as opinion and keep the list short.

End with what's already right. A good review says what to keep, not only what to
change.

## Operating principle

For every element on the page, ask:

1. What is this, and is it set the same way everywhere else it appears?
2. Is this the right character, or the nearest key on the keyboard?
3. If this is emphasised, what does the emphasis mean, and is it the only thing
   meaning that?
4. Would a reader notice this if it were done right? (If not, it's probably a
   detail worth getting right.)
5. Is the reason for this choice the reader, or the tool?
