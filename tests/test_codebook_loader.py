"""Tests for the YAML codebook template loader."""

from __future__ import annotations

import pytest

from bristlenose.server.codebook import (
    CodebookTemplate,
    TemplateGroup,
    TemplateTag,
    get_template,
    load_all_templates,
)

# ---------------------------------------------------------------------------
# Discovery and loading
# ---------------------------------------------------------------------------


class TestLoadAllTemplates:
    def test_loads_all_three(self) -> None:
        templates = load_all_templates()
        ids = {t.id for t in templates}
        assert {"garrett", "norman", "uxr"} <= ids

    def test_returns_codebook_template_instances(self) -> None:
        templates = load_all_templates()
        for t in templates:
            assert isinstance(t, CodebookTemplate)

    def test_deterministic_order(self) -> None:
        """Templates are sorted alphabetically by filename."""
        templates = load_all_templates()
        ids = [t.id for t in templates]
        assert ids == sorted(ids)


class TestGetTemplate:
    def test_garrett(self) -> None:
        t = get_template("garrett")
        assert t is not None
        assert t.id == "garrett"

    def test_norman(self) -> None:
        t = get_template("norman")
        assert t is not None
        assert t.id == "norman"

    def test_uxr(self) -> None:
        t = get_template("uxr")
        assert t is not None
        assert t.id == "uxr"

    def test_nonexistent_returns_none(self) -> None:
        assert get_template("nonexistent") is None


# ---------------------------------------------------------------------------
# Garrett — structure
# ---------------------------------------------------------------------------


class TestGarrettStructure:
    @pytest.fixture()
    def garrett(self) -> CodebookTemplate:
        t = get_template("garrett")
        assert t is not None
        return t

    def test_metadata(self, garrett: CodebookTemplate) -> None:
        assert garrett.title == "The Elements of User Experience"
        assert garrett.author == "Jesse James Garrett"
        assert garrett.enabled is True

    def test_five_groups(self, garrett: CodebookTemplate) -> None:
        assert len(garrett.groups) == 5
        names = [g.name for g in garrett.groups]
        assert names == ["Strategy", "Scope", "Structure", "Skeleton", "Surface"]

    def test_twenty_tags(self, garrett: CodebookTemplate) -> None:
        total = sum(len(g.tags) for g in garrett.groups)
        assert total == 20

    def test_four_tags_per_group(self, garrett: CodebookTemplate) -> None:
        for g in garrett.groups:
            assert len(g.tags) == 4, f"{g.name} has {len(g.tags)} tags, expected 4"

    def test_colour_sets(self, garrett: CodebookTemplate) -> None:
        expected = {"ux", "emo", "task", "trust", "opp"}
        actual = {g.colour_set for g in garrett.groups}
        assert actual == expected

    def test_author_links(self, garrett: CodebookTemplate) -> None:
        assert len(garrett.author_links) == 3
        labels = [lbl for lbl, _ in garrett.author_links]
        assert "jjg.net" in labels

    def test_preamble_present(self, garrett: CodebookTemplate) -> None:
        assert garrett.preamble
        assert "five layers" in garrett.preamble.lower()

    def test_group_subtitles_present(self, garrett: CodebookTemplate) -> None:
        for g in garrett.groups:
            assert g.subtitle, f"{g.name} has no subtitle"


# ---------------------------------------------------------------------------
# Garrett — discrimination prompts
# ---------------------------------------------------------------------------


class TestGarrettPrompts:
    @pytest.fixture()
    def garrett(self) -> CodebookTemplate:
        t = get_template("garrett")
        assert t is not None
        return t

    def test_all_tags_have_definition(self, garrett: CodebookTemplate) -> None:
        for g in garrett.groups:
            for tag in g.tags:
                assert tag.definition, (
                    f"Garrett > {g.name} > {tag.name}: missing definition"
                )

    def test_all_tags_have_apply_when(self, garrett: CodebookTemplate) -> None:
        for g in garrett.groups:
            for tag in g.tags:
                assert tag.apply_when, (
                    f"Garrett > {g.name} > {tag.name}: missing apply_when"
                )

    def test_all_tags_have_not_this(self, garrett: CodebookTemplate) -> None:
        for g in garrett.groups:
            for tag in g.tags:
                assert tag.not_this, (
                    f"Garrett > {g.name} > {tag.name}: missing not_this"
                )

    def test_no_trailing_whitespace(self, garrett: CodebookTemplate) -> None:
        """YAML > folding adds trailing newlines; loader must strip them."""
        for g in garrett.groups:
            for tag in g.tags:
                for field in ("definition", "apply_when", "not_this"):
                    value = getattr(tag, field)
                    assert value == value.strip(), (
                        f"Garrett > {g.name} > {tag.name} > {field}:"
                        f" has trailing whitespace"
                    )

    def test_unicode_preserved(self, garrett: CodebookTemplate) -> None:
        """Em dashes should come through as real Unicode, not escape sequences."""
        all_text = " ".join(
            tag.definition
            for g in garrett.groups
            for tag in g.tags
        )
        assert "\u2014" in all_text, "Em dashes should be real Unicode"
        assert "\\u2014" not in all_text, "Should not contain literal escape sequences"


# ---------------------------------------------------------------------------
# Norman — structure (prompts not yet written)
# ---------------------------------------------------------------------------


class TestNormanStructure:
    @pytest.fixture()
    def norman(self) -> CodebookTemplate:
        t = get_template("norman")
        assert t is not None
        return t

    def test_enabled(self, norman: CodebookTemplate) -> None:
        assert norman.enabled is True

    def test_seven_groups(self, norman: CodebookTemplate) -> None:
        assert len(norman.groups) == 7

    def test_twenty_eight_tags(self, norman: CodebookTemplate) -> None:
        total = sum(len(g.tags) for g in norman.groups)
        assert total == 28

    def test_tags_have_full_prompts(self, norman: CodebookTemplate) -> None:
        """Norman tags have discrimination prompts."""
        for g in norman.groups:
            for tag in g.tags:
                assert tag.definition, f"{tag.name} missing definition"
                assert tag.apply_when, f"{tag.name} missing apply_when"
                assert tag.not_this, f"{tag.name} missing not_this"

    def test_preamble_present(self, norman: CodebookTemplate) -> None:
        assert norman.preamble
        assert "interaction design" in norman.preamble.lower()


# ---------------------------------------------------------------------------
# UXR — structure
# ---------------------------------------------------------------------------


class TestUxrStructure:
    @pytest.fixture()
    def uxr(self) -> CodebookTemplate:
        t = get_template("uxr")
        assert t is not None
        return t

    def test_enabled(self, uxr: CodebookTemplate) -> None:
        assert uxr.enabled is True

    def test_ten_groups(self, uxr: CodebookTemplate) -> None:
        assert len(uxr.groups) == 10

    def test_empty_author(self, uxr: CodebookTemplate) -> None:
        assert uxr.author == ""

    def test_no_author_links(self, uxr: CodebookTemplate) -> None:
        assert uxr.author_links == []

    def test_tags_have_empty_prompts(self, uxr: CodebookTemplate) -> None:
        """UXR tags don't have discrimination prompts yet."""
        for g in uxr.groups:
            for tag in g.tags:
                assert tag.definition == ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_all_colour_sets_valid(self) -> None:
        valid = {"ux", "emo", "task", "trust", "opp"}
        for t in load_all_templates():
            for g in t.groups:
                assert g.colour_set in valid, (
                    f"{t.id} > {g.name}: invalid colour_set '{g.colour_set}'"
                )

    def test_no_empty_tag_names(self) -> None:
        for t in load_all_templates():
            for g in t.groups:
                for tag in g.tags:
                    assert tag.name, f"{t.id} > {g.name}: empty tag name"

    def test_no_empty_group_names(self) -> None:
        for t in load_all_templates():
            for g in t.groups:
                assert g.name, f"{t.id}: empty group name"

    def test_tag_names_unique_within_template(self) -> None:
        for t in load_all_templates():
            names: list[str] = []
            for g in t.groups:
                for tag in g.tags:
                    names.append(tag.name)
            assert len(names) == len(set(names)), (
                f"{t.id}: duplicate tag names: "
                f"{[n for n in names if names.count(n) > 1]}"
            )

    def test_dataclass_types(self) -> None:
        for t in load_all_templates():
            assert isinstance(t, CodebookTemplate)
            for g in t.groups:
                assert isinstance(g, TemplateGroup)
                for tag in g.tags:
                    assert isinstance(tag, TemplateTag)
