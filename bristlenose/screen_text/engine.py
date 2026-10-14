"""The OCR seam: one protocol, an engine per platform, a fake for tests.

Everything above this module is engine-agnostic. A frame is raw BGRA bytes with its size; a
line is text, a confidence and a box in 0–1 page coordinates, top-left origin.

The Vision engine is macOS-only and needs ``pyobjc-framework-Vision`` and ``-Quartz`` (the
``apple`` extra, which the desktop sidecar ships). Two rules from the spikes are load-bearing:

- **Copy the frame into ``NSData``** (``CGDataProviderCreateWithCFData``), never wrap the Python
  buffer with ``CGDataProviderCreateWithData``: the latter leaked a whole frame per call.
- **Read inside ``objc.autorelease_pool()``**, or memory grows a frame per call in a long loop.

In the sandboxed sidecar Vision also needs ``CFFIXED_USER_HOME`` set to the container, or its model
cache write is refused and every request fails silently; the Mac host sets it
(``BristlenoseShared.foundationHomeEnvironment``). The first frame after an app or macOS update pays
a ~40 s model compile, once.
"""

from __future__ import annotations

import logging
import platform
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypedDict

from bristlenose.screen_text import EngineUnavailable

logger = logging.getLogger(__name__)


class Line(TypedDict):
    text: str
    conf: float
    box: list[float]  # x, y, w, h in 0–1, top-left origin


@dataclass(frozen=True)
class Frame:
    width: int
    height: int
    bgra: bytes
    t: float = 0.0


class ScreenTextEngine(Protocol):
    name: str
    version: str

    def available(self) -> EngineUnavailable | None:
        """None when the engine can run here; otherwise a reason code (never a sentence: the
        reader says it in the researcher's language; any detail goes to the log)."""
        ...

    def recognize(self, frame: Frame) -> list[Line]: ...


class VisionEngine:
    """Apple Vision, accurate mode, language correction on (measured best of three engines)."""

    name = "vision"
    version = "accurate-1"

    def __init__(self) -> None:
        self._checked = False
        self._why: EngineUnavailable | None = None

    def available(self) -> EngineUnavailable | None:
        # Asked on every screens request: worked out once (neither the platform nor the installed
        # packages change under a running process), and the detail logged once.
        if not self._checked:
            self._why = self._check()
            self._checked = True
        return self._why

    def _check(self) -> EngineUnavailable | None:
        if platform.system() != "Darwin":
            logger.info("Screen text off: Vision is macOS only (%s)", platform.system())
            return "not_macos"
        try:
            import Foundation  # noqa: F401
            import objc  # noqa: F401
            import Quartz  # noqa: F401
            import Vision  # noqa: F401
        except ImportError as exc:
            logger.info('Screen text off: %s (pip install "bristlenose[apple]")', exc)
            return "vision_missing"
        return None

    def recognize(self, frame: Frame) -> list[Line]:
        import Foundation
        import objc
        import Quartz
        import Vision

        with objc.autorelease_pool():
            data = Foundation.NSData.dataWithBytes_length_(frame.bgra, len(frame.bgra))
            provider = Quartz.CGDataProviderCreateWithCFData(data)
            img = Quartz.CGImageCreate(
                frame.width, frame.height, 8, 32, frame.width * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                Quartz.kCGBitmapByteOrder32Little | Quartz.kCGImageAlphaPremultipliedFirst,
                provider, None, False, Quartz.kCGRenderingIntentDefault)
            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
            req = Vision.VNRecognizeTextRequest.alloc().init()
            req.setRecognitionLevel_(0)  # accurate
            req.setUsesLanguageCorrection_(True)
            ok, err = handler.performRequests_error_([req], None)
            if not ok:
                # Vision can refuse with no error at all: in the sandboxed sidecar that has meant a
                # text model it could not compile into the cache (desktop/CLAUDE.md, CFFIXED_USER_HOME).
                raise RuntimeError(f"Vision failed: {err}" if err is not None else
                                   "Vision failed with no error (model cache unwritable? see e5rt in the system log)")
            out: list[Line] = []
            for obs in req.results() or []:
                cands = obs.topCandidates_(1)
                if not cands:
                    continue
                c = cands[0]
                bb = obs.boundingBox()
                out.append({
                    "text": str(c.string()), "conf": round(float(c.confidence()), 3),
                    "box": [round(float(bb.origin.x), 4), round(1 - float(bb.origin.y) - float(bb.size.height), 4),
                            round(float(bb.size.width), 4), round(float(bb.size.height), 4)],
                })
            return out


class FakeEngine:
    """Returns lines a test gives it, keyed by the frame's time (rounded to the second)."""

    name = "fake"
    version = "1"

    def __init__(self, lines_at: Callable[[float], list[Line]]) -> None:
        self._lines_at = lines_at

    def available(self) -> EngineUnavailable | None:
        return None

    def recognize(self, frame: Frame) -> list[Line]:
        return self._lines_at(frame.t)


def select_engine() -> ScreenTextEngine | None:
    """The engine this machine can run, or None. Vision on macOS; nothing elsewhere yet."""
    engine = VisionEngine()
    return engine if engine.available() is None else None
