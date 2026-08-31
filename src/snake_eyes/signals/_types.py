"""Shared value type for classification-signal extractors.

Each extractor returns a :class:`SignalResult` (a weight plus a short,
non-empty reason) or ``None`` when no signal applies. The adapter attaches the
``source`` and ``side_effect_type`` fields when building the protocol wire dict,
so the extractors stay free of protocol-shape concerns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalResult:
    """A raw extractor result.

    ``weight`` is an integer preserved verbatim from the extractor heuristic
    (never summed, clamped, or otherwise post-processed by snake-eyes).
    ``reasoning`` is always a short, non-empty human-readable string.
    """

    weight: int
    reasoning: str
