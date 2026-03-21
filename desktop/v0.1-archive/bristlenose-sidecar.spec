# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the bristlenose desktop sidecar binary.
# Builds a --onedir bundle for fast startup inside the macOS .app.
#
# Usage:
#   pyinstaller --distpath Resources --workpath build/pyinstaller \
#               --clean --noconfirm bristlenose-sidecar.spec

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH is set by PyInstaller to the directory containing this spec file.
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(PROJECT_ROOT, "bristlenose", "__main__.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # Theme assets (CSS, JS, HTML templates, images)
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "theme"),
            os.path.join("bristlenose", "theme"),
        ),
        # Data files (man page, surname list, honorifics)
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "data"),
            os.path.join("bristlenose", "data"),
        ),
        # faster_whisper ships a Silero VAD ONNX model in its assets/ directory
        *collect_data_files("faster_whisper"),
    ],
    hiddenimports=[
        # --- rich (hyphenated _unicode_data modules not detected by PyInstaller) ---
        *collect_submodules("rich"),
        # --- LLM providers (dynamically imported in llm/client.py) ---
        "anthropic",
        "openai",
        "google.genai",
        "google.genai.types",
        # --- Transcription backends (imported in stages/transcribe.py) ---
        "faster_whisper",
        "ctranslate2",
        # MLX (optional — included when building on Apple Silicon)
        "mlx",
        "mlx_whisper",
        # --- PII detection (imported in doctor.py / pipeline.py) ---
        "presidio_analyzer",
        "presidio_anonymizer",
        "spacy",
        # --- Serve mode (imported in cli.py / server/) ---
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
        # --- Bristlenose lazy imports ---
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
        # Dev-only packages — not needed at runtime
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
    exclude_binaries=True,  # --onedir mode
    name="bristlenose-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,  # UPX causes issues with signed macOS binaries
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
