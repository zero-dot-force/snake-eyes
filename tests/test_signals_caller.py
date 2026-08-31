from __future__ import annotations

from snake_eyes.signals import caller


def test_zero_callers_no_signal() -> None:
    assert caller.extract(0) is None


def test_negative_callers_no_signal() -> None:
    assert caller.extract(-3) is None


def test_five_callers_weight_15() -> None:
    result = caller.extract(5)
    assert result is not None
    assert result.weight == 15
    assert result.reasoning


def test_twenty_callers_weight_25() -> None:
    result = caller.extract(20)
    assert result is not None
    assert result.weight == 25


def test_single_caller_light_weight_5() -> None:
    result = caller.extract(1)
    assert result is not None
    assert result.weight == 5
