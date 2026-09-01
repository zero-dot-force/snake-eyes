"""Effect-type inference for test mapping rows.

FRESH — not lifted from gaze-py. No provenance header required.

Infers ``side_effect_type`` from an assertion's ``assertion_type`` and the
target function's ``FunctionRecord.side_effects`` (detector output — no
re-parsing). Consumes ``TIER_MAP`` safely (``get``) with no ``KeyError`` on
unknown type strings.

Public API:
- ``infer_side_effect_type(assertion_type, target_effects) -> str``
"""

from __future__ import annotations

from ..analysis.effects import TIER_MAP, SideEffectType, Tier
from ..analysis.models import Effect

# Assertion types that form the value-assertion group
_VALUE_TYPES: frozenset[str] = frozenset(
    {"equality", "comparison", "identity", "membership"}
)


def _effect_type_str(et: SideEffectType) -> str:
    return str(et)


def infer_side_effect_type(
    assertion_type: str,
    target_effects: tuple[Effect, ...],
) -> str:
    """Infer ``side_effect_type`` from assertion kind and target side effects.

    Chains:
    - ``error_check``: ``ErrorReturn`` if present, else ``ErrorSignal`` if
      present, else ``"ErrorReturn"`` (fallback).
    - ``equality``/``comparison``/``identity``/``membership``: ``ReturnValue``
      if present, else first P0 effect, else ``"ReturnValue"`` (fallback).
    - ``generic``: first detected effect if any, else ``"ReturnValue"``
      (fallback).
    """
    effect_types: list[str] = [e.type for e in target_effects]

    if assertion_type == "error_check":
        err_return = _effect_type_str(SideEffectType.ErrorReturn)
        err_signal = _effect_type_str(SideEffectType.ErrorSignal)
        if err_return in effect_types:
            return err_return
        if err_signal in effect_types:
            return err_signal
        return err_return

    if assertion_type in _VALUE_TYPES:
        ret_val = _effect_type_str(SideEffectType.ReturnValue)
        if ret_val in effect_types:
            return ret_val
        # First P0 effect
        for effect in target_effects:
            try:
                se_type = SideEffectType(effect.type)
                tier = TIER_MAP.get(se_type)
                if tier == Tier.P0:
                    return effect.type
            except ValueError:
                # Unknown type string — safe fallback per spec
                continue
        return ret_val

    # generic
    if effect_types:
        return effect_types[0]
    return _effect_type_str(SideEffectType.ReturnValue)
