"""What the HTML export carries for language, and what it must not.

The export is a single-file build, so anything the SPA bundle references is
inlined into every report. Until 23 Aug 2026 the locale loader's
template-literal import made vite glob all 192 locale JSON files — 1,802 KB of
a 3.38 MB report, including Czech strings for a ``--whisper-model`` flag that no
browser report can reach. The bundle now carries none; the server embeds the
chosen language instead.

These tests cover the embedding rule. The *removal* was verified empirically
against the built bundle (2,523 KB → 780 KB; zero hits sampling ja/cs strings
that were previously all present), which no unit test can assert because CI does
not build the frontend.

See docs/design-export-locale.md.
"""

from __future__ import annotations

from bristlenose.i18n import SUPPORTED_LOCALES, locale_resources
from bristlenose.server.routes.export import _EXPORT_NAMESPACES


class TestChainNotLeaf:
    """"One locale" has to mean the whole fallback chain."""

    def test_a_plain_locale_carries_itself_and_english(self) -> None:
        assert list(locale_resources("de", _EXPORT_NAMESPACES)) == ["de", "en"]

    def test_english_carries_only_itself(self) -> None:
        assert list(locale_resources("en", _EXPORT_NAMESPACES)) == ["en"]

    def test_hong_kong_carries_taiwan_beneath_it(self) -> None:
        """zh-Hant-HK is a thin override fork: shipping its leaf alone would
        render raw keys at whoever the report was sent to."""
        assert list(locale_resources("zh-Hant-HK", _EXPORT_NAMESPACES)) == [
            "zh-Hant-HK",
            "zh-Hant",
            "en",
        ]

    def test_the_hong_kong_leaf_really_is_incomplete(self) -> None:
        """The reason the test above matters, pinned so it cannot rot into a
        tautology: HK ships no enums.json at all, so a leaf-only export would
        lose that namespace outright rather than merely miss a few keys."""
        res = locale_resources("zh-Hant-HK", _EXPORT_NAMESPACES)
        assert "enums" not in res["zh-Hant-HK"]
        assert "enums" in res["zh-Hant"]

    def test_an_unknown_locale_degrades_to_english(self) -> None:
        assert list(locale_resources("kling-on", _EXPORT_NAMESPACES)) == ["en"]


class TestCarriesNoMoreThanItNeeds:
    def test_the_other_twenty_locales_are_absent(self) -> None:
        """The whole point: a German export must not carry Japanese."""
        res = locale_resources("de", _EXPORT_NAMESPACES)
        for loc in SUPPORTED_LOCALES:
            if loc not in ("de", "en"):
                assert loc not in res, f"{loc} rode along in a German export"

    def test_only_namespaces_a_browser_report_can_reach(self) -> None:
        """cli, doctor, preflight, server and pipeline are unreachable from a
        report opened in a browser. pipeline has no live consumers anywhere."""
        assert _EXPORT_NAMESPACES == ("common", "settings", "enums")
        for bundle in locale_resources("fr", _EXPORT_NAMESPACES).values():
            assert set(bundle) <= set(_EXPORT_NAMESPACES)

    def test_every_supported_locale_resolves_to_something(self) -> None:
        """No locale may produce an empty embed — that would render a report
        with raw keys, and it is the failure mode adding a language invites."""
        for loc in SUPPORTED_LOCALES:
            res = locale_resources(loc, _EXPORT_NAMESPACES)
            assert res, f"{loc} embedded nothing"
            assert "common" in res.get(loc, {}) or "common" in res["en"]
