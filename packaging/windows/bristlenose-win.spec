# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the self-contained Windows x64 build of the Bristlenose
# CLI, packaged for winget (docs/design-winget.md).
#
# Forked from desktop/bristlenose-sidecar.spec. Differences, all deliberate:
#   - Transcription is faster-whisper (ctranslate2), not MLX, so ctranslate2 and
#     faster_whisper are COLLECTED here where the Mac spec excludes them.
#   - No App Store literal patches, no Mac credential store, no arm64 target.
#   - Entry is the whole CLI (packaging/windows/entry.py).
#
# Build from the repo root, inside a venv holding bristlenose (with its built
# SPA) and pyinstaller:  pyinstaller --noconfirm packaging\windows\bristlenose-win.spec

import importlib.util as _ilu
import os

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
# The package as installed in the build venv, so a wheel install works the same
# as an editable one (data dirs come from wherever `bristlenose` resolves).
PKG = os.path.dirname(_ilu.find_spec("bristlenose").origin)

# ctranslate2's __init__ loads every *.dll in its own folder, so the DLLs must
# land in _internal/ctranslate2/. pyinstaller-hooks-contrib has no hook for it.
_CT2_BINARIES = collect_dynamic_libs("ctranslate2")
# faster_whisper ships assets/silero_vad_v6.onnx; without it voice-activity
# detection fails at runtime.
_FW_DATAS = collect_data_files("faster_whisper")

# Same package-relative templates/statics/assets rule as the Mac spec: each of
# these loads its own data files by path at import or construction time.
_SQLADMIN_DATAS, _SQLADMIN_BINARIES, _SQLADMIN_HIDDEN = collect_all("sqladmin")
_JSONSCHEMA_SPEC_DATAS, _JSONSCHEMA_SPEC_BINARIES, _JSONSCHEMA_SPEC_HIDDEN = collect_all(
    "jsonschema_specifications"
)
_JSONSCHEMA_DATAS, _JSONSCHEMA_BINARIES, _JSONSCHEMA_HIDDEN = collect_all("jsonschema")

# Voice pass (optional at runtime): kaldi-native-fbank's DLLs and the licence
# notices the Mac build also carries.
_KNF_BINARIES = collect_dynamic_libs("kaldi_native_fbank")
_ORT_PKG = _ilu.find_spec("onnxruntime").submodule_search_locations[0]
_VOICE_NOTICES = [
    (os.path.join(_ORT_PKG, name), "onnxruntime")
    for name in ("LICENSE", "ThirdPartyNotices.txt")
    if os.path.exists(os.path.join(_ORT_PKG, name))
]
_VOICE_NOTICES += copy_metadata("kaldi-native-fbank")


def _pkg(*parts):
    """(source, dest) for a data folder of the installed package."""
    return (os.path.join(PKG, *parts), os.path.join("bristlenose", *parts))


a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[PROJECT_ROOT],
    binaries=[
        *_CT2_BINARIES,
        *_SQLADMIN_BINARIES,
        *_JSONSCHEMA_SPEC_BINARIES,
        *_JSONSCHEMA_BINARIES,
        *_KNF_BINARIES,
    ],
    datas=[
        *_FW_DATAS,
        *_SQLADMIN_DATAS,
        *_JSONSCHEMA_SPEC_DATAS,
        *_JSONSCHEMA_DATAS,
        *_VOICE_NOTICES,
        *copy_metadata("starlette"),
        *copy_metadata("bristlenose"),
        _pkg("theme"),
        _pkg("data"),
        _pkg("locales"),
        _pkg("llm", "prompts"),
        (os.path.join(PKG, "llm", "cohort-baselines.json"), os.path.join("bristlenose", "llm")),
        _pkg("server", "alembic"),
        _pkg("server", "static"),
        _pkg("server", "static-export"),
        _pkg("server", "codebook"),
    ],
    hiddenimports=[
        *_SQLADMIN_HIDDEN,
        *_JSONSCHEMA_SPEC_HIDDEN,
        *_JSONSCHEMA_HIDDEN,
        *collect_submodules("rich"),
        *collect_submodules("bristlenose"),
        "anthropic",
        "openai",
        "google.genai",
        "google.genai.types",
        "faster_whisper",
        "ctranslate2",
        "onnxruntime",
        "kaldi_native_fbank",
        "fastapi",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "mlx",
        "mlx_whisper",
        "en_core_web_lg",
        "torch",
        "torchgen",
        "torchvision",
        "functorch",
        "huggingface_hub.serialization._torch",
        "huggingface_hub.hub_mixin",
        "scipy._lib.array_api_compat.torch",
        "onnxruntime.transformers",
        "onnxruntime.quantization",
        "onnxruntime.tools",
        "pytest",
        "ruff",
        "mypy",
        "tkinter",
    ],
    noarchive=False,
    # typeguard rewrites inflect's decorated factory from source at import time;
    # the PYZ holds bytecode only (Mac spec, 16 May 2026).
    module_collection_mode={"inflect": "pyz+py"},
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bristlenose",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="bristlenose",
)
