"""The live check's stage fixture keeps up with the real prompts and schemas.

`scripts/check-providers-live.py --stages` reproduces the six pipeline LLM calls
from `scripts/live_check_fixture.py`. When the speaker-splitting prompt gained
`{prior_context}` and `{first_index}`, and the role schema renamed `speakers`
to `assignments`, the fixture didn't follow, and `--stages` crashed for every
provider (found by the any-llm walks, 23 Oct 2026). The default run uses two
stages that hadn't drifted, so nothing said so. Free: no call is made.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import live_check_fixture as fixture  # noqa: E402


@pytest.mark.parametrize("stage", fixture.STAGES, ids=lambda s: s.key)
def test_each_stage_formats_its_real_prompt(stage: fixture.Stage) -> None:
    system, user = stage.prompts()  # a KeyError here is a field the prompt gained
    assert system and user


@pytest.mark.parametrize("stage", fixture.STAGES, ids=lambda s: s.key)
def test_each_usefulness_check_reads_real_schema_fields(stage: fixture.Stage) -> None:
    used = re.findall(r"r\.(\w+)", inspect.getsource(stage.substantive))
    assert used, stage.key
    assert set(used) <= set(stage.model.model_fields), (stage.key, used)
