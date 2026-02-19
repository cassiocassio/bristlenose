"""Tests for the prompt loader (bristlenose.llm.prompts)."""

from __future__ import annotations

import re

import pytest

from bristlenose.llm.prompts import _PROMPTS_DIR, PromptPair, get_prompt

PROMPT_NAMES = [
    "speaker-identification",
    "topic-segmentation",
    "quote-extraction",
    "quote-clustering",
    "thematic-grouping",
]

EXPECTED_VARIABLES: dict[str, set[str]] = {
    "speaker-identification": {"transcript_sample", "speaker_list"},
    "topic-segmentation": {"transcript_text"},
    "quote-extraction": {"topic_boundaries", "transcript_text"},
    "quote-clustering": {"quotes_json"},
    "thematic-grouping": {"quotes_json"},
}

_VAR_RE = re.compile(r"\{(\w+)\}")


class TestPromptLoading:
    """Every prompt file loads and contains expected sections."""

    @pytest.mark.parametrize("name", PROMPT_NAMES)
    def test_file_exists(self, name: str) -> None:
        path = _PROMPTS_DIR / f"{name}.md"
        assert path.exists(), f"Missing prompt file: {path}"

    @pytest.mark.parametrize("name", PROMPT_NAMES)
    def test_loads_successfully(self, name: str) -> None:
        pair = get_prompt(name)
        assert isinstance(pair, PromptPair)

    @pytest.mark.parametrize("name", PROMPT_NAMES)
    def test_non_empty_sections(self, name: str) -> None:
        pair = get_prompt(name)
        assert len(pair.system) > 0, f"{name}: empty system prompt"
        assert len(pair.user) > 0, f"{name}: empty user prompt"

    @pytest.mark.parametrize("name", PROMPT_NAMES)
    def test_expected_variables_present(self, name: str) -> None:
        pair = get_prompt(name)
        found_vars = set(_VAR_RE.findall(pair.user))
        expected = EXPECTED_VARIABLES[name]
        assert expected.issubset(found_vars), (
            f"{name}: missing variables {expected - found_vars}"
        )

    @pytest.mark.parametrize("name", PROMPT_NAMES)
    def test_format_does_not_raise(self, name: str) -> None:
        """str.format() with dummy values must not raise KeyError."""
        dummy = {
            "transcript_sample": "hello",
            "speaker_list": "A, B",
            "transcript_text": "text",
            "topic_boundaries": "bounds",
            "quotes_json": "[]",
        }
        pair = get_prompt(name)
        expected = EXPECTED_VARIABLES[name]
        kwargs = {k: dummy[k] for k in expected}
        formatted = pair.user.format(**kwargs)
        assert len(formatted) > 0

    @pytest.mark.parametrize("name", PROMPT_NAMES)
    def test_no_double_braces(self, name: str) -> None:
        """No accidental {{ or }} that would break str.format()."""
        pair = get_prompt(name)
        assert "{{" not in pair.user, f"{name}: unexpected {{{{ in user prompt"
        assert "}}" not in pair.user, f"{name}: unexpected }}}} in user prompt"


class TestBackwardCompatibility:
    """Old-style constant imports still work."""

    def test_topic_segmentation_prompt(self) -> None:
        from bristlenose.llm.prompts import TOPIC_SEGMENTATION_PROMPT
        assert isinstance(TOPIC_SEGMENTATION_PROMPT, str)
        assert "{transcript_text}" in TOPIC_SEGMENTATION_PROMPT

    def test_speaker_identification_prompt(self) -> None:
        from bristlenose.llm.prompts import SPEAKER_IDENTIFICATION_PROMPT
        assert isinstance(SPEAKER_IDENTIFICATION_PROMPT, str)
        assert "{transcript_sample}" in SPEAKER_IDENTIFICATION_PROMPT

    def test_quote_extraction_prompt(self) -> None:
        from bristlenose.llm.prompts import QUOTE_EXTRACTION_PROMPT
        assert isinstance(QUOTE_EXTRACTION_PROMPT, str)
        assert "{transcript_text}" in QUOTE_EXTRACTION_PROMPT

    def test_quote_clustering_prompt(self) -> None:
        from bristlenose.llm.prompts import QUOTE_CLUSTERING_PROMPT
        assert isinstance(QUOTE_CLUSTERING_PROMPT, str)
        assert "{quotes_json}" in QUOTE_CLUSTERING_PROMPT

    def test_thematic_grouping_prompt(self) -> None:
        from bristlenose.llm.prompts import THEMATIC_GROUPING_PROMPT
        assert isinstance(THEMATIC_GROUPING_PROMPT, str)
        assert "{quotes_json}" in THEMATIC_GROUPING_PROMPT

    def test_nonexistent_attribute_raises(self) -> None:
        with pytest.raises(AttributeError):
            from bristlenose.llm import prompts
            _ = prompts.NONEXISTENT_PROMPT  # type: ignore[attr-defined]


class TestErrorHandling:
    """Loader raises useful errors for bad files."""

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            get_prompt("nonexistent-prompt")
