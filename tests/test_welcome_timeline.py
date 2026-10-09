"""The Welcome window's Session timeline picture draws with the lens's own CSS.

`WelcomeTimelineCSS.swift` is generated from `bristlenose/theme/` so the
illustration's colours and type are the Sessions lens's, not a hand-copied
subset that drifts (which is what the older illustrations carry). A generated
file is only as good as its regeneration, so this fails the moment a theme
file it inlines changes without `scripts/gen-welcome-timeline.py` being rerun.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _gen():
    spec = importlib.util.spec_from_file_location("gen_welcome_timeline", REPO / "scripts/gen-welcome-timeline.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_generated_css_matches_the_theme() -> None:
    gen = _gen()
    assert gen.OUT.read_text(encoding="utf-8") == gen.swift_file(), (
        "WelcomeTimelineCSS.swift is out of date with bristlenose/theme/ — run "
        ".venv/bin/python scripts/gen-welcome-timeline.py"
    )


def test_the_template_reads_the_generated_css() -> None:
    """The generated file is pointless if the template stops interpolating it."""
    src = (REPO / "desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift").read_text(encoding="utf-8")
    body = src[src.index("static func timeline(dark: Bool"):]
    assert r"\(WelcomeTimelineCSS.shipped)" in body.split('"""')[1]


def test_the_template_fills_completely() -> None:
    """The mockup harness fills every interpolation the way Swift does; a new one it
    does not know fails here rather than shipping a harness that shows `\\(…)`."""
    doc = _gen().timeline_document(dark=False, palette="default")
    assert "BN.register" in doc and "session-tapestry.css" in doc
