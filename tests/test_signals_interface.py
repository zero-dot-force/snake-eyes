from __future__ import annotations

from snake_eyes.signals import interface


def test_abc_base_fires_with_weight_30() -> None:
    result = interface.extract(("ABC",))
    assert result is not None
    assert result.weight == 30
    assert result.reasoning


def test_abcmeta_metaclass_fires_with_weight_30() -> None:
    result = interface.extract(("ABCMeta",))
    assert result is not None
    assert result.weight == 30


def test_protocol_base_fires_with_weight_30() -> None:
    result = interface.extract(("Protocol",))
    assert result is not None
    assert result.weight == 30


def test_dotted_base_name_uses_simple_name() -> None:
    result = interface.extract(("abc.ABC",))
    assert result is not None
    assert result.weight == 30


def test_plain_base_no_signal() -> None:
    assert interface.extract(("object",)) is None


def test_no_bases_no_signal() -> None:
    assert interface.extract(None) is None
    assert interface.extract(()) is None
