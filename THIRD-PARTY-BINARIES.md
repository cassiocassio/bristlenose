# Third-party binaries shipped in Bristlenose

Canonical inventory of every non-Bristlenose binary that ships in
`Bristlenose.app/Contents/Resources/`. Maintained as part of Track C C5
(supply-chain provenance). Procurement reviewers, CVE responders, and
future-Martin all read this file first.

This file covers the **macOS desktop app** specifically. CLI distributions
(Homebrew, Snap, pip) bundle nothing of their own — they pull from the
system / package manager and the user's chosen Python environment.

**For a scanner, read the SBOM, not this file.** `desktop/scripts/build-dmg.sh`
emits `Bristlenose-<version>.sidecar-sbom.json` — CycloneDX 1.6, generated from
`.venv-sidecar`, hashed into the build manifest beside the `.dmg` — and that is
the machine-readable answer. This Markdown is for people, and it is deliberately
an **over-estimate**: it lists what is installed in the venv the bundle is built
from, and PyInstaller may strip transitive packages nothing imports. The bundle's
own metadata is a third answer and the least useful one — pure-Python packages
are bytecompiled into the archive and leave no `dist-info` unless the spec
`copy_metadata`s them, so a scanner reading `_internal/` sees roughly 21
packages, one of which (`presidio_analyzer`) is metadata for code the spec
excludes. Three counts, one artefact to hand over.

## Native binaries (hand-curated)

These are signed under our Apple Distribution identity (Team ID
`Z56GZVA2QB`) at build time.

**FFmpeg is built by us, from source.** `desktop/scripts/build-ffmpeg-lgpl.sh`
(called by `fetch-ffmpeg.sh`) downloads the six release tarballs below, checks
each against the SHA256 pinned in the script, and builds one static arm64
`ffmpeg` and `ffprobe` that link only macOS's own libraries. It is an
LGPL-2.1-or-later build: no `--enable-gpl`, `--enable-nonfree` or
`--enable-version3`, and the script refuses to hand over a binary whose embedded
configure line has one, that links outside `/usr/lib` and `/System/Library`, or
that lacks the `subtitles` filter, the VideoToolbox H.264 encoder or dav1d. The
complete corresponding source is those six tarballs, unmodified, plus that
script. The binaries are not bit-reproducible across Xcode versions, so the
pins are on the sources; `fetch-ffmpeg.sh` prints the binaries' SHA256 when it
installs them. A signed `build-all.sh` then reads the copies inside the exported
app with `check-ffmpeg-licence.sh` and stops if either was configured with
`--enable-gpl`, `--enable-nonfree`, `--enable-version3`, x264 or x265, or if any
of its libraries' embedded licence strings says anything but "LGPL version 2.1
or later".

Until 25 Nov 2026 the app bundled martin-riedl.de's static build, a **GPL**
build (`--enable-gpl --enable-libx264 --enable-libx265`; the binary on disk
reported 8.0.1 although the script pinned an 8.1 zip), which this table
wrongly listed as LGPL-2.1+. A GPL binary can't ship under Apple's EULA, and no
reputable source publishes a static LGPL macOS arm64 build with libass, hence
the build. Clip export's burnt-in subtitles, the one feature that used x264,
now encode with Apple's VideoToolbox in the app (`h264_videotoolbox`); the CLI
keeps x264 wherever the system FFmpeg has it.

| Binary | Version | Origin | SHA256 | Licence |
|---|---|---|---|---|
| `ffmpeg` | 8.1.3 (`8.1.3-bristlenose-lgpl-1`) | Built by `desktop/scripts/build-ffmpeg-lgpl.sh` from <https://ffmpeg.org/releases/ffmpeg-8.1.3.tar.xz> | source tarball `7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3` | LGPL-2.1-or-later. Configure: `--disable-autodetect --disable-network --disable-indevs --enable-indev=lavfi --disable-outdevs --enable-videotoolbox --enable-audiotoolbox --enable-zlib --enable-bzlib --enable-iconv --enable-libass --enable-libfreetype --enable-libharfbuzz --enable-libfribidi --enable-libdav1d`, static, no ffplay |
| `ffprobe` | 8.1.3 (`8.1.3-bristlenose-lgpl-1`) | the same build | the same | LGPL-2.1-or-later, the same configure line |
| libass, statically linked into both (the `subtitles` filter) | 0.17.5 | <https://github.com/libass/libass/releases/download/0.17.5/libass-0.17.5.tar.xz> | `2dca25c0e0c837ddf00b52011b3f82cac1e4ddd3ad018227806b0c2288864acc` | ISC |
| FreeType, statically linked (libass's rasteriser) | 2.14.3 | <https://download.savannah.gnu.org/releases/freetype/freetype-2.14.3.tar.xz> | `36bc4f1cc413335368ee656c42afca65c5a3987e8768cc28cf11ba775e785a5f` | FreeType Licence (FTL), chosen from its FTL-or-GPL-2.0 dual licence |
| FriBidi, statically linked (libass's bidirectional text) | 1.0.18 | <https://github.com/fribidi/fribidi/releases/download/v1.0.18/fribidi-1.0.18.tar.xz> | `1de5e8073d035388b71d0b2d452b1da1f8caeea8a7702997b401fe1b6250727f` | LGPL-2.1-or-later |
| HarfBuzz, statically linked (libass's shaper) | 15.1.0 | <https://github.com/harfbuzz/harfbuzz/releases/download/15.1.0/harfbuzz-15.1.0.tar.xz> | `0fc7c565443a5f4be7da65ac5ee5bd737d9b158dc908708b7689a0a5796b0c8d` | MIT ("Old MIT") |
| dav1d, statically linked (AV1 decoding) | 1.5.5 | <https://downloads.videolan.org/pub/videolan/dav1d/1.5.5/dav1d-1.5.5.tar.xz> | `ca96b1d0ba3f01f55de7231d775892b64994ba061aaeeaaa4f662a390b3abf9e` | BSD-2-Clause |
| `Python.framework` | 3.12.x | Copied from the build runner's installed Python (today: developer's local `python3.12`; a future GitHub Actions desktop-build job would use `actions/setup-python@v5` which is `python-build-standalone`) | _captured per build in `desktop/build/sign-manifest.json`_ | Python Software Foundation Licence |
| PyInstaller bootloader (`bristlenose-sidecar` outer binary) | 6.x | <https://pyinstaller.org> | _captured per build in `desktop/build/sign-manifest.json`_ | GPL-2.0-or-later WITH PyInstaller-bootloader-exception (proprietary apps may embed the bootloader; see <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt>) |
| ONNX Runtime Python binding (`onnxruntime/capi/onnxruntime_pybind11_state.so`, the voice pass) | as resolved in `.venv-sidecar` (its wheel row is in the auto block below) | <https://github.com/microsoft/onnxruntime> | _signed per build; listed in `desktop/build/sign-manifest.json`_ | MIT; statically links Abseil, Protobuf, flatbuffers, cpuinfo, Eigen and more — the package's `ThirdPartyNotices.txt` lists them, none is GPL-only, and it ships in the bundle at `_internal/onnxruntime/` beside `LICENSE` (the spec refuses to build without them). The package's C library `libonnxruntime.<ver>.dylib` is **not** shipped: the binding links the runtime statically, and the spec drops it |
| kaldi-native-fbank (`_kaldi_native_fbank.cpython-312-darwin.so`, `libkaldi-native-fbank-core.dylib`, the voice pass's feature front end) | as resolved in `.venv-sidecar` (auto block below) | <https://github.com/csukuangfj/kaldi-native-fbank> | _signed per build; listed in `desktop/build/sign-manifest.json`_ | Apache-2.0. Replaced sherpa-onnx on 4 Oct 2026, whose wheels statically link espeak-ng (GPL-3.0-or-later): `docs/design-voice-diarization.md` § Licence |

### Bundled inside Python.framework (auto-generated)

`Python.framework` rolls up several C libraries that procurement reviewers want broken out for CVE matching. Versions move with whichever Python the build runner installed; bumps land when that Python is upgraded.

<!-- BEGIN AUTO: framework-libs -->
| Library | Version | Where it lives in the bundle |
|---|---|---|
| `Python` | 3.12.13 | The interpreter that created `.venv-sidecar` (Homebrew `python3.12` on the dev Mac today) |
| `OpenSSL` | 3.6.3 | Linked into `_ssl` and `_hashlib` |
| `SQLite` | 3.53.3 | Linked into `_sqlite3` |
| `zlib` | 1.2.12 | Linked into `zlib` |
| `expat` | 2.7.4 | Linked into `pyexpat` |
<!-- END AUTO: framework-libs -->

## Python wheels (auto-generated)

> **A snapshot of `.venv-sidecar`** — the venv `desktop/scripts/build-sidecar.sh`
> builds the bundle from — at the last regeneration; `git log` on this file
> dates it (deliberately no date here: a date outside the generated block
> rotted for four months once). It is not the dev venv, which resolves
> separately and may carry different versions. `build-all.sh` step 2b refuses
> a release whose sidecar venv disagrees with this table. The same applies to
> the framework-libs table above.

The block between the markers below is regenerated by
`scripts/generate-third-party-binaries.py`, which runs `pip-licenses`
against the **sidecar venv** (`--python`, default `.venv-sidecar/bin/python`)
and subtracts the packages the PyInstaller spec `excludes` plus a
never-shipped list. It does **not** open the bundle's `_internal/`: this
table follows what PyInstaller was given, not what it wrote, which is a
slight over-count of the code that ships. In the other direction, a
`*.dist-info` can sit in `_internal/` for a package whose code is excluded
(metadata only), so an SCA scanner reading dist-info may name a package this
table does not. Don't hand-edit between the markers — re-run the script and
commit the result.

If you've changed dependencies in `pyproject.toml`, run:

```bash
.venv/bin/pip install -e '.[dev,serve,apple,release]'
desktop/scripts/build-sidecar.sh   # rebuild the bundle
.venv/bin/python scripts/generate-third-party-binaries.py
```

CI can call `scripts/generate-third-party-binaries.py --check` to fail
the build if this file is stale relative to the bundle. `desktop/scripts/build-all.sh`
runs the check automatically after `build-sidecar.sh`. The check is meant
to run on the canonical Mac sidecar build runner; per-platform venv
differences (mlx, av, torch) may flag drift on other machines that isn't
real drift.

**Caveat (over-inclusion).** The auto-generated table errs on the side of
listing every package in the build venv that isn't explicitly excluded by
the PyInstaller spec — even transitive dependencies of excluded packages
(e.g. some spaCy transitives) that PyInstaller's modulegraph would actually
strip from the bundle. Over-listing is the safer error direction for
procurement; under-listing would be a compliance risk.

<!-- BEGIN AUTO: python-wheels -->
| Package | Version | Licence | URL |
|---|---|---|---|
| `alembic` | 1.20.1 | MIT | <https://alembic.sqlalchemy.org> |
| `annotated-doc` | 0.0.7 | MIT | <https://github.com/fastapi/annotated-doc> |
| `annotated-types` | 0.8.0 | MIT | <https://github.com/annotated-types/annotated-types> |
| `anthropic` | 1.17.0 | MIT License | <https://github.com/anthropics/anthropic-sdk-python> |
| `anyio` | 4.16.0 | MIT | <https://anyio.readthedocs.io/en/stable/versionhistory.html> |
| `attrs` | 26.1.0 | MIT | <https://www.attrs.org/en/stable/changelog.html> |
| `av` | 18.1.1 | BSD-3-Clause | <https://pyav.basswood.io> |
| `blis` | 1.3.4 | BSD License | <https://github.com/explosion/cython-blis> |
| `budoux` | 0.10.4 | Apache-2.0 | — |
| `catalogue` | 2.0.10 | MIT License | <https://github.com/explosion/catalogue> |
| `certifi` | 2026.11.20 | Mozilla Public License 2.0 (MPL 2.0) | <https://github.com/certifi/python-certifi> |
| `cffi` | 2.1.1 | MIT-0 | <https://cffi.readthedocs.io/en/latest/whatsnew.html> |
| `charset-normalizer` | 3.5.3 | MIT | <https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md> |
| `click` | 8.5.1 | BSD-3-Clause | <https://github.com/pallets/click/> |
| `cloudpathlib` | 0.26.0 | MIT License | <https://github.com/drivendataorg/cloudpathlib> |
| `confection` | 1.3.4 | MIT License | <https://github.com/explosion/confection> |
| `cryptography` | 50.0.2 | Apache-2.0 OR BSD-3-Clause | <https://github.com/pyca/cryptography> |
| `cymem` | 2.0.16 | MIT License | <https://github.com/explosion/cymem> |
| `distro` | 1.9.0 | Apache Software License | <https://github.com/python-distro/distro> |
| `docstring_parser` | 0.18.0 | MIT License | <https://github.com/rr-/docstring_parser> |
| `et_xmlfile` | 2.0.0 | MIT License | <https://foss.heptapod.net/openpyxl/et_xmlfile> |
| `fastapi` | 0.165.0 | MIT | <https://github.com/fastapi/fastapi> |
| `filelock` | 4.3.1 | MIT | <https://github.com/tox-dev/filelock> |
| `flatbuffers` | 25.12.19 | Apache Software License | <https://google.github.io/flatbuffers/> |
| `fsspec` | 2026.9.0 | BSD-3-Clause | <https://github.com/fsspec/filesystem_spec> |
| `google-auth` | 2.63.1 | Apache Software License | <https://github.com/googleapis/google-cloud-python/tree/main/packages/google-auth> |
| `google-genai` | 3.6.1 | Apache-2.0 | <https://github.com/googleapis/python-genai> |
| `greenlet` | 3.5.6 | MIT AND PSF-2.0 | <https://greenlet.readthedocs.io> |
| `h11` | 0.16.0 | MIT License | <https://github.com/python-hyper/h11> |
| `hf-xet` | 1.8.0 | Apache-2.0 | <https://github.com/huggingface/xet-core> |
| `httpcore` | 1.0.9 | BSD-3-Clause | <https://www.encode.io/httpcore/> |
| `httpcore2` | 2.16.2 | BSD-3-Clause | <https://github.com/pydantic/httpx2> |
| `httptools` | 0.9.0 | MIT | <https://github.com/MagicStack/httptools> |
| `httpx` | 0.28.1 | BSD License | <https://github.com/encode/httpx> |
| `httpx2` | 2.16.2 | BSD-3-Clause | <https://github.com/pydantic/httpx2> |
| `huggingface_hub` | 1.33.0 | Apache Software License | <https://github.com/huggingface/huggingface_hub> |
| `idna` | 3.20 | BSD-3-Clause | <https://github.com/kjd/idna> |
| `inflect` | 7.6.0 | MIT | <https://github.com/jaraco/inflect> |
| `jaraco.functools` | 4.6.0 | MIT | <https://github.com/jaraco/jaraco.functools> |
| `Jinja2` | 3.1.6 | BSD License | <https://github.com/pallets/jinja/> |
| `jiter` | 0.19.0 | MIT | <https://github.com/pydantic/jiter/> |
| `jsonschema` | 4.26.0 | MIT | <https://github.com/python-jsonschema/jsonschema> |
| `jsonschema-specifications` | 2025.9.1 | MIT | <https://github.com/python-jsonschema/jsonschema-specifications> |
| `kaldi_native_fbank` | 1.23.3 | Apache-2.0 | <https://github.com/csukuangfj/kaldi-native-fbank> |
| `llvmlite` | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception | <http://llvmlite.readthedocs.io> |
| `lxml` | 6.1.3 | BSD-3-Clause | <https://lxml.de/> |
| `Mako` | 1.4.3 | MIT | <https://www.makotemplates.org/> |
| `markdown-it-py` | 4.3.0 | MIT License | <https://github.com/executablebooks/markdown-it-py> |
| `MarkupSafe` | 3.0.4 | BSD-3-Clause | <https://github.com/pallets/markupsafe/> |
| `mcp` | 2.3.0 | MIT License | <https://modelcontextprotocol.io> |
| `mcp-types` | 2.3.0 | MIT License | <https://modelcontextprotocol.io> |
| `mdurl` | 0.1.2 | MIT License | <https://github.com/executablebooks/mdurl> |
| `mlx` | 0.32.4 | MIT | <https://github.com/ml-explore/mlx> |
| `mlx-metal` | 0.32.4 | MIT | <https://github.com/ml-explore/mlx> |
| `mlx-whisper` | 0.4.3 | MIT | <https://github.com/ml-explore/mlx-examples> |
| `more-itertools` | 11.2.1 | MIT | <https://github.com/more-itertools/more-itertools> |
| `mpmath` | 1.3.0 | BSD License | <http://mpmath.org/> |
| `murmurhash` | 1.0.16 | MIT License | <https://github.com/explosion/murmurhash> |
| `networkx` | 3.7 | BSD-3-Clause | <https://networkx.org/> |
| `numba` | 0.68.1 | BSD License | <https://numba.pydata.org> |
| `numpy` | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | <https://numpy.org> |
| `onnxruntime` | 1.32.0 | MIT License | <https://onnxruntime.ai> |
| `openai` | 3.59.0 | Apache-2.0 | <https://github.com/openai/openai-python> |
| `openpyxl` | 3.1.5 | MIT License | <https://openpyxl.readthedocs.io> |
| `opentelemetry-api` | 1.45.2 | Apache-2.0 | <https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api> |
| `packaging` | 26.4 | Apache-2.0 OR BSD-2-Clause | <https://github.com/pypa/packaging> |
| `phonenumbers` | 9.0.44 | Apache-2.0 | <https://github.com/daviddrysdale/python-phonenumbers> |
| `preshed` | 3.0.13 | MIT License | <https://github.com/explosion/preshed> |
| `protobuf` | 7.36.2 | 3-Clause BSD License | <https://developers.google.com/protocol-buffers/> |
| `pyasn1` | 0.6.5 | BSD-2-Clause | <https://github.com/pyasn1/pyasn1> |
| `pyasn1_modules` | 0.4.2 | BSD License | <https://github.com/pyasn1/pyasn1-modules> |
| `pycparser` | 3.12 | BSD-3-Clause | <https://github.com/eliben/pycparser> |
| `pydantic` | 2.14.4 | MIT | <https://github.com/pydantic/pydantic> |
| `pydantic-settings` | 2.16.3 | MIT | <https://github.com/pydantic/pydantic-settings> |
| `pydantic_core` | 2.50.5 | MIT | <https://github.com/pydantic> |
| `Pygments` | 2.21.0 | BSD-2-Clause | <https://pygments.org> |
| `PyJWT` | 2.15.1 | MIT | <https://github.com/jpadilla/pyjwt> |
| `pyobjc-core` | 13.1 | MIT | <https://github.com/ronaldoussoren/pyobjc> |
| `pyobjc-framework-Cocoa` | 13.1 | MIT | <https://github.com/ronaldoussoren/pyobjc> |
| `pyobjc-framework-CoreML` | 13.1 | MIT | <https://github.com/ronaldoussoren/pyobjc> |
| `pyobjc-framework-Quartz` | 13.1 | MIT | <https://github.com/ronaldoussoren/pyobjc> |
| `pyobjc-framework-Vision` | 13.1 | MIT | <https://github.com/ronaldoussoren/pyobjc> |
| `python-docx` | 1.2.0 | MIT License | <https://github.com/python-openxml/python-docx> |
| `python-dotenv` | 1.2.4 | BSD-3-Clause | <https://github.com/theskumar/python-dotenv> |
| `python-multipart` | 0.0.34 | Apache-2.0 | <https://github.com/Kludex/python-multipart> |
| `PyYAML` | 6.0.4 | MIT License | <https://pyyaml.org/> |
| `referencing` | 0.37.0 | MIT | <https://github.com/python-jsonschema/referencing> |
| `regex` | 2026.11.23 | Apache-2.0 AND CNRI-Python | <https://github.com/mrabarnett/mrab-regex> |
| `requests` | 2.34.2 | Apache Software License | <https://github.com/psf/requests> |
| `requests-file` | 3.0.1 | Apache Software License | <https://codeberg.org/dashea/requests-file> |
| `rich` | 15.0.0 | MIT License | <https://github.com/Textualize/rich> |
| `rpds-py` | 2026.9.1 | MIT | <https://github.com/crate-py/rpds> |
| `scipy` | 1.18.1 | BSD License | <https://scipy.org/> |
| `shellingham` | 1.5.4 | ISC License (ISCL) | <https://github.com/sarugaku/shellingham> |
| `smart_open` | 10.0.0 | MIT | <https://github.com/piskvorky/smart_open> |
| `sniffio` | 1.3.1 | Apache Software License; MIT License | <https://github.com/python-trio/sniffio> |
| `spacy-legacy` | 3.0.12 | MIT License | <https://spacy.io> |
| `spacy-loggers` | 1.0.5 | MIT | <https://github.com/explosion/spacy-loggers> |
| `sqladmin` | 0.32.0 | BSD-3-Clause | <https://github.com/smithyhq/sqladmin> |
| `SQLAlchemy` | 2.1.9 | MIT | <https://www.sqlalchemy.org> |
| `srsly` | 2.5.6 | MIT License | <https://github.com/explosion/srsly> |
| `sse-starlette` | 3.7.1 | BSD-3-Clause | <https://github.com/sysid/sse-starlette> |
| `starlette` | 1.10.0 | BSD-3-Clause | <https://github.com/Kludex/starlette> |
| `sympy` | 1.14.0 | BSD License | <https://sympy.org> |
| `tenacity` | 9.1.4 | Apache Software License | <https://github.com/jd/tenacity> |
| `thinc` | 8.3.14 | MIT License | <https://github.com/explosion/thinc> |
| `tiktoken` | 0.14.0 | MIT | <https://github.com/openai/tiktoken> |
| `tldextract` | 5.4.0 | BSD-3-Clause | <https://github.com/john-kurkowski/tldextract> |
| `tokenizers` | 0.23.3 | Apache Software License | <https://github.com/huggingface/tokenizers> |
| `tqdm` | 4.70.1 | MPL-2.0 AND MIT | <https://tqdm.github.io> |
| `truststore` | 0.10.5 | MIT | <https://github.com/sethmlarson/truststore> |
| `typeguard` | 4.6.1 | MIT | <https://typeguard.readthedocs.io/en/latest/> |
| `typer` | 0.29.2 | MIT | <https://github.com/fastapi/typer> |
| `typing_extensions` | 4.16.0 | PSF-2.0 | <https://github.com/python/typing_extensions> |
| `urllib3` | 2.8.0 | MIT | <https://github.com/urllib3/urllib3/blob/main/CHANGES.rst> |
| `uvicorn` | 0.54.0 | BSD-3-Clause | <https://uvicorn.dev/> |
| `uvloop` | 0.23.0 | Apache Software License; MIT License | — |
| `wasabi` | 1.1.3 | MIT | <https://github.com/explosion/wasabi> |
| `watchfiles` | 1.3.0 | MIT License | <https://github.com/samuelcolvin/watchfiles> |
| `weasel` | 1.0.1 | MIT License | <https://github.com/explosion/weasel/> |
| `websockets` | 16.1.1 | BSD-3-Clause | <https://github.com/python-websockets/websockets> |
| `webvtt-py` | 0.8.0 | MIT | <https://github.com/glut23/webvtt-py> |
| `wrapt` | 2.5.2 | BSD-2-Clause | <https://github.com/GrahamDumpleton/wrapt> |
| `WTForms` | 3.2.2 | BSD License | <https://wtforms.readthedocs.io> |
<!-- END AUTO: python-wheels -->

## First-run downloads

These are not bundled in the `.app`; they download to
`~/Library/Application Support/Bristlenose/models/` on first
transcription. Verification is delegated to the upstream library's hash
mechanism, not re-implemented here.

| Asset | Origin | Verification | Default |
|---|---|---|---|
| Voice model (TitaNet-small, `nemo_en_titanet_small.onnx`, 40 MB) | https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/ (redirects to release-assets.githubusercontent.com) | SHA-256 pinned in `bristlenose/stages/s05b_voice.py` (`ad4a1802…789e`), checked on download and at the start of each run; lands in the app container's `Library/Caches/bristlenose/models/` (purgeable, not backed up), not Application Support | Apache-2.0 (NVIDIA NeMo) |
| Whisper model | Mac App Store app on macOS 26 or later: Apple's Background Assets hosting (the app's asset pack, downloaded by macOS). Otherwise, and as the fallback: https://huggingface.co/mlx-community/whisper-* | `large-v3-turbo` (MLX): revision, file sizes and SHA-256 pinned in `bristlenose/whisper_pins.py` and in the app's `WhisperPackManifest` (kept equal by `tests/test_whisper_pins.py`), checked for the pack and the Hugging Face download. Other models: HuggingFace Hub built-in SHA verification (`hf_hub_download` checks file hashes against the repo manifest) | `large-v3-turbo` (override via `BRISTLENOSE_WHISPER_MODEL`) |

If alpha bundles a model directly into the `.app` per
`desktop/CLAUDE.md`'s "alpha bundles the `small.en` model directly"
note, add a row above with the bundled model's SHA256 captured at
build time.

## Vulnerability-monitoring cadence

No automated gate forces re-audit; the cadence below is the gate.

- **GitHub Dependabot** — configured at [`.github/dependabot.yml`](.github/dependabot.yml)
  (pip + npm/frontend + npm/e2e + npm/desktop, weekly, grouped by
  minor-and-patch). PRs land for security advisories without human
  prompting; quarterly review covers anything Dependabot can't auto-PR
  (e.g. major-version bumps with breaking changes).
- **Quarterly manual review** — `pip list --outdated` against the
  pinned venv, diff vs the previous quarter's snapshot, regenerate the
  Python wheels table above. Tracked in `docs/private/100days.md`
  maintenance section.
- **FFmpeg-specific** — subscribe to the [FFmpeg security mailing
  list](https://ffmpeg.org/security.html). Mail traffic is low; one or
  two advisories per quarter at most.
- **`Python.framework`** — version is whatever `pyinstaller` bundles.
  Bumps land when `pyinstaller` upgrades, which happens during the
  quarterly review.
- **Off-cycle** — when a high-profile CVE drops (Log4Shell-class
  events), check this file's latest SHAs against the advisory. The
  hand-curated rows above + the auto-generated rows below cover every
  attack surface inside the `.pkg`.

## Deferred decisions (honest disclosure)

These are tracked here so a procurement reviewer asking "do you do X?"
gets a yes/no with reasoning rather than silence.

- **Wheel hash pinning (`pip install --require-hashes`).** Not
  enforced. A `requirements-locked.txt` with hashes for every wheel
  would defend against PyPI account compromise; the trade-off is
  re-locking friction on every dependency upgrade. Deferred until the
  next dependency-management overhaul (likely a `uv` migration).
  Dependabot covers the more common compromised-transitive-dep case.
- **CycloneDX SBOM emission.** Not generated. The Markdown table above
  covers the same ground in a human-readable form; CycloneDX JSON is
  easier to grep but harder to read. Will add if a procurement
  reviewer specifically asks; trivial to drive from the same
  `pip-licenses --format=json` output the auto section uses.

## See also

- `desktop/scripts/build-ffmpeg-lgpl.sh` — the LGPL FFmpeg build: pinned-SHA source tarballs, the configure line, and the gates on what it produces.
- `desktop/scripts/fetch-ffmpeg.sh` — installs that build into `Resources/` (from `desktop/build/ffmpeg-cache/` after the first build); `--check` tells `ensure-sidecar.sh` whether the installed copy is this recipe's.
- `desktop/scripts/check-ffmpeg-licence.sh` — the licence gate on the bundled ffmpeg/ffprobe, run by `build-all.sh` on the exported app and by `fetch-ffmpeg.sh --check`.
- `desktop/scripts/sign-sidecar.sh` — emits per-binary
  `desktop/build/sign-manifest.json` with SHA256 of every signed
  Mach-O.
- `desktop/scripts/check-release-binary.sh` — pre-archive scan that
  rejects Debug-only literals + `get-task-allow=TRUE` entitlements.
- `desktop/scripts/check-bundle-manifest.sh` — bundle-data coverage
  gate against the PyInstaller spec.
- `SECURITY.md` "Code signing and runtime hardening" — links here.
- `docs/design-desktop-python-runtime.md` §"Supply-chain provenance
  (C5)" — explains the cadence in narrative form.
