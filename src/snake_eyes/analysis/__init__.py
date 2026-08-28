"""Analysis package: the effect taxonomy public API."""

from __future__ import annotations

from .effects import TIER_MAP as TIER_MAP
from .effects import SideEffectType as SideEffectType

__all__ = ["SideEffectType", "TIER_MAP"]
