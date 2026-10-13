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

import platform
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypedDict


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

    def available(self) -> str | None:
        """None when the engine can run here; otherwise a reason a person can act on."""
        ...

    def recognize(self, frame: Frame) -> list[Line]: ...


class VisionEngine:
    """Apple Vision, accurate mode, language correction on (measured best of three engines)."""

    name = "vision"
    version = "accurate-1"

    def available(self) -> str | None:
        if platform.system() != "Darwin":
            return "Vision is macOS only"
        try:
            import Foundation  # noqa: F401
            import objc  # noqa: F401
            import Quartz  # noqa: F401
            import Vision  # noqa: F401
        except ImportError:
            return "pyobjc-framework-Vision is not installed (pip install 'bristlenose[apple]')"
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
                raise RuntimeError(f"Vision failed: {err}")
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

    def available(self) -> str | None:
        return None

    def recognize(self, frame: Frame) -> list[Line]:
        return self._lines_at(frame.t)


def select_engine() -> ScreenTextEngine | None:
    """The engine this machine can run, or None. Vision on macOS; nothing elsewhere yet."""
    engine = VisionEngine()
    return engine if engine.available() is None else None
