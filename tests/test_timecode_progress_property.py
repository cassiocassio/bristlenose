"""The playback progress variable must not be inherited.

PlayerContext sets --bn-segment-progress on the playing paragraph about four times a second.
Inherited, that restyles every word span under it (about 20 layout passes a tick on a 400-word
paragraph, measured 4 Nov 2026); registered with inherits: false it is one. Only the paragraph's
::before reads it, so nothing depends on inheritance.
"""

from __future__ import annotations

import re
from pathlib import Path

_CSS = Path(__file__).parents[1] / "bristlenose" / "theme" / "atoms" / "timecode.css"


def test_the_progress_variable_is_registered_and_not_inherited() -> None:
    css = _CSS.read_text(encoding="utf-8")
    block = re.search(r"@property\s+--bn-segment-progress\s*\{([^}]*)\}", css)
    assert block, "--bn-segment-progress is no longer registered: it inherits again"
    body = block.group(1)
    assert re.search(r"inherits:\s*false", body)
    assert re.search(r'syntax:\s*"<number>"', body)
    assert re.search(r"initial-value:\s*0", body)


def test_only_a_pseudo_element_reads_it() -> None:
    # If a descendant ever reads the variable, it needs inheritance and this registration breaks it.
    css = _CSS.read_text(encoding="utf-8")
    uses = list(re.finditer(r"var\(--bn-segment-progress", css))
    assert uses
    for m in uses:
        rule_start = css.rfind("}", 0, m.start()) + 1
        selector = css[rule_start:css.index("{", rule_start)]
        assert "::before" in selector, f"{selector.strip()!r} reads the progress variable"
