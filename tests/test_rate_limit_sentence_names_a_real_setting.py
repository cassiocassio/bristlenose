"""The rate-limit preflight line points at a setting that exists (N119 follow-up, 1 Nov 2026).

It told researchers to "reduce `llm_concurrency` in your bristlenose.toml" when nothing reads that
file. The CLI reader's remedy is the environment variable the settings do read.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bristlenose.config import BristlenoseSettings

_TEXT = Path("bristlenose/locales/en/preflight.json").read_text(encoding="utf-8")


def test_the_rate_limit_line_names_the_environment_variable() -> None:
    line = json.loads(_TEXT)["api_key"]["rate_limit"]
    assert "BRISTLENOSE_LLM_CONCURRENCY" in line


def test_no_preflight_line_sends_anyone_to_a_toml_file() -> None:
    assert "toml" not in _TEXT


def test_every_setting_the_preflight_names_is_a_real_environment_variable() -> None:
    names = re.findall(r"BRISTLENOSE_[A-Z_]+", _TEXT)
    assert names
    for name in names:
        assert name.removeprefix("BRISTLENOSE_").lower() in BristlenoseSettings.model_fields, name
