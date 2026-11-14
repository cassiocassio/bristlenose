"""The two Claude plugin manifests must agree on everything that forms the id.

Claude builds an installed extension's id from ``author.name`` as well as
``name`` (measured 13 Nov 2026: ``local.mcpb.martin-storey.bristlenose``), and it
replaces an install only when the id matches and the version is higher. The Node
manifest (``desktop/mcpb/manifest.json``, the fallback) and the one the native
package generates (``NativeExtensionPackage.manifest``) are written separately,
so a drift in either installs a second copy beside the first instead of
replacing it. See ``desktop/gotchas.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_NODE = _REPO / "desktop" / "mcpb" / "manifest.json"
_SWIFT = _REPO / "desktop" / "Bristlenose" / "Bristlenose" / "NativeExtensionPackage.swift"


def _swift_string(key: str, text: str) -> str:
    m = re.search(rf'"{re.escape(key)}":\s*"([^"]*)"', text)
    assert m, f"NativeExtensionPackage.swift has no string value for {key!r}"
    return m.group(1)


def test_the_node_and_native_manifests_share_their_id_and_publisher() -> None:
    node = json.loads(_NODE.read_text(encoding="utf-8"))
    swift = _SWIFT.read_text(encoding="utf-8")

    assert _swift_string("name", swift) == node["name"]
    assert _swift_string("display_name", swift) == node["display_name"]
    assert _swift_string("description", swift) == node["description"]
    assert _swift_string("homepage", swift) == node["homepage"]
    assert _swift_string("license", swift) == node["license"]

    # The author and repository are nested dictionaries on the Swift side
    # (`"author": ["name": "...", "url": "..."]`), so read the literal block.
    author = re.search(r'"author":\s*\[([^\]]*)\]', swift)
    assert author, "NativeExtensionPackage.swift has no author literal"
    assert _swift_string("name", author.group(1)) == node["author"]["name"]
    assert _swift_string("url", author.group(1)) == node["author"]["url"]
    repo = re.search(r'"repository":\s*\[([^\]]*)\]', swift)
    assert repo, "NativeExtensionPackage.swift has no repository literal"
    assert _swift_string("url", repo.group(1)) == node["repository"]["url"]
