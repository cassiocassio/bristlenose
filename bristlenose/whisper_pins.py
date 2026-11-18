"""Pinned Hugging Face revisions for the Whisper models Bristlenose verifies itself.

One declaration for the Python side. The Mac app's Swift manifest
(``WhisperPackManifest.largeV3Turbo`` in ``WhisperPackVerifier.swift``) holds the same revision,
sizes and hashes for the Background Assets pack; ``tests/test_whisper_pins.py`` reads that file
and fails if the two copies disagree, so a re-pin changes both or neither.

A repo that is not listed here is fetched exactly as before (``main``, every file, no check).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PinnedFile:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class PinnedModel:
    repo_id: str
    revision: str
    files: tuple[PinnedFile, ...]

    @property
    def allow_patterns(self) -> list[str]:
        return [f.name for f in self.files]


PINNED_MODELS: dict[str, PinnedModel] = {
    "mlx-community/whisper-large-v3-turbo": PinnedModel(
        repo_id="mlx-community/whisper-large-v3-turbo",
        revision="a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb",
        files=(
            PinnedFile(
                "config.json", 268,
                "b34fc29e4e11e0a25e812775dd67f4dd16fc2c8eb43d28ae25ff7d660ecb6379",
            ),
            PinnedFile(
                "weights.safetensors", 1_613_977_612,
                "951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6",
            ),
        ),
    ),
}
