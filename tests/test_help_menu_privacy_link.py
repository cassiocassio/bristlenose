"""The Mac app's Help menu links the privacy policy in every build, unconditionally.

App Store Review Guideline 5.1.1(i) wants the privacy policy reachable inside the
app. Only one link satisfies that. `NewsPreferences.privacyURL` renders only when
`NewsKeys.isLive`, and the paywall's link shows only at the paywall. So the
guarantee is **Help ▸ Privacy Policy** (`HelpMenuContent` in `MenuCommands.swift`,
added 21 Nov 2026 in 2fcecac61).

Nothing else pins it. The menu is a private SwiftUI view with no test seam, and
the most natural edit to break it is to wrap the button in an `if` or `#if`
("only on the App Store build", "only once news is live"). It would compile, and
the review would fail. So this test reads the source and checks that the button:

1. exists, with its key, and opens the policy URL;
2. sits at the top level of `HelpMenuContent.body`, so no `if`, `Group`, or other
   block wraps it, and no `#if` is open around it;
3. carries no `.disabled(` or `.hidden(` modifier;
4. is reached, because `CommandGroup(replacing: .help)` with `HelpMenuContent` sits
   at the top level of the menu's `Commands.body` as well.

If you restructure the menu *without* making the link conditional, update this
test. If you make it conditional, put an unconditional link somewhere else first.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MENU_COMMANDS = _ROOT / "desktop/Bristlenose/Bristlenose/MenuCommands.swift"

PRIVACY_KEY = "desktop.menu.help.privacyPolicy"
PRIVACY_URL = "https://bristlenose.app/privacy.html"
_BUTTON = f'Button(i18n.t("{PRIVACY_KEY}"))'


def _blank(source: str) -> tuple[str, str]:
    """Return (code, structure), both the same length as `source`.

    `code` has comments blanked to spaces, with string literals kept. `structure`
    also blanks string-literal contents, so a brace or `#if` inside a string or
    comment never counts.
    """
    code: list[str] = []
    structure: list[str] = []
    i, n = 0, len(source)
    while i < n:
        two = source[i : i + 2]
        if two == "//":
            j = source.find("\n", i)
            j = n if j == -1 else j
            code.append(" " * (j - i))
            structure.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = source.find("*/", i + 2)
            j = n if j == -1 else j + 2
            gap = re.sub(r"[^\n]", " ", source[i:j])
            code.append(gap)
            structure.append(gap)
            i = j
        elif source[i] == '"':
            j = i + 1
            while j < n and source[j] != '"':
                j += 2 if source[j] == "\\" else 1
            j = min(j + 1, n)
            code.append(source[i:j])
            structure.append('"' + " " * (j - i - 2) + '"' if j - i >= 2 else source[i:j])
            i = j
        else:
            code.append(source[i])
            structure.append(source[i])
            i += 1
    return "".join(code), "".join(structure)


def _depth(structure: str, pos: int) -> int:
    head = structure[:pos]
    return head.count("{") - head.count("}")


def _open_ifs(structure: str, pos: int) -> int:
    head = structure[:pos]
    return len(re.findall(r"#if\b", head)) - len(re.findall(r"#endif\b", head))


def _matching_brace(structure: str, open_pos: int) -> int:
    depth = 0
    for k in range(open_pos, len(structure)):
        if structure[k] == "{":
            depth += 1
        elif structure[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    raise AssertionError("unbalanced braces in MenuCommands.swift")


def _body_start(code: str, structure: str, after: int, signature: str) -> int:
    """Index just inside the `{` of the first `signature {` at or after `after`."""
    pos = code.find(signature, after)
    assert pos != -1, f"`{signature}` not found in MenuCommands.swift"
    brace = structure.find("{", pos + len(signature))
    return brace + 1


def privacy_link_problems(source: str) -> list[str]:
    """Every reason the Help menu's privacy link is missing or conditional."""
    code, structure = _blank(source)
    problems: list[str] = []

    # The Help menu reaches the menu bar unconditionally.
    group = code.find("CommandGroup(replacing: .help)")
    app_info = code.find("CommandGroup(replacing: .appInfo)")
    if group == -1:
        problems.append("no `CommandGroup(replacing: .help)`")
    else:
        if app_info != -1 and _depth(structure, group) != _depth(structure, app_info):
            problems.append("the Help CommandGroup is nested inside a block")
        if _open_ifs(structure, group):
            problems.append("the Help CommandGroup sits inside an `#if`")
        brace = structure.find("{", group)
        inner = code[brace : _matching_brace(structure, brace)]
        if "HelpMenuContent(" not in inner:
            problems.append("the Help CommandGroup no longer builds HelpMenuContent")

    # The button, at the top level of HelpMenuContent.body.
    struct = code.find("struct HelpMenuContent")
    if struct == -1:
        return [*problems, "no `struct HelpMenuContent`"]
    body = _body_start(code, structure, struct, "var body: some View")
    body_end = _matching_brace(structure, body - 1)
    button = code.find(_BUTTON, body, body_end)
    if button == -1:
        return [*problems, f"HelpMenuContent.body has no `{_BUTTON}`"]
    if _depth(structure, button) != _depth(structure, body):
        problems.append("the privacy button is nested inside a block (an `if`, a `Group`…)")
    if _open_ifs(structure, button):
        problems.append("the privacy button sits inside an `#if`")

    action_open = structure.find("{", button + len(_BUTTON))
    action_close = _matching_brace(structure, action_open)
    if f'Self.open("{PRIVACY_URL}")' not in code[action_open:action_close]:
        problems.append(f"the privacy button does not open {PRIVACY_URL}")
    trailing = code[action_close + 1 :].lstrip()
    if re.match(r"\.(disabled|hidden)\(", trailing):
        problems.append("the privacy button is disabled or hidden by a modifier")
    return problems


def test_help_menu_links_the_privacy_policy_unconditionally() -> None:
    problems = privacy_link_problems(_MENU_COMMANDS.read_text(encoding="utf-8"))
    assert not problems, (
        "Help ▸ Privacy Policy is the app's only unconditional link to the privacy "
        "policy (App Store Guideline 5.1.1(i)). Problems: " + "; ".join(problems)
    )


# The gate must be able to fail. Each mutation is a plausible edit that would
# lose the unconditional link; the real source must pass and each mutant must not.
_ORIGINAL_BLOCK = f"""        Button(i18n.t("{PRIVACY_KEY}")) {{
            Self.open("{PRIVACY_URL}")
        }}
"""

_MUTATIONS = {
    "wrapped in if": (
        "        if NewsKeys.isLive {\n" + _ORIGINAL_BLOCK + "        }\n"
    ),
    "wrapped in #if": "        #if APPSTORE\n" + _ORIGINAL_BLOCK + "        #endif\n",
    "disabled": _ORIGINAL_BLOCK.rstrip("\n") + "\n        .disabled(true)\n",
    "wrong url": _ORIGINAL_BLOCK.replace(PRIVACY_URL, "https://bristlenose.app/docs/"),
    "removed": "",
    "commented out": "".join(f"// {line}\n" for line in _ORIGINAL_BLOCK.splitlines()),
}


@pytest.mark.parametrize("name", sorted(_MUTATIONS))
def test_gate_catches(name: str) -> None:
    source = _MENU_COMMANDS.read_text(encoding="utf-8")
    assert source.count(_ORIGINAL_BLOCK) == 1, (
        "the privacy button's block changed shape; update _ORIGINAL_BLOCK"
    )
    mutant = source.replace(_ORIGINAL_BLOCK, _MUTATIONS[name])
    assert privacy_link_problems(mutant), f"mutation {name!r} went unnoticed"


def test_gate_catches_help_menu_wrapped_in_if() -> None:
    source = _MENU_COMMANDS.read_text(encoding="utf-8")
    group = "        CommandGroup(replacing: .help) {"
    assert source.count(group) == 1
    mutant = source.replace(group, "        if showsHelp {\n" + group, 1)
    # Close the `if` after the group's own closing brace.
    start = mutant.index(group)
    _code, structure = _blank(mutant)
    close = _matching_brace(structure, structure.index("{", start))
    mutant = mutant[: close + 1] + "\n        }" + mutant[close + 1 :]
    assert privacy_link_problems(mutant), "a conditional Help menu went unnoticed"
