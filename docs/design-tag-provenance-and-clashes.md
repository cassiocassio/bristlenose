---
status: proposal. §2 (what the code does) is measured; §4 and §5 are for the maintainer to rule on. Nothing here is built.
last-trued: 2026-11-01
trued-against: HEAD@main on 2026-11-01
---

# Tag provenance and name clashes: a researcher's own tags are never displaced

**The problem (N146, P2, loss; maintainer, 1 Nov 2026):** a tag the researcher made themselves
("trust", "workaround", "friction") ends up on the wrong codebook once a codebook with a tag
of the same name (UXR has all three) is installed, and removing that codebook later strips the
researcher's own tagging from those quotes.

**The maintainer's brief:** we need the provenance of a tag in terms of which codebook it came
from, including manual (the project codebook), and in future a shared "all project-codebooks
in this folder of projects" and a global user-library of opt-in codebooks; handle tag clash
and removal intelligently; (i) a tag with the same name is likely to be similar but not
necessarily identical; (ii) groups carry meaning, so `customer-feedback/frustration` and
`support-team/frustration` are not the same thing; (iii) manual tags are hard work and almost
certainly meaningful, whereas auto-tags are promiscuous and cheap to add, hide, disable and
refuse, so a clash between competing auto tags and one between manual and auto want different
handling, and an auto tag must never displace or overwrite a manual one. A distinct visual style
for manual tags, and priority for them when scanning a page, is a likely future step.

---

## 1. Principles (the rules the solutions are judged against)

1. **Identity is the tag's row, never its name.** A tag is (group, name). Two tags may share a
   leaf name; the app never merges them unasked.
2. **Groups carry meaning, and the default stays quiet.** The group is data (it is what makes
   two same-named tags different tags, and what Signals count). Showing it is *not* the default:
   today the colour is enough, extra visual weight is usually a mistake for a researcher on a
   deadline, and a clash is usually disentangled by context (this quote came from the CX
   person, not a user). The group can appear on demand (a tooltip) or when a researcher is
   choosing between two same-named tags, and nowhere else.
   The group is also **the unit Signals measure**: a quote contributes once per group (the
   matrix columns are groups, `routes/signals.py`, `signals/generic_matrix.py`), on the premise
   that a group's tags overlap enough in meaning to belong to one discussion. So the name-lookup
   bug is not only a tagging nuisance: when a typed "trust" lands on a codebook's "trust", the
   quote silently counts toward that codebook's group in Signals instead of the researcher's own,
   and moving or merging a tag across groups changes the signal, not just a label. Group
   membership is part of the methodology, which is the strongest argument for resolving by
   identity and for never merging same-named tags unasked.
3. **Manual outranks auto, always.** An auto tag cannot overwrite, shadow or remove a manual
   one; removing auto content cannot strip manual work. Auto content is cheap to add and
   cheap to discard; manual content is expensive and kept.
4. **Similar is a suggestion, not an action.** "These look alike, merge?" is offered, never
   done automatically.
5. **Subscribed means linked, like a Figma symbol (maintainer, 1 Nov 2026).** A tag a project
   takes from a shared library is a reference to one row, not a copy. Rename "moan" to "gripe"
   while working in another project and it changes everywhere it is used; the link can be
   **detached** as a conscious act, after which that project's tag is its own row. A rename is
   therefore an edit to one row, never a find-and-replace on names, which is the practical reason
   identity is the row. Detach is one-way and must say so. (Library design is v1+; this records
   the requirement so the identity work in §3 A is built to carry it.)
6. **Scope is separate from identity.** Where a tag lives (this project, a folder of projects,
   the global library, a framework template) decides who sees it and who can delete it, not
   what it is.

## 2. What the code does today (measured 1 Nov 2026)

- **A tag belongs to a `CodebookGroup`; a group has a `framework_id`** (the template it came
  from, such as `uxr`) or none (the researcher's own). Projects activate groups through
  `ProjectCodebookGroup`. So the provenance of a tag already exists: group, then
  `framework_id`. **The schema calls these tables "instance-scoped", but each project has its
  own database file** (`db_url_for_project`, `<output>/.bristlenose/bristlenose.db`; the instance
  database is "unused today", `design-multi-project.md`), so in the shipped product every tag,
  manual or framework, lives in one project's database and is that project's alone.
- **Each application of a tag has a source.** `QuoteTag.source` is `human` or `autocode`.
  So "manual versus auto" already exists per application.
- **A tagging gesture resolves the tag by NAME, over every tag in the library.**
  `patch_tags` (`routes/data.py`) builds `{name.lower(): id}` from all `TagDefinition` rows;
  the last row with a given name wins. Installing UXR after you made "trust" can make your
  gesture land on UXR's "trust". (Within that project's database; other projects are not in it.)
- **Removing a tag removes by name too:** every `QuoteTag` on the quote whose tag has that name,
  so removing your "trust" also removes a same-named auto tag on that quote.
- **Installing a framework does no clash check.** `import_template` creates the framework's
  tags as new rows in the framework's group, whatever the researcher already has.
- **Uninstalling a framework deletes its tags and their `QuoteTag` rows** (decision D20,
  option A). Combined with the name resolution, that deletes the researcher's work.

### 2a. Added 1 Nov 2026 after the maintainer's follow-up questions (traced in code, not run)

- **Manual tags are project-scoped in practice** (corrected 1 Nov 2026; the maintainer's
  screenshots showed project-ikea's "bad bad" absent from Talismanic). A tag typed onto a quote
  is created in the project's own "Uncategorised" group, in that project's own database. An
  earlier version of this section said manual tags were shared across the whole library and that
  `delete_tag` could strip another project's tagging; that was read from a schema that can hold
  many projects, not from the product, which never puts two in one database. The cross-project
  reproduction was built, found unreachable, and withdrawn. **The loss is inside one project:**
  the name lookup, the removal by name and the uninstall below.
- **The tag input discards the choice the dropdown shows.** The suggestion rows carry group
  headers and colours, but `onCommit(tagName: string)` receives only the name; Enter on a typed
  "trust", on a ghost completion, or on an arrowed row all commit the same string. When the whole
  word is typed the exact-match row is not even listed (`lower !== val`), so your own "trust" is
  absent from the list while longer siblings show.
- **Suggestion order is the codebook's, with Uncategorised last, by design for the codebook
  panel** (the floor sits at the bottom). It was not chosen for suggestions: manual-first is
  neither luck nor design, it is simply not a rule yet.
- **Removal is by name, in two places.** The client sends `remove: ["trust"]` and `patch_tags`
  deletes every `QuoteTag` on that quote with that name, so clicking × on one "trust" removes
  the other. The badge colour is truthful (each tag a quote carries is sent with its own
  `codebook_group`, `colour_set`, `colour_index` and `source`), but the × and undo do not use it.
- **The client's tag-to-group map is keyed by lower-cased name** (`QuoteSections` and its
  siblings), so with two "trust" tags the last group read wins that entry. Anything derived from
  it (hiding a group by its eye, a group's colour for a bare name) cannot tell them apart.
- **Signals already treat same-named tags in different groups as different.** The matrix is
  built from each applied tag's definition id, mapped to its group, and the columns are the
  groups (`routes/signals.py`, the tag-definition-to-group map); names are carried only as a
  label list per group. So the risk is confined to the tagging gesture, removal, undo and the
  client's name-keyed map above, plus any export that writes tag names as text (a CSV column
  cannot tell two "frustration"s apart; nobody counts those by hand except an academic).
- **Sentiments are special-cased, and any tag design must carry the exceptions** (maintainer,
  1 Nov 2026; verified in code). The sentiment framework (`framework_id == "sentiment"`, its
  group literally named "Sentiment", displayed as "Emotional & Cognitive Signals") is
  machine-authored: `_auto_import_sentiment_framework` links it to **every** project on import
  and the pipeline auto-tags it from quote extraction, so it is on by default on every run.
  It is the one tag family that **never counts as researcher commitment**: it is excluded from
  the pin predicate and from minting a durable id (`_is_sentiment_tag`, mirrored in
  `importer._pinned_quote_ids`). In Signals its unit is the **sentiment value, not the group**:
  the original `/signals/sentiment` matrix has the sentiments themselves as columns, and in the
  group-based endpoints the "Sentiment" group's card is relabelled from what its quotes actually
  say (`sentiment_label`), because the group name is the framework talking rather than the
  finding. Every other codebook's unit is the group. The same name-lookup bug is already on
  record for sentiments: the docstring of `_is_sentiment_tag` notes that a hand-typed
  "frustration" or "delight" resolves by name to the machine's sentiment tag, arrives as
  `human`, and would have minted a spurious pin; the code patched that symptom and not the
  cause. So the clash is not hypothetical, it is the first thing a researcher types.
  Consequences for the design: (a) resolve by identity so a typed "frustration" is the
  researcher's own tag unless they pick the sentiment one; (b) sentiments keep their exemptions
  (never pinned, never "manual") whatever the origin model becomes; (c) a shared library must
  not let a subscribed tag be mistaken for, or merged into, a sentiment.
- **Root cause, one level up:** the whole stack identifies a tag by its name; the data model
  already identifies it by row. The fix that lasts carries the tag's identity (definition id)
  through add, remove, undo, de-duplication and the suggestion list, and uses a name only to
  create a tag that does not exist yet.

**The defect is therefore name-based resolution and uninstall semantics, not the absence of
provenance.** (The first recommendation, refusing a clashing tag at install, addresses a
different mechanism and would leave the loss in place.)

## 3. Solutions, smallest first

| | What | Fixes | Cost |
|---|---|---|---|
| **A. Resolve by identity, manual first** | A tagging gesture resolves to the researcher's own groups first; a tag picked from the list is committed by its row, not its name; typing a whole name and pressing Return means the manual one if there is one; the manual tag is listed first. Removal and undo remove the tag pointed at. | the loss inside a project | small to medium: the id must travel through the client (§2a) |
| **B. Uninstall protects manual work** | Removing a codebook deletes only its **auto** applications. Applications the researcher made are kept, re-homed to a same-named tag in the researcher's own group (created if absent). | the stripped tagging | small; a decision on re-homing |
| **C. Make clashes discoverable, and merging a choice** | Colour stays the default signal. The group is available on demand (a tooltip on the badge) and in the tag picker when two same-named tags are offered. At install or in the codebook, a "looks like a tag you have" list with a merge the researcher chooses. No rename on install, no standing group labels. | confusion, duplicates | small design; new words only for the merge |
| **D. Origin as a first-class scope** | Replace "framework id or none" with an origin: project, folder, global, framework. Identity stays the row; scope decides visibility and deletion. Builds the folder codebook and global library the brief anticipates. | the roadmap | a migration and a design doc of its own |
| **E. Manual tags look different** | A distinct style, and priority in scanning, from `source` and group origin. | scanning | visual design; data already supports it |

**Rejected:** refusing at install (does not stop the loss); rename on install, "trust (UXR)"
(a new naming rule, new copy, a migration for installed rows, and it hides that two tags
are the same word); merging same-named tags automatically (violates principle 4).

## 4. Recommendation

**A and B now** (beta-sized, no screens, no new words, they stop the data loss), then **C and
D together** as the design for the folder and global libraries, then **E** whenever the visual
language is ready. A and B are the only parts that touch stored data semantics, so they need a
test that fails before them: install UXR after the researcher has "trust" on 5 quotes, tag a
6th "trust", uninstall UXR, and all 6 are still the researcher's.

## 5. Questions for the maintainer

1. **Re-homing in B.** When a codebook with a same-named tag is removed, do the researcher's
   applications move to a same-named tag in their own group (created if absent), or to a
   visible "kept from <codebook>" group? (Recommendation: their own group, silently; they
   made the tag, it is theirs.)
2. **Removal by name.** Should removing a tag from a quote remove only the one pointed at?
   (Recommendation: yes; the picker already knows which.)
3. **Scope.** Is the folder codebook (shared across a folder of projects) and the global
   library one feature or two? It decides whether D is one migration or two.
4. **Visual priority for manual tags (E).** Before or after v1?

## 6. Related

- `docs/design-codebook-state-model.md` (what enable and disable mean) and
  `docs/design-codebook-library.md`.
- Decision D20 (uninstall deletes the framework's proposals and applications).
- `docs/design-upgrades-and-compatibility.md`: any change to stored data semantics here is
  a migration, and falls under its rules.
