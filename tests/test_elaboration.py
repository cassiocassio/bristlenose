"""Tests for the signal elaboration service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bristlenose.server.elaboration import (
    VALID_PATTERNS,
    _normalise_pattern,
    compute_content_hash,
    compute_signal_key,
    format_signals_for_prompt,
    generate_elaborations,
)

# ---------------------------------------------------------------------------
# compute_signal_key
# ---------------------------------------------------------------------------


class TestComputeSignalKey:
    def test_format(self) -> None:
        assert compute_signal_key("section", "Homepage", "Discoverability") == (
            "section|Homepage|Discoverability"
        )

    def test_theme_source(self) -> None:
        assert compute_signal_key("theme", "Onboarding", "Feedback") == (
            "theme|Onboarding|Feedback"
        )


# ---------------------------------------------------------------------------
# compute_content_hash
# ---------------------------------------------------------------------------


class TestComputeContentHash:
    def test_deterministic(self) -> None:
        h1 = compute_content_hash(["quote A", "quote B"], ["tag1", "tag2"])
        h2 = compute_content_hash(["quote A", "quote B"], ["tag1", "tag2"])
        assert h1 == h2

    def test_order_independent(self) -> None:
        h1 = compute_content_hash(["quote B", "quote A"], ["tag2", "tag1"])
        h2 = compute_content_hash(["quote A", "quote B"], ["tag1", "tag2"])
        assert h1 == h2

    def test_different_quotes_different_hash(self) -> None:
        h1 = compute_content_hash(["quote A"], ["tag1"])
        h2 = compute_content_hash(["quote B"], ["tag1"])
        assert h1 != h2

    def test_different_tags_different_hash(self) -> None:
        h1 = compute_content_hash(["quote A"], ["tag1"])
        h2 = compute_content_hash(["quote A"], ["tag2"])
        assert h1 != h2

    def test_returns_hex_string(self) -> None:
        h = compute_content_hash(["q"], ["t"])
        assert len(h) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# _normalise_pattern
# ---------------------------------------------------------------------------


class TestNormalisePattern:
    @pytest.mark.parametrize("pattern", sorted(VALID_PATTERNS))
    def test_valid_patterns(self, pattern: str) -> None:
        assert _normalise_pattern(pattern) == pattern

    def test_uppercase(self) -> None:
        assert _normalise_pattern("Success") == "success"

    def test_whitespace(self) -> None:
        assert _normalise_pattern("  gap  ") == "gap"

    def test_unknown_defaults_to_tension(self) -> None:
        assert _normalise_pattern("mixed") == "tension"

    def test_empty_defaults_to_tension(self) -> None:
        assert _normalise_pattern("") == "tension"


# ---------------------------------------------------------------------------
# format_signals_for_prompt
# ---------------------------------------------------------------------------


def _make_signal_quote(
    text: str = "test quote",
    pid: str = "p1",
    sid: str = "s1",
    tags: list[str] | None = None,
) -> MagicMock:
    q = MagicMock()
    q.text = text
    q.participant_id = pid
    q.session_id = sid
    q.start_seconds = 0.0
    q.intensity = 1
    q.tag_names = tags or []
    q.segment_index = -1
    return q


def _make_signal(
    location: str = "Homepage",
    group_name: str = "Discoverability",
    source_type: str = "section",
    quotes: list[MagicMock] | None = None,
) -> MagicMock:
    sig = MagicMock()
    sig.location = location
    sig.source_type = source_type
    sig.group_name = group_name
    sig.quotes = quotes or []
    sig.composite_signal = 0.5
    sig.colour_set = "ux"
    return sig


def _make_template(
    groups: list[tuple[str, str, list[tuple[str, str, str, str]]]] | None = None,
) -> MagicMock:
    """Create a mock template.

    groups: [(name, subtitle, [(tag_name, definition, apply_when, not_this), ...])]
    """
    template = MagicMock()
    template.groups = []
    for name, subtitle, tags in (groups or []):
        g = MagicMock()
        g.name = name
        g.subtitle = subtitle
        g.tags = []
        for tname, defn, apply_when, not_this in tags:
            t = MagicMock()
            t.name = tname
            t.definition = defn
            t.apply_when = apply_when
            t.not_this = not_this
            g.tags.append(t)
        template.groups.append(g)
    return template


class TestFormatSignalsForPrompt:
    def test_includes_section_and_group(self) -> None:
        sig = _make_signal(
            location="Product listing",
            group_name="Discoverability",
            quotes=[_make_signal_quote(tags=["visible action"])],
        )
        template = _make_template([
            ("Discoverability", "Can the user figure out what actions are possible?", [
                ("visible action", "The interface makes possibilities obvious", "", ""),
            ]),
        ])
        result = format_signals_for_prompt([sig], template)
        assert "Section: Product listing" in result
        assert "Discoverability" in result
        assert "Can the user figure out what actions are possible?" in result

    def test_includes_tag_definitions(self) -> None:
        sig = _make_signal(
            quotes=[_make_signal_quote(tags=["hidden feature"])],
        )
        template = _make_template([
            ("Discoverability", "Can the user find actions?", [
                ("hidden feature", "A useful capability exists but the user can't find it",
                 "Participant misses an available action", "Not confusion about the action"),
            ]),
        ])
        result = format_signals_for_prompt([sig], template)
        assert "hidden feature" in result
        assert "A useful capability exists but the user can't find it" in result
        assert "Participant misses an available action" in result

    def test_includes_quotes_with_tags(self) -> None:
        sig = _make_signal(quotes=[
            _make_signal_quote(text="I can't find it", pid="p2", tags=["hidden feature"]),
        ])
        template = _make_template([
            ("Discoverability", "lens", [("hidden feature", "def", "", "")]),
        ])
        result = format_signals_for_prompt([sig], template)
        assert "[p2]" in result
        assert "I can't find it" in result
        assert "[tag: hidden feature]" in result

    def test_multiple_signals_numbered(self) -> None:
        sig0 = _make_signal(location="Home", quotes=[_make_signal_quote()])
        sig1 = _make_signal(location="Cart", quotes=[_make_signal_quote()])
        template = _make_template([("Discoverability", "lens", [])])
        result = format_signals_for_prompt([sig0, sig1], template)
        assert "### Signal 0" in result
        assert "### Signal 1" in result

    def test_missing_group_in_template(self) -> None:
        sig = _make_signal(
            group_name="Unknown Group",
            quotes=[_make_signal_quote()],
        )
        template = _make_template([])
        result = format_signals_for_prompt([sig], template)
        assert "Group: Unknown Group" in result


# ---------------------------------------------------------------------------
# generate_elaborations — integration tests with mocked LLM
# ---------------------------------------------------------------------------


def _make_settings(provider: str = "anthropic", api_key: str = "test-key") -> MagicMock:
    settings = MagicMock()
    settings.llm_provider = provider
    settings.anthropic_api_key = api_key if provider == "anthropic" else ""
    settings.openai_api_key = api_key if provider == "openai" else ""
    settings.azure_api_key = api_key if provider == "azure" else ""
    settings.google_api_key = api_key if provider == "google" else ""
    return settings


class TestGenerateElaborations:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_signals(self) -> None:
        settings = _make_settings()
        db = MagicMock()
        result = await generate_elaborations([], "norman", settings, db, 1)
        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_local_provider(self) -> None:
        settings = _make_settings(provider="local")
        db = MagicMock()
        sig = _make_signal(quotes=[_make_signal_quote()])
        result = await generate_elaborations([sig], "norman", settings, db, 1)
        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_no_api_key(self) -> None:
        settings = _make_settings(provider="anthropic", api_key="")
        db = MagicMock()
        sig = _make_signal(quotes=[_make_signal_quote()])
        result = await generate_elaborations([sig], "norman", settings, db, 1)
        assert result == {}

    @pytest.mark.asyncio
    async def test_cache_hit_no_llm_call(self) -> None:
        """When cache has a matching hash, no LLM call is made."""
        sig = _make_signal(
            location="Homepage", group_name="Discoverability",
            quotes=[_make_signal_quote(text="test", tags=["visible action"])],
        )
        settings = _make_settings()
        expected_key = "section|Homepage|Discoverability"
        expected_hash = compute_content_hash(["test"], ["visible action"])

        # Mock DB to return a cached row
        cache_row = MagicMock()
        cache_row.signal_key = expected_key
        cache_row.content_hash = expected_hash
        cache_row.signal_name = "Discoverability strength"
        cache_row.pattern = "success"
        cache_row.elaboration = "Filters are easy to find || and participants use them."

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [cache_row]

        with patch(
            "bristlenose.server.codebook.get_template",
            return_value=_make_template([("Discoverability", "lens", [])]),
        ):
            result = await generate_elaborations([sig], "norman", settings, db, 1)

        assert expected_key in result
        assert result[expected_key].signal_name == "Discoverability strength"
        assert result[expected_key].pattern == "success"

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self) -> None:
        """When cache is empty, LLM is called and result is cached."""
        sig = _make_signal(
            location="Homepage", group_name="Discoverability",
            quotes=[_make_signal_quote(text="I see it", tags=["visible action"])],
        )
        settings = _make_settings()

        # Mock DB: empty cache
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        # Mock LLM response
        mock_elab = MagicMock()
        mock_elab.signal_index = 0
        mock_elab.signal_name = "Navigation clarity"
        mock_elab.pattern = "success"
        mock_elab.elaboration = "Nav is clear || users find it."

        mock_result = MagicMock()
        mock_result.elaborations = [mock_elab]

        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_result

        with (
            patch(
                "bristlenose.server.codebook.get_template",
                return_value=_make_template([("Discoverability", "lens", [])]),
            ),
            patch(
                "bristlenose.llm.client.LLMClient",
                return_value=mock_client,
            ),
            patch("bristlenose.llm.prompts.get_prompt") as mock_prompt,
        ):
            mock_prompt.return_value.system = "system prompt"
            mock_prompt.return_value.user = "User: {signals_text}"
            result = await generate_elaborations([sig], "norman", settings, db, 1)

        key = "section|Homepage|Discoverability"
        assert key in result
        assert result[key].signal_name == "Navigation clarity"
        assert result[key].pattern == "success"
        assert result[key].elaboration == "Nav is clear || users find it."
        # Verify LLM was called
        mock_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_stale_cache_regenerates(self) -> None:
        """When cache exists but hash differs, LLM is called again."""
        sig = _make_signal(
            location="Home", group_name="Feedback",
            quotes=[_make_signal_quote(text="new quote", tags=["system response"])],
        )
        settings = _make_settings()

        # Cache has wrong hash (stale)
        cache_row = MagicMock()
        cache_row.signal_key = "section|Home|Feedback"
        cache_row.content_hash = "stale_hash_that_wont_match"
        cache_row.signal_name = "Old name"
        cache_row.pattern = "success"
        cache_row.elaboration = "Old elaboration"

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [cache_row]

        # Mock LLM
        mock_elab = MagicMock()
        mock_elab.signal_index = 0
        mock_elab.signal_name = "Feedback strength"
        mock_elab.pattern = "success"
        mock_elab.elaboration = "Feedback is clear || users understand."

        mock_result = MagicMock()
        mock_result.elaborations = [mock_elab]

        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_result

        with (
            patch(
                "bristlenose.server.codebook.get_template",
                return_value=_make_template([("Feedback", "lens", [])]),
            ),
            patch(
                "bristlenose.llm.client.LLMClient",
                return_value=mock_client,
            ),
            patch("bristlenose.llm.prompts.get_prompt") as mock_prompt,
        ):
            mock_prompt.return_value.system = "sys"
            mock_prompt.return_value.user = "{signals_text}"
            result = await generate_elaborations([sig], "norman", settings, db, 1)

        key = "section|Home|Feedback"
        assert key in result
        assert result[key].signal_name == "Feedback strength"
        mock_client.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_returns_cached_only(self) -> None:
        """When LLM call fails, cached results are still returned."""
        sig0 = _make_signal(
            location="Home", group_name="Disco",
            quotes=[_make_signal_quote(text="q1", tags=["t1"])],
        )
        sig1 = _make_signal(
            location="Cart", group_name="Feedback",
            quotes=[_make_signal_quote(text="q2", tags=["t2"])],
        )
        settings = _make_settings()

        # sig0 is cached, sig1 is not
        cached_hash = compute_content_hash(["q1"], ["t1"])
        cache_row = MagicMock()
        cache_row.signal_key = "section|Home|Disco"
        cache_row.content_hash = cached_hash
        cache_row.signal_name = "Disco strength"
        cache_row.pattern = "success"
        cache_row.elaboration = "It works || well."

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [cache_row]

        mock_client = AsyncMock()
        mock_client.analyze.side_effect = RuntimeError("LLM exploded")

        with (
            patch(
                "bristlenose.server.codebook.get_template",
                return_value=_make_template([
                    ("Disco", "lens", []),
                    ("Feedback", "lens", []),
                ]),
            ),
            patch(
                "bristlenose.llm.client.LLMClient",
                return_value=mock_client,
            ),
            patch("bristlenose.llm.prompts.get_prompt") as mock_prompt,
        ):
            mock_prompt.return_value.system = "sys"
            mock_prompt.return_value.user = "{signals_text}"
            result = await generate_elaborations(
                [sig0, sig1], "norman", settings, db, 1,
            )

        # sig0's cached result survives, sig1 is missing
        assert "section|Home|Disco" in result
        assert result["section|Home|Disco"].signal_name == "Disco strength"
        assert "section|Cart|Feedback" not in result

    @pytest.mark.asyncio
    async def test_pattern_normalised_in_result(self) -> None:
        """Pattern from LLM is normalised (e.g., 'Success' -> 'success')."""
        sig = _make_signal(
            location="Home", group_name="Disco",
            quotes=[_make_signal_quote(text="q", tags=["t"])],
        )
        settings = _make_settings()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        mock_elab = MagicMock()
        mock_elab.signal_index = 0
        mock_elab.signal_name = "Disco strength"
        mock_elab.pattern = "SUCCESS"  # uppercase from LLM
        mock_elab.elaboration = "Good || stuff."

        mock_result = MagicMock()
        mock_result.elaborations = [mock_elab]

        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_result

        with (
            patch(
                "bristlenose.server.codebook.get_template",
                return_value=_make_template([("Disco", "lens", [])]),
            ),
            patch(
                "bristlenose.llm.client.LLMClient",
                return_value=mock_client,
            ),
            patch("bristlenose.llm.prompts.get_prompt") as mock_prompt,
        ):
            mock_prompt.return_value.system = "sys"
            mock_prompt.return_value.user = "{signals_text}"
            result = await generate_elaborations([sig], "norman", settings, db, 1)

        assert result["section|Home|Disco"].pattern == "success"

    @pytest.mark.asyncio
    async def test_out_of_range_index_skipped(self) -> None:
        """LLM returning out-of-range signal_index is skipped gracefully."""
        sig = _make_signal(
            location="Home", group_name="Disco",
            quotes=[_make_signal_quote(text="q", tags=["t"])],
        )
        settings = _make_settings()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        mock_elab = MagicMock()
        mock_elab.signal_index = 99  # out of range
        mock_elab.signal_name = "Bad"
        mock_elab.pattern = "gap"
        mock_elab.elaboration = "Bad || stuff."

        mock_result = MagicMock()
        mock_result.elaborations = [mock_elab]

        mock_client = AsyncMock()
        mock_client.analyze.return_value = mock_result

        with (
            patch(
                "bristlenose.server.codebook.get_template",
                return_value=_make_template([("Disco", "lens", [])]),
            ),
            patch(
                "bristlenose.llm.client.LLMClient",
                return_value=mock_client,
            ),
            patch("bristlenose.llm.prompts.get_prompt") as mock_prompt,
        ):
            mock_prompt.return_value.system = "sys"
            mock_prompt.return_value.user = "{signals_text}"
            result = await generate_elaborations([sig], "norman", settings, db, 1)

        assert "section|Home|Disco" not in result
