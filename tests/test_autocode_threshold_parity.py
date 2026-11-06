"""The review dialog and the server agree on the AutoCode cutoffs (two copies of one rule).

The review dialog (``frontend/src/components/ThresholdReviewModal.tsx``) opens at an upper cutoff of
0.70 and a lower of 0.30 on a 0.05 grid (``frontend/src/utils/confidenceStep.ts``); a codebook
applied without stored cutoffs, and the catch-up that applies a quote counting again, must use the
same numbers, or the catch-up accepts or denies on lines the researcher never saw. The server's
constants say they "mirror" the dialog in a comment; nothing held the two to it. The catch-up
shipped ignoring the lower cutoff and float-drifted cutoffs both cost a serious defect each
(30 and 25 Oct 2026), the same shape: one rule, two copies. Same family as
``tests/test_env_name_parity.py``: read the other language's source, do not copy its value.
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.server.autocode import (
    CONFIDENCE_STEPS_PER_UNIT,
    DEFAULT_ACCEPT_THRESHOLD,
    DEFAULT_DENY_THRESHOLD,
)

_SRC = Path(__file__).parent.parent / "frontend" / "src"


def _ts_number(path: Path, name: str) -> float:
    text = path.read_text(encoding="utf-8")
    # A declaration line only: a comment or a string that mentions the name must not win.
    match = re.search(
        rf"^[ \t]*(?:export[ \t]+)?const[ \t]+{name}(?:[ \t]*:[ \t]*number)?[ \t]*="
        rf"[ \t]*([0-9]+(?:\.[0-9]+)?)[ \t]*;", text, re.MULTILINE)
    assert match, (
        f"const {name} = <number>; not found in {path.name}: the parity test must follow a "
        "rename or a change of form, not guess")
    return float(match.group(1))


def test_the_default_upper_cutoff_is_the_dialogs() -> None:
    dialog = _SRC / "components" / "ThresholdReviewModal.tsx"
    assert DEFAULT_ACCEPT_THRESHOLD == _ts_number(dialog, "DEFAULT_UPPER")


def test_the_default_lower_cutoff_is_the_dialogs() -> None:
    dialog = _SRC / "components" / "ThresholdReviewModal.tsx"
    assert DEFAULT_DENY_THRESHOLD == _ts_number(dialog, "DEFAULT_LOWER")


def test_the_cutoff_grid_is_the_sliders() -> None:
    step = _ts_number(_SRC / "utils" / "confidenceStep.ts", "CONFIDENCE_STEP")
    assert CONFIDENCE_STEPS_PER_UNIT == round(1 / step)
