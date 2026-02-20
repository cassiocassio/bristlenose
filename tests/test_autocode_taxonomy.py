"""Tests for AutoCode taxonomy formatting, quote batching, and tag resolution."""

from __future__ import annotations

from bristlenose.server.autocode import (
    BATCH_SIZE,
    QuoteBatchItem,
    build_quote_batch,
    build_tag_name_map,
    build_tag_taxonomy,
    resolve_tag_name_to_id,
)
from bristlenose.server.codebook import CodebookTemplate, TemplateGroup, TemplateTag, get_template

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tag(name: str, *, definition: str = "", apply_when: str = "", not_this: str = "") -> TemplateTag:
    return TemplateTag(name=name, definition=definition, apply_when=apply_when, not_this=not_this)


def _make_group(
    name: str, subtitle: str, colour_set: str, tags: list[TemplateTag]
) -> TemplateGroup:
    return TemplateGroup(name=name, subtitle=subtitle, colour_set=colour_set, tags=tags)


def _make_template(
    *,
    template_id: str = "test",
    title: str = "Test Codebook",
    preamble: str = "",
    groups: list[TemplateGroup] | None = None,
) -> CodebookTemplate:
    return CodebookTemplate(
        id=template_id,
        title=title,
        author="Test Author",
        description="Test description",
        author_bio="",
        author_links=[],
        preamble=preamble,
        groups=groups or [],
    )


def _make_quote(index: int, text: str = "Sample quote text") -> QuoteBatchItem:
    return QuoteBatchItem(
        db_id=index + 100,
        text=text,
        session_id=f"s{(index // 5) + 1}",
        participant_id=f"p{(index % 3) + 1}",
        topic_label="Dashboard" if index % 2 == 0 else "",
        sentiment="frustration" if index % 3 == 0 else "",
    )


# ---------------------------------------------------------------------------
# build_tag_taxonomy
# ---------------------------------------------------------------------------


class TestBuildTagTaxonomy:
    """Tests for formatting codebook templates into prompt text."""

    def test_garrett_has_all_20_tags(self) -> None:
        """All 20 Garrett sub-tags appear in the formatted taxonomy."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        expected_tags = [
            "user need", "business objective", "success metric", "value proposition",
            "feature requirement", "content requirement", "priority", "scope creep",
            "interaction design", "information architecture", "navigation pattern", "task flow",
            "interface layout", "wireframe issue", "convention", "component placement",
            "visual design", "sensory experience", "brand alignment", "aesthetic reaction",
        ]
        for tag_name in expected_tags:
            assert f"**{tag_name}**" in taxonomy, f"Missing tag: {tag_name}"

    def test_garrett_has_all_5_groups(self) -> None:
        """All 5 Garrett groups appear as headers."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        for group_name in ("Strategy", "Scope", "Structure", "Skeleton", "Surface"):
            assert f"### {group_name}" in taxonomy, f"Missing group: {group_name}"

    def test_includes_preamble_reference(self) -> None:
        """Preamble text is available separately (not in taxonomy itself)."""
        template = get_template("garrett")
        assert template is not None
        assert "mutually exclusive" in template.preamble

    def test_includes_not_this(self) -> None:
        """Tags with not_this have it in the formatted output."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        # Garrett's "user need" has not_this mentioning "feature requirement"
        assert "Not this:" in taxonomy
        assert "feature requirement" in taxonomy.lower()

    def test_includes_apply_when(self) -> None:
        """Tags with apply_when have it in the formatted output."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        assert "Apply when:" in taxonomy

    def test_includes_definition(self) -> None:
        """Tags with definition have it after the bolded name."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        # Definitions follow the tag name with an em dash
        assert "**user need** —" in taxonomy

    def test_tags_without_prompts_name_only(self) -> None:
        """Tags without discrimination prompts get name-only entries."""
        template = _make_template(
            groups=[
                _make_group("Group A", "Subtitle A", "ux", [
                    _make_tag("bare tag"),  # no definition/apply_when/not_this
                ]),
            ],
        )
        taxonomy = build_tag_taxonomy(template)
        assert "**bare tag**" in taxonomy
        assert "Apply when:" not in taxonomy
        assert "Not this:" not in taxonomy

    def test_norman_tags_have_full_prompts(self) -> None:
        """Norman template has discrimination prompts for all tags."""
        template = get_template("norman")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        assert "**visible action**" in taxonomy
        assert "**system response**" in taxonomy
        # Norman now has full discrimination prompts
        assert "Apply when:" in taxonomy
        assert "Not this:" in taxonomy

    def test_empty_template(self) -> None:
        """Template with no groups returns empty string."""
        template = _make_template(groups=[])
        taxonomy = build_tag_taxonomy(template)
        assert taxonomy == ""

    def test_group_subtitles_present(self) -> None:
        """Group subtitles appear in the header line."""
        template = get_template("garrett")
        assert template is not None
        taxonomy = build_tag_taxonomy(template)
        assert "Is the product solving the right problem" in taxonomy


# ---------------------------------------------------------------------------
# build_quote_batch
# ---------------------------------------------------------------------------


class TestBuildQuoteBatch:
    """Tests for formatting quotes into prompt text."""

    def test_formats_numbered_quotes(self) -> None:
        """Quotes are 0-indexed with correct numbering."""
        quotes = [_make_quote(i, f"Quote number {i}") for i in range(3)]
        text = build_quote_batch(quotes)
        assert '0. [s1/p1]' in text
        assert '1. [s1/p2]' in text
        assert '2. [s1/p3]' in text

    def test_includes_topic_label(self) -> None:
        """Topic label appears when present."""
        quotes = [_make_quote(0)]  # index 0 gets topic_label="Dashboard"
        text = build_quote_batch(quotes)
        assert "[Dashboard]" in text

    def test_includes_sentiment(self) -> None:
        """Sentiment appears when present."""
        quotes = [_make_quote(0)]  # index 0 gets sentiment="frustration"
        text = build_quote_batch(quotes)
        assert "[frustration]" in text

    def test_omits_empty_metadata(self) -> None:
        """Empty topic/sentiment are omitted, not shown as empty brackets."""
        quote = QuoteBatchItem(
            db_id=1, text="Hello", session_id="s1", participant_id="p1",
            topic_label="", sentiment="",
        )
        text = build_quote_batch([quote])
        assert "[]" not in text

    def test_quote_text_in_quotes(self) -> None:
        """Quote text is wrapped in double quotes."""
        quotes = [_make_quote(0, "I can't find the filter")]
        text = build_quote_batch(quotes)
        assert '"I can\'t find the filter"' in text

    def test_full_batch_of_25(self) -> None:
        """A full 25-item batch formats correctly."""
        quotes = [_make_quote(i) for i in range(BATCH_SIZE)]
        text = build_quote_batch(quotes)
        assert "24." in text


# ---------------------------------------------------------------------------
# resolve_tag_name_to_id
# ---------------------------------------------------------------------------


class TestResolveTagName:
    """Tests for mapping LLM tag names to TagDefinition IDs."""

    def test_exact_match(self) -> None:
        """Exact lowercase match resolves correctly."""
        tag_map = {"user need": 1, "feature requirement": 2}
        assert resolve_tag_name_to_id("user need", tag_map) == 1

    def test_case_insensitive(self) -> None:
        """Case differences are normalised."""
        tag_map = {"user need": 1}
        assert resolve_tag_name_to_id("User Need", tag_map) == 1
        assert resolve_tag_name_to_id("USER NEED", tag_map) == 1

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        tag_map = {"user need": 1}
        assert resolve_tag_name_to_id("  user need  ", tag_map) == 1

    def test_unknown_tag_returns_none(self) -> None:
        """Completely unknown tag name returns None."""
        tag_map = {"user need": 1}
        assert resolve_tag_name_to_id("poodle grooming", tag_map) is None

    def test_fuzzy_match_high_similarity(self) -> None:
        """Very close match (>0.9) is resolved via fuzzy matching."""
        tag_map = {"information architecture": 5}
        # "information architectur" is close enough (missing 'e')
        result = resolve_tag_name_to_id("information architectur", tag_map)
        assert result == 5

    def test_fuzzy_match_too_different(self) -> None:
        """Moderately different name is NOT fuzzy-matched (cutoff 0.9)."""
        tag_map = {"information architecture": 5}
        # "info arch" is too different (similarity < 0.9)
        result = resolve_tag_name_to_id("info arch", tag_map)
        assert result is None


# ---------------------------------------------------------------------------
# build_tag_name_map
# ---------------------------------------------------------------------------


class TestBuildTagNameMap:
    """Tests for building the tag name → ID lookup."""

    def test_maps_template_tags_to_db_ids(self) -> None:
        """Tags from template are mapped to their DB IDs."""
        template = _make_template(
            groups=[
                _make_group("G1", "S1", "ux", [
                    _make_tag("alpha"),
                    _make_tag("beta"),
                ]),
            ],
        )
        tag_id_lookup = {"alpha": 10, "beta": 20}
        result = build_tag_name_map(template, tag_id_lookup)
        assert result == {"alpha": 10, "beta": 20}

    def test_skips_tags_not_in_db(self) -> None:
        """Tags not found in the DB lookup are excluded."""
        template = _make_template(
            groups=[
                _make_group("G1", "S1", "ux", [
                    _make_tag("alpha"),
                    _make_tag("gamma"),  # not in DB
                ]),
            ],
        )
        tag_id_lookup = {"alpha": 10}
        result = build_tag_name_map(template, tag_id_lookup)
        assert result == {"alpha": 10}
        assert "gamma" not in result
