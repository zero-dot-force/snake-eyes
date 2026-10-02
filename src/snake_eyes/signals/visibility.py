# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""``visibility`` source: public vs. private surface of a function.

Public functions (and those exported via ``__all__``) present their side
effects as part of the module's contract; leading-underscore names are private
by convention and weigh in the opposite direction. Dunder methods follow their
enclosing class's surface; nested helpers are private; a nested closure that
can escape stays `unclaimed` (emits no signal).
"""

from __future__ import annotations

from ..analysis.effects import SideEffectType
from ._types import (
    EnclosingClassVisibility,
    FunctionSurface,
    SignalResult,
)

PUBLIC_WEIGHT = 10
PRIVATE_WEIGHT = -10

#: Effect type whose nested surface is genuinely unknowable (a closure can
#: escape and be caller-visible), so no signal is emitted.
_CLOSURE_CAPTURE = SideEffectType.ClosureCaptureMutation.value


def extract(
    func_name: str,
    in_all: bool,
    surface: FunctionSurface,
    enclosing_class_visibility: EnclosingClassVisibility,
    effect_type: str,
) -> SignalResult | None:
    """Return a visibility signal for a function.

    ``in_all`` is ``True`` when the (module-level) function is listed in the
    module's ``__all__``. ``surface`` is where the function is defined;
    ``enclosing_class_visibility`` is the enclosing class's visibility for
    ``method`` surfaces (``none`` otherwise). Dunder-ness is re-derived from
    ``func_name``. ``effect_type`` distinguishes a nested closure-capture
    mutation, for which no signal is emitted.
    """
    is_dunder = func_name.startswith("__") and func_name.endswith("__")

    if surface is FunctionSurface.NESTED:
        if effect_type == _CLOSURE_CAPTURE:
            return None
        return SignalResult(
            weight=PRIVATE_WEIGHT,
            reasoning=f"nested helper ({func_name})",
        )

    if surface is FunctionSurface.METHOD:
        if is_dunder:
            if enclosing_class_visibility is EnclosingClassVisibility.PUBLIC:
                return SignalResult(
                    weight=PUBLIC_WEIGHT,
                    reasoning=f"dunder method of a public class ({func_name})",
                )
            # PRIVATE (and, defensively, NONE which is out-of-contract for
            # METHOD) leans private.
            return SignalResult(
                weight=PRIVATE_WEIGHT,
                reasoning=f"dunder method of a private class ({func_name})",
            )
        if enclosing_class_visibility is EnclosingClassVisibility.PRIVATE:
            return SignalResult(
                weight=PRIVATE_WEIGHT,
                reasoning=f"method of a private class ({func_name})",
            )

    if is_dunder:
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
