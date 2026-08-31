# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.
# Modified 2026 by zero-dot-force: reconstructed for snake_eyes from documented
# gaze-py classify/signals behavior; adapted to snake_eyes SideEffectType; new
# Python effect types mapped to their closest gaze-py branch.
"""``interface`` source: membership on an abstract base class or Protocol.

A function defined on an ``abc.ABC``/``abc.ABCMeta`` class or a
``typing.Protocol`` is part of a declared interface, a strong signal that its
side effects are contractual rather than incidental.
"""

from __future__ import annotations

from ._types import SignalResult

INTERFACE_WEIGHT = 30

_INTERFACE_BASES = frozenset({"ABC", "ABCMeta", "Protocol"})


def extract(class_bases: tuple[str, ...] | None) -> SignalResult | None:
    """Return an interface signal when an enclosing-class base is abstract.

    ``class_bases`` is the tuple of simple names of the enclosing class's bases
    and metaclass (e.g. ``("ABC",)`` or ``("ABCMeta",)``), or ``None`` when the
    function is not a method. Dotted names are reduced to their final segment so
    ``abc.ABC`` and ``ABC`` match identically.
    """

    if not class_bases:
        return None
    for base in class_bases:
        simple = base.rsplit(".", 1)[-1]
        if simple in _INTERFACE_BASES:
            return SignalResult(
                weight=INTERFACE_WEIGHT,
                reasoning=f"defined on an abstract base/protocol ({simple})",
            )
    return None
