"""The live check's stage fixture keeps up with the real prompts and schemas.

`scripts/check-providers-live.py --stages` reproduces the six pipeline LLM calls
from `scripts/live_check_fixture.py`. When the speaker-splitting prompt gained
`{prior_context}` and `{first_index}`, and the role schema renamed `speakers`
to `assignments`, the fixture didn't follow, and `--stages` crashed for every
provider (found by the any-llm walks, 23 Oct 2026). The default run uses two
stages that hadn't drifted, so nothing said so. Free: no call is made.
"""

from __future__ import annotations

import sys
import types
import typing
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_check_fixture as fixture  # noqa: E402


@pytest.mark.parametrize("stage", fixture.STAGES, ids=lambda s: s.key)
def test_each_stage_formats_its_real_prompt(stage: fixture.Stage) -> None:
    system, user = stage.prompts()  # a KeyError here is a field the prompt gained
    assert system and user


def _reply(model: type[BaseModel], *, full: bool) -> dict[str, Any]:
    """A reply that validates against ``model``: one of everything, or nothing.

    Built from the schema rather than written out, so it follows a renamed or
    added field instead of drifting the way the fixture did.
    """

    def value(tp: Any) -> Any:
        origin = typing.get_origin(tp)
        if origin is typing.Literal:
            return typing.get_args(tp)[0]
        if origin in (typing.Union, types.UnionType):
            return value(next(a for a in typing.get_args(tp) if a is not type(None)))
        if origin is list:
            return [value(typing.get_args(tp)[0])] if full else []
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            return _reply(tp, full=full)
        # bool before int: bool is an int subclass. 0.5 sits inside a 0-1 confidence.
        defaults = {bool: True, int: 1 if full else 0, float: 0.5, str: "x" if full else ""}
        return defaults[tp]

    return {name: value(f.annotation) for name, f in model.model_fields.items()}


@pytest.mark.parametrize("stage", fixture.STAGES, ids=lambda s: s.key)
def test_each_usefulness_check_runs_against_its_real_schema(stage: fixture.Stage) -> None:
    # An AttributeError here is a field the schema renamed under the check.
    full = stage.model.model_validate(_reply(stage.model, full=True))
    empty = stage.model.model_validate(_reply(stage.model, full=False))
    assert stage.substantive(full), f"{stage.key}: a reply with one of everything is not usable"
    assert not stage.substantive(empty), f"{stage.key}: an empty reply passes as usable"
