"""Python classification-signal extraction for the ``classify_signals`` method.

snake_eyes emits the five raw, mechanical signals that Gaze's Go core feeds into
its universal classification formula. The extractors are reconstructed from the
documented gaze-py ``classify/signals`` behavior; the scoring engine is
deliberately not reproduced (Gaze owns scoring). Importing this package is
side-effect free.
"""

from __future__ import annotations

from . import caller, docstring, interface, naming, visibility
from ._types import SignalResult
from .adapter import extract_signals

__all__ = [
    "SignalResult",
    "caller",
    "docstring",
    "extract_signals",
    "interface",
    "naming",
    "visibility",
]
