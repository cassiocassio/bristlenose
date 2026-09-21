"""Orphan locale keys: a key in every locale, and a reader in none.

`scripts/check-locales.py` is green when a key is *present*, whichever side you
ask from — so a key that nothing reads is invisible in both directions. That is
**failure class 5** in `docs/i18n-defects.md`, and its worked instance is row
23: `49ec8a50` extracted "every string in the cloud-import window" to keys and
translated them into 21 locales, but the failure sentences live one layer below
the window, in the adapters. Ten keys — **210 translated values** — sat unread
for five weeks while the rows they were written for rendered English inside a
fully-localised window.

`tests/test_cloud_fetch_failure_keys.py` closed that one family by deriving its
expectations from a Swift enum. This is the corpus-wide sibling, and the reason
it had not shipped is that the corpus-wide version is noisy: a first pass
measured **293 of 1,637 keys with no apparent reader** (21 Sep 2026), which
`docs/i18n-defects.md` §"What to build next" refused to ship as a gate, because
a gate that fires on 293 things gets switched off and `CLAUDE.md` §"Gate policy"
is explicit that `continue-on-error` is how a check stops being a check.

WHAT MAKES IT SHIPPABLE

Not a better detector — a **classification**. "Unread" collapses several
different things, and only some are defects. Five are handled by the reader
before the register is consulted, so they never reach it:

* **computed keys.** `i18n.plural("desktop.cloudImport.attendeeCount", …)`,
  `"desktop.pipeline.category." + leaf`, `` t(`enums:sentiment.${s}`) ``. Any
  literal that is a proper dotted prefix of a key counts as reading every key
  under it. This is a deliberate **over**-approximation of "read": it cannot
  tell which leaves the composer actually reaches, so it forgives all of them.
  A tighter rule would have to model the composing expression, and the price of
  getting that wrong is a false alarm on live code — the one failure this gate
  cannot afford.
* **three surfaces, not one.** `desktop/Bristlenose/Bristlenose/**.swift`,
  `frontend/src/**`, `bristlenose/**.py`, plus the theme's Jinja templates and
  frozen JS. A key read only by the SPA is read.
* **implied namespaces.** i18next resolves a bare `configReference.categories.llm`
  against `defaultNS` or whatever `useTranslation(ns)` selected, and `dt()`
  writes the bare key while reading both `desktop:` and the base. So the bare
  spelling counts — but only for the four namespaces the SPA loads, because
  `cli` / `doctor` / `pipeline` / `preflight` / `server` are Python-only and
  always written fully qualified, where accepting a bare `start` is pure noise.
* **CLDR plural siblings.** The call site writes the base; `_one` / `_few` /
  `_many` / `_other` are composed at lookup.
* **pseudo-keys.** `_comment_*` and `_divergent_*` are notes to maintainers, as
  `flatten()` in `check-locales.py` already has it.

What is left is 152 keys, and they are not one thing either. `_KNOWN_ORPHANS`
below carries them in 24 blocks, each with a tag and the commit that did it:

* `DEAD` — the reader was deleted and the key stayed. `common.help.` was 129
  of them and is **gone as of 21 Sep 2026**: `3f49d170` had retired the in-app
  help modal on 10 Jul, two of its keys were still being reworded and
  re-translated into 20 locales on 20 Sep, and the public docs superseded the
  content entirely. Deleting it took 2,730 values out of the tree, plus the
  three `desktop.help.` overrides `docs/platform-text-map.md` had been carrying
  an open "decision owed" on since it was written.
* `UNWIRED` — a surface that never had a call site at all. The `cli`, `doctor`
  and `pipeline` namespaces are wholly in this class; they anticipate a
  translation that `docs/design-i18n.md` §"Which surfaces are targets" has
  since decided against.
* `RESERVED` — a key waiting for a reader rather than one whose reader went
  away (register item 6, pending Decision 4).
* `TRIAGED` — decided, not yet executed (register item 24).

WHY AN ALLOW-LIST IS NOT THE THING THIS FILE WARNS ABOUT

`docs/i18n-defects.md` item 4 is the standing objection to allow-lists:
`test_pipeline_diagnostic_locale_keys.py` checks hardcoded lists of things to
*look at*, so anything not listed is invisible and a new gap ships silently.
This register has the opposite polarity. It lists what is **excused**, so
anything not listed is caught. Adding to it is a deliberate edit in a commit
that has to say why; the entries may shrink and may not grow.

WHAT IT CATCHES, AND WHAT IT DELIBERATELY DOES NOT

Catches: a key added with no reader (row 23's shape — same block, new leaf, or
a new block entirely); a key whose last reader is deleted; and — because the
register pins leaves rather than counts — a fix and a regression that cancel
out in the same block.

Does not catch: a key whose name happens to appear in a doc comment or a
docstring. This scan cannot tell prose from code, and `docs/i18n-defects.md`
row 16 predicted it: `desktop.help.privacy.redactionIntro` is a real orphan
that reads as alive because `platformTranslation.ts`'s doc comment uses it as
its worked example. Its two siblings are in the register; it is not. Nor does
it catch a key composed from a prefix that is itself computed
(``t(`${ns}.${section}.title`)``), or one reached only through a data file.
Both are under-approximations chosen in the same direction: forgive rather
than false-alarm.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LOCALES = _ROOT / "bristlenose" / "locales"

#: The namespaces `bristlenose/locales/en/` ships, as `I18n.swift` and
#: `bristlenose/i18n.py` spell them. Derived from disk rather than listed, so a
#: new namespace file is swept the day it lands.
_NAMESPACES = sorted(p.stem for p in (_LOCALES / "en").glob("*.json"))

#: The four the SPA loads (`frontend/src/i18n/index.ts` — `common`, `settings`,
#: `enums`, and `desktop` in desktop mode). Only these resolve a bare key.
_SPA_NAMESPACES = {"common", "settings", "enums", "desktop"}

_PLURAL_SUFFIXES = ("_one", "_two", "_few", "_many", "_zero", "_other")
_PSEUDO_PREFIXES = ("_comment", "_divergent_")

#: Every surface that can read a locale key, and nothing else. Tests are
#: excluded on purpose: a key read only by a test is a key no researcher sees,
#: which is exactly how `AutoCodeToast.test.tsx` came to be the only witness to
#: a helper nothing rendered (`CLAUDE.md` §"Deleting a UI surface…").
_CORPUS: tuple[tuple[Path, tuple[str, ...]], ...] = (
    (_ROOT / "desktop" / "Bristlenose" / "Bristlenose", (".swift",)),
    (_ROOT / "frontend" / "src", (".ts", ".tsx")),
    (_ROOT / "bristlenose", (".py",)),
    (_ROOT / "bristlenose" / "theme", (".html", ".js")),
)

#: `bristlenose/server/static/` is the built Vite bundle — minified copies of
#: the frontend source. Reading it would let a stale build vouch for a key the
#: source no longer mentions.
_CORPUS_EXCLUDE = ("/static/", "/node_modules/", "/dist/")


def _is_test_file(path: Path) -> bool:
    return ".test." in path.name or path.name == "test-setup.ts"


@lru_cache(maxsize=1)
def _corpus_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for root, suffixes in _CORPUS:
        for suffix in suffixes:
            for path in root.rglob(f"*{suffix}"):
                text = str(path)
                if any(bad in text for bad in _CORPUS_EXCLUDE) or _is_test_file(path):
                    continue
                files.append(path)
    return tuple(sorted(set(files)))


# A locale key contains no quote, no space and no escape, so it can be found by
# scanning for key-shaped tokens between quotes rather than by pairing quotes.
# That matters: `"\(cause) \(i18n.t("settings.general.fallbackNote"))"` and
# `` `(${t("pipeline.qualifier.default")})` `` both defeat a paired-quote scan,
# and both are live call sites that a first pass reported as orphans.
_KEY_TOKEN = re.compile(r"""["'`]([A-Za-z_][A-Za-z0-9_.:-]*)["'`]""")

#: A literal that is *followed* by a composition, so everything under it is
#: reachable: Swift `"a.b\(x)"` and `"a.b" + x`, TS `` `a.b${x}` ``, Python
#: `f"a.b{x}"` and `"a.b".format(…)`.
_COMPOSED = (
    re.compile(r'"([^"\n]*?)\\\('),                      # Swift interpolation
    re.compile(r"`([^`\n]*?)\$\{"),                      # TS template literal
    re.compile(r"""[fF]["']([^"'\n]*?)\{"""),            # Python f-string
    re.compile(r"""["'`]([^"'`\n]*)["'`]\s*\+"""),       # any `"…" +`
    re.compile(r"""["']([^"'\n]*)["']\s*(?:%|\.format\()"""),
)

#: The shortest literal accepted as a composed prefix. A one- or two-character
#: fragment would forgive half the corpus; every real prefix in the tree is a
#: dotted path well past this.
_MIN_PREFIX = 6


@lru_cache(maxsize=1)
def _read_literals() -> tuple[frozenset[str], frozenset[str]]:
    """Every quoted key-shaped token, and every literal a composition follows."""
    exact: set[str] = set()
    composed: set[str] = set()
    for path in _corpus_files():
        try:
            body = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):  # pragma: no cover - defensive
            continue
        exact.update(m.group(1) for m in _KEY_TOKEN.finditer(body))
        for pattern in _COMPOSED:
            for match in pattern.finditer(body):
                fragment = match.group(1)
                if "." in fragment and len(fragment) >= _MIN_PREFIX:
                    composed.add(fragment)
    return frozenset(exact), frozenset(composed)


def _flatten(node: dict, prefix: str = "") -> dict[str, str]:
    """Dotted keys, dropping the pseudo-keys `check-locales.py` also drops."""
    out: dict[str, str] = {}
    for key, value in node.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, full))
        elif not full.rsplit(".", 1)[-1].startswith(_PSEUDO_PREFIXES):
            out[full] = str(value)
    return out


@lru_cache(maxsize=1)
def _en_keys_cached() -> tuple[tuple[str, str], ...]:
    keys: dict[str, str] = {}
    for namespace in _NAMESPACES:
        path = _LOCALES / "en" / f"{namespace}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        for key, value in _flatten(raw).items():
            keys[f"{namespace}.{key}"] = value
    return tuple(sorted(keys.items()))


def _en_keys() -> dict[str, str]:
    """Every key `en` ships, namespace-qualified as a call site writes it.

    A fresh dict each call: the mutation tests inject into what they get back.
    """
    return dict(_en_keys_cached())


def _spellings(key: str) -> list[str]:
    """Every way a call site may legitimately write `key`."""
    namespace, _, rest = key.partition(".")
    out = [key, f"{namespace}:{rest}"]
    if namespace in _SPA_NAMESPACES:
        out.append(rest)
    plural = [
        candidate[: -len(suffix)]
        for candidate in list(out)
        for suffix in _PLURAL_SUFFIXES
        if candidate.endswith(suffix)
    ]
    return out + plural


def _is_read(key: str, exact: frozenset[str], composed: frozenset[str]) -> bool:
    candidates = _spellings(key)
    if any(candidate in exact for candidate in candidates):
        return True
    return any(
        candidate.startswith(prefix)
        for candidate in candidates
        for prefix in composed
    )


def _unread(
    keys: dict[str, str], exact: frozenset[str], composed: frozenset[str]
) -> list[str]:
    """The predicate, with its corpus passed in so a test can doctor it."""
    return sorted(key for key in keys if not _is_read(key, exact, composed))


def orphans(keys: dict[str, str] | None = None) -> list[str]:
    """Keys in `en` that no surface reads. The whole gate is one function."""
    return _unread(keys if keys is not None else _en_keys(), *_read_literals())


# --------------------------------------------------------------------------
# The register. Each block carries a tag, the reason, and the exact leaves it
# excuses — leaves rather than a count, so a fix and a regression inside one
# block cannot cancel out. Shrink it when a key is wired or deleted; growing it
# is a deliberate edit in a commit that says why.
# --------------------------------------------------------------------------

#: The reader was deleted and the key stayed behind.
DEAD = "dead"
#: A surface that never had a call site at all — failure class 2's residue.
UNWIRED = "unwired"
#: A key waiting for a reader, not one whose reader went away.
RESERVED = "reserved"
#: Decided, not yet executed.
TRIAGED = "triaged"

_TAGS = {DEAD, UNWIRED, RESERVED, TRIAGED}


class _Block:
    __slots__ = ("tag", "why", "leaves")

    def __init__(self, tag: str, why: str, leaves: str) -> None:
        self.tag = tag
        self.why = why
        self.leaves = frozenset(leaves.split())


_KNOWN_ORPHANS: dict[str, _Block] = {
    "common.codebook.": _Block(
        tag=DEAD,
        why="`baa1aa0e` deleted the v1 codebook lens. The v2 navigator reuses the "
            "block, so the live and dead keys are interleaved and only a "
            "fully-qualified sweep separates them. `foldedSummary_one/_other` is "
            "register item 8 — seeded into 19 locales on 21 Aug 2026 to clear the "
            "last `check-locales.py` warning, and dead within ten days.",
        leaves="""
            autoCodePreserved autoCodeQuotes autoCodeStartFailed
            browseSubtitle browseTitle codebookFramework codebookLab
            comingSoon description errorLoading foldedSummary_one
            foldedSummary_other frameworksHeader hide hideTitle
            importHelp importingCodebook loadingImpact newCode
            noQuotesTagged previouslyImported restoreAnytime
            restoreCodebook restoreHelp restoringCodebook
            sentimentTitle tagGroups tagsRemovedFromQuotes_one
            tagsRemovedFromQuotes_other
        """,  # 29
    ),
    "desktop.pipeline.status.": _Block(
        tag=DEAD,
        why="`11435ddd` removed the per-project pipeline toolbar pill. The one "
            "survivor, `headline.failed`, is read by `ProjectDiagnosticPopover:125` — "
            "which is why the block cannot be deleted wholesale.",
        leaves="""
            analysing elapsed headline.queued headline.running
            headline.stopping help.failed help.queued help.running
            queued resuming stage stageShort starting startingUp stop
            stopping waitingInQueue waitingSubprocess working
        """,  # 19
    ),
    "desktop.pipeline.diagnostic.pill.": _Block(
        tag=RESERVED,
        why="Register item 6: `ProjectDiagnosticPopover.humanCategoryLabel` is "
            "English on purpose until Decision 4 splits the UI label from the "
            "English-only pasteboard payload a maintainer receives, so these six "
            "are keys waiting for a reader rather than keys whose reader went "
            "away. The other ten categories have no key at all — this block is "
            "half a feature, parked, and the register is where that is visible.",
        leaves="""
            auth missing_binary network out_of_credit quota unknown
        """,  # 6
    ),
    "desktop.pipeline.diagnostic.tooltip.": _Block(
        tag=DEAD,
        why="`tooltip.completed_partial` lost its reader to "
            "`diagnostic.header.completed_partial`, which is read at three sites "
            "(`ProjectDiagnosticPopover:127`, `ProjectRow:268`, "
            "`SidebarSubtitleText:47`). Same leaf name, different block — which "
            "is precisely why a leaf-name grep cannot answer this question.",
        leaves="""
            completed_partial
        """,  # 1
    ),
    "cli.": _Block(
        tag=UNWIRED,
        why="A surface that was never wired: CLI terminal chrome is English by "
            "design (`docs/design-i18n.md` §\"Which surfaces are targets\"), so these "
            "17 of the file's 19 keys have never had a call site. The two that are "
            "not here — `cli.stage.transcribe` and `cli.version` — are 'read' "
            "only by the usage example in `bristlenose/i18n.py`'s docstring, which is "
            "the one place this gate's literal scan cannot tell prose from code.",
        leaves="""
            error.noFiles error.noInput error.notFound help
            progress.complete progress.failed progress.skipped
            stage.extractAudio stage.identifySpeakers stage.ingest
            stage.mergeTranscript stage.piiRemoval
            stage.quoteClustering stage.quoteExtraction stage.render
            stage.thematicGrouping stage.topicSegmentation
        """,  # 17
    ),
    "common.export.": _Block(
        tag=DEAD,
        why="`cf75c779` routed downloads through `WKDownload` + `NSSavePanel`, which "
            "moved the progress and count strings to the native side. The block still "
            "holds live keys (`clips.noClips`, `scope.*`), so it is not deletable "
            "wholesale.",
        leaves="""
            clips.donePartial clips.noMedia clips.revealMac
            copyQuotesCount_one copyQuotesCount_other exporting
            exportingQuotes_other fromSessions_one fromSessions_other
        """,  # 9
    ),
    "desktop.welcome.": _Block(
        tag=DEAD,
        why="`a310bca6`'s bento rewrite replaced the three-step onboarding strip. The "
            "same commit is register item 12, which caught the *other* half of its "
            "damage — three `i18n.t` wrappers dropped while the keys stayed — and "
            "never looked for keys left behind with no wrapper at all.",
        leaves="""
            newProject newProjectHint steps.exportDetail
            steps.exportTitle steps.ingestDetail steps.ingestTitle
            steps.processDetail steps.processTitle subtitle
        """,  # 9
    ),
    "common.autocode.toast.": _Block(
        tag=DEAD,
        why="`d5906862` — \"delete the unmounted toast, port the coverage nothing else "
            "had\". The component went, the keys did not. `donePartial` survives in "
            "`ActivityChipStack.tsx:142`, whose own comment notes that the "
            "`autocode.toast.*` key name outlives the toast.",
        leaves="""
            dismiss done failed failedWithError progress report
        """,  # 6
    ),
    "settings.pipeline.": _Block(
        tag=DEAD,
        why="`1f4613b9` re-grained pipeline-view to per-(provider, model), retiring "
            "the alternatives summary. The `reasons.*` / `quality.*` keys in the same "
            "block are live and mirrored in `pipeline_view/cli.py`.",
        leaves="""
            alternatives.available alternatives.none
            alternatives.summaryHeading alternatives.unavailable
            available unavailable
        """,  # 6
    ),
    "common.buttons.": _Block(
        tag=DEAD,
        why="Generic v1-report button labels. Five of the block's fourteen have no "
            "call site on any surface — each live control names its own key now — so "
            "this is a block that must be pruned by leaf, never by namespace.",
        leaves="""
            apply copy reset save undo
        """,  # 5
    ),
    "common.signals.": _Block(
        tag=DEAD,
        why="`aacf3e88` rebuilt the lens as one navigation and one card list. The "
            "five superseded descriptions stayed; the block's live keys were reworded "
            "and re-translated in the 0.30.0 rename (register item 21).",
        leaves="""
            codebookTags sentimentDesc sentimentSignals tagDesc
            tagSignals
        """,  # 5
    ),
    "common.tags.": _Block(
        tag=DEAD,
        why="`4b3b1593` moved search, starred and remove-tag to the native toolbar, "
            "and the four count/empty-state strings the web dropdown had shown went "
            "unread with it.",
        leaves="""
            countHidden countTags noTags noTagsLabel
        """,  # 4
    ),
    "desktop.toolbar.": _Block(
        tag=DEAD,
        why="`53e8d7aa` — \"sessions popover 3/3: remove the embedded sessions sidebar "
            "and dropdown\". Four labels for controls that are no longer drawn.",
        leaves="""
            searchShortcut showSessions sidebar tab
        """,  # 4
    ),
    "enums.speakerRole.": _Block(
        tag=DEAD,
        why="The SPA renders `sessions.speakerPlaceholder.{moderator,observer, "
            "participant}` instead (`SessionsTable.tsx:49`), keyed off the badge-code "
            "prefix rather than the stored role \u2014 so these were a vocabulary spelled "
            "somewhere else. **`participant` left this set on 22 Sep 2026**: the "
            "AutoCode illustration reads it, because the role on a quote card is "
            "genuinely this vocabulary and genuinely translated. The gate caught the "
            "staleness the same night, from the other direction.",
        leaves="""
            observer researcher unknown
        """,  # 3
    ),
    "common.footer.": _Block(
        tag=DEAD,
        why="Superseded within the same block: the React footer reads `reportBug`, "
            "`feedback` and `version`, while `builtWith`, `reportIssue` and "
            "`giveFeedback` are the wording they replaced and nothing reads them.",
        leaves="""
            builtWith giveFeedback reportIssue
        """,  # 3
    ),
    "desktop.cloudImport.": _Block(
        tag=TRIAGED,
        why="`untitledMeeting` is register item 24 — decided: the adapter is right to "
            "hardcode English because `row.title` feeds search and the downloaded "
            "filename, so the *key* is the mistake and should be deleted. The two "
            "`zoom*` sentences have no reader on any surface and are a new find. "
            "Note what is NOT here: `dayToday` / `dayYesterday` / `attendeeCount_*` "
            "were register item 27 and are now read from `CloudImportOutlineView`.",
        leaves="""
            untitledMeeting zoomCloudRecordingOff zoomTranscriptOff
        """,  # 3
    ),
    "common.labels.": _Block(
        tag=DEAD,
        why="Generic v1-report labels — `loading` and `noResults` lost their last "
            "readers to `baa1aa0e`'s codebook-lens rewrite. `search` and `error` in "
            "the same block are still read.",
        leaves="""
            loading noResults
        """,  # 2
    ),
    "desktop.connectAgent.": _Block(
        tag=DEAD,
        why="A quote-count line the MCP Agents pane no longer renders (`be325728`). "
            "Both CLDR forms are orphaned together, which is the normal shape: the "
            "call site wrote the base and took the whole family with it.",
        leaves="""
            quotes_one quotes_other
        """,  # 2
    ),
    "doctor.": _Block(
        tag=UNWIRED,
        why="The whole `doctor` namespace, born orphaned: `git log -S` finds no "
            "commit that ever wrote one of these literals at a call site. The "
            "Diagnostics menu and `doctor.py` are English by decision (register item "
            "13), so the file anticipates a translation the surface rule has since "
            "decided against.",
        leaves="""
            checkFail checkOk checkWarn heading summary.allPassed
            summary.issuesFound
        """,  # 6
    ),
    "server.": _Block(
        tag=UNWIRED,
        why="Born orphaned, same shape: `server.error.*` and `server.status.*` have "
            "no call site in any commit. `server.statusPage.*` in the same file IS "
            "live (`status_page.py` reads eleven of them), which is why this entry "
            "pins leaves rather than the namespace.",
        leaves="""
            error.badRequest error.internal error.notFound
            status.degraded status.healthy
        """,  # 5
    ),
    "common.emptyState.": _Block(
        tag=DEAD,
        why="The pre-pipeline empty state names its own key now; `postZeroQuotes`, the "
            "sibling in the same block, is still live. One key, and the reason it is "
            "worth a line: a two-key block where one is read is exactly the shape a "
            "namespace-level sweep cannot see.",
        leaves="""
            prePipeline
        """,  # 1
    ),
    "desktop.menu.": _Block(
        tag=DEAD,
        why="The live verb is `removeFromSidebar`, at three call sites; `delete` is "
            "the wording it replaced, and the distinction matters enough that the "
            "old noun should not sit around waiting to be reached for again.",
        leaves="""
            project.delete
        """,  # 1
    ),
    "pipeline.": _Block(
        tag=UNWIRED,
        why="The whole four-key `pipeline` namespace, born orphaned. It is "
            "unreachable from the desktop target by construction "
            "(`I18n.unloadedOnDiskNamespaces`) and has no Python call site; the CLI "
            "prints these lines as English literals, by design.",
        leaves="""
            done stageComplete stageStart start
        """,  # 4
    ),
    "settings.configReference.": _Block(
        tag=DEAD,
        why="A copy confirmation the config reference no longer shows. One key out of "
            "the 76 in this block, every other one of which is read bare through "
            "`useTranslation(\"settings\")` — the case that made the namespace rule "
            "necessary.",
        leaves="""
            copied
        """,  # 1
    ),
}


def _registered() -> dict[str, str]:
    """Every excused key, mapped to the block prefix that excuses it."""
    out: dict[str, str] = {}
    for prefix, block in _KNOWN_ORPHANS.items():
        for leaf in block.leaves:
            out[prefix + leaf] = prefix
    return out


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


def test_no_unregistered_orphan() -> None:
    """A key nothing reads, that nobody has said why about.

    This is the whole gate. It is green at HEAD by construction and red the
    moment a key lands with no call site — row 23's shape, whether the key is a
    new leaf inside a block already excused or a block of its own.
    """
    registered = _registered()
    new = [key for key in orphans() if key not in registered]
    assert not new, (
        f"{len(new)} locale key(s) in `en` that no surface reads:\n  "
        + "\n  ".join(new)
        + "\n\nEach will be translated into 21 locales and rendered nowhere — "
        "failure class 5 in docs/i18n-defects.md. Wire a call site, delete the "
        "key from every locale (block-scoped prune, never a file-wide regex on "
        "the bare name), or add it to _KNOWN_ORPHANS with a tag and a reason. "
        "If the reader is real and this gate cannot see it, say which "
        "under-approximation it fell through — the module docstring lists them."
    )


def test_the_register_has_not_gone_stale() -> None:
    """An excused key that is now read, or gone, must leave the register.

    This is what makes the list shrink-or-hold rather than a place debt
    accumulates: the slack cannot be re-spent on a different key, because the
    register pins leaves and not a count.
    """
    live = set(orphans())
    present = set(_en_keys())
    resolved = sorted(key for key in _registered() if key not in live)
    assert not resolved, (
        "These keys are excused in _KNOWN_ORPHANS and are no longer orphans "
        "— they now have a reader, or they have been deleted. Remove them "
        "from the register in the same commit:\n  "
        + "\n  ".join(
            f"{key} ({'deleted' if key not in present else 'now read'})"
            for key in resolved
        )
    )


def test_every_block_is_classified() -> None:
    """A register entry with no tag and no reason is an allow-list entry.

    `docs/i18n-defects.md` item 4 is the standing objection to those. The
    difference here is the polarity — this list is what is *excused* — and the
    reason is what keeps it honest.
    """
    for prefix, block in sorted(_KNOWN_ORPHANS.items()):
        assert block.tag in _TAGS, f"{prefix}: unknown tag {block.tag!r}"
        assert len(block.why.split()) >= 12, (
            f"{prefix}: the reason is too short to be one. Name the commit that "
            f"removed the reader, or the decision that means there is not one."
        )
        assert block.leaves, f"{prefix}: excuses nothing — delete the entry"
        assert all("." not in leaf.split(".")[0] for leaf in block.leaves)


def test_no_key_is_excused_twice() -> None:
    """Overlapping prefixes would let a leaf hide under either, and a stale
    entry under one of them would never be reported."""
    seen: dict[str, str] = {}
    for prefix, block in _KNOWN_ORPHANS.items():
        for leaf in block.leaves:
            key = prefix + leaf
            assert key not in seen, f"{key} excused by both {seen[key]} and {prefix}"
            seen[key] = prefix


# --------------------------------------------------------------------------
# Proof that it bites. A gate that passes on arrival has demonstrated nothing,
# so each of these mutates what the gate reads and asserts the shape of the
# failure — never by touching a real locale file.
# --------------------------------------------------------------------------


def test_it_would_have_caught_row_23() -> None:
    """Replay the defect, against the tree as it stood before the fix.

    Row 23 is `desktop.cloudImport.error*`: ten keys translated into 21 locales
    with no reader, for five weeks. Injecting one today proves nothing, because
    the *fix* created a reader for the whole family — `CloudImportSource:90`
    composes `"desktop.cloudImport.error" + rawValue…`, so the composed-prefix
    rule now forgives every leaf under it, correctly.

    So the replay removes that composer, which is exactly what was missing in
    August 2026, and asserts the gate names every one of the keys and excuses
    none of them. The count is not pinned: a later pass added the download
    verdicts, and the number is not what is being proved.
    """
    exact, composed = _read_literals()
    keys = _en_keys()
    family = sorted(k for k in keys if k.startswith("desktop.cloudImport.error"))
    assert len(family) >= 10, f"row 23's family has shrunk to {len(family)}"

    pre_fix = frozenset(
        p for p in composed if not p.startswith("desktop.cloudImport.error")
    )
    pre_fix_exact = frozenset(e for e in exact if e not in set(family))
    found = set(_unread(keys, pre_fix_exact, pre_fix))
    missed = [k for k in family if k not in found]
    assert not missed, f"the gate would have missed {missed} in August 2026"
    assert not [k for k in family if k in _registered()], (
        "row 23's keys are excused in the register — they should be live"
    )


def test_a_new_orphan_leaf_in_a_known_block_is_caught() -> None:
    """A key added beside excused ones, in a block with no composer.

    This is what makes the register pin leaves rather than counts: a count
    would absorb this silently, and a *swap* — one key wired, one orphaned, in
    the same commit — invisibly.
    """
    injected = dict(_en_keys())
    injected["desktop.toolbar.somethingNobodyReads"] = "Sidebar"
    found = orphans(injected)
    assert "desktop.toolbar.somethingNobodyReads" in found
    assert "desktop.toolbar.somethingNobodyReads" not in _registered()


def test_a_whole_new_orphan_block_is_caught() -> None:
    """The other half: a block that did not exist before. Row 23 was this."""
    injected = dict(_en_keys())
    injected["desktop.unbuiltSurface.errorNoAccess"] = "You do not have access."
    assert "desktop.unbuiltSurface.errorNoAccess" in orphans(injected)


def test_the_gate_predicate_reports_an_injected_orphan() -> None:
    """The gate's own expression, not just the detector under it."""
    registered = _registered()
    injected = dict(_en_keys())
    injected["desktop.toolbar.madeUpForThisTest"] = "x"
    new = [key for key in orphans(injected) if key not in registered]
    assert new == ["desktop.toolbar.madeUpForThisTest"], (
        "the gate's own predicate no longer reports an injected orphan"
    )


def test_a_computed_prefix_forgives_its_whole_family() -> None:
    """The blind spot, pinned rather than left to be rediscovered.

    Once a composer exists, every leaf under its prefix is forgiven — including
    one nothing reaches. That is the price of never false-alarming on live
    code, and it means a family behind a composer is guarded by its enum's own
    round-trip test (`test_cloud_fetch_failure_keys.py`), not by this file.
    """
    injected = dict(_en_keys())
    injected["desktop.cloudImport.errorNothingEverProduces"] = "x"
    assert "desktop.cloudImport.errorNothingEverProduces" not in orphans(injected)


# --------------------------------------------------------------------------
# Proof that it does NOT bite on the classes of non-defect. These are the noise
# that kept the corpus-wide version unshippable; each one is pinned so a later
# simplification of the reader cannot quietly reintroduce it.
# --------------------------------------------------------------------------


def test_a_computed_key_is_not_an_orphan() -> None:
    """`i18n.plural("desktop.cloudImport.attendeeCount", count:)` at
    `CloudImportOutlineView.swift:796` reads two keys and writes neither.
    `docs/i18n-defects.md` row 27 called these orphans; they are not, any more.
    """
    exact, composed = _read_literals()
    for key in ("desktop.cloudImport.attendeeCount_one",
                "desktop.cloudImport.attendeeCount_other"):
        assert key in _en_keys()
        assert _is_read(key, exact, composed), f"{key} read as an orphan"


def test_a_key_read_only_by_the_spa_is_not_an_orphan() -> None:
    """`settings.configReference.categories.llm` is written bare at
    `SettingsPanel.tsx:56` and resolved by `useTranslation("settings")`. There
    are 76 keys in that one block; a namespace-strict reader loses them all."""
    exact, composed = _read_literals()
    key = "settings.configReference.categories.llm"
    assert key in _en_keys()
    assert _is_read(key, exact, composed)


def test_a_key_read_only_by_python_is_not_an_orphan() -> None:
    """The `preflight` namespace is reached by `bristlenose --lang=de run …`
    and by nothing else — 34 keys that a Swift-only or SPA-only sweep loses."""
    orphaned = [key for key in orphans() if key.startswith("preflight.")]
    assert not orphaned, f"preflight is a live Python surface: {orphaned}"


def test_a_key_inside_a_swift_interpolation_is_not_an_orphan() -> None:
    """`GeneralSettingsView.swift:157` reads `settings.general.fallbackNote`
    from inside a Swift interpolation. A paired-quote scan loses the inner key
    and reports a live call site as dead; `_KEY_TOKEN` is why it does not."""
    exact, composed = _read_literals()
    assert _is_read("settings.general.fallbackNote", exact, composed)


def test_pseudo_keys_never_reach_the_gate() -> None:
    """`_comment_*` and `_divergent_*` are notes to maintainers. They were
    demanded from all 21 locales once (register item 15) precisely because a
    gate could not tell them from strings."""
    keys = _en_keys()
    assert keys, "the corpus read empty — did the locale layout move?"
    leaves = [k.rsplit(".", 1)[-1] for k in keys]
    assert not [x for x in leaves if x.startswith(("_comment", "_divergent"))]


def test_the_corpus_is_not_empty() -> None:
    """The failure this gate is most likely to die of is silence: a moved
    directory makes every key an orphan, or — worse, because it is green — an
    empty key set makes none of them one."""
    files = _corpus_files()
    assert len(files) > 300, f"only {len(files)} corpus files — did a surface move?"
    exact, composed = _read_literals()
    assert len(exact) > 5000, f"only {len(exact)} literals — is the scanner reading?"
    assert len(composed) > 100, f"only {len(composed)} composed prefixes"
    assert len(_en_keys()) > 1000, "en shipped fewer keys than any release has"
    assert set(_NAMESPACES) >= {"cli", "common", "desktop", "enums", "settings"}


@pytest.mark.parametrize("tag", sorted(_TAGS))
def test_each_tag_is_used(tag: str) -> None:
    """A tag nothing carries is a classification that stopped being true."""
    assert any(block.tag == tag for block in _KNOWN_ORPHANS.values()), (
        f"no block is tagged {tag!r} any more — delete the tag or the claim"
    )
