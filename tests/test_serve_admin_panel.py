"""Tests for the SQLAdmin panel mount gate + read-only flag.

The `/admin` DB browser is mounted under full `serve --dev` (CRUD) OR the
`_BRISTLENOSE_ADMIN_PANEL=1` env gate (read-only, for desktop beta builds).
It is never mounted in the App Store build (the env var is never set there).
See docs/design-desktop-debug-admin-panel.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from bristlenose.server.admin import _ADMIN_VIEWS, register_admin_views
from bristlenose.server.app import create_app


def _admin_mounted(app: object) -> bool:
    return any(getattr(r, "path", None) == "/admin" for r in app.routes)  # type: ignore[attr-defined]


def _make_app(tmp_path: Path, *, dev: bool, admin_env: bool):
    output_dir = tmp_path / "bristlenose-output"
    output_dir.mkdir(exist_ok=True)
    env = {"_BRISTLENOSE_ADMIN_PANEL": "1"} if admin_env else {}
    with patch.dict("os.environ", env, clear=False):
        return create_app(project_dir=tmp_path, dev=dev, db_url="sqlite://")


class TestAdminMountGate:
    def test_not_mounted_in_app_store_build(self, tmp_path: Path) -> None:
        # No dev, no env var → App Store final build: route absent.
        app = _make_app(tmp_path, dev=False, admin_env=False)
        assert not _admin_mounted(app)

    def test_mounted_when_env_gate_set(self, tmp_path: Path) -> None:
        # Bundled beta channel sets the env var → route present.
        app = _make_app(tmp_path, dev=False, admin_env=True)
        assert _admin_mounted(app)

    def test_mounted_under_full_dev(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path, dev=True, admin_env=False)
        assert _admin_mounted(app)


class TestReadOnlyFlag:
    def test_read_only_strips_mutation_affordances(self) -> None:
        recorded: list[type] = []

        class _StubAdmin:
            def add_view(self, view: type) -> None:
                recorded.append(view)

        try:
            register_admin_views(_StubAdmin(), read_only=True)  # type: ignore[arg-type]
            assert recorded == _ADMIN_VIEWS
            for view in _ADMIN_VIEWS:
                assert view.can_create is False
                assert view.can_edit is False
                assert view.can_delete is False
                # can_export off too — else read-only /admin still allows an
                # unauthenticated GET .../export/csv full-table PII dump.
                assert view.can_export is False

            # A subsequent full-CRUD registration restores the affordances
            # (flags must not leak across calls — the views are singletons).
            register_admin_views(_StubAdmin(), read_only=False)  # type: ignore[arg-type]
            for view in _ADMIN_VIEWS:
                assert view.can_create is True
                assert view.can_edit is True
                assert view.can_delete is True
                assert view.can_export is True
        finally:
            # Leave the module-level singletons in their default (CRUD) state.
            for view in _ADMIN_VIEWS:
                view.can_create = True
                view.can_edit = True
                view.can_delete = True
                view.can_export = True
