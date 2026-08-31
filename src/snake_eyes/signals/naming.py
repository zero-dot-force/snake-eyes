# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""``naming_convention`` source: function-name prefix vs. effect category.

An accessor-style name (``get_``, ``is_``, ...) that returns a value agrees
with the effect and weighs positively; the same name paired with a mutation
effect contradicts it and weighs negatively (and vice versa for mutator-style
names). Names without a recognised prefix -- or effects that route to
``OTHER`` -- produce no signal.
"""

from __future__ import annotations

from ._routing import ERROR, MUTATING, RETURNING, effect_category
from ._types import SignalResult

POSITIVE_WEIGHT = 15
NEGATIVE_WEIGHT = -10

_ACCESSOR_PREFIXES = (
    "get_",
    "is_",
    "has_",
    "read_",
    "fetch_",
    "load_",
    "compute_",
    "calc_",
    "to_",
)
_MUTATOR_PREFIXES = (
    "set_",
    "add_",
    "append_",
    "update_",
    "delete_",
    "remove_",
    "write_",
    "save_",
    "store_",
    "put_",
    "insert_",
    "pop_",
    "clear_",
    "reset_",
)


def _prefix_kind(name: str) -> str | None:
    if name.startswith(_ACCESSOR_PREFIXES):
        return "accessor"
    if name.startswith(_MUTATOR_PREFIXES):
        return "mutator"
    return None


def extract(func_name: str, effect_type: str) -> SignalResult | None:
    """Return a naming signal comparing the name prefix to the effect category."""

    kind = _prefix_kind(func_name)
    if kind is None:
        return None
    category = effect_category(effect_type)
    if category in (RETURNING, ERROR):
        if kind == "accessor":
            return SignalResult(
                weight=POSITIVE_WEIGHT,
                reasoning=f"accessor name '{func_name}' agrees with a returned value",
            )
        return SignalResult(
            weight=NEGATIVE_WEIGHT,
            reasoning=f"mutator name '{func_name}' contradicts a returned value",
        )
    if category == MUTATING:
        if kind == "mutator":
            return SignalResult(
                weight=POSITIVE_WEIGHT,
                reasoning=f"mutator name '{func_name}' agrees with a mutation",
            )
        return SignalResult(
            weight=NEGATIVE_WEIGHT,
            reasoning=f"accessor name '{func_name}' contradicts a mutation",
        )
    return None
