"""Stage 5b voice pass: tell two speakers apart by how they sound.

The text splitter (`split_single_speaker_llm`) guesses speaker changes from
the words alone. This pass embeds each Whisper segment's audio with a speaker
model (TitaNet-small, run through onnxruntime), clusters the embeddings into two
voices, and relabels every segment the model could judge. Segments too short
to embed keep the text splitter's label. Measured against a Teams transcript's
named turns, that combination got 12 of 286 segments wrong where the text
splitter alone got 22 (`docs/design-voice-diarization.md` § Measured against
platform ground truth).

Optional by construction. It runs only when the ``voice`` extra is installed,
the model is on disk or can be fetched, the setting is on, and the text
splitter found exactly two speakers. Any other case leaves the text labels as
they were and says why in the per-session record the pipeline writes to the
speaker cache. Nothing leaves the machine: the audio and the model are local,
and the pass makes no LLM call.

Kept out of ``s05b_identify_speakers`` so that module stays importable without
numpy, and so the decisions (``cluster_voices``, ``merge_voice_and_text``) are
testable without audio or a model.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import os
import subprocess
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bristlenose.models import TranscriptSegment

logger = logging.getLogger(__name__)

#: Bump when the algorithm, its thresholds or the model change. Recorded per
#: session in the speaker cache, so a reader can tell which voice pass (if any)
#: produced the labels it is looking at.
VOICE_VERSION = "1"

#: TitaNet-small, NVIDIA NeMo, exported to ONNX by k2-fsa. Licence: NVIDIA's
#: model card (catalog.ngc.nvidia.com/orgs/nvidia/teams/nemo/models/titanet_small)
#: says it is "covered by the license of the NeMo Toolkit", which is Apache-2.0
#: (github.com/NVIDIA/NeMo/blob/main/LICENSE; both read 4 Oct 2026). The
#: release tag's spelling is upstream's.
VOICE_MODEL_NAME = "nemo_en_titanet_small.onnx"
VOICE_MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/nemo_en_titanet_small.onnx"
)
VOICE_MODEL_SHA256 = "ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e"
VOICE_MODEL_BYTES = 40_257_283

#: Overrides the cached model with a file on disk (a bundled copy, say).
VOICE_MODEL_ENV = "BRISTLENOSE_VOICE_MODEL"

SAMPLE_RATE = 16_000
#: Segments at least this long are used to find the two voices.
MIN_FIT_S = 2.0
#: Shorter than this, a segment gets no voice verdict and keeps its text label.
MIN_ASSIGN_S = 0.6
#: Fewer fitting segments than this, and two clusters mean nothing.
MIN_FIT_SEGMENTS = 8
#: Cosine between the two voice centroids above which the model has found one
#: voice, not two. Measured: 0.26–0.62 on real two-person sessions with
#: TitaNet; 0.87–0.95 where a weaker model collapsed them.
MAX_CENTROID_COS = 0.75
#: Voice may overrule the text splitter on at most this share of the segments
#: it judges. Measured on a real two-person session: 6–8 %. Far above that, the
#: two methods describe different splits — the likeliest cause being one
#: person's voice split in two when the other's turns were too short to fit —
#: and voice should not win silently. (A minimum share per voice was tried and
#: dropped: it would also decline a moderator who genuinely says little.)
MAX_RELABEL_SHARE = 0.35


@dataclass
class VoiceClusters:
    """Per-segment voice verdicts from one session."""

    clusters: list[int | None]
    margins: list[float]
    centroid_cos: float
    fit_segments: int


@dataclass
class VoiceRecord:
    """What the voice pass did to one session, written to the speaker cache."""

    method: str = "text"  # "voice+text" when voice relabelled, else "text"
    reason: str = ""  # why voice did not apply, empty when it did
    voice_version: str = VOICE_VERSION
    voice_model: str = VOICE_MODEL_NAME
    segments: int = 0
    voice_verdicts: int = 0
    relabelled: int = 0
    centroid_cos: float | None = None
    elapsed_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "method": self.method,
            "reason": self.reason,
            "voice_version": self.voice_version,
            "voice_model": self.voice_model,
            "segments": self.segments,
            "voice_verdicts": self.voice_verdicts,
            "relabelled": self.relabelled,
            "centroid_cos": self.centroid_cos,
            "elapsed_ms": self.elapsed_ms,
        }
        d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# Availability and the model file
# ---------------------------------------------------------------------------


def voice_runtime_available() -> bool:
    """True when the ``voice`` runtime is installed: onnxruntime (already a
    core dependency on the CLI, through faster-whisper) and kaldi-native-fbank,
    which the ``voice`` extra adds."""
    import importlib.util

    return all(importlib.util.find_spec(m) is not None
               for m in ("onnxruntime", "kaldi_native_fbank"))


def voice_model_cache_path() -> Path:
    """Where a fetched model lives.

    In the Mac app: ``~/Library/Caches`` — the container's, since HOME is the
    container under the sandbox — which Time Machine skips and macOS may
    purge; a purged model is simply fetched again. On the CLI: the snap's
    common area, ``$XDG_CACHE_HOME``, or ``~/.cache``.
    """
    import sys

    from bristlenose.config import hosted_by_desktop

    snap_common = os.environ.get("SNAP_USER_COMMON")
    if sys.platform == "darwin" and hosted_by_desktop():
        base = Path.home() / "Library" / "Caches" / "bristlenose" / "models"
    elif snap_common:
        base = Path(snap_common) / "models"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".cache") / "bristlenose" / "models"
    return base / VOICE_MODEL_NAME


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cached_voice_model() -> Path | None:
    """The model already on disk (override, or a cache file of the right size).

    A cheap look, for doctor: size only, and never raises — an unreadable
    cache directory reads as "not cached". ``resolve_voice_model`` verifies
    the hash before a run uses the file.
    """
    try:
        override = os.environ.get(VOICE_MODEL_ENV)
        if override:
            p = Path(override)
            return p if p.is_file() else None
        p = voice_model_cache_path()
        if p.is_file() and p.stat().st_size == VOICE_MODEL_BYTES:
            return p
    except OSError:
        pass
    return None


def fetch_voice_model(timeout: float = 30.0, deadline: float = 600.0) -> Path:
    """Download the model to the cache, verify its hash, and return its path.

    Streams into a uniquely named temporary file beside the destination,
    hashing as it writes; renames into place only when the size and hash
    match, so an interrupted, oversized, redirected or tampered download is
    never where ``cached_voice_model`` would accept it, and two runs fetching
    at once cannot truncate each other's file. ``timeout`` is per socket read;
    ``deadline`` bounds the whole download. Raises on any failure.
    """
    import tempfile

    dest = voice_model_cache_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A run killed mid-download leaves its uniquely named part file behind;
    # clear any older than an hour so they cannot pile up at 40 MB each.
    for stale in dest.parent.glob(dest.name + ".*.part"):
        try:
            if time.time() - stale.stat().st_mtime > 3600:
                stale.unlink()
        except OSError:
            pass
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=dest.name + ".", suffix=".part")
    tmp = Path(tmp_name)
    try:
        h = hashlib.sha256()
        size = 0
        started = time.monotonic()
        with urllib.request.urlopen(VOICE_MODEL_URL, timeout=timeout) as resp, os.fdopen(fd, "wb") as out:
            if not resp.geturl().startswith("https://"):
                raise ValueError(f"voice model download left https: {resp.geturl()}")
            while chunk := resp.read(1 << 20):
                size += len(chunk)
                if size > VOICE_MODEL_BYTES:
                    raise ValueError("voice model download is larger than expected")
                if time.monotonic() - started > deadline:
                    raise TimeoutError(f"voice model download took over {deadline:.0f} s")
                h.update(chunk)
                out.write(chunk)
        if size != VOICE_MODEL_BYTES or h.hexdigest() != VOICE_MODEL_SHA256:
            raise ValueError(
                f"voice model hash mismatch: expected {VOICE_MODEL_SHA256[:12]}…, "
                f"got {h.hexdigest()[:12]}… ({size} bytes)"
            )
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    logger.info("voice model fetched to %s", dest)
    return dest


def resolve_voice_model(*, allow_fetch: bool) -> tuple[Path | None, str]:
    """The model path, fetching it if allowed. Returns ``(path, reason)``.

    ``reason`` is empty when a path is returned and says why otherwise, in the
    words the speaker-cache record and the log will use.
    """
    try:
        override = os.environ.get(VOICE_MODEL_ENV)
        if override:
            # Deliberately not hash-checked: an override is the operator's own
            # file (a bundled or mirrored copy), documented as unverified.
            if Path(override).is_file():
                return Path(override), ""
            return None, f"{VOICE_MODEL_ENV} names a file that does not exist"
        found = cached_voice_model()
        if found is not None:
            if _sha256(found) == VOICE_MODEL_SHA256:  # ~60 ms, once per run
                return found, ""
            logger.warning("cached voice model fails its hash check; fetching again")
        if not allow_fetch:
            return None, "voice model not downloaded (no-fetch)"
        return fetch_voice_model(), ""
    except Exception as exc:  # network, disk, hash — all mean "no voice this run"
        logger.debug("voice model unavailable: %s", exc)
        return None, f"voice model could not be fetched: {exc}"


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


def load_audio_16k(path: Path) -> Any:
    """Decode any media file to 16 kHz mono float32 samples with ffmpeg.

    Video sessions already have a 16 kHz WAV from stage 2; audio sessions point
    at the researcher's original file, in whatever format it came. One decoder
    for both keeps the sample format identical.
    """
    import numpy as np

    from bristlenose.utils.bundled_binary import bundled_binary_path
    from bristlenose.utils.fs import ensure_materialised

    ensure_materialised(path)
    ffmpeg = bundled_binary_path("ffmpeg") or "ffmpeg"
    result = subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        capture_output=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg could not decode {path.name} (exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    if len(result.stdout) < 2:
        raise RuntimeError(f"ffmpeg decoded no audio from {path.name}")
    audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
    audio /= 32768.0
    return audio


# ---------------------------------------------------------------------------
# The decisions — pure, testable without audio or a model
# ---------------------------------------------------------------------------


def segment_spans(
    segments: list[TranscriptSegment], audio_seconds: float | None = None,
) -> list[tuple[float, float]]:
    """The audio span to embed for each segment: its words if it has them.

    Word timings are tighter than segment timings, which Whisper pads into the
    surrounding pause — and a pause can hold the other speaker's breath.
    Clamped to the audio, so a segment that runs past the end of a trimmed
    recording is judged on the audio that exists, or not at all.
    """
    spans = []
    for seg in segments:
        if seg.words:
            a, b = seg.words[0].start_time, seg.words[-1].end_time
        else:
            a, b = seg.start_time, seg.end_time
        a = max(0.0, a)
        if audio_seconds is not None:
            b = min(b, audio_seconds)
        spans.append((a, b))
    return spans


def _kmeans2(x: Any, iters: int = 50, restarts: int = 20, seed: int = 0) -> Any:
    """Spherical 2-means; deterministic for a given input."""
    import numpy as np

    rng = np.random.default_rng(seed)
    best = None
    for _ in range(restarts):
        c = x[rng.choice(len(x), 2, replace=False)]
        for _ in range(iters):
            lab = np.argmax(x @ c.T, axis=1)
            new = np.stack([x[lab == k].mean(0) if (lab == k).any() else c[k] for k in (0, 1)])
            new /= np.linalg.norm(new, axis=1, keepdims=True) + 1e-12
            if np.allclose(new, c):
                break
            c = new
        score = (x @ c.T).max(1).sum()
        if best is None or score > best[0]:
            best = (score, c)
    assert best is not None
    return best[1]


def cluster_voices(
    spans: list[tuple[float, float]],
    embed: Callable[[float, float], Any],
) -> VoiceClusters | None:
    """Embed each long-enough span and split the embeddings into two voices.

    ``embed(start, end)`` returns an embedding vector for that span, or None
    when it could not make one. An empty or non-finite vector also counts as
    no verdict — an embedder may return an empty one for an empty slice rather
    than raising, and an empty vector would otherwise cluster as a voice.
    Returns None when too few segments are long enough to find two voices.
    """
    import numpy as np

    vecs: list[Any] = []
    dim = None
    for a, b in spans:
        if b - a < MIN_ASSIGN_S:
            vecs.append(None)
            continue
        raw = embed(a, b)
        v = None if raw is None else np.asarray(raw, dtype=np.float64).ravel()
        norm = 0.0 if v is None or v.size == 0 else float(np.linalg.norm(v))
        if v is None or v.size == 0 or not np.isfinite(v).all() or norm == 0.0:
            vecs.append(None)
            continue
        if dim is None:
            dim = v.size
        if v.size != dim:
            vecs.append(None)
            continue
        vecs.append(v / norm)
    fit_rows = [v for v, (a, b) in zip(vecs, spans) if v is not None and b - a >= MIN_FIT_S]
    if len(fit_rows) < MIN_FIT_SEGMENTS:
        return None
    c = _kmeans2(np.stack(fit_rows))
    clusters: list[int | None] = []
    margins: list[float] = []
    for v in vecs:
        if v is None:
            clusters.append(None)
            margins.append(0.0)
            continue
        sims = c @ v
        clusters.append(int(np.argmax(sims)))
        margins.append(round(float(abs(sims[0] - sims[1])), 4))
    return VoiceClusters(clusters, margins, round(float(c[0] @ c[1]), 4), len(fit_rows))


def text_split_reason(segments: list[TranscriptSegment]) -> str:
    """Why the voice pass cannot refine this text split, or "" if it can.

    Checked before any audio is decoded: the pass maps two voices onto two
    text speakers, so anything else is a decline, and an expensive one if
    found only after embedding a whole recording.
    """
    from bristlenose.utils.text import count_noun

    n = len({seg.speaker_label for seg in segments if seg.speaker_label})
    if n == 2:
        return ""
    return f"text splitter found {count_noun(n, 'speaker')}; the voice pass separates two"


def merge_voice_and_text(
    segments: list[TranscriptSegment], vc: VoiceClusters,
) -> tuple[int, str]:
    """Relabel segments by voice, keeping the text splitter's speaker names.

    The two voice clusters are matched to the text splitter's two labels by
    whichever pairing agrees on more segments, so "Speaker A" stays the same
    person the text splitter meant. A segment with no voice verdict keeps its
    text label. Declines (and changes nothing) when the voices are not
    distinct, or when voice would overrule text on more than
    ``MAX_RELABEL_SHARE`` of the lines it judged — counted before anything is
    changed. Returns ``(relabelled, reason)``; a
    non-empty reason means nothing was changed.
    """
    labels = [seg.speaker_label for seg in segments]
    reason = text_split_reason(segments)
    if reason:
        return 0, reason
    # Written as "not <=" so a NaN cosine declines rather than passing.
    if not vc.centroid_cos <= MAX_CENTROID_COS:
        return 0, f"voices not distinct (centroid cosine {vc.centroid_cos:.2f})"
    verdicts = [c for c in vc.clusters if c is not None]
    a, b = sorted({lab for lab in labels if lab})
    agree = {(0, a): 0, (0, b): 0, (1, a): 0, (1, b): 0}
    for lab, cl in zip(labels, vc.clusters):
        if cl is not None and lab in (a, b):
            agree[(cl, lab)] += 1
    straight = agree[(0, a)] + agree[(1, b)]
    crossed = agree[(0, b)] + agree[(1, a)]
    mapping = {0: a, 1: b} if straight >= crossed else {0: b, 1: a}
    would_move = min(straight, crossed)
    if would_move > MAX_RELABEL_SHARE * len(verdicts):
        return 0, (f"voice and text disagree on {would_move} of {len(verdicts)} judged lines; "
                   "keeping the text split")
    relabelled = 0
    for seg, cl in zip(segments, vc.clusters):
        if cl is None:
            continue
        new = mapping[cl]
        if seg.speaker_label != new:
            seg.speaker_label = new
            relabelled += 1
    return relabelled, ""


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------


#: Window types kaldi-native-fbank accepts. Anything else makes it print an error
#: and exit the PROCESS (status 255) — no Python exception, so nothing upstream
#: could catch it — hence checked here first. Each was run on 1.22.3.
_KNF_WINDOWS = frozenset({"hann", "hanning", "hamming", "povey", "rectangular", "blackman", "sine"})


def fbank_options(
    *, feat_dim: int = 80, frame_length_ms: float = 25.0, frame_shift_ms: float = 10.0,
    window_type: str = "hann",
) -> Any:
    """kaldi-native-fbank options for a NeMo speaker model, as sherpa-onnx
    configures them (``speaker-embedding-extractor-nemo-impl.h``, ``features.cc``
    at v1.13.8). One builder, so ``doctor`` self-tests the options the pass uses.
    """
    import kaldi_native_fbank as knf

    if window_type not in _KNF_WINDOWS:
        raise ValueError(f"voice model asks for an unknown window: {window_type!r}")
    if not (0 < frame_shift_ms <= frame_length_ms <= 100) or not (1 <= feat_dim <= 512):
        raise ValueError(
            f"voice model asks for an implausible front end: {feat_dim} bins, "
            f"{frame_length_ms}/{frame_shift_ms} ms")
    o = knf.FbankOptions()
    o.frame_opts.dither = 0.0
    o.frame_opts.snip_edges = True
    o.frame_opts.samp_freq = SAMPLE_RATE
    o.frame_opts.frame_shift_ms = frame_shift_ms
    o.frame_opts.frame_length_ms = frame_length_ms
    o.frame_opts.remove_dc_offset = False
    o.frame_opts.preemph_coeff = 0.97
    o.frame_opts.window_type = window_type
    o.frame_opts.round_to_power_of_two = True
    o.mel_opts.num_bins = feat_dim
    o.mel_opts.low_freq = 0.0
    o.mel_opts.high_freq = -400.0
    o.mel_opts.is_librosa = True
    return o


class _TitaNet:
    """TitaNet-small through onnxruntime, with the NeMo front end sherpa-onnx
    uses (``speaker-embedding-extractor-nemo-impl.h`` at v1.13.8).

    Driven directly rather than through sherpa-onnx because sherpa's published
    wheels statically link espeak-ng (GPL-3.0-or-later) from their TTS code,
    which an App Store binary cannot carry (`docs/design-voice-diarization.md`
    § Licence). Measured equivalent on 4 Oct 2026: cosine 1.000000 to sherpa's
    embedding on every span, and the same verdict from ``cluster_voices`` on
    794 of 794 windows of a 40-minute interview
    (``experiments/voice_onnx_equivalence/``).

    The feature settings are read from the model's own metadata where it has
    them; the rest are sherpa's fixed choices for NeMo models.
    """

    def __init__(self, model_path: str, threads: int) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        # sherpa ran its session at ERROR; a WARNING from a future onnxruntime
        # would otherwise land on stderr in the middle of Rich's live display.
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(
            model_path, opts, providers=["CPUExecutionProvider"])
        meta = self.session.get_modelmeta().custom_metadata_map
        if int(meta.get("sample_rate", SAMPLE_RATE)) != SAMPLE_RATE:
            raise ValueError(f"voice model expects {meta['sample_rate']} Hz audio")
        if meta.get("feature_normalize_type", "") != "per_feature":
            raise ValueError("voice model is not a NeMo per-feature model")
        self.feat_dim = int(meta.get("feat_dim", 80))
        self.frame_length_ms = float(meta.get("window_size_ms", 25))
        self.frame_shift_ms = float(meta.get("window_stride_ms", 10))
        self.window_type = meta.get("window_type", "hann")
        # Validates the metadata now, at load, not inside the first session.
        self._options = fbank_options(
            feat_dim=self.feat_dim, frame_length_ms=self.frame_length_ms,
            frame_shift_ms=self.frame_shift_ms, window_type=self.window_type,
        )

    def features(self, samples: Any) -> Any:
        """Log-mel filterbank frames, ``(frames, feat_dim)``, or None when the
        slice is too short for one frame."""
        import kaldi_native_fbank as knf
        import numpy as np

        fbank = knf.OnlineFbank(self._options)
        fbank.accept_waveform(SAMPLE_RATE, np.asarray(samples, dtype=np.float32).tolist())
        fbank.input_finished()
        n = fbank.num_frames_ready
        if n == 0:
            return None
        return np.stack([np.asarray(fbank.get_frame(i), dtype=np.float32) for i in range(n)])

    def embed(self, samples: Any) -> Any:
        import numpy as np

        feats = self.features(samples)
        if feats is None:
            return None
        n = feats.shape[0]
        mean = feats.mean(axis=0)
        std = np.sqrt(((feats - mean) ** 2).mean(axis=0))
        feats = (feats - mean) / (std + 1e-5)
        # No padding. sherpa resizes its buffer to a multiple of 16 frames, but
        # the tensor it hands the model keeps the unpadded frame count, so the
        # padding never reaches the model; padding here scored 0.89 against it
        # on 0.7 s spans.
        (emb,) = self.session.run(
            ["embs"],
            {"audio_signal": feats.T[None, :, :].astype(np.float32),
             "length": np.array([n], dtype=np.int64)},
        )
        return emb[0]


@functools.lru_cache(maxsize=1)
def _model(model_path: str, mtime_ns: int) -> _TitaNet:
    """One loaded model per run, not per session (keyed on the file's mtime, so
    a re-fetched model in a long-lived serve process is reloaded). The pipeline
    runs the pass one session at a time (a semaphore of one), so it is never
    used by two threads at once; raise that semaphore and this needs a lock."""
    return _TitaNet(model_path, threads=min(4, os.cpu_count() or 1))


def load_voice_model(model_path: Path) -> str:
    """Load the model once, before any session, and say why if it will not load.

    The pipeline calls this right after ``resolve_voice_model``, so a model or
    runtime that cannot load is one visible warning rather than a quiet
    text-only fallback in every session. Returns "" when the model loaded.
    """
    try:
        _model(str(model_path), model_path.stat().st_mtime_ns)
    except Exception as exc:  # onnxruntime, metadata, kaldi-native-fbank options
        logger.debug("voice model will not load: %s", exc)
        return f"voice model will not load: {exc}"
    return ""


def _titanet_embedder(model_path: Path, audio: Any) -> Callable[[float, float], Any]:
    model = _model(str(model_path), model_path.stat().st_mtime_ns)

    def embed(start: float, end: float) -> Any:
        lo, hi = int(start * SAMPLE_RATE), int(end * SAMPLE_RATE)
        if hi <= lo:
            return None
        return model.embed(audio[lo:hi])

    return embed


def refine_speakers_by_voice(
    segments: list[TranscriptSegment],
    audio_path: Path | None,
    model_path: Path | None,
    *,
    unavailable_reason: str = "",
) -> VoiceRecord:
    """Run the voice pass on one session's text-split segments, in place.

    Never raises: any failure leaves the text labels untouched and is recorded
    as the reason. Blocking and CPU-bound — call it from a worker thread.
    """
    rec = VoiceRecord(segments=len(segments))
    t0 = time.perf_counter()
    try:
        text_reason = text_split_reason(segments)
        if unavailable_reason:
            rec.reason = unavailable_reason
        elif text_reason:
            rec.reason = text_reason
        elif audio_path is None:
            rec.reason = "no audio extracted for this session (it came with a transcript)"
        elif model_path is None:
            rec.reason = "voice model unavailable"
        else:
            audio = load_audio_16k(audio_path)
            spans = segment_spans(segments, audio_seconds=len(audio) / SAMPLE_RATE)
            vc = cluster_voices(spans, _titanet_embedder(model_path, audio))
            if vc is None:
                rec.reason = f"fewer than {MIN_FIT_SEGMENTS} segments long enough to compare voices"
            else:
                rec.voice_verdicts = sum(c is not None for c in vc.clusters)
                rec.centroid_cos = vc.centroid_cos
                rec.relabelled, rec.reason = merge_voice_and_text(segments, vc)
                if not rec.reason:
                    rec.method = "voice+text"
    except Exception as exc:
        rec.reason = f"voice pass failed: {exc}"
        logger.warning("voice pass failed, keeping the text labels: %s", exc)
    rec.elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return rec
