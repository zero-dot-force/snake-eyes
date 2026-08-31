# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""``caller_count`` source: how widely a function is called in-project.

The inbound call count is bucketed into weights: a function called from many
sites is more likely to expose a contractual effect than one called rarely or
not at all. A zero count yields no signal.
"""

from __future__ import annotations

from ._types import SignalResult

HEAVY_THRESHOLD = 20
WIDE_THRESHOLD = 5

HEAVY_WEIGHT = 25
WIDE_WEIGHT = 15
LIGHT_WEIGHT = 5


def extract(caller_count: int) -> SignalResult | None:
    """Bucket an inbound-call count into a caller signal.

    ``0`` (or negative) callers produce ``None``; ``>=20`` -> 25; ``>=5`` -> 15;
    otherwise -> 5.
    """

    if caller_count <= 0:
        return None
    if caller_count >= HEAVY_THRESHOLD:
        return SignalResult(
            weight=HEAVY_WEIGHT,
            reasoning=f"called from {caller_count} sites (heavily used)",
        )
    if caller_count >= WIDE_THRESHOLD:
        return SignalResult(
            weight=WIDE_WEIGHT,
            reasoning=f"called from {caller_count} sites (widely used)",
        )
    return SignalResult(
        weight=LIGHT_WEIGHT,
        reasoning=f"called from {caller_count} site(s)",
    )
