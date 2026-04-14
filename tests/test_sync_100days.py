"""Tests for scripts/sync_100days.py — markdown parsing and line rewriting."""

# Import from the script (it's not a package, so we use importlib)
import importlib.util
import pathlib
import textwrap

_script = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "sync_100days.py"
_spec = importlib.util.spec_from_file_location("sync_100days", _script)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


# ---------------------------------------------------------------------------
# normalize()
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_basic(self):
        assert sync.normalize("Hello World") == "hello world"

    def test_strips_punctuation(self):
        assert sync.normalize("**Title** — description") == "title description"

    def test_strips_strikethrough(self):
        assert sync.normalize("~~Done item~~") == "done item"

    def test_smart_quotes(self):
        assert sync.normalize("it\u2019s") == "its"

    def test_collapses_whitespace(self):
        assert sync.normalize("  hello   world  ") == "hello world"

    def test_backticks_stripped(self):
        assert sync.normalize("`bristlenose doctor`") == "bristlenose doctor"


# ---------------------------------------------------------------------------
# escape_graphql()
# ---------------------------------------------------------------------------

class TestEscapeGraphql:
    def test_quotes(self):
        assert sync.escape_graphql('say "hello"') == 'say \\"hello\\"'

    def test_backslashes(self):
        assert sync.escape_graphql("\\<project\\>") == "\\\\<project\\\\>"

    def test_newlines(self):
        assert sync.escape_graphql("line1\nline2") == "line1 line2"

    def test_combined(self):
        result = sync.escape_graphql('"Duplicate of \\<project\\>"')
        assert "\n" not in result
        assert '\\"' in result
        assert "\\\\" in result


# ---------------------------------------------------------------------------
# parse_doc()
# ---------------------------------------------------------------------------

def _write_doc(tmp_path, content):
    p = tmp_path / "100days.md"
    p.write_text(textwrap.dedent(content))
    return str(p)


class TestParseDoc:
    def test_basic_item(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Demo dataset** — 5h IKEA study
        """)
        items = sync.parse_doc(path)
        assert len(items) == 1
        assert items[0]["title"] == "Demo dataset"
        assert items[0]["kind"] == "1. Missing"
        assert items[0]["priority"] == "Must"
        assert items[0]["sprint"] is None
        assert "5h IKEA" in items[0]["description"]

    def test_sprint_tag(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 3. Embarrassing — too ugly to ship

        ### Must
        - [S5] **Typography audit** — 16 font-sizes
        """)
        items = sync.parse_doc(path)
        assert len(items) == 1
        assert items[0]["title"] == "Typography audit"
        assert items[0]["sprint"] == "Sprint 5"

    def test_two_digit_sprint(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - [S12] **Future item** — far away
        """)
        items = sync.parse_doc(path)
        assert items[0]["sprint"] == "Sprint 12"

    def test_strikethrough_item(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **~~Desktop app v0.1~~** — SwiftUI shell
        """)
        items = sync.parse_doc(path)
        assert len(items) == 1
        assert items[0]["title"] == "Desktop app v0.1"

    def test_strikethrough_with_sprint(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 2. Broken — doesn't work

        ### Must
        - [S1] **~~Fixed thing~~** — was broken
        """)
        items = sync.parse_doc(path)
        assert items[0]["title"] == "Fixed thing"
        assert items[0]["sprint"] == "Sprint 1"

    def test_item_no_description(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Should
        - **Bare title**
        """)
        items = sync.parse_doc(path)
        assert len(items) == 1
        assert items[0]["title"] == "Bare title"
        assert items[0]["description"] == ""

    def test_item_no_desc_with_sprint(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Should
        - [S2] **Tagged bare title**
        """)
        items = sync.parse_doc(path)
        assert items[0]["sprint"] == "Sprint 2"
        assert items[0]["title"] == "Tagged bare title"

    def test_multiple_priorities(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Must item** — important

        ### Should
        - **Should item** — nice to have

        ### Could
        - **Could item** — optional
        """)
        items = sync.parse_doc(path)
        assert len(items) == 3
        assert items[0]["priority"] == "Must"
        assert items[1]["priority"] == "Should"
        assert items[2]["priority"] == "Could"

    def test_multiple_categories(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Item A** — first

        ## 2. Broken — doesn't work

        ### Must
        - **Item B** — second
        """)
        items = sync.parse_doc(path)
        assert len(items) == 2
        assert items[0]["kind"] == "1. Missing"
        assert items[1]["kind"] == "2. Broken"

    def test_icebox_treated_as_priority_none(self, tmp_path):
        """Icebox headings don't match the priority regex, so priority stays as-is."""
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Must item** — important

        ### Icebox (100 days)
        - **Icebox item** — parked
        """)
        items = sync.parse_doc(path)
        assert len(items) == 2
        assert items[0]["priority"] == "Must"
        # Icebox doesn't match the priority regex, so it keeps the last priority
        assert items[1]["priority"] == "Must"

    def test_supplementary_sections(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## Active feature branches

        - **Branch A** — in progress
        """)
        items = sync.parse_doc(path)
        assert len(items) == 1
        assert items[0]["kind"] == "Active Branches"

    def test_wont_priority(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Won't (100 days)
        - **Windows app** — defer
        """)
        items = sync.parse_doc(path)
        assert items[0]["priority"] == "Won't"

    def test_en_dash_separator(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Title** \u2013 en dash description
        """)
        items = sync.parse_doc(path)
        assert items[0]["title"] == "Title"
        assert "en dash" in items[0]["description"]


# ---------------------------------------------------------------------------
# sync_done_to_doc() — line rewriting
# ---------------------------------------------------------------------------

class TestSyncDoneToDoc:
    def test_strikes_done_item(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Desktop app v0.1** — SwiftUI shell
        """)
        board_items = [{"normalized": sync.normalize("Desktop app v0.1"), "status": "Done"}]
        changes = sync.sync_done_to_doc(board_items, path, apply=True)
        assert changes == 1
        content = pathlib.Path(path).read_text()
        assert "**~~Desktop app v0.1~~**" in content

    def test_unstrikes_undone_item(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **~~Desktop app v0.1~~** — SwiftUI shell
        """)
        board_items = [{"normalized": sync.normalize("Desktop app v0.1"), "status": "In Progress"}]
        changes = sync.sync_done_to_doc(board_items, path, apply=True)
        assert changes == 1
        content = pathlib.Path(path).read_text()
        assert "**Desktop app v0.1**" in content
        assert "~~" not in content

    def test_preserves_sprint_tag_on_strike(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - [S3] **Multi-project support** — home screen
        """)
        board_items = [{"normalized": sync.normalize("Multi-project support"), "status": "Done"}]
        changes = sync.sync_done_to_doc(board_items, path, apply=True)
        assert changes == 1
        content = pathlib.Path(path).read_text()
        assert "[S3] **~~Multi-project support~~**" in content

    def test_preserves_sprint_tag_on_unstrike(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - [S3] **~~Multi-project support~~** — home screen
        """)
        board_items = [{"normalized": sync.normalize("Multi-project support"), "status": "Todo"}]
        changes = sync.sync_done_to_doc(board_items, path, apply=True)
        assert changes == 1
        content = pathlib.Path(path).read_text()
        assert "[S3] **Multi-project support**" in content
        assert "~~" not in content

    def test_no_change_when_already_correct(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **~~Already done~~** — finished
        - **Not done** — still open
        """)
        board_items = [
            {"normalized": sync.normalize("Already done"), "status": "Done"},
            {"normalized": sync.normalize("Not done"), "status": "Todo"},
        ]
        changes = sync.sync_done_to_doc(board_items, path, apply=False)
        assert changes == 0

    def test_dry_run_does_not_write(self, tmp_path):
        path = _write_doc(tmp_path, """\
        ## 1. Missing — essential feature gaps

        ### Must
        - **Item** — description
        """)
        original = pathlib.Path(path).read_text()
        board_items = [{"normalized": sync.normalize("Item"), "status": "Done"}]
        changes = sync.sync_done_to_doc(board_items, path, apply=False)
        assert changes == 1
        assert pathlib.Path(path).read_text() == original
