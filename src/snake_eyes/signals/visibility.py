# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""``visibility`` source: public vs. private surface of a function.

Public functions (and those exported via ``__all__``) present their side
effects as part of the module's contract; leading-underscore names are private
by convention and weigh in the opposite direction. Dunder methods are neither
and produce no signal.
"""

from __future__ import annotations

from ._types import SignalResult

PUBLIC_WEIGHT = 10
PRIVATE_WEIGHT = -10


def extract(func_name: str, in_all: bool) -> SignalResult | None:
    """Return a visibility signal for a function name.

    ``in_all`` is ``True`` when the (module-level) function is listed in the
    module's ``__all__``. Dunder methods (``__x__``) return ``None``.
    """

    if func_name.startswith("__") and func_name.endswith("__"):
        return None
    if in_all:
        return SignalResult(
            weight=PUBLIC_WEIGHT,
            reasoning=f"exported in __all__ ({func_name})",
        )
    if func_name.startswith("_"):
        return SignalResult(
            weight=PRIVATE_WEIGHT,
            reasoning=f"private by naming convention ({func_name})",
        )
    return SignalResult(
        weight=PUBLIC_WEIGHT,
        reasoning=f"public by naming convention ({func_name})",
    )
