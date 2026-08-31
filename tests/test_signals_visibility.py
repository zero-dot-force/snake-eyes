from __future__ import annotations

from snake_eyes.signals import visibility


def test_public_name_positive_weight() -> None:
    result = visibility.extract("public_fn", in_all=False)
    assert result is not None
    assert result.weight == 10
    assert result.reasoning


def test_private_name_negative_weight() -> None:
    result = visibility.extract("_private", in_all=False)
    assert result is not None
    assert result.weight == -10


def test_public_and_private_weights_differ() -> None:
    pub = visibility.extract("public_fn", in_all=False)
    priv = visibility.extract("_private", in_all=False)
    assert pub is not None
    assert priv is not None
    assert pub.weight != priv.weight


def test_all_membership_marks_public() -> None:
    result = visibility.extract("_exported", in_all=True)
    assert result is not None
    assert result.weight == 10


def test_dunder_no_signal() -> None:
    assert visibility.extract("__init__", in_all=False) is None
