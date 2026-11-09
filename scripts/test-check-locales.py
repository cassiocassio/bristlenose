#!/usr/bin/env python3
"""Negative fixtures for check-locales.py.

The gate guards 21 locale files against drift that renders English silently. A gate that cannot
fail would let that happen while reading "passed", so each rule is driven red here against a scratch
locales tree, each exemption (plural suffixes, the zh-Hant-HK fallback, warnings vs --strict) is
shown to be the only reason a case passes, and a clean tree must pass.

The gate reads module-level paths (LOCALES_DIR, VALUE_PINS, GLOSSARY), so the real script is loaded
and those are pointed at a temp directory; nothing in bristlenose/locales is touched.

Usage: python3 scripts/test-check-locales.py
Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean tree)
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_locales", HERE / "check-locales.py")
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_locales"] = gate
_spec.loader.exec_module(gate)

EN = {"title": "Hello {{name}}", "items_one": "1 item", "items_other": "{{count}} items"}
FR = {"title": "Bonjour {{name}}", "items_one": "1 élément", "items_other": "{{count}} éléments"}
GLOSSARY = "term,lang,context,note\nA,fr,x,y\n"


class LocaleGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._saved = (gate.LOCALES_DIR, gate.VALUE_PINS, gate.GLOSSARY)
        gate.LOCALES_DIR = self.root
        gate.VALUE_PINS = self.root / "en-value-pins.json"
        gate.GLOSSARY = self.root / "glossary.csv"
        self.addCleanup(self._restore)
        self.put("en", "common", EN)
        self.put("fr", "common", FR)
        (self.root / "glossary.csv").write_text(GLOSSARY, encoding="utf-8")

    def _restore(self) -> None:
        gate.LOCALES_DIR, gate.VALUE_PINS, gate.GLOSSARY = self._saved

    def put(self, lang: str, ns: str, data: dict | str) -> None:
        d = self.root / lang
        d.mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        (d / f"{ns}.json").write_text(text, encoding="utf-8")

    def run_gate(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        old = sys.argv
        sys.argv = ["check-locales.py", *argv]
        try:
            with contextlib.redirect_stdout(out):
                rc = gate.main()
        finally:
            sys.argv = old
        return rc, out.getvalue()

    def expect_red(self, *argv: str, needle: str) -> None:
        rc, out = self.run_gate(*argv)
        self.assertEqual(rc, 1, out)
        self.assertIn(needle, out)

    def expect_green(self, *argv: str) -> str:
        rc, out = self.run_gate(*argv)
        self.assertEqual(rc, 0, out)
        return out

    # -- the control -------------------------------------------------------

    def test_a_clean_tree_passes_even_under_strict(self) -> None:
        self.assertIn("All locale checks passed", self.expect_green("--strict"))

    # -- always errors -----------------------------------------------------

    def test_invalid_json_is_an_error(self) -> None:
        self.put("fr", "common", '{"title": ')
        self.expect_red(needle="invalid JSON")

    def test_a_missing_english_directory_is_an_error(self) -> None:
        import shutil
        shutil.rmtree(self.root / "en")
        self.expect_red(needle="English locale directory not found")

    def test_a_placeholder_mismatch_is_an_error(self) -> None:
        self.put("fr", "common", {**FR, "title": "Bonjour"})
        self.expect_red(needle="placeholder mismatch")

    def test_an_unknown_placeholder_in_a_plural_form_is_an_error(self) -> None:
        self.put("fr", "common", {**FR, "items_other": "{{total}} éléments"})
        self.expect_red(needle="unknown placeholder")

    def test_an_english_only_namespace_copied_into_a_locale_is_an_error(self) -> None:
        self.put("en", "preflight", {"a": "A"})
        self.put("fr", "preflight", {"a": "A"})
        self.expect_red(needle="English-only")

    def test_a_recurring_one_locale_must_interpolate_count_in_its_one_form(self) -> None:
        self.put("ru", "common", {**FR, "items_one": "один", "items_other": "{{count}} штук"})
        self.expect_red(needle="must interpolate")

    # -- a genuine gap: a warning by default, an error under --strict ------

    def test_a_genuine_missing_key_warns_and_fails_only_under_strict(self) -> None:
        self.put("fr", "common", {k: v for k, v in FR.items() if k != "title"})
        self.assertIn("genuine missing", self.expect_green())
        self.expect_red("--strict", needle="--strict")

    # -- the exemptions -----------------------------------------------------

    def test_a_missing_plural_form_is_not_a_genuine_gap(self) -> None:
        # ja/ko/zh keep only `_other`: leaving `_one` out is correct, even under --strict.
        self.put("fr", "common", {k: v for k, v in FR.items() if k != "items_one"})
        self.assertGreater(len(self.expect_green("--strict")), 0)

    def test_the_hant_hk_fallback_covers_a_key_its_base_has(self) -> None:
        self.put("zh-Hant", "common", FR)
        self.put("zh-Hant-HK", "common", {"title": "你好 {{name}}"})
        self.assertGreater(len(self.expect_green("--strict")), 0)

    def test_only_a_fallback_locale_may_leave_a_namespace_out_without_a_warning(self) -> None:
        # zh-Hant-HK ships only the overrides it needs, so a missing file is expected there...
        self.put("zh-Hant", "common", FR)
        (self.root / "zh-Hant-HK").mkdir()
        # ...but a locale with no fallback base that is missing the file is worth saying.
        (self.root / "de").mkdir()
        out = self.expect_green("--strict")
        self.assertNotIn("zh-Hant-HK/common.json: file not found", out)
        self.assertIn("de/common.json: file not found", out)

    def test_empty_values_and_orphan_keys_are_warnings_not_errors(self) -> None:
        self.put("fr", "common", {**FR, "title": "", "extra": "x"})
        out = self.expect_green("--strict")
        self.assertIn("empty value", out)
        self.assertIn("orphan key", out)

    # -- divergence markers --------------------------------------------------

    def _marker(self, pin: str, reason: str = "intended") -> dict:
        return {**EN, "_divergent_title": f"en:{pin} {reason}"}

    def test_a_current_divergence_marker_passes(self) -> None:
        self.put("en", "common", self._marker(gate.value_pin(EN["title"])))
        self.assertGreater(len(self.expect_green()), 0)

    def test_a_stale_divergence_marker_is_an_error(self) -> None:
        self.put("en", "common", self._marker("000000"))
        self.expect_red(needle="STALE")

    def test_a_malformed_divergence_marker_is_an_error(self) -> None:
        self.put("en", "common", {**EN, "_divergent_title": "no pin here"})
        self.expect_red(needle="malformed")

    def test_a_divergence_marker_for_a_missing_key_is_an_error(self) -> None:
        self.put("en", "common", {**EN, "_divergent_gone": "en:000000 x"})
        self.expect_red(needle="which does not exist")

    # -- value drift ----------------------------------------------------------

    def test_a_reworded_english_value_is_caught_until_it_is_re_stamped(self) -> None:
        rc, _ = self.run_gate("--stamp")
        self.assertEqual(rc, 0)
        self.assertGreater(len(self.expect_green()), 0)  # stamped and unchanged: clean
        self.put("en", "common", {**EN, "title": "Hi {{name}}"})
        self.put("fr", "common", {**FR})  # translations untouched
        self.expect_red(needle="reworded")
        self.assertEqual(self.run_gate("--stamp")[0], 0)  # accepting is a deliberate act
        self.assertGreater(len(self.expect_green()), 0)

    # -- the glossary ----------------------------------------------------------

    def test_a_glossary_row_with_a_split_note_is_an_error(self) -> None:
        (self.root / "glossary.csv").write_text(GLOSSARY + "B,fr,x,a note, with a comma\n", encoding="utf-8")
        self.expect_red(needle="fields, expected")

    def test_a_missing_glossary_is_an_error(self) -> None:
        (self.root / "glossary.csv").unlink()
        self.expect_red(needle="file not found")


if __name__ == "__main__":
    unittest.main(verbosity=1)
