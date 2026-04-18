# -*- mode: python ; coding: utf-8 -*-
# Track C C0 spike spec — trimmed per docs/design-modularity.md.
#
# Differences from desktop/v0.1-archive/bristlenose-sidecar.spec:
#   - Excludes ctranslate2 + faster-whisper (Mac is MLX-only)
#   - Excludes presidio-* + spacy (not in alpha scope)
#   - Keeps mlx + mlx_whisper (Apple Silicon transcription)
#   - Scoped to `bristlenose serve` (sidecar entry point), not full CLI
#
# Usage:
#   cd /Users/cassio/Code/bristlenose_branch\ sidecar-signing
#   .venv/bin/python -m PyInstaller \
#       --distpath desktop/sidecar-c0/dist \
#       --workpath desktop/sidecar-c0/build \
#       --clean --noconfirm \
#       desktop/sidecar-c0/bristlenose-sidecar.spec

import os

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

a = Analysis(
    # Entry point: run `bristlenose serve` directly.
    [os.path.join(SPECPATH, "sidecar_entry.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "theme"),
            os.path.join("bristlenose", "theme"),
        ),
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "data"),
            os.path.join("bristlenose", "data"),
        ),
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "locales"),
            os.path.join("bristlenose", "locales"),
        ),
        # Alembic migrations (read at runtime by server/db.py).
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "server", "alembic"),
            os.path.join("bristlenose", "server", "alembic"),
        ),
    ],
    hiddenimports=[
        *collect_submodules("rich"),
        # LLM providers (dynamically imported in llm/client.py)
        "anthropic",
        "openai",
        "google.genai",
        "google.genai.types",
        # MLX only — no ctranslate2/faster-whisper in the sidecar.
        "mlx",
        "mlx_whisper",
        # Serve mode
        "fastapi",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "sqlalchemy",
        "sqlalchemy.dialects.sqlite",
        "sqladmin",
        # Bristlenose lazy imports
        "bristlenose.server",
        "bristlenose.server.app",
        "bristlenose.server.db",
        "bristlenose.server.models",
        "bristlenose.server.importer",
        "bristlenose.server.admin",
        "bristlenose.server.routes",
        "bristlenose.server.routes.codebook",
        "bristlenose.server.routes.dashboard",
        "bristlenose.server.routes.data",
        "bristlenose.server.routes.dev",
        "bristlenose.server.routes.health",
        "bristlenose.server.routes.quotes",
        "bristlenose.server.routes.sessions",
        "bristlenose.server.routes.transcript",
        "bristlenose.ollama",
        "bristlenose.providers",
        "bristlenose.credentials_macos",
        "bristlenose.analysis",
        "bristlenose.analysis.matrix",
        "bristlenose.analysis.signals",
        "bristlenose.analysis.metrics",
        "bristlenose.analysis.models",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Explicitly excluded per design-modularity.md.
        "ctranslate2",
        "faster_whisper",
        "presidio_analyzer",
        "presidio_anonymizer",
        "spacy",
        "en_core_web_lg",
        # Dev-only
        "pytest",
        "pytest_cov",
        "pytest_asyncio",
        "ruff",
        "mypy",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bristlenose-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    name="bristlenose-sidecar",
)
