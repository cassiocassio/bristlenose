"""Trust gate: no code path can send an image to a model (trust map rows 34 and 36).

``docs/design-screens.md`` §4: Bristlenose never sends participants' screens to an LLM on its own.
That is a statement about reach, so it is pinned two ways. The provider-facing entry point takes
text only, and no module builds a provider's image content block (Claude's ``"type": "image"``,
ChatGPT's ``image_url`` / ``input_image``, Gemini's ``inline_data``). Screens and frames are
produced and served as data URLs in route responses, which is a different path.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import bristlenose
from bristlenose.llm.client import LLMClient

_IMAGE_MARKERS = re.compile(
    r"image_url|input_image|inline_data|[\"']type[\"']\s*:\s*[\"']image[\"']|\bImagePart\b"
)
_ROOT = Path(bristlenose.__file__).parent


def _hits(source: str) -> list[str]:
    return _IMAGE_MARKERS.findall(source)


def test_the_scanner_flags_each_provider_shape() -> None:
    for snippet in (
        '{"type": "image", "source": {}}',
        "{'type': 'image'}",
        '{"type": "image_url", "image_url": {"url": u}}',
        '{"type": "input_image"}',
        '{"inline_data": {"mime_type": "image/png"}}',
    ):
        assert _hits(snippet), snippet


def test_no_module_builds_an_image_content_block() -> None:
    files = [p for p in _ROOT.rglob("*.py") if "static" not in p.parts]
    assert len(files) > 100, "the scan found nothing to read"
    offenders = {
        str(p.relative_to(_ROOT)): _hits(p.read_text(encoding="utf-8")) for p in files
        if _hits(p.read_text(encoding="utf-8"))
    }
    assert not offenders, offenders


def test_the_provider_entry_point_takes_text_only() -> None:
    params = set(inspect.signature(LLMClient.analyze).parameters)
    assert params == {
        "self", "system_prompt", "user_prompt", "response_model", "max_tokens",
        "prompt_template",
    }, params
