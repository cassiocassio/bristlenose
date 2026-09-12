#!/usr/bin/env python3
"""Prove check-providers-live can go red — and cannot go green on a short list.

WHY THIS EXISTS

`check-providers-live.py` is the only thing that asks whether a shipped model
still answers. It costs pence and needs three vendors' keys, so nobody was ever
going to watch it fail on purpose, and it arrived unproven — 14 against a
ceiling of 13, which is the ratchet doing exactly its job.

A live gate can still be proven for nothing, because the expensive half is the
network and the failure logic is not. Everything here runs offline: `check()` is
stubbed, so no key is read and no call is made.

THE HOLE THIS FOUND

The gate's own worst failure is not a wrong verdict, it is a SHORT LIST.
`shipped_models` derives the model set from `LLMProvider.swift` by regex, and
the miss branch used to be `if m:` with no else — so one `return` added to a
Swift case dropped two of Claude's three models, and the run printed
"5/5 shipped models passed all three questions" and exited 0. A gate that tests
less than it claims, reporting success, is the defect the whole gate-proof
register exists for; it was one layer up from where anyone was looking.
Enumeration is now all-or-nothing, and the cases below are what hold it there.

DELIBERATELY NOT COVERED

Whether a real dead model produces an error string `classify` recognises. That
is a claim about three vendors' wire formats, it changes without notice, and no
local fixture can hold it — which is the whole reason the live script exists.
What is pinned instead is that the strings observed on 4-5 Sep 2026 map to the
right question, so a rewrite of `classify` cannot quietly lose them.

Usage: .venv/bin/python scripts/test-providers-live.py
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cpl", HERE / "check-providers-live.py")
cpl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpl)

REAL_SWIFT = cpl.SWIFT.read_text(encoding="utf-8")
FAILURES: list[str] = []


class _Empty:
    """Schema-valid but useless: every list empty, every count zero."""

    def __getattr__(self, name: str):
        return 0 if name.endswith("count") else []


def check(label: str, cond, detail: str = "") -> None:
    """cond is a callable so a raising assertion FAILS its case instead of
    killing the run — a suite that dies on the first defect reports one."""
    try:
        ok, why = bool(cond()), detail
    except Exception as e:  # noqa: BLE001
        ok, why = False, f"{type(e).__name__}: {e}"
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        FAILURES.append(f"{label}{' — ' + why if why else ''}")


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:  # noqa: BLE001
        return True
    return False


def swift(variant: str):
    """Point the module at a rewritten copy of LLMProvider.swift.

    A temp file, never the tracked one: this suite cannot leave the tree dirty,
    so there is no restore step to be skipped by a SIGTERM.
    """
    p = pathlib.Path(tempfile.mkdtemp()) / "LLMProvider.swift"
    p.write_text(variant, encoding="utf-8")
    cpl.SWIFT = p
    return p


def run(argv: list[str], verdicts: dict[tuple[str, str], str]) -> tuple[int, str]:
    """Drive the real main() with check() stubbed. Returns (exit code, stdout)."""
    async def fake_check(provider: str, model: str, stage_keys=()) -> tuple[str, str]:
        return verdicts.get((provider, model), "PASS"), "stubbed"

    real_check, real_argv = cpl.check, sys.argv
    cpl.check, sys.argv = fake_check, ["check-providers-live.py", *argv]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = asyncio.run(cpl.main())
    finally:
        cpl.check, sys.argv = real_check, real_argv
    return code, buf.getvalue()


print("\n\033[1mclassify — which of the three questions failed\033[0m")
print("  the strings are real, from the 4-5 Sep 2026 runs and the vendors' own wording")
for text, want, note in [
    ("Error code: 401 - Incorrect API key provided: sk-***", "i.alive", "OpenAI bad key"),
    ("API key not valid. Please pass a valid API key.", "i.alive", "Gemini bad key"),
    ("authentication_error: invalid x-api-key", "i.alive", "Anthropic bad key"),
    ("404 - The model `gpt-4.5-preview` does not exist", "ii.exists", "OpenAI retired"),
    ("models/gemini-2.5-pro is not found for API version v1beta", "ii.exists", "Gemini retired"),
    ("model: claude-3-sonnet-20240229 is no longer available", "ii.exists", "soft retirement"),
    ("1 validation error for QuoteExtractionResult", "iii.shape", "the Sonnet 5 shape"),
    ("Expecting value: line 1 column 1 (char 0)", "iii.shape", "unparseable body"),
]:
    check(f"{note:<18} -> {want}", lambda t=text, w=want: cpl.classify(Exception(t)) == w)
check(
    "an unrecognised error is shape, not silently alive",
    lambda: cpl.classify(Exception("connection reset by peer")) == "iii.shape",
    "the default arm must be the one that fails loudest, not the one that reads as fine",
)

print("\n\033[1mshipped_models — a partial list is a tool failure, not a pass\033[0m")
swift(REAL_SWIFT)
check("the real tree gives 3 Claude models",
      lambda: cpl.shipped_models("anthropic") == [
          "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-5"],
      "if this fails the picker moved and the rest of this file is stale")
check("the registry default leads the list",
      lambda: cpl.shipped_models("openai")[0] == cpl.PROVIDERS["openai"].default_model)

# The regression. Each of these is a plausible one-token Swift edit; before the
# fix the first two returned the registry default ALONE and the run exited 0.
swift(REAL_SWIFT.replace('case .claude: ["claude', 'case .claude: return ["claude'))
check("an explicit `return` does not shorten the list",
      lambda: len(cpl.shipped_models("anthropic")) == 3,
      "the shape that silently dropped opus-5 and haiku")
swift(REAL_SWIFT.replace('case .claude: ["claude', 'case .claude:\n            ["claude'))
check("a wrapped array does not shorten the list",
      lambda: len(cpl.shipped_models("anthropic")) == 3,
      "what a fourth model would do to that line")

swift(REAL_SWIFT.replace("case .claude:", "case .anthropic:"))
check("a RENAMED case raises rather than testing one model",
      lambda: _raises(lambda: cpl.shipped_models("anthropic")),
      "SWIFT_CASE drift is the miss no regex can absorb — it must be exit 2")
swift(REAL_SWIFT.replace("var availableModels: [String] {", "var pickerModels: [String] {"))
check("a renamed availableModels block raises",
      lambda: _raises(lambda: cpl.shipped_models("anthropic")))

print("\n\033[1mthe fixture is the REAL stage prompts, not an invented one\033[0m")
import live_check_fixture as fx  # noqa: E402

check("all six stages render with the pipeline's own templates",
      lambda: len(fx.STAGES) == 6 and all(all(fx_p) for fx_p in (st.prompts() for st in fx.STAGES)),
      "a KeyError here means a template grew a placeholder the fixture does not fill")
check("every stage carries the model its pipeline call uses",
      lambda: [st.model.__name__ for st in fx.STAGES] == [
          "SpeakerSplitAssignment", "SpeakerRoleAssignment", "TopicSegmentationResult",
          "QuoteExtractionResult", "ScreenClusteringResult", "ThematicGroupingResult"])
check("the default set is the two stages that actually broke",
      lambda: cpl.DEFAULT_STAGES == ("s10:clusters", "s11:themes"),
      "s09 was the invented prompt's stage and was never where the failures were")
check("the untrusted envelope is present, as in production",
      lambda: all("untrusted" in st.prompts()[1] for st in fx.STAGES),
      "a fixture that skips wrap_untrusted is not testing the request we send")
check("a VACUOUS result is a failure, not a pass",
      lambda: not any(st.substantive(_Empty()) for st in fx.STAGES),
      "validating is not answering — an empty list is how a stage ships an empty report")

print("\n\033[1mpreflight — the second request builder runs FIRST, through its own code\033[0m")
import types  # noqa: E402

from bristlenose.preflight.api_key import ValidationResult  # noqa: E402

THE_4SEP_MESSAGE = ("Unsupported parameter: 'max_tokens' is not supported with this model. "
                    "Use 'max_completion_tokens' instead.")


class _FakeStage:
    key = "s00:fake"
    model = object

    @staticmethod
    def prompts():
        return ("system", "user")

    @staticmethod
    def substantive(_result):
        return True


class _ClientNotReached:
    """If preflight said no, no client is built and analyze() never runs."""

    def __init__(self, _settings):
        raise AssertionError("LLMClient was built before preflight said yes")

    async def analyze(self, **_kw):
        raise AssertionError("analyze() ran first")


class _ClientOk:
    def __init__(self, _settings):
        pass

    async def analyze(self, **_kw):
        return object()


def _settings(**kw):
    return types.SimpleNamespace(llm_provider=kw["llm_provider"], llm_model=kw["llm_model"],
                                 openai_api_key="not-a-real-key")


def probe(validator, client):
    """Drive the REAL check() offline: settings, the validator and the client are stubbed."""
    saved = (cpl.load_settings, cpl.preflight._validate_openai, cpl.LLMClient, dict(cpl.BY_KEY))
    cpl.load_settings, cpl.preflight._validate_openai, cpl.LLMClient = _settings, validator, client
    cpl.BY_KEY["s00:fake"] = _FakeStage
    try:
        return asyncio.run(cpl.check("openai", "gpt-5.6-terra", ("s00:fake",)))
    finally:
        cpl.load_settings, cpl.preflight._validate_openai, cpl.LLMClient = saved[:3]
        cpl.BY_KEY.clear()
        cpl.BY_KEY.update(saved[3])


v, d = probe(lambda key, model: ValidationResult(ok=False, error_class="model_unavailable",
                                                 raw_message=THE_4SEP_MESSAGE), _ClientNotReached)
check("the 4 Sep preflight-only break is red, and analyze() is never reached",
      lambda: v == "FAIL" and "preflight" in d and "max_completion_tokens" in d, d)
check("...classified as ii.exists, preflight's own bucket mapped onto the questions",
      lambda: d.startswith("ii.exists"), d)
v, d = probe(lambda key, model: ValidationResult(ok=True), _ClientOk)
check("preflight ok -> the stage runs -> PASS names both",
      lambda: v == "PASS" and "preflight+fake" in d, d)
v, d = probe(lambda key, model: ValidationResult(ok=False, error_class="invalid_key",
                                                 raw_message="Incorrect API key provided"),
             _ClientNotReached)
check("a dead key is i.alive, from preflight, before any stage call",
      lambda: v == "FAIL" and d.startswith("i.alive"), d)
v, d = probe(lambda key, model: ValidationResult(
    ok=False, error_class=None,
    raw_message="models/gemini-2.5-pro is not found for API version v1beta"), _ClientNotReached)
check("an unbucketed preflight error falls through to classify()",
      lambda: v == "FAIL" and d.startswith("ii.exists"), d)
seen: dict[str, str] = {}


def _spy(key, model):
    seen.update(key=key, model=model)
    return ValidationResult(ok=True)


probe(_spy, _ClientOk)
check("preflight is asked with the MODEL UNDER TEST, not a fixed cheap one",
      lambda: seen.get("model") == "gpt-5.6-terra", str(seen))
check("...and with the key the client will use", lambda: seen.get("key") == "not-a-real-key")
_saved_key_for = cpl.preflight._api_key_for
cpl.preflight._api_key_for = lambda _s: ("", "")
try:
    v, d = probe(lambda key, model: (_ for _ in ()).throw(AssertionError("validator ran with no key")),
                 _ClientNotReached)
finally:
    cpl.preflight._api_key_for = _saved_key_for
check("no key -> a FAIL that says so; no validator call, no client",
      lambda: v == "FAIL" and "no key" in d and "AssertionError" not in d, d)

print("\n\033[1mmain — the exit codes, which are what a caller reads\033[0m")
swift(REAL_SWIFT)
code, out = run([], {})
check("all seven pass -> exit 0", lambda: code == 0, f"got {code}")
check("...and it says seven", lambda: "7/7 shipped models passed" in out, out.strip()[-90:])

code, out = run([], {("google", "gemini-3.8-flash"): "FAIL"})
check("ONE failing model -> exit 1", lambda: code == 1, f"got {code}")
check("...and the run names it",
      lambda: any("gemini-3.8-flash" in ln and "FAIL" in ln for ln in out.splitlines()),
      "a red that does not say which model is a red nobody can act on")
check("...and the tally drops to 6/7", lambda: "6/7 shipped models passed" in out)

code, _ = run(["--provider", "anthropic"], {("anthropic", "claude-opus-5"): "FAIL"})
check("--provider narrows and still goes red", lambda: code == 1, f"got {code}")

swift(REAL_SWIFT.replace("case .claude:", "case .anthropic:"))
code, out = run([], {})
check("un-enumerable -> exit 2, NOT 0", lambda: code == 2, f"got {code}")
check("...and 2 is distinguishable from a model failure",
      lambda: "cannot enumerate" in out,
      "exit 1 means a vendor moved; exit 2 means this script is broken")

cpl.SWIFT = HERE.parent / "desktop/Bristlenose/Bristlenose/LLMProvider.swift"

print()
if FAILURES:
    print(f"\033[31m{len(FAILURES)} case(s) failed\033[0m", file=sys.stderr)
    for f in FAILURES:
        print(f"  - {f}", file=sys.stderr)
    raise SystemExit(1)
print("\033[32mall cases passed\033[0m — check-providers-live can go red, and "
      "cannot go green on a partial list")
