"""Voice pass: one speaker embedding per Whisper segment, two clusters.

The research session's best variant (`docs/design-voice-diarization.md`,
"A2: embed each Whisper segment, TitaNet, 2-means"), cleaned up to take a
`session_segments`-shaped JSON with word timings. Runs in a scratch venv,
not the project's: `python3.12 -m venv v && v/bin/pip install sherpa-onnx
soundfile numpy`. Models from the k2-fsa `speaker-recongition-models` release
(sic). Audio is participant data: keep the 16 kHz mono WAV in a scratchpad.

    v/bin/python voice.py <wav> <segments.json> <sid> <embedding.onnx> <out.json>

Writes, per segment: cluster (0/1, or null when the span is too short to
embed), the margin between the two centroid similarities, and the span used.
Role mapping is NOT done here — eval_voice.py does it, the way the product
would (the LLM role pass), and reports the oracle mapping beside it.
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import sherpa_onnx
import soundfile as sf

MIN_FIT_S = 2.0     # segments used to fit the clusters
MIN_ASSIGN_S = 0.6  # shorter than this: no voice verdict


def embed(ext, audio, sr, a, b):
    s = ext.create_stream()
    s.accept_waveform(sr, audio[int(a * sr):int(b * sr)])
    s.input_finished()
    v = np.array(ext.compute(s))
    return v / (np.linalg.norm(v) + 1e-9)


def kmeans2(x, iters=50, restarts=20, seed=0):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(restarts):
        c = x[rng.choice(len(x), 2, replace=False)]
        for _ in range(iters):
            lab = np.argmax(x @ c.T, axis=1)
            new = np.stack([x[lab == k].mean(0) if (lab == k).any() else c[k] for k in (0, 1)])
            new /= np.linalg.norm(new, axis=1, keepdims=True)
            if np.allclose(new, c):
                break
            c = new
        score = (x @ c.T).max(1).sum()
        if best is None or score > best[0]:
            best = (score, c)
    return best[1]


def main() -> None:
    wav, seg_path, sid, model, out = sys.argv[1:6]
    ext = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=4))
    audio, sr = sf.read(wav, dtype="float32", always_2d=True)
    audio = audio[:, 0]
    segs = json.load(open(seg_path))[sid]
    t0 = time.perf_counter()
    spans = []
    for s in segs:
        w = s.get("words") or []
        spans.append((w[0]["start_time"], w[-1]["end_time"]) if w else (s["start_time"], s["end_time"]))
    emb = [embed(ext, audio, sr, a, b) if b - a >= MIN_ASSIGN_S else None for a, b in spans]
    fit = np.stack([e for e, (a, b) in zip(emb, spans) if e is not None and b - a >= MIN_FIT_S])
    c = kmeans2(fit)
    elapsed = time.perf_counter() - t0
    rows = []
    for e, (a, b) in zip(emb, spans):
        if e is None:
            rows.append({"cluster": None, "margin": 0.0, "span": [a, b]})
            continue
        sims = c @ e
        rows.append({"cluster": int(np.argmax(sims)), "margin": round(float(abs(sims[0] - sims[1])), 3),
                     "span": [round(a, 2), round(b, 2)]})
    summary = {"model": model.rsplit("/", 1)[-1], "segments": len(segs), "fit_segments": len(fit),
               "no_verdict": sum(r["cluster"] is None for r in rows),
               "centroid_cos": round(float(c[0] @ c[1]), 3),
               "elapsed_s": round(elapsed, 1), "audio_s": round(len(audio) / sr, 1)}
    json.dump({"summary": summary, "rows": rows}, open(out, "w"), indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
