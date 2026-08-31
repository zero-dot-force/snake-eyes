# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""``docstring`` source: docstring keywords vs. effect category.

When a function's docstring documents the behaviour that produced an effect
(mentions returning/yielding for a returning effect, raising for an error
effect, or mutating for a mutation effect), the effect is more likely
contractual. A missing docstring or an unrelated category produces no signal.
"""

from __future__ import annotations

from ._routing import ERROR, MUTATING, RETURNING, effect_category
from ._types import SignalResult

MATCH_WEIGHT = 15

_RETURN_KEYWORDS = ("return", "returns", "yield", "yields")
_ERROR_KEYWORDS = ("raise", "raises", "error", "errors", "exception", "exceptions")
_MUTATE_KEYWORDS = ("mutat", "modif", "update", "append", "insert", "writes", "stores")


def extract(docstring: str | None, effect_type: str) -> SignalResult | None:
    """Return a docstring signal when the docstring documents the effect."""

    if not docstring:
        return None
    text = docstring.lower()
    category = effect_category(effect_type)
    if category == RETURNING and any(kw in text for kw in _RETURN_KEYWORDS):
        return SignalResult(
            weight=MATCH_WEIGHT,
            reasoning="docstring documents a returned/yielded value",
        )
    if category == ERROR and any(kw in text for kw in _ERROR_KEYWORDS):
        return SignalResult(
            weight=MATCH_WEIGHT,
            reasoning="docstring documents raised errors",
        )
    if category == MUTATING and any(kw in text for kw in _MUTATE_KEYWORDS):
        return SignalResult(
            weight=MATCH_WEIGHT,
            reasoning="docstring documents a mutation",
        )
    return None
