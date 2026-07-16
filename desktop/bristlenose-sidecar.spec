# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the bristlenose desktop sidecar (Track C).
#
# Per docs/design-modularity.md:
#   - Mac is MLX-only (ctranslate2 + faster-whisper excluded)
#   - Presidio + spaCy excluded (Background Assets post-alpha)
#   - Keeps mlx + mlx_whisper (Apple Silicon transcription)
#
# Usage (via desktop/scripts/build-sidecar.sh):
#   cd <repo-root>
#   .venv/bin/python -m PyInstaller \
#       --distpath desktop/Bristlenose/Resources \
#       --workpath desktop/build/pyinstaller \
#       --clean --noconfirm \
#       desktop/bristlenose-sidecar.spec

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# PyInstaller's default analysis walks `import mlx.core` and copies
# core.cpython-312-darwin.so + libmlx.dylib, but misses libjaccl.dylib
# (linked by libmlx via @rpath), mlx.metallib (the compiled Metal shader
# library libmlx loads at first kernel dispatch), and a handful of small
# pure-python submodules that mlx's native init probes (`mlx.nn`,
# `mlx.optimizers`, `mlx.utils`, `mlx._distributed_utils`, etc.). Without
# all of them `import mlx_whisper` fails inside the bundled sidecar with
# either `Library not loaded: @rpath/libjaccl.dylib` or the more
# inscrutable nanobind `Encountered an error while initializing the
# extension.` Discovered during S3 bundle-trim (4 May 2026): pre-existing
# latent bug exposed by trimming torch, which had been masking the
# breakage by being the first thing to fail in the import chain.
# `collect_all` mirrors `pip install`'s view of the package, which is
# what mlx_metal's wheel layout assumes at runtime.
_MLX_DATAS, _MLX_BINARIES, _MLX_HIDDEN = collect_all("mlx")

# `mlx_whisper/assets/` ships three data files that PyInstaller's
# modulegraph (which only walks `import` statements) doesn't see:
# `mel_filters.npz` (loaded by `mlx_whisper/audio.py::mel_filters` via
# `mx.load(... "assets/mel_filters.npz")`) and the GPT-2 / multilingual
# tiktoken vocabularies. Without these the bundle imports `mlx_whisper`
# fine but the first transcribe call dies with `[load_npz] Input must
# be a zip file …` because `os.path.dirname(__file__) + "/assets/…"`
# resolves to a path that doesn't exist in the bundle. Found via
# end-to-end smoke test post-S3 (4 May 2026) — same class of bug as
# the mlx-metal artefacts that were missing pre-S3.
_MLX_WHISPER_DATAS, _MLX_WHISPER_BINARIES, _MLX_WHISPER_HIDDEN = collect_all(
    "mlx_whisper"
)

# SQLAdmin ships Jinja2 templates (`sqladmin/templates/`) and static assets
# (`sqladmin/statics/`) that PyInstaller's modulegraph doesn't see — it only
# walks `import` statements. A bare `sqladmin` hiddenimport bundles the module
# code into the PYZ but leaves the data files behind, so `Admin(...)`'s
# `PackageLoader("sqladmin", "templates")` dies at construction with
# `ValueError: PackageLoader could not find a 'templates/sqladmin' directory`.
# Only reached when the admin panel is mounted (`serve --dev` or
# `_BRISTLENOSE_ADMIN_PANEL=1` from the desktop Debug menu), so it doesn't fire
# on a normal serve — but a crash-on-mount all the same. `collect_all` mirrors
# `pip install`'s view (templates + statics + submodules). Found 14 Jul 2026
# when the Debug-menu admin panel SIGed the bundled sidecar with exit 1.
_SQLADMIN_DATAS, _SQLADMIN_BINARIES, _SQLADMIN_HIDDEN = collect_all("sqladmin")

a = Analysis(
    # Entry point: run `bristlenose serve` directly.
    [os.path.join(SPECPATH, "sidecar_entry.py")],
    pathex=[PROJECT_ROOT],
    binaries=[*_MLX_BINARIES, *_MLX_WHISPER_BINARIES, *_SQLADMIN_BINARIES],
    datas=[
        *_MLX_DATAS,
        *_MLX_WHISPER_DATAS,
        *_SQLADMIN_DATAS,
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
        # LLM prompt templates (.md files loaded at runtime by
        # bristlenose/llm/prompts/__init__.py::_load_prompt). Every
        # LLM-using stage reads from here — topic-segmentation,
        # quote-extraction, thematic-grouping, autocode, etc.
        # Without this entry, every LLM call fails with FileNotFoundError
        # before reaching the provider (BUG-5 from the C3 smoke test,
        # 21 Apr 2026).
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "llm", "prompts"),
            os.path.join("bristlenose", "llm", "prompts"),
        ),
        # Cohort baselines for LLM cost forecasting (bristlenose/llm/pricing.py
        # ::_load_baselines reads at runtime). Falls back to empty list on
        # missing file, but cost-forecast quality degrades — ship the file.
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "llm", "cohort-baselines.json"),
            os.path.join("bristlenose", "llm"),
        ),
        # Alembic migrations (read at runtime by server/db.py).
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "server", "alembic"),
            os.path.join("bristlenose", "server", "alembic"),
        ),
        # React SPA build output. Generated by `cd frontend && npm run build`,
        # gitignored at the source. PyInstaller will fail loudly if this
        # directory is missing — that's intentional, the build script must
        # ensure the React bundle is present before sidecar packaging.
        # Without this entry the sidecar serves the deprecated static-render
        # HTML for everything (BUG-3 from the C3 smoke test, 21 Apr 2026).
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "server", "static"),
            os.path.join("bristlenose", "server", "static"),
        ),
        # YAML codebook templates (garrett, morville, norman, uxr, plato).
        # Loaded by routes/codebook.py and exposed via the Browse Codebooks
        # modal. Without this entry the CODEBOOK FRAMEWORKS list is empty
        # (BUG-4 from the C3 smoke test, 21 Apr 2026).
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "server", "codebook"),
            os.path.join("bristlenose", "server", "codebook"),
        ),
        # LLM cost-baselines (alpha-telemetry Slice A, 27 Apr 2026).
        # bristlenose/llm/pricing.py:68 loads this at runtime via
        # `Path(__file__).parent / "cohort-baselines.json"` for the
        # baseline-fallback path of cost forecasting. Without this entry
        # the sidecar can't resolve baselines and falls back to whatever
        # the no-baseline path does — silent in unit tests because they
        # run against `pip install -e .` where __file__ resolves correctly.
        (
            os.path.join(PROJECT_ROOT, "bristlenose", "llm", "cohort-baselines.json"),
            os.path.join("bristlenose", "llm"),
        ),
    ],
    hiddenimports=[
        # Build provenance, generated by build-sidecar.sh before this runs.
        # Imported via try/except in bristlenose/_build.py, so static analysis
        # misses it without this hint.
        "bristlenose._build_info",
        *_MLX_HIDDEN,
        *_MLX_WHISPER_HIDDEN,
        *_SQLADMIN_HIDDEN,
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
        # Orphan checkpoint-conversion tool inside mlx_whisper. Top-level
        # `import torch` pulls ~284 MB of torch into the bundle, but nothing
        # in mlx_whisper (or anywhere else) actually imports torch_whisper —
        # it's a dev utility for converting OpenAI Whisper checkpoints to
        # MLX format. Excluding it sheds torch entirely. Verified orphan via
        # `grep -rn torch_whisper site-packages/mlx_whisper/` (4 May 2026).
        "mlx_whisper.torch_whisper",
        # S3 step 1: huggingface_hub.serialization._torch does `import torch`
        # at top level. mlx_whisper only uses huggingface_hub.snapshot_download
        # for model HTTP fetches — verified in load_models.py — so the torch-
        # serialisation submodule is dead weight. Removing it kills one of the
        # four torch-import edges PyInstaller's modulegraph follows.
        "huggingface_hub.serialization._torch",
        # huggingface_hub.hub_mixin defines a PyTorchModelHubMixin that does
        # `import torch` at top level. mlx_whisper doesn't use the mixin
        # (only snapshot_download), so it's another dead torch caller.
        "huggingface_hub.hub_mixin",
        # S3 step 2: scipy probes torch on import via the array-API-compat
        # shim. mlx_whisper doesn't ask scipy to operate on torch tensors
        # (it uses MLX arrays exclusively), so the whole .torch subpackage
        # is dead under our usage. Keeps the rest of scipy intact.
        "scipy._lib.array_api_compat.torch",
        # S3 step 3: onnxruntime is reached via faster_whisper.vad and via
        # torch.onnx._internal.exporter. Both upstreams are excluded /
        # unused on Mac (faster_whisper already in excludes; torch is MLX-
        # alternative-path, not us). Dropping the whole package sheds 58 MB
        # AND removes onnxruntime.transformers.machine_info from torch's
        # incoming-edge list.
        "onnxruntime",
        # S3 step 4: torch (288 MB) — the headline trim. After steps 1–3
        # the only remaining torch importers in the modulegraph are
        # functorch.* (torch's own internal cycle, gone with torch) and
        # scipy._lib.array_api_compat.common._helpers (a generic helper
        # that probes torch via try/except — safe under MLX-only). Mac
        # transcription path is MLX (mlx_whisper); torch has no load-
        # bearing role at runtime per design-modularity.md "Mac is
        # MLX-only".
        "torch",
        "torchgen",
        "torchvision",
        "functorch",
        "pytest",
        "pytest_cov",
        "pytest_asyncio",
        "ruff",
        "mypy",
    ],
    noarchive=False,
    # `inflect` (used by bristlenose/utils/text.py::count_noun) decorates its
    # `engine()` factory with typeguard's @typechecked at import time.
    # typeguard 4.x rewrites the decorated function's AST via
    # `inspect.getsource`, which fails inside a frozen PyInstaller bundle
    # because the package is only shipped as bytecode in PYZ — no .py source
    # for inspect to read. Result: import-time OSError "could not get source
    # code" before the sidecar serves a byte. Fix: tell PyInstaller to also
    # collect inflect's source files alongside the bytecode.
    # Hit 16 May 2026 on the multi-project-folder-watcher acceptance walk.
    module_collection_mode={
        "inflect": "pyz+py",
    },
)

# --- App Store §2.5.2 compliance: strip the `itms-services` literal ---
# CPython's Lib/urllib/parse.py lists 'itms-services' among the known URL
# schemes (uses_relative / uses_netloc / uses_params). App Store Connect's
# automated static scan rejects any binary that CONTAINS that literal —
# "the app uses the itms-services URL scheme to install an app" — EVEN when
# the code is never executed (real bundled-Python rejections in 2024;
# CPython gh-120522, fixed upstream by the `--with-app-store-compliance`
# configure flag in gh-120984). Homebrew's python@3.12 is NOT built with
# that flag (verify: `python3 -c "import sysconfig;
# print(sysconfig.get_config_var('CONFIG_ARGS'))"` — no app-store-compliance),
# so the literal survives into the frozen `urllib.parse` inside the PYZ.
#
# The literal is marshalled into the module's code object and the PYZ is
# zlib-compressed, so it is INVISIBLE to `strings`/`grep` on the bundle
# (which is exactly why the post-build gate,
# desktop/scripts/check-sidecar-appstore-strings.sh, decompresses the PYZ
# and scans code-object constants rather than grepping bytes).
#
# Fix: recompile `urllib.parse` from a length-preserving-patched copy of its
# own source ('itms-services' -> 'itmx-services') and replace the cached code
# object that PYZ.assemble would otherwise freeze. PYZ() copies code objects
# out of CONF['code_cache'][id(a.pure)] at construction time, so we patch
# that cache BEFORE constructing the PYZ below. The scheme is never parsed by
# Bristlenose, so the rename is entirely inert. Belt-and-suspenders: the
# post-build gate re-verifies the assembled bundle and fails the build if the
# literal survived (e.g. if PyInstaller internals shift and this patch stops
# taking effect).
def _strip_app_store_noncompliant_strings(analysis):
    from PyInstaller.config import CONF

    needle = "itms-services"
    replacement = "itmx-services"  # same length — byte offsets preserved
    module = "urllib.parse"

    code_cache = CONF["code_cache"].get(id(analysis.pure))
    if code_cache is None or module not in code_cache:
        raise SystemExit(
            f"app-store-compliance spec patch: {module!r} not found in the "
            "PyInstaller code cache — PyInstaller internals changed. Update "
            "this patch (the post-build gate would otherwise fail the build)."
        )

    src_path = next(
        (path for name, path, _tc in analysis.pure if name == module), None
    )
    if not src_path or not os.path.isfile(src_path):
        raise SystemExit(
            f"app-store-compliance spec patch: could not resolve source for {module!r}."
        )

    with open(src_path, encoding="utf-8") as fh:
        original = fh.read()
    if needle not in original:
        # Already compliant (e.g. a future --with-app-store-compliance CPython).
        return
    patched = original.replace(f"'{needle}'", f"'{replacement}'").replace(
        f'"{needle}"', f'"{replacement}"'
    )
    if needle in patched:
        raise SystemExit(
            f"app-store-compliance spec patch: {needle!r} still present after "
            "quoted replacement — an unquoted occurrence exists. Update the patch."
        )

    # optimize=0 matches PyInstaller's PYMODULE typecode (plain `python -m
    # PyInstaller`, no -O). co_filename stays the real stdlib path so
    # tracebacks are unchanged.
    code_cache[module] = compile(patched, src_path, "exec", optimize=0)


_strip_app_store_noncompliant_strings(a)

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
