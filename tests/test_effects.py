"""Tests for the 48-type side effect taxonomy."""

from __future__ import annotations

from snake_eyes.analysis.effects import TIER_MAP, SideEffectType, Tier


def test_48_members() -> None:
    assert len(SideEffectType) == 48


def test_every_member_in_tier_map() -> None:
    for member in SideEffectType:
        assert member in TIER_MAP


def test_tier_map_has_no_unknown_members() -> None:
    assert set(TIER_MAP) == set(SideEffectType)


def test_new_types_have_correct_tiers() -> None:
    assert TIER_MAP[SideEffectType.ErrorSignal] == Tier.P0
    assert TIER_MAP[SideEffectType.GeneratorYield] == Tier.P1
    assert TIER_MAP[SideEffectType.ContainerMutation] == Tier.P1
    assert TIER_MAP[SideEffectType.StreamOutput] == Tier.P1
    assert TIER_MAP[SideEffectType.AsyncGeneratorYield] == Tier.P2
    assert TIER_MAP[SideEffectType.MetaprogrammingMutation] == Tier.P2
    assert TIER_MAP[SideEffectType.DescriptorEffect] == Tier.P2
    assert TIER_MAP[SideEffectType.ResourceManagement] == Tier.P2
    assert TIER_MAP[SideEffectType.ImportSideEffect] == Tier.P2
    assert TIER_MAP[SideEffectType.MonkeyPatch] == Tier.P2


def test_p0_set_complete() -> None:
    p0 = {member for member in SideEffectType if TIER_MAP[member] == Tier.P0}
    assert p0 == {
        SideEffectType.ReturnValue,
        SideEffectType.ErrorReturn,
        SideEffectType.SentinelError,
        SideEffectType.ReceiverMutation,
        SideEffectType.PointerArgMutation,
        SideEffectType.ErrorSignal,
    }


def test_type_values_are_canonical_strings() -> None:
    assert SideEffectType.ReturnValue.value == "ReturnValue"
    assert SideEffectType.MonkeyPatch.value == "MonkeyPatch"
    assert str(SideEffectType.ErrorSignal) == "ErrorSignal"


def test_package_reexports_taxonomy() -> None:
    from snake_eyes.analysis import TIER_MAP as pkg_tier_map
    from snake_eyes.analysis import SideEffectType as pkg_side_effect_type

    assert pkg_side_effect_type is SideEffectType
    assert pkg_tier_map is TIER_MAP
