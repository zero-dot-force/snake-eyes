# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""Effect-type routing shared by the ``naming`` and ``docstring`` extractors.

gaze-py switches its naming/docstring heuristics on a small set of effect
categories. snake_eyes extends the universal taxonomy with ten Python-specific
``SideEffectType`` values (plus the gaze-py-original ``ClosureCaptureMutation``);
each is routed here to its closest existing category so the extractors never
raise ``KeyError`` and never silently drop a mappable type. Any value with no
category -- including a string that is not a known ``SideEffectType`` -- routes
to :data:`OTHER`, for which the extractors emit no signal.
"""

from __future__ import annotations

from ..analysis.effects import SideEffectType

RETURNING = "returning"
ERROR = "error"
MUTATING = "mutating"
OTHER = "other"

# Values whose "contract" is producing/returning a value to the caller.
_RETURNING: frozenset[SideEffectType] = frozenset(
    {
        SideEffectType.ReturnValue,
        SideEffectType.GeneratorYield,
        SideEffectType.StreamOutput,
        SideEffectType.AsyncGeneratorYield,
    }
)

# Values whose contract is signalling an error condition.
_ERROR: frozenset[SideEffectType] = frozenset(
    {
        SideEffectType.ErrorReturn,
        SideEffectType.ErrorSignal,
        SideEffectType.SentinelError,
    }
)

# Values whose contract is mutating state (receiver, args, globals, closures,
# containers, or the Python-specific reflection/descriptor/import mutations).
_MUTATING: frozenset[SideEffectType] = frozenset(
    {
        SideEffectType.ReceiverMutation,
        SideEffectType.PointerArgMutation,
        SideEffectType.SliceMutation,
        SideEffectType.MapMutation,
        SideEffectType.GlobalMutation,
        SideEffectType.ContainerMutation,
        SideEffectType.DeferredReturnMutation,
        SideEffectType.ClosureCaptureMutation,
        SideEffectType.ReflectionMutation,
        SideEffectType.UnsafeMutation,
        SideEffectType.MonkeyPatch,
        SideEffectType.DescriptorEffect,
        SideEffectType.ResourceManagement,
        SideEffectType.MetaprogrammingMutation,
        SideEffectType.ImportSideEffect,
        SideEffectType.EnvVarMutation,
    }
)


def effect_category(effect_type: str) -> str:
    """Return the routing category for a side-effect type string.

    Unknown strings (values outside the taxonomy) and taxonomy values without a
    naming/docstring branch both route to :data:`OTHER`, never raising.
    """

    try:
        et = SideEffectType(effect_type)
    except ValueError:
        return OTHER
    if et in _RETURNING:
        return RETURNING
    if et in _ERROR:
        return ERROR
    if et in _MUTATING:
        return MUTATING
    return OTHER
