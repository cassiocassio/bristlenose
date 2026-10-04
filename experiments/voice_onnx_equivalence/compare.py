"""Is the voice pass's direct onnxruntime path the same as sherpa-onnx?

The pass ran TitaNet-small through sherpa-onnx until 4 Oct 2026 and now runs
it through onnxruntime + kaldi-native-fbank (`s05b_voice._TitaNet`), because
sherpa's published wheels statically link espeak-ng, GPL-3.0-or-later
(docs/design-voice-diarization.md § Licence). Re-run this after a change to the
front end, the model, onnxruntime or kaldi-native-fbank.

sherpa-onnx is deliberately not a project dependency any more, so it comes from
a side venv on the same Python minor:

    python3.12 -m venv /tmp/sv && /tmp/sv/bin/pip install sherpa-onnx==1.13.8
    .venv/bin/python experiments/voice_onnx_equivalence/compare.py \\
        /tmp/sv/lib/python3.12/site-packages <recording> [<recording> ...]

The model must already be cached (`bristlenose doctor --fetch`). For each
recording: the worst cosine between the two embeddings, and whether the shipped
`cluster_voices` gives the same verdict on every 3 s window.

4 Oct 2026, FOSSDA 01-bruce-perens.mp4 (public, 40 min): 794 windows, worst
cosine 1.000000, 794 of 794 verdicts agree, centroid cosine 0.1302 both ways.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

from bristlenose.stages import s05b_voice as v

WINDOW_S = 3.0


def sherpa_embedder(model: Path, audio: np.ndarray):
    import sherpa_onnx

    ex = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model), num_threads=4))

    def embed(lo: float, hi: float):
        x = audio[int(lo * v.SAMPLE_RATE):int(hi * v.SAMPLE_RATE)]
        if not len(x):
            return None
        s = ex.create_stream()
        s.accept_waveform(v.SAMPLE_RATE, x)
        s.input_finished()
        return np.array(ex.compute(s)) if ex.is_ready(s) else None

    return embed


def main() -> int:
    sys.path.append(sys.argv[1])
    model, reason = v.resolve_voice_model(allow_fetch=False)
    if model is None:
        print(f"no model: {reason}")
        return 2
    worst_overall = 1.0
    for rec in sys.argv[2:]:
        audio = v.load_audio_16k(Path(rec))
        dur = len(audio) / v.SAMPLE_RATE
        spans = [(t, min(t + WINDOW_S, dur)) for t in np.arange(0, dur - 1, WINDOW_S)]
        ref, new = sherpa_embedder(model, audio), v._titanet_embedder(model, audio)
        worst = 1.0
        for lo, hi in spans:
            a, b = ref(lo, hi), new(lo, hi)
            if a is None or b is None:
                assert a is None and b is None, (rec, lo)
                continue
            worst = min(worst, float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))))
        t0 = time.perf_counter(); ca = v.cluster_voices(spans, ref); ta = time.perf_counter() - t0
        t0 = time.perf_counter(); cb = v.cluster_voices(spans, new); tb = time.perf_counter() - t0
        assert ca is not None and cb is not None
        same = sum(x == y for x, y in zip(ca.clusters, cb.clusters))
        swapped = sum((x is None and y is None) or (x is not None and y is not None and x == 1 - y)
                      for x, y in zip(ca.clusters, cb.clusters))
        print(f"{Path(rec).name}: {len(spans)} windows; worst cosine {worst:.6f}; "
              f"verdicts agree {max(same, swapped)}/{len(spans)}; centroid cosine "
              f"sherpa {ca.centroid_cos} direct {cb.centroid_cos}; time {ta:.1f}s vs {tb:.1f}s")
        worst_overall = min(worst_overall, worst)
    return 0 if worst_overall > 0.9999 else 1


if __name__ == "__main__":
    sys.exit(main())
