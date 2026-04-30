"""Shared utilities for the thematic-analysis spike.

Quote dataclass, LLM wrapper, embeddings, ThemeSet IO. Nothing here
imports from bristlenose/ — the spike stands alone.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from anthropic import Anthropic

# ---------- Data shapes ---------------------------------------------------


@dataclass
class Quote:
    """One quote in the spike corpus. `index` is its position in the corpus."""

    index: int
    participant_id: str
    timecode: str
    topic_label: str
    text: str
    quote_type: str  # 'screen_specific' | 'general_context' (kept for reference, not used to filter)


@dataclass
class Theme:
    label: str
    description: str
    quote_indices: list[int] = field(default_factory=list)

    def participants(self, corpus: list[Quote]) -> set[str]:
        return {corpus[i].participant_id for i in self.quote_indices if 0 <= i < len(corpus)}


@dataclass
class ThemeSet:
    """A prototype's output. Saved as JSON, loaded by render.py."""

    prototype: str  # 'baseline' | 'a' | ... | 'e'
    label: str  # human-readable e.g. "B — Code-first"
    themes: list[Theme]
    meta: dict[str, Any]  # cost, tokens, elapsed, n_calls, notes

    def to_dict(self) -> dict[str, Any]:
        return {
            "prototype": self.prototype,
            "label": self.label,
            "themes": [asdict(t) for t in self.themes],
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThemeSet:
        return cls(
            prototype=d["prototype"],
            label=d["label"],
            themes=[Theme(**t) for t in d["themes"]],
            meta=d["meta"],
        )


def save_themes(ts: ThemeSet, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"themes_{ts.prototype}.json"
    with open(path, "w") as f:
        json.dump(ts.to_dict(), f, indent=2, ensure_ascii=False)
    return path


def load_themes(path: Path) -> ThemeSet:
    with open(path) as f:
        return ThemeSet.from_dict(json.load(f))


def save_corpus(corpus: list[Quote], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([asdict(q) for q in corpus], f, indent=2, ensure_ascii=False)


def load_corpus(path: Path) -> list[Quote]:
    with open(path) as f:
        return [Quote(**d) for d in json.load(f)]


# ---------- LLM client wrapper -------------------------------------------


MODEL = "claude-sonnet-4-5-20250929"


class LLM:
    """Tiny wrapper that tracks tokens and cost across calls."""

    # Sonnet 4.5 pricing per million tokens
    PRICE_IN = 3.0
    PRICE_OUT = 15.0

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            # Try Bristlenose's keychain entry — best-effort, not required
            import subprocess

            try:
                api_key = subprocess.run(
                    [
                        "security",
                        "find-generic-password",
                        "-s",
                        "Bristlenose Anthropic API Key",
                        "-w",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except Exception:
                pass
        if not api_key:
            raise RuntimeError(
                "No ANTHROPIC_API_KEY in env and not in keychain. "
                "Run: export ANTHROPIC_API_KEY=sk-ant-..."
            )
        self.client = Anthropic(api_key=api_key)
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def call(
        self,
        system: str,
        user: str,
        max_tokens: int = 8000,
        temperature: float = 1.0,
    ) -> str:
        resp = self.client.messages.create(
            model=MODEL,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=600.0,
        )
        self.input_tokens += resp.usage.input_tokens
        self.output_tokens += resp.usage.output_tokens
        self.calls += 1
        # Concatenate all text blocks
        out: list[str] = []
        for block in resp.content:
            if hasattr(block, "text"):
                out.append(block.text)
        return "".join(out)

    def cost(self) -> float:
        return (
            self.input_tokens * self.PRICE_IN / 1_000_000
            + self.output_tokens * self.PRICE_OUT / 1_000_000
        )

    def stats(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost(), 4),
        }


def parse_json_block(text: str) -> Any:
    """Extract and parse a JSON object/array from an LLM response.

    Handles ```json fenced blocks and bare JSON.
    """
    s = text.strip()
    if "```" in s:
        # Find the json block
        start = s.find("```")
        # Skip the language tag if present
        nl = s.find("\n", start)
        end = s.find("```", nl)
        if end > nl:
            s = s[nl + 1 : end].strip()
    # Find first { or [
    for i, ch in enumerate(s):
        if ch in "{[":
            s = s[i:]
            break
    # Find matching last } or ]
    for i in range(len(s) - 1, -1, -1):
        if s[i] in "}]":
            s = s[: i + 1]
            break
    return json.loads(s)


# ---------- Embeddings (local, free) -------------------------------------


_embedder = None


def embed(texts: list[str]) -> np.ndarray:
    """Return (N, D) float32 embeddings using sentence-transformers."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)


# ---------- Convenience timing -------------------------------------------


class Stopwatch:
    def __init__(self) -> None:
        self.t0 = time.monotonic()

    def lap(self) -> float:
        return round(time.monotonic() - self.t0, 2)
