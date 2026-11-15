"""Key-shaped text is masked wherever a provider's words leave the call site.

``bristlenose/utils/key_redaction.py`` copies the Mac's patterns verbatim; the
first class reads the Swift source so the two cannot drift. The rest pin each
CALLER (the run log, the events file, the preflight copy), because a helper
nobody calls is green forever.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.utils import key_redaction
from bristlenose.utils.key_redaction import redact_keys

SWIFT = (
    Path(__file__).resolve().parents[1]
    / "desktop/Bristlenose/Bristlenose/BristlenoseShared.swift"
)

# Synthetic keys, built so no literal key shape sits in the source.
ANTHROPIC = "sk-ant-api03-" + "A1b2" * 24
OPENAI = "sk-proj-" + "Zz9_" * 13
GOOGLE = "AIza" + "B3c4d" * 7
AZURE_84 = ("Ab1" * 28)[:84]
AZURE_HEX = "0123456789abcdef" * 2


def _swift_pattern(name: str) -> str:
    """The pattern of ``static let <name>`` in the Swift source, unescaped."""
    src = SWIFT.read_text(encoding="utf-8")
    m = re.search(rf"static let {name} = try! NSRegularExpression\((.*?)options:", src, re.S)
    assert m, f"{name} not found in {SWIFT.name}"
    block = m.group(1)
    # keyRedactionRegex joins an array with "|"; the Azure two concatenate with +.
    joined = ".joined(separator:" in block
    if joined:
        assert '.joined(separator: "|")' in block, "the Swift separator changed"
        block = block.split(".joined(separator:")[0]
    literals = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
    assert literals, f"no string literals in {name}"
    unescaped = [lit.encode().decode("unicode_escape") for lit in literals]
    joiner = "|" if joined else ""
    return joiner.join(unescaped)


class TestSameAsTheMac:
    @pytest.mark.parametrize(
        ("swift_name", "python_name"),
        [
            ("keyRedactionRegex", "KEY_PATTERN"),
            ("azureKeyRedactionRegex", "AZURE_KEY_PATTERN"),
            ("azureHexKeyRedactionRegex", "AZURE_HEX_KEY_PATTERN"),
        ],
    )
    def test_pattern_matches_swift(self, swift_name: str, python_name: str) -> None:
        assert getattr(key_redaction, python_name) == _swift_pattern(swift_name)


class TestShapes:
    @pytest.mark.parametrize("key", [ANTHROPIC, OPENAI, GOOGLE, AZURE_84])
    def test_bare_key_is_masked(self, key: str) -> None:
        out = redact_keys(f"error: echoed {key} back")
        assert key not in out
        assert "***REDACTED***" in out

    @pytest.mark.parametrize(
        "line",
        [f"api-key: {AZURE_HEX}", f'"subscription-key":"{AZURE_HEX}"', f"Bearer {AZURE_HEX}"],
    )
    def test_hex_key_after_a_key_word_is_masked_and_the_word_kept(self, line: str) -> None:
        out = redact_keys(line)
        assert AZURE_HEX not in out
        assert out.endswith(("***REDACTED***", '***REDACTED***"'))

    @pytest.mark.parametrize(
        "line",
        [
            "apim-request-id: 3d1fae88-0000-4000-8000-0123456789ab",  # dashed guid
            f"request {AZURE_HEX} failed",  # 32-hex with no key word
            "commit " + "a" * 40,  # sha-1
            "DeploymentNotFound: The API deployment for this resource does not exist.",
        ],
    )
    def test_ordinary_text_survives(self, line: str) -> None:
        assert redact_keys(line) == line


class TestCallers:
    def test_the_run_log_line_masks_a_key_in_a_bodyless_error(self) -> None:
        from bristlenose.llm.client import failure_summary

        assert OPENAI not in failure_summary(RuntimeError(f"proxy said: key {OPENAI}"))

    def test_the_run_log_line_masks_a_key_in_a_body_message(self) -> None:
        from bristlenose.llm.client import failure_summary

        exc = RuntimeError("x")
        exc.body = {"error": {"message": f"Bad api-key: {AZURE_HEX}"}}  # type: ignore[attr-defined]
        exc.status_code = 401  # type: ignore[attr-defined]
        out = failure_summary(exc)
        assert AZURE_HEX not in out
        assert "status=401" in out

    def test_a_key_straddling_the_500_char_cap_is_masked_not_cut(self) -> None:
        from bristlenose.llm.client import failure_summary

        out = failure_summary(RuntimeError("x" * 480 + " " + ANTHROPIC))
        assert "A1b2A1b2" not in out

    def test_the_events_file_cause_masks_a_key(self) -> None:
        from bristlenose.run_lifecycle import categorise_exception

        cause = categorise_exception(RuntimeError(f"gateway echoed {GOOGLE}"))
        assert GOOGLE not in cause.message

    def test_the_preflight_copy_masks_a_key(self) -> None:
        from bristlenose.preflight.api_key import ValidationResult

        r = ValidationResult(ok=False, raw_message=f"401 invalid key {AZURE_84}")
        assert AZURE_84 not in r.raw_message
        assert r.raw_message.startswith("401 invalid key")
