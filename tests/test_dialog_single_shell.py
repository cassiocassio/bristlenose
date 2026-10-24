"""Every modal in the report draws through one shell, Dialog.tsx.

Until 24 Oct 2026 the SPA had ten lightboxes in three CSS families, each
hand-rolling its backdrop, Escape, focus and portal, and they had drifted:
some had no Escape, some no dialog role, some no inert page behind, and three
different backdrops. Dialog.tsx and atoms/modal.css are now the only places a
modal's backdrop is drawn; this keeps it that way, so the next dialog cannot
quietly grow its own.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
THEME = ROOT / "bristlenose" / "theme"
SHELL = SRC / "components" / "Dialog.tsx"


def _components() -> list[Path]:
    return [
        p
        for p in SRC.rglob("*.tsx")
        if not p.name.endswith(".test.tsx") and "__tests__" not in p.parts
    ]


def test_only_the_shell_draws_a_modal_backdrop_or_marks_a_dialog_modal() -> None:
    offenders = []
    for path in _components():
        if path == SHELL:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in ('"bn-overlay', "`bn-overlay"):
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)}: {needle}")
        # The JSX attribute, not a selector reading it: the Discussion and
        # Screens lenses look for `[aria-modal="true"]` to leave a dialog's keys alone.
        if re.search(r"(?<!\[)aria-modal=", text):
            offenders.append(f"{path.relative_to(ROOT)}: aria-modal")
    assert not offenders, (
        "A modal draws its own backdrop instead of using Dialog.tsx:\n  " + "\n  ".join(offenders)
    )


def test_the_shell_is_what_it_claims() -> None:
    # The gate above passes vacuously if the shell itself stops drawing the
    # backdrop, so pin that it does.
    text = SHELL.read_text(encoding="utf-8")
    assert '"bn-overlay"' in text
    assert 'aria-modal="true"' in text
    assert "createPortal" in text


def test_only_the_modal_atom_styles_the_backdrop() -> None:
    # One backdrop rule, and no second full-window scrim under another name:
    # the frosted merge overlay and the AutoCode Review copy were exactly that.
    defining = [
        p.relative_to(ROOT).as_posix()
        for p in THEME.rglob("*.css")
        if re.search(r"^\.bn-overlay\s*\{", p.read_text(encoding="utf-8"), re.M)
    ]
    assert defining == ["bristlenose/theme/atoms/modal.css"]
    for retired in (".merge-overlay", ".codebook-modal-overlay"):
        hits = [
            p.relative_to(ROOT).as_posix()
            for p in list(THEME.rglob("*.css")) + _components()
            if retired in p.read_text(encoding="utf-8")
        ]
        assert not hits, f"{retired} is retired; still named in {hits}"
