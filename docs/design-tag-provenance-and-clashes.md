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
2. **Groups carry meaning.** Where two tags share a leaf name the group is shown beside it.
3. **Manual outranks auto, always.** An auto tag cannot overwrite, shadow or remove a manual
   one; removing auto content cannot strip manual work. Auto content is cheap to add and
   cheap to discard; manual content is expensive and kept.
4. **Similar is a suggestion, not an action.** "These look alike, merge?" is offered, never
   done automatically.
5. **Scope is separate from identity.** Where a tag lives (this project, a folder of projects,
   the global library, a framework template) decides who sees it and who can delete it, not
   what it is.

## 2. What the code does today (measured 1 Nov 2026)

- **Tag definitions are shared by every project** (`TagDefinition`, instance-scoped). A tag
  belongs to a `CodebookGroup`; a group has a `framework_id` (the template it came from, such
  as `uxr`) or none (the researcher's own). Projects activate groups through
  `ProjectCodebookGroup`. So the provenance of a tag already exists: group, then
  `framework_id`.
- **Each application of a tag has a source.** `QuoteTag.source` is `human` or `autocode`.
  So "manual versus auto" already exists per application.
- **A tagging gesture resolves the tag by NAME, over every tag in the library.**
  `patch_tags` (`routes/data.py`) builds `{name.lower(): id}` from all `TagDefinition` rows;
  the last row with a given name wins. Installing UXR after you made "trust" can make your
  gesture land on UXR's "trust". It also spans other projects' tags.
- **Removing a tag removes by name too:** every `QuoteTag` on the quote whose tag has that name,
  so removing your "trust" also removes a same-named auto tag on that quote.
- **Installing a framework does no clash check.** `import_template` creates the framework's
  tags as new rows in the framework's group, whatever the researcher already has.
- **Uninstalling a framework deletes its tags and their `QuoteTag` rows** (decision D20,
  option A). Combined with the name resolution, that deletes the researcher's work.

**The defect is therefore name-based resolution and uninstall semantics, not the absence of
provenance.** (The first recommendation, refusing a clashing tag at install, addresses a
different mechanism and would leave the loss in place.)

## 3. Solutions, smallest first

| | What | Fixes | Cost |
|---|---|---|---|
| **A. Resolve by identity, manual first** | A tagging gesture resolves to the researcher's own groups first, and by the specific tag row when picked from the tag picker. Never silently to a framework tag by name. Removal removes the tag pointed at. | the loss and the cross-project bleed | small; no screens, no words |
| **B. Uninstall protects manual work** | Removing a codebook deletes only its **auto** applications. Applications the researcher made are kept, re-homed to a same-named tag in the researcher's own group (created if absent). | the stripped tagging | small; a decision on re-homing |
| **C. Make clashes visible, and merging a choice** | Where leaf names collide, show the group beside the name. At install or in the codebook, list "looks like a tag you have" with a merge the researcher chooses. No rename on install. | confusion, duplicates | design; new words |
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
