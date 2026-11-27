"""The Mac app's Help menu links the privacy policy in every build, unconditionally.

App Store Review Guideline 5.1.1(i) wants the privacy policy reachable inside the
app. Only one link does that in every build. `NewsPreferences.privacyURL` renders
only when `NewsKeys.isLive`, and the paywall's link shows only at the paywall. So
the guarantee is **Help ▸ Privacy Policy** (`HelpMenuContent` in
`MenuCommands.swift`, added 21 Nov 2026 in 2fcecac61).

The menu is a private SwiftUI view with no test seam, and the likely way to break
it is a plausible edit that compiles: wrap the button in an `if` or `#if` ("only
on the App Store build", "only once news is live"), or give it a `.disabled`. So
this test reads the source and pins the **exact shape** that is known to be
unconditional. Anything else goes red, harmless refactors included, because for
an App Review guarantee a false red is the cheap failure. What it pins:

1. `MenuCommands.body` has `CommandGroup(replacing: .help)` as a top-level
   statement, outside any `#if`, and builds `HelpMenuContent(` directly inside it.
2. `HelpMenuContent.body` has the privacy button as a top-level statement, outside
   any `#if`, with no modifiers. Its action is exactly
   `Self.open("https://bristlenose.app/privacy.html")`.
3. `HelpMenuContent.open` still hands the URL to `NSWorkspace.shared.open(url)`.

Nesting is read from indentation, which Xcode keeps consistent in this file
(`if`/`Group` bodies are indented; `#if` blocks are not, so directives are counted
instead). That avoids parsing Swift. The known blind spot is a mis-indented
wrapper (`if x {` with the button left unindented), which Xcode re-indents on
paste. The check stops at `MenuCommands.body`: whether the app installs
`MenuCommands` at all (`BristlenoseApp.swift`, `.commands { … }`) is outside it.

If you restructure the menu without making the link conditional, update this
test. If you make it conditional, add an unconditional link somewhere else first.
The locale strings are pinned separately, in every full locale, by
`test_swift_i18n_keys_resolve.py`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MENU_COMMANDS = _ROOT / "desktop/Bristlenose/Bristlenose/MenuCommands.swift"

PRIVACY_KEY = "desktop.menu.help.privacyPolicy"
PRIVACY_URL = "https://bristlenose.app/privacy.html"
_BUTTON_HEAD = re.compile(
    r'Button\(i18n\.t\("' + re.escape(PRIVACY_KEY) + r'"\)(, systemImage: "[^"]*")?\) \{'
)
_ACTION = f'Self.open("{PRIVACY_URL}")'
_HELP_GROUP = "CommandGroup(replacing: .help) {"

# One message per check, so each mutant below can assert the check it targets.
NO_TABS = "MenuCommands.swift indents with tabs; this test reads 4-space indentation"
NO_MENU_BODY = "no `struct MenuCommands` with a `var body: some Commands`"
NO_GROUP = "MenuCommands.body has no `CommandGroup(replacing: .help)`"
GROUP_NESTED = "the Help CommandGroup is nested inside a block in MenuCommands.body"
GROUP_IN_IF = "the Help CommandGroup sits inside an `#if`"
GROUP_CONTENT = "the Help CommandGroup no longer builds HelpMenuContent( as its first line"
NO_HELP_BODY = "no `struct HelpMenuContent` with a `var body: some View`"
NO_BUTTON = f"HelpMenuContent.body has no button with key {PRIVACY_KEY}"
BUTTON_NESTED = "the privacy button is nested inside a block (an `if`, a `Group`…)"
BUTTON_IN_IF = "the privacy button sits inside an `#if`"
BUTTON_SHAPE = "the privacy button no longer reads `Button(i18n.t(key)) {`"
ACTION_SHAPE = f"the privacy button's action is no longer exactly {_ACTION}"
MODIFIERS = "the privacy button carries a modifier or a postfix `#if`"
SINK = "HelpMenuContent.open no longer calls NSWorkspace.shared.open(url)"


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_code(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("//")


def _open_ifs(lines: list[str], upto: int) -> int:
    depth = 0
    for line in lines[:upto]:
        stripped = line.strip()
        if re.match(r"#if\b", stripped):
            depth += 1
        elif re.match(r"#endif\b", stripped):
            depth -= 1
    return depth


def _block(lines: list[str], header: str, start: int = 0) -> tuple[int, int] | None:
    """(header line, closing-brace line) of the first line from `start` matching
    `header`, closed by the first later `}` at the header's own indentation."""
    pattern = re.compile(header)
    for i in range(start, len(lines)):
        if pattern.match(lines[i]):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "}" and _indent(lines[j]) == _indent(lines[i]):
                    return i, j
            return None
    return None


def _body(lines: list[str], struct: str, body: str) -> tuple[int, int] | None:
    outer = _block(lines, rf"^(private )?struct {struct}\b")
    if outer is None:
        return None
    inner = _block(lines, rf"^ +var body: some {body} \{{$", outer[0])
    if inner is None or inner[1] > outer[1]:
        return None
    return inner


def privacy_link_problems(source: str) -> list[str]:
    """Every reason the Help menu's privacy link is missing or conditional."""
    lines = source.splitlines()
    if any(line.startswith("\t") for line in lines):
        return [NO_TABS]
    problems: list[str] = []

    menu = _body(lines, "MenuCommands", "Commands")
    if menu is None:
        problems.append(NO_MENU_BODY)
    else:
        start, end = menu
        top = _indent(lines[start]) + 4
        hits = [k for k in range(start + 1, end) if lines[k].strip() == _HELP_GROUP]
        if not hits:
            problems.append(NO_GROUP)
        else:
            k = hits[0]
            if _indent(lines[k]) != top:
                problems.append(GROUP_NESTED)
            if _open_ifs(lines, k):
                problems.append(GROUP_IN_IF)
            first = lines[k + 1]
            inside = _indent(lines[k]) + 4
            if not (first.strip().startswith("HelpMenuContent(") and _indent(first) == inside):
                problems.append(GROUP_CONTENT)

    help_struct = _block(lines, r"^(private )?struct HelpMenuContent\b")
    help_body = _body(lines, "HelpMenuContent", "View")
    if help_struct is None or help_body is None:
        return [*problems, NO_HELP_BODY]
    start, end = help_body
    top = _indent(lines[start]) + 4
    hits = [k for k in range(start + 1, end) if _is_code(lines[k]) and PRIVACY_KEY in lines[k]]
    if not hits:
        problems.append(NO_BUTTON)
    else:
        k = hits[0]
        if _indent(lines[k]) != top:
            problems.append(BUTTON_NESTED)
        if _open_ifs(lines, k):
            problems.append(BUTTON_IN_IF)
        if not _BUTTON_HEAD.fullmatch(lines[k].strip()):
            problems.append(BUTTON_SHAPE)
        action, close = lines[k + 1 : k + 3] if k + 2 < len(lines) else ("", "")
        if action.strip() != _ACTION or close.rstrip() != " " * _indent(lines[k]) + "}":
            problems.append(ACTION_SHAPE)
        following = next((ln for ln in lines[k + 3 :] if _is_code(ln)), "")
        if re.match(r"\s*(\.|#if\b)", following):
            problems.append(MODIFIERS)

    struct_lines = lines[help_struct[0] : help_struct[1]]
    if not any(_is_code(ln) and "NSWorkspace.shared.open(url)" in ln for ln in struct_lines):
        problems.append(SINK)
    return problems


def test_help_menu_links_the_privacy_policy_unconditionally() -> None:
    problems = privacy_link_problems(_MENU_COMMANDS.read_text(encoding="utf-8"))
    assert not problems, (
        "Help ▸ Privacy Policy is the app's only unconditional link to the privacy "
        "policy (App Store Guideline 5.1.1(i)). Problems: " + "; ".join(problems)
    )


# The gate must be able to fail, check by check. Each mutant is a plausible edit
# to the real source, and must trip exactly the check it targets.

def _source() -> list[str]:
    return _MENU_COMMANDS.read_text(encoding="utf-8").splitlines()


def _button_at(lines: list[str]) -> int:
    start, end = _body(lines, "HelpMenuContent", "View") or (0, 0)
    return next(k for k in range(start, end) if PRIVACY_KEY in lines[k])


def _group_at(lines: list[str]) -> int:
    return next(k for k, ln in enumerate(lines) if ln.strip() == _HELP_GROUP)


def _wrap(lines: list[str], k: int, n: int, head: str, tail: str, indent: bool) -> list[str]:
    pad = " " * _indent(lines[k])
    body = ["    " + ln if indent else ln for ln in lines[k : k + n]]
    return [*lines[:k], pad + head, *body, pad + tail, *lines[k + n :]]


def _m_button_if(ls: list[str]) -> list[str]:
    return _wrap(ls, _button_at(ls), 3, "if NewsKeys.isLive {", "}", indent=True)


def _m_button_hash_if(ls: list[str]) -> list[str]:
    return _wrap(ls, _button_at(ls), 3, "#if APPSTORE", "#endif", indent=False)


def _m_button_removed(ls: list[str]) -> list[str]:
    k = _button_at(ls)
    return ls[:k] + ls[k + 3 :]


def _m_button_commented(ls: list[str]) -> list[str]:
    k = _button_at(ls)
    return [*ls[:k], *("// " + ln for ln in ls[k : k + 3]), *ls[k + 3 :]]


def _m_button_label_form(ls: list[str]) -> list[str]:
    k = _button_at(ls)
    return [*ls[:k], ls[k].replace('"))', '"), role: nil)'), *ls[k + 1 :]]


def _m_action_if(ls: list[str]) -> list[str]:
    return _wrap(ls, _button_at(ls) + 1, 1, "if NewsKeys.isLive {", "}", indent=True)


def _m_wrong_url(ls: list[str]) -> list[str]:
    k = _button_at(ls) + 1
    return [*ls[:k], ls[k].replace(PRIVACY_URL, "https://bristlenose.app/docs/"), *ls[k + 1 :]]


def _m_disabled(ls: list[str]) -> list[str]:
    k = _button_at(ls) + 3
    return [*ls[:k], "        .disabled(true)", *ls[k:]]


def _m_shortcut_then_disabled(ls: list[str]) -> list[str]:
    k = _button_at(ls) + 3
    return [*ls[:k], '        .keyboardShortcut("p")', "        .disabled(true)", *ls[k:]]


def _m_postfix_hash_if(ls: list[str]) -> list[str]:
    k = _button_at(ls) + 3
    return [*ls[:k], "        #if APPSTORE", "        .disabled(true)", "        #endif", *ls[k:]]


def _m_decoy_struct(ls: list[str]) -> list[str]:
    # A same-prefix struct keeps the button while the real one loses it.
    k = _button_at(ls)
    decoy = ["private struct HelpMenuContentOld: View {", "    var body: some View {",
             *ls[k : k + 3], "    }", "}", ""]
    cut = ls[:k] + ls[k + 3 :]
    s = next(i for i, ln in enumerate(cut) if ln.startswith("private struct HelpMenuContent:"))
    return [*cut[:s], *decoy, *cut[s:]]


def _m_sink_gutted(ls: list[str]) -> list[str]:
    return [ln.replace("NSWorkspace.shared.open(url)", "_ = url") for ln in ls]


def _m_group_if(ls: list[str]) -> list[str]:
    return _wrap(ls, _group_at(ls), 3, "if showsHelp {", "}", indent=True)


def _m_group_hash_if(ls: list[str]) -> list[str]:
    return _wrap(ls, _group_at(ls), 3, "#if !APPSTORE", "#endif", indent=False)


def _m_group_inner_if(ls: list[str]) -> list[str]:
    return _wrap(ls, _group_at(ls) + 1, 1, "if showsHelp {", "}", indent=True)


def _m_group_to_child(ls: list[str]) -> list[str]:
    # Moved into a child Commands struct, called conditionally from the body.
    k = _group_at(ls)
    group = ls[k : k + 3]
    call = ["        if showsHelp {", "            HelpCommands()", "        }"]
    child = ["struct HelpCommands: Commands {", "    var body: some Commands {",
             *group, "    }", "}", ""]
    out = [*ls[:k], *call, *ls[k + 3 :]]
    s = next(i for i, ln in enumerate(out) if ln.startswith("private struct HelpMenuContent:"))
    return [*out[:s], *child, *out[s:]]


def _m_menu_renamed(ls: list[str]) -> list[str]:
    return [ln.replace("struct MenuCommands:", "struct MainMenuCommands:") for ln in ls]


def _m_help_renamed(ls: list[str]) -> list[str]:
    return [ln.replace("struct HelpMenuContent:", "struct HelpMenuItems:") for ln in ls]


def _m_tabs(ls: list[str]) -> list[str]:
    return [ln.replace("    ", "\t") for ln in ls]


_MUTANTS: dict[str, tuple[Callable[[list[str]], list[str]], list[str]]] = {
    "button in if": (_m_button_if, [BUTTON_NESTED]),
    "button in #if": (_m_button_hash_if, [BUTTON_IN_IF]),
    "button removed": (_m_button_removed, [NO_BUTTON]),
    "button commented out": (_m_button_commented, [NO_BUTTON]),
    "button header changed": (_m_button_label_form, [BUTTON_SHAPE]),
    "action in if": (_m_action_if, [ACTION_SHAPE]),
    "wrong url": (_m_wrong_url, [ACTION_SHAPE]),
    "disabled": (_m_disabled, [MODIFIERS]),
    "shortcut then disabled": (_m_shortcut_then_disabled, [MODIFIERS]),
    "postfix #if": (_m_postfix_hash_if, [MODIFIERS]),
    "same-prefix decoy struct": (_m_decoy_struct, [NO_BUTTON]),
    "open() gutted": (_m_sink_gutted, [SINK]),
    "help group in if": (_m_group_if, [GROUP_NESTED]),
    "help group in #if": (_m_group_hash_if, [GROUP_IN_IF]),
    "help content in if": (_m_group_inner_if, [GROUP_CONTENT]),
    "help group moved to a child, called in if": (_m_group_to_child, [NO_GROUP]),
    "MenuCommands renamed": (_m_menu_renamed, [NO_MENU_BODY]),
    "HelpMenuContent renamed": (_m_help_renamed, [NO_HELP_BODY]),
    "tab indentation": (_m_tabs, [NO_TABS]),
}


@pytest.mark.parametrize("name", sorted(_MUTANTS))
def test_gate_catches(name: str) -> None:
    mutate, expected = _MUTANTS[name]
    mutant = "\n".join(mutate(_source())) + "\n"
    assert privacy_link_problems(mutant) == expected
